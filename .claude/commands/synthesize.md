# /synthesize - Drafter-Reviewer Synthesis Workflow

Scores discovered sources, drafts a cited LaTeX report, fact-checks every citation
with a second agent, compiles to PDF, and verifies the result.

`$ARGUMENTS` is the topic, optionally followed by source numbers from a prior
`/research` run (e.g. `/synthesize retrieval-augmented generation 1,2,4` or
`/synthesize retrieval-augmented generation all`). If no numbers are given, run
`/research`'s Steps 0-4 first to populate candidates, then use all `status: new`,
`status: skipped` or `status: ranked` (never previously synthesized) entries for this
topic. Leaving out `ranked` is how three Core sources `/rank` had scored went
uncited in the prompt-injection report.

Follow these steps **exactly in order**. Do not skip steps.

**Token-efficiency rules:**
- Never re-Read a file already in context from an earlier step.
- Give the reviewer agent the draft's **file paths**, not a pasted copy. Pasting makes
  the drafter re-emit the whole draft as output (the expensive direction, and a long
  report runs to tens of thousands of tokens), and any transcription slip means the
  reviewer checks text that is not in the file that compiles. Reading the two files is
  cheap input for the reviewer and checks exactly what ships.
- Step 5 (compile and inspect) is mandatory and non-skippable - a `.tex`/`.bib` pair
  that looks fine can still fail to compile, orphan a citation, or render a broken
  bibliography.

---

## Step 1: DRAFTER - Score Sources

Read the scoring framework and profile **once**:
- `.claude/skills/research-assistant/02-source-evaluation.md`
- `.claude/skills/research-assistant/01-researcher-profile.md`

