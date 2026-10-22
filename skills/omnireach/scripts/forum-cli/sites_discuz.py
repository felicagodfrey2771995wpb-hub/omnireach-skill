"""恩山无线论坛（Discuz! X3.5）只读站点模块。

来源说明（重要，见 --verbose 输出的 meta.note）
------------------------------------------------
引擎：Discuz! X3.5（实测 <meta name="generator" content="Discuz! X3.5" />、
      rewrite URL 形态 thread-<tid>-<page>-<xfid>.html / forum-<fid>-<page>.html、
      JS 常量 discuz_uid = '0'）。

实测可达面（2026-10-19，GET + 完整浏览器 UA，未登录、未带 Cookie）：
  GET /forum/                                                   -> HTTP 200 ✅
  GET /forum/forum-70-1.html                                    -> HTTP 200 ✅（分区主题列表）
  GET /forum/forum-70-2.html                                    -> HTTP 200 ✅（第 2 页）
  GET /forum/thread-8287728-1-1.html                            -> HTTP 200 ✅（完整主题正文）
  GET /forum/archiver/?mod=forum                                -> HTTP 200 ✅（纯 GET 版分区总览）
  GET /forum/archiver/fid-136.html                              -> HTTP 200 ✅
  GET /forum/archiver/?mod=thread&tid=8287728                   -> HTTP 200，
        但响应体与 ?mod=forum **逐字节相同** —— archiver 的主题视图被站方关掉，
        静默回落成分区总览，因此不可用。主题正文走普通 rewrite URL。
  GET /forum/search.php?mod=forum&searchsubmit=yes&kw=OpenWrt    -> HTTP 200，
        但返回的是 Discuz「提示信息」页，不是结果页。游客被明确拒绝。
        游客搜索还有一条硬约束：必须先 POST 拿到 formhash + 搜索会话 cookie，
        而本工具只发 GET、不带 Cookie，所以这条路结构性不可用。

因此 SEARCH 的做法是：
  1) GET /forum/archiver/?mod=forum 拿全站分区（fid）清单；
  2) 按 --page 取一批分区，GET /forum/forum-<fid>-1.html 拿该分区的完整主题列表；
  3) 在本地按标题做关键词过滤。
这**不是**站内检索：语料只覆盖每页 3 个分区、每分区第 1 页（站方每页 50 主题），
且只匹配标题。
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

_ENGINE = "discuz"

_TIMEOUT = 20
_RETRIES = 2
_BACKOFF = 1.5

FORUMS_PER_SEARCH_PAGE = 3   # 每个 --page 抓几个分区的第 1 页
_SCAN_CAP = 18                # 单次 search 最多扫描的分区数

# Cloudflare / WAF interstitial 特征。
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

# Discuz 提示信息页：「抱歉，您所在的用户组(游客)无法进行此操作」
_REFUSE_RE = re.compile(r"抱歉[，,]\s*您所在的用户组[（(]([^）)]*)[）)]无法进行此操作")
_ALERT_PAGE_RE = re.compile(r"<title[^>]*>\s*提示信息")

# archiver 分区总览：<li><a href="fid-176.html">COMFAST 新品福利</a></li>
_ARCH_FID_RE = re.compile(r'<a href="fid-(\d+)\.html"[^>]*>(.*?)</a>', re.S)
_ARCH_CAT_RE = re.compile(r"<h3>(.*?)</h3>", re.S)

# 主题列表行：<tbody id="normalthread_TID"> / <tbody id="stickthread_TID">
_ROW_RE = re.compile(r'<tbody id="(?:normalthread|stickthread)_(\d+)">(.*?)</tbody>', re.S)
_ROW_TITLE_RE = re.compile(
    r'<a href="(thread-\d+-\d+-\d+\.html)"[^>]*class="s xst"[^>]*>(.*?)</a>', re.S
)
_ROW_AUTHOR_RE = re.compile(
    r'<td class="by">\s*<cite>\s*<a href="space-uid-\d+\.html"[^>]*>(.*?)</a>', re.S
)
_ROW_DATE_RE = re.compile(r'<em><span>([^<]+)</span></em>')
_ROW_NUM_RE = re.compile(
    r'<td class="num"><a href="[^"]*" class="xi2">(\d+)</a><em>(\d+)</em></td>', re.S
)

# 主题页
_SUBJECT_RE = re.compile(r'<span id="thread_subject">(.*?)</span>', re.S)
_COUNT_RE = re.compile(
    r'查看:\s*</span>\s*<span class="xi1">(\d+)</span>.*?回复:\s*</span>\s*<span class="xi1">(\d+)</span>',
    re.S,
)
_POST_SPLIT_RE = re.compile(r'(?=<div id="post_\d+")')
_POST_AUTHOR_RE = re.compile(
    r'<div class="authi">\s*<a href="space-uid-(\d+)\.html"[^>]*>(.*?)</a>', re.S
)
_POST_DATE_RE = re.compile(r'发表于\s*([^<]*?)\s*(?:</em>|$)')
_POST_BODY_RE = re.compile(r'<td class="t_f"[^>]*id="postmessage_\d+"[^>]*>(.*?)</td>', re.S)
_UID_ANY_RE = re.compile(r"space-uid-(\d+)\.html")

_TAG_RE = re.compile(r"<[^>]+>")


class _TextExtractor(html.parser.HTMLParser):
    """把一段 HTML 片段压成纯文本，保留块级换行。"""

    _BREAK = {"p", "br", "li", "h1", "h2", "h3", "h4", "h5", "h6",
              "div", "tr", "blockquote", "hr", "pre", "td"}
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


def _is_challenge(body: str, headers) -> bool:
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
    """GET 一个页面，返回 (status, body_text, headers)。"""
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
                kind = "Cloudflare 安全验证页" if _is_challenge(text, hdrs) else "拒绝页"
                raise Blocked(
                    f"恩山 HTTP {exc.code} {kind} — GET {url}\n"
                    f"原文摘录: {_snippet(text)}"
                ) from exc
            return exc.code, text, hdrs
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last = exc
        if attempt < _RETRIES:
            time.sleep(_BACKOFF * (attempt + 1))
    raise last if last else RuntimeError("恩山 请求失败")


def _matches(item_title: str, query: str) -> bool:
    """标题本地过滤：query 按空白切词，要求全部词都出现（不区分大小写）。"""
    tokens = [t for t in re.split(r"\s+", (query or "").strip()) if t]
    if not tokens:
        return True
    low = (item_title or "").lower()
    return all(t.lower() in low for t in tokens)


def _probe_search(site_cfg: dict, query: str) -> dict:
    """如实探测 GET 形态的站内搜索，把结果（含拒绝原文）记进 meta。"""
    base = site_cfg["base"].rstrip("/")
    url = (f"{base}/forum/search.php?mod=forum&searchsubmit=yes"
           f"&kw={urllib.parse.quote(query)}")
    try:
        status, body, hdrs = _get(url, site_cfg["user_agent"])
    except Blocked as exc:
        return {"endpoint": url, "status": 403, "blocked": True, "raw": str(exc)}

    if _is_challenge(body, hdrs):
        return {"endpoint": url, "status": status, "blocked": True,
                "raw": f"Cloudflare 安全验证页: {_snippet(body)}"}

    refuse = _REFUSE_RE.search(body)
    if refuse or _ALERT_PAGE_RE.search(body):
        raw = _snippet(body, 600)
        # 优先取出那句拒绝原文本身
        m = re.search(r"抱歉[，,]\s*您所在的用户组[（(][^）)]*[）)]无法进行此操作", body)
        return {
            "endpoint": url, "status": status, "blocked": True,
            "guest_group": refuse.group(1) if refuse else None,
            "raw": m.group(0) if m else raw,
            "note": (
                f"HTTP {status} 但返回的是 Discuz「提示信息」页，不是搜索结果页。"
                f"游客搜索被站方按用户组权限拒绝。"
            ),
        }
    return {"endpoint": url, "status": status, "blocked": False,
            "note": f"HTTP {status}，返回的既不是结果页也不是提示信息页；未判定为阻断。"}


def _list_forums(site_cfg: dict):
    """用 archiver 分区总览拿全站 fid 清单。返回 (list[(fid,name)], status)。"""
    base = site_cfg["base"].rstrip("/")
    url = f"{base}/forum/archiver/?mod=forum"
    status, body, hdrs = _get(url, site_cfg["user_agent"])
    if _is_challenge(body, hdrs):
        raise Blocked(f"恩山 分区总览返回安全验证页 — GET {url}\n原文摘录: {_snippet(body)}")

    fids = []
    seen = set()
    for fid, name in _ARCH_FID_RE.findall(body):
        if fid in seen:
            continue
        seen.add(fid)
        fids.append((fid, _plain(name)))
    return fids, status, url


def _parse_threadlist(body: str, base: str, fid: str):
    out = []
    for tid, block in _ROW_RE.findall(body):
        tm = _ROW_TITLE_RE.search(block)
        if not tm:
            continue
        href, inner = tm.group(1), tm.group(2)
        author = _ROW_AUTHOR_RE.search(block)
        date = _ROW_DATE_RE.search(block)
        num = _ROW_NUM_RE.search(block)
        out.append({
            "id": tid,
            "title": _plain(inner),
            "url": f"{base}/forum/{href}",
            "author": _plain(author.group(1)) if author else None,
            "replies": int(num.group(1)) if num else None,
            "views": int(num.group(2)) if num else None,
            "created": date.group(1).strip() if date else None,
            "fid": fid,
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

    search_probe = _probe_search(site_cfg, query)

    fids, index_status, index_url = _list_forums(site_cfg)
    fids = fids[:_SCAN_CAP]
    if not fids:
        raise Blocked(f"恩山 分区总览 {index_url} 未解析出任何分区（HTTP {index_status}）")

    start = (page - 1) * FORUMS_PER_SEARCH_PAGE
    batch = fids[start:start + FORUMS_PER_SEARCH_PAGE]
    if not batch:
        batch = fids[-FORUMS_PER_SEARCH_PAGE:]

    items, endpoints, statuses, scanned = [], [], [], 0
    seen = set()
    for fid, fname in batch:
        url = f"{base}/forum/forum-{fid}-1.html"
        status, body, hdrs = _get(url, ua)
        endpoints.append(url)
        statuses.append(status)
        if status != 200 or _is_challenge(body, hdrs):
            continue
        rows = _parse_threadlist(body, base, fid)
        scanned += len(rows)
        for it in rows:
            if it["url"] in seen or not _matches(it["title"], query):
                continue
            it["forum"] = fname
            seen.add(it["url"])
            items.append(it)

    items = items[:limit]

    meta = {
        "endpoint": index_url,
        "endpoints_scanned": endpoints,
        "statuses": statuses,
        "status": index_status,
        "search_probe": search_probe,
        "source": "site-ssr-forumdisplay+client-side-title-filter",
        "forums_scanned": [{"fid": f, "name": n} for f, n in batch],
        "topics_scanned": scanned,
        "pagination": (
            f"站方两层分页都真实可用：分区列表 forum-<fid>-<page>.html（实测 "
            f"forum-70-1.html 标题=“DD-WRT…怀旧区-恩山无线论坛”，forum-70-2.html 标题=“…-第2页-…”），"
            f"主题楼层 thread-<tid>-<page>-<xfid>.html。本 SEARCH 的 --page 走的是**第一层**："
            f"每个 --page 换 {FORUMS_PER_SEARCH_PAGE} 个不同分区（按 fid 升序切批，"
            f"--page={page} -> 第 {start + 1}..{start + len(batch)} 个分区），"
            f"每个分区固定取第 1 页（站方每页 50 主题），因此 page 1 与 page 2 的 id/url 必然不同。"
            f"全站共发现 {len(fids)} 个分区，本模块单次最多扫描 {_SCAN_CAP} 个。"
        ),
        "note": (
            "这不是站内检索。Discuz 的搜索必须先 POST 拿 formhash 与搜索会话 cookie，"
            "而本工具只发 GET、不提交表单、不带 Cookie；"
            "游客搜索更是被站方按用户组直接拒绝（拒绝原文见 search_probe.raw）。"
            "所以 SEARCH = archiver 分区总览 + forumdisplay 服务端渲染列表 + 本地标题过滤："
            f"本次覆盖 {len(batch)} 个分区、共 {scanned} 条主题，只匹配标题、不匹配正文，"
            f"且只取每个分区的第 1 页。未登录、未带 Cookie、未提交任何表单。"
            "archiver 的 ?mod=thread 被站方关闭（实测响应体与 ?mod=forum 逐字节相同，"
            "静默回落成分区总览），主题正文因此走普通 rewrite URL。"
        ),
    }
    return items, meta


def RESOLVE(site_cfg: dict, ref: str):
    raw = (ref or "").strip()
    base = site_cfg["base"].rstrip("/")
    m = re.search(r"thread-(\d+)-(\d+)-(\d+)\.html", raw)
    if m:
        tid, _pg, xfid = m.group(1), m.group(2), m.group(3)
    else:
        q = re.search(r"[?&](?:t|tid)=(\d+)", raw)
        if q:
            tid, xfid = q.group(1), "1"
        elif re.fullmatch(r"\d+", raw):
            tid, xfid = raw, "1"
        else:
            raise ValueError(
                f"无法从 {ref!r} 解析 Discuz tid；"
                "支持 https://www.right.com.cn/forum/thread-<tid>-<page>-<xfid>.html、"
                "forum.php?mod=viewthread&tid=<id> 或纯数字 tid"
            )
    return f"{base}/forum/thread-{tid}-1-{xfid}.html", tid


def POST(site_cfg: dict, ref: str, page: int, limit: int):
    page = max(1, int(page))
    limit = max(1, int(limit))
    _url, tid = RESOLVE(site_cfg, ref)
    base = site_cfg["base"].rstrip("/")
    xfid = "1"
    m = re.search(r"thread-\d+-\d+-(\d+)\.html", (ref or "").strip())
    if m:
        xfid = m.group(1)
    url = f"{base}/forum/thread-{tid}-{page}-{xfid}.html"

    status, body, hdrs = _get(url, site_cfg["user_agent"])
    if _is_challenge(body, hdrs):
        raise Blocked(f"恩山 主题正文返回安全验证页 — GET {url}\n原文摘录: {_snippet(body)}")

    refuse = _REFUSE_RE.search(body)
    if refuse or _ALERT_PAGE_RE.search(body):
        m2 = re.search(r"抱歉[，,]\s*您所在的用户组[（(][^）)]*[）)]无法进行此操作", body)
        raise Blocked(
            f"恩山 主题正文被站方拒绝（HTTP {status}，Discuz 提示信息页）— GET {url}\n"
            f"原文: {m2.group(0) if m2 else _snippet(body, 400)}"
        )
    if status != 200:
        raise Blocked(f"恩山 主题页不可读 — GET {url} -> HTTP {status}")

    tm = _SUBJECT_RE.search(body)
    if not tm:
        raise Blocked(f"恩山 主题页 {url} 结构无法解析（找不到 thread_subject）")
    title = _plain(tm.group(1))

    counts = _COUNT_RE.search(body)

    posts = []
    for blk in _POST_SPLIT_RE.split(body)[1:]:
        pm = _POST_BODY_RE.search(blk)
        if not pm:
            continue
        text = _to_text(pm.group(1))
        if not text:
            continue
        am = _POST_AUTHOR_RE.search(blk)
        dm = re.search(r'<em id="authorposton\d+">发表于\s*([^<]*)</em>', blk)
        um = _UID_ANY_RE.search(blk)
        posts.append({
            "floor": len(posts) + 1,
            "author": _plain(am.group(2)) if am else None,
            "author_id": int(am.group(1)) if am else (int(um.group(1)) if um else None),
            "created": dm.group(1).strip() if dm else None,
            "body": text,
        })

    shown = posts[:limit]
    op = posts[0] if posts else None
    # Discuz 只在第 1 页重复首帖；翻页后 body 退回本页第一条楼层。
    op_present = page == 1

    meta = {
        "endpoint": url,
        "status": status,
        "pages_returned": len(shown),
        "views": int(counts.group(1)) if counts else None,
        "total_replies": int(counts.group(2)) if counts else None,
        "op_present_on_page": op_present,
        "pagination": (
            f"支持：主题楼层分页 thread-<tid>-<page>-<xfid>.html（站方每页 10 楼），"
            f"本次取第 {page} 页；同一 URL 形态也用于分区列表 forum-<fid>-<page>.html。"
        ),
        "note": (
            "服务端渲染 HTML 直接解析（rewrite URL，非 archiver），未登录、未带 Cookie、未提交表单。"
            "created 取自 Discuz 展示的 <em id=\"authorposton…\">发表于 YYYY-M-D HH:MM</em>。"
            "楼层号 floor 按本页顺序重排；第 1 页含首帖，后续页不含。"
            "title 是 thread_subject（不含站方追加的 “-版块名-恩山无线论坛” 后缀）。"
        ),
        "source": "site-ssr",
    }
    if not op_present:
        meta["note"] += (
            f" 注意：第 {page} 页不含首帖（站方只在第 1 页重复首帖），"
            "故顶层 body 取本页第一条楼层而非首帖；该页的 查看/回复 计数站方也不再输出。"
        )

    data = {
        "title": title,
        "url": url,
        "id": tid,
        "author": op.get("author") if op else None,
        "created": op.get("created") if op else None,
        "body": op.get("body", "") if op else "",
        "posts": shown,
    }
    if not data["body"]:
        meta["note"] += "；正文解析为空"
    return data, meta