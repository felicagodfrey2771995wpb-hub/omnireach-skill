---
name: omnireach
description: >-
  Internet research and URL-reading router for current facts, official sources,
  code, academic papers, products, travel, social and video platforms, RSS,
  podcasts, finance, local libraries, and user-named private sources. This is the
  machine-verified superset (skill id `omnireach`): every channel route below was exercised locally and
  each route records its own limits, so the routing here is newer than the
  upstream copy shipped in the agent-reach package. Use for
  web/platform search, source comparison, lookups, or reading a URL. Routes to
  native tools, MCPs, CLIs, specialist skills, and channel references. For each
  new multi-step task, ask whether to research existing solutions; honor explicit
  yes/no choices and reuse the choice on continuations. See the bundled routing,
  OpenCLI, host-tool, coverage, and Exa references.
---

# Agent Reach — Internet research and channel router

Use this skill as the search-routing entry point for public web, platforms, scholarship, products, travel, skill markets, news, local libraries, and user-requested private-source searches. Read [references/tool-routing.md](references/tool-routing.md) to select the provider and channel. Use [references/opencli-read-tools.json](references/opencli-read-tools.json) for the complete read-only OpenCLI snapshot and [references/host-tools.md](references/host-tools.md) for host MCP, local search, and specialist assignments. For broad work, follow [references/research-coverage.md](references/research-coverage.md) and [references/coverage-runner.md](references/coverage-runner.md).

## Pinned XiaoHongShu route — mandatory

**小红书 / XiaoHongShu / RedNote 必须使用专用 `xhs` CLI，禁止走 OpenCLI。** This channel-specific rule overrides generic browser discovery and fallback advice, Doctor hints, the OpenCLI command inventory, and historical browser instructions.

- Search: `xhs --cookie-source chrome search "QUERY" --json` (paginate with `--page N`). Body: `xhs --cookie-source chrome read "NOTE_ID" --json` — pass the **bare note id** returned by search so the CLI reuses its own cached note token and `xsec_source`. If you must build a URL, use the **note's** `xsec_token` (top-level `item.xsec_token`); `note_card.user.xsec_token` is the **author** token and makes the body read fail.
- Comments: use this skill's `scripts/xhs-comments --url "NOTE_URL_WITH_XSEC_TOKEN" --max-pages N --json`. It uses a browser-native signer internally, **not OpenCLI**; returns top-level comments only. Do not replace it with the known-rejected `xhs comments` signer.
- **Never run `opencli xiaohongshu ...`, `opencli xhs ...`, or `opencli browser ...` against XiaoHongShu**, including search, note body, comments, and failure recovery. Do not substitute another generic browser/MCP route automatically.
- A missing binary, empty result, timeout, sandbox/cache permission error, expired session, or HTTP/signature failure does not unlock OpenCLI. Diagnose and retry the same dedicated route through the approved host path when appropriate; otherwise report the exact blocker. An allowed `site:xiaohongshu.com` web search is **indirect**, never native CLI success.
- Cookie cache reality (verified 2026-10-21 against the `xhs` 0.6.4 source): the CLI prefers its **saved** cookie cache (`~/.xiaohongshu-cli/cookies.json`) and only re-reads the browser when that cache is older than 7 days or when a session-expired error triggers one forced refresh. `--cookie-source chrome` does **not** re-read Chrome on every call. Refresh it on purpose with `xhs login --cookie-source chrome`, which extracts the already-logged-in browser session and needs neither a QR scan nor a new login.
- Failure classification (verified 2026-10-21 by an offline mock test of the same version): HTTP 461/471 → `verification_required`, the platform is asking for human verification — complete it in the browser, refresh the cookie cache, then retry slowly, because repeated retries escalate the block instead of clearing it. `code=-100` → `not_authenticated`, the server-side session is dead — the user logs in again in the browser, then refresh the cache. `300015` → `signature_error`. `300012` → `ip_blocked`, change network. `empty noteDetailMap` / `api_error` is **not** proof the note is missing: the CLI falls back to an HTML read and can mask an earlier verification failure, so re-run the classification before reporting the note as absent.
- Announce `小红书：xhs CLI；评论：scripts/xhs-comments（非 OpenCLI）` before use. The registry route is `xhs-cli + xhs-comments`; see [social.md](references/social.md) and [route-manifest.json](references/route-manifest.json). Do not revive [the retired browser-search note](references/xiaohongshu-browser-search.md).

## Pinned Zhihu search route — mandatory

