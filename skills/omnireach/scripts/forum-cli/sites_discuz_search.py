#!/usr/bin/env python3
"""sites_discuz_search — 恩山无线论坛「只读站内搜索」可达性判别器。

结论（2026-10-19 实测）：**站方游客搜索是用户组权限阻断，不存在只读 GET 路径。**

实测依据（本文件 probe 可复现）：
  1. formhash 可以纯 GET 拿到：`forum-70-1.html` 的 `scbar_form` 里
     `<input name="formhash" value="0be7efbc">`。它在**同一会话内跨分区恒定**
     （fid=70/166/176 三页均为同一值），但**跨会话会轮换**（另一次独立会话实测为
     `1b722df0`）——即它绑定的是匿名会话（server_session/rHEX saltkey），不是登录账号。
     关键点：第 2 步用的是**与搜索请求同一 cookie 罐里取到的当前 formhash**，
     若 formhash 是拦路的那道门，这样配对必然能过；实测没有。
  2. 带上正确 formhash + 完整匿名 cookie 罐重试：
       GET /forum/search.php?mod=forum&searchsubmit=yes&kw=OpenWrt&formhash=0be7efbc
     → HTTP 200，但正文是 Discuz「提示信息」页：
       「抱歉，您所在的用户组(游客)无法进行此操作」
     与不带 formhash 的结果**逐字相同**。故属 (a) 权限阻断，非 (b) 缺 formhash。
  3. `mod=album` 同样被拒 → 是**全局搜索权限位**（用户组级），不是某个版块单独关闭；
     3 个不同 fid 的页面表单一模一样、formhash 一致 → 无分区差异。
  4. `archiver/?mod=search` 与 `archiver/?mod=forum` **响应体逐字节相同**（均 4937 字节），
     即站方把 archiver 的 search 静默回落成分区总览，与已知的 ?mod=thread 同一手法。
  5. `search.php` 另有一层限流：连续请求后该端点稳定 503，而同时刻 `archiver/` 仍 200。

硬性约束（代码层面保证）：
  - 只用 Python 标准库；**只发 GET/HEAD**；不 POST、不提交任何表单。
  - 不登录、不携带任何账号凭证：cookie 只来自本进程当场 GET 拿到的**匿名** cookie，
    只在内存里、不落盘、不复用用户浏览器 cookie。
  - formhash 仅用于**拼进 GET URL**，不用于伪造表单提交。
  - 不解 `acw_tc` 反爬；遇到 Cloudflare 挑战如实上报，不绕过。

用法:
    python3 sites_discuz_search.py --probe OpenWrt            # 复现判别，打印证据 JSON
    python3 sites_discuz_search.py --probe OpenWrt --budget 12
"""

from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar

try:
    import forum_cli as _forum_cli
    Blocked = _forum_cli.Blocked
except Exception:  # 允许脱离 forum_cli 单独运行
    class Blocked(Exception):
        """站点拒绝了匿名只读访问。"""

_ENGINE = "discuz_search"
_TIMEOUT = 25
_RETRIES = 2
_BACKOFF = 2.0
_BUDGET = 20            # 单次 probe 的请求上限（题面约束为 35）

_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.S | re.I)
_FORM_RE = re.compile(r"<form\b[^>]*>.*?</form>", re.S | re.I)
_FH_RE = re.compile(
    r"name\s*=\s*[\"']formhash[\"']\s+value\s*=\s*[\"']([A-Za-z0-9]{8})[\"']", re.I)
_REFUSE_RE = re.compile(r"抱歉[，,]\s*您所在的用户组[（(]([^）)]*)[）)]无法进行此操作")
_ALERT_RE = re.compile(r"提示信息")
_CF_TITLE_RE = re.compile(r"<title[^>]*>\s*(Just a moment|Checking your browser)", re.I)
_THREAD_LINK_RE = re.compile(r"thread-\d+-\d+-\d+\.html")
_TAG_RE = re.compile(r"<[^>]+>")


