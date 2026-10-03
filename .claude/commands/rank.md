# /rank - Triage Discovered Sources into a Ranked Shortlist

You are batch-scoring the sources that `/research` has collected, so the user can
decide where to spend `/synthesize` effort. `/research` finds and dedupes sources with
a cheap 3-tier triage; `/synthesize` scores and writes up one topic in depth. `/rank`
is the bridge: it runs the full four-dimension scoring on every new source and returns
a ranked shortlist, cheap enough to run after every `/research` batch.

`/rank` produces **triage scores**, not a finished synthesis. It scores from each
source's abstract/content and the researcher profile only - no fact-checking, no deep
detail fetches beyond what's needed to read the abstract, no LaTeX drafting.
`/synthesize`'s own Step 1 scoring remains authoritative and always re-runs when the
user actually synthesizes a report - `/rank`'s scores are a triage signal, not a
substitute.

Follow these steps **in order**.

---

## Step 0: Parse Input

`$ARGUMENTS` may contain:

- Nothing → rank all sources with status `new` in `research/seen_sources.json`
- A topic filter (e.g. `/rank keystroke inference`) → rank only sources whose stored
  title/topic context matches
- `--all` → re-rank every source that hasn't been synthesized yet, including
  previously-ranked ones (useful after the profile changes)
- `--top <N>` → shortlist size (default 5)

---

## Step 1: Load State

1. Read `research/seen_sources.json`. If the file is missing or has no entries, tell
   the user to run `/research` first and stop.
2. Select candidates: entries with status `new` (or all non-`synthesized` entries with
   `--all`), filtered by the topic filter if one was given.
