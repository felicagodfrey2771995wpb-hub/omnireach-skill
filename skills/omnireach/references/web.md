# Web pages, WeChat articles, RSS, and local WeChat cache

For broad research, follow [research-coverage.md](research-coverage.md): source discovery alone does not count as reading article bodies or incremental behavior.

## General web pages

```bash
curl -s "https://r.jina.ai/https://example.com/article"
```

Use Jina Reader for readable public pages. Verify that the response includes the expected article text, title, and author/date where available. A blank response, challenge page, or metadata-only output is not a successful read. Use a registered web-reader MCP only after confirming it exists with `mcporter list` and checking its schema.

## WeChat official account articles

### Search

Prefer a configured Exa query limited to `mp.weixin.qq.com`. This machine also has the `wechat-article-for-ai` helper:

```bash
~/.agent-reach/tools/wechat-article-for-ai/.venv/bin/python \
  ~/.agent-reach/tools/wechat-article-for-ai/wechat_search.py "query" 10
```

The local `wechat-search` script is a Sogou WeChat search adapter. Its `--page` is one requested page, and `--limit` is a per-command output cap (default 10), not a total. Check page progression and duplicates; captcha, antispider, empty parsed cards, and true zero-result pages are distinct outcomes. Resolve and preserve the original `mp.weixin.qq.com` URL when available. Search cards and snippets are discovery evidence, not article-body reads.

```bash
wechat-search "query" --page 1 --limit 10 --json --resolve
```

### Read article body

Use the installed Camoufox-based reader and inspect its output:

```bash
~/.agent-reach/tools/wechat-article-for-ai/.venv/bin/python \
  ~/.agent-reach/tools/wechat-article-for-ai/main.py "https://mp.weixin.qq.com/s/ARTICLE_ID" \
  -o /tmp/wechat-out --no-images
```

Remove `--no-images` when article images are part of the requested evidence. The reader uses its project virtual environment; system Python may lack dependencies. Jina and curl often hit WeChat verification; `miku_ai`/Sogou redirect is not a reliable article-body reader. Record challenge/empty output as access blocked or discovered-only according to what was actually read.

## Local WeChat data CLI

The installed `wx` CLI can query locally cached WeChat data. `wx biz-articles --help` shows it filters cached pushed articles by account/date, unread state, and a display limit (default 50); it is not a public web search or a full historical account archive.

```bash
wx biz-articles --account "ACCOUNT_NAME" --since YYYY-MM-DD --until YYYY-MM-DD --limit 100 --with-meta
```

This reads local chat/cache data. Use only when the user asks to search their local WeChat data, never as a substitute for public multi-platform research. Record cache freshness/source metadata when relevant. Do not run broad message history or export commands for public research.

## RSS / Atom

Discover a relevant source or author before fetching its feed. Parse all entries in scope and follow relevant links to read full content; `entries[:N]` is a command-side cap, not feed exhaustion.

```python
import feedparser
feed = feedparser.parse("FEED_URL")
for entry in feed.entries:
    print(entry.get("published", ""), entry.get("title", ""), entry.get("link", ""))
```

Check feed pagination/continuation, date coverage, and update timestamps. RSS entries generally have no comments; record that comment feedback is unavailable. A feed may contain only incremental/latest items and cannot establish historical backfill unless the source documents and returns that history.

## Acceptance

- Record the direct URL, title, author, publication date, and actual body/text read.
- Separate source discovery from body reading; keep RSS, local-cache, and public web data labeled by origin.
- Preserve per-page counts, duplicates, date coverage, output truncation, and captcha/network/access failures.
- Use `/tmp/` for temporary article outputs; keep secrets and unrelated local conversations out of research results.
