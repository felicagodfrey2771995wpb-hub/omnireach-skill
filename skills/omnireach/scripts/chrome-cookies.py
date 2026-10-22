#!/usr/bin/env python3
"""Dump Chrome cookies as a classic Netscape cookie file.

Why this file exists: the Go-side tooling only accepts the classic 7-field
format. Modern Chrome stores a 10-field variant that older parsers read as
one giant cookie string, and the magic "# Netscape HTTP Cookie File" line is
mandatory. Output here is always the classic format.

Exit codes (callers must not treat every non-zero code as "no cookies"):
  0  cookies written to stdout
  2  no usable cookie backend (browser_cookie3 and pycookiecheat both absent)
  3  a backend exists but the read/decrypt failed
  4  the backend worked, but this domain has no cookies
"""
import os
import subprocess
import sys

DOMAIN = sys.argv[1] if len(sys.argv) > 1 else "youtube.com"
BROWSER = sys.argv[2] if len(sys.argv) > 2 else "chrome"

# The linuxdo runtime venv ships pycookiecheat; re-exec under it when the
# current interpreter has no cookie backend at all.
FALLBACK_PYTHON = "/Users/mac/Work/projects/codex/app-data/linuxdo-browser/.venv/bin/python"


def _reexec_with_fallback():
    if os.environ.get("OMNIREACH_COOKIE_REEXEC"):
        return False
    try:
        same = os.path.realpath(sys.executable) == os.path.realpath(FALLBACK_PYTHON)
    except OSError:
        same = False
    if same or not os.path.exists(FALLBACK_PYTHON):
        return False
    env = dict(os.environ, OMNIREACH_COOKIE_REEXEC="1")
    raise SystemExit(subprocess.call(
        [FALLBACK_PYTHON, os.path.abspath(__file__), DOMAIN, BROWSER], env=env))


def _collect():
    """Return a list of cookie dicts, or raise a BackendError."""
    try:
        import browser_cookie3
        getter = getattr(browser_cookie3, BROWSER, None)
        if getter is not None:
            jar = getter(domain_name=DOMAIN)
            return [c for c in jar if getattr(c, "name", None)]
    except ImportError:
        pass
    except Exception as exc:
        raise BackendError("browser_cookie3 读取/解密失败: %s: %s" % (type(exc).__name__, exc))
    try:
        import pycookiecheat
    except ImportError:
        raise BackendError("没有可用的 cookie 后端（browser_cookie3 / pycookiecheat 都没装）")
    try:
        raw = pycookiecheat.chrome_cookies(DOMAIN)
    except Exception as exc:
        raise BackendError("pycookiecheat 读取/解密失败: %s: %s" % (type(exc).__name__, exc))
    if isinstance(raw, dict):
        raw = [{"name": k, "value": v} for k, v in raw.items()]
    out = []
    for c in raw or []:
        if isinstance(c, dict):
            name = c.get("name")
            value = c.get("value")
            domain = c.get("domain")
            expires = c.get("expires")
            httponly = bool(c.get("httponly") or c.get("HttpOnly"))
        else:
            name = getattr(c, "name", None)
            value = getattr(c, "value", None)
            domain = getattr(c, "domain", None)
            expires = getattr(c, "expires", None)
            httponly = False
        if name:
            out.append({"name": name, "value": value, "domain": domain,
                        "expires": expires, "httponly": httponly})
    return out


class BackendError(Exception):
    pass


def main():
    try:
        jar = _collect()
    except BackendError as exc:
        if "没有可用的 cookie 后端" in str(exc):
            _reexec_with_fallback()
        print("chrome-cookies: %s" % exc, file=sys.stderr)
        return 2 if "没有可用的 cookie 后端" in str(exc) else 3
    if not jar:
        print("chrome-cookies: Chrome 里没有 %s 的 cookie" % DOMAIN, file=sys.stderr)
        return 4
    print("# Netscape HTTP Cookie File")
    for c in jar:
        value = str(c["value"] or "").replace("\n", " ").replace("\r", " ").replace("\t", " ")
        name = str(c["name"]).replace("\t", " ").replace("\n", " ")
        try:
            expires = int(c["expires"]) if c.get("expires") else 0
        except (TypeError, ValueError):
            expires = 0
        domain = (c.get("domain") or "." + DOMAIN).lstrip(".")
        flag = "TRUE"
        if c.get("httponly"):
            print("\t".join(["#HttpOnly_." + domain, flag, "/", "TRUE", str(expires), name, value]))
        else:
            print("\t".join(["." + domain, flag, "/", "TRUE", str(expires), name, value]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
