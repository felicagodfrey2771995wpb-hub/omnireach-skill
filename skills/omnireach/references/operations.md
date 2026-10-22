# Agent Reach setup, configuration, and maintenance commands

Use these commands to inspect capabilities and explain setup options. `doctor`, `version`, and `check-update` inspect state; `setup`, `configure`, `install`, `skill --install`, and uninstall commands change local state. Do not make those changes unless the user explicitly requests them. Run `agent-reach <command> --help` before relying on version-specific flags.

## Status and version

```bash
agent-reach doctor --json
agent-reach version
agent-reach check-update
agent-reach watch
```

`doctor` reports channel/backend hints and can leave platforms `warn`/`null` to avoid side effects or credential access. It does not search a query or verify a specific item. `check-update` checks for an upstream release; it does not update. `watch` combines a concise health and update check for a scheduled status task; creating a schedule is a separate user request.

## Configuration

Supported local configuration includes proxy, GitHub token, Groq/OpenAI transcription keys, Twitter/YouTube cookies, and XiaoHongShu cookies. Supply credentials through the hidden prompt or stdin mode where supported; never put secrets in shell history, process arguments, output, or progress files.

```bash
agent-reach configure --help
agent-reach configure groq-key
agent-reach configure openai-key
agent-reach configure proxy --stdin
```

Browser-cookie import has a restricted platform list and does not handle Twitter or XiaoHongShu; those use user-exported Cookie-Editor values when explicitly requested. Browser extraction reads an existing named browser/profile and should only be performed at the user's direction:

```bash
agent-reach configure --from-browser chrome --platform bilibili
agent-reach configure --from-browser chrome --platform youtube
agent-reach configure --from-browser chrome --platform xueqiu
```

Inspect the installed CLI help for accepted fields and constraints before configuration. Doctor's configured/installed status is not proof that a backend can retrieve content.

## Setup and install

```bash
agent-reach setup
agent-reach install --help
agent-reach install --dry-run
agent-reach install --env auto --safe
```

Setup is interactive. Install's safe mode checks and prints missing prerequisites. `--dry-run` previews a plan. `--system` explicitly permits system dependency, global tool, configuration, and skill installation; optional `--channels` selects channel dependencies. Installing tools, starting services, changing shell/profile/config files, registering skills, or accepting package downloads requires an explicit user request. Confirm runtime platform and actual installer's supported channel names first; do not infer a successful install from its plan.

## Formatting and skill registration

```bash
agent-reach format --help
cat /tmp/api-result.json | agent-reach format xhs
agent-reach skill --help
agent-reach skill --install
```

`format xhs` normalizes XiaoHongShu API JSON from stdin; it is not a search or read. `skill --install` registers the Agent Reach skill into supported client skill directories and changes local state. Prefer the existing unified skill library deployment flow when managing this shared skill.

## Destructive lifecycle commands

```bash
agent-reach uninstall --help
```

`uninstall` removes Agent Reach configuration/tokens and skill files unless `--keep-config` is selected. It is destructive and only runs on an explicit uninstall request after scope is clear; use `--dry-run` for an authorized preview. Never call it as a troubleshooting shortcut.
