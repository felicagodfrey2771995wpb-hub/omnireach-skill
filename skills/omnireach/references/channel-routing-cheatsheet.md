# Channel routing cheatsheet

Pick the route before running anything. "The command exists" is not a route; the route is the command that was **actually verified on this machine**. Base verification: 2026-10-19. Relevant sandbox/host routes rechecked 2026-10-20; see the paired evidence below.

## Fast path first: the exposed `agent-reach` MCP server

The current host exposes an `agent-reach` MCP server with these tools:

| Tool | Covers |
|---|---|
| `agent_reach_search` | **Reddit, Exa, Bilibili only** |
| `agent_reach_probe` | same three |
| `research_start` / `research_step` / `research_record` / `research_check` | the persistent research runner (auto scope, per-channel work items) |

**小红书 and 知乎 are outside `agent_reach_search` / `agent_reach_probe` coverage.** The research runner can queue these channels, but their searches and reads still use the host CLI/browser routes below.

## Route table

| Need | Primary (verified) | Fallback | Sandbox caveat |
|---|---|---|---|
| Reddit search (免凭据，无需登录；`rdt-cli` 已于 2026-11-01 移除) | MCP `agent_reach_search(channels=["reddit"], …)` | **Arctic Shift 归档优先**（`score`/`num_comments`/嵌套评论树/真分页，`source_type: archive`）：查询写 `r/<SUB>` 最快（~3 s），否则网关用查询词反查候选子版（≤4 个）并逐级放宽关键词（~10 s）；**Reddit RSS 仅兜底**（live 全站关键词搜索，扁平无分数，限流 60–90 s/请求，网关 10 分钟缓存）；RSS 命中行自动并入归档元数据 → `reddit-hybrid`（live=true 但 `score_meta=arctic-shift-archive`，约 36h 回填）；`discover: <关键词>` 触发全局子版发现（unscoped 全局流 2 天×6 片点采样 → 发现子版逐个 scoped 深搜，`discovered_via=global-stream`，总请求 ≤8）；再退 Exa `site:reddit.com`（indirect） | probe a **data** endpoint（`.rss` / 归档 API），never the homepage (200 = 8 KB login-wall shell)；RSS 撞 429 不要重试循环；报告里水合分数必须注明来自归档 |
| Broad web / Exa | MCP `agent_reach_search(channels=["exa_search"], …)` | host web search | — |
| Bilibili video search | MCP `agent_reach_search(channels=["bilibili"], …)` (page pagination, one page is not the whole set) | `bili search` | — |
| Bilibili subtitles | `bili-subs --list-subs URL` then `bili-subs -o DIR URL` | `opencli bilibili subtitle BV_ID -f yaml` | **`-o` takes a directory, not a yt-dlp template** — a template creates a literal directory named after it and hides the file |
| Bilibili comments | `scripts/bili-comments comments BV_ID --order time --replies` (Chrome session, main-floor pagination works) | `agent-reach bili-comments BV_ID` (other API route, not like-for-like) | for the credential-free baseline call `tools/bilibili-comments/bin/bili-comments-candidate` directly without `--cookie-file` |
| XiaoHongShu search / body | **Pinned, browser-native primary:** `scripts/xhs-mcp search "q"` / `scripts/xhs-mcp detail --feed-id ID --xsec-token TOKEN [--load-all-comments]` (one `detail` call returns body, author, interaction counts, the first comment page and, for video notes, signed subtitle URLs). The `xhs` CLI is the fallback: `xhs --cookie-source chrome search "q" --json` / `xhs --cookie-source chrome read "NOTE_ID" --json` (bare note id from search; a URL must carry the note-level `xsec_token`, never the author token `note_card.user.xsec_token`) | **OpenCLI forbidden**, including browser/homepage search and failure recovery; no automatic browser/MCP substitution. Degradation is one-way: `xiaohongshu-mcp` → `xhs` CLI → report the blocker. Report blockers; allowed site-indexed discovery is indirect. `scripts/xhs-comments --search` invokes the same `xhs` search, not an independent fallback. On HTTP 461/471 (`verification_required`) stop the chain, complete the check in the browser, then refresh the cache with `xhs login --cookie-source chrome`; `code=-100` means the user must log in again in the browser. The CLI prefers its saved cookie cache and re-reads Chrome only when the cache is older than 7 days, so refresh it explicitly after a browser verification | the browser-native route needs the local deployment at `~/Work/projects/codex/app-data/xiaohongshu-mcp` with a valid `data/cookies.json`; its own session file is refreshed by that deployment's `import-from-chrome.sh` (no QR scan, keeps the fingerprint seed). The CLI fallback needs access to authorized Chrome cookies and write access to `~/.xiaohongshu-cli` (including `search_sessions.json`); sandbox failures may report cache permissions or missing `a1` → compare with the same approved host call before classifying auth/session failure. On a foreign exit the upstream explore-page deadlines are marginal (8s hydration, 30s navigation): use `search`/`detail`/`user-profile`, not `login-status`/`list-feeds` |
| XiaoHongShu comments | **Browser-native primary:** `scripts/xhs-mcp detail --feed-id ID --xsec-token TOKEN --load-all-comments` (free, first page + `hasMore` + `cursor`). **TikHub App V2 only when the browser route is not enough** — second-level replies, pages past the first, or folded-comment coverage: `scripts/xhs-tikhub-comments NOTE_ID_OR_SHARE_URL --max-pages N`; add `--comment-id PARENT_ID` for replies | No OpenCLI fallback. Existing `scripts/xhs-comments` is an explicitly selected, top-level-only local fallback | TikHub API key and eligible free credit by default, and it **spends credit** — an ordinary "show me the comments" read should not use it. A page or budget limit can leave the result partial |
| Zhihu search | **Pinned official OpenAPI:** `zhihu-search` skill / `zhihu-search.py` | **No automatic fallback:** OpenCLI search, OpenCLI browser search and `zhihu-search-browser.js` are forbidden. Missing key/API error/quota/empty results do not unlock them; report the API blocker | this sandbox returned `timeout or network error`; the same host API query returned content, so retry the same API command on the approved host when appropriate. The separate `zhihu-toolkit` 0.3.0 CLI has historical signature failures. OpenAPI returns at most 10/query and has no verified continuation cursor |
 | Zhihu body / comments | `opencli zhihu answer-detail ID -f yaml`, `opencli zhihu answer-comments ID -f yaml` | — | use an answer ID from search (a `zhuanlan.zhihu.com/p/...` article ID is not an answer ID); sandbox daemon startup can fail while the same host body read succeeds. Verify actual `content`; comments are a separate read, and their count includes replies/bots |
