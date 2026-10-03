# /update - Living-Document Refresh of an Existing Report

Re-runs discovery for a topic that already has a synthesized report, and instead of
drafting a fresh report, merges what's new into the existing one: body revised in
place, a dated Revision History entry recording what changed and why. The merge
rules live in `.claude/skills/research-assistant/08-living-updates.md` - read that
file once at the start of every run.

`$ARGUMENTS` is the topic slug matching an existing `reports/<topic_slug>/`
directory (same matching behavior as `/defend`: exact or unambiguous partial match
proceeds, ambiguity asks, no match lists what's available).

Follow these steps in order.

---

## Step 0: Match the Report & Establish the Baseline

1. Match `$ARGUMENTS` against `reports/*/`. No report for the topic → this command
   has nothing to update; point to `/research` + `/synthesize` and stop.
2. Read the existing `report.tex` and `references.bib` fully - the whole run merges
   into these, and Step 3's impact classification needs the actual current claims,
   not a memory of them.
3. Establish the **baseline date** (when the report was last current), checking in
   order: `research_tracker.csv`'s row for this topic (`last_event_date` /
   `date_synthesized`) if the file exists; the report's own metadata block (its
   search-scope date is required by `03-report-templates.md`); the most recent
   `\paragraph{YYYY-MM-DD}` in an existing Revision History section. If none of
   these yields a date, ask the user.
4. Read `.claude/skills/research-assistant/08-living-updates.md` (merge rules) and
   `02-source-evaluation.md` (scoring - if not already in context).

---

## Step 1: Re-Discover

Run `/research`'s Steps 0-4 for the topic (`.claude/commands/research.md` - connector
discovery, one well-formed query per connector, RATE_LIMITED/NO_API_KEY handling,
dedup, storage - all identical). Two update-specific adjustments:

- Where a connector supports date filtering (`--year-from`), set it to the baseline
  year - dedup against `seen_sources.json` is the real filter for anything finer
  than year granularity, since every source considered for the original report is
  already recorded there.
- The interesting output is **new-since-baseline sources only**. Already-seen
  sources drop out via dedup as usual - which is why Step 1b exists.

### Step 1b: Scored but Never Merged

Dedup treats every source already in `seen_sources.json` as not new, including one
that was scored Core for this report and then never carried into it - so no later
`/update` would offer it again. (This happened: three Core sources ranked on
2026-08-26 stayed out of the prompt-injection report through two updates while its
prose named one of them about 30 times.) List them alongside re-discovery:

```bash
python3 tools/state.py unmerged --subject "<subject>" --bib reports/<topic_slug>/references.bib
```

`<subject>` is the report's Research Interest: the `subject` column of its
`research_tracker.csv` row if there is one, otherwise the interest this topic
classifies under per `05-subject-index.md` (the same match `/research` Step 4 makes).
The helper lists every `ranked` Core/Supporting entry under that interest that the
`.bib` does not cite, matching on DOI, arXiv id or URL however each side spells them.

The list covers the whole Research Interest, not just this topic, so triage it by
title and stored scores: on-topic entries join the new sources as **merge
candidates** in Step 2; the rest were ranked for other topics under the same
interest - count them in one line, never skip them silently. An entry that looks
on-topic but turns out to be cited under an identifier the helper could not match
(e.g. the `.bib` has only the venue DOI and state only the arXiv URL) is not a
candidate - say which `.bib` key covers it.

If discovery finds nothing new **and** Step 1b has no on-topic candidates: say so
plainly, update the report's metadata-block search-scope date (the "checked through"
date moving forward IS information), add no Revision History entry (nothing
changed), and stop - do not pad an update out of nothing. Recompile only if the
metadata line changed.

---

## Step 2: Score the New Sources

Full four-dimension scoring per `02-source-evaluation.md` for each new source and
each Step 1b candidate, with full text via `paper-fetch` where a score turns on
something the abstract doesn't state (per `07-fulltext.md` - same as `/synthesize`
Step 1). A Step 1b candidate's stored score may be `/rank`'s abstract-only triage or
an older `/synthesize` scoring, so it is a prior, not a substitute. Present one
scoring table with Step 1b candidates marked as previously ranked (and their
`rank_date`), plus a one-line reminder of the report's current headline conclusion,
and ask:

> "Merge the Core/Supporting sources into the report? Reply yes, or tell me which
> to drop."

Peripheral/Excluded sources are recorded in `seen_sources.json` but never trigger
report changes. If nothing scores Core/Supporting, report that honestly (the field
hasn't moved) and stop after updating the metadata date as in Step 1. A Step 1b
candidate the user declines keeps `status: "ranked"`, so the next `/update` lists
it again - that is intended; say so when they decline.

---

## Step 3: Classify Impact & Draft the Merge

For each source being merged, classify its impact per `08-living-updates.md`'s five
categories (extends a theme / opens a theme / contradicts a claim / answers an Open
Question / strengthens a claim) - against the actual current report text from
Step 0. Present the classification list briefly before editing.

**If any source contradicts the report's headline conclusion** (the abstract's own
claim), stop and tell the user per `08-living-updates.md` - that's a rewrite
decision, not an update.

A Step 1b candidate merges like any new source, but its Revision History line says
it was scored earlier and omitted (e.g. "scored Core on 2026-08-26, not carried in
until now") - the reader should not take a back-filled 2023 paper for new work.

Then edit `report.tex` and `references.bib` per the merge rules:
- Body sections revised in place; never append "Update: actually..." paragraphs
  against stale claims
- New `.bib` entries for merged sources, each carrying an `evidencebasis` field
  (never `note` - see `04-citation-rules.md`) plus a matching new row in the
  Evidence Basis table (`03-report-templates.md`, Section 8) - a report updated
  without this regresses to having some sources documented and others not
- Technical Findings and comparison-table updates where the categories call for them
- Open Questions updated (answered ones removed/reworded with the answering
  citation)
- Revision History entry appended (create the section after the Abstract if this is
  the report's first update, including the retroactive initial-synthesis line)
- Metadata block's search scope refreshed

Only touch what the new sources justify - no opportunistic rewrites of unaffected
prose.

---

## Step 4: Fact-Check the Changes

Spawn the reviewer agent exactly as `/synthesize` Step 3 does (same prompt
structure, full-text-first evidence discipline), with one scope change: list for
the reviewer the citation keys that are **new or whose citing prose changed** in
this run, and instruct it to verify only those. Claims untouched since the last
verified version stay verified - this scoping is what makes an update materially
cheaper than a fresh synthesis.

Resolve every flagged citation per `/synthesize` Step 4's rules before compiling.

---

## Step 5: Compile, Inspect, Update State

1. Compile, lint and inspect per `/synthesize` Step 5 - including
   `python3 tools/check_report.py reports/<topic_slug> --compile` until it reports
   zero errors. Check the Revision History section renders correctly on its first
   appearance.

   **A report written before a convention existed will fail the linter on things this
   update did not cause** - no Evidence Basis section, evidence commentary in `note`
   instead of `evidencebasis`, or a `\bibliographystyle` that no longer matches the
   profile's citation style. Bring the report up to current conventions as part of
   this update rather than leaving it failing: move each `note`'s evidence commentary
   into `evidencebasis`, add the Evidence Basis table, and re-render in the profile's
   style (switching the natbib option with it, and adding the `\harvardurl` override
   when the new style is Harvard - see `04-citation-rules.md`). Record
   each migration in the Revision History entry, separately from the content changes,
   so a reader can tell "new sources merged" from "formatting brought up to date".
2. Record merged sources (new and Step 1b alike) in state with one call -
   `python3 tools/state.py batch --file sources --json-file <scratch>/merged.json` -
   setting `"status": "synthesized"` plus their scoring fields. The helper regenerates
   `research/papers_by_subject.md` in the same write.
3. If `research_tracker.csv` exists and has a row for this topic, update it with
   `python3 tools/state.py upsert --file tracker --key <topic_slug> --json '{...}'`: a
   `superseded` or `needs_revision` status returns to `active`, `last_event_date` set,
   and a dated note added via `"notes_append"` (e.g. "2026-10-02: updated: +3
   sources, revised §4.2") so earlier notes are kept. Do not create the tracker or a
   new row if none exists - that's `/outcome`'s job, so check first.

---

## Step 6: Present the Delta

Lead with what changed, not a re-summary of the whole report:

```
## Report Updated: <topic> - YYYY-MM-DD

### What Changed
[per merged source: impact category, section touched, one-line summary of the
change - matching the Revision History entry]

### What Didn't
[one line: N sections untouched; any new sources scored but not merged, with
verdicts; Step 1b candidates declined, and the count of off-topic Step 1b entries]

### Verification
[fact-check scope (K citations checked) and result; compile checklist pass/fail]

### Files
- reports/<topic_slug>/report.pdf (updated, Revision History dated YYYY-MM-DD)
```

If the update resolved an Open Question or revised a claim, suggest `/defend` prep
may be stale if a prep pack exists for this topic.

---

## Important Rules

1. **The body is always current; the Revision History is the only append-only part.**
   Never leave a stale claim standing next to an appended correction.
2. **An empty update is a valid outcome.** "Nothing new since <date>" with a
   refreshed checked-through date is honest and useful; padding is not.
3. **Headline-conclusion contradictions stop the run** for an explicit user
   decision - update vs. rewrite is not this command's call to make.
4. **Fact-check scope = change scope.** New and changed claims only; never re-open
   verified-and-untouched claims, and never skip the pass entirely either.
5. **Same honesty rules as everywhere else**: disagreements stated not smoothed,
   evidence basis recorded (full text vs. abstract), no claim beyond what a fetched
   source supports.
