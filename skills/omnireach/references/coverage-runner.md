# Persistent coverage runner

Use the runner for broad research and solution comparisons. Use `scope="forums"` for a generic forum/community search, focused scope for one named site, exact URL, or narrow fact.

## MCP flow

1. Generate a bilingual `QUERY_PACK` with `bilingual-skill-search`; run Doctor and pass any discovered channel IDs as `extra_channels`.
2. Let `research_start(original_query, query_pack, scope="auto")` use the shared resolver: explicit all-forum wording wins over a named-site mention; a named single site stays focused; generic forum/community search queues every registered forum. Other broad searches keep the required 18 channels and add registered technical forums for software, Linux, hardware, servers, or networking topics.
3. Call `research_step(run_id)` repeatedly. It resumes an existing `in_progress` item before claiming new work. Execute its channel query using the indicated backend. Record each returned page with channel, query group, query, backend, method, page/cursor, screened count, and terminal evidence. Supply a stable `event_id` when recording so retries are idempotent; the same ID with conflicting evidence is rejected. Follow each cursor before starting another route.
4. On native access failure, record `channel_status` with the direct method and `attempt_fallback=true`; the next step queues the site-limited indirect route. Record the fallback separately.
5. Read relevant source bodies through the host tool and pass the body to `research_record` as `body_read`. The runner stores only character count and SHA-256, not the body, so those fields alone are not sufficient for audit. For factual findings and auditor input, preserve the exact read body in the current run's temporary evidence directory and build a claim evidence bundle using [evidence-contract.md](evidence-contract.md). Keep summaries, URL, publication date and comments state in the event; unread or blocked replies keep the result partial. Complete short-form sources (for example, a short social post) may be counted at 200+ characters only when `short_form_source: true` and a `short_form_reason` explains that the full source was read.
6. If screening marks a result relevant by mistake, record an auditable `relevance_review` for that exact search page and item ID, with `relevant: false` and a reason. Never silently edit or delete a screened result.
7. Call `research_check(run_id)` before presenting findings. Keep the run ID and resume pending work after interruption. A partial result must list exact channel issues. Before delivery, validate the evidence bundle and have the auditor check each key claim against the cited body; a valid hash or matching quote proves traceability, not semantic support.

## CLI

```bash
agent-reach-search "broad research query"   # creates broad or automatically routed forum/focused run
agent-reach-research start --query "forum query" --query-pack '<JSON>' --scope forums
agent-reach-search step RUN_ID
agent-reach-search check RUN_ID
```

For structured evidence writes, use the `research_record` MCP tool or:
`agent-reach-research record RUN_ID --evidence '<JSON>'`.

## Evidence states

`not-run`, `access-blocked`, `discovered-only`, `searched-no-relevant-results`, and `deep-read` describe distinct states. A title-only result, probe, empty output, or successful command does not prove a source body was read. Broad completion requires both query groups to have a documented pagination stop on every channel, result screening, relevant source-body reads, and no remaining issue. Channel availability does not imply full-site coverage.

RSS and Xiaoyuzhou tasks require feed/program discovery before reading entries or episodes. The forum registry includes Reddit, V2EX, Linux.do, NodeSeek, Ubuntu China, Arch Linux China, NixOS Discourse, Ubuntu Discourse, It's FOSS, Linux.org, OSDev and Enshan. It is the source for forum queue membership and native-route acceptance checks. Keep it aligned with the per-site route and status recorded in [forums.md](forums.md): the registry row must not claim a native route the table marks otherwise, and a status change in one file needs the same change in the other. As of 2026-10-19 the two rows that changed are Reddit (`status: verified` — `rdt` primary, `--after` cursor pagination, disjoint-id pagination check) and Linux.do (`status: verified` — one fixed runtime and one authorized session, registered per agent; the session was restored by a single `linuxdo-mcp login`).
