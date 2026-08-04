# /research - Source Discovery

Discovers sources on a topic via installed connector CLIs (arXiv, Semantic Scholar,
and any connectors added later). Deduplicates across runs and quick-triages by
relevance.

`$ARGUMENTS` is the topic (free text), e.g. `/research retrieval-augmented generation
for code search`. If empty, use the first Research Interest topic from
`01-researcher-profile.md` and confirm with the user before proceeding.

Follow these steps in order.

---

## Step 0: Load State

1. Read `research/seen_sources.json` (create if missing - start with `{"seen": {}}`)
2. Read `.claude/skills/research-assistant/01-researcher-profile.md` for the profile's
   standing exclusions and expertise level (informs query scoping, not yet full
   scoring - that's `/synthesize`'s job)

---

## Step 1: Search

**Use the installed connector CLIs as the primary search mechanism.** Fall back to
`WebSearch` only if `bun` is unavailable or a specific connector's CLI fails.

### 1a. Check bun availability

```bash
bun --version
```

If this fails, skip to **1c (WebSearch fallback)** for all connectors and note the
fallback in the Step 5 output.

### 1b. Run connector CLIs (primary - run in parallel where possible)

Discover all installed connector skills by reading every `SKILL.md` under
`.agents/skills/*/SKILL.md`. Each documents that connector's exact CLI flags. **Use
each connector's own documented interface - do not guess flags.** This automatically
includes any connector added later without requiring changes to this file.

For each installed connector skill:

1. Read its `SKILL.md` for the correct `bun run …` invocation and supported flags.
2. Translate the topic into that connector's query format.
3. Cap results to ~20 per call using the connector's limit flag.
4. Use `--format json` for machine-readable output.

Run all connector CLI calls in parallel where possible using the Agent tool. Collect
all `results` arrays into a single pool, tagged with source connector (for Step 2
`detail` lookups).

If a CLI exits non-zero, log the error and continue - do not abort the whole search.

### 1c. WebSearch fallback

Use `WebSearch` for any connector whose CLI fails at runtime, or when bun is
unavailable. Use the topic directly as the query, appended with the connector's domain
(e.g. `site:arxiv.org <topic>`) as a rough substitute.

---

## Step 2: Fetch & Parse

For each promising result from Step 1, the CLI's search output already includes title,
authors, year, venue/category, and URL/ID. For sources worth a closer look, fetch full
detail with that connector's `detail` command (see its `SKILL.md` - do not guess flags)
to get the full abstract.

For every candidate:
- Skip if its DOI/arXiv ID/S2 paper ID/URL already exists in `seen_sources.json`

---

## Step 3: Quick Relevance Triage

Per `02-source-evaluation.md`'s **Quick Triage** section (title + abstract only, not
the full four-dimension rubric):

- **High**: Topic is clearly the paper's primary subject
- **Medium**: Topic is a plausible component, needs a closer read
- **Low**: Title matched but the abstract suggests a different focus

---

## Step 4: Deduplicate & Store

Add ALL fetched sources (new and skipped) to `research/seen_sources.json`:

```json
{
  "seen": {
    "<doi_or_arxiv_id_or_s2_id_or_url>": {
      "title": "...",
      "authors": ["..."],
      "year": 2024,
      "venue": "...",
      "url": "...",
      "source_connector": "arxiv-search | semantic-scholar-search",
      "first_seen": "YYYY-MM-DD",
      "relevance": "high/medium/low",
      "status": "new/skipped/scored/synthesized"
    }
  }
}
```

`/synthesize` extends this schema additively: scored entries also carry `scores`
(the four-dimension breakdown), `overall_score`, and `verdict`. Do not drop these
fields when re-writing entries.

---

## Step 5: Present Results

```
## Source Discovery - <topic> - YYYY-MM-DD

Found X new sources (Y high, Z medium, W low relevance).

| # | Relevance | Title | Authors | Year | Venue | Link |
|---|-----------|-------|---------|------|-------|------|
| 1 | High | ... | ... | ... | ... | [Link](...) |

### High-Relevance Highlights
For each high-relevance source, add 1-2 bullets on why it matches the topic (from the
actually-fetched abstract, not the title).
```

After presenting, ask:
> "Want me to synthesize a report from any of these? Give me the numbers (or 'all') and
> I'll run `/synthesize`."

---

## Important Rules

1. **Never fabricate a source.** Only present sources from actual CLI search/detail
   output or WebFetch/WebSearch results.
2. **Respect deduplication.** Always check `seen_sources.json` before presenting.
3. **Respect standing exclusions** from the researcher profile.
4. **Be efficient with detail fetches.** Pre-filter by title/abstract snippet before
   running `detail` on every hit.
5. **Parallel searches.** Run connector CLI searches in parallel; use WebSearch only
   for gaps the CLIs don't cover.
