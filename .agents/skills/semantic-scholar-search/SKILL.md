---
name: semantic-scholar-search
version: 1.0.0
description: >
  Use this skill whenever the user wants to search for academic papers across any
  field (not just arXiv-covered ones), needs citation counts or venue/impact signal,
  or wants to look up a specific paper by DOI/arXiv id/Semantic Scholar id. Invoke
  for literature search, source discovery, citation impact, "how influential is this
  paper", cross-disciplinary research (medicine, social science, humanities, etc).
context: fork
allowed-tools: Bash(bun run .agents/skills/semantic-scholar-search/cli/src/cli.ts *)
---

# Semantic Scholar Search Skill

Search papers on Semantic Scholar via its public Graph API. No authentication
required, **zero runtime dependencies** - runs with just `bun`. An optional free API
key raises the rate limit (see below).

Complements `arxiv-search`: Semantic Scholar indexes across all fields (not just
arXiv's CS/physics/math/stats coverage) and returns venue and citation-count data,
which arXiv's own API does not provide. Use it for the Rigor and Impact dimensions in
`02-source-evaluation.md`, and for topics outside arXiv's coverage.

## ⚠️ Rate limits

Unauthenticated Semantic Scholar traffic shares **one small pool across every
unauthenticated caller globally** - not a per-user limit. This means a `429` can
happen even on the very first request of a session; it is not necessarily a sign this
CLI is being over-used. The CLI retries with exponential backoff, and if every retry
is exhausted it exits with **`code: "RATE_LIMITED"`** and a message explaining the
situation - do not hand-retry or sleep-loop on that exit, since the CLI has already
backed off as far as usefully possible. Fall back to `arxiv-search` or `WebSearch` for
that query instead (`/research`'s Step 1b covers this).

**To reduce how often this happens:** set the `SEMANTIC_SCHOLAR_API_KEY` environment
variable to a free key from
[semanticscholar.org/product/api](https://www.semanticscholar.org/product/api). The
CLI sends it as the `x-api-key` header automatically when present, moving traffic onto
a dedicated per-key quota instead of the shared pool.

**With a key, the quota is a firm 1 request/second, cumulative across every S2
endpoint** (a `search` followed immediately by a `detail` call counts as two
requests against the same 1/sec budget, not one each). A single CLI invocation is
always within that budget on its own - the requirement is on whoever *sequences*
multiple invocations: `/research` and `/synthesize` must space consecutive calls to
this connector by at least one second, the same "one query at a time, no
back-to-back calls to the same connector" rule they already apply for the
unauthenticated case, just now with a precise number behind it instead of a vague
"keep volume low."

Also **keep query volume low** generally - avoid looping `detail` calls over long
result lists; fetch detail only for sources that survived a first relevance pass.

## When to use this skill

- Search for papers matching a topic, optionally filtered by year range or venue
- Get citation count, influential-citation count, venue, and full abstract for a
  specific paper by Semantic Scholar id, DOI, arXiv id, or PubMed id

## Commands

### Search papers

```bash
bun run .agents/skills/semantic-scholar-search/cli/src/cli.ts search --query "<text>" [flags]
```

Key flags:
- `--query <text>` / `-q <text>` — free-text query. **Required.**
- `--year-from <year>` / `--year-to <year>` — bound the publication year.
- `--venue <name>` — filter by venue name (exact match per S2's API).
- `--limit <n>` / `-n <n>` — max results. Default 20 (S2 caps at 100/request).
- `--offset <n>` — result offset, for pagination.
- `--format json|table|plain` — default `json`.

### Fetch full paper detail

```bash
bun run .agents/skills/semantic-scholar-search/cli/src/cli.ts detail <id> [--format json|plain]
```

`id` is a Semantic Scholar paper id from `search` results, or a prefixed external id:
`arxiv:2301.12345`, `doi:10.1234/x`, `pubmed:12345`. Returns the full abstract plus
venue, citation count, and influential-citation count.

## Usage examples

```bash
# Papers on graph neural networks since 2022, in table form
bun run .agents/skills/semantic-scholar-search/cli/src/cli.ts search -q "graph neural networks" --year-from 2022 --limit 15 --format table

# Filter to a specific venue
bun run .agents/skills/semantic-scholar-search/cli/src/cli.ts search -q "protein folding" --venue "Nature" --format table

# Full detail by arXiv id (cross-reference with arxiv-search results)
bun run .agents/skills/semantic-scholar-search/cli/src/cli.ts detail arxiv:2301.12345 --format plain
```

## Output formats

| Format | Best for |
|--------|----------|
| `json` | Default — programmatic use, passing ids to `detail` |
| `table` | Quick human-readable scanning, sorted by whatever `search` returned |
| `plain` | Reading a single paper's full detail (`detail` command) |

All errors are written to **stderr** as `{ "error": "...", "code": "..." }` and the
process exits with code `1`.

## Notes

- Data is from Semantic Scholar's public Graph API — no credentials required.
- A `null` `venue` field means the paper has no indexed venue (commonly a preprint) -
  treat this as a signal for `02-source-evaluation.md`'s Rigor dimension, not a parse
  failure.
- `citationCount` and `influentialCitationCount` feed the Impact dimension. A paper
  found only via `arxiv-search` with no Semantic Scholar match should be scored
  "insufficient data" on Impact, not defaulted to 0 - cross-check by arXiv id via
  `detail arxiv:<id>` before concluding there's no match.
