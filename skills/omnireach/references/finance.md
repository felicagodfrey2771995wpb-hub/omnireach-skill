# Xueqiu / 雪球

First inspect `agent-reach doctor --json`. `active_backend: null` or an HTTP 400 means the read is unverified or the session/API failed; it does not mean a ticker is absent. Prefer an already-installed OpenCLI adapter with an existing user-controlled session:

```bash
opencli xueqiu whoami -f yaml
opencli xueqiu search "NVDA" -f yaml
opencli xueqiu stock NVDA -f yaml
opencli xueqiu hot -f yaml
opencli xueqiu hot-stock -f yaml
```

Only rely on commands shown by `opencli xueqiu --help`. If the session is missing, record `access-blocked`; do not log in or extract browser cookies. `agent-reach configure --from-browser chrome --platform xueqiu` imports a platform credential and requires an explicit user request.

Accept a quote read only when the output includes the expected ticker/name and market data, or a non-empty content list. Check the quote timestamp and whether it is delayed. A successful `whoami` without quote data is not a successful quote read. Search and read recent public user feedback when evaluating a tool or service. Market information may be delayed and is not investment advice.
