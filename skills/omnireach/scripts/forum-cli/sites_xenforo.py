"""XenForo / phpBB 只读站点模块（linuxorg、osdev）。

站型结论（本机匿名 GET 实测，2026-10-19）
--------------------------------------------
* linuxorg / https://www.linux.org  = **XenForo 2.x**
  证据：`https://www.linux.org/` 200 且首页 HTML 开头为
  `<html id="XF" ... data-app="public" data-template="EWRporta_articles_index" ...
  data-cookie-prefix="xf_" ...>`；搜索结果页 `data-template="search_results"`，
  帖子页 `data-template="thread_view"` + `<article class="message-body">`。

* osdev / https://forum.osdev.org  = **站型未能实测确认**
  该域所有路径（`/`、`/index.php`、`/app.php`、`/robots.txt`、`/sitemap.xml`）
  一律返回 HTTP 403 + Cloudflare "Just a moment..." 托管挑战页，主域
  `https://osdev.org/` 同样 403。因此本轮拿不到任何来自源站的 HTML，
  无法用 HTML 特征判定站型。
  仅存的**间接**证据是历史验收记录里用的是 `search.php?keywords=` 这一 phpBB 3.x
  形态（XenForo 的站内搜索是 `/search/search`）。本模块因此在 engine=="osdev"
  时先做一次站型探测（GET `/` 与 `/index.php`），探测到 Cloudflare 挑战就直接
  抛 Blocked（退出码 75），不会去猜站型、更不会绕过挑战。

只读约束
--------
只发 GET；不提交表单（XenForo 的站内搜索虽然后台是 POST，但
`GET /search/search?keywords=...` 服务端会接受并 303 到结果页，已实测）；
不携带 Cookie / 凭证；不执行浏览器自动化；不换 IP、不伪造指纹、不解 JS 挑战。
"""

from __future__ import annotations

import html
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

import forum_cli as _forum_cli

# forum_cli.py 既可能被当脚本跑（模块名 __main__），也可能被当库 import。
# 两种情况下 Blocked 是两个不同的类对象；raise 非框架那一个的话，
# 框架的 `except Blocked` 抓不到，退出码会退化成 1 而不是 75。
# 这里优先用框架运行时的那个，保证退出码语义正确。
Blocked = getattr(sys.modules.get("__main__"), "Blocked", None) or _forum_cli.Blocked

_TIMEOUT = 20          # 秒，落在要求的 15–25s 区间内
_RETRIES = 2           # 退避重试次数上限（额外 2 次，即最多 3 次尝试）
_BACKOFF = 1.5

# Cloudflare / WAF 挑战页特征（命中即抛 Blocked，不做任何绕过）
# 注意：不要单用 `challenge-platform` 当信号——linux.org 的正常页面里也注入了
# 一次 Cloudflare challenge-platform（登录/注册表单的 Turnstile 小组件），
# 用它会误判 linux.org 全站被挑战。挑战页（interstitial）独有的信号是
# <title>Just a moment...、cf_chl_opt、cf-browser-verification、"Enable JavaScript
# and cookies to continue" 这几项。
_CHALLENGE_PATTERNS = [
    (re.compile(r"<title>\s*Just a moment", re.I), "Cloudflare 「Just a moment...」托管挑战页"),
    (re.compile(r"Enable JavaScript and cookies to continue", re.I), "Cloudflare 挑战页正文「Enable JavaScript and cookies to continue」"),
    (re.compile(r"cf-browser-verification", re.I), "Cloudflare cf-browser-verification 拦截脚本"),
    (re.compile(r"cf_chl_opt", re.I), "Cloudflare cf_chl_opt 挑战参数"),
    (re.compile(r"Checking your browser before accessing", re.I), "Cloudflare 浏览器校验页"),
    (re.compile(r"Attention Required!\s*\|\s*Cloudflare", re.I), "Cloudflare Attention Required 拦截页"),
    (re.compile(r"<title>\s*Access denied", re.I), "访问被拒绝页（Access denied）"),
]


class _Resp:
    __slots__ = ("status", "url", "text", "location", "headers")

    def __init__(self, status, url, text, location, headers):
        self.status = status
        self.url = url          # 真实请求 URL（重定向后即最终 URL）
        self.text = text
        self.location = location
        self.headers = headers