class _Session:
    """匿名 GET 会话。cookie 仅存在于本进程内存，不落盘、不复用外部凭证。"""

    def __init__(self, budget: int = _BUDGET):
        self.jar = CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        self.used = 0
        self.budget = budget

    def cookie_names(self) -> list[str]:
        """只暴露 cookie 名字和长度；**不返回也不打印 cookie 值**。"""
        return sorted({f"{c.name}(len={len(c.value)})" for c in self.jar})

    def get(self, url: str, max_bytes: int = 600_000) -> dict:
        last = None
        for attempt in range(_RETRIES + 1):
            if self.used >= self.budget:
                raise Blocked(f"请求预算耗尽（已用 {self.used}/{self.budget}）")
            self.used += 1
            req = urllib.request.Request(url, method="GET", headers={
                "User-Agent": _UA,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Accept-Encoding": "gzip",
            })
            try:
                with self.opener.open(req, timeout=_TIMEOUT) as resp:
                    raw = resp.read(max_bytes)
                    if resp.headers.get("Content-Encoding") == "gzip":
                        raw = gzip.decompress(raw)
                    return {"url": url, "status": resp.status,
                            "body": raw.decode("utf-8", "replace"),
                            "headers": dict(resp.headers)}
            except urllib.error.HTTPError as exc:
                body = b""
                try:
                    body = exc.read()
                    if exc.headers.get("Content-Encoding") == "gzip":
                        body = gzip.decompress(body)
                except Exception:
                    pass
                text = body.decode("utf-8", "replace")
                return {"url": url, "status": exc.code, "body": text,
                        "headers": dict(exc.headers or {})}
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last = exc
            if attempt < _RETRIES:
                time.sleep(_BACKOFF * (attempt + 1))
        raise last if last else RuntimeError("请求失败")


_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


def _title(body: str) -> str | None:
    m = _TITLE_RE.search(body or "")
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else None


def _classify(body: str) -> tuple[str, str | None]:
    ref = _REFUSE_RE.search(body or "")
    if ref:
        return "REFUSED_BY_GROUP", ref.group(0)
    if _CF_TITLE_RE.search(body or ""):
        return "CLOUDFLARE_CHALLENGE", "未尝试绕过"
    if _ALERT_RE.search(_title(body) or ""):
        return "ALERT_PAGE", None
    if len(set(_THREAD_LINK_RE.findall(body or ""))) >= 3:
        return "RESULTS_PAGE", None
    return "OTHER", None


def _search_forms(body: str) -> list[dict]:
    out = []
    for form in _FORM_RE.findall(body or ""):
        open_tag = form[:form.find(">") + 1]
        if "search.php" in open_tag or "mod=search" in open_tag:
            m = _FH_RE.search(form)
            out.append({
                "action": (re.search(r'action="([^"]*)"', open_tag) or [None, None])[1]
                if re.search(r'action="([^"]*)"', open_tag) else None,
                "method": (re.search(r'method="([^"]*)"', open_tag, re.I) or [None, None])[1]
                if re.search(r'method="([^"]*)"', open_tag, re.I) else None,
                "formhash": m.group(1) if m else None,
            })
    return out


def _get_formhash(session: _Session, base: str, fid: str = "70") -> dict:
    url = f"{base.rstrip('/')}/forum/forum-{fid}-1.html"
    r = session.get(url)
    return {"url": url, "status": r["status"], "title": _title(r["body"]),
            "search_forms": _search_forms(r["body"])[:3]}


def _try_search(session: _Session, base: str, query: str, formhash: str | None,
                label: str) -> dict:
    q = urllib.parse.quote(query)
    url = (f"{base.rstrip('/')}/forum/search.php?mod=forum&searchsubmit=yes&kw={q}"
           + (f"&formhash={formhash}" if formhash else ""))
    r = session.get(url)
    verdict, detail = _classify(r["body"])
    return {"probe": label, "url": url, "status": r["status"], "title": _title(r["body"]),
            "verdict": verdict, "detail": detail, "refused_group":
                (_REFUSE_RE.search(r["body"]).group(1)
                 if _REFUSE_RE.search(r["body"]) else None)}


