# Forums and communities (credential-free routes)

Two stdlib-only CLIs ship with this skill; run them with `python3` from the
skill directory (or via their absolute path in the repo). Exit codes:
`0` ok · `1` usage/HTTP error · `75` access-blocked (WAF/403/401/503) —
**blocked, not empty**.

## forum-cli — six non-Discourse communities

```bash
python3 scripts/forum-cli/forum_cli.py sites                      # list site keys
python3 scripts/forum-cli/forum_cli.py search v2ex "QUERY" [--page N]
python3 scripts/forum-cli/forum_cli.py post v2ex "TOPIC_URL" [--page N]
```

| Site key | Community | Notes |
|---|---|---|
| `v2ex` | V2EX | Search via SoV2EX index (first posts only). Chinese titles yield slug-less URLs; bare id works. Reply/floor bodies not readable (CF-403 site policy) — reply counts come from the public page. |
| `nodeseek` | NodeSeek | Search + body verified 2026-10. |
| `ubuntucn` | Ubuntu 中文论坛 | "Search" filters homepage lastpost titles locally — NOT native full-text search; label it. |
| `enshan` | 恩山无线论坛 | Topic bodies read anonymously; **site search requires login** — CLI exits 75 ("游客无法搜索"); use indexed web search for discovery. |
| `linuxorg` | Linux.org (XenForo) | Intermittently Cloudflare-blocked even for real users; a 75 is the site's WAF, retry later before declaring down. |
| `osdev` | OSDev.org | Whole site behind Cloudflare challenge (403 on everything, incl. robots.txt) even for browsers sometimes — falls back to indexed search, marked indirect. |

## discourse-forum — any Discourse site

```bash
python3 scripts/discourse-forum search archcn "QUERY"
python3 scripts/discourse-forum topic archcn TOPIC_ID
python3 scripts/discourse-forum latest nixos
python3 scripts/discourse-forum categories itsfoss
```

Built-in keys: `nixos` (discourse.nixos.org), `archcn` (forum.archlinuxcn.org),
`ubuntu` (discourse.ubuntu.com), `itsfoss` (itsfoss.community), `linuxdo`
(linux.do — usually needs cookies; see below). Any other Discourse host: pass
the base URL directly.

**linux.do in this environment:** anonymous access covers `latest_topics`,
`top_topics`, `category_topics`, `get_topic`, `list_tags`, `list_categories`;
`search` returns 403 "You need to be logged in" (Discourse site gate — that's
local-machine-only). Repeated anonymous reads can still trip a Cloudflare
challenge — send one request at a time.

## Reddit — Arctic Shift archive (no login)

```bash
# posts in a subreddit, real pagination via before/after (unix ts)
curl -s "https://arctic-shift.photon-reddit.com/api/posts/search?subreddit=SUB&after=30d&limit=25"
# nested comment tree for a submission
curl -s "https://arctic-shift.photon-reddit.com/api/comments/tree?link_id=t3_ID&limit=500"
```

- Archive, not live — scores are ~36 h backfilled. Label it
  `arctic-shift-archive`.
- No site-wide keyword search: it indexes by subreddit/author. For discovery
  without a known subreddit, use host web search `site:reddit.com` (indirect),
  then read the matching subreddit's archive.
- Reddit's own JSON/RSS endpoints answer 403 to datacenter IPs — do not treat
  a reddit.com 403 as "no results".

## Indexed fallback

When a community's direct route is blocked or unverified, use
`site:domain` indexed web search, mark it `indirect`, and record which reader
failed, when, and with what exact error.
