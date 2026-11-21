# Academic papers (no key needed)

## arXiv

```bash
curl -s "https://export.arxiv.org/api/query?search_query=all:QUERY&start=0&max_results=10&sortBy=submittedDate&sortOrder=descending"
# by id / category / author:
#   search_query=cat:cs.CL+AND+all:keyword   id_list=2401.12345   au:Lastname
```

Atom feed with titles, authors, abstracts, dates. Follow `export.arxiv.org`
rate guidance (~1 request / 3 s). Abs page: `https://arxiv.org/abs/ID`; full
text: `https://arxiv.org/pdf/ID`.

## Semantic Scholar Graph API

```bash
curl -s "https://api.semanticscholar.org/graph/v1/paper/search?query=QUERY&limit=10&fields=title,abstract,year,authors,citationCount,externalIds,openAccessPdf"
curl -s "https://api.semanticscholar.org/graph/v1/paper/ARXIV:2401.12345?fields=title,abstract,citations.title,references.title"
```

Key-free light use; ~100 req / 5 min shared pool — back off on 429.

## OpenAlex

```bash
curl -s "https://api.openalex.org/works?search=QUERY&per-page=10&mailto=you@example.com"
curl -s "https://api.openalex.org/works/doi:10.1234/example"
```

Free, no key; `mailto` param puts you in the polite pool. Good for venue,
institution, citation-graph questions.

## Rules

- A search hit is an index entry; read the abstract/body (or the arXiv PDF)
  before citing content.
- Record venue, year, and whether the version read is a preprint.