**知乎关键词搜索必须调用 `zhihu-search` 官方 OpenAPI，禁止用 OpenCLI 搜索或浏览器搜索代替。** Run `python3 /Users/mac/LocalSkills/统一技能库/sources/skill-manager/zhihu-search-2/scripts/zhihu-search.py '{"query":"QUERY","count":10}'`. Credentials are loaded from the shared skill's private `.env`; never print or record them.

- Do not run `opencli zhihu search`, OpenCLI browser search, or `zhihu-search-browser.js`. A missing key, empty result, API error, quota error, timeout, or sandbox failure does not permit automatic fallback. If appropriate, rerun the same API command on the approved host; otherwise report the exact API blocker. No automatic indexed-web substitution.
- Announce `知乎搜索：官方 OpenAPI（zhihu-search）` before searching; record the actual API status. At most 10 results per query and no verified continuation cursor: split queries without claiming pagination exhaustion.
- Answer bodies and comments have separate readers (`opencli zhihu answer-detail` / `answer-comments`); using those after API discovery does not authorize OpenCLI **search**. See [social.md](references/social.md) and [route-manifest.json](references/route-manifest.json).

## Persistent coverage runner

Broad research and solution comparisons MUST use the four-operation workflow: `research_start` → repeated `research_step` / host-native searches and reads / `research_record` → `research_check`. It creates a durable run ID and reports exact gaps. Never use the legacy quick search helper as a substitute for this workflow. Exact URLs, one-platform tasks and narrow facts may use a focused route.

Use the shared scope resolver in CLI and MCP. An explicit request for all forums (including “搜所有论坛，尤其关注 Linux.do”) queues every registered forum even when it also names one site; a named single site stays focused; a generic request to search forums/communities queues all registered forums. Ordinary broad research keeps its existing scope and adds registered technical forums for technical topics. The resolver is `research_start(scope="auto")`; explicit `scope="forums"`, `focused`, or `broad` remains available.

The current runner is installed at `/Users/mac/Work/projects/codex/app-data/agent-reach/runtime/agent-reach-research`. If MCP tools are unavailable, use its `start`, `step`, `record` and `check` commands. Search execution remains on the current host's existing platform tools; the runner coordinates and validates their returned evidence. Pass new Doctor channels as `extra_channels`. Do not report broad coverage complete while any channel is blocked, discovered-only or pending.

Linux.do uses the already browser-authorized `mrsxs/linuxdo-mcp` independent session through the registered **MCP `linuxdo` tools** (`search`, `get_topic`, `whoami`); no manually supplied API Key is required. Call those tools whenever the host exposes them — the route is fixed by the skill and does not depend on the user naming it — and do not substitute an anonymous Discourse or plain HTTP path. For hosts without MCP tools, `scripts/linuxdo-read` speaks MCP stdio to the same server. That site rate-limits by request frequency: pace consecutive reads, and on 「被 Cloudflare 拦截/请验证您是真人」 pause about a minute and retry once rather than looping. See [the forum reference](references/forums.md) for search/reply cursors and the OpenCLI fallback.

## Routing sequence

1. Classify the subject and evidence needed: current fact, official rule/specification, code/repository, scholarly paper, product or trip, current discussion, video/audio, local library, private workspace, or prior conversation.
2. Honor a named source, platform, URL, date range, geography, and output format. Search private sources only when the user names them or the task requires them.
3. Select the primary provider and owner from `tool-routing.md`. Prefer the most direct source that answers the request: official docs/APIs for authoritative facts; native platform search for platform-specific results; specialist sources for their domain; broad engines for discovery or missing coverage.
4. Assign separate tools for discovery, page/body reading, comments/replies/reviews, and media transcripts. Search snippets alone are not a body read. Add one complementary provider when independent confirmation or coverage is needed; do not duplicate general engines by default.
5. Check the selected channel's prerequisite and status, then make a read-only call. Do not mistake configuration, installed adapters, schema discovery, or a health check for a successful content read. For Reddit, Exa search, and Bilibili search, explicitly run `agent-reach doctor --json --probe --channels reddit,exa_search,bilibili`; inspect each channel's `content_probe`. A plain doctor/version check is not a content query.
6. On failure, classify the cause: missing tool, unavailable configuration, auth/session, quota, network/proxy, unsupported endpoint, or empty results. Follow the listed fallback and label direct platform access separately from indexed-web results.
7. Report readiness as distinct states: `configured`, `tool discovered`, `query returned relevant items`, and `requested content read`.

### Network failure routing