class _ChallengeBlocked(Blocked):
    """挑战页/限流：携带结构化信息，便于塞进异常消息。

    forum_cli 顶层只打印 str(exc)，所以 endpoint / status / pagination / note
    全部拼进 message，保证 --verbose 也看得到。
    """


def _challenge_text(text: str) -> str:
    """把挑战页压成可读的纯文本片段，原样保留关键文案。"""
    body = re.sub(r"(?is)<script.*?</script>", " ", text)
    body = re.sub(r"(?is)<style.*?</style>", " ", body)
    body = re.sub(r"(?is)<[^>]+>", " ", body)
    body = html.unescape(body)
    return re.sub(r"[ \t\r\n]+", " ", body).strip()


def _blocked(reason: str, status, endpoint, snippet, pagination, note) -> None:
    raise _ChallengeBlocked(
        f"{reason}\n"
        f"  endpoint   : {endpoint}\n"
        f"  status     : {status}\n"
        f"  pagination : {pagination}\n"
        f"  挑战页原文 : {snippet}\n"
        f"  note       : {note}"
    )


def _get(url: str, ua: str, accept: str = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
         allow_redirect: bool = True):
    """只读 GET。返回 _Resp；挑战页 / 401·403·429·503 抛 Blocked(75)。

    只对网络层错误（超时、DNS、连接重置）退避重试；HTTP 状态错误直接判定，
    不浪费请求配额。
    """
    handlers = []
    if not allow_redirect:
        class _NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *a, **k):
                return None

        handlers.append(_NoRedirect())
    opener = urllib.request.build_opener(*handlers)

    last = None
    for attempt in range(_RETRIES + 1):
        req = urllib.request.Request(
            url,
            method="GET",
            headers={
                "User-Agent": ua,
                "Accept": accept,
                "Accept-Language": "en-US,en;q=0.9",
                # identity：避免自动 gzip/br 解码分支，减少不确定性
                "Accept-Encoding": "identity",
                "Connection": "close",
            },
        )
        status = final = headers = raw = None
        try:
            try:
                with opener.open(req, timeout=_TIMEOUT) as resp:
                    raw = resp.read()
                    final = resp.geturl()
                    status = resp.status
                    headers = dict(resp.headers)
            except urllib.error.HTTPError as exc:
                # 4xx/5xx 也要把 body 读出来：挑战页正文就在 body 里
                raw = exc.read()
                final = url
                status = exc.code
                headers = dict(exc.headers or {})
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            last = exc
            if attempt < _RETRIES:
                time.sleep(_BACKOFF * (attempt + 1))
            continue

        text = raw.decode("utf-8", "replace")
        resp_obj = _Resp(status, final, text, headers.get("Location") or "", headers)

        for pattern, label in _CHALLENGE_PATTERNS:
            if pattern.search(text):
                _blocked(
                    f"检测到 {label}，拒绝匿名只读访问（不尝试绕过挑战）",
                    status, final, _challenge_text(text)[:600],
                    "未探测：挑战页早于任何分页解析",
                    "站点在边缘层就拦住了，未触达源站，解析器未被调用；"
                    "未换 IP、未伪造指纹、未解 JS 挑战。",
                )
        if status in (401, 403, 429, 503):
            _blocked(
                f"站点返回 HTTP {status}，拒绝匿名只读访问",
                status, final, _challenge_text(text)[:600],
                "未探测：HTTP 错误早于任何分页解析",
                "未携带任何 Cookie 或凭证；仅发匿名 GET。",
            )
        if 500 <= status < 600:
            last = RuntimeError(f"HTTP {status}")
            if attempt < _RETRIES:
                time.sleep(_BACKOFF * (attempt + 1))
            continue
        return resp_obj

    raise RuntimeError(f"请求失败（已重试 {_RETRIES} 次）: {url} / {last}")


# --------------------------------------------------------------------------
# 通用 HTML -> 纯文本
# --------------------------------------------------------------------------

_BLOCK_TAGS = r"(?:p|div|br|li|tr|h[1-6]|blockquote|pre)"


