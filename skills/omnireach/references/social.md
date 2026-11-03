# Social and community channels

Use read-only commands for research. Inspect `agent-reach doctor --json` and the channel's dedicated CLI help before choosing a backend; inspect `opencli list` / `opencli PLATFORM --help` only for channels whose route allows OpenCLI. XiaoHongShu explicitly forbids it. An installed adapter or browser bridge does not prove a platform session or query is usable. Keep direct reads distinct from indirect site-indexed web results. Do not sign in or import cookies without an explicit user request.

For a sandbox DNS/connection failure, do not mark the whole channel unavailable from that result alone. When an approved host-network execution path exists, repeat the same read-only query there; record environment, time, backend, status, and item count for both calls. Pass `--execution-context sandbox|host` to explicit Doctor probes only when known. Use the host's permission flow as needed; never self-elevate or change DNS/proxy policy. If the host succeeds, continue direct platform search and report “sandbox failed, host succeeded.”

## XiaoHongShu / 小红书

**Pinned route: `xhs-cli + xhs-comments`. 搜索与正文强制用专用 `xhs` CLI，评论用 `scripts/xhs-comments`。禁止小红书的 OpenCLI 适配器与 OpenCLI browser，失败也不能回退到它们。** This overrides generic discovery/fallback advice and any OpenCLI snapshot entry. The older [browser-search note](xiaohongshu-browser-search.md) is retired and is not an executable route.

```bash
xhs --cookie-source chrome search "query" --json
xhs --cookie-source chrome read "NOTE_ID" --json   # 首选：裸笔记 ID，CLI 用自己的令牌缓存
xhs --cookie-source chrome read "NOTE_URL?xsec_token=..&xsec_source=pc_search" --json   # 备选
```

Confirm `xhs` exists and reuse the user's already-authorized Chrome session via `--cookie-source chrome`; do not script login or import a new account. **Token rule (fixed 2026-10-21):** pass the **bare note id** from the search result so the CLI reuses its own cached note token and `xsec_source`; if you must build a URL, use the **note's** `xsec_token` (top-level `item.xsec_token`). `note_card.user.xsec_token` is the **author** token — reading a note with it fails with `empty noteDetailMap`. A missing CLI, empty result, timeout, cache permission error, or session/signature failure does not authorize another browser/MCP route. Follow the same-route host retry rule below; if still blocked, report the precise cause. If indirect discovery is within scope, `site:xiaohongshu.com` web search must be labeled indirect. Reduce request rate if verification appears.

See [channel-routing-cheatsheet.md](channel-routing-cheatsheet.md) for the per-route command table and the sandbox caveats (the `xhs` CLI needs write access to `~/.xiaohongshu-cli`; the Zhihu OpenAPI times out in a sandbox — rerun both on the host).

### Search and body via the CLI (verified 2026-10-19)

**Cookie cache behavior (corrected 2026-10-21 from the `xhs` 0.6.4 source):** the CLI prefers its **saved** cookie cache (`~/.xiaohongshu-cli/cookies.json`) and only re-reads the browser when that cache is older than **7 days** (`COOKIE_TTL_DAYS`) or when a session-expired error triggers one forced refresh. `--cookie-source chrome` therefore does **not** re-read Chrome on every call, and a stale cache can keep a dead session alive. Refresh it on purpose with `xhs login --cookie-source chrome` — it extracts the already-logged-in browser session, requires no QR scan and no new login, and reports `authenticated` / `guest`. The saved cache is the unit of freshness: after the user completes a browser verification, refresh the cache instead of assuming the next call picks it up. Search returns real notes with `xsec_token` and `has_more`; two consecutive pages returned 22 notes each with zero overlap. Use `--page N` for search pagination; body reads use the bare note id (or the note-level token URL).

```bash
xhs --cookie-source chrome search "query" --json
```

### Classify the failure before retrying (verified 2026-10-21, offline mock test of `xhs` 0.6.4)

