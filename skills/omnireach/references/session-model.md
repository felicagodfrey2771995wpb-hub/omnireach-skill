# Session model and signature-failure diagnosis

Established 2026-10-19 on this machine by a read-only CLI acceptance run (F04–F10). It generalizes beyond the six platforms in that run.

## 0. Where this skill lives on each client

This skill is **one shared source**; every client reaches it through a symlink, so the content is identical everywhere. Only the path differs. In the examples below, `<skill-root>` means the client-facing skill directory:

| Client | `<skill-root>` |
|---|---|
| Codex | `~/.codex/skills/omnireach` |
| OpenCode | `~/.config/opencode/skills/omnireach` |
| Hermes | `~/.hermes/skills/omnireach` |
| WorkBuddy | `~/.workbuddy/skills/omnireach` |
| Claude | `~/.claude/skills/omnireach` |

Canonical source (all clients symlink here): `/Users/mac/LocalSkills/统一技能库/sources/desktop-local/common/omnireach/`. Run the helper scripts through `<skill-root>/scripts/...`; if your client exposes the skill under a different directory, resolve `<skill-root>` from the skill listing rather than hardcoding another client's path.

## 1. Session model: one Chrome session, no per-platform login

**Rule: a platform session comes from the user's Chrome cookies, not from a login flow you run.** Do not create accounts, scan QR codes, or export cookie values into evidence. The user stays logged in; the tools read that session.

| Platform | Mechanism | User action | Notes |
|---|---|---|---|
| XiaoHongShu | `xhs --cookie-source chrome search "q" --json` | keep Chrome logged in | The CLI **prefers its saved cookie cache** (`~/.xiaohongshu-cli/cookies.json`) and re-reads Chrome only when that cache is older than 7 days or a session-expired error forces one refresh (corrected 2026-10-21 from the `xhs` 0.6.4 source: it does **not** live-read Chrome on every call). Refresh it deliberately with `xhs login --cookie-source chrome` — extracts from the logged-in browser, no QR, no re-login |
| Bilibili | `bili-subs` / `yt-dlp --cookies-from-browser chrome` | keep Chrome logged in | Live read on every call; never stale |
| YouTube | `yt-dlp --cookies-from-browser chrome` | keep Chrome logged in | Live read on every call |
| Zhihu | `zhihu auth import -b chrome` | run once; rerun when the profile expires | Import persists into a CLI profile; **no QR re-scan needed** |

Check all of them at once:

```bash
<skill-root>/scripts/session-check
```

**Expiry semantics**: an expired platform cookie is not a reason to ask the user to re-authenticate by hand. If the user is still logged in to the site in Chrome, re-import or re-read. Two cases genuinely need the user, and neither needs a QR scan: a **server-side** session that is void (cookies present and unexpired but the API still returns `-100` / `SessionExpiredError`) requires the user to log in again in the browser; the **Zhihu CLI profile** expires on its own and is repaired by `zhihu auth import -b chrome`. Everything else is repaired by the automatic Chrome read. **XiaoHongShu exception (corrected 2026-10-21):** its CLI does not re-read Chrome on every call — it prefers its saved cookie cache and re-reads only when that cache is older than 7 days or a session-expired error forces one refresh — so refresh it explicitly with `xhs login --cookie-source chrome` after any browser-side change. A `verification_required` response (HTTP 461/471) is a **human-verification request, not an expiry**: it needs the user to complete the check in the browser, then a cache refresh, then slower retries; it is not repaired by re-reading cookies alone.

**Side effects of the read-only tools** — "read-only" describes the *remote* effect; these helpers still touch local files, so know them before running one in a read-only task:
- `scripts/session-check` **rewrites** the XiaoHongShu session file when it refreshes it from Chrome (a local cache write, not a remote one). It reads the three domains in parallel, so its total time is bounded by the slowest single read (~40 s worst case) instead of the sum of three.
- `scripts/bili-comments` writes a **temporary** 600-permission Netscape cookie file and deletes it afterwards; `scripts/yt` writes a temporary cookie file (also removed) and, with `--subs --out`, subtitle files where you point it.
- `scripts/yt --print-subs` leaves **no subtitle file**: it uses a self-deleting temp directory and prints the subtitle text to stdout. It is still not side-effect-free — the PO token provider writes a persistent log at `/tmp/bgutil-pot.log` and leaves a Node process listening on 127.0.0.1:4416, and if the provider's build output or `node_modules` is missing the wrapper will run `npx tsc` / `npm install` first. In a sandbox the provider cannot bind loopback (`listen EPERM`); run it on the host network.
- `scripts/yt --search` without `--compact` prints the full yt-dlp JSON dump (tens of MB); use `--compact` for a one-line-per-result summary.
- `scripts/yt` bounds every yt-dlp invocation with `--call-timeout` (default 300 s) and exits 124 when it trips, so a stuck cookie read can no longer hang the command.

**Do not** create Shadowrocket split rules to work around a platform problem. Verify first whether the exit IP matters at all: on 2026-10-19 the same failures reproduced on a domestic-CN exit, and two platforms worked on both exits. YouTube is the only channel that needs a proxy (GFW), and a global proxy switch is enough — no per-domain rules.

## 2. Diagnosing a signature failure: swap one header

A `4xx` with an **empty body** from a platform API is nearly always a rejected signature, not a business error and not a network problem. The cheap way to prove it is a controlled experiment against the browser's own request.

1. Capture the real request: open the page with Playwright using the injected Chrome session, listen to responses, and save the full request (URL, all headers) to a file.
2. Replay it unchanged → expect the same status as the browser.
3. Now change **exactly one** variable and replay:
   - browser headers + **your** signature header → if it fails, the signature is the variable
   - **browser** signature header + your other headers → if it succeeds, the signature is the variable