def _to_text(fragment: str) -> str:
    frag = re.sub(r"(?is)<(script|style|svg|noscript)\b.*?</\1>", " ", fragment)
    frag = re.sub(r"(?i)<br\s*/?>", "\n", frag)
    frag = re.sub(r"(?i)</\s*" + _BLOCK_TAGS + r"\s*>", "\n", frag)
    frag = re.sub(r"(?i)<\s*" + _BLOCK_TAGS + r"[^>]*>", "\n", frag)
    frag = re.sub(r"(?is)<[^>]+>", "", frag)
    frag = html.unescape(frag)
    frag = frag.replace(" ", " ")
    frag = re.sub(r"[ \t]+", " ", frag)
    frag = re.sub(r"\n\s*\n\s*\n+", "\n\n", frag)
    return frag.strip()


def _clean_title(raw: str) -> str:
    return re.sub(r"\s+", " ", _to_text(raw)).strip()


# --------------------------------------------------------------------------
# XenForo 解析
# --------------------------------------------------------------------------

_XF_THREAD_RE = re.compile(r"/threads/([^/?#]+?)\.(\d+)(?:/|$)")


def _xf_rows(text: str):
    """切出搜索结果里的 <li class="block-row ..."> 块。"""
    return re.split(r'<li class="block-row', text)[1:]


def _xf_search_items(text: str):
    items = []
    for row in _xf_rows(text):
        m = re.search(r'<h3 class="contentRow-title">\s*<a href="([^"]+)"[^>]*>(.*?)</a>', row, re.S)
        if not m:
            continue
        href, inner = m.group(1), m.group(2)
        tm = _XF_THREAD_RE.search(href)
        if not tm:
            continue
        tid = tm.group(2)
        # 标签（News / General ...）从标题里剥出来
        label = re.search(r'<span class="label label--primary"[^>]*>(.*?)</span>', inner, re.S)
        for junk in re.findall(r'<span class="label-append">.*?</span>', inner, re.S):
            inner = inner.replace(junk, " ")
        inner = re.sub(r'(?is)<span class="label label--primary".*?</span>', " ", inner)
        snippet = re.search(r'<div class="contentRow-snippet">(.*?)</div>', row, re.S)
        author = re.search(r'class="username[^"]*"[^>]*>(.*?)</a>', row, re.S)
        created = re.search(r'<time[^>]*?datetime="([^"]+)"[^>]*?(?:data-date="([^"]*)")?', row, re.S)
        replies = re.search(r"Replies:\s*([\d,]+)", row)
        forum = re.search(r'<li>Forum:\s*<a href="([^"]+)"[^>]*>(.*?)</a>', row, re.S)
        items.append({
            "id": tid,
            "title": _clean_title(inner),
            "url": href,
            "author": _clean_title(author.group(1)) if author else None,
            "replies": int(replies.group(1).replace(",", "")) if replies else None,
            "created": (created.group(1) or (created.group(2) if created else None)) if created else None,
            "snippet": _clean_title(snippet.group(1)) if snippet else "",
            "tag": _clean_title(label.group(1)) if label else None,
            "forum": (urllib.parse.urljoin("", forum.group(1)), _clean_title(forum.group(2))) if forum else None,
        })
    return items


def _xf_pages(text: str):
    """从 pageNav 里读出 (可见页码, 完整 URL) 列表。"""
    out = []
    for href, label in re.findall(
        r'<li class="pageNav-page[^"]*"><a href="([^"]+)"[^>]*>(\d+)</a></li>', text
    ):
        out.append((int(label), html.unescape(href)))
    return out


def _xf_next_url(text: str):
    # class="pageNav-jump pageNav-jump--next"（XenForo 会同时挂两个 class）
    m = re.search(r'<a href="([^"]+)"\s+class="[^"]*pageNav-jump--next"', text)
    return html.unescape(m.group(1)) if m else None


def _xf_total_pages(text: str):
    """结果总页数。XenForo 在 pageNavSimple 的 "N of M" 和 pageJump 输入框 max 上都给了。"""
    m = re.search(r'pageNavSimple-el--current"[^>]*>\s*(\d+)\s+of\s+(\d+)', text)
    if m:
        return int(m.group(2))
    m = re.search(r'js-pageJumpPage"[^>]*\bmax="(\d+)"', text)
    if m:
        return int(m.group(1))
    return None


_XF_ENGINE_RE = re.compile(r'id="XF"|data-app="public"|data-cookie-prefix="xf_"')


