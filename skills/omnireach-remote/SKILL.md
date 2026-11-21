---
name: omnireach-remote
description: >-
  Cloud/remote-safe subset of the omnireach internet-research router. Covers
  credential-free channels only: web search and page reads, GitHub repos and CI,
  technical forums, Reddit archives, academic papers, RSS, WeChat article
  discovery, and Zhihu keyword search (API key). Use for web/platform search,
  source comparison, lookups, or reading a URL when running outside the user's
  local machine. Channels that need the user's logged-in browser, home IP, or
  local libraries are out of scope — report them as `requires_local_machine`
  instead of substituting indirect web search.
---

# OmniReach Remote — credential-free research router

This skill is the remote-safe tier of `omnireach`. It assumes a fresh VM: no
user Chrome, no saved cookies, no residential IP, no local file libraries.
Everything here works over plain HTTPS or a documented API key.

## Hard boundary — read first

These channels are **local-machine-only** and this skill must refuse them
honestly. If the user's request needs any of them, say the channel requires the
home machine (it reads the user's logged-in Chrome session or local files) and
stop — do **not** silently downgrade to an indexed web search:

| Local-only channel | Why |
|---|---|
| Xiaohongshu (search, notes, comments) | reads Chrome cookies + browser-native signer |
| Zhihu answer bodies and comments | OpenCLI browser session |
| Douyin, Weibo, X/Twitter, Facebook, Instagram, LinkedIn, Xueqiu | OpenCLI logged-in Chrome |
| YouTube (search/subs beyond public metadata), Bilibili comments & subtitles | cookies + PO token; Bilibili comment API needs session |
| linux.do search | browser-authorized MCP session (anonymous reads still work — see forums ref) |
| Local libraries: 资料库, Zotero, study_library.db, email archive, WeChat cache | files on the home machine |

Allowed fallback for the above: clearly **label** an indexed web search as
`indirect`, and only when the user asked for best-effort coverage rather than
that specific platform's native data. Never describe an indirect hit as a
platform-native read.

## Channel inventory (this skill)

| Need | Route | Secret |
|---|---|---|
| Web search, official docs | Exa REST API (`EXA_API_KEY`) or host-native web search | optional |
| Read a web page | `curl https://r.jina.ai/URL` (Jina Reader, free tier), Exa fetch, or host web fetch | optional |
| GitHub: repos, code, issues, PRs, releases, Actions/CI | `gh` CLI or REST `api.github.com` (`GH_TOKEN` raises limits) | optional |
| Zhihu keyword search | `scripts/zhihu-search.py '{"query":"...","count":10}'` | `ZHIHU_ACCESS_KEY` required |
| Forums: v2ex, nodeseek, ubuntucn, enshan, linuxorg, osdev | `scripts/forum-cli/forum_cli.py <search|post>` | none |
| Discourse sites: nixos, archcn, ubuntu, itsfoss, linux.do (anonymous), any other | `scripts/discourse-forum <cmd>` | none |
| Reddit | Arctic Shift archive API (curl) | none |
| Academic papers | arXiv API, OpenAlex, Semantic Scholar Graph API | none |
| WeChat official-account articles (discovery) | Exa `site:mp.weixin.qq.com` search; body read is best-effort via Jina | `EXA_API_KEY` for search |
| RSS / Atom | `feedparser` or curl + XML parse | none |

See `references/` for per-channel commands, failure signatures, and notes.

## Broad-research workflow

For broad or multi-channel requests, run this planning sequence first — it is
pure reasoning, no tools or local binaries needed. For one exact URL read, one
named platform, or a narrow fact, skip to the focused route instead.

1. **Decompose the request (RouteIntent-style).** Before searching, write down
   `{topic, subquestions[], channel_families[], chinese_scope,
   include_channels[], exclude_channels[], focus_channels[], time_range}`.
   `chinese_scope` is `auto` (default), `only`, `include`, `prefer`, or
   `exclude`. Explicit includes narrow the scope, exclusions always win, focus
   only changes priority. `只查` is a hard restriction. If the topic is
   missing, requirements conflict, or a reference is unclear, ask **one**
   clarification question and do not start.
2. **Pick the channel package.** `所有` / `all` / `全球` means every channel in
   the inventory table above plus discovery of relevant new sources.
   `只查中文` selects the Chinese-language channels (v2ex, nodeseek, archcn,
   Zhihu search, WeChat discovery, Chinese forums/RSS). A named channel list
   overrides the package. When the user asks which channels you would use,
   answer with the selected package without starting research.
3. **Deduplicate across subquestions.** Split multi-part questions into
   subquestions, then share channel/query work between them — read the same
   source once, attribute it to every subquestion it answers.
4. **Assign tools per subquestion.** Separate discovery from body reads from
   comments: pick the most direct source that answers each part, and add one
   complementary backend only when independent confirmation or missing
   coverage requires it. Do not run parallel general engines by default.
5. **Check prerequisites before calling.** Confirm the channel's credential
   and adapter exist before counting it as usable. A configured adapter,
   health check, or discovery listing is not a successful content read.
6. **Track coverage while running.** Keep per-channel state: adapter
   available → query matched → body read → pagination exhausted. Broad
   coverage is **not** complete while any selected channel is blocked,
   discovered-only, or pending — report the exact gap instead of claiming
   completeness.
7. **Close with the ledger** (runtime rule 9).

## Runtime rules

1. **Announce channel and backend** before each search/read
   (e.g. `V2EX: forum-cli`, `知乎: 官方 OpenAPI`, `Reddit: Arctic Shift`).
2. **Generate a bilingual query pack** before each search request: keep the
   original query plus 3–5 short intent-preserving variants in Chinese and
   English. Preserve product names and technical terms. A direct URL read does
   not need expansion.
3. **Snippets are not reads.** Search results, titles, and cards are discovery
   evidence. Read the body of relevant sources before reporting claims.
4. **Separate states.** Distinguish: adapter available, query matched, body
   read, pagination exhausted. `empty` (ran, matched nothing) ≠ `blocked`
   (HTTP/WAF refusal) ≠ `missing credential`. `exit 75` from forum-cli means
   blocked, not empty.
5. **Direct vs indirect.** Label results as `direct` (platform-native route) or
   `indirect` (indexed web search). Keep login/captcha/anti-bot/network/tooling
   failures as distinct states and report the exact blocker.
6. **Secrets.** Read credentials from environment variables only
   (`EXA_API_KEY`, `GH_TOKEN`/`GITHUB_TOKEN`, `ZHIHU_ACCESS_KEY`,
   `JINA_API_KEY`). Never print, log, or persist them. A missing optional key
   degrades that channel to host web search — say so; a missing required key
   means the channel is unavailable, not empty.
7. **No writes.** Read-only research: no sign-ins, posting, liking, comments,
   installs of heavy browsers, or repo writes unless the user explicitly asks.
8. **Temp files in `/tmp/`.** Do not create research artifacts in the repo
   unless asked for a saved deliverable.
9. **Ledger for broad research.** For multi-channel work, end with one row per
   channel: backend, direct/indirect, queries run, retrieval time, stop
   evidence (last page/cursor or blocker), source URLs with dates, bodies
   actually read, status, limitations.