4. Cross-check the two results. If only the signature differs in outcome, the root cause is the signature implementation.

Worked example (XiaoHongShu `edith` comment API, 2026-10-19): browser `x-s` length 416 vs third-party 352, diverging at character 17; the third-party signer's payload was missing a field. `PAYLOAD_LENGTH` tuning could not fix it — the difference was content, not length.

Before blaming the network or the session, rule out: exit IP, TLS/HTTP2 fingerprint (`curl_cffi` impersonation), extra/missing headers the browser sends, token freshness, cookie combination, and query-string normalization (diff the string you sign against the string you send, byte for byte).

## 3. When the third-party signer's algorithm is outdated, do not reverse it

Do not re-implement a platform's signing algorithm. It rotates and you will lose the work. Instead, **let a real browser sign**:

- Inject the user's Chrome cookies into a Playwright context.
- Navigate to the content page so the page's own JavaScript produces the signature.
- Capture the JSON response the page requests, and aggregate it yourself.

Measured cost on this machine: 25–50 s per note (one note was observed at 50.8 s) and ~300 MB of resident Chromium — acceptable for a coverage run, not for high-volume work. Deduplicate by item id, because a frozen cursor replays pages.

This pattern also gave the decisive evidence: the browser's own page-level request returned the same empty body, which proved the missing piece was a platform-side token rather than a client bug.

## 4. YouTube: a PO token is required for subtitle bodies

`yt-dlp --list-subs` succeeding proves captions **exist**; it does not prove the caption body is retrievable.

| Symptom | Cause | Fix |
|---|---|---|
| `Sign in to confirm you're not a bot` | no session | add `--cookies-from-browser chrome` |
| timedtext returns **HTTP 200 with an empty body** (base URL carries `ip=0.0.0.0` and `sparams=ip,...`) | **missing PO token** | run a PO token provider |
| `RequestBlocked: ... blocking requests from your IP` (library route) | IP reputation | switch to the provider route; do not loop retries |

A real browser page without a PO token also gets an empty body, so this is a platform requirement, not a client defect.

Working stack on this machine (`tools/yt/`, all local):

```bash
yt --search "query" -n 5
yt --video VIDEO_ID --subs --out /tmp/ytout/
```

- `tools/bgutil-pot/` — PO token server (bgutil-ytdlp-pot-provider v2.0.2), `node build/main.js`, listens on `127.0.0.1:4416`. The route is **`POST /get_pot`**; a GET returns 404.
- `tools/yt-dlp-venv/` — yt-dlp 2026.08.19 + the provider plugin.
- `tools/yt/yt` — wrapper: probes the port, starts the server if needed, passes Chrome cookies, and on a bot gate **restarts the server to clear its cached token** before retrying.

**Token cache gotcha**: the provider caches tokens in memory. A cached bad token makes every retry fail. Restarting the server between attempts took the observed success rate from 2/3 to 4/4.

**Cookie-read details**: `scripts/chrome-cookies.py` runs the read in a **separate process** with a **40 s hard timeout**; its exit code classifies the failure — `3` = read/decrypt error (the reason is printed on stderr), `4` = no cookies for that domain (the browser is not logged in), `2` = the extractor is missing. Callers surface these separately, so a decryption problem is never reported as "not logged in". The emitted file is a classic **7-field Netscape** cookie file: the magic line `# Netscape HTTP Cookie File` is mandatory (yt-dlp rejects the file without it), HttpOnly cookies use the domain field `#HttpOnly_.example.com` — **without** a leading dot, or the cookie is silently dropped, and emits a Netscape cookie file — the `# Netscape HTTP Cookie File` magic line is mandatory (yt-dlp rejects the file without it) and HttpOnly cookies need the `#HttpOnly_` domain prefix. Reading Chrome's cookie database can also return a **partial** set — one run extracted 30 cookies instead of the usual ~1,500, and the request then failed the bot gate. `scripts/chrome-cookies.py` does the read in a separate process with a timeout, and `scripts/yt` warns when the count is suspiciously low. Treat a low count as a retryable condition, not a credential problem.

`ytsearchN:` is linear with no stable page cursor, and Chinese-language queries returned zero results on this machine — a corpus fact, not a tool failure.

## 5. Bilibili: main-floor pagination needs a patched client

The public `tamnd/bilibili-cli` v0.3.0 has three real defects: the loop terminates on the top-level `cursor.is_end` (which the endpoint sets even when `pagination_reply.is_end` is false); `--page`/`--page-size` are never passed into `CommentOptions`, so the flags are silent no-ops; and the "no new records" guard sits after the emit check, so `--page 2` stops on page 1. Fix by signing with `pagination_str={"offset":...}` and reading `cursor.pagination_reply.next_offset`, and by moving the dedupe/count before the emit check.

Top-level pagination is also **login-gated**: the same build returned 1 top-level comment anonymously and 157 with the Chrome session (488 nested replies, every `reply_count` matched). Treat "anonymous" and "logged in" as different capabilities and record both.

The patched client reads its cookie from a file. `parseCookieFile` accepts the **classic 7-field Netscape format**; a modern 10-field file is parsed as one garbage cookie string.

## 6. Read-only boundaries

Everything in this file is read-only. Browser use is limited to: injecting the user's own session, navigating to public content pages, and capturing responses. Never post, comment, like, follow, or message. Never print or persist cookie values in evidence, and never write platform configuration. Keep generated subtitles, transcripts, and audio in `/tmp` unless the user asks for a saved deliverable.