def _xf_search(site_cfg: dict, query: str, page: int, limit: int):
    base = site_cfg["base"]
    ua = site_cfg["user_agent"]
    page = max(1, int(page))

    # XenForo 站内搜索：GET /search/search?keywords=... 服务端会 303 到
    # /search/<searchId>/?q=...&o=<order>。实测 303 302 皆可。
    kick = (f"{base}/search/search?"
            + urllib.parse.urlencode({"keywords": query, "o": "relevance"},
                                     quote_via=urllib.parse.quote))
    r1 = _get(kick, ua, allow_redirect=False)
    if r1.status not in (301, 302, 303, 307, 308) or not r1.location:
        raise RuntimeError(
            f"XenForo 搜索入口未返回重定向，status={r1.status}, endpoint={r1.url}"
        )
    results_url = urllib.parse.urljoin(kick, r1.location)

    if page > 1:
        results_url = _with_param(results_url, "page", str(page))
    r2 = _get(results_url, ua)

    items = _xf_search_items(r2.text)
    items = [i for i in items if i["title"]]
    for i in items:
        i["url"] = urllib.parse.urljoin(base, i["url"])
    total = len(items)
    items = items[: max(1, int(limit))]

    pages = _xf_pages(r2.text)
    next_url = _xf_next_url(r2.text)
    total_pages = _xf_total_pages(r2.text)

    meta = {
        "engine_detected": "xenforo",
        "endpoint": kick,
        "endpoint_redirect": r1.location,
        "endpoint_final": r2.url,
        "status": r2.status,
        "pagination": (
            f"支持：XenForo 搜索分页走 /search/<searchId>/?page=N&q=..&o=relevance；"
            f"searchId 由 GET /search/search?keywords=.. 的 303 响应头 Location 下发，"
            f"因此每页需 2 次 GET（取 searchId + 取该页）。本次 page={page}，"
            f"该查询共 {total_pages} 页，本页 {total} 条，"
            f"pageNav 可见页码 {[p for p, _ in pages]}"
            + (f"，Next -> {next_url}" if next_url else "，无 Next（末页）")
        ),
        "pages_seen": [p for p, _ in pages],
        "total_pages": total_pages,
        "next_page_url": next_url,
        "results_on_page": total,
        "returned": len(items),
        "note": (
            "读的是搜索结果页自身的 HTML 标签（contentRow / block-row），不是任何 JSON 接口。"
            "XenForo 站内搜索后台是 POST，但 GET /search/search?keywords=.. 被服务端接受并"
            " 303 跳到结果页，本模块全程只用 GET。"
            "站内搜索要求 JavaScript 提交时用的就是这个 GET 入口（已实测 status=303）。"
        ),
    }
    return items, meta


def _with_param(url: str, key: str, value: str) -> str:
    parts = urllib.parse.urlsplit(url)
    q = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
    q = [(k, v) for (k, v) in q if k != key]
    q.append((key, value))
    return urllib.parse.urlunsplit((
        parts.scheme, parts.netloc, parts.path,
        urllib.parse.urlencode(q, quote_via=urllib.parse.quote), parts.fragment))


# 单个帖子的切分边界：XenForo 2.x 用 <div class="message-userContent" data-lb-id="post-N">，
# 另一些皮肤用 <li id="post-N">，两种都认。
_XF_POST_BOUNDARY = re.compile(
    r'(?=<div class="message-userContent[^"]*"[^>]*data-lb-id="post-\d+"'
    r'|<li id="post-\d+")',
    re.S,
)