| Douyin search + comments | `opencli douyin search "q" -f json` (returns real `desc` copy + aweme_id) then `opencli douyin comments AWEME_ID_OR_VIDEO_URL --pages N|all -f json` (omnireach thin wrapper installed at `~/.opencli/clis/douyin/`, authoritative source `scripts/douyin-comments/`) | `opencli douyin user-videos SEC_UID --with_comments --comment_limit 10` (params confirmed in the package, not live-tested — no sec_uid source in current routes) | comments paginate by cursor: 50/page, `--pages 1` (default) = **first page only ≠ full list**, `--pages all` sweeps to has_more=false (cap 100 pages), dedup by cid; login required — check `opencli douyin whoami`; verified 2026-10-20 (2 pages: 50+48, 0 overlap, 2115 chars). **Reply bodies** are not in that endpoint — start the local DTK-API v4 service (`tools/douyin-dtk-v4`, `uvicorn app.main:app --port 8666`) and call `/api/douyin/web/fetch_video_comment_replies?item_id=…&comment_id=…&cursor=N` (verified 2026-10-20: 20+20 replies, 516 chars, 0 overlap) |
| The 12 registered forum/community channels | six site keys use `scripts/forum-cli/forum_cli.py search <site>` / `post <site> <url>`; four use `discourse-forum`; Reddit and Linux.do use their own rows | discovery/read capabilities vary by site; see [forums.md](forums.md) | **exit 75 alone is ambiguous**: explicit `access-blocked`, a challenge page or structured blocked payload takes priority over its network fallback; expired-session evidence is auth. Preserve stderr/stdout and actual endpoint. Never turn an access refusal into an automatic retry loop or infer CF solely from HTTP 403 |
| YouTube search | `yt-dlp --cookies-from-browser chrome "ytsearchN:query"` | `scripts/yt --search "query" --compact` | the default JSON dump is tens of MB — always use `--compact` |
| YouTube subtitles | `scripts/yt --video ID --print-subs` (stdout, no file left behind) | `yt-dlp --write-auto-subs` | subtitle **bodies** need a PO token; the wrapper starts the local provider server itself and restarts it on a bot gate. `ytsearchN` is linear with no stable page cursor |
| Linux.do | **MCP `linuxdo`** `search(query,page,pages)` / `get_topic(topic_id,posts,start)` / `whoami` (registered `mrsxs/linuxdo-mcp`, browser-authorized session) | `scripts/linuxdo-read search QUERY` / `topic ID` — same MCP server over stdio, for hosts without MCP tools | `next_page` / `terminal_page` / `next_start` are **wrapper-normalized fields**, not raw MCP output. **The MCP route is the default and does not need the user to name it** — do not substitute anonymous Discourse/HTTP. The legacy `linuxdo-browser` CLI shares the session but was observed failing with a Cloudflare interception while the MCP route read the same topic in the same minute, so it is a comparison path, not the default. **The site rate-limits by request frequency**: spaced reads pass, bursts get intercepted. `scripts/linuxdo-read` throttles by default (`--min-interval 3`) and retries once after a 20 s pause (burst test 1/6 → 6/6); agents calling the MCP tools directly should pace themselves and never loop |
| WeChat articles | `wechat-article-for-ai` (Exa, limited to `mp.weixin.qq.com`) | `wechat-search` (Sogou; index of public accounts only) | search cards are discovery evidence, not body reads |
| Weibo / Twitter / Facebook / Instagram / LinkedIn / Xueqiu / Xiaoyuzhou | `opencli <platform> search` / `read` (needs a logged-in Chrome session) | — | not content-verified on this machine — treat as unproven and report the failure honestly |
| RSS | any feed reader route | — | an RSS item is an index entry, not a body read |

