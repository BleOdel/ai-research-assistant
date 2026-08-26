# /synthesize - Drafter-Reviewer Synthesis Workflow

Scores discovered sources, drafts a cited LaTeX report, fact-checks every citation
with a second agent, compiles to PDF, and verifies the result.

`$ARGUMENTS` is the topic, optionally followed by source numbers from a prior
`/research` run (e.g. `/synthesize retrieval-augmented generation 1,2,4` or
`/synthesize retrieval-augmented generation all`). If no numbers are given, run
`/research`'s Steps 0-4 first to populate candidates, then use all `status: new` or
`status: skipped` (never previously synthesized) entries for this topic.

Follow these steps **exactly in order**. Do not skip steps.

**Token-efficiency rules:**
- Never re-Read a file already in context from an earlier step.
- Pass draft content to the reviewer agent **inline in the prompt**, not as a file it
  must re-Read.
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

- Title, metadata block stating search scope (connectors queried, date this was run)
- Abstract
- Background (length per the profile's expertise level for this topic)
- Thematic body sections organized by approach/theme, not a flat per-paper list
- Technical Findings (Plain Language) - standard section per `03-report-templates.md`,
  unless the active template's manifest says it doesn't map onto that template's
  required structure
- Comparison table if the topic has genuinely comparable approaches
- Open Questions / Gaps - stated explicitly, disagreements not smoothed over
- Bibliography via `\bibliography{references}` (or the active template's declared
  bibliography engine), style set from the profile's citation style preference
  unless the active template's manifest forces a specific style (see
  `04-citation-rules.md`'s style table)

**Every claim must trace to a source's actually-fetched content from Step 1.** If a
claim can't be pinned to a specific source, mark it as synthesis/inference in the prose,
not a citation.

Keep the draft text in working memory - you will pass it inline to the reviewer in
Step 3 and revise it in Step 4 without re-reading.

---

## Step 3: REVIEWER - Fact-Check Every Citation

Use the **Agent tool** to spawn a `general-purpose` reviewer agent with fresh context.
Pass the draft **inline in the prompt** - do not make the reviewer Read the files.

Replace `<TOPIC>`, `<INSERT_REPORT_TEX_HERE>`, and `<INSERT_REFERENCES_BIB_HERE>`
before dispatching:

```
You are a fact-checker reviewing a literature synthesis report before publication. Your
ONLY job is citation verification, not prose critique.

## Draft to Review

<REPORT_TEX file="reports/<TOPIC>/report.tex">
<INSERT_REPORT_TEX_HERE>
</REPORT_TEX>

<REFERENCES_BIB file="reports/<TOPIC>/references.bib">
<INSERT_REFERENCES_BIB_HERE>
</REFERENCES_BIB>

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

### 5b. Inspect

Read the compiled `report.pdf` via the Read tool and verify:
- [ ] No `??` anywhere (unresolved `\cite`/`\ref`)
- [ ] Bibliography section lists every cited work, correctly formatted in the profile's
      chosen citation style
- [ ] No table or content visibly overflowing a page edge
- [ ] Section structure matches what was drafted (background, thematic sections,
      comparison table if present, open questions, references)

### 5c. Iterate until clean

Fix `.tex` issues and recompile (full 4-pass sequence) until 5b passes fully.

### 5d. Clean up build artifacts

```bash
rm -f *.aux *.log *.bbl *.blg *.out
```

If the active template uses `biber` (per its manifest), also remove its artifact
types: `rm -f *.bcf *.run.xml`.

Keep `report.tex`, `references.bib`, and `report.pdf`.

---

## Step 6: Present Final Output

Run the full Verification Checklist from `CLAUDE.md` now - this is the only
verification pass in the workflow, done once here with final state on disk.

```
## Synthesis Report: <topic>

### Verification Checklist
[pass/fail per CLAUDE.md's checklist items]

### Sources Used
[table: source, verdict from Step 1 scoring, whether the reviewer flagged and resolved
any issue with it]

### Key Findings
[2-4 sentence summary of the report's headline conclusion]

### Open Questions Surfaced
[bullet list, pulled directly from the report's Open Questions section]

### Files Created
- reports/<topic_slug>/report.tex
- reports/<topic_slug>/references.bib
- reports/<topic_slug>/report.pdf
```

Update `research/seen_sources.json`: set `status: "synthesized"` for every source used
in this report. Then regenerate `research/papers_by_subject.md` from the full, current
contents of `seen_sources.json` per
`.claude/skills/research-assistant/05-subject-index.md`'s file format - a full
rebuild, not an incremental patch.

Tell the user the PDF is ready for review at the path above.
