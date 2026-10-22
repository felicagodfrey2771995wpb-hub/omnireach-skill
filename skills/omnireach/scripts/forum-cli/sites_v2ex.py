"""V2EX 只读站点模块。

来源说明（重要，见 --verbose 输出的 meta.note）
------------------------------------------------
V2EX 官方 API v1 (https://www.v2ex.com/api/...) 在匿名请求下一律返回
HTTP 403 + Cloudflare "Just a moment..." 挑战页（含 / 首页本身也是 403），
纯 urllib 无法通过。因此本模块的检索与正文读取全部走**第三方只读索引
SoV2EX** (https://www.sov2ex.com/api/search)，不是本站接口。

SoV2EX 只暴露一个 JSON 端点（其 SPA bundle 中唯一硬编码的接口）：
    GET https://www.sov2ex.com/api/search
        q     查询串（空白分隔的词按 OR 匹配）
        sort  sumup | created
        order 0 降序 | 1 升序
        from  偏移量，(page-1)*size
        size  1..50（服务端硬上限，>50 返回 400）
        node / username / gte / lte  可选过滤
响应：{"took":ms,"total":N,"hits":[{"_id":topic_id,"_source":{...}}]}
_source 字段：id / title / content(首帖 Markdown) / member / replies /
             created / node

SoV2EX 没有 "按 topic id 取详情" 的端点，所以 POST 只能用标题（来自 ref
URL 里的 slug）反查。若 slug 反查命中不了，会抛 Blocked 并说明原因。
"""

from __future__ import annotations

import gzip
import json
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

SOV2EX_SEARCH = "https://www.sov2ex.com/api/search"
V2EX_TOPIC_BASE = "https://www.v2ex.com/t/"
SO_SIZE_MAX = 50          # SoV2EX 服务端硬上限
SO_LOOKUP_PAGES = 3       # POST 反查最多翻 3 页 * 50 = 150 个候选
V2EX_TOPIC_API = "https://www.v2ex.com/api/topics/show.json"  # 官方单帖端点，匿名可用（无需 slug）
V2EX_SIMPLE_UA = "Mozilla/5.0"  # V2EX WAF 对完整 Chrome UA 反而 403，简单 UA 放行（实测 2026-10-20）

_TIMEOUT = 20
_RETRIES = 2
_BACKOFF = 1.5

_MD_STRIP = [
    (re.compile(r"!\[[^\]]*\]\([^)]*\)"), " "),
    (re.compile(r"\[([^\]]*)\]\([^)]*\)"), r"\1"),
    (re.compile(r"^\s{0,3}#{1,6}\s*", re.M), ""),
    (re.compile(r"^\s{0,3}>\s?", re.M), ""),
    (re.compile(r"`{1,3}"), ""),
    (re.compile(r"(\*\*|__|\*|_|~~)"), ""),
    (re.compile(r"^\s{0,3}[-*+]\s+", re.M), "- "),
    (re.compile(r"<[^>]+>"), " "),
]


