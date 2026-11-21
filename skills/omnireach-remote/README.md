# omnireach-remote

Cloud/remote-safe subset of the local `omnireach` skill — the "A tier":
credential-free internet research channels that work from any VM, cloud agent,
or Android phone (Termux), no browser/cookies/home IP required.

Channels needing the user's logged-in browser or local files (Xiaohongshu,
Zhihu bodies, Douyin, Weibo, YouTube subs, local libraries, …) are explicitly
out of scope and report `requires_local_machine`.

## Layout

```
skills/omnireach-remote/
├── SKILL.md            # boundary + routing + runtime rules
├── references/         # per-channel commands & failure notes
└── scripts/            # stdlib-only Python CLIs (forum-cli, discourse-forum, zhihu-search)
.devin/skills/omnireach-remote -> ../../skills/omnireach-remote   # Devin auto-discovery
install/termux-install.sh                                       # Android/Termux installer
```

## Devin Cloud

Attach this repo to a cloud session (`/repo`); Devin loads the skill
automatically via the `.devin/skills/` symlink.

## Android (Termux)

```bash
pkg install -y git gh bash
curl -fsSL https://raw.githubusercontent.com/felicagodfrey2771995wpb-hub/omnireach-skill/main/install/termux-install.sh | bash
```

(Private repo: the script runs `gh auth login` once.) Afterward:

```bash
forum-cli search v2ex "mac mini"
discourse-forum search archcn "keyword"
zhihu-search '{"query":"...","count":10}'   # set ZHIHU_ACCESS_KEY in skills/omnireach-remote/.env
```

## Optional secrets

`EXA_API_KEY`, `GH_TOKEN`, `ZHIHU_ACCESS_KEY`, `JINA_API_KEY` — env vars or the
`.env` file next to the skill. Everything degrades gracefully without them
(except Zhihu search, which requires its key).
