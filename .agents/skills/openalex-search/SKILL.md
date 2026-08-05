---
name: openalex-search
version: 1.0.0
description: >
  Use this skill whenever the user wants broad cross-publisher, cross-field academic
  search with no account required to start, needs a reliable citation count without
  Semantic Scholar's rate-limit problems, or is researching outside CS/physics/math
  (medicine, social science, humanities, any field) where arXiv has no coverage.
  Invoke for literature search, source discovery, citation counts, cross-disciplinary
  research, "how many times has this been cited".
context: fork
allowed-tools: Bash(bun run .agents/skills/openalex-search/cli/src/cli.ts *)
---

# OpenAlex Search Skill

Search [OpenAlex](https://openalex.org) (`api.openalex.org`), a fully open scholarly
index covering all fields and publishers. **No account required to start** - zero
runtime dependencies, runs with just `bun`.

Complements the other two connectors differently than they complement each other:
broader field coverage than arXiv (which is preprint-only, CS/physics/math/stats),
and a rate-limit model that doesn't share Semantic Scholar's documented
unauthenticated-pool problems (see that connector's own `SKILL.md`) - OpenAlex's free
allowance is per-caller, not a single global pool everyone fights over.

## ⚠️ Rate limits: a small free daily allowance, no account required

Unauthenticated requests get roughly **10 searches/day** (OpenAlex uses a
credit-metered system, not a simple requests/second cap - confirmed empirically
against the live API during this connector's development, not just from
documentation, which turned out to be necessary: an early doc fetch during
development returned an inaccurate summary of the auth model that a direct API call
immediately contradicted). **Fetching a single work by id/DOI (`detail`) is free
regardless of key** per OpenAlex's documented per-operation costs - prefer `detail`
over repeated `search` calls where possible.

**To raise the daily allowance ~100x:** set `OPENALEX_API_KEY` to a free key from
[openalex.org/settings/api](https://openalex.org/settings/api) - no payment required
for the free allowance. **Caveat:** this connector sends the key as an `api_key`
query parameter, inferred from OpenAlex's query-param-heavy API style (`search=`,
`filter=`, `mailto=` are all query params) - this could not be empirically verified
during development (doing so requires an OpenAlex account, which wasn't created for
this build). If requests with `OPENALEX_API_KEY` set still behave like the
unauthenticated tier, that's the first thing to check.

An optional `OPENALEX_MAILTO` env var (your email) is also supported as a courtesy
identifier, matching OpenAlex's older "polite pool" convention, though its effect
under the newer credit system is unclear.

## When to use this skill

- Search for papers across all fields and publishers - not just arXiv's CS/physics/
  math/stats coverage or what Semantic Scholar/Google Scholar happen to index well
- Get a citation count (`citedByCount`) for the Impact dimension in
  `02-source-evaluation.md`
- Fetch a paper's abstract by DOI or OpenAlex id, free of the daily search allowance

## Commands

### Search papers

```bash
bun run .agents/skills/openalex-search/cli/src/cli.ts search --query "<text>" [flags]
```

Key flags:
- `--query <text>` / `-q <text>` — free-text query. **Required.**
- `--year-from <year>` / `--year-to <year>` — bound the publication year.
- `--limit <n>` / `-n <n>` — cap results returned. Default 20 (max 100/request).
- `--page <n>` — 1-indexed page. Default 1.
- `--format json|table|plain` — default `json`.

### Fetch full paper detail (free of the search allowance)

```bash
bun run .agents/skills/openalex-search/cli/src/cli.ts detail <id|doi> [--format json|plain]
```

`<id|doi>` accepts an OpenAlex work id (`W4391725312`), a bare DOI
(`10.14722/ndss.2024.24100`), or a full `doi.org`/`openalex.org` URL.

## Usage examples

```bash
# Recent papers on a topic, in table form
bun run .agents/skills/openalex-search/cli/src/cli.ts search -q "keystroke inference virtual reality" --year-from 2022 --limit 15 --format table

# Full detail by DOI - free regardless of the daily search allowance
bun run .agents/skills/openalex-search/cli/src/cli.ts detail 10.14722/ndss.2024.24100 --format plain
```

## Output formats

| Format | Best for |
|--------|----------|
| `json` | Default — programmatic use, passing ids to `detail` |
| `table` | Quick human-readable scanning |
| `plain` | Reading a single paper's full detail (`detail` command) |

All errors are written to **stderr** as `{ "error": "...", "code": "..." }` and the
process exits with code `1`. Distinct codes: `RATE_LIMITED` (daily allowance
exhausted and retries gave up - do not hand-retry, fall back to another connector or
wait until the allowance resets), `NOT_FOUND`, `SEARCH_FAILED`/`DETAIL_FAILED`.

## Notes

- **Abstracts are reconstructed from an inverted index**, not stored as plain text
  (OpenAlex's own design, for copyright reasons) - this connector rebuilds plain text
  by placing each word at its indexed position. Verified against a real response
  during development, with one caveat worth knowing: OpenAlex's own source data
  occasionally merges a sentence-ending period into the next word as a single token
  (e.g. `"ecosystems.Previous"` observed directly in a live response) - this shows up
  as a missing space at some sentence boundaries in the reconstructed abstract. This
  is a data-quality characteristic of OpenAlex's own index, not a parsing bug in this
  connector, and is not "fixed" with guessed space-insertion (that risks breaking
  real abbreviations/acronyms) - read reconstructed abstracts with that in mind.
- **Venue can be `null` even when a human-readable name exists.**
  `primary_location.source` is sometimes `null` (observed on real Crossref-indexed
  records) even though `primary_location.raw_source_name` has the actual venue name -
  this connector falls back to `raw_source_name` when `source` is unavailable, rather
  than reporting no venue when one is genuinely known.
- `citedByCount` here is OpenAlex's own count, independently maintained from
  Semantic Scholar's or Google Scholar's - the three will not agree exactly (already
  observed in practice: 20 here vs. 36 on Semantic Scholar vs. 47 on Google Scholar
  for the same paper at the same point in time). Note which connector a citation
  count came from, per `02-source-evaluation.md`'s guidance, rather than treating
  them as interchangeable.
