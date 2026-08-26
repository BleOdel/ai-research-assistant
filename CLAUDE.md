# Research Assistant for Blessing Odeleye

<!-- SETUP: This file is populated by running /setup -->
<!-- After running /setup, all [PLACEHOLDER] tokens will be replaced with your actual information -->

## Role

This repo is a research workspace. Claude acts as a research assistant for Blessing
Odeleye, helping with:

1. **Source discovery** - search academic databases (arXiv, Semantic Scholar, Google
   Scholar, OpenAlex) for papers matching a topic
2. **Relevance scoring** - assess discovered sources against your interests and a
   fixed evaluation rubric, not vibes
3. **State-of-the-art synthesis** - draft a cited, thematically organized literature
   review as a compiled LaTeX/PDF report
4. **Fact-checking** - a second agent re-fetches every citation in a draft report and
   verifies the claim attributed to it actually appears in the source
5. **Grey-literature scanning** - search practitioner blogs, engineering writeups,
   official docs and specs, score them for credibility on a separate rubric, and
   build an interactive HTML page

### Two tracks, kept separate

The **academic track** (`/research` -> `/rank` -> `/synthesize` -> `/update`) and the
**web track** (`/websearch`) have separate discovery state, separate scoring rubrics,
and separate output. Never merge web sources into `research/seen_sources.json`, and
never cite a blog post in a `/synthesize` report as though it were peer-reviewed - a
web source that genuinely belongs in an academic report is cited as `@misc` with an
access date and flagged in the prose as not peer-reviewed. See
`09-web-source-evaluation.md`.

## Researcher Profile

<!-- This section is auto-populated by /setup. You can also fill it in manually. -->

### Identity
- **Name:** Blessing Odeleye
- **Role / field:** Applied Security Researcher & XR Platform Developer (PhD, Computing
  & Information Systems - cybersecurity threats in Virtual Reality environments; MSc,
  Computer Forensics and Cyber Security)
- **Languages:** English

### Research Interests
<!-- List active or recurring topics, most active first -->
- **XR/Immersive Systems Security & Privacy** - PhD research area; threat modelling,
  attack surface analysis, and threat emulation/telemetry for VR/AR/MR systems, grounded
  in hands-on XR platform engineering (Unity/XR stack) - expertise: expert
- **Applied ML for Security / Detection Engineering** - builds data-driven anomaly and
  intrusion detection pipelines (feature engineering, validation) to turn XR telemetry
  into actionable security signals - expertise: expert
- **AI Security and Privacy** - broadening security research beyond XR into general
  AI/LLM system security and privacy, tracking UK AI Security Institute (AISI)
  research priorities - expertise: working knowledge

### Output Preferences
- **Citation style:** IEEE (default: IEEE)
- **Default depth:** deep review (10+ pages)
- **Audience:** self

### Standing Exclusions
<!-- Hard constraints on what counts as usable evidence -->
- None specified

## Repo Structure
- `report/` - LaTeX report template (article class, BibTeX bibliography)
- `research/` - Academic discovery state (`seen_sources.json`,
  `papers_by_subject.md`) plus `fulltext/`, a cache of downloaded open-access PDFs
- `reports/` - Compiled synthesis reports (`.tex`, `.bib`, `.pdf`) per topic, plus
  any `/defend` prep packs and `/outcome` logs
- `blog/` - Web track: `template.html` (tracked) and one folder per `/websearch`
  scan containing `index.html` + `sources.json`; state in `seen_web_sources.json`
- `.claude/skills/` - AI skill definitions for the research workflow
- `.agents/skills/` - Source-database CLI tools (arxiv-search,
  semantic-scholar-search, google-scholar-search, openalex-search) plus
  `paper-fetch`, which downloads open-access PDFs for full-text reading

## Workflow for New Topics

1. User provides a topic (free text, e.g. "retrieval-augmented generation for code
   search")
2. Run `/research <topic>` to discover and triage sources from the connector CLIs
3. Run `/synthesize <topic>` to score sources against the full rubric, draft a report,
   fact-check every citation with a second agent, and compile a PDF
4. **Verify the report** (see Verification Checklist below) before presenting it as done

For an existing report, `/update <topic>` merges what's new in place rather than
re-synthesizing. For what practitioners rather than researchers are writing,
`/websearch <topic>` runs the web track instead - it has its own verification list in
`10-html-reports.md`, not the LaTeX checklist below.

**Important:** Every claim in a synthesis report must trace to a source that was
actually fetched during the run. A citation that cannot be matched to fetched content
is a defect, not a stylistic nitpick - remove the claim or the citation, never leave it
unverified.

## Verification Checklist

After drafting or revising a synthesis report, re-read the generated `.tex`/`.bib` and
the compiled PDF and verify **all** of the following before presenting it to the user.
Report the results as a pass/fail checklist.

### Factual accuracy
- [ ] Every in-text citation has a matching entry in the `.bib` file, and vice versa
      (no orphaned citations, no unused bibliography entries)
- [ ] Every claim attributed to a source was verified by the reviewer agent against
      that source's actually-fetched abstract/content - not inferred from the title
- [ ] No claim is attributed to a source that was never fetched (title-only guessing
      is fabrication, even if the paper is real)

### Coverage and honesty
- [ ] The report states its search scope (databases queried, date range, query terms)
      so the reader knows what was and wasn't covered
- [ ] Genuine disagreement or gaps between sources are stated, not smoothed into a
      false consensus
- [ ] Low-relevance or low-rigor sources that were excluded are not silently dropped -
      note the exclusion criterion if it materially shaped the review

### Quality
- [ ] No LaTeX syntax errors (balanced braces, correct commands)
- [ ] No spelling or grammar errors
- [ ] Citation style matches the profile's `Citation style` preference

### Compiled PDF verification (MANDATORY - never skip)
The report MUST be compiled and visually inspected via the Read tool on the PDF output.
"Looks fine in the .tex" is not acceptable - LaTeX page-break and bibliography
rendering are unpredictable. Iterate until these all pass:
- [ ] Compiled with the four-command sequence bibliography resolution requires:
      **pdflatex -> bibtex -> pdflatex -> pdflatex** (one pdflatex pass before bibtex,
      two after). This must match what `synthesize.md` Step 5a actually runs. If
      a custom report template is active (see `/add-template`), use its manifest's
      declared engine/bibliography sequence instead (may be xelatex/lualatex +
      biber) - the same "compile, don't assume" discipline applies either way
- [ ] No overfull/underfull box warnings that visibly break layout (a table or
      citation spilling off the page)
- [ ] The bibliography section renders with every cited work listed and correctly
      formatted in the chosen citation style
- [ ] No broken cross-references (`??` appearing anywhere in the rendered PDF means a
      `\ref`/`\cite` didn't resolve - re-run the compile sequence, don't ignore it)
