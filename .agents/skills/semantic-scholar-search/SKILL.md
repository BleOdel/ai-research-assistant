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

Search papers on Semantic Scholar via its public Graph API. No authentication, no API
key, **zero runtime dependencies** - runs with just `bun`.

Complements `arxiv-search`: Semantic Scholar indexes across all fields (not just
arXiv's CS/physics/math/stats coverage) and returns venue and citation-count data,
which arXiv's own API does not provide. Use it for the Rigor and Impact dimensions in
`02-source-evaluation.md`, and for topics outside arXiv's coverage.

## ⚠️ Rate limits

Unauthenticated Semantic Scholar traffic shares a small, tightly-limited request pool.
The CLI retries 429/5xx with exponential backoff, but **keep query volume low** -
avoid looping `detail` calls over long result lists; fetch detail only for sources
that survived a first relevance pass.

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