## The two broadest request shapes

These two shapes are the most common asks. The runner now resolves both explicitly (`research_start` with `scope=auto`):

| Ask | Scope | Channels |
|---|---|---|
| "check every social media and forum" / "所有社媒、论坛都查一遍" | `broad` | **28** — the 18 social channels (`web` `official_docs` `github` `bilibili` `xiaohongshu` `zhihu` `weibo` `twitter_x` `reddit` `youtube` `v2ex` `wechat` `facebook` `instagram` `linkedin` `xueqiu` `xiaoyuzhou` `rss`) plus the 12 forum channels (`reddit` `v2ex` `linux_do` `nodeseek` `ubuntu_forum_cn` `archlinuxcn` `nixos_discourse` `ubuntu_discourse` `itsfoss` `linux_org` `osdev` `enshan`) |
| "only Chinese forums / Chinese social media" / "只查中文论坛或中文社媒" | `focused` | **12** — `zhihu` `xiaohongshu` `weibo` `wechat` `v2ex` `xueqiu` `bilibili` + `linux_do` `nodeseek` `ubuntu_forum_cn` `enshan` `archlinuxcn` |

Other shapes for reference: "all forums" → `forums` (12); a single named site → `focused` with that one channel; anything else → `broad` (18).

**Depth still follows relevance, not breadth.** A broad request keeps every channel in the queue, but read the body only for the results that survived screening. A 28-channel run is 56 work items — do not deep-read all of them.

## Test all forum channels in one command

```bash
scripts/forum-probe                 # 12 站逐站：搜索 → 读第一帖正文
scripts/forum-probe --only v2ex,linuxorg
scripts/forum-probe --json /tmp/probe.json
```

The default console output prints status, count and a short detail, and **now also prints the executed command for every non-verified row**; pass `--json /tmp/probe.json` to record every `search_cmd` and `body_cmd`.

Classification is decided by the **payload, never by the exit code alone**: `forum-cli` and `discourse-forum` both use exit 75 for "host retry required" (a sandbox DNS/connection failure) *and* for a real Cloudflare/WAF refusal. The probe therefore separates them —
- `blocked` — explicit Cloudflare/WAF/access-denial evidence (`error.code=blocked`, a challenge page, `CF-MITIGATED`)
- `error` with `failure_class=network` — DNS, connection, or timeout failure → **rerun on the host**; it is not evidence that the route is broken
- `empty` — the query ran and matched nothing

## Sandbox rules that apply to every row

1. A sandbox DNS failure, timeout, or permission error is **not** evidence that a site or a route is broken. Repeat the same read-only call on the host network and report both results.
2. `exit 75` from `forum-cli` means *blocked*, not *empty*. Preserve `ok:false`, `error.code=blocked` and its reason. Network/other exceptions can exit `1`, so do not assume every environment failure returns `75`.
3. An empty result and a blocked result are different states. Record which one happened.
4. Search snippets are discovery evidence. Read the body before claiming content.