- Every `doctor --probe` run writes a private JSONL attempt record and a `probe_id`. Each event keeps the channel, backend, timestamp, execution context, status, cause, and result count. Reuse `record_path` and `probe_id` for the host retry; the ledger appends and retains both attempts.
- Sandbox DNS/connection failures set `route_state=host_retry_required` and exit `75`. Unknown-context network failures set `execution_context_unverified` and also exit `75`. Run the JSON `host_retry_command` through the host's formal network path. Do not report a channel outage while host retry is pending. If the evidence file cannot be written, Doctor exits `74` before the probe.
- Sandbox HTTP-level blocks — 403/401/429/503, a Cloudflare "Just a moment..." interstitial, or any WAF/challenge page — carry the same semantics as a connection failure: `route_state=host_retry_required`, exit `75`, retry through the host network, and never record the site as unavailable from the sandbox attempt alone. Verified 2026-10-15: linux.do, nodeseek.com, forum.osdev.org, linux.org forums all returned 403 to sandbox curl while the same URLs returned content over the host network. Forum and community sites are almost universally WAF-protected; see [references/forums.md](references/forums.md) for per-engine routes.
- A successful host retry sets `route_state=recovered_on_host`, keeps both events in `attempt_history`, and allows the task to continue through that host route. Other failures exit `1`; valid content on every selected probe exits `0`. Empty output remains `empty_result`, not content success.
- Pass `--execution-context sandbox`, `host`, or `unknown` only when the caller knows the current execution context; the CLI default is `unknown`. The field is diagnostic metadata and never grants network access.
- A sandbox DNS or connection error alone does not prove a platform outage or sandbox restriction. If the host offers an approved local-network execution path, repeat the same read-only operation there and record both attempts' context, time, backend, status, and returned item count. Use the host's formal permission flow when required; the program must not elevate itself or change system DNS, global proxy, or sandbox policy.
- If the sandbox fails and the host succeeds, continue the requested native search on the host and report the split accurately. If the host probe also fails, use the channel's existing auth/rate-limit/service-error fallback. Keep indexed-web results marked as indirect.
- Probe JSON preserves the outer `error_type` and may add `cause_type`, redacted `diagnostic_message`, `http_status`, and `attempts`. Interpret `status` and returned content together; a zero exit code is not sufficient evidence of success.

```bash
agent-reach doctor --json --probe --channels reddit,exa_search,bilibili --execution-context sandbox
agent-reach doctor --json --probe --channels reddit,exa_search,bilibili --execution-context host
```

For one named platform, use its direct route first and indexed-web fallback second. For mixed questions, split by subquestion and route each to its domain owner. Explicit broad-research requests retain every required channel; tool selection does not reduce coverage.

For multi-step web research, prefer Exa `agent_run` once per task: use explicit `effort=low` for ordinary multi-step work and `effort=medium` for harder cross-source checks. Medium is the automatic ceiling; ask before using a higher effort or starting an additional run for the same task. Record each run and resume the same `runId` after timeouts or interruptions. For single lookups, use search/fetch instead. See [references/exa-mcp.md](references/exa-mcp.md).

At the start of every new multi-step task, show the current chat choice “本次是否先调研现成方案？” with “是” and “否” options, and wait if the user makes no selection. Yes enables the full research-coverage protocol; No means proceed directly, while checking relevant official documentation when needed. A direct request to research or skip research takes precedence without another prompt. Reuse the same choice when resuming, repairing, or handing off that task. This choice controls optional solution research; it does not replace the task instructions. When research is selected, prefer a verified, maintained option that fits the user's environment and saves effort. Combine existing approaches and add only missing implementation work when no complete fit exists. Clearly distinguish official documentation, independent user feedback, and a local test.

When the user selects Yes or directly requests broad research, use team-mode by default to dispatch one dedicated research subagent with model `gpt-6-luna` and high reasoning effort. Give it a concise, independent brief with the actual question, constraints, and acceptance criteria. The child performs the searches, reads source bodies and available user feedback, and returns the evidence ledger and findings; it does not only propose a plan. The main Agent owns final acceptance: audit the returned work against the complete coverage, pagination, expansion, deep-reading, and evidence rules, fill any gaps, make complex fit or strategy judgments, and synthesize the final conclusion. If the requested model or dispatch route is unavailable, the main Agent performs the same workflow directly and records that fallback. Any persistent or long-term memory write remains subject to the existing project consent and ownership rules.

## Non-negotiable runtime rules

