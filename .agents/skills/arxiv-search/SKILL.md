---
name: arxiv-search
version: 1.0.0
description: >
  Use this skill whenever the user wants to search for academic papers or preprints
  on arXiv, or look up a specific arXiv paper's abstract/metadata. Invoke for
  literature search, source discovery, "find papers on X", "what's on arXiv about Y",
  state-of-the-art research in CS/physics/math/stats-adjacent fields.
context: fork
allowed-tools: Bash(bun run .agents/skills/arxiv-search/cli/src/cli.ts *)
---

# arXiv Search Skill

Search papers on arXiv via its public Export API. No authentication, no API key,
**zero runtime dependencies** - runs with just `bun`.

## When to use this skill

- Search for papers matching a topic, optionally scoped to an arXiv category and/or
  submission date
- Get the full abstract and metadata for a specific paper by its arXiv id

## Commands

### Search papers

```bash
bun run .agents/skills/arxiv-search/cli/src/cli.ts search [flags]
```

At least one of `--query`, `--category`, or `--since` is required.

Key flags:
- `--query <text>` / `-q <text>` — free-text query, matched against title/abstract/
  authors/etc.
- `--category <code>` / `-c <code>` — an arXiv category, e.g. `cs.LG`, `cs.CL`,
  `stat.ML`. See https://arxiv.org/category_taxonomy for the full list.
- `--since <YYYY-MM-DD>` — only papers submitted on or after this date.
- `--sort <mode>` — `relevance` (default) or `date`.
- `--limit <n>` / `-n <n>` — max results. Default 20.
- `--start <n>` — result offset, for pagination.
- `--format json|table|plain` — default `json`.

### Fetch full paper detail

```bash
bun run .agents/skills/arxiv-search/cli/src/cli.ts detail <id|abs-url> [--format json|plain]
```

`id` is the arXiv id from `search` results (e.g. `2301.12345` or `2301.12345v2`). A
full `arxiv.org/abs/...` URL also works. Returns the full abstract plus comment,
journal reference, and DOI when arXiv has them.

## Usage examples

```bash
# Recent RAG papers in the NLP category
bun run .agents/skills/arxiv-search/cli/src/cli.ts search -q "retrieval augmented generation" -c cs.CL --sort date --limit 15 --format table

# Everything in cs.LG since a given date
bun run .agents/skills/arxiv-search/cli/src/cli.ts search -c cs.LG --since 2024-06-01 --format table

# Full detail on a specific paper
bun run .agents/skills/arxiv-search/cli/src/cli.ts detail 2301.12345 --format plain
```

## Output formats

| Format | Best for |
|--------|----------|
| `json` | Default — programmatic use, passing ids to `detail` |
| `table` | Quick human-readable scanning |
| `plain` | Reading a single paper's full detail (`detail` command) |

All errors are written to **stderr** as `{ "error": "...", "code": "..." }` and the
process exits with code `1`.

## Notes

- Data is from arXiv's public Export API — no credentials required.
- arXiv is preprint-only: results carry no peer-review signal by themselves. Combine
  with `semantic-scholar-search` for citation counts and venue information, or note the
  preprint status explicitly per `02-source-evaluation.md`'s Rigor dimension.
- The API asks integrators to be considerate of request volume; the CLI retries
  429/5xx with exponential backoff, but keep batch sizes reasonable.
