# Web pages, WeChat articles, RSS

## General web pages

```bash
curl -s "https://r.jina.ai/https://example.com/article"
```

Jina Reader for readable public pages (free tier; `JINA_API_KEY` optional for
higher limits). Verify the response contains the article text, title, and
author/date. Blank output, a challenge page, or metadata-only is not a read.

## WeChat official-account articles

**Discovery** (`EXA_API_KEY` required): Exa query with
`includeDomains:["mp.weixin.qq.com"]`. Cards/snippets are discovery evidence,
not body reads.

**Body read**: `curl https://r.jina.ai/https://mp.weixin.qq.com/s/ID`. Jina and
curl often hit WeChat's verification — record challenge/empty output as
`blocked`/`discovered-only`. The reliable body reader (Camoufox, local cache
via `wx biz-articles`) is local-machine-only.

## RSS / Atom

Discover the feed URL from the site's own page, then:

```python
import feedparser  # pip install feedparser, or parse XML with stdlib
feed = feedparser.parse("FEED_URL")
for e in feed.entries:
    print(e.get("published",""), e.get("title",""), e.get("link",""))
```

Check pagination/continuation, date coverage, and update timestamps. RSS items
are index entries — follow links for full posts; comments are unavailable.

## Acceptance

- Record the direct URL, title, author, publication date, and actual body read.
- Keep source discovery separate from body reading.
- Preserve per-page counts, duplicates, truncation, and captcha/network
  failures. Temp files in `/tmp/`.