## When the route does not exist

Prefer a **direct platform route** over an indexed web search, and label indexed results `indirect`. If the native route fails, record the original error first, then fall back — do not silently swap routes.

For the six `forum-cli` site keys, inspect the supported read commands below; these are not a guarantee of native full-text search on every site:

```
scripts/forum-cli/forum_cli.py sites
scripts/forum-cli/forum_cli.py search <site> <query> [--page N]
scripts/forum-cli/forum_cli.py post <site> <url> [--page N]
```

Sites: `v2ex` `nodeseek` `linuxorg` `osdev` `ubuntucn` `enshan`. The four Discourse communities (Arch Linux 中文, NixOS, Ubuntu Discourse, It's FOSS) go through `discourse-forum`; Reddit and Linux.do bring the registered total to twelve. V2EX discovery uses the third-party SoV2EX first-post index; NodeSeek search filters list titles; site-specific permission/challenge limits remain in effect.

`forum-probe` requests `--verbose` metadata for forum-cli and preserves **separate** `search_source/search_meta` and `body_source/body_meta`. Its `verified` means a discovery-plus-body **sample** worked, not native full-text search or complete enumeration. Ubuntu CN is homepage lastpost filtering (`items_scanned` is sample size), not a working `search.php`; V2EX index/official API bodies are first posts only, not reply-floor bodies. `search_complete` is unknown unless proven, and false for homepage filtering. Sources reported as `unreported` must not be guessed. Non-verified records require class + action; full failures remain in `*_diagnostic` while terminal `detail` is a shortened preview. A malformed channel response becomes error/unknown and does not prevent the other channels or final JSON from being returned.


## Broad research and current `auto` scope limits

Use `research_start(scope="auto")` → `research_step` → execute the indicated host-native search/read → `research_record` → `research_check`. The runner coordinates evidence; it does not expand the three-channel search MCP into a universal executor.

Current runtime verification (2026-10-20): `auto` recognizes **registered forum aliases**, not arbitrary platform names. `只查 Linux.do` resolves to `focused`; `搜所有论坛，尤其关注 Linux.do` resolves to all twelve `forums`; ordinary research resolves to `broad`. `只查小红书` and `只查知乎` currently also resolve to `broad`. For one of these social platforms, explicitly pass `scope="focused", channels=["xiaohongshu"]` or `["zhihu"]`, or use its narrow direct route. A `route` response with `scope="broad", channels=[]` means use the broad default list; it does not mean zero channels.

## Paired sandbox / host verification — 2026-10-20

These are bounded route checks, not exhaustive platform coverage. The approved host calls used the same executable, arguments and existing user-controlled session as the sandbox calls. Local caches may be refreshed; no installation or login flow was run. Evidence is stored with tokens redacted under `/Users/mac/Work/projects/codex/outputs/omnireach-host-check-20261020/`.

| Operation | Sandbox | Host |
|---|---|---|
| `xhs --cookie-source chrome search "露营" --json` | exit 1, missing `a1` in Chrome view; earlier sandbox attempt hit `search_sessions.json` write permission | exit 0, 22 search items (20 note cards), all 22 with `xsec_token`, `has_more=true` |
| `scripts/xhs-comments --search "露营" -n 1 --max-pages 3 --json` | exit 2, no usable search URL reached the reader | exit 0, 10 unique nonempty top-level comments / 2 captured pages / `has_more=false` on the selected note; no child-reply bodies |
| official `zhihu-search.py '{"query":"程序员 焦虑","count":5}'` | exit 1, `HTTP request failed (timeout or network error)` | exit 0, 5 items with nonempty summaries; summaries remain distinct from answer-body reads |
| `opencli zhihu answer-detail 2035695578139579577 -f yaml` | exit 69, `BROWSER_CONNECT`, daemon startup failed | exit 0, matching answer ID and nonempty `content` (full default `max-content=0`) |

The original four caveats were also checked: `forum-cli search osdev bootloader --page 1` returned host exit 75 / `ok:false` / Cloudflare HTTP 403; `bili-subs -o '.../%(id)s.%(ext)s' URL` created that literal **directory** and wrote a 12,551-byte subtitle TXT inside it. Thus `bili-subs -o` takes a directory; it does not accept a yt-dlp filename template. XHS cache-write requirements were confirmed in the installed implementation; the fresh host search verified cookie/session access. Exact commands, timestamps, exits and content outputs are in the paired JSON evidence files.