1. Before searching a supported channel, run `agent-reach doctor --json` when available and read the matching backend status. `active_backend: null` or `warn` means that channel is unverified, not absent. Run a task-relevant read-only command when needed; success requires actual non-empty content.
2. Announce the channel and backend in use. Read that channel's reference before complex work; follow its bounded retry path instead of guessing commands.
3. Generate a bilingual `QUERY_PACK` before each search request. Use the `bilingual-skill-search` workflow when available; otherwise use the local generator documented in the research reference. Preserve the original query and route intent-preserving variants.
4. For broad research, execute the channel coverage, pagination, reading-depth, and evidence checks in the research reference. Search summaries, titles, `doctor`, exit code zero, and downloaded result counts alone do not count as content verification.
5. Distinguish direct platform reads from indirect site-indexed web searches and fallbacks. Keep login, captcha, anti-bot, network, and local execution-environment failures in separate states. Never claim an indirect hit came from a direct adapter.
6. Keep output and temporary files in `/tmp/`; use `~/.agent-reach/` only for persistent Agent Reach data. Do not create research artifacts in the skill or agent workspace unless the user asks for a saved artifact.
7. Do not sign in, import credentials, post, comment, like, or install optional channel dependencies unless the user asks for that action. Never expose credentials in commands, logs, or evidence.
8. When the user has authorized a platform session, reuse the browser session read-only instead of scripting a login flow: read the user's own Chrome cookies through the channel's documented flag, never print or persist the values, and never write platform configuration. An empty-body `4xx` is a rejected signature until proven otherwise — see [session-model.md](references/session-model.md).

## Route map

| Intent | Reference |
|---|---|
| Web search, official docs, broad research, evidence protocol | [search.md](references/search.md), [exa-mcp.md](references/exa-mcp.md), [research-coverage.md](references/research-coverage.md) |
| X/Twitter, Reddit, Bilibili, XiaoHongShu, V2EX, Facebook, Instagram, Weibo, Douyin, Zhihu | [social.md](references/social.md) |
| Platform sessions, signature failures, browser-native signers, PO tokens | [session-model.md](references/session-model.md) |
| LinkedIn profiles, companies, jobs | [career.md](references/career.md) |
| GitHub repositories, code, issues, releases | [dev.md](references/dev.md) |
| Web pages, WeChat articles, RSS, local WeChat cache | [web.md](references/web.md) |
| Finding and comparing technical forums or online communities | [forums.md](references/forums.md), [tool-routing.md](references/tool-routing.md#技术论坛与社区发现), [research-coverage.md](references/research-coverage.md) |
| YouTube, Bilibili, Xiaoyuzhou, subtitles, comments, transcription | [video.md](references/video.md) |
| Xueqiu stocks and community content | [finance.md](references/finance.md) |

## Runtime discovery and health

```bash
agent-reach doctor --json       # channel inventory and backend readiness hints
agent-reach version             # installed version
agent-reach check-update        # check upstream release; does not update
agent-reach watch               # concise health + update check for scheduled checks
opencli list                    # discover installed OpenCLI adapters
opencli PLATFORM --help         # inspect one adapter's read-only commands
```

Treat the doctor report as a routing hint. It does not verify a particular query, page, post, transcript, or comment. Run a read-only operation only for a channel relevant to the user's request and record the returned content or the exact access limitation.

Agent Reach adds local browser-free comment fallbacks (`bili-comments`, `yt-comments`), transcription (`transcribe`), provider configuration, output formatting, setup, and skill registration. See [video.md](references/video.md), [social.md](references/social.md), and [operations.md](references/operations.md). `agent-reach install` can change system dependencies, configuration, or skills; reserve it for an explicit installation request.

## Existing fast-discovery command

`agent-reach-search "query"` is a convenience discovery bundle, not a complete research workflow. Its installed script uses fixed small result counts, a fixed set of GitHub queries, an optional Reddit output cut, and combines several Chinese platforms into one web query. Do not treat it as exhaustive, platform-native coverage, or a substitute for the per-channel queries, full pagination, source reading, and evidence ledger required for broad research. See [search.md](references/search.md).

## References

- [Research coverage and evidence protocol](references/research-coverage.md)
- [Search, Exa MCP, and pagination](references/search.md)
- [Exa tool parameters, costs, and Agent run recovery](references/exa-mcp.md)
- [Social and community platforms](references/social.md)
- [Session model and signature-failure diagnosis](references/session-model.md)
- [Developer and GitHub tools](references/dev.md)
- [Web, WeChat, RSS](references/web.md)
- [Video, comments, transcription](references/video.md)
- [Career platforms](references/career.md)
- [Finance platforms](references/finance.md)
- [Agent Reach configuration and lifecycle commands](references/operations.md)
