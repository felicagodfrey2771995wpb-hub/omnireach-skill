# GitHub and developer research

Use the official `gh` CLI when installed; unauthenticated access covers public
repo search/read at low rate limits. `GH_TOKEN`/`GITHUB_TOKEN` (env only) raises
limits and unlocks private repos the token can see. Otherwise use plain REST:

```bash
gh search repos "query" --sort stars --limit 20
gh search code "query" --language python --limit 100
gh repo view OWNER/REPO
gh release list -R OWNER/REPO
gh issue list -R OWNER/REPO --state all --limit 100
gh issue view N -R OWNER/REPO
gh pr list -R OWNER/REPO --state all --limit 100
gh run list --repo OWNER/REPO --limit 100          # CI status / Actions runs
gh api repos/OWNER/REPO/actions/runs               # raw API equivalent
```

- `--limit` is a requested row count, not proof the repo has no more matches.
  Use follow-up queries (tool names, alternatives, maintenance, failures,
  pricing, install) to widen coverage.
- Search cards and stars are not maintenance or user-feedback evidence: open
  README/docs, issue and PR bodies.
- Keep writes out of research. `gh repo clone`, fork, issue/PR creation,
  release creation, and workflow dispatch modify state — only when the user
  explicitly asks.
