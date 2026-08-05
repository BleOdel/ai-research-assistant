# Report Template Guide

The synthesis report is a single `article`-class LaTeX document with a BibTeX
bibliography, compiled to PDF. The stock structure lives at
`report/report_example.tex` - copy it as the starting point for a new topic; don't
build a report's structure from scratch each time.

## File Naming

For a topic, create:
- `reports/<topic_slug>/report.tex`
- `reports/<topic_slug>/references.bib`

`<topic_slug>` is the topic lowercased, spaces to hyphens (e.g.
`retrieval-augmented-generation`).

## Section Structure

1. **Title + metadata block** - topic, date, search scope (databases queried, date
   range or query terms used) as a footnote or preamble note. This is not decorative:
   it tells the reader what the review does and doesn't cover.
2. **Abstract** - 4-6 sentences: what topic, what was found, the headline
   state-of-the-art conclusion, and the most important open question.
3. **Background** (skip or keep to 1 paragraph if the profile's expertise level for
   this topic is "expert" - see `01-researcher-profile.md`) - define the problem and
   any terms a working-knowledge reader would need.
4. **Thematic body sections** - organize by sub-theme or approach, **never** as a flat
   chronological or per-paper list. A reader should come away understanding how
   approaches relate to each other, not just that N papers exist. Typical shape:
   - One subsection per major approach/family of methods
   - Within each: what problem it solves, key papers (cited), tradeoffs
5. **Technical Findings (Plain Language)** - a standard section, not optional. Restates
   the core technical mechanism of each approach/attack/method covered in Section 4 in
   plain language: minimal jargon, terms defined inline on first use, analogies where
   they genuinely clarify rather than oversimplify. This is not a re-summary of the
   abstracts - it's "if you had to explain how this actually works to a colleague
   outside the subfield, in one paragraph per approach, what would you say." Numbers
   and accuracy figures are still cited exactly as in Section 4; only the explanation
   register changes, not the facts. Skip only if the topic is already so
   non-technical that Section 4 reads plainly on its own - the default is to include
   it.
6. **Comparison table** (when the topic has multiple competing approaches/methods) -
   columns typically: Approach, Key Paper(s), Strengths, Limitations. Skip this section
   entirely if the topic doesn't have genuinely comparable approaches - don't force a
   table where it adds nothing.
7. **Open Questions / Gaps** - explicit, not folded into the conclusion. What does the
   current literature not resolve? Where do sources actively disagree? This section is
   often what the reader is most looking for - a synthesis that pretends the field is
   settled when it isn't has failed at its job.
8. **References** - BibTeX-driven, rendered via `\bibliography{references}` with the
   style set by `04-citation-rules.md`'s profile-driven citation style.

## LaTeX Mechanics

- Document class: `\documentclass[11pt]{article}`
- Packages: `hyperref` (clickable citations/links), `natbib` (citation style control),
  `booktabs` (clean comparison tables), `geometry` (reasonable margins)
- Bibliography: classic BibTeX (`\bibliographystyle{<style>}` + `\bibliography{...}`),
  compiled with the 4-pass sequence in `CLAUDE.md`'s verification checklist
  (pdflatex → bibtex → pdflatex → pdflatex). This is deliberately **not** biblatex/biber
  - keeps the toolchain to what's present on a stock TeX Live install without extra
  package installation.
- No fixed page-count target (unlike a CV). Length should match the profile's `Default
  report depth` preference and the topic's actual breadth - padding a thin topic to hit
  a page count is worse than a short, honest report.

## Length Calibration

- **Quick brief**: Abstract + 2-3 thematic sections + Technical Findings + Open
  Questions. No comparison table unless trivial to include. Target ~4-5 pages (the
  Technical Findings section is standard even at this depth - see Section Structure
  above).
- **Deep review**: Full structure above, comparison table included where applicable,
  more sources per thematic section (aim for enough sources that each thematic
  subsection has more than one citation backing it, not a single paper standing in for
  a whole approach), and a correspondingly fuller Technical Findings section covering
  every approach discussed. Target 10+ pages.

Use the profile's `Default report depth` unless the user specifies otherwise for a
given `/synthesize` run. A report that undershoots its target depth because too few
sources were carried in from `/research`/`/rank` should say so explicitly (state the
number of sources used) rather than padding prose to hit a page count - length comes
from genuine coverage, never from restating the same finding in more words.
