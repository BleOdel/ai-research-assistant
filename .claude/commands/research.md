# /research - Source Discovery

Discovers sources on a topic via installed connector CLIs (arXiv, Semantic Scholar,
Google Scholar, OpenAlex, and any connectors added later via `/add-source`).
Deduplicates across runs and quick-triages by relevance.

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

Skip any skill whose `SKILL.md` does not document a `search` command - those are
utility skills, not source connectors (e.g. `paper-fetch`, which downloads full-text
PDFs for `/synthesize` and has nothing to search). Do not count a skipped utility
skill as a coverage gap in Step 5.

For each installed connector skill:

1. Read its `SKILL.md` for the correct `bun run …` invocation and supported flags.
2. Translate the topic into **one well-formed query** for that connector. Do not fire
   several differently-worded phrasings at the same connector to "cover more ground" -
   both arXiv and Semantic Scholar rate-limit on request volume, and a handful of
   query variants within a short window is the single most common way to trip that.
   If the first query's results genuinely look too narrow, try one broader
   reformulation - not three or four.

   **Query precision matters more than breadth.** The rubric filters sources *after*
   discovery, but a query that is too broad wastes the whole pipeline scoring noise.
   Aim at the *intersection* that defines the topic, not a single field-level term:
   "adversarial attacks on VR telemetry anomaly detection" is a topic, "AI security"
   is a field. A bare field name will match anything that mentions it in passing -
   a run on "AI security" in this repo returned CAPTCHA design from 2003, 6G network
   slicing, UAV backscatter localization, Kubernetes multi-tenancy and chess-agent
   alignment, none of which belong to any tracked research interest.

   Where a topic genuinely is a field-level scan, say so to the user and expect a
   lower hit rate - do not silently treat keyword matches as coverage.
3. Cap results to ~20 per call using the connector's limit flag.
4. Use `--format json` for machine-readable output.

It's fine to run the (at most one) query per *different* connector in parallel (e.g.
arXiv and Semantic Scholar at the same time) - the rate limits are per-connector, not
shared across them. Do not run multiple queries against the *same* connector in
parallel or back-to-back. Collect all `results` arrays into a single pool, tagged with
source connector (for Step 2 `detail` lookups).

If a CLI exits non-zero with `code: "RATE_LIMITED"`, **do not retry it** - the CLI has
already exhausted its own exponential backoff, so a manual retry or sleep loop will not
succeed where the built-in one didn't, and will just burn more time against a limit
that needs real wall-clock recovery (Semantic Scholar's unauthenticated pool is shared
globally and can take minutes to free up; a `SEMANTIC_SCHOLAR_API_KEY` env var moves it
to a dedicated per-key quota if this happens often). Instead: log it, fall back to the
other connectors or WebSearch for this query, and say so plainly in the Step 5 output -
do not silently under-report source coverage.

If a CLI exits non-zero with `code: "NO_API_KEY"` (currently only
`google-scholar-search`, which has no unauthenticated tier at all), treat that
connector as **unavailable for the rest of this run**, not just this one query - do
not retry it on a differently-worded query either, since the failure is permanent
until the user sets the key. Skip straight to the other connectors/WebSearch for the
topic and note in Step 5 that this connector was skipped for lacking a key.

Any other non-zero exit: log the error and continue - do not abort the whole search.

### 1c. WebSearch fallback

Use `WebSearch` for any connector whose CLI fails at runtime (including after a
`RATE_LIMITED` exit), or when bun is unavailable. Use the topic directly as the query,
appended with the connector's domain (e.g. `site:arxiv.org <topic>`) as a rough
substitute.

---

## Step 2: Fetch & Parse

For each promising result from Step 1, the CLI's search output already includes title,
authors, year, venue/category, and URL/ID. For sources worth a closer look, fetch full
detail with that connector's `detail` command (see its `SKILL.md` - do not guess flags)
to get the full abstract.

When fetching multiple `detail` calls against `semantic-scholar-search` in this step
(even with `SEMANTIC_SCHOLAR_API_KEY` set), space them at least one second apart - its
authenticated quota is a firm 1 request/second cumulative across search and detail
together, not a per-call allowance. `arxiv-search` and `google-scholar-search` don't
have this specific constraint documented, but the general "one call at a time per
connector" rule from Step 1b still applies to all three.

For every candidate:
- Skip if its DOI/arXiv ID/S2 paper ID/URL already exists in `seen_sources.json`

---

## Step 3: Quick Relevance Triage

Per `02-source-evaluation.md`'s **Quick Triage** section (title + abstract only, not
the full four-dimension rubric):

- **High**: Topic is clearly the paper's primary subject
- **Medium**: Topic is a plausible component, needs a closer read
- **Low**: Title matched but the abstract suggests a different focus

**If most results come back Low, the query is wrong, not the field.** Say so and
reformulate rather than storing a batch of keyword matches - every one of them will
otherwise be re-scored on later runs and clutter the subject index permanently.

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
      "source_connector": "arxiv-search | semantic-scholar-search | google-scholar-search | openalex-search",
      "first_seen": "YYYY-MM-DD",
      "relevance": "high/medium/low",
      "status": "new/skipped/ranked/unfetchable/synthesized",
      "subject": "<matched Research Interest name, or 'Uncategorized'>"
    }
  }
}
```

Set `subject` once per entry, per `05-subject-index.md`'s classification rules
(match the current topic against `01-researcher-profile.md`'s Research Interests).
Do not re-classify an existing entry on a later run.

### Step 4b: Regenerate the Subject Index

Regenerate `research/papers_by_subject.md` from the full, current contents of
`research/seen_sources.json` per `05-subject-index.md`'s file format - a full
rebuild, not an incremental patch.

`/rank` and `/synthesize` extend this schema additively: scored entries also carry
`scores` (the four-dimension breakdown), `overall_score`, `verdict` (one bare word:
`Core`/`Supporting`/`Peripheral`/`Excluded`), `rigor_basis` and `disclosure` (see
`02-source-evaluation.md`). `/rank` also adds `rank_date` and `impact_basis`. Do not
drop these fields when re-writing entries.

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

If any connector hit `RATE_LIMITED` and fell back to WebSearch (or was skipped
entirely), say so explicitly here - e.g. "Semantic Scholar was rate-limited for this
run; results below are arXiv + WebSearch only." Coverage gaps should be visible, not
silently absorbed.

After presenting, ask:
> "Want me to synthesize a report from any of these? Give me the numbers (or 'all') and
> I'll run `/synthesize`."

If this run found many new sources (roughly 8+), also suggest `/rank` - it
batch-scores all new sources against the full evaluation rubric and returns a ranked
shortlist, which beats eyeballing a long table. (`/rank` sets the `ranked` and
`unfetchable` status values in `seen_sources.json`; treat both as already-seen for
dedup purposes.)

---

## Important Rules

1. **Never fabricate a source.** Only present sources from actual CLI search/detail
   output or WebFetch/WebSearch results.
2. **Respect deduplication.** Always check `seen_sources.json` before presenting.
3. **Respect standing exclusions** from the researcher profile.
4. **Be efficient with detail fetches.** Pre-filter by title/abstract snippet before
   running `detail` on every hit.
5. **Parallel across connectors, not within one.** Different connectors can be queried
   at the same time; a single connector should see one query at a time, one topic at a
   time.
6. **Never hand-retry a `RATE_LIMITED` exit.** The CLI already backed off as far as it
   usefully can. Fall back per Step 1b/1c instead of looping.
7. **Never retry a `NO_API_KEY` exit at all, on any query.** It's not transient -
   skip that connector for the rest of the run.