| Symptom | Structured code | Meaning | Action |
|---|---|---|---|
| HTTP 461 / 471 | `verification_required` | the platform is asking for human verification | complete it in the browser, then `xhs login --cookie-source chrome` to refresh the cache, then retry **slowly** — repeated retries escalate the block instead of clearing it |
| HTTP 200 + `code=-100` | `not_authenticated` | the server-side session is dead | the user logs in again in the browser, then `xhs login --cookie-source chrome` |
| `code=300015` | `signature_error` | the request signature was rejected | report it; do not loop the same request shape |
| `code=300012` | `ip_blocked` | the exit IP is rate-limited | change network (hotspot / VPN), then retry |
| `empty noteDetailMap` / `api_error` | `api_error` | **not** proof the note is missing | the CLI falls back to an HTML read and can mask an earlier verification failure; re-run the classification before reporting the note as absent |

`not_authenticated` is one code for **two different causes** — read the message to tell them apart: `NoCookieError` means there is no usable `a1` locally (cache missing, or browser extraction failed), while `SessionExpiredError` means the local cookie exists but the server-side session is void. `xhs status` re-extracts from the browser once before giving up, so it failing already implies one refresh attempt failed. On success, `xhs status --json` always reports `data.authenticated: true`; there is no `authenticated: false` state. The field that separates a real user from a guest session is `data.user.guest` — `guest: true` means the cookies are accepted but the session is not a logged-in user, and the CLI treats it as an invalid login.

**What can void a web session (checked 2026-10-21):** the platform allows the phone app and one PC browser session at the same time, but it **kicks concurrent web sessions** — logging into the web version in a second browser, profile, or incognito window can evict the first one and surface as `not_authenticated`. Other known causes: a re-login on the main device, an IP change, and risk-control revocation. So when a session dies, check whether another browser signed into xiaohongshu.com, whether the phone re-logged in, and whether the exit IP changed — before telling the user to re-authenticate. The CLI itself has no device-consistency logic; this is platform behavior.

**Egress IP is a risk factor worth checking (checked 2026-10-21 on this host):** the host's traffic runs through a system-wide proxy plus a TUN interface, so the web session reached Xiaohongshu from a **US datacenter** address while the phone was on a domestic network — an "overseas data-centre IP" profile that the platform treats as higher risk, and a plausible reason verification triggers early. Two cautions: the phone and the PC being on different IPs is **not itself a problem** (the app and the web are separate session systems, and a phone that moves between cellular and Wi-Fi changes IP constantly), and this host's own 2026-10-19 record shows a failure that **reproduced on a domestic exit**, so a DIRECT rule is risk reduction, not a cure. Never change the user's proxy configuration unilaterally: propose a `xiaohongshu.com` → DIRECT rule, let the user apply it, then verify the egress IP and re-run the route. Also advise fixing one stable exit path rather than switching nodes, since IP drift itself voids the session.

If the API answers `-100` / `SessionExpiredError` while the cookies are present and unexpired, the **server-side session is dead** — the user must log in again in the browser. For **this XiaoHongShu route** that is the only case needing a user action, and there is no separate login flow to script. The Zhihu CLI profile has its own expiry, repaired by `zhihu auth import -b chrome` — also without a QR scan. See [session-model.md](session-model.md) for the full expiry semantics and the local side effects of the read-only helpers.

**Pacing (measured 2026-10-21):** the CLI already inserts a ~1–1.5 s Gaussian jitter between requests and doubles its own delay after a verification event, but that does not clear a verification block. One `search` plus one `read` about 8 s apart passed repeatedly. When verification appears, stop that request chain instead of re-running it.

**Diagnostic ordering (observed 2026-10-21):** a `search` that still succeeds while a `read` is challenged points at the **read request shape**, not at the session — the first verification of that session appeared on a read that carried the author token, right after a search had returned 22 notes. A challenged read can therefore escalate into a challenged search within a few calls, so a later `verification_required` on search does not prove search was the trigger. When a session-level problem is suspected, re-run one `search` before blaming the session: a clean search plus a challenged read means token/`xsec_source` correctness; a challenged search means the risk state itself.

### Comments: the third-party signer is rejected, use the browser's own signer

`GET /api/sns/web/v2/comment/page` returns **HTTP 406 with an empty body** for every request from the `xhs` CLI, on both a foreign and a domestic exit, with a full Chrome session, a fresh token, and with `curl_cffi` TLS impersonation. The response carries `Access-Control-Allow-Headers: f,x-s,x-sign,x-t` and a `X-Kong-Sign: 1` header: the gateway is rejecting the **signature**. The upstream `xhshow` signer produces a payload the site no longer accepts, and it cannot be tuned into working.

