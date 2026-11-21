# Secrets and graceful degradation

All credentials come from environment variables (cloud secrets). Never print,
log, write to files, or embed them in queries.

| Variable | Covers | If missing |
|---|---|---|
| `EXA_API_KEY` | Exa web search/fetch, WeChat article discovery | Use host-native web search; WeChat discovery → `site:mp.weixin.qq.com` indexed search, label `indirect` |
| `GH_TOKEN` / `GITHUB_TOKEN` | GitHub rate limits, private repos | Unauthenticated `gh`/REST still works for public repos at low limits; on `rate limit` errors say so and wait/narrow queries |
| `ZHIHU_ACCESS_KEY` | Zhihu official search API (required) | Channel unavailable — report `missing_credential`, do not substitute browser/indexed search silently |
| `JINA_API_KEY` | Jina Reader higher limits | Free tier still works at lower rate |

## Zhihu search usage

```bash
python3 scripts/zhihu-search.py '{"query":"QUERY","count":10}'
# optional env: ZHIHU_OPENAPI_BASE_URL (default https://developer.zhihu.com)
```

Results are search cards (title, author, summary) — discovery evidence. Answer
bodies/comments are local-machine-only (OpenCLI browser route).

## Setting secrets on Devin Cloud

Org-level secrets apply to every cloud session
(**Settings > Secrets**, or `devin cloud drs secret-create --key NAME --from-env NAME`).
A running session picks up new secrets the next time it lists them.