def _xf_thread(title_text: str):
    """返回 (title, [post...])。

    XenForo 2.x 一篇帖子的 DOM 顺序是：
        message-cell--user  (message-name -> 作者)
        message-cell--main
            header.message-attribution  (post 永久链接 + <time datetime>)
            div.message-userContent[data-lb-id="post-N"]
                article.message-body > div.bbWrapper
    也就是「作者 + 时间 + 永久链接」在 message-userContent **之前**，
    所以光按 message-userContent 切块会丢掉它们；这里按 message-userContent
    的起点切片，同时把「上一个起点 → 本起点」这一段当作本帖的前缀来取头部信息。
    """
    m = re.search(r'<h1 class="p-title-value">(.*?)</h1>', title_text, re.S)
    title = _clean_title(m.group(1)) if m else None

    starts = [mm.start() for mm in _XF_POST_BOUNDARY.finditer(title_text)]
    posts = []
    for i, s in enumerate(starts):
        prefix = title_text[(starts[i - 1] if i else 0):s]
        end = starts[i + 1] if i + 1 < len(starts) else len(title_text)
        body_html = title_text[s:end]

        pid_m = (re.match(r'[^>]*data-lb-id="post-(\d+)"', body_html)
                 or re.match(r'<li id="post-(\d+)"', body_html))
        if not pid_m:
            continue
        pid = pid_m.group(1)

        author = re.search(
            r'<h4 class="message-name">.*?class="username[^"]*"[^>]*>(.*?)</a>', prefix, re.S)
        attrib = re.search(r'<header class="message-attribution[^"]*">(.*?)</header>', prefix, re.S)
        seg = attrib.group(1) if attrib else prefix
        time_tag = re.search(r'<time[^>]*?datetime="([^"]+)"', seg)
        perm_m = re.search(r'href="(/threads/[^"]+/post-%s)"' % pid, prefix)
        floor_m = re.search(r'rel="nofollow"[^>]*>\s*(#\d+)\s*</a>', prefix)

        art = re.search(r'<article class="message-body[^"]*">(.*?)</article>', body_html, re.S)
        raw_body = ""
        if art:
            inner = art.group(1)
            # 正文到 bbWrapper 结束为止；签名 (div.signature) 之前截断
            bb = re.search(r'<div class="bbWrapper">(.*?)(?=<div class="signature"|</article>)',
                           inner, re.S)
            raw_body = bb.group(1) if bb else inner

        posts.append({
            "post_id": pid,
            "author": _clean_title(author.group(1)) if author else None,
            "created": time_tag.group(1) if time_tag else None,
            "body": _to_text(raw_body),
            "floor": floor_m.group(1) if floor_m else None,
            "path": perm_m.group(1) if perm_m else None,
        })
    return title, posts


def _xf_post(site_cfg: dict, url: str, thread_id: str, page: int, limit: int):
    base = site_cfg["base"]
    ua = site_cfg["user_agent"]
    page = max(1, int(page))
    target = url if page <= 1 else _with_param(url, "page", str(page))
    r = _get(target, ua)

    title, posts = _xf_thread(r.text)
    # 楼层永久链接
    for p in posts:
        path = p.pop("path", None)
        p["url"] = urllib.parse.urljoin(base, path) if path else None

    thread_pages = sorted({int(x) for x in re.findall(r'page=(\d+)', r.text)})
    posts = posts[: max(1, int(limit))]
    body = next((p["body"] for p in posts if p["body"]), "")

    meta = {
        "engine_detected": "xenforo",
        "endpoint": target,
        "status": r.status,
        "pagination": (
            f"支持：XenForo 长贴翻页用 <threadUrl>?page=N（本页 page={page}）；"
            f"页面内出现的 page 参数取值 {thread_pages[:12]}"
            if thread_pages else
            f"单页贴：页面内无 ?page= 参数（page={page} 即全部）"
        ),
        "thread_id": thread_id,
        "posts_parsed": len(posts),
        "note": (
            "解析 XenForo thread_view 的 <li id=\"post-N\"> / <article class=\"message-body\"> / "
            "<div class=\"bbWrapper\">，作者取 message-name 里的 username，时间取 message-attribution "
            "里的 <time datetime=...>。正文只取 bbWrapper，不含签名与表情条。"
            "只读 GET，无 Cookie。"
        ),
    }
    data = {
        "title": title,
        "url": r.url,
        "author": posts[0]["author"] if posts else None,
        "created": posts[0]["created"] if posts else None,
        "body": body,
        "posts": posts,
    }
    return data, meta


# --------------------------------------------------------------------------
# phpBB 解析（osdev 历史证据指向 phpBB 3.x；本轮被 Cloudflare 挡住，
#   以下解析器未经本轮真实响应验证）
# --------------------------------------------------------------------------

_PHPBB_ENGINE_RE = re.compile(
    r'Powered by\s*<a href="https?://www\.phpbb\.com|'
    r'phpbb-template-|class="search-results|id="block-search',
    re.I,
)