A browser-native signer is the working route. The dedicated `scripts/xhs-comments` helper injects the Chrome session, lets the page sign, and aggregates the responses it captures. Its internal Playwright signer does **not** use OpenCLI and is the approved comment route; it does not authorize general browser search or OpenCLI fallback:

```bash
<skill-root>/scripts/xhs-comments --search "query" -n 3 --max-pages 6
<skill-root>/scripts/xhs-comments --url "NOTE_URL?xsec_token=..&xsec_source=pc_search" --max-pages 10 --json
```

Verified: 6 pages / 59 comments with `has_more=false` (read to the end), 10 pages / 100 comments on a high-engagement note, no duplicate comment ids, and every comment carried user, body, like count, and IP location. Cost is **25–50 s per note** (a single note was observed at 50.8 s) and ~300 MB of resident Chromium. See [session-model.md](session-model.md) for the diagnosis method.

`xhs-comments` returns **top-level comments only** — child-reply bodies are not fetched, so a thread's replies are out of scope for this route. `--max-pages` is a ceiling, not a promise: pages hold roughly ten comments each, so `--max-pages 10` can still leave `has_more=true` — raise it until `has_more=false` to read a thread out.

Cross-page dedup, reproducible: run with `--json` and compare comment ids across pages — the ids must be unique overall, because a frozen cursor replays pages.
```bash
cd <skill-root>
scripts/xhs-comments --search "关键词" -n 1 --max-pages 3 --json \
  | python3 -c "import sys,json; d=json.load(sys.stdin); ids=[c['id'] for c in d['comments']]; print(len(ids), len(set(ids)))"
```
The two numbers must be equal (observed: 28 28). Use an absolute path to `scripts/xhs-comments` if you are not in the skill root — the example above assumes it.

## X / Twitter

`twitter-cli` commands require credentials explicitly present in the child process environment. `agent-reach configure twitter-cookies` only stores values for configuration checks; it does not export them into the current shell or prove search works. Never print credential values.

```bash
twitter search "query" -n 10
twitter tweet URL_OR_ID
twitter thread URL_OR_ID
twitter article URL_OR_ID
twitter user-posts username -n 20
```

The search endpoint can change or return 404. Retry once; when maintenance is requested, upgrade an already-installed CLI; try a verified OpenCLI adapter; then use an indirect Exa query limited to `site:x.com OR site:twitter.com`. Label fallback results `indirect`; do not treat them as native search. If credentials are not available, use the indirect route rather than attempting login.

## Bilibili / B站

Use `bili` for public search, hot/rank lists, video metadata, and audio. Search is the primary route; OpenCLI is the verified browser-backed fallback. A successful search requires structured `ok` plus returned content; a zero command exit alone is insufficient. Doctor distinguishes structured DNS, timeout, connection, authentication, 403/412, 429, service, invalid-output, and empty-result states, preserving sanitized diagnostics and HTTP status where available. `yt-dlp` supports `bilisearchN:QUERY` but this machine returned HTTP 412 on 2026-10-14, so treat it as a conditional fallback only after environment changes. On 412, stop retrying and switch to OpenCLI; if that route fails, use Exa `site:bilibili.com/video` as indirect web discovery and label it separately. `bili video` may independently receive HTTP 412; do not infer that all Bilibili endpoints are blocked.

```bash
bili search "query" --type video --page 1 -n 42 --page-info --json
bili video BV_ID
bili hot -n 20
bili rank -n 20
bili audio BV_ID
OPENCLI_BROWSER_COMMAND_TIMEOUT=60 opencli bilibili search "query" --type video --page 1 --limit 20 -f json
opencli bilibili subtitle BV_ID -f yaml
```

`--page-info` preserves the original normalized `data` list and adds the full raw `upstream_items`, page metadata, per-page duplicate BV count, invalid/no-BV card summaries, and client truncation. `platform_total` is the API-reported searchable window, not a site-wide count. Request each page explicitly, deduplicate by BV ID across pages, and stop only at `has_next_page=false`, a documented platform cap, the user's requested limit, or a recorded access failure. Keep search, detail, subtitle, and comment statuses separate. See [video.md](video.md) for subtitles, audio transcription, comments, and zero-comment handling.

