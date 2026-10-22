# Video and podcast search, reading, comments, transcription

For broad research, follow the query, pagination, publication-date, transcript, comment, and evidence rules in [research-coverage.md](research-coverage.md). Result titles and metadata are discovery evidence only.

## YouTube

### Search and metadata

```bash
yt-dlp --dump-json "ytsearch20:query"
yt-dlp --dump-json "https://www.youtube.com/watch?v=VIDEO_ID"
```

`ytsearchN` requests a fixed number of results; it is not a page-completion signal. Save all returned metadata and use additional intent-preserving queries. Record title, URL, publication/upload date when available, channel, and duration.

**A session is required on this machine.** Without one, every player call answers `Sign in to confirm you're not a bot`; with `--cookies-from-browser chrome` the same call succeeds. The wrapper below adds the cookie, a PO token provider, and a restart-and-retry path for the bot gate:

```bash
<skill-root>/scripts/yt --search "query" -n 5
```

Verified: three real videos with title, channel, upload date, duration, view count, and id. Limits to record: `ytsearchN` is linear with **no stable public page cursor** (only the official Data API has token pagination, and it needs a Cloud project plus key), and Chinese-language queries returned zero results here — a corpus fact, not a tool failure. The official Data API route is the documented preference in [search.md](search.md); this CLI route needs no API key and is the practical fallback.

### Subtitles and transcripts

```bash
yt-dlp --write-sub --write-auto-sub --sub-lang "zh-Hans,zh,en" --skip-download -o "/tmp/%(id)s" "URL"
```

Read the created `.vtt` file and verify it contains actual transcript text. If the request fails, subtitles are empty, or no file was created, use a verified OpenCLI transcript command (`opencli youtube transcript "URL" -f yaml`) when installed. Retry a transient empty caption response up to three times. If no transcript is available, `agent-reach transcribe "URL"` is the audio-transcription fallback. A `doctor` check or exit status alone is not transcript verification. Auto-generated captions may contain repeated lines; retain the source transcript and note cleanup.

**Distinguish four different failures before concluding "no subtitles" (verified 2026-10-19).**

| Symptom | Cause | Action |
|---|---|---|
| `--list-subs` lists auto-caption tracks | captions **exist** | continue to the body |
| `Sign in to confirm you're not a bot` | no session | add `--cookies-from-browser chrome` |
| timedtext answers **HTTP 200 with an empty body** (base URL carries `ip=0.0.0.0` and `sparams=ip,...`) | **missing PO token** | run a PO token provider |
| `RequestBlocked: ... blocking requests from your IP` (library route) | IP reputation | switch route, do not loop |

A real browser page without a PO token also receives an empty body, so this is a platform requirement rather than a client defect. The working local stack is `scripts/yt` (wrapper), `tools/bgutil-pot/` (PO token server, `POST /get_pot` on 127.0.0.1:4416 — a GET returns 404), and `tools/yt-dlp-venv/` (yt-dlp plus the provider plugin). The server caches tokens in memory, so a cached bad token makes every retry fail: the wrapper restarts the server between attempts, which moved the observed success rate from 2/3 to 4/4.

```bash
<skill-root>/scripts/yt --video VIDEO_ID --subs --out /tmp/ytout/
```

For a check that leaves no subtitle file behind, use `--print-subs`: it prints the caption text to stdout through a self-deleting temp directory.
```bash
<skill-root>/scripts/yt --video FwOTs4UxQS4 --print-subs | head -20
```
`FwOTs4UxQS4` (Jeff Su, *AI Agents, Clearly Explained*, 10:07) is the reproducible fixture for this check: it yields an English auto-caption track of ~1,480 lines. For search, prefer `--compact` (one line per result, ~260 B) over the default JSON dump, which is tens of MB — pass `--compact` whenever you only need a result list, and do not pipe the default dump into another command. A bot-gate response is retried with the provider restarted; if the cookie count in the log is far below ~1,500, the Chrome cookie DB was read partially and the retry may keep failing — re-run once the browser is idle.

Verified output: `en.vtt` + `en-orig.vtt` (86,279 B each), 742 lines / 57,780 characters of real transcript matching the video's topic. A PO token provider needs a local Node server; keep it bound to loopback. See [session-model.md](session-model.md).

### Comments

Use Agent Reach's browser-free InnerTube fallback, rather than `yt-dlp --write-comments`:

```bash
agent-reach yt-comments "URL_OR_VIDEO_ID" --limit 20
agent-reach yt-comments "URL_OR_VIDEO_ID" --limit 20 --order newest
```

The current command makes two InnerTube JSON POST requests and returns one batch of top-level comments, with `top` or `newest` ordering. There is no pagination option in the installed CLI; `--limit` is an output cap. It does not fetch complete comment history or child replies. An empty list with exit code zero can mean no visible comments; verify the target and record the result rather than retrying indefinitely. It is an unofficial web-client route, not the YouTube Data API. Recent comments and replies are evidence samples, not exhaustive discussion coverage.

`yt-dlp --write-comments` is an unreliable fallback: its player clients can be blocked by YouTube's IP reputation checks. Keep `yt-dlp` for metadata and subtitle retrieval.

### Transcription and configuration

```bash
agent-reach transcribe "https://www.youtube.com/watch?v=VIDEO_ID"
agent-reach transcribe ./local_audio.mp3 --output /tmp/transcript.txt
agent-reach transcribe "URL" --provider groq
agent-reach transcribe "URL" --provider openai
```

