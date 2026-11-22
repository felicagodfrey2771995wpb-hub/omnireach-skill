# Research coverage, deep reading, and evidence

Use this protocol for broad internet research and tool comparisons, and for deployment, installation, configuration, or implementation tasks only after the user selects Yes to researching existing solutions. A No selection skips broad solution research; still consult relevant official documentation when needed. Honor an explicit user limit on channels, time, or budget; record what that limit leaves uncovered. A named single-platform query can stay focused, but still use a bilingual query pack, verify results, and read the requested content.

## Delegated research execution

For Codex broad research using the Omnireach skill, follow the eight-role dispatch matrix in [SKILL.md](../SKILL.md#codex-specialist-subagents). For OpenCode broad research using Omnireach, follow the OpenCode-specific registrations and dispatch rules in [SKILL.md](../SKILL.md#opencode-specialist-subagents). For Antigravity broad research using Omnireach, follow the Antigravity-specific registrations and dispatch rules in [SKILL.md](../SKILL.md#antigravity-specialist-subagents) (Gemini 4 Argon for the auditor and Gemini 3.8 Flash for research roles). Across all hosts, preserve all requested channel coverage, assign one owner per channel, use the host-specific model settings on each actual dispatch, and run the auditor only after research returns. For research that does not use Omnireach, the general route remains one dedicated `gpt-6-luna` child with high reasoning effort. The main Agent verifies source evidence, fills audit gaps, and owns final synthesis. Persistent memory writes follow existing project consent and ownership rules.

## Required channel coverage

For broad research, make a coverage ledger before searching. Attempt each of these 18 channel rows using a direct adapter when one exists. The channel list is a minimum: add relevant platforms reported by the current `agent-reach doctor --json`, plus channels discovered during the search. Do not silently skip a row because of topic, an early good result, or time pressure.

| Required channel | Preferred route / discovery note |
|---|---|
| Exa / general web search | Exa MCP; `agent-reach-search` is discovery only |
| Official documentation | Search official product or maintainer documentation and read it directly |
| GitHub | `gh search`, then open README, releases, issues, or discussions |
| Bilibili | `bili search`; inspect video metadata and subtitles/comments when available |
| XiaoHongShu | **Pinned `xiaohongshu-mcp` (browser-native)**: `scripts/xhs-mcp search/detail/user-profile/my-profile/unread-count`; `xhs` CLI as the search/body fallback; TikHub App V2 only for second-level replies and extra comment pages. **No OpenCLI**, including browser and failure fallback; the browser-native route reuses only the already-authorized session. See [social.md](social.md) and [xiaohongshu-mcp.md](xiaohongshu-mcp.md) |
| Zhihu | **Pinned `zhihu-search` official OpenAPI for keyword search**; no OpenCLI/browser search or automatic indexed fallback. On sandbox failure retry the same approved host API command, otherwise report the blocker. Body/comment readers are separate |
| Weibo | Direct OpenCLI adapter if present; otherwise label `site:weibo.com` as indirect |
| Twitter/X | `twitter` backend when verified; otherwise label `site:x.com OR site:twitter.com` as indirect |
| Reddit | Use the current Agent Reach gateway route in `route-manifest.json`: Arctic Shift archive first, Reddit RSS fallback, with RSS rows hydrated from archive metadata; report archive/live/hybrid freshness accurately. Use Exa or web search only as an explicitly indirect fallback |
| YouTube | `yt-dlp` search/metadata and transcripts; use `yt-comments` for comment sampling |
| V2EX | Public API for topic/node browsing; site-indexed search is indirect |
| WeChat official accounts | WeChat article search backend or `wechat-search`; read with the documented reader |
| Facebook | OpenCLI with existing session; otherwise indirect web search if useful |
| Instagram | OpenCLI with existing session; otherwise indirect web search if useful |
| LinkedIn | LinkedIn MCP when configured; otherwise public profile/article web search is indirect |
| Xueqiu | OpenCLI when already configured and signed in; otherwise indirect web search |
| Xiaoyuzhou | Discover relevant episodes/feeds first, then obtain a transcript or read episode content |
| RSS | Discover relevant feeds/authors first, then read feed entries and linked source content |

The fixed list supplements, rather than replaces, the live channel inventory. If no direct adapter exists, try a focused `site:` search through web search and mark the method `indirect`. Do not mark an unvisited channel `no-result`. For RSS, podcasts, and platforms where reading requires a known account or source, discover relevant feeds/authors first.

## Query expansion and search depth

1. Before searching, generate a bilingual `QUERY_PACK` from the original request with the `bilingual-skill-search` skill. If skill invocation is unavailable, run:

   ```bash
   python3 "/Users/mac/LocalSkills/统一技能库/sources/desktop-local/common/bilingual-skill-search/scripts/generate_query_pack.py" --intent "ORIGINAL_REQUEST" --json
   ```

   Retain the original wording, product names, and technical terms. Use 3–5 short, intent-preserving queries; include original-language and English/Chinese canonical variants where useful. Do not invent requested features. Save the pack and each query in provenance.

2. For each required, relevant channel, use at least two complementary query groups: one describing the user's problem or scenario, and one naming candidate tools, competing approaches, or equivalent terms. Add synonyms, new candidate names, and failure/maintenance/cost/install terms as discoveries suggest. A user-imposed channel or time limit overrides this breadth and must appear in the coverage ledger.

3. Inspect at least 10 returned results per channel, or every result when the channel returns fewer. This is a minimum screening depth, never a command limit or a reason to stop. Keep result totals, unique IDs, screened items, and deeply read sources as separate counts.

4. If a channel has relevant results, deeply read at least two different primary-source bodies. If only one relevant source exists, read it and record the limitation. For videos, verify publication date, description, and transcript/subtitles or actual content. A title or thumbnail alone is `discovered-only`. Read recent comments/replies for feedback where available, especially failure, stale, blocked, pricing, installation, and login reports. Formal docs and RSS entries without comment threads should say `comments unavailable`, not imply they were reviewed.

## Full pagination and stopping evidence

Before a search, inspect command help, API docs/source, or response metadata for default output caps, explicit `--limit`/`-n`, page size, cursor/page parameters, and total/page count. Preserve and screen every item returned on each page; do not silently truncate a page to a display-sized sample. Save large raw results to `/tmp/` when necessary.

Continue using the actual next-page cursor/page until one of these conditions is evidenced: the platform reports the terminal page/cursor; the platform's documented/observed maximum is reached; or the bounded retry chain still fails. Record the exact last page/cursor and response evidence. A repeated page, empty output, mismatch between reported and received counts, or unknown total requires checking before stopping. Do not call any of these `complete` without support.

Separate platform caps from limits introduced by a CLI, script, API wrapper, or the agent's own command. If a platform cap prevents further pages, use supported synonyms, scenario splits, candidate names, or time/sort filters to add relevant coverage; do not evade access controls. Search new candidates and alternative implementation routes again, including their current failure, maintenance, cost, and install evidence.

The installed `agent-reach-search` helper is only a fast discovery shortcut: the current script hardcodes Exa result counts (8 or 5), runs five fixed GitHub repository queries with an 8-item cap each, combines multiple sites into one query, and truncates optional direct Reddit output to 220 lines. Those limits are helper choices, not platform end-of-results evidence. It cannot fulfill this protocol by itself.

## Per-channel evidence ledger

Maintain one row per channel with these fields:

`channel | backend | method(direct/indirect) | queries | retrieval_time | pages/cursors + stop evidence | retrieved/unique/screened/deep-read counts | source URL + publication date | content/comments actually read | status | conclusion/limitations`

For each material finding, also create a claim evidence bundle as specified in [evidence-contract.md](evidence-contract.md). Quote the saved source body with a locator, label supported facts, inferences, conflicts, and unverified claims, and retain the limits on date, version, geography, and read scope. Pass the readable source bodies with the bundle to the auditor; a ledger, body character count, or hash alone cannot establish that a conclusion follows from the source. Run `python3 scripts/check-evidence BUNDLE --sources-dir SOURCE_DIR` to catch missing fields, broken references, changed bodies, and quotes that are absent from the cited body. The check does not decide semantic support.

Keep all screened items in the run evidence. Correct a false-positive match only through an auditable `relevance_review` tied to the exact query, page, and item ID; retain the item and the review reason. A complete short-form post can count as a body read from 200 characters when `short_form_source` is true, `short_form_reason` confirms the complete source was read, and the source is genuinely short. Longer pages still require at least 500 characters of body evidence.

Allowed statuses:

- `deep-read`: relevant body/content was actually read at the required depth.
- `searched-no-relevant-results`: all supported query groups were searched and no relevant result appeared.
- `discovered-only`: results were found but relevant body, transcript, or content was not read.
- `access-blocked`: authentication, captcha, anti-bot, network, permission, or environment failure prevented the read.
- `not-run`: work remains; state why and continue independent channels.

Record direct adapter failures and indirect fallback results separately. Keep source links and dates. Do not use a repost as an independent source when it duplicates another source.

For a proposed tool or workflow, check current official requirements, maintenance/release status, environment, login, cost, historical bulk/backfill behavior, incremental update behavior, and recent failure reports. Report evidence levels explicitly: `official docs`, `independent user feedback`, and `local test`. A configured backend, HTTP 200, or successful command exit is not proof that the desired content was obtained.

## Completion check

Before delivery, inspect every row and verify query expansion, complete page handling or a recorded stop condition, platform-vs-command caps, content/video/comment depth, source links/dates, and status. Only when every required channel is `deep-read` or `searched-no-relevant-results` may the work be called **complete broad-channel research**. If any row is `discovered-only`, `access-blocked`, or `not-run`, deliver a clearly labeled partial result, list exact gaps, and finish all other independent work first.

Summarize channel coverage, blockers, excluded candidates and reasons, and the strongest supported findings. Include the evidence ledger in a user-visible deliverable for substantial research. Do not claim results beyond what was searched, screened, and read.
