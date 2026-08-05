---
name: paper-fetch
version: 1.0.0
description: >
  Use this skill to download the full-text PDF of a specific paper for reading -
  when fact-checking a citation, when an abstract isn't enough to score a source,
  or when the user wants a paper read in depth. Takes an arXiv id, DOI, OpenAlex
  work id, or direct PDF URL; downloads open-access PDFs only. Invoke for: read
  the full paper, get the PDF, fetch full text, verify against the actual paper.
context: fork
allowed-tools: Bash(bun run .agents/skills/paper-fetch/cli/src/cli.ts *)
---

# paper-fetch

Downloads a paper's open-access PDF into the repo's full-text cache
(`research/fulltext/`, gitignored) so Claude can read the whole paper with the Read
tool instead of working from the abstract alone.

**This is a utility skill, NOT a search connector.** It has no `search` command -
`/research`'s connector discovery must skip it (see `research.md` Step 1b). It exists
to serve `/synthesize`'s scoring and fact-check passes, and direct "read this paper"
requests. `07-fulltext.md` in the research-assistant skill documents when to reach
for it.

## Commands

Run from the repo root:

```bash
bun run .agents/skills/paper-fetch/cli/src/cli.ts fetch <id|doi|url> [--force] [--out <dir>] [--format json|plain]
bun run .agents/skills/paper-fetch/cli/src/cli.ts resolve <id|doi|url> [--format json|plain]
```

- **`fetch`** resolves the identifier to an open-access PDF URL, downloads it,
  verifies the payload actually starts with the `%PDF` magic bytes (a publisher's
  HTML error page saved as `.pdf` would silently poison the cache), and writes it to
  `research/fulltext/<kind>-<id>.pdf`. Already-cached files are returned immediately
  (`"cached": true`) unless `--force`.
- **`resolve`** prints the PDF URL `fetch` would download, without downloading - use
  it to check whether an open-access copy exists before committing to a multi-MB
  transfer.

Accepted identifiers: arXiv ids (`2401.08998`, `cs/0601001v1`, or any
arxiv.org/abs|pdf URL), DOIs (bare `10.xxxx/yyyy` or doi.org URLs), OpenAlex work
ids (`W1234567` or openalex.org URLs), and direct URLs (downloaded as-is).

## Resolution behavior

- **arXiv ids** go straight to `arxiv.org/pdf/<id>` - no lookup call, always
  available.
- **DOIs / OpenAlex ids** are resolved through OpenAlex's single-work endpoint
  (free regardless of API key), preferring `best_oa_location.pdf_url`, then
  `primary_location.pdf_url`, then any location's `pdf_url`.
- **OA works with no direct PDF link**: observed in the wild (a genuinely
  open-access PLOS ONE paper with `is_oa: true` but `pdf_url: null` in every
  location) - in that case the OA landing URL is *attempted* and the magic-byte
  check arbitrates: some landing URLs serve the PDF directly; HTML ones fail with
  `NO_OA_PDF` and a message pointing at the landing page so the direct link can be
  found manually and passed back in as a URL.
- **Paywalled works** (not flagged OA at all) fail immediately with `NO_OA_PDF`.
  **This tool never scrapes paywalled publisher sites** - the honest response to a
  paywalled source is to score/fact-check from its abstract and say so in the
  report's evidence basis, not to route around the paywall.

## Error codes (stderr, exit 1)

- `BAD_ID` - input couldn't be classified; no network call was made
- `NO_OA_PDF` - no open-access PDF obtainable (paywalled, or OA-but-landing-page;
  the message says which). Not transient - do not retry the same id.
- `NOT_PDF` - a direct URL served something that isn't a PDF; nothing was cached
- `RATE_LIMITED` - built-in backoff exhausted (OpenAlex lookup or download). Do not
  hand-retry; arXiv ids never hit this on resolution since they skip the lookup.
- `FETCH_FAILED` / `RESOLVE_FAILED` - other errors (404, network), message has
  detail

## Cache

`research/fulltext/` is gitignored (enforced by `tools/security_guards.py`) - full
paper PDFs are copyrighted works and personal working data, never committed. Cache
filenames are deterministic per identifier (`arxiv-2401.08998.pdf`,
`doi-10.14722-ndss.2024.24100.pdf`), so repeated fetches across sessions hit the
cache. The Read tool reads the PDFs directly (up to 20 pages per request - read a
long paper in ranges).

## Setup

None. Zero runtime dependencies; `bun install` in `cli/` only pulls TypeScript dev
types for the typechecker. Optional `OPENALEX_API_KEY`/`OPENALEX_MAILTO` env vars
are passed through on OpenAlex lookups if set (single-work lookups are free
regardless).
