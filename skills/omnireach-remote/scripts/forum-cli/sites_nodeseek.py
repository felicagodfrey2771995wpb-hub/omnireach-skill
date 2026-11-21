"""NodeSeek 只读站点模块。

来源说明（重要，见 --verbose 输出的 meta.note）
------------------------------------------------
NodeSeek 没有服务端全文检索：
  * https://www.nodeseek.com/search?q=X  -> HTTP 302 跳到
    https://www.google.com/search?q=site:www.nodeseek.com&q=X
    而 Google 对匿名程序化 GET 返回 "enablejs" 挑战页（实测带完整浏览器
    UA 仍是挑战页）。跳转也没有透传 page 参数，所以这条路没有服务端分页。
  * /api/* 下只有 account / notification / promotion / statistics 之类，
    post 与 search 相关端点实测全部 404。

可用的是服务端渲染的列表页与主题页（Nuxt SSR，纯静态 HTML 可读）：
  * 列表： https://www.nodeseek.com/ 与 https://www.nodeseek.com/page-N
           （服务端分页，pager 最多到 100 页，约 4970 篇最新主题）
           ?sortBy=postTime|replyTime 会被 SSR 采纳。
           注意 /categories/<key>?page=N 不生效（服务端忽略 page）。
  * 主题： https://www.nodeseek.com/post-<id>-<page>  （每页 10 楼）

因此 SEARCH 的做法是：抓取站方自己的分页列表 HTML，在本地按标题做关键词
过滤。这**不是**站内全文检索，语料仅限可分页窗口内、且只匹配标题。
"""

from __future__ import annotations

import gzip
import html
import html.parser
import re
import time
import urllib.error
import urllib.parse
import urllib.request

import sys

import forum_cli as _forum_cli

# forum_cli.py 既可能被当脚本跑（模块名 __main__），也可能被当库 import。
# 两种情况下 Blocked 是两个不同的类对象；raise 非框架那一个的话，
# 框架的 `except Blocked` 抓不到，退出码会退化成 1 而不是 75。
# 这里优先用框架运行时的那个，保证退出码语义正确。
Blocked = getattr(sys.modules.get("__main__"), "Blocked", None) or _forum_cli.Blocked

LIST_PAGES_PER_SEARCH_PAGE = 5   # 每个 --page 扫几个列表页
_SCAN_CAP = 20                    # 单次 search 最多请求的列表页数

_TIMEOUT = 20
_RETRIES = 2
_BACKOFF = 1.5

_ITEM_RE = re.compile(r'<li class="post-list-item">(.*?)</li>', re.S)
_TITLE_RE = re.compile(
    r'class="post-title"><a href="/post-(\d+)-\d+"[^>]*>(.*?)</a>', re.S
)
_AUTHOR_RE = re.compile(r'info-author.*?<a href="/space/\d+">(.*?)</a>', re.S)
_COMMENTS_RE = re.compile(r'title="(\d+) comments"')
_TAG_RE = re.compile(r"<[^>]+>")

# 主题页
_POST_TITLE_RE = re.compile(
    r'<div class="post-title"><h1><a href="/post-\d+-\d+" class="post-title-link">(.*?)</a>',
    re.S,
)
_OP_ITEM_RE = re.compile(
    r'<div id="0"[^>]*data-comment-id="\d+"[^>]*class="content-item"[^>]*>(.*)',
    re.S,
)
_COMMENT_RE = re.compile(
    r'<li data-comment-id="(\d+)" id="(\d+)" class="content-item">(.*?)(?=<li data-comment-id=|</ul>)',
    re.S,
)
_AUTHOR_NAME_RE = re.compile(r'class="author-name">(.*?)</a>', re.S)
_DATE_RE = re.compile(r'<span class="date-created"><time title="([^"]+)"', re.S)
# 首帖块在 </article> 处被截断，评论块在下一个 <li> / </ul> 处被截断，
# 所以正文用「抓到块尾」的贪婪写法，两种块都能吃到完整正文。
_CONTENT_RE = re.compile(r"<article class=\"post-content\">(.*)", re.S)
_PAGER_LAST_RE = re.compile(r'class="pager-pos">\s*(?:<span class="ellipsis">\.\.</span>)?(\d+)\s*</a>')


