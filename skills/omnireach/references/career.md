# Career and LinkedIn

LinkedIn tools vary by machine. First check `agent-reach doctor --json` and `mcporter list`; only call a registered LinkedIn tool, and inspect its current schema before using it. A profile read does not prove search is available.

Examples for a registered `linkedin` MCP server (confirm argument names from its live tool schema):

```bash
mcporter call 'linkedin.get_person_profile(linkedin_url: "https://linkedin.com/in/username")'
mcporter call 'linkedin.search_people(keyword: "AI engineer", limit: 10)'
mcporter call 'linkedin.search_jobs(keywords: "software engineer", location: "Remote", max_pages: 2)'
```

For public indexed material, a Jina/web query can be a fallback:

```bash
curl -s "https://r.jina.ai/https://linkedin.com/in/username"
```

Mark web-indexed results as indirect; login-required profiles, jobs, or posts remain `access-blocked` if they cannot be read. Inspect the tool's pagination and output limits, open relevant profile/job source pages, and record dates. Do not log in or message people as part of search.
