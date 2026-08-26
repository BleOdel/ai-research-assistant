# /gaps - Cross-Report Analysis

Reasons across **all** synthesized reports at once, rather than one at a time. Every
other command in this framework operates on a single report; this one exists because
the interesting signals only appear when you look at several together - the same gap
flagged independently in two reports, a paper both cite but treat differently, or an
open question that a source already sitting in your corpus appears to answer.

It reads `reports/*/report.tex`, their `.bib` files, `research/seen_sources.json` and
`research_tracker.csv` if present. It **never edits a report** - like `/outcome`, it
surfaces and suggests. Acting on a finding is `/update`'s job or yours.

`$ARGUMENTS` is optional: a subject area or topic fragment to narrow the analysis to
a subset of reports. Empty means all of them.

Follow these steps in order.

---

## Step 0: Load

1. List `reports/*/` and read each `report.tex` and `references.bib`. If fewer than
   two reports exist, say so and stop - there is nothing to compare, and a
   single-report analysis is what `/defend` already does better.
2. Read `research/seen_sources.json`, and `research_tracker.csv` if it exists.
3. Read `.claude/skills/research-assistant/01-researcher-profile.md` for the tracked
   Research Interests, which set what "adjacent" means in Step 2.

State how many reports are in scope before proceeding.

---

## Step 1: Recurring Open Questions

Extract the Open Questions section from each report. Two questions "recur" when they
name the same underlying gap, **not** merely when they share vocabulary - two reports
saying "evaluation is hard" in different subfields is not a recurring question; two
reports independently finding that no shared benchmark exists in their respective
areas is.

For each recurrence, report: the reports involved, each one's phrasing verbatim, and
what the shared gap actually is.

**This is the highest-value output of the command.** A gap you found once is an
observation; the same gap surfacing independently in two literatures is a research
direction, and it is the kind of pattern no single-report command can see.

Be conservative. A forced connection between unrelated questions is worse than
reporting none - say plainly when the reports share no genuine gap.

---

## Step 2: Open Questions Your Own Corpus May Already Answer

For each report's open questions, search `seen_sources.json` for sources that are
**scored but never synthesized** (`status: "ranked"`) whose title and recorded scores
suggest they address it - especially Core-tier ones.

Report matches as candidates, never as answers: you are matching an open question
against a *title and score*, not against fetched content. Say so explicitly, and
recommend `/update <topic>` to evaluate properly rather than asserting the question is
resolved.

This is where a stale report shows up. A report whose subject area has accumulated
sources since synthesis, with none merged, is drifting out of date whether or not
anything contradicts it.

---

## Step 3: Shared Sources, Divergent Treatment

Find bibliography keys, DOIs or titles appearing in more than one report. For each:

- **Different verdict or score** recorded across runs - a source Core in one report
  and Peripheral in another may be legitimate (relevance is topic-relative), but it
  may also be inconsistent scoring. Report the scores and let the user judge.
- **Different evidence basis** - read in full for one report, abstract-only for
  another. The full-text reading already exists in `research/fulltext/`; the second
  report could be upgraded at no fetch cost.
- **Different or conflicting interpretation** - the two reports characterize the same
  paper's findings differently. Quote both, and do not adjudicate unless one of them
  demonstrably misstates the source.

A shared source is not a problem by itself. Reports in adjacent fields *should*
overlap; the finding is divergence, not overlap.

---

## Step 4: Portfolio Health

A short factual summary, no interpretation beyond what the numbers show:

- Reports by subject area, and any tracked Research Interest with no report at all
- Per report: source count, tier distribution, date of last revision, and whether its
  subject's source pool has grown since
- Corpus-wide: how many sources are `ranked` but never used, how many carry
  `evidence_basis: fulltext` versus `abstract`, how many are `unfetchable`
- Any Research Interest whose recorded expertise level looks out of step with its
  coverage - an interest marked "expert" with three sources behind it is a gap in the
  corpus, not in the field

---

## Step 5: Present

```
## Cross-Report Analysis - YYYY-MM-DD

Analyzed N reports across M subject areas.

### Recurring open questions
[per recurrence: the shared gap, which reports, each phrasing verbatim]

### Open questions your corpus may already address
[per match: the question, the candidate source with score and status,
 and the /update command that would evaluate it]

### Shared sources treated differently
[per source: which reports, what diverges, both characterizations quoted]

### Portfolio health
[the Step 4 summary]

### Suggested next steps
[concrete and ordered - which /update to run, which interest is under-covered]
```

Offer to save to `research/gaps-YYYY-MM-DD.md` (gitignored). Do not write it
unprompted.

---

## Important Rules

1. **Never edit a report.** This command reads and suggests. `/update` merges new
   work; `/synthesize` writes; `/gaps` neither.
2. **Never assert that an open question is answered** on the strength of a title and
   a score. Step 2 produces candidates for evaluation, and must say so.
3. **Be conservative about recurrence.** Two questions recur when they name the same
   gap, not when they share words. Reporting no recurrence is a valid and common
   result; a manufactured connection is worse than silence.
4. **Overlap between adjacent reports is expected and healthy.** Only divergence in
   how a shared source is scored, read, or characterized is worth reporting.
5. **Quote, don't paraphrase**, when reporting how two reports characterize the same
   source - the difference is often in the hedging, which paraphrase destroys.