### Subtitles and comments (verified 2026-10-19)

Subtitle tracks are reachable through `bili-subs` (a `bili2txt` wrapper around yt-dlp with `--cookies-from-browser chrome`), which returned an `ai-zh/srt` track and a real transcript file (12,551 B / 4,908 characters / 367 cues). Note that `bili video -s` returning HTTP 412 is a **view-API** risk control and does not mean the subtitle track is unavailable — the two endpoints fail independently.

```bash
bili-subs --list-subs "https://www.bilibili.com/video/BV1csJC6yEQx"
bili-subs -o /tmp/out "https://www.bilibili.com/video/BV1csJC6yEQx"
```

`bili-subs -o` takes a **directory**, not a yt-dlp output template — the file is written inside it, named after the video title. Passing `"%(id)s.%(ext)s"` creates a literal directory with that name and hides the file inside, which looks like "listed the track but exported nothing". Primary route: `bili-subs` with the Chrome cookie. Fallback when the wrapper lists tracks but writes nothing: `opencli bilibili subtitle BV_ID -f yaml`, which returns the cues directly; record which route produced the result. Note the wrapper's own yt-dlp call uses `--cookies-from-browser chrome` in-process, so it can inherit a stuck cookie read — the bundled `scripts/yt` avoids that by reading the cookies through the isolated extractor.

Comments need the patched Go client plus a logged-in Chrome session. `scripts/bili-comments` reads the Chrome cookies, writes a 600-permission classic 7-field Netscape temp file, runs the candidate, and deletes the file afterwards:

```bash
<skill-root>/scripts/bili-comments comments BV1csJC6yEQx --order time --replies -o Json -q --no-cache
```

Verified on the same video: with the Chrome session 157 unique top-level comments and 488 nested replies, against **4 top-level and 15 nested** from the credential-free candidate-binary route above; `--page 1/2/3` each returning 20 distinct records with page 2 and page 3 sharing none. The anonymous figure varies between runs (1–4 top-level) — the point is the order of magnitude, and that the anonymous route really omits credentials. Main-floor pagination is **login-gated**; report anonymous and logged-in results separately. `scripts/bili-comments` **always reads the Chrome session** — for the anonymous baseline call the patched candidate binary directly, without `--cookie-file` — note the exact file name, `bili-comments-candidate` (there is no `bin/bili-comments`; that path is the wrapper, and the wrapper always reads the Chrome session):

```bash
/Users/mac/Work/projects/codex/work/agent-reach-coverage/candidate-20261018/tools/bilibili-comments/bin/bili-comments-candidate comments BV1csJC6yEQx --order time --replies -o Json -q --no-cache
```

That path is the only one that truly omits credentials; `agent-reach bili-comments` is a different API route and is not a like-for-like comparison. The Go side parses only the **classic 7-field Netscape** format — a modern 10-field file is read as one garbage cookie string. See [video.md](video.md) and [session-model.md](session-model.md).

## Douyin / 抖音

OpenCLI exposes read commands for search, hashtags, user videos, and public profile metrics; login may be required. Inspect exact options first:

```bash
opencli douyin search "query" -f yaml
opencli douyin comments AWEME_ID_OR_VIDEO_URL -f yaml
opencli douyin hashtag --help -f yaml
opencli douyin user-videos SEC_UID -f yaml
opencli douyin stats AWEME_ID -f yaml
```

