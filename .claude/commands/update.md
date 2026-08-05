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
  sources drop out via dedup as usual.

If discovery finds nothing new: say so plainly, update the report's metadata-block
search-scope date (the "checked through" date moving forward IS information), add no
Revision History entry (nothing changed), and stop - do not pad an update out of
nothing. Recompile only if the metadata line changed.

---

## Step 2: Score the New Sources

Full four-dimension scoring per `02-source-evaluation.md` for each new source, with
full text via `paper-fetch` where a score turns on something the abstract doesn't
state (per `07-fulltext.md` - same as `/synthesize` Step 1). Present the scoring
table, plus a one-line reminder of the report's current headline conclusion, and
ask:

> "Merge the Core/Supporting sources into the report? Reply yes, or tell me which
> to drop."

Peripheral/Excluded sources are recorded in `seen_sources.json` but never trigger
report changes. If nothing scores Core/Supporting, report that honestly (the field
hasn't moved) and stop after updating the metadata date as in Step 1.

---

## Step 3: Classify Impact & Draft the Merge

For each source being merged, classify its impact per `08-living-updates.md`'s five
categories (extends a theme / opens a theme / contradicts a claim / answers an Open
Question / strengthens a claim) - against the actual current report text from
Step 0. Present the classification list briefly before editing.

**If any source contradicts the report's headline conclusion** (the abstract's own
claim), stop and tell the user per `08-living-updates.md` - that's a rewrite
decision, not an update.

Then edit `report.tex` and `references.bib` per the merge rules:
- Body sections revised in place; never append "Update: actually..." paragraphs
  against stale claims
- New `.bib` entries for merged sources; Technical Findings and comparison-table
  updates where the categories call for them
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

1. Compile and inspect per `/synthesize` Step 5 (4-pass sequence or the active
   template's declared engine, read the PDF, iterate until clean, remove build
   artifacts). Check the Revision History section renders correctly on its first
   appearance.
2. Update `research/seen_sources.json`: `status: "synthesized"` for merged sources.
   Regenerate `research/papers_by_subject.md` per `05-subject-index.md`.
3. If `research_tracker.csv` exists and has a row for this topic, update it: a
   `superseded` or `needs_revision` status returns to `active`, `last_event_date`
   set, and a dated note appended (e.g. "updated: +3 sources, revised §4.2"). Do
   not create the tracker if it doesn't exist - that's `/outcome`'s job.

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
verdicts]

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