def _get_json(url: str, ua: str):
    """GET 一个 JSON 端点。返回 (status, decoded_body)。失败按需抛 Blocked。"""
    last = None
    for attempt in range(_RETRIES + 1):
        req = urllib.request.Request(
            url,
            method="GET",
            headers={
                "User-Agent": ua,
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
                raw = resp.read()
                if resp.headers.get("Content-Encoding") == "gzip":
                    raw = gzip.decompress(raw)
                return resp.status, json.loads(raw.decode("utf-8", "replace"))
        except urllib.error.HTTPError as exc:
            body = b""
            try:
                body = exc.read()
                if exc.headers.get("Content-Encoding") == "gzip":
                    body = gzip.decompress(body)
            except Exception:
                pass
            snippet = body.decode("utf-8", "replace")[:160]
            host = urllib.parse.urlparse(url).netloc or "unknown-host"
            if exc.code in (401, 403, 429, 503):
                raise Blocked(
                    f"{host} HTTP {exc.code} 拒绝匿名访问: {snippet}"
                ) from exc
            last = RuntimeError(f"{host} HTTP {exc.code}: {snippet}")
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            last = exc
        if attempt < _RETRIES:
            time.sleep(_BACKOFF * (attempt + 1))
    raise last if last else RuntimeError(
        f"{urllib.parse.urlparse(url).netloc or 'unknown-host'} 请求失败")


def _plain(md: str) -> str:
    """把 SoV2EX 返回的 Markdown 首帖压成纯文本正文。"""
    if not md:
        return ""
    text = md.replace("\r\n", "\n").replace("\r", "\n")
    for pattern, repl in _MD_STRIP:
        text = pattern.sub(repl, text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _slug(title: str) -> str:
    """生成 V2EX 风格 slug：ASCII 词、小写、非字母数字折叠为 '-'、截断。"""
    words = re.findall(r"[0-9A-Za-z]+", title or "")
    out = []
    for w in words:
        for part in re.split(r"(?<=[a-z0-9])(?=[A-Z0-9])", w):
            if part:
                out.append(part.lower())
    return "-".join(out)[:48].strip("-")


def _topic_url(topic_id, title: str) -> str:
    slug = _slug(title)
    return f"{V2EX_TOPIC_BASE}{topic_id}" + (f"/{slug}" if slug else "")


def _query_from_slug(slug: str) -> str:
    """把 URL slug 还原成 SoV2EX 可用的查询串。"""
    parts = [p for p in re.split(r"[-_]+", slug or "") if p and len(p) > 1]
    seen, uniq = set(), []
    for p in parts:
        low = p.lower()
        if low not in seen:
            seen.add(low)
            uniq.append(p)
    return " ".join(uniq)


def _hit_to_item(hit: dict) -> dict:
    src = hit.get("_source") or {}
    tid = src.get("id") or hit.get("_id")
    title = (src.get("title") or "").strip()
    return {
        "id": tid,
        "title": title,
        "url": _topic_url(tid, title),
        "author": src.get("member"),
        "replies": src.get("replies"),
        "created": src.get("created"),
        "node": src.get("node"),
    }


# --------------------------------------------------------------------------
# 公开接口
# --------------------------------------------------------------------------

def SEARCH(site_cfg: dict, query: str, page: int, limit: int):
    page = max(1, int(page))
    size = max(1, min(int(limit), SO_SIZE_MAX))
    params = {
        "q": query,
        "sort": "sumup",
        "order": "0",
        "from": (page - 1) * size,
        "size": size,
    }
    url = SOV2EX_SEARCH + "?" + urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    status, data = _get_json(url, site_cfg["user_agent"])

    items = [_hit_to_item(h) for h in data.get("hits") or []]
    items = [i for i in items if i["title"] and i["id"]]

    meta = {
        "endpoint": url,
        "status": status,
        "pagination": (
            f"支持：offset = (page-1)*size；SoV2EX 服务端 size 上限 {SO_SIZE_MAX}"
            f"（>50 返回 400），本次 size={size}, from={(page - 1) * size}"
        ),
        "total_hits": data.get("total"),
        "took_ms": data.get("took"),
        "note": (
            "数据来自第三方只读索引 SoV2EX (https://www.sov2ex.com/api/search)，"
            "不是 V2EX 官方 API。官方 API v1 与 v2ex.com 首页在本机匿名 GET 下"
            "一律返回 HTTP 403 + Cloudflare 'Just a moment...' 挑战页，"
            "本模块因此不请求 www.v2ex.com。索引为快照，可能滞后于原站；"
            "url 指向 V2EX 原站，slug 由标题生成。"
        ),
        "source": "third-party-index:sov2ex",
    }
    return items, meta


def RESOLVE(site_cfg: dict, ref: str):
    raw = (ref or "").strip()
    m = re.search(r"/t/(\d+)(?:/([^/?#]+))?", raw)
    if m:
        tid, slug = m.group(1), m.group(2)
    elif re.fullmatch(r"\d+", raw):
        tid, slug = raw, None
    else:
        raise ValueError(
            f"无法从 {ref!r} 解析 V2EX topic id；"
            "支持 https://www.v2ex.com/t/<id>[/<slug>] 或纯数字 id"
        )
    url = f"{V2EX_TOPIC_BASE}{tid}" + (f"/{slug}" if slug else "")
    return url, tid


def _official_topic(site_cfg: dict, tid: str):
    """Read one topic through the official V2EX API.

    www.v2ex.com HTML is behind a Cloudflare challenge for anonymous clients,
    but /api/topics/show.json?id=<id> still answers anonymously. It needs no
    slug, which is exactly what the SoV2EX slug reverse-lookup lacks for
    Chinese-titled topics (a Chinese title yields an empty slug).
    """
    url = f"{V2EX_TOPIC_API}?id={urllib.parse.quote(str(tid))}"
    status, data = _get_json(url, V2EX_SIMPLE_UA)
    if status != 200 or not data:
        return None, url, status
    if isinstance(data, dict):
        data = [data]
    if not data:
        return None, url, status
    return data[0], url, status


def _official_result(official: dict, tid: str, meta: dict):
    """把官方单帖端点返回的 topic 组装成统一的 post 结构。"""
    body = _plain(official.get("content_rendered") or official.get("content") or "")
    meta["source"] = "official-api:v2ex"
    meta["pagination"] = "官方单帖端点只返回首帖；楼层正文需 /api/replies/show.json（CF 403 拦截）"
    meta["note"] = (
        "正文取自 V2EX 官方 api/topics/show.json（匿名可用，无需 slug）。"
        "posts 仅含首帖：官方 replies API 被 Cloudflare 403 拦截。"
        f" replies 计数（官方）={official.get('replies')}"
    )
    return {
        "title": (official.get("title") or "").strip(),
        "url": f"{V2EX_TOPIC_BASE}{tid}",
        "author": (official.get("member") or {}).get("username"),
        "created": official.get("created"),
        "replies": official.get("replies"),
        "node": (official.get("node") or {}).get("title"),
        "body": body,
        "posts": [{
            "author": (official.get("member") or {}).get("username"),
            "body": body,
            "created": official.get("created"),
            "floor": 0,
            "is_op": True,
        }],
    }, meta


def POST(site_cfg: dict, ref: str, page: int, limit: int):
    page = max(1, int(page))
    url, tid = RESOLVE(site_cfg, ref)
    slug = url.split("/", 5)[-1] if "/" in url[len(V2EX_TOPIC_BASE):] else ""
    q = _query_from_slug(slug)

    meta = {
        "endpoint": None,
        "status": None,
        "pagination": "不支持",
        "note": "",
        "source": "third-party-index:sov2ex",
    }

    official = None
    if not q:
        official, off_url, off_status = _official_topic(site_cfg, tid)
        meta["endpoint"] = off_url
        meta["status"] = off_status
        if not official:
            meta["note"] = (
                f"ref {ref!r} 不含标题 slug，且官方 {V2EX_TOPIC_API} 也没有返回内容"
                f"（status={off_status}）。中文标题的 slug 恒为空，"
                "这类主题只能靠官方端点读。"
            )
            raise Blocked(meta["note"])
        return _official_result(official, tid, meta)

    status = 0
    found = None
    scanned = []
    for p in range(SO_LOOKUP_PAGES):
        frm = p * SO_SIZE_MAX
        params = {"q": q, "sort": "sumup", "order": "0", "from": frm, "size": SO_SIZE_MAX}
        ep = SOV2EX_SEARCH + "?" + urllib.parse.urlencode(
            params, quote_via=urllib.parse.quote
        )
        status, data = _get_json(ep, site_cfg["user_agent"])
        scanned.append(ep)
        hits = data.get("hits") or []
        for hit in hits:
            if str((hit.get("_source") or {}).get("id") or hit.get("_id")) == str(tid):
                found = hit
                break
        if found or not hits:
            break

    meta["endpoint"] = scanned[0] if scanned else None
    meta["endpoints_scanned"] = scanned
    meta["status"] = status
    meta["lookup_query"] = q
    meta["lookup_pages_scanned"] = len(scanned)

    if not found and official is None:
        official, off_url, off_status = _official_topic(site_cfg, tid)
        if official:
            meta["endpoint"] = off_url
            meta["status"] = off_status

    if official is not None:
        return _official_result(official, tid, meta)

    if not found:
        meta["note"] = (
            f"SoV2EX 按 slug 词 {q!r} 翻了 {len(scanned)} 页（{len(scanned) * SO_SIZE_MAX} "
            f"个候选）仍未命中 topic {tid}。多数情况下 slug 里的 ASCII 词不足以"
            "唯一确定一个中文标题的主题。"
        )
        raise Blocked(meta["note"])

    src = found.get("_source") or {}
    body = _plain(src.get("content") or "")
    meta["pagination"] = (
        "不支持：SoV2EX 只索引主题首帖，不提供回复正文；"
        "V2EX /api/replies/show.json 被 Cloudflare 403 拦截，故 posts 只含首帖"
    )
    meta["note"] = (
        "正文取自 SoV2EX 索引的 _source.content（首帖 Markdown，已转纯文本），"
        "非实时抓取。posts 仅含首帖一条：SoV2EX 不暴露楼层正文，"
        "V2EX 官方 replies API 被 Cloudflare 403 拦截。"
        f" replies 计数（来自索引，可能滞后）={src.get('replies')}"
    )

    if not body:
        meta["note"] += "；索引返回的 content 为空"

    data = {
        "title": (src.get("title") or "").strip(),
        "url": _topic_url(tid, (src.get("title") or "").strip()),
        "author": src.get("member"),
        "created": src.get("created"),
        "replies": src.get("replies"),
        "node": src.get("node"),
        "body": body,
        "posts": [
            {
                "author": src.get("member"),
                "body": body,
                "created": src.get("created"),
                "floor": 0,
                "is_op": True,
            }
        ],
    }
    return data, meta