class _TextExtractor(html.parser.HTMLParser):
    """把一段 HTML 片段压成纯文本，保留块级换行。"""

    _BREAK = {"p", "br", "li", "h1", "h2", "h3", "h4", "h5", "h6",
              "div", "tr", "blockquote", "hr", "pre"}
    _SKIP = {"script", "style", "svg", "noscript"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self._skip_depth += 1
        elif tag in self._BREAK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self._SKIP:
            self._skip_depth = max(0, self._skip_depth - 1)
        elif tag in self._BREAK:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._skip_depth:
            self.parts.append(data)

    def text(self) -> str:
        out = "".join(self.parts)
        out = re.sub(r"[ \t\u00a0]+", " ", out)
        out = re.sub(r" *\n *", "\n", out)
        out = re.sub(r"\n{3,}", "\n\n", out)
        return out.strip()


def _to_text(fragment: str) -> str:
    parser = _TextExtractor()
    try:
        parser.feed(fragment)
        parser.close()
    except Exception:
        return html.unescape(_TAG_RE.sub(" ", fragment)).strip()
    return parser.text()


def _get(url: str, ua: str):
    """GET 一个页面。返回 (status, html_text)。"""
    last = None
    for attempt in range(_RETRIES + 1):
        req = urllib.request.Request(
            url,
            method="GET",
            headers={
                "User-Agent": ua,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Accept-Encoding": "gzip",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
                raw = resp.read()
                if resp.headers.get("Content-Encoding") == "gzip":
                    raw = gzip.decompress(raw)
                return resp.status, raw.decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            body = b""
            try:
                body = exc.read()
                if exc.headers.get("Content-Encoding") == "gzip":
                    body = gzip.decompress(body)
            except Exception:
                pass
            snippet = body.decode("utf-8", "replace")[:160]
            if exc.code in (401, 403, 429, 503):
                raise Blocked(
                    f"NodeSeek HTTP {exc.code} 拒绝匿名访问: {snippet}"
                ) from exc
            return exc.code, snippet
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last = exc
        if attempt < _RETRIES:
            time.sleep(_BACKOFF * (attempt + 1))
    raise last if last else RuntimeError("NodeSeek 请求失败")


def _parse_list(body: str):
    out = []
    for block in _ITEM_RE.findall(body):
        m = _TITLE_RE.search(block)
        if not m:
            continue
        author = _AUTHOR_RE.search(block)
        comments = _COMMENTS_RE.search(block)
        out.append(
            {
                "id": m.group(1),
                "title": html.unescape(_TAG_RE.sub("", m.group(2))).strip(),
                "url": f"https://www.nodeseek.com/post-{m.group(1)}-1",
                "author": html.unescape(_TAG_RE.sub("", author.group(1))).strip()
                if author else None,
                "replies": int(comments.group(1)) if comments else None,
            }
        )
    return out


def _matches(item_title: str, query: str) -> bool:
    """标题本地过滤：query 按空白切词，要求全部词都出现（不区分大小写）。"""
    tokens = [t for t in re.split(r"\s+", (query or "").strip()) if t]
    if not tokens:
        return True
    low = item_title.lower()
    return all(t.lower() in low for t in tokens)


# --------------------------------------------------------------------------
# 公开接口
# --------------------------------------------------------------------------

def SEARCH(site_cfg: dict, query: str, page: int, limit: int):
    page = max(1, int(page))
    limit = max(1, int(limit))
    first = (page - 1) * LIST_PAGES_PER_SEARCH_PAGE + 1
    last = first + LIST_PAGES_PER_SEARCH_PAGE - 1
    last = min(last, _SCAN_CAP)

    base = site_cfg["base"].rstrip("/")
    ua = site_cfg["user_agent"]
    items, endpoints, statuses = [], [], []
    seen_urls = set()

    for n in range(first, last + 1):
        url = base + "/" if n == 1 else f"{base}/page-{n}"
        status, body = _get(url, ua)
        endpoints.append(url)
        statuses.append(status)
        if status != 200:
            continue
        for it in _parse_list(body):
            if it["url"] in seen_urls:
                continue
            if _matches(it["title"], query):
                seen_urls.add(it["url"])
                items.append(it)

    items = items[:limit]

    meta = {
        "endpoint": endpoints[0] if endpoints else None,
        "endpoints_scanned": endpoints,
        "status": statuses[0] if statuses else None,
        "statuses": statuses,
        "pagination": (
            f"服务端支持分页：列表页 /page-N（SSR，pager 最多 100 页，约 4970 篇最新主题）。"
            f"本模块每个 --page 扫 {LIST_PAGES_PER_SEARCH_PAGE} 个连续列表页；"
            f"--page {page} -> 列表页 {first}..{last}"
        ),
        "note": (
            "NodeSeek 无服务端全文搜索：/search?q=X 返回 302 跳到 "
            "https://www.google.com/search?q=site:www.nodeseek.com&q=X，"
            "而 Google 对匿名程序化 GET 一律返回 enablejs 挑战页（实测带完整浏览器 UA 仍是挑战页）；"
            "跳转也未透传 page 参数。/api/* 下无 post/search 端点（实测 404）。"
            "因此本 SEARCH = 抓站方自己的 SSR 分页列表 + 本地按标题过滤，"
            "**不是站内全文检索**：语料仅限列表分页窗口内（最近约 4970 篇），"
            "且只匹配标题、不匹配正文。/categories/<key>?page=N 服务端忽略 page，不分页。"
        ),
        "source": "site-ssr-list+client-side-title-filter",
    }
    return items, meta


def RESOLVE(site_cfg: dict, ref: str):
    raw = (ref or "").strip()
    base = site_cfg["base"].rstrip("/")
    m = re.search(r"/post-(\d+)(?:-(\d+))?", raw)
    if m:
        pid, pg = m.group(1), m.group(2) or "1"
    elif re.fullmatch(r"\d+", raw):
        pid, pg = raw, "1"
    else:
        raise ValueError(
            f"无法从 {ref!r} 解析 NodeSeek post id；"
            "支持 https://www.nodeseek.com/post-<id>[-<page>] 或纯数字 id"
        )
    return f"{base}/post-{pid}-{pg}", pid


def POST(site_cfg: dict, ref: str, page: int, limit: int):
    page = max(1, int(page))
    limit = max(1, int(limit))
    url, pid = RESOLVE(site_cfg, ref)
    url = re.sub(r"-(\d+)$", f"-{page}", url)

    status, body = _get(url, site_cfg["user_agent"])
    if status != 200:
        raise Blocked(f"NodeSeek 主题页不可读：{url} -> HTTP {status}")

    tm = _POST_TITLE_RE.search(body)
    if not tm:
        raise Blocked(f"NodeSeek 主题页 {url} 结构无法解析（找不到 post-title h1）")
    title = html.unescape(_TAG_RE.sub("", tm.group(1))).strip()

    posts = []

    op = _OP_ITEM_RE.search(body)
    if op:
        block = op.group(1)
        author = _AUTHOR_NAME_RE.search(block)
        date = _DATE_RE.search(block)
        content = _CONTENT_RE.search(block)
        text = _to_text(content.group(1)) if content else ""
        if text:
            posts.append(
                {
                    "floor": 0,
                    "author": html.unescape(_TAG_RE.sub("", author.group(1))).strip()
                    if author else None,
                    "created": date.group(1).strip() if date else None,
                    "body": text,
                    "is_op": True,
                }
            )

    for cid, floor, block in _COMMENT_RE.findall(body):
        author = _AUTHOR_NAME_RE.search(block)
        date = _DATE_RE.search(block)
        content = _CONTENT_RE.search(block)
        text = _to_text(content.group(1)) if content else ""
        if not text:
            continue
        posts.append(
            {
                "floor": int(floor),
                "comment_id": cid,
                "author": html.unescape(_TAG_RE.sub("", author.group(1))).strip()
                if author else None,
                "created": date.group(1).strip() if date else None,
                "body": text,
                "is_op": False,
            }
        )

    shown = posts[:limit]
    main = next((p for p in posts if p["floor"] == 0), None)
    if main is None and shown:
        # 非首页时站方不在该页重复首帖，body 退回本页第一条楼层
        main = shown[0]

    pager = [int(x) for x in _PAGER_LAST_RE.findall(body)]
    last_page = max(pager) if pager else 1

    meta = {
        "endpoint": url,
        "status": status,
        "pagination": (
            f"支持：主题楼层分页 /post-<id>-<page>，站方每页 10 楼；"
            f"本次取第 {page}/{last_page} 页。"
            "列表页也分页（/page-N，最多 100 页）"
        ),
        "pages_returned": len(shown),
        "total_floor_pages": last_page,
        "op_present_on_page": any(p["floor"] == 0 for p in posts),
        "note": (
            "服务端渲染 HTML 直接解析，未登录、未带 Cookie。"
            "每页固定 10 楼；posts 只含当前页的楼层。"
            "created 取自 NodeSeek 展示的本地时间字符串（<time title=...>）。"
            "主题页不存在该页码时站方返回 HTTP 404。"
            + (
                ""
                if any(p["floor"] == 0 for p in posts)
                else f" 注意：第 {page} 页不含首帖（floor=0），"
                     "故顶层 body 取本页第一条楼层而非首帖。"
            )
        ),
        "source": "site-ssr",
    }

    if not main or not main.get("body"):
        meta["note"] += "；正文解析为空"

    data = {
        "title": title,
        "url": url,
        "id": pid,
        "author": main.get("author"),
        "created": main.get("created"),
        "body": main.get("body", ""),
        "posts": shown,
    }
    return data, meta