def _phpbb_search_items(text: str):
    items = []
    for block in re.split(r'<div class="search-result(?:search-result--highlight)?[^"]*"', text)[1:]:
        m = re.search(r'<a class="search-result-title"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', block, re.S)
        if not m:
            m = re.search(r'href="([^"]*viewtopic\.php\?[^"]*)"[^>]*class="search-result-title"[^>]*>(.*?)</a>',
                          block, re.S)
        if not m:
            continue
        href, inner = m.group(1), m.group(2)
        tm = re.search(r"[?&]t=(\d+)", href)
        author = re.search(r'class="username[^"]*"[^>]*>(.*?)</a>', block, re.S)
        when = re.search(r'<span class="search-result-date">(.*?)</span>', block, re.S)
        content = re.search(r'<p class="search-result-content">(.*?)</p>', block, re.S)
        forum = re.search(r'<a class="search-result-forum"[^>]*>(.*?)</a>', block, re.S)
        items.append({
            "id": tm.group(1) if tm else None,
            "title": _clean_title(inner),
            "url": href,
            "author": _clean_title(author.group(1)) if author else None,
            "replies": None,
            "created": _clean_title(when.group(1)) if when else None,
            "snippet": _clean_title(content.group(1)) if content else "",
            "forum": _clean_title(forum.group(1)) if forum else None,
        })
    return items


def _phpbb_post(site_cfg: dict, url: str, thread_id: str, page: int, limit: int):
    base = site_cfg["base"]
    page = max(1, int(page))
    start = (page - 1) * 20
    target = url if start == 0 else _with_param(url, "start", str(start))
    r = _get(target, site_cfg["user_agent"])

    m = re.search(r'<h2 class="topic-title">(.*?)</h2>', r.text, re.S)
    if not m:
        m = re.search(r'<title>(.*?)</title>', r.text, re.S)
    title = _clean_title(m.group(1)) if m else None

    posts = []
    for chunk in re.split(r'(?=<div class="post" id="p\d+")', r.text)[1:]:
        author = re.search(r'class="username[^"]*"[^>]*>(.*?)</a>', chunk, re.S)
        when = re.search(r'class="postdate[^"]*"[^>]*title="([^"]*)"', chunk)
        content = re.search(r'<div class="content">(.*?)</div>\s*(?:<div class="postfooter"|</div>)',
                            chunk, re.S)
        if not content:
            content = re.search(r'<div class="content">(.*?)</div>', chunk, re.S)
        if not content:
            continue
        posts.append({
            "author": _clean_title(author.group(1)) if author else None,
            "created": when.group(1) if when else None,
            "body": _to_text(content.group(1)),
            "floor": None,
            "url": None,
        })
    posts = posts[: max(1, int(limit))]

    meta = {
        "engine_detected": "phpbb",
        "endpoint": target,
        "status": r.status,
        "pagination": f"支持：phpBB 3.x 翻页用 &start={(page - 1) * 20}（每页 20 条）；本次 page={page}",
        "thread_id": thread_id,
        "posts_parsed": len(posts),
        "note": ("phpBB 解析器基于 3.x 官方模板类名（search-result / post / content / postdate）。"
                 "本轮该站被 Cloudflare 挑战拦截，此解析器未经真实响应验证。"),
    }
    return {
        "title": title,
        "url": r.url,
        "author": posts[0]["author"] if posts else None,
        "created": posts[0]["created"] if posts else None,
        "body": next((p["body"] for p in posts if p["body"]), ""),
        "posts": posts,
    }, meta


# --------------------------------------------------------------------------
# engine 分派
# --------------------------------------------------------------------------

def _detect_station(site_cfg: dict):
    """探测 osdev 的实际站型。返回 "xenforo" / "phpbb"；被挑战则抛 Blocked。"""
    base = site_cfg["base"]
    probes = ["/", "/index.php"]
    seen = []
    for path in probes:
        r = _get(base + path, site_cfg["user_agent"])   # 挑战页会在这里抛 Blocked
        seen.append(f"{base + path} -> {r.status}")
        if _XF_ENGINE_RE.search(r.text):
            return "xenforo", seen, r
        if _PHPBB_ENGINE_RE.search(r.text):
            return "phpbb", seen, r
    raise RuntimeError(
        f"站型探测失败：两次探测都拿到 200 但既无 XenForo 特征也无 phpBB 特征。{seen}"
    )


def _dispatch_search(site_cfg: dict, query: str, page: int, limit: int):
    engine = site_cfg["engine"]

    if engine == "xenforo":
        return _xf_search(site_cfg, query, page, limit)

    if engine == "osdev":
        station, seen, r = _detect_station(site_cfg)     # 挑战页在此抛 Blocked
        if station == "xenforo":
            items, meta = _xf_search(site_cfg, query, page, limit)
            meta["station_type_probes"] = seen
            meta["note"] = "站型实测为 XenForo。" + meta["note"]
            return items, meta
        items, meta = _phpbb_search(site_cfg, query, page, limit)
        meta["station_type_probes"] = seen
        meta["note"] = "站型实测为 phpBB。" + meta["note"]
        return items, meta

    raise ValueError(f"sites_xenforo 不处理 engine={engine!r}")


def _phpbb_search(site_cfg: dict, query: str, page: int, limit: int):
    base = site_cfg["base"]
    page = max(1, int(page))
    params = {"keywords": query, "start": (page - 1) * 20}
    url = base + "/search.php?" + urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    r = _get(url, site_cfg["user_agent"])
    items = [i for i in _phpbb_search_items(r.text) if i["title"] and i["id"]]
    for i in items:
        i["url"] = urllib.parse.urljoin(base, i["url"])
    total = len(items)
    items = items[: max(1, int(limit))]
    meta = {
        "engine_detected": "phpbb",
        "endpoint": url,
        "status": r.status,
        "pagination": f"支持：phpBB 3.x 搜索翻页 &start={(page - 1) * 20}；本次 page={page}",
        "results_on_page": total,
        "returned": len(items),
        "note": "读 search.php 的 HTML（search-result / search-result-title）。",
    }
    return items, meta


def _dispatch_post(site_cfg: dict, ref: str, page: int, limit: int):
    engine = site_cfg["engine"]

    if engine == "xenforo":
        url, tid = RESOLVE(site_cfg, ref)
        return _xf_post(site_cfg, url, tid, page, limit)

    if engine == "osdev":
        station, seen, _r = _detect_station(site_cfg)
        url, tid = RESOLVE(site_cfg, ref)
        if station == "xenforo":
            data, meta = _xf_post(site_cfg, url, tid, page, limit)
        else:
            data, meta = _phpbb_post(site_cfg, url, tid, page, limit)
        meta["station_type_probes"] = seen
        return data, meta

    raise ValueError(f"sites_xenforo 不处理 engine={engine!r}")


# --------------------------------------------------------------------------
# 公开接口
# --------------------------------------------------------------------------

def SEARCH(site_cfg: dict, query: str, page: int, limit: int):
    return _dispatch_search(site_cfg, query, page, limit)


def POST(site_cfg: dict, ref: str, page: int, limit: int):
    return _dispatch_post(site_cfg, ref, page, limit)


def RESOLVE(site_cfg: dict, ref: str):
    raw = (ref or "").strip()
    base = site_cfg["base"].rstrip("/")
    engine = site_cfg["engine"]

    # XenForo: /threads/<slug>.<threadId>/  （也可能只给了数字 id）
    m = re.search(r"/threads/(?:[^/?#]*\.)?(\d+)", raw)
    if m:
        tid = m.group(1)
        slug_m = re.search(r"/threads/([^/?#]+?)\.(\d+)", raw)
        if slug_m:
            return f"{base}/threads/{slug_m.group(1)}.{tid}/", tid
        return f"{base}/threads/{tid}/", tid

    # phpBB: viewtopic.php?t=<id>
    m = re.search(r"[?&]t=(\d+)", raw)
    if m:
        return f"{base}/viewtopic.php?t={m.group(1)}", m.group(1)

    # 裸的 XenForo slug.id
    m = re.fullmatch(r"([^/?#\s]+)\.(\d+)", raw)
    if m:
        return f"{base}/threads/{m.group(1)}.{m.group(2)}/", m.group(2)

    # 裸数字 id：按 engine 决定默认站型
    if re.fullmatch(r"\d+", raw):
        if engine == "xenforo":
            return f"{base}/threads/{raw}/", raw
        return f"{base}/viewtopic.php?t={raw}", raw

    raise ValueError(
        f"无法从 {ref!r} 解析帖子地址（engine={engine}）。支持 XenForo "
        f"{base}/threads/<slug>.<id>/ 或 phpBB {base}/viewtopic.php?t=<id>，"
        "也可直接传纯数字 id。"
    )