`transcribe` accepts a public HTTP(S) media URL or local audio file. Configure a provider only when the user requests setup: `agent-reach configure groq-key` or `agent-reach configure openai-key` (hidden input). `auto` uses the first configured provider and stops on failure. `--allow-provider-fallback` allows the same audio to be sent to another configured provider and may incur a charge; disclose the data-sharing/provider change and only use it when the user has asked for that fallback. Do not print keys.

## Bilibili / B站

Route table and sandbox caveats: [channel-routing-cheatsheet.md](channel-routing-cheatsheet.md).

Use `bili` as the Bilibili search primary for search, hot/rank lists, video metadata, and audio. Search, detail, subtitles, and comments are separately verified capabilities. `yt-dlp` supports `bilisearchN:QUERY`, but this machine returned HTTP 412 on 2026-10-14; keep it as a conditional fallback only after environment changes. After a 412, stop retrying and switch to the verified OpenCLI browser search. If that fails, use Exa `site:bilibili.com/video` as indirect web search and label the method.

```bash
bili search "query" --type video --page 1 -n 42 --page-info --json
bili video BV_ID
bili hot -n 20
bili rank -n 20
bili audio BV_ID
OPENCLI_BROWSER_COMMAND_TIMEOUT=60 opencli bilibili search "query" --type video --page 1 --limit 20 -f json
opencli bilibili subtitle BV_ID -f yaml
opencli bilibili video BV_ID -f yaml
```

`--page-info` preserves full raw upstream rows and reports page size, the API-reported result window (not total site-wide videos), page count, invalid/no-BV cards, per-page duplicates, and `-n` truncation. Its `has_next_page` signal comes from the API page metadata. Request pages individually, deduplicate by BV ID across pages, and record the actual stopping reason. A successful search does not prove detail, subtitle, or comment access; preserve each endpoint's result independently. Do not repeatedly retry a stable access-control response.

### Comments and replies

Preferred route is OpenCLI. First inspect `opencli bilibili comments --help -f yaml` for the installed adapter's exact argument names and caps:

```bash
opencli bilibili comments BV_ID -f json --limit 30
opencli bilibili comments BV_ID --parent RPID -f json --limit 30
opencli bilibili comments BV_ID --top -f json
```

If OpenCLI comments are unavailable, the installed Agent Reach fallback calls Bilibili's web API directly and does not need a browser or login:

```bash
agent-reach bili-comments BV_ID --limit 50 --pages 1
agent-reach bili-comments BV_ID --parent RPID --limit 50
agent-reach bili-comments BV_ID --mode 2 --limit 50 --pages 1
```

The fallback accepts a BV ID, URL, or numeric aid. It returns at most 50 rows per command. Main-floor pagination is capped by the explicitly requested `--pages` value (default 1); inspect each response/cursor and issue subsequent bounded calls when appropriate. Child replies use a separate endpoint and page sequence; request each parent explicitly. Neither the default command nor one call reads every comment. The fallback uses WBI signing and a public API; HTTP 412/-352 or signature failures should be reported after the documented retry path, not looped. A confirmed empty list is valid zero-comment evidence, not a failure.

For deep community analysis, inspect selected comment threads, not just pinned/top comments; record the query, order, pages, counts, and any unexpanded reply trees.

**Patched client and login gate (verified 2026-10-19).** The public `tamnd/bilibili-cli` v0.3.0 cannot paginate the main floor: it stops on the top-level `cursor.is_end`, never passes `--page` into `CommentOptions`, and treats a skipped first page as "no new records". A patched build (source under `tools/bilibili-comments/src/bilibili-cli/`, original binary kept as `.orig-bili-comments-candidate-unpatched-v0.3.0`) fixes all three. Main-floor pagination is also login-gated: 1 top-level comment anonymously versus 157 with the Chrome session, 488 nested replies, and every `reply_count` matched.

```bash
<skill-root>/scripts/bili-comments comments BV_ID --order time --replies -o Json -q --no-cache
<skill-root>/scripts/bili-comments comments BV_ID --order time --page 2 -n 20 -o Json -q --no-cache
```

The Go side parses only the **classic 7-field Netscape cookie format**; a modern 10-field file is read as one garbage cookie string. The wrapper handles that and deletes its temp file after the run. Report anonymous and logged-in results as separate capabilities.

### Audio transcription

If no usable subtitle exists, `bili audio BV_ID` can export audio for transcription. Inspect its actual output path, then run `agent-reach transcribe /path/to/audio.wav`. Verify non-empty transcript text. Keep generated audio/transcript in `/tmp/` unless the user requests a saved deliverable.

## Xiaoyuzhou / 小宇宙

Discover a relevant episode or RSS/feed source first. The installed local helper can transcribe a known episode URL:

```bash
~/.agent-reach/tools/xiaoyuzhou/transcribe.sh "https://www.xiaoyuzhoufm.com/episode/EPISODE_ID"
```

It requires `ffmpeg` and a configured Groq key. An optional `--polish` pass makes an additional provider call for punctuation/paragraphs. The helper is not a podcast search index: locate the episode through a direct feed/search first, then verify the resulting transcript. Do not install dependencies or configure a key unless requested.

## Successful read criteria

- Search: actual result items with URLs/IDs, not an empty page or a success message.
- Transcript: non-empty text read from the subtitle/transcription output.
- Comments: actual comment bodies and known page/batch limits; empty arrays recorded as a valid result only after target access is confirmed.
- Pagination: inspect each available page/cursor, retain every returned row, and record the terminal page, platform cap, or access block. Never present the command's `--limit` as the platform's total.