For each candidate source, fetch its full content if not already fetched (use each
connector's `detail` command per its `SKILL.md`, or `WebFetch` on its URL), then score
all four dimensions (Relevance, Recency, Rigor, Impact) per the framework, and assign
each source a `disclosure` label. Rigor is now two-part - score venue, then apply the
method-quality adjustments and record the breakdown in `rigor_basis` so the reader can
see which half of the score is venue prestige and which is demonstrated method. If several
candidates in this batch came from `semantic-scholar-search`, space consecutive
`detail` calls to it at least one second apart - its authenticated quota is a firm
1 request/second cumulative across all its endpoints (see its `SKILL.md`), not a
per-call allowance, and this step is exactly the kind of "several sources, one
connector" loop that can burn through it quickly if called back-to-back.

If a source's Relevance or Rigor score genuinely turns on something its abstract
doesn't state (evaluation setup, sample size, whether the method applies to this
topic's setting), fetch its full text with `paper-fetch` and read the deciding
sections rather than guessing - see
`.claude/skills/research-assistant/07-fulltext.md` for when this is and isn't
warranted. A paywalled source (`NO_OA_PDF`) is scored from its abstract with that
weaker evidence basis noted explicitly in the scoring notes.

Before presenting, check the batch as a whole against
`03-report-templates.md`'s **Evidential Sufficiency** section: if the load-bearing
sources are Peripheral-tier, or every source supporting the headline claim is
`self-evaluating`, or nothing addresses the topic's core question directly, say so now
rather than after drafting. A short honest report that reports an absence is a valid
outcome, and it is much cheaper to decide that here than at Step 5.

Present the scoring table (see `02-source-evaluation.md`'s Output Format) and ask:
> "Proceed to draft the synthesis with these sources? Reply yes, or tell me which to
> drop."

**If the user says no, stop here.** If yes, continue to Step 2.

---

## Step 2: DRAFTER - Draft the Report

You already have the profile and scored sources in context. **Do not re-read them.**

Read only what you don't yet have:
- `.claude/skills/research-assistant/03-report-templates.md`
- `.claude/skills/research-assistant/04-citation-rules.md`

**Check `03-report-templates.md` for an `ACTIVE-TEMPLATE` managed block** (added by
`/add-template`) before deciding where to draft from:

- **If present:** draft from `templates/<name>/template.tex` (per the block's
  `Template skeleton` path) instead of the stock structure, follow the required
  section structure in that template's `TEMPLATE.md` manifest, and use the
  compile/bibliography engine the block specifies in Step 5 instead of the stock
  4-pass pdflatex+bibtex sequence. The block tells you exactly what overrides what -
  don't guess.
- **If absent:** draft from `report/report_example.tex` as the structural starting
  point (the stock behavior, unchanged).

Create `reports/<topic_slug>/report.tex` and `reports/<topic_slug>/references.bib`
following the structure in `03-report-templates.md` (or the active template's
manifest, if one is active) and the citation rules in `04-citation-rules.md`:

- Title, and a metadata block carrying all four fields
  `03-report-templates.md` marks required: connectors queried (naming any that failed
  or lacked a key, with the reason), date/query terms, source count **with its
  Core/Supporting/Peripheral distribution**, and exclusions including any unfetchable
  candidates by name
- Abstract
- **Revision History**, seeded now with the initial dated entry (date, source count,
  connectors) - not deferred to first `/update`
- Background (length per the profile's expertise level for this topic)
- Thematic body sections organized by approach/theme, not a flat per-paper list
- Technical Findings (Plain Language) - standard section per `03-report-templates.md`,
  unless the active template's manifest says it doesn't map onto that template's
  required structure
- Comparison table if the topic has genuinely comparable approaches - as a
  `longtable`, not a `table` float, if it may run past a page
  (`03-report-templates.md`, LaTeX Mechanics)
- Open Questions / Gaps - stated explicitly, disagreements not smoothed over
- **Evidence Basis** - a required table, one row per source, per
  `03-report-templates.md`'s Section 8. Every `.bib` entry carries an
  `evidencebasis` field recording how its content was obtained - full text read, or
  abstract-only with the reason - per `04-citation-rules.md`'s BibTeX Entry Format;
  this section turns that field (with its disclosure label and caveat) into one
  table rather than leaving it to render inline after each reference. Required on
  every entry, not just the ones that seem doubtful. Write the fields in the
  structured form `04-citation-rules.md` gives, then generate the section instead of
  typing the table:
  ```bash
  python3 tools/evidence_table.py reports/<topic_slug> --write
  ```
  Re-run it after any `.bib` change, including Step 4's fixes.
  **Use the `evidencebasis` field name, not `note`** - `note` renders inline in the
  bibliography under every stock citation style, which is exactly what this section
  exists to avoid.
- Bibliography via `\bibliography{references}` (or the active template's declared
  bibliography engine), style set from the profile's citation style preference
  unless the active template's manifest forces a specific style (see
  `04-citation-rules.md`'s style table)

**Every claim must trace to a source's actually-fetched content from Step 1.** If a
claim can't be pinned to a specific source, mark it as synthesis/inference in the prose,
not a citation.

Keep the draft text in working memory - you will revise it in Step 4 without
re-reading. (The reviewer reads the files itself in Step 3.)

---

## Step 3: REVIEWER - Fact-Check Every Citation

Use the **Agent tool** to spawn a `general-purpose` reviewer agent with fresh context.
Point it at the draft's files rather than pasting them (see the token-efficiency rules
above). Write both files to disk before dispatching, and do not edit them while the
reviewer runs, so it checks exactly the version that will compile.

Replace `<TOPIC>` before dispatching:

```
You are a fact-checker reviewing a literature synthesis report before publication. Your
ONLY job is citation verification, not prose critique.

## Draft to Review

Read these two files in full before starting - they are the complete draft:
- reports/<TOPIC>/report.tex
- reports/<TOPIC>/references.bib

Do not edit either file. Your output is the JSON report below; the drafter makes
every change.

## Your Task

For EVERY \cite{} in the report:

1. Confirm a matching entry exists in the .bib file, and that its `url` field points at
   a real, fetchable source (an arXiv abstract page, a Semantic Scholar paper page, or a
   DOI link - not a fabricated URL).
2. Get the source's actual content, strongest evidence first:
   a. Try the full text: run
      `bun run .agents/skills/paper-fetch/cli/src/cli.ts fetch <arxiv-id-or-doi>`
      (it caches under research/fulltext/ and returns instantly if already fetched),
      then Read the PDF - the sections relevant to the claims, not necessarily the
      whole paper. If it exits with NO_OA_PDF or RATE_LIMITED, do NOT retry it -
      fall through to (b).
   b. Fall back to WebFetch on the .bib entry's URL and read the abstract/landing
      page content.
3. Find the specific sentence(s) in report.tex that cite this source, and check whether
   the claim made actually appears in (or is a fair restatement of) what you just
   read. A citation supporting a claim the source doesn't make is a FAIL, even if the
   source is real and relevant to the general topic. A claim the abstract doesn't
   mention but that you could only check against full text you couldn't get is not a
   FAIL - report it as unverifiable at your evidence level, not as false.

Also check the reverse direction: any .bib entry that is never \cite{}'d anywhere in
report.tex (unused).

Then, ACROSS the sources you have just read - you already have them all in context, so
this needs no further fetching - check the report as a whole for four failures that no
per-citation check can catch:

- **Single-source load-bearing claims.** A claim carrying real weight in the report's
  argument, cited to exactly one source, where that source released no artifact
  (no code, dataset, or benchmark). Per `02-source-evaluation.md`'s Corroboration
  section such a claim must be *attributed* in the prose ("Luo et al. report 96.51%"),
  not stated flatly ("the attack achieves 96.51%"). Flag the flat ones.
- **Contradictions between cited sources.** Two sources in this report that disagree
  on a fact, a figure, or a conclusion, where the report presents only one side or
  smooths the disagreement away. Report both positions.
- **Causal language on correlational findings.** The report says X causes/enables/
  prevents Y where the cited source reports only an association, or reports a result
  under conditions the report's sentence drops.
- **Figures quoted without their conditions.** A number carried into the report
  without the sample size, threat model, task, or interval that makes it meaningful -
  especially where the report compares two such numbers as if they were commensurable.

## Output

Return a JSON object with two keys:

```json
{
  "citations": [
    {
      "key": "<bibtex key>",
      "url_resolves": true | false,
      "evidence_basis": "fulltext" | "abstract",
      "claim_verified": true | false | "unverifiable_at_evidence_level" | "not_applicable_unused",
      "issue": "<one-line description if a check failed or a claim was only checkable against full text you couldn't get, else null>"
    }
  ],
  "report_level": [
    {
      "type": "single_source_claim" | "source_contradiction" | "causal_overreach" | "unconditioned_figure",
      "claim": "<the sentence or clause from report.tex, quoted>",
      "keys": ["<bibtex key(s) involved>"],
      "issue": "<what is wrong and what the sources actually support>"
    }
  ]
}
```

`report_level` is an empty array if you find nothing - that is a valid and expected
result for a well-drafted report. Do not manufacture findings to fill it.

Do not critique prose style, structure, or length. The four report-level checks above
are the only judgments beyond citation-to-source accuracy that are yours to make;
everything else is the drafter's job in Step 4.
```

---

## Step 4: DRAFTER - Resolve Every Flagged Finding

The reviewer returns two arrays. Both must be resolved before Step 5.

### 4a. Per-citation findings (`citations`)

For every entry with `url_resolves: false` or `claim_verified: false` (and weigh
`unverifiable_at_evidence_level` honestly - see rule 3 below):

1. Re-check the source yourself. If the claim is simply mis-stated, correct the prose
   in `report.tex` to match what the source actually says.
2. If the source genuinely doesn't support the claim, either find a different source
   from the scored candidates that does, or remove the claim/citation and mark the point
   as unsupported if it can't be dropped without losing a needed transition.
3. For `unverifiable_at_evidence_level` (the claim needs full text, and no
   open-access copy exists): either soften the claim to what the abstract actually
   supports, or keep it with the weaker evidence basis stated in the prose (e.g.
   "per the authors' abstract") - never leave a full-text-strength claim standing
   on abstract-level evidence.
4. Remove any `unused` `.bib` entry, or add a citation for it if it should have been
   cited and was simply missed.

### 4b. Report-level findings (`report_level`)

These are not citation errors - each one is a real claim cited to a real source that
says it. They are failures of *how much weight the evidence bears*, which is why the
per-citation pass cannot see them. Resolve each by type:

- **`single_source_claim`** - attribute it in the prose ("Luo et al. report…"), or
  find a second independent source and say the two agree. Do not simply delete the
  claim: the finding is that it is under-attributed, not that it is wrong.
- **`source_contradiction`** - present both positions with their evidence and say the
  disagreement is unresolved, per `03-report-templates.md`'s Open Questions rules.
  Never silently pick a winner; if one side is better supported, say so in terms of
  the evidence (released artifact, larger N, independent replication).
- **`causal_overreach`** - rewrite to the associational claim the source actually
  supports, or state the conditions under which causation was demonstrated.
- **`unconditioned_figure`** - restore the sample size, threat model, task or
  interval, or stop comparing the figure to another that was measured differently.

A `report_level` finding is resolved by **changing the prose**, not by adding a
caveat sentence elsewhere and leaving the original claim standing.

Do not proceed to Step 5 until both arrays are resolved. This is not optional - a
report with an unresolved citation flag is not "mostly done," it's a report with a
known false claim in it, and an unresolved report-level flag is a claim the evidence
does not carry.

### 4c. Re-check what the resolution rewrote

A fix that corrects a figure or adds an attribution in place needs no second pass. A
fix that **rewrites** claims does - restructuring a section, reframing a conclusion, or
adding claims drawn from full text the reviewer surfaced. That new prose has not been
checked by anyone but its drafter. Send the rewritten regions back to the **same**
reviewer (`SendMessage` to its agent ID - it still has the sources in context, so this
is far cheaper than a fresh spawn), naming the regions and asking for the same JSON
restricted to them. Resolve what it returns the same way. In practice the second pass
finds less but not nothing: on the first run that needed one, it caught a figure
attached to the wrong benchmark and an "independent" check that was not.

---

## Step 5: DRAFTER - Compile & Inspect PDF (MANDATORY)

**Never skip this step.** A `.tex`/`.bib` pair that looks correct can still fail to
compile, mis-render the bibliography, or leave `??` where a citation should be.

### 5a. Compile (4-pass sequence)

**If an `ACTIVE-TEMPLATE` block is present** (see Step 2), use the compile command
from that template's `TEMPLATE.md` manifest instead of the sequence below - it may
use `xelatex`/`lualatex` and/or `biber` instead of `pdflatex`/`bibtex`. Otherwise, use
the stock sequence:

```bash
cd reports/<topic_slug>
pdflatex -interaction=nonstopmode report.tex
bibtex report
pdflatex -interaction=nonstopmode report.tex
pdflatex -interaction=nonstopmode report.tex
```

If any pass errors, fix the `.tex`/`.bib` and re-run the full sequence from the top -
a partial re-run after a fix can hide a real error behind stale `.aux` state.

### 5b. Lint, then inspect

First run the report linter - it rebuilds a copy in a temp directory and checks
everything mechanical: required sections, an `evidencebasis` field on every `.bib`
entry, no evidence commentary in `note`, citations and bibliography matching both
ways, `\bibliographystyle` matching the profile's citation style, the natbib option
matching the style, no `\citet` with a numbered style, the `\harvardurl` override on
a Harvard report, no `[H]` without `float`, and no undefined citations/references,
visible overfull boxes, or floats taller than the page:

```bash
python3 tools/check_report.py reports/<topic_slug> --compile
```

Every ERROR must be fixed before continuing; warnings are judgment calls - fix them or
say in Step 6 why not. If an active template's `TEMPLATE.md` explicitly drops a
section this framework normally requires, that one structure error may stand -
state it in Step 6. The linter does not read prose: it cannot see a stale claim or a
smoothed-over disagreement, which is what the reviewer and the PDF read are for.

Then read the compiled `report.pdf` via the Read tool and verify:
- [ ] No `??` anywhere (unresolved `\cite`/`\ref`)
- [ ] Bibliography section lists every cited work, correctly formatted in the profile's
      chosen citation style
- [ ] No table or content visibly overflowing a page edge
- [ ] Section structure matches what was drafted (background, thematic sections,
      comparison table if present, open questions, references)

### 5c. Iterate until clean

Fix `.tex` issues and recompile (full 4-pass sequence) until 5b passes fully - the
linter with zero errors, and the PDF read with nothing found.

### 5d. Clean up build artifacts

```bash
rm -f *.aux *.log *.bbl *.blg *.out
```

If the active template uses `biber` (per its manifest), also remove its artifact
types: `rm -f *.bcf *.run.xml`.

Keep `report.tex`, `references.bib`, and `report.pdf`.

---

## Step 6: Present Final Output

### 6a. Record state and check for dropped sources

Record the outcome in state with one state-helper call - never by editing the JSON
directly. For every source scored in Step 1, write its final Step 1 scoring
(`scores`, `rigor_basis`, `disclosure`, `evidence_basis`) with `"status":
"synthesized"` if the report cites it, or `"status": "ranked"` and `"rank_date"` if it
does not - a scored source left at `new` is invisible to every later check:

```bash
python3 tools/state.py batch --file sources --json-file <scratch>/synthesized.json
```

The helper computes `overall_score`/`verdict` from `scores`, refuses anything
invalid, and regenerates `research/papers_by_subject.md` in the same write. Write the
same author list and venue the `.bib` uses - state and bibliography should not
disagree about who wrote a paper.

Then list what was scored Core/Supporting but is not in the `.bib`:

```bash
python3 tools/state.py unmerged --subject "<subject>" --bib reports/<topic_slug>/references.bib
```

`<subject>` is the Research Interest this topic's sources are filed under. The list
covers the whole interest, so it also holds sources ranked for other topics - ignore
those. Every entry Step 1 scored for this report must appear in the output's **Scored
but Not Cited** section with its reason (dropped at the Step 1 prompt, no claim
needed it, superseded by a cited source). If `report.tex` names a listed source in
prose - search for its title's distinctive words or tool name - it must be cited: add
the citation and its `.bib` entry, have the reviewer verify the citing claims as in
Steps 3-4, recompile and re-lint per Step 5, and set its status to `synthesized`.

### 6b. Verify and present

Run the full Verification Checklist from `CLAUDE.md` now - this is the only
verification pass in the workflow, done once here with final state on disk.

```
## Synthesis Report: <topic>

### Verification Checklist
[the final `check_report.py --compile` result (must be PASS), then pass/fail for
CLAUDE.md's remaining checklist items the linter cannot check]

### Sources Used
[table: source, verdict from Step 1 scoring, whether the reviewer flagged and resolved
any issue with it]

### Scored but Not Cited
[from 6a: each Core/Supporting source Step 1 scored that the report does not cite,
with verdict and reason - or "none"]

### Key Findings
[2-4 sentence summary of the report's headline conclusion]

### Open Questions Surfaced
[bullet list, pulled directly from the report's Open Questions section]

### Files Created
- reports/<topic_slug>/report.tex
- reports/<topic_slug>/references.bib
- reports/<topic_slug>/report.pdf
```

Tell the user the PDF is ready for review at the path above.
