# GitHub and developer research

Use the official `gh` CLI when installed. For unauthenticated access, public repository search/read may work; private content requires an existing session. `agent-reach doctor --json` and `gh auth status` have different side effects, so do not run auth checks that may change device state when the doctor deliberately avoids them. For broad public research, read actual repository documentation and relevant feedback.

```bash
gh search repos "query" --sort stars --limit 20
gh search code "query" --language python --limit 100
gh repo view OWNER/REPO
gh release list -R OWNER/REPO
gh issue list -R OWNER/REPO --state all --limit 100
gh issue view ISSUE_NUMBER -R OWNER/REPO
gh pr list -R OWNER/REPO --state all --limit 100
gh run list --repo OWNER/REPO --limit 100
```

Inspect `gh ... --help`, API response metadata, and page tokens. Command `--limit` controls returned rows and is not a statement that the repository or platform has no more matches. Use relevant follow-up queries for tool names, alternatives, maintenance, failures, pricing, and installation. Open source files and issue bodies; search cards/stars alone are not maintenance or user-feedback evidence.

Keep writes out of research. `gh repo clone`, fork, sync, issue creation, PR creation, release creation, and workflow dispatch modify state; use them only when the user explicitly requests those actions.
