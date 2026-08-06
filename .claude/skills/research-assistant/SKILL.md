---
name: research-assistant
description: >
  Assists with topic research: discovering academic sources, ranking and scoring their
  relevance, and synthesizing a cited state-of-the-art report. Triggers on keywords
  like: research topic, literature review, state of the art, find papers, rank sources,
  synthesize research, source discovery, citation check, /research, /rank, /synthesize
allowed-tools: Read, Glob, Grep, WebFetch, WebSearch, Edit, Write, Agent, AskUserQuestion
---

# Research Assistant

---

## Workflow

When the user gives a topic, follow this workflow:

### Step 1: Discover Sources
- Run the installed connector CLIs (`.agents/skills/arxiv-search`,
  `.agents/skills/semantic-scholar-search`, `.agents/skills/google-scholar-search`) for
  the topic - see `/research`'s own command file for the exact procedure
- Deduplicate against `research/seen_sources.json`
- Quick-triage each new source (high/medium/low) per `02-source-evaluation.md`'s
  Quick Triage section - not the full rubric yet
- Present results, ask which sources (or "all") to carry into synthesis

### Step 1.5: Rank a Large Batch (optional, `/rank`)
- When a discovery batch is large (roughly 8+ new sources), run `/rank` to batch-score
  every new source against the full four-dimension rubric via parallel agent dispatch
  and return a shortlist - cheaper than scoring everything inline in `/synthesize`
- `/rank` never fact-checks or drafts; it exists purely to help decide what's worth a
  full `/synthesize` pass

### Step 2: Score Sources
- For sources selected for synthesis, run the full four-dimension scoring in
  `02-source-evaluation.md`
- Present the scoring table before drafting - the user should see what's about to be
  cited and why, and can veto a source before it enters the report

### Step 3: Draft the Report
- Follow the structure in `03-report-templates.md`, starting from
  `report/report_example.tex`
- Follow the citation rules in `04-citation-rules.md` - every claim traces to fetched
  content, no exceptions
- Write `reports/<topic_slug>/report.tex` and `reports/<topic_slug>/references.bib`

### Step 4: Fact-Check
- Spawn a reviewer agent with fresh context (via the Agent tool) to run the Fact-Check
  Pass described in `04-citation-rules.md`
- The reviewer verifies against full text where an open-access PDF exists (via
  `paper-fetch`, per `07-fulltext.md`), falling back to the abstract - and records
  which evidence basis backed each source
- Resolve every flagged citation before proceeding

### Step 5: Compile and Verify
- Compile with the 4-pass pdflatex/bibtex sequence in `CLAUDE.md`'s verification
  checklist
- Read the rendered PDF pages and fix any layout or rendering defects
- Run through the full Verification Checklist in `CLAUDE.md` and report it as a
  pass/fail list

---

## Reference Files

| File | Purpose |
|------|---------|
| `01-researcher-profile.md` | Interests, expertise level, output preferences |
| `02-source-evaluation.md` | Scoring framework for source relevance/rigor/impact/recency |
| `03-report-templates.md` | LaTeX report structure and section rules |
| `04-citation-rules.md` | Citation style, BibTeX rules, verify-before-cite honesty rule |
| `05-subject-index.md` | Subject-organized paper index (`research/papers_by_subject.md`) format and classification rules |
| `06-defense-prep.md` | Question-derivation and honest-answer framework used by `/defend` |
| `07-fulltext.md` | When and how to read full-text PDFs (via the `paper-fetch` utility skill) instead of abstracts |
| `08-living-updates.md` | Merge rules for `/update`: revise in place, dated Revision History, impact categories |
| `09-web-source-evaluation.md` | Credibility rubric for blogs/websites (`/websearch`) - separate from the academic rubric |
| `10-html-reports.md` | Interactive HTML output format and build rules for `/websearch` |

---

## Quick Commands

The user may also ask for individual steps without the full workflow:
- "Find sources on [topic]" - Step 1 only (equivalent to `/research`)
- "Rank/triage what we found" - Step 1.5 only (equivalent to `/rank`)
- "Score these sources against my interests" - Step 2 only
- "Write up what we found" - Steps 3-5 (equivalent to `/synthesize`, assuming Step 1-2
  already ran)
- "Check the citations in this report" - Step 4 only, run standalone against an
  existing `.tex`/`.bib` pair
- "Help me prep to present/defend this report" - equivalent to `/defend`, see
  `06-defense-prep.md`
- "Record what happened to this report" (presented, cited, needs revision,
  superseded) - equivalent to `/outcome`
- "Bring this report up to date" / "what's new on this topic since the report" -
  equivalent to `/update`, see `08-living-updates.md`
- "What are practitioners writing about X" / "find blogs and websites on X" -
  equivalent to `/websearch`, see `09-web-source-evaluation.md`. This is the
  grey-literature track: separate state, separate rubric, HTML output. Never blend
  its sources into an academic `/synthesize` report
