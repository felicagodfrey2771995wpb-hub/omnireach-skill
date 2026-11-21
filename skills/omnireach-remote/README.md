# omnireach-remote

Cloud/remote-safe subset of the local [omnireach](https://github.com/) skill —
the "A tier": credential-free internet research channels that work from any VM
or cloud agent, no browser/cookies/home IP required.

## What this is for

Run internet research from a phone-triggered cloud agent (e.g. a Devin Cloud
session started from the Devin mobile app) without depending on the home Mac
being online. Channels needing the user's logged-in browser or local files
(Xiaohongshu, Zhihu bodies, Douyin, Weibo, YouTube subs, local libraries, …)
are explicitly out of scope and report `requires_local_machine`.

## Layout

```
.devin/skills/omnireach-remote/
├── SKILL.md            # boundary + routing + runtime rules
├── references/         # per-channel commands & failure notes
└── scripts/            # stdlib-only Python CLIs (forum-cli, discourse-forum, zhihu-search)
```

Devin loads it automatically as a **project skill** when this repo is attached
to a cloud session (`/repo`). Other agents can point at the same directory.

## Optional secrets

`EXA_API_KEY`, `GH_TOKEN`, `ZHIHU_ACCESS_KEY`, `JINA_API_KEY` — set as cloud
org secrets; everything degrades gracefully without them (except Zhihu search,
which requires its key).