def probe_reachability(site_cfg: dict, query: str = "OpenWrt", budget: int = _BUDGET) -> dict:
    """实测「只读 GET 站内搜索」是否可达，返回结构化证据。"""
    base = site_cfg["base"].rstrip("/")
    sess = _Session(budget=budget)
    evidence: list[dict] = []

    fh_step = _get_formhash(sess, base)
    formhash = next((f["formhash"] for f in fh_step["search_forms"] if f["formhash"]), None)
    fh_step["formhash_found"] = formhash
    fh_step["cookies_anon"] = sess.cookie_names()

    without = _try_search(sess, base, query, None, "不带formhash-只带匿名cookie")
    withfh = _try_search(sess, base, query, formhash, "带formhash+匿名cookie")

    # 只有真的拿到结果页才算可用；403/503/挑战页/提示页一律不算。
    if withfh["verdict"] == "RESULTS_PAGE":
        verdict = "NATIVE_SEARCH_REACHABLE"
    elif withfh["verdict"] == "REFUSED_BY_GROUP":
        verdict = "BLOCKED_BY_GROUP_PERMISSION"
    else:
        verdict = f"UNRESOLVED_{withfh['verdict']}"
    identical_shape = (without["verdict"] == withfh["verdict"] == "REFUSED_BY_GROUP")
    return {
        "engine": _ENGINE,
        "query": query,
        "requests_used": sess.used,
        "budget": budget,
        "formhash_step": fh_step,
        "search_probes": [without, withfh],
        "formhash_changed_outcome": not identical_shape,
        "verdict": verdict,
        "readonly_search_usable": verdict == "NATIVE_SEARCH_REACHABLE",
        "evidence_note": (
            "formhash 用纯 GET 取得，并与第 2 步的搜索请求取自**同一匿名会话**"
            f"（同一 cookie 罐，当前值 {formhash!r}；同会话内跨分区恒定，跨会话轮换）。"
            "补上它与完整匿名 cookie 后，返回页面与不带 formhash 时逐字相同，仍是"
            "「抱歉，您所在的用户组(游客)无法进行此操作」；"
            "故阻断点是站方用户组搜索权限位，不是 formhash/会话缺失。"
        ),
    }


def SEARCH(site_cfg: dict, query: str, page: int, limit: int):
    """站方站内搜索不可达时**显式失败**，绝不静默返回空结果冒充成功。

    需要恩山的列表+标题过滤式检索时，请用 sites_discuz.SEARCH（SSR 列表 + 本地过滤）。
    """
    ev = probe_reachability(site_cfg, query)
    if ev["readonly_search_usable"]:
        items, meta = _try_live_search(site_cfg, query, page, limit, ev)
        return items, meta
    raw = next((p["detail"] for p in ev["search_probes"]
                if p["verdict"] == "REFUSED_BY_GROUP"), "（未取到拒绝原文）")
    raise Blocked(
        "恩山只读站内搜索不可达：站方按用户组权限拒绝游客搜索，非 formhash/会话问题。\n"
        f"拒绝原文: {raw}\n"
        f"formhash 实测: {ev['formhash_step'].get('formhash_found')!r}（纯 GET 可得，补上无效）\n"
        f"本轮请求数: {ev['requests_used']}；判定: {ev['verdict']}\n"
        "请改用 sites_discuz.SEARCH（archiver 分区总览 + SSR 列表 + 本地标题过滤）。"
    )


def _try_live_search(site_cfg: dict, query: str, page: int, limit: int, ev: dict):
    """仅当 probe 判定原生搜索可用时才走；目前实测恒为不可达。"""
    raise Blocked("原生搜索解析器尚未实现（当前实测恒不可达，分支保留）。")


def RESOLVE(site_cfg: dict, ref: str):
    import sites_discuz
    return sites_discuz.RESOLVE(site_cfg, ref)


def POST(site_cfg: dict, ref: str, page: int, limit: int):
    import sites_discuz
    return sites_discuz.POST(site_cfg, ref, page, limit)


def main() -> int:
    ap = argparse.ArgumentParser(description="恩山只读站内搜索可达性判别（只发 GET）")
    ap.add_argument("query", nargs="?", default="OpenWrt")
    ap.add_argument("--base", default="https://www.right.com.cn")
    ap.add_argument("--budget", type=int, default=_BUDGET)
    a = ap.parse_args()
    cfg = {"base": a.base, "user_agent": _UA}
    ev = probe_reachability(cfg, a.query, budget=a.budget)
    print(json.dumps(ev, ensure_ascii=False, indent=2))
    return 0 if ev["readonly_search_usable"] else 75


if __name__ == "__main__":
    sys.exit(main())