# Exa MCP: routing, parameters, and run records

The shared Exa MCP server is configured in `~/.mcporter/mcporter.json`; all clients use the local `mcporter` command. Do not copy the API key into client-specific configuration, shell history, skills, run records, or evidence. The config file must remain mode `0600`.

## Tool routing

| Need | MCP tool | Notes |
|---|---|---|
| Discover sources, official pages, or documentation | `exa.web_search_exa` | Pass both `query` and required `objective`; optional `numResults`. |
| Read a known page | `exa.web_fetch_exa` | Required `urls` array; optional `maxCharacters`. |
| Restrict search by domain/date/category/freshness or text | `exa.web_search_advanced_exa` | Defaults to `type="auto"`; use only filters present in the live MCP schema. |
| Research across multiple sources, verify criteria, or produce a bounded table | `exa.agent_run` | One run by default per multi-step task; save the returned run ID and resume it rather than creating a duplicate. |

Examples (mcporter uses schema-aware named arguments):

```bash
mcporter call exa.web_search_exa query="Exa MCP official setup docs" objective="Prefer official Exa documentation; exclude third-party guides; identify the current endpoint and enabled tools." numResults=5
mcporter call exa.web_fetch_exa --args '{"urls":["https://exa.ai/docs/get-started/exa-mcp"],"maxCharacters":5000}'
mcporter call exa.web_search_advanced_exa --args '{"query":"Exa MCP","type":"auto","includeDomains":["exa.ai"],"startPublishedDate":"2026-01-01","numResults":5}'
mcporter call exa.agent_run --args '{"query":"Compare the official Exa MCP setup and Agent run lifecycle; cite the official pages and report any mismatch.","effort":"low"}'
```

`web_search_exa` MCP parameters are `query`, `objective` (required), and optional `numResults`. This MCP mapping differs from REST request shapes: Search REST uses `/search` fields such as `query`, `type`, `numResults`, `includeDomains`, `startPublishedDate`, and `contents`; MCP exposes named tool arguments and `web_fetch_exa` for page reading. Check `mcporter list exa --schema --all-parameters` before relying on optional fields. The MCP tool surface is the operational source of truth for `mcporter`; do not assume a REST field or endpoint is exposed by MCP. Run `agent-reach doctor --json --probe --channels exa_search --execution-context unknown` for a real, read-only search check; the default doctor only checks local setup. Each run writes a private append-only attempt record and reports `route_state`; sandbox DNS/connectivity failures exit `75` with a host retry command. Reuse its `record_path` and `probe_id`; successful host retries retain both attempts as `recovered_on_host`. Pass `sandbox` or `host` only when the caller knows the execution context. The probe requires complete title/source-URL records; exit code zero or error text alone does not count as search success. It preserves the outer error and reports a cause category, redacted diagnostic, HTTP status when present, and actual probe attempts. Transient DNS/connectivity/5xx failures receive at most one retry. If a sandbox call fails on DNS or connection, repeat the same operation through an approved host-network path when available and record both results; DNS failure alone does not prove a sandbox restriction. Do not self-elevate or change DNS/proxy settings. Configuration and `agent_run` cost/continuation behavior remain separate.

## Agent selection and cost

Use `effort="low"` for an ordinary multi-step research task. Use `effort="medium"` when independent sources and several criteria need cross-checking. Medium is the automatic ceiling: ask before high/xhigh/ultra, `auto`, or starting a second run for the same user task. Prefer search/fetch for one lookup or one known page.

Set `effort` explicitly. Fixed `minimal`, `low`, and `medium` tiers do not take a `budget` object; the API supports `budget` only with metered `auto` or `ultra`. Leave `dataSources` empty unless the user explicitly asks to use Exa Connect. Leave contact enrichment fields out. Current published Agent effort prices are minimal $0.012, low $0.025, medium $0.10, high $0.50, and x-high $1.00 per request; Agent search calls are priced separately at $0.005 per call, and contact enrichment / Connect can add costs. Verify current [Exa pricing](https://exa.ai/pricing) before changing these defaults.

Ordinary Search is currently $4 per 1,000 Instant requests or $7 per 1,000 Fast/Auto requests (up to 10 results); Contents is $1 per 1,000 pages. Search/fetch charges are separate from the Agent fixed-effort amount. Pricing can change; report observed `costDollars` when available instead of treating these reference prices as a receipt.

## Async runs and persistent records

Store one JSON record per Agent run under `~/.agent-reach/exa/runs/<runId>.json`, with file permissions `0600`; directory permissions should be `0700`. Never store credentials. Keep `querySummary` short and omit private user data. Record at least:

```json
{
  "runId": "agent_run_…",
  "status": "running",
  "effort": "low",
  "createdAt": "ISO-8601 timestamp",
  "updatedAt": "ISO-8601 timestamp",
  "querySummary": "short, non-sensitive purpose",
  "costDollars": {"total": null, "agentCompute": null, "search": null},
  "sources": []
}
```

After each `agent_run` response, create or update the matching record with the actual status, requested effort, cost breakdown, timestamps, and result sources. For `status="running"`, call `agent_run(runId="agent_run_…")` to continue that run, then update the same file. On timeout, client interruption, or uncertain tool response, first inspect recent run records. If the MCP timed out before returning an ID, use the official paginated `GET /agent/runs?limit=100` list and match the newly created run by creation time and the non-sensitive query purpose; store its returned ID, then resume that same run. Do not submit a replacement while the original may be running. A second run for the same task requires the user's approval. A completed run followed by a distinct, user-requested follow-up may use `previousRunId`; do not confuse that with resuming a running run.

Treat run results as discovery and research output, not independent verification. Open key sources with `web_fetch_exa` or a direct platform route. Exa-indexed social pages count as indirect web search, not direct platform access.

## Sources

- [Exa MCP setup, tools, and authentication](https://exa.ai/docs/get-started/exa-mcp)
- [Agent API: create a run and supported REST fields](https://exa.ai/docs/reference/agent-api/create-a-run)
- [Agent API: list runs and pagination](https://exa.ai/docs/reference/agent-api/list-runs)
- [Exa pricing](https://exa.ai/pricing)
