# Search, QueryPack, and pagination

The central dispatcher and per-task provider/channel map live in [tool-routing.md](tool-routing.md). Use this page for QueryPack, exact invocation limits, and pagination. Broad research must follow [research-coverage.md](research-coverage.md).

## Bilingual QueryPack

Before every search, invoke `bilingual-skill-search` with the original request. If agent-to-agent skill invocation is unavailable, run the local generator:

```bash
python3 "/Users/mac/LocalSkills/统一技能库/sources/desktop-local/common/bilingual-skill-search/scripts/generate_query_pack.py" --intent "ORIGINAL_REQUEST" --json
```

Keep 3–5 short, intent-preserving queries and the original request. Preserve product names and technical terms; do not add capabilities. Respect a user-imposed language restriction. Run the pack's relevant queries even for a named single platform; a direct URL read without searching does not need query expansion.

## Exa / general web search

Use Agent Reach's provider map before selecting a general engine or specialist source. Choose one provider per subquestion by default; add an independent provider when the result set is incomplete or needs cross-checking. Use `web_search_exa` for Exa-led discovery, `web_fetch_exa` for known URLs, `web_search_advanced_exa` when filters matter, and `agent_run` for multi-step research. See [exa-mcp.md](exa-mcp.md) for exact parameters, run logging, and cost controls.

```bash
mcporter call exa.web_search_exa query="query" objective="Prefer official or primary sources; exclude unrelated pages; extract the facts needed to answer the request." numResults=10
mcporter call exa.web_search_exa query="site:example.com query" objective="Find relevant official pages on this domain and extract the requested facts." numResults=10
```

`objective` is required by the current MCP schema. Use official domains for documentation and site-specific searches only as indirect platform evidence. Inspect tool schema/help and returned paging metadata before deciding whether more results are available. If the Exa tool exposes no page cursor or total count, record that as a backend limit; add supported query variants or filters and do not equate `numResults` with exhaustive platform search.

Host web search, Exa, Skywork Search, and AnySearch overlap on general web queries. Route ordinary single lookups to one available general engine; route vertical queries through the domain-specific source, using AnySearch only after `get_sub_domains` discovers its exact schema. Skywork Search requires its configured key. Do not start several generic engines merely because they are installed.

## Fast discovery helper

```bash
agent-reach-search "query"
```

The installed helper is a discovery bundle with fixed caps: Exa calls request 8 or 5 results; it runs five fixed GitHub repository searches at 8 results each; it combines V2EX, Linux.do, and Zhihu into one indirect query, and combines WeChat, Bilibili, XiaoHongShu, and Weibo into another. Optional direct Reddit output is cut at 220 lines. These are script limits, not platform limits; the helper does not perform complete per-channel paging or deep reading. Continue with platform-native commands and [research-coverage.md](research-coverage.md).

## GitHub and code search

Use the official `gh` CLI and read the candidate repository itself, then inspect relevant releases, issues, discussions, or source files. See [dev.md](dev.md).

```bash
gh search repos "query" --sort stars --limit 10
gh search code "query" --language python --limit 100
gh repo view OWNER/REPO
gh release list -R OWNER/REPO
gh issue list -R OWNER/REPO --state all --limit 100
```

`--limit` is the command's requested result count. Inspect `gh ... --help` and page/API metadata for the endpoint's actual maximum; continue with supported pagination or complementary terms where available. Search-result titles do not replace reading README/docs and relevant feedback.

## Channel search

Use the direct route documented for each platform:

- Bilibili: `bili search "query" --type video --page N -n 42 --page-info --json`. The response preserves raw rows and provides page metadata, no-BV card counts, duplicate counts, and client truncation. API `platform_total` is the reported search window, not site-wide volume; deduplicate stable BV IDs across pages and continue until a terminal page or documented cap. See [video.md](video.md).
- YouTube: `yt-dlp --dump-json "ytsearchN:query"`; `N` is a requested result count. Increase it deliberately and use distinct supported queries; metadata alone is not a transcript.
- Reddit: use the Agent Reach gateway (`agent_reach_search(channels=["reddit"], …)`). It needs no credential and no login: a subreddit scope routes to the Arctic Shift archive (scores, comment counts, nested comment trees, real pagination), and an unscoped query routes to Reddit RSS (live site-wide keyword search, flat, ~25 items, strict rate limit). The credentialed `rdt` route was removed on 2026-11-01 because Reddit's JSON API answers 403 to datacenter/VPN egress IPs; see [social.md](social.md).
- Twitter/X: `twitter search "query" -n N` after the explicit credential environment is available; otherwise use and label indirect site-indexed search.
- V2EX: use its public API for node/topic browsing. Search via a relevant node and clearly label web-indexed queries as indirect.
- WeChat: use the local `wechat-search "query" --page N --limit N` or configured search backend. The script accepts one page per invocation; inspect real page counts and stop/error markers rather than assuming `--limit` covers all matches.
- Zhihu, Weibo, Facebook, Instagram, LinkedIn, Xueqiu: follow the adapters and login constraints in [social.md](social.md), [career.md](career.md), and [finance.md](finance.md). Use indirect web queries only when the direct path is absent or blocked, and keep the method explicit.

For every command, separate platform page size and total from command output caps and any agent-side truncation. Preserve all items actually returned, deduplicate by stable ID/URL without losing query provenance, and continue until there is documented terminal-page evidence, a confirmed platform cap, or an evidenced access failure.
