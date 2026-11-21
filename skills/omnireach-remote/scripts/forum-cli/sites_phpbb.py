"""Ubuntu 中文论坛（phpBB 3.x）只读站点模块。

来源说明（重要，见 --verbose 输出的 meta.note）
------------------------------------------------
引擎：phpBB 3.x（实测首页含 /viewtopic.php、/viewforum.php、/app.php/feed、
      <dl class="row-item"> 论坛树、atom feed 入口）。

实测可达面（2026-10-19，GET + 完整浏览器 UA，未登录、未带 Cookie）：
  GET https://forum.ubuntu.org.cn/                        -> HTTP 200  ✅
  GET https://forum.ubuntu.org.cn/index.php               -> HTTP 403  Cloudflare 挑战
  GET https://forum.ubuntu.org.cn/index.php?f=95          -> HTTP 403  Cloudflare 挑战
  GET https://forum.ubuntu.org.cn/viewforum.php?f=95      -> HTTP 403  Cloudflare 挑战
  GET https://forum.ubuntu.org.cn/viewtopic.php?p=3240000 -> HTTP 403  Cloudflare 挑战
  GET https://forum.ubuntu.org.cn/search.php?keywords=…   -> HTTP 403  Cloudflare 挑战
  GET https://forum.ubuntu.org.cn/app.php/feed/topics     -> HTTP 403  Cloudflare 挑战
  GET https://forum.ubuntu.org.cn/ucp.php?mode=register   -> HTTP 403  Cloudflare 挑战

即：Cloudflare 只放行裸根路径 /，其余所有 PHP 路径一律下 managed challenge
（响应头 Cf-Mitigated: challenge，正文 <title>Just a moment...</title>）。
两次独立 GET / 都返回 200（正文 md5 不同，页面含时间戳），所以不是一次性放行。

后果：
  * 站内检索：不可用。search.php 被挑战挡住；phpBB 的 search 本来就是 POST 表单，
    本工具只发 GET，本来就只能走 ?keywords= 形态，而该形态正好被挡。
  * 正文：不可用。viewtopic.php 被挑战挡住，没有可读替代路径
    （app.php/feed/topics 同样被挡）。
  * 列表：仅首页可达。首页对每个有内容的分区给出 1 条「最新文章」，
    即 title / url(viewtopic.php?p=<post_id>) / 最后发表者 / 最后发表时间，
    约 29 条。首页没有主题列表、没有回复数、没有分页。

因此 SEARCH 的做法是：抓可达的首页，在本地按标题做关键词过滤。这**不是**站内
全文检索，语料仅为首页那约 29 条「最后文章」，且只匹配标题。
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

_ENGINE = "phpbb"

_TIMEOUT = 20
_RETRIES = 2
_BACKOFF = 1.5

# Cloudflare managed challenge 特征。
# 注意：不要把 "challenge-platform" 单独当判据 —— 部分正常站点（如 linux.org）
# 会注入 Turnstile challenge-platform 小组件。这里只用 interstitial 标题、
# 挑战脚本变量和响应头这几个强特征。
_CF_TITLE = re.compile(r"<title[^>]*>\s*(?:Just a moment|Checking your browser)", re.I)
_CF_MARKERS = (
    "cf_chl_opt",
    "cf_chl_jschl",
    "__cf_chl",
    "cf-browser-verification",
    "Enable JavaScript and cookies to continue",
    "正在进行安全验证",
    "请完成下面的操作以继续",
)

# 首页论坛树的一行：<dl class="row-item …"> <dt>…</dt> <dd class="lastpost">…</dd> </dl>
_ROW_RE = re.compile(r'<dl class="row-item[^"]*">(.*?)</dl>', re.S)
# 行内的「最新文章」链接；title 属性是完整标题，锚文本在可见块里会被截断成 "…"。
_TOPIC_A = re.compile(
    r'<a href="[^"]*viewtopic\.php\?p=(\d+)[^"]*"(?:\s+title="([^"]*)")?[^>]*class="lastsubject"[^>]*>(.*?)</a>',
    re.S,
)
_LASTUSER = re.compile(
    r'由\s*<a[^>]*class="username"[^>]*>(.*?)</a>', re.S
)
_LASTDATE = re.compile(
    r'class="username"[^>]*>\s*[^<]*</a>\s*,?\s*([0-9]{4}-[0-9]{1,2}-[0-9]{1,2}\s+[0-9]{1,2}:[0-9]{2})'
)
_TAG_RE = re.compile(r"<[^>]+>")


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
        out = "".join(self.parts).replace("\r\n", "\n").replace("\r", "\n")
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


def _plain(fragment: str) -> str:
    return html.unescape(_TAG_RE.sub("", fragment)).strip()


def _is_cloudflare_challenge(body: str, headers) -> bool:
    hdr = {k.lower(): v for k, v in (headers or {}).items()}
    if hdr.get("cf-mitigated", "").lower() == "challenge":
        return True
    if _CF_TITLE.search(body or ""):
        return True
    return any(m in (body or "") for m in _CF_MARKERS)


def _snippet(body: str, n: int = 300) -> str:
    b = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", body or "")
    return _TAG_RE.sub(" ", b).strip()[:n]


def _get(url: str, ua: str):
    """GET 一个页面，返回 (status, body_text, headers)。

    403 会先 exc.read() 把响应体读出来再判定，否则拿不到 Cloudflare 挑战原文，
    退出码也会从 75 静默退化成 1。
    """
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
                return resp.status, raw.decode("utf-8", "replace"), dict(resp.headers)
        except urllib.error.HTTPError as exc:
            body = b""
            try:
                body = exc.read()
                if exc.headers.get("Content-Encoding") == "gzip":
                    body = gzip.decompress(body)
            except Exception:
                pass
            text = body.decode("utf-8", "replace")
            hdrs = dict(exc.headers or {})
            if exc.code in (401, 403, 429, 503):
                kind = "Cloudflare 安全验证页" if _is_cloudflare_challenge(text, hdrs) else "拒绝页"
                raise Blocked(
                    f"Ubuntu中文论坛 HTTP {exc.code} {kind} — GET {url}\n"
                    f"响应头 Server={hdrs.get('Server', '(无)')} "
                    f"Cf-Mitigated={hdrs.get('Cf-Mitigated', '(无)')} "
                    f"CF-RAY={hdrs.get('CF-RAY', '(无)')}\n"
                    f"原文摘录: {_snippet(text)}"
                ) from exc
            return exc.code, text, hdrs
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last = exc
        if attempt < _RETRIES:
            time.sleep(_BACKOFF * (attempt + 1))
    raise last if last else RuntimeError("Ubuntu中文论坛 请求失败")


def _matches(item_title: str, query: str) -> bool:
    """标题本地过滤：query 按空白切词，要求全部词都出现（不区分大小写）。"""
    tokens = [t for t in re.split(r"\s+", (query or "").strip()) if t]
    if not tokens:
        return True
    low = (item_title or "").lower()
    return all(t.lower() in low for t in tokens)


def _parse_index(body: str, base: str):
    """从首页解析每个分区的「最新文章」条目。

    返回 [{"id","post_id","topic_id","title","url","author","replies","created"}]
    """
    out = []
    for block in _ROW_RE.findall(body):
        entries = _TOPIC_A.findall(block)
        if not entries:
            continue
        pid, title_attr, inner_text = entries[0]
        title = _plain(title_attr) or _plain(inner_text)
        if not title or title.endswith("…"):
            # 锚文本被截断成 "…"，若 title 属性也是截断的则放弃这一条
            continue
        author = _LASTUSER.search(block)
        date = _LASTDATE.search(block)
        out.append({
            "id": pid,
            "post_id": int(pid),
            "topic_id": None,
            "title": title,
            "url": f"{base}/viewtopic.php?p={pid}",
            "author": _plain(author.group(1)) if author else None,
            "replies": None,
            "created": date.group(1).strip() if date else None,
        })
    return out


# --------------------------------------------------------------------------
# 公开接口
# --------------------------------------------------------------------------

def SEARCH(site_cfg: dict, query: str, page: int, limit: int):
    page = max(1, int(page))
    limit = max(1, int(limit))
    base = site_cfg["base"].rstrip("/")
    ua = site_cfg["user_agent"]

    # 1) 先如实探测 GET 形态的站内搜索，把真实阻断证据记进 meta（不掩盖）。
    search_url = f"{base}/search.php?keywords={urllib.parse.quote(query)}"
    try:
        st, _b, _h = _get(search_url, ua)
        search_probe = {"endpoint": search_url, "status": st, "blocked": False,
                        "note": f"HTTP {st}，未判定为阻断"}
    except Blocked as exc:
        search_probe = {"endpoint": search_url, "status": 403, "blocked": True,
                        "raw": str(exc)}

    # 2) 抓唯一可达路径：首页。
    home_url = base + "/"
    status, body, hdrs = _get(home_url, ua)
    if _is_cloudflare_challenge(body, hdrs):
        raise Blocked(
            f"Ubuntu中文论坛 首页也返回 Cloudflare 安全验证页 — GET {home_url}\n"
            f"原文摘录: {_snippet(body)}"
        )

    scanned = _parse_index(body, base)
    items = [it for it in scanned if _matches(it["title"], query)][:limit]

    meta = {
        "endpoint": home_url,
        "search_endpoint": search_url,
        "status": status,
        "search_probe": search_probe,
        "source": "site-homepage-lastpost+client-side-title-filter",
        "items_scanned": len(scanned),
        "pagination": (
            f"不支持。实测：GET / 连续两次独立请求均 HTTP 200，但首页不含 start= / page= "
            f"分页参数，也不含主题列表；带参数的 /index.php?f=95 被 Cloudflare 挑战（HTTP 403）。"
            f"本次 --page={page} 无论取何值都只抓同一份首页，故不产生新条目。"
        ),
        "note": (
            "这不是站内检索。phpBB 的 search 是 POST 表单，本工具只发 GET；"
            "GET 形态 ?keywords= 被 Cloudflare managed challenge 挡住（原文见 search_probe.raw）。"
            "唯一可达路径是裸根 /，首页对每个有内容的分区只给出 1 条「最新文章」，"
            f"本次共解析 {len(scanned)} 条。字段限制（如实说明）："
            "(1) id 是首页 URL 里的**帖子** id（viewtopic.php?p=NNN），"
            "首页不暴露 t= 主题 id，故 topic_id=null；"
            "(2) replies=null —— 首页不含任何回复数（回复数只在 viewforum.php / viewtopic.php，"
            "而这两个路径都被 Cloudflare 挑战挡住）；"
            "(3) author 是该分区**最后发表者**，不是主题作者。"
            "未登录、未带 Cookie、未解挑战。"
        ),
    }
    return items, meta


def RESOLVE(site_cfg: dict, ref: str):
    raw = (ref or "").strip()
    base = site_cfg["base"].rstrip("/")
    m = re.search(r"viewtopic\.php\?(?:[^#]*[?&])?p=(\d+)", raw)
    if m:
        pid = m.group(1)
    elif re.fullmatch(r"\d+", raw):
        pid = raw
    else:
        raise ValueError(
            f"无法从 {ref!r} 解析 phpBB post id；"
            "支持 https://forum.ubuntu.org.cn/viewtopic.php?p=<id> 或纯数字 post id"
        )
    return f"{base}/viewtopic.php?p={pid}", pid


def POST(site_cfg: dict, ref: str, page: int, limit: int):
    page = max(1, int(page))
    limit = max(1, int(limit))
    url, pid = RESOLVE(site_cfg, ref)
    if page > 1:
        url = f"{url}&start={(page - 1) * 15}"

    # 首页之外的所有 phpBB 路径都被 Cloudflare managed challenge 挡住。
    # 这里不尝试任何绕过，把真实响应原文上抛。
    status, body, hdrs = _get(url, site_cfg["user_agent"])
    if _is_cloudflare_challenge(body, hdrs) or status != 200:
        raise Blocked(
            f"Ubuntu中文论坛 主题正文不可读：GET {url} -> HTTP {status}，"
            f"Cloudflare managed challenge（未尝试绕过）。\n"
            f"原文摘录: {_snippet(body)}"
        )

    tm = re.search(r'<span id="thread_subject">(.*?)</span>', body, re.S)
    if not tm:
        raise Blocked(f"Ubuntu中文论坛 主题页 {url} 结构无法解析（找不到 thread_subject）")
    title = _plain(tm.group(1))

    posts = []
    for blk in re.split(r'(?=<div id="post_\d+")', body)[1:]:
        pm = re.search(r'<td class="t_f"[^>]*id="postmessage_\d+"[^>]*>(.*?)</td>', blk, re.S)
        if not pm:
            continue
        text = _to_text(pm.group(1))
        if not text:
            continue
        am = re.search(
            r'<div class="authi">\s*<a href="memberlist\.php\?mode=viewprofile[^"]*"[^>]*>(.*?)</a>',
            blk, re.S,
        )
        dm = re.search(r'<em id="authorposton\d+">发表于\s*([^<]*)</em>', blk)
        um = re.search(r'memberlist\.php\?mode=viewprofile&amp;u=(\d+)', blk)
        posts.append({
            "floor": len(posts) + 1,
            "author": _plain(am.group(1)) if am else None,
            "author_id": int(um.group(1)) if um else None,
            "created": dm.group(1).strip() if dm else None,
            "body": text,
        })

    shown = posts[:limit]
    op = posts[0] if posts else None
    meta = {
        "endpoint": url,
        "status": status,
        "pagination": (
            f"站方语义支持 viewtopic.php?p=<id>&start=<n>，但该路径被 Cloudflare 挑战挡住，"
            f"本次 --page={page} 无实际分页效果。"
        ),
        "pages_returned": len(shown),
        "note": (
            "服务端渲染 HTML 直接解析，未登录、未带 Cookie。"
            "created 取自 phpBB 展示的 <em id=\"authorposton…\">发表于 …</em>。"
        ),
        "source": "site-ssr",
    }
    data = {
        "title": title,
        "url": url,
        "id": pid,
        "author": op.get("author") if op else None,
        "created": op.get("created") if op else None,
        "body": op.get("body", "") if op else "",
        "posts": shown,
    }
    if not data["body"]:
        meta["note"] += "；正文解析为空"
    return data, meta