3. If no candidates remain, say so ("Nothing new to rank - run `/research` to find
   fresh sources") and stop.
4. Read the scoring framework and profile **once**:
   - `.claude/skills/research-assistant/02-source-evaluation.md`
   - `.claude/skills/research-assistant/01-researcher-profile.md`

State how many sources will be ranked before proceeding.

---

## Step 2: Batch-Fetch and Score

Dispatch parallel `general-purpose` agents via the **Agent tool**, ~5 sources per
agent (a single agent is fine for ≤5 sources). Token-efficiency rules, consistent with
`/synthesize`:

- Pass each agent everything it needs **inline in the prompt** - the source list
  (title, authors, year, venue, url, source_connector) and the four-dimension rubric
  extracted from `02-source-evaluation.md` (scoring tables, weighting, thresholds). Do
  **not** make agents re-read the skill files.
- Agents fetch each source's full abstract via its connector's `detail` command
  (per that connector's `SKILL.md` - do not guess flags) and score **only from
  actually-fetched content**. If a source's `detail` lookup fails (dead id, connector
  rate-limited, `NO_API_KEY`), the agent marks that source `unfetchable` - it never
  scores from the title alone.
- If an agent's batch spans multiple sources from `semantic-scholar-search`, remind it
  in the prompt to space consecutive `detail` calls to that connector by at least one
  second (see that connector's `SKILL.md` - the authenticated quota is 1 request/second
  cumulative).
- Impact scoring follows `02-source-evaluation.md`'s connector fallback chain exactly
  (Semantic Scholar, then OpenAlex, then Google Scholar, then "insufficient data") -
  never default to 0, and do not drop a connector from the chain.

Each agent returns a JSON array, one object per source:

```json
{
  "key": "<the source's key in seen_sources.json>",
  "status": "scored" | "unfetchable",
  "scores": { "relevance": 0-100, "recency": 0-100, "rigor": 0-100, "impact": 0-100 or "insufficient data" },
  "rigor_basis": "<venue score, then each method adjustment applied and why, e.g. 'venue 68, +10 released artifact'>",
  "evidence_basis": "abstract" | "fulltext",
  "disclosure": "academic | industry | self-evaluating | vendor-report | unclear",
  "impact_basis": "<which connector's citation data was used, or null>",
  "notes": "1-2 bullets on any non-obvious score, grounded in the fetched abstract"
}
```

The honesty rule from `02-source-evaluation.md` applies here too: gaps are stated,
never smoothed over, and a source that looks prestigious by title but scores low on
Relevance gets a low score.

---

## Step 3: Aggregate and Rank

Back in the main context, for each scored source:

1. Compute the overall score and verdict with the state helper rather than by hand -
   it applies `02-source-evaluation.md`'s weights, the renormalization for Impact
   "insufficient data", and the verdict bands:
   ```bash
   python3 tools/state.py score --relevance R --rigor G --impact I --recency C
   ```
   (`--impact insufficient` when no citation data exists.) The Step 4 write computes
   the same values again and refuses any that disagree, so a hand-computed score
   cannot slip through.

Sort by overall score (descending). `unfetchable` sources go into a separate list, not
the ranking.

---

## Step 4: Update State

Write every result in **one** state-helper call - never edit the JSON directly:

```bash
python3 tools/state.py batch --file sources --json-file <scratch>/ranked.json
```

The input is `{"<key>": {fields}, ...}`; fields merge into the existing entries:

- Scored sources: `"status": "ranked"`, `"scores"`, `"rigor_basis"`, `"disclosure"`,
  `"evidence_basis"`, `"impact_basis"`, `"rank_date"` (ISO date).
  `evidence_basis` is `"abstract"` for a source scored from its fetched abstract -
  the normal case here - and `"fulltext"` only if the agent actually read the PDF.
  Omit `overall_score` and `verdict` - the helper computes both from `scores`.
- Unfetchable sources: `"status": "unfetchable"` with a `"note"` explaining why

The batch is all-or-nothing: if the helper refuses it, nothing was written - fix the
entries it lists and re-run.

Re-running `/rank` is idempotent: already-`ranked` sources are skipped unless `--all`
re-scores them.

The helper regenerates `research/papers_by_subject.md` as part of the same write.

---

## Step 5: Present the Shortlist

```
## Source Ranking - YYYY-MM-DD

Ranked <N> new sources (<X> shortlisted, <Y> below threshold, <Z> unfetchable).

### Shortlist

| # | Score | Verdict | Title | Year | Venue | |
|---|-------|---------|-------|------|-------|---|

### Why these ranked highest
**1. <Title> (<Score>)** - [1-2 notes from the agent's findings, grounded in the
fetched abstract]
[repeat for each shortlisted source]

### Below threshold
| Score | Verdict | Title | One-line reason |

### Unfetchable
- <Title> - <connector> failed: <reason>
```

Rules for the presentation:

- Every claim traces to a fetched abstract or the profile - no invented details.
- State explicitly that these are **triage scores from the abstract only**, and that
  `/synthesize` will re-score with full context (and fact-check every citation)
  before anything is drafted.
- Then ask: "Want to synthesize a report from any of these? Give me the number(s) (or
  a topic) and I'll start `/synthesize`."
- If the user picks source(s), run `/synthesize` on that topic, passing the triage
  verdict as prior context but **re-running the full Step 1 scoring** - triage never
  substitutes for it.

---

## Important Rules

1. **Never rank an unfetchable source.** A source whose abstract can't be retrieved is
   marked `unfetchable`, not guessed at from its title.
2. **Triage depth only.** No fact-checking, no LaTeX drafting, no deep multi-source
   cross-referencing - `/rank` exists to be cheap enough to run after every
   `/research` batch.
3. **Honest scoring.** Gaps are reported per source; a low-scoring source is presented
   as such even if its title sounds impressive. The bands and weights come from
   `02-source-evaluation.md` - if the user disagrees with a ranking, the fix is
   updating the profile or the framework, not bending scores.
4. **State stays additive.** `seen_sources.json` fields are only added, never
   restructured, so `/research`'s dedup keeps working.
5. **Respect connector rate limits.** Space out `semantic-scholar-search` `detail`
   calls within and across agent batches per its `SKILL.md`.
