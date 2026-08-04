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
all four dimensions (Relevance, Recency, Rigor, Impact) per the framework.

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
- `report/report_example.tex` as a structural starting point

Create `reports/<topic_slug>/report.tex` and `reports/<topic_slug>/references.bib`
following the structure in `03-report-templates.md` and the citation rules in
`04-citation-rules.md`:

- Title, metadata block stating search scope (connectors queried, date this was run)
- Abstract
- Background (length per the profile's expertise level for this topic)
- Thematic body sections organized by approach/theme, not a flat per-paper list
- Comparison table if the topic has genuinely comparable approaches
- Open Questions / Gaps - stated explicitly, disagreements not smoothed over
- Bibliography via `\bibliography{references}`, style set from the profile's citation
  style preference (see `04-citation-rules.md`'s style table)

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
2. Fetch that URL with WebFetch and read the actual abstract/content.
3. Find the specific sentence(s) in report.tex that cite this source, and check whether
   the claim made actually appears in (or is a fair restatement of) what you just
   fetched. A citation supporting a claim the source doesn't make is a FAIL, even if the
   source is real and relevant to the general topic.

Also check the reverse direction: any .bib entry that is never \cite{}'d anywhere in
report.tex (unused).

## Output

Return a JSON array, one object per citation key in the .bib file:

```json
[
  {
    "key": "<bibtex key>",
    "url_resolves": true | false,
    "claim_verified": true | false | "not_applicable_unused",
    "issue": "<one-line description if either check failed, else null>"
  }
]
```

Do not critique prose style, structure, or completeness - only citation-to-source
accuracy. That is the drafter's job in Step 4.
```

---

## Step 4: DRAFTER - Resolve Every Flagged Citation

For every entry the reviewer returned with `url_resolves: false` or
`claim_verified: false`:

1. Re-check the source yourself. If the claim is simply mis-stated, correct the prose
   in `report.tex` to match what the source actually says.
2. If the source genuinely doesn't support the claim, either find a different source
   from the scored candidates that does, or remove the claim/citation and mark the point
   as unsupported if it can't be dropped without losing a needed transition.
3. Remove any `unused` `.bib` entry, or add a citation for it if it should have been
   cited and was simply missed.

Do not proceed to Step 5 until every flagged citation is resolved. This is not
optional - a report with an unresolved citation flag is not "mostly done," it's a
report with a known false claim in it.

---

## Step 5: DRAFTER - Compile & Inspect PDF (MANDATORY)

**Never skip this step.** A `.tex`/`.bib` pair that looks correct can still fail to
compile, mis-render the bibliography, or leave `??` where a citation should be.

### 5a. Compile (4-pass sequence)

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
in this report.

Tell the user the PDF is ready for review at the path above.
