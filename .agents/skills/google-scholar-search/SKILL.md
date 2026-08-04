---
name: google-scholar-search
version: 1.0.0
description: >
  Use this skill whenever the user wants broad cross-publisher academic search
  (beyond arXiv's preprint-only coverage), needs a reliable citation count for a
  paper (Semantic Scholar's unauthenticated API is frequently rate-limited; this
  connector's citation counts come through consistently once configured), or wants
  to find papers that cite a specific work. Invoke for literature search, source
  discovery, citation impact, "what cites this paper", cross-disciplinary or
  non-CS research.
context: fork
allowed-tools: Bash(bun run .agents/skills/google-scholar-search/cli/src/cli.ts *)
---

# Google Scholar Search Skill

Search Google Scholar via [SerpApi](https://serpapi.com/google-scholar-api) (Google
Scholar itself has no public API and blocks direct scraping, so this goes through a
third-party proxy). Zero runtime dependencies beyond that - runs with just `bun`.

## ⚠️ Requires an account and API key - every request, no exceptions

Unlike `arxiv-search` and `semantic-scholar-search`, there is **no unauthenticated
tier at all**. Every request needs `SERPAPI_API_KEY` set. SerpApi's free tier is 250
searches/month at 50/hour throughput (paid tiers scale up from there) - see
[serpapi.com/pricing](https://serpapi.com/pricing). Sign up at
[serpapi.com/users/sign_up](https://serpapi.com/users/sign_up) and set:

```bash
export SERPAPI_API_KEY="your-key-here"
```

If the key is missing, the CLI fails immediately with `code: "NO_API_KEY"` and a
message pointing at signup - it does not attempt a request without one.

## When to use this skill

- Search for papers across all fields and publishers (not just arXiv's CS/physics/
  math/stats coverage) - useful for the researcher profile's non-CS-adjacent
  interests or any topic arXiv doesn't preprint well
- Get a citation count (`citedByCount`) for the Impact dimension in
  `02-source-evaluation.md` when Semantic Scholar is rate-limited or has no match
- Find papers that cite a specific work (`cited-by`) - neither of the other two
  connectors offers this

## Commands

### Search papers

```bash
bun run .agents/skills/google-scholar-search/cli/src/cli.ts search --query "<text>" [flags]
```

Key flags:
- `--query <text>` / `-q <text>` — free-text query. **Required.**
- `--year-from <year>` / `--year-to <year>` — bound the publication year.
- `--limit <n>` / `-n <n>` — cap results returned (client-side). Default 20.
- `--start <n>` — result offset, for pagination.
- `--format json|table|plain` — default `json`.

### Find papers that cite a given work

```bash
bun run .agents/skills/google-scholar-search/cli/src/cli.ts cited-by <cites-id> [flags]
```

`<cites-id>` comes from a prior `search` result's **`citedById`** field - it is a
different id than the result's own `resultId`, and is only present when Google
Scholar has indexed at least one citing work (otherwise it's `null`).

## Usage examples

```bash
# Papers on gaze-based side channels since 2023, in table form
bun run .agents/skills/google-scholar-search/cli/src/cli.ts search -q "gaze estimation side channel VR" --year-from 2023 --limit 15 --format table

# Papers citing a specific landmark work (id from that paper's own search result)
bun run .agents/skills/google-scholar-search/cli/src/cli.ts cited-by uNijGkgAAAAJ:abc123 --format table
```

## Output formats

| Format | Best for |
|--------|----------|
| `json` | Default — programmatic use, passing ids to `cited-by` |
| `table` | Quick human-readable scanning |
| `plain` | Reading a small result set with full author/venue detail |

All errors are written to **stderr** as `{ "error": "...", "code": "..." }` and the
process exits with code `1`. Distinct codes: `NO_API_KEY` (see above),
`RATE_LIMITED` (SerpApi throughput cap hit and retries exhausted - do not hand-retry,
fall back to another connector), `SEARCH_FAILED`/`CITED_BY_FAILED` (other errors).

## Notes

- **Year and venue are parsed, not structured fields.** Google Scholar's own API
  (via SerpApi) returns publication info as a loose string like `"A Author, B
  Author - Journal Name, 2020 - publisher.com"`, not separate year/venue fields.
  This connector extracts a plausible year and venue with a best-effort parser and
  returns `null` for either when it can't confidently extract one - never a
  guessed value. Treat a `null` venue as "not parseable," not "no venue."
- **`citedByCount` is `null`, not `0`, when Scholar has no citation data for a
  result** - do not treat a null as "zero citations" in `02-source-evaluation.md`'s
  Impact scoring.
- SerpApi's free-tier throughput (50/hour) is tighter than its monthly cap (250) -
  space out queries within a session the same way `/research`'s guidance already
  requires for the other two connectors.
