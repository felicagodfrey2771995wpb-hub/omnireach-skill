# Web search, Exa, page reads, pagination

## Exa REST API (`EXA_API_KEY` set)

```bash
curl -s https://api.exa.ai/search -H "x-api-key: $EXA_API_KEY" -H 'content-type: application/json' \
  -d '{"query":"QUERY","numResults":10,"contents":{"text":{"maxCharacters":3000}}}'
```

- Restrict to a domain with `"includeDomains":["example.com"]` — use official
  domains for documentation lookups; treat domain-limited results on social
  platforms as `indirect` evidence only.
- `numResults` is a requested cap, not proof of exhaustion. If Exa returns no
  cursor, record that as a backend limit and try query variants instead of
  claiming completeness.

## Host-native web search / fetch

When no `EXA_API_KEY` is present, use the host agent's built-in web
search/fetch tools and label the backend accordingly. Do not start several
generic engines just because they exist — pick one per subquestion, add a
second only when coverage is incomplete or needs cross-checking.

## Reading a page

```bash
curl -s "https://r.jina.ai/https://example.com/article"        # Jina Reader (free tier; JINA_API_KEY optional)
curl -s "https://example.com/feed.xml"                          # raw fetch for feeds/APIs
```

A blank response, challenge page, or metadata-only output is not a successful
read — record the blocker. Jina/curl often hit WAFs; a 403 is `blocked`, not
`empty`.

## Pagination rules

- Separate **platform page size / total** from **command output caps** and
  agent-side truncation.
- Preserve all returned items; deduplicate by stable ID/URL without losing
  query provenance.
- Continue until documented terminal-page evidence, a confirmed platform cap,
  or an evidenced access failure — not until a `--limit` is reached.

## Bilingual query pack

Produce it yourself before each search: original request + 3–5 short variants
split across Chinese and English. Example for "iPhone 17 发热":
`["iPhone 17 发热", "iPhone 17 overheating", "iPhone 17 烫手", "iPhone 17 Pro thermal issue"]`.
Respect a user-imposed language restriction; a direct URL read needs no pack.