Status (verified 2026-10-20, macOS host): `search` returns real video `desc` copy with aweme_id; `comments` is the omnireach thin wrapper (`scripts/douyin-comments/` in this skill, installed to `~/.opencli/clis/douyin/` — opencli's sanctioned user-adapter dir, survives package updates; uninstall with `rm -rf ~/.opencli/clis/douyin/`). It reads `aweme/v1/web/comment/list` with cursor pagination: 50 per page, `--pages 1` (default) returns the **first page only — not the full list**; `--pages N` fetches N pages and `--pages all` sweeps until `has_more=false` (safety cap 100 pages), deduplicating by `cid`. Fields: `text` / `digg_count` / `nickname` / `reply_comment_total` — top-level comments only; reply **bodies** are not exposed by this endpoint (only their counts). `user-videos <sec_uid> --with_comments` has its params confirmed in the package but has not been live-tested (no sec_uid source in current routes).

For a user-provided share URL, an installed Douyin MCP may resolve video metadata, download links, or spoken text. Confirm its registration with `mcporter list` and inspect the tool schema before calling it. Posting, drafts, deletion, login, and account changes are write operations and require a distinct explicit request.

## Weibo / 微博

Prefer a discovered OpenCLI read adapter when available. It can search, read posts and comments, browse hot lists, feeds, and user posts; login/session may be required.

```bash
opencli weibo search "query" -f yaml
opencli weibo post POST_ID -f yaml
opencli weibo comments POST_ID -f yaml
opencli weibo hot -f yaml
opencli weibo user-posts USER_ID -f yaml
```

If the adapter is unavailable or blocked, use focused `site:weibo.com` web search as indirect discovery and mark it as such. Do not sign in or publish.

## Zhihu / 知乎

**Pinned keyword search: the shared `zhihu-search` official OpenAPI only. 禁止 `opencli zhihu search`、OpenCLI browser 搜索及 `zhihu-search-browser.js` 自动替代。** It reads `ZHIHU_ACCESS_KEY` from the skill's private `.env`; never print, copy into task evidence, or expose the credential. The API returns at most 10 items per query and exposes no verified continuation cursor, so use complementary/split queries and do not claim pagination exhaustion. Missing credentials, empty results, API/quota errors, timeouts, and sandbox failures do not authorize fallback. Record the exact error; when appropriate rerun the same API command on the approved host, then report blockers if it still fails. Do not automatically substitute indexed-web search. Announce `知乎搜索：官方 OpenAPI（zhihu-search）`.

```bash
python3 /Users/mac/LocalSkills/统一技能库/sources/skill-manager/zhihu-search-2/scripts/zhihu-search.py '{"query":"query","count":10}'
opencli zhihu hot -f yaml
opencli zhihu question QUESTION_ID -f yaml
opencli zhihu answer-detail ANSWER_ID -f yaml
opencli zhihu answer-comments ANSWER_ID -f yaml
```

`question`, `answer-detail`, and `answer-comments` are separate read routes after API discovery; they do not authorize OpenCLI keyword search. `hot` is a hot-list read, not a substitute for the requested API query. Some content may require a session. Do not invoke `login`, `comment`, `like`, `favorite`, or `follow` in a read task.

Latest API probe (2026-10-21, query `钢琴练习`, count 1): **`code=0`, `message="success"`, 1 real result** using the private `.env` credential. Earlier the inherited process credential differed from the private file and returned `30002 / quota exceeded` with process exit 0. Removing the inherited credential made the same query succeed; after fixing private-file credential precedence, the normal default command also succeeded with the inherited environment still present. No server-side key was generated/revoked and no quota was reset. Local nonempty `.env` credentials now take precedence; environment-only usage remains when the file has no credential. Always check API business code/message as well as process status; an old credential's quota failure is not proof the configured credential is exhausted. Never switch search backends or spend automatically.

### Session import and the signature ceiling (verified 2026-10-19)

The official OpenAPI is the primary search route (the `zhihu-search` skill). It answers from the host network; a sandbox request times out, which is a sandbox limit rather than a broken route.

The isolated `zhihu-toolkit` 0.3.0 CLI has no anonymous path. A persistent session can be established **without a QR scan** by importing the user's Chrome session, and it is stored in a CLI profile that survives restarts:

```bash
/Users/mac/Work/projects/codex/work/agent-reach-coverage/candidate-20261018/tools/zhihu-cli-venv/bin/zhihu auth import -b chrome
/Users/mac/Work/projects/codex/work/agent-reach-coverage/candidate-20261018/tools/zhihu-cli-venv/bin/zhihu auth status
```

The import succeeded (22 cookies, identity and UID confirmed), and `auth status` then reported the profile as ready. The `auth login` QR flow is **not** usable on a datacenter exit: it renders a QR and then immediately demands "network environment verification" and blocks waiting for Enter.

Even with a valid session, the CLI's **read** routes stay blocked: `api/v4/search_v3` and `api/v4/members/{token}/answers` both return **HTTP 403 with an empty body** on a foreign and on a domestic exit, while `api/v4/me` succeeds — so the cookie chain is healthy and the `x-zse-96` signature is what the WAF rejects. Keep the official API route as the primary path; treat the CLI as a session-holding backup and do not spend effort on the signature.

## V2EX

Public JSON API supports hot topics, node topics, topic details/replies, and user profiles without a login. It does not provide general full-text search, so use relevant nodes or a clearly marked indirect web query.

```bash
curl -s "https://www.v2ex.com/api/topics/hot.json" -H "User-Agent: agent-reach/1.0"
curl -s "https://www.v2ex.com/api/topics/show.json?node_name=python&page=1" -H "User-Agent: agent-reach/1.0"
curl -s "https://www.v2ex.com/api/topics/show.json?id=TOPIC_ID" -H "User-Agent: agent-reach/1.0"
curl -s "https://www.v2ex.com/api/replies/show.json?topic_id=TOPIC_ID&page=1" -H "User-Agent: agent-reach/1.0"
```

Check response paging fields and fetch all pages required by the research protocol. A hot-list response is discovery, not topic search coverage.

## Reddit

Doctor's backend hint plus an actual read determine which backend is usable. **Use the Agent Reach gateway (`agent_reach_search(channels=["reddit"], …)` / the `agent-reach` CLI) as the entry point.** Since 2026-11-01 the channel needs **no credential and no login**: the credentialed `rdt-cli` route was removed because Reddit's JSON API answers 403 to datacenter / VPN egress IPs, so it could only ever work from an unblocked IP — and its write capabilities are out of scope for a read-only skill. The gateway now runs two credential-free routes, both immune to that block:

- **Arctic Shift archive** (`backend=arctic-shift-archive`, `source_type=archive`) — the **default**, even for an unscoped query: the gateway resolves candidate subreddits from the query words (up to 4), tries them in order and relaxes the keyword match progressively, so the archive usually covers the query on its own. Structured results: `score`, `num_comments`, real pagination, nested comment trees.
- **Reddit RSS** (`backend=reddit-rss`, `source_type=direct`, `pagination.live=true`) — **last resort only**, used when the archive finds neither a usable scope nor a hit. Live and site-wide, but flat and strictly rate-limited; the gateway caches identical queries for 10 minutes so a repeat does not spend another request.
- **RSS hydration → reddit-hybrid (new 2026-11-02)** — RSS rows are batch-enriched with Arctic Shift archive metadata via `GET /api/posts/ids?ids=<bare_ids>` (batch cap 500, gateway uses 100/batch): `score`, `num_comments`, `created_utc`, `permalink`. A hydrated row is `source_type=reddit-hybrid`: `live=true` (content is live RSS) with `score_meta=arctic-shift-archive` (metadata from the archive, refreshed ~36h after posting — new posts may show 0/1). Never report hydrated scores as live Reddit scores. Hydration failure degrades silently to plain RSS rows; cached rows hydrate too.
- **Global subreddit discovery (opt-in, `discover: <query>`)** — samples the archive's unscoped global stream (`GET /api/posts/search?after=..&before=..&limit=100`, real global posts across all subreddits; ~1.4M posts/day so 100 rows is a point sample) over 2-day × 6 recent slices, filters locally for the query tokens, ranks subreddits by mentions, then runs the scoped archive search on the top candidates (≤4, total ≤8 archive requests). Deep-search rows carry `discovered_via=global-stream` and are archive data. Rare topics may discover nothing → the gateway degrades to the normal archive path.

Do not bypass the gateway and re-implement the degradation yourself. If sandbox DNS/connection fails, use the documented host-network recheck route before declaring Reddit unavailable. Do not log in as part of research.

A comment count is **not** a count of independent human opinions: replies from the author and from automated accounts appear in the same list, so report "13 comments including the author's replies" rather than "13 people said". On the Zhihu comment route the pagination can also fail mid-run with `malformed next URL`; that is a known limitation of that backend, not an empty thread.


### The two active Reddit routes (2026-11-01, live-verified)

Reddit's JSON API answers **403 to datacenter / VPN egress IPs** — `search.json`, `oauth.reddit.com` and `old.reddit.com` alike — and self-service API registration is closed (Responsible Builder Policy). This is global policy, not a local fault: it also hits residential IPs and commercial residential-proxy scrapers. Two credential-free read routes survive it, and the gateway picks between them automatically.

**Arctic Shift community archive** (built into `agent-reach`, no credentials, no install):

```bash
# posts — score, num_comments, permalink included
curl "https://arctic-shift.photon-reddit.com/api/posts/search?subreddit=iOS27&after=2026-10-01&before=2026-11-02&limit=100&sort=desc"
# nested comment tree — same shape as the official API
curl "https://arctic-shift.photon-reddit.com/api/comments/tree?link_id=t3_1x1z85s&limit=9999"
```

Scope limits, all measured live:

- keyword filters (`title`, `selftext`, `query`) are only accepted together with `subreddit` or `author`, and the archive **times out with HTTP 422 on very active subreddits** — `r/iOS27` with `title=27.2` 422s, while the same subreddit over a plain date window returns 200. The built-in backend therefore fetches subreddit + window rows and filters keywords locally.
- no global keyword search exists: `query` without `subreddit`/`author` is rejected and `subreddit=all` returns no rows.
- **exception — unscoped global stream (verified 2026-11-02)**: `GET /api/posts/search?after=<DATE>&before=<DATE>&limit=100&sort=desc` WITHOUT subreddit/author/title returns real global posts across all subreddits (`limit` 1–100 or `"auto"`; `sort=asc|desc`). The archive records ~1.4M posts/day, so each 100-row response is a point sample — global scanning must use multiple short windows. This is what powers the gateway's opt-in `discover:` mode. `GET /api/posts/ids?ids=<id,...>` (bare base36 or `t3_`-prefixed, cap 500) returns posts keyed by bare id — this powers RSS hydration. Scores/num_comments are refreshed ~36h after posting.
- it is **archived data**, not live Reddit: newest posts lag slightly, deleted posts may be absent, and nothing can be posted, voted or commented on. Report it as "来自社区归档（Arctic Shift）", never as "直接读取 Reddit".

**Reddit RSS** (live Reddit, no scores, flat comments, strict rate limit — measured 60–90 s between requests, bursts return 429):

```bash
# site-wide keyword search (the only route that can do this)
curl "https://www.reddit.com/search.rss?q=iOS+27.2+battery&sort=relevance&t=year&limit=25"
# scoped search
curl "https://www.reddit.com/r/iOS27/search.rss?q=27.2&restrict_sr=1&sort=new&limit=25"
# post comments (flat, no scores)
curl "https://www.reddit.com/r/iOS27/comments/1xl5bms/.rss"
```

Search results also list matching **subreddits** (entries whose link is `/r/<name>/` with no `/comments/`); those are not posts and the built-in reader skips them.

Availability checks must probe a **data endpoint** (`.rss`, archive API), never the homepage: from a datacenter IP `https://www.reddit.com/` returns 200 with an 8 KB login-wall shell page, which is a false positive.

## Facebook

OpenCLI can search visible users/pages/posts, inspect profiles, feed, and groups using an existing Chrome session:

```bash
opencli facebook search "query" -f yaml
opencli facebook profile USERNAME -f yaml
opencli facebook feed --limit 20 -f yaml
opencli facebook groups --limit 20 -f yaml
```

Groups visibility is limited to groups available to the current account; do not imply arbitrary group or comment access. On a login wall, record `access-blocked` and continue independent channels. Do not automatically sign in.

## Instagram

OpenCLI reuses an existing Instagram browser session. Search is for users, not global post keywords. First identify an account, then read its profile or recent posts:

```bash
opencli instagram search "query" -f yaml
opencli instagram profile USERNAME -f yaml
opencli instagram user USERNAME --limit 20 -f yaml
opencli instagram explore --limit 20 -f yaml
```

If the session is missing or returns a login wall/429, record the block. Use indirect site-indexed search when useful, but do not describe it as Instagram-native results.

## General constraints

- Use output format flags (`-f yaml` or `--json`) supported by the adapter; inspect `--help` instead of assuming options.
- Distinguish relevant content from an empty response, login prompt, captcha, network error, or local sandbox/path error.
- Open relevant result bodies and recent user feedback. Search cards alone do not meet the broad-research reading requirement.
- Never use login, publish, post, comment, delete, like, follow, favorite, draft, or update commands unless the user separately asks for that exact action.
