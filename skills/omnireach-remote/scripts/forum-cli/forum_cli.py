#!/usr/bin/env python3
"""forum_cli — 只读命令行工具，覆盖非 Discourse 引擎的社区站点。

只读：仅发起 GET/HEAD 请求读取公开内容。不登录、不发帖、不评论、不点赞、
不提交表单、不携带任何凭证或 Cookie、不执行浏览器自动化。

用法:
    forum_cli.py search <site> <query> [--page N] [--limit N]
    forum_cli.py post   <site> <url-or-id> [--page N] [--limit N]
    forum_cli.py sites

退出码:
    0  成功
    1  用法或 HTTP 错误
    75访问被阻断（403/401/429/503/挑战页/需要登录）

站点实现在同目录 sites_*.py 模块，每个模块必须暴露:
    SEARCH(site_cfg, query, page, limit) -> (list[dict], dict)
    POST(site_cfg, ref, page, limit)      -> (dict, dict)
    RESOLVE(site_cfg, ref)               -> (url, note_id)   # 把用户给的 ref 变成可请求的 URL
返回的第二个元素是 meta，用于 --verbose 时打印来源/状态等。
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys

EXIT_OK = 0
EXIT_ERR = 1
EXIT_BLOCKED = 75

# 站点注册表：key -> (base_url, engine, label, capability)
# capability 由 2026-10-19 实测反推，含义为该站命令行可真实读到的最高能力：
#   list-only          仅列表/标题过滤可用（站内搜索与正文均被阻断）
#   list+post          列表 + 正文可读，站内搜索不可用
#   list+post+search   列表 + 正文 + 站内搜索均可用
SITES = {
    "v2ex":       ("https://www.v2ex.com",        "v2ex",    "V2EX",                 "list+post"),
    "nodeseek":   ("https://www.nodeseek.com",    "nodeseek", "NodeSeek",            "list+post"),
    "linuxorg":   ("https://www.linux.org",       "xenforo", "Linux.org",            "list+post+search"),
    "osdev":      ("https://forum.osdev.org",     "osdev",   "OSDev 论坛",           "list-only"),
    "ubuntucn":   ("https://forum.ubuntu.org.cn", "phpbb",   "Ubuntu 中文论坛",       "list-only"),
    "enshan":     ("https://www.right.com.cn",   "discuz",  "恩山",                  "list+post"),
}

# engine -> 实现模块名
ENGINE_MODULE = {
    "v2ex": "sites_v2ex",
    "nodeseek": "sites_nodeseek",
    "xenforo": "sites_xenforo",
    "osdev": "sites_xenforo",
    "phpbb": "sites_phpbb",
    "discuz": "sites_discuz",
}

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0 Safari/537.36"
)


class Blocked(Exception):
    """站点拒绝了匿名只读访问。"""


def load_engine(engine: str):
    name = ENGINE_MODULE[engine]
    try:
        return importlib.import_module(name)
    except ImportError as exc:
        raise SystemExit(f"模块 {name}.py 未实现或导入失败: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser(prog="forum_cli", description="只读论坛命令行工具")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_sites = sub.add_parser("sites", help="列出支持站点")
    p_search = sub.add_parser("search", help="站内搜索")
    p_search.add_argument("site")
    p_search.add_argument("query")
    p_search.add_argument("--page", type=int, default=1)
    p_search.add_argument("--limit", type=int, default=5)

    p_post = sub.add_parser("post", help="读取主题/帖子正文")
    p_post.add_argument("site")
    p_post.add_argument("ref", help="URL 或站点原生 id")
    p_post.add_argument("--page", type=int, default=1)
    p_post.add_argument("--limit", type=int, default=5)

    for p in (p_search, p_post):
        p.add_argument("--verbose", action="store_true")

    args = parser.parse_args()

    if args.cmd == "sites":
        for key, (base, engine, label, cap) in SITES.items():
            print(f"{key:10s} {engine:10s} {cap:18s} {base}  {label}")
        return EXIT_OK

    if args.site not in SITES:
        print(f"未知站点 {args.site!r}；可用: {', '.join(SITES)}", file=sys.stderr)
        return EXIT_ERR

    base, engine, label, cap = SITES[args.site]
    site_cfg = {"key": args.site, "base": base, "engine": engine, "label": label,
                "capability": cap, "user_agent": USER_AGENT}

    mod = load_engine(engine)
    try:
        if args.cmd == "search":
            items, meta = mod.SEARCH(site_cfg, args.query, args.page, args.limit)
            payload = {"ok": True, "site": args.site, "query": args.query,
                       "page": args.page, "count": len(items), "items": items}
        else:
            data, meta = mod.POST(site_cfg, args.ref, args.page, args.limit)
            payload = {"ok": True, "site": args.site, "ref": args.ref,
                       "page": args.page, "post": data}
    except Blocked as exc:
        print(json.dumps({"ok": False, "site": args.site,
                          "error": {"code": "blocked", "message": str(exc)}},
                         ensure_ascii=False, indent=2))
        return EXIT_BLOCKED
    except Exception as exc:  # noqa: BLE001 - CLI 顶层需要把任何异常转成退出码
        print(json.dumps({"ok": False, "site": args.site,
                          "error": {"code": type(exc).__name__, "message": str(exc)}},
                         ensure_ascii=False, indent=2))
        return EXIT_ERR

    if args.verbose:
        payload["meta"] = meta
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())