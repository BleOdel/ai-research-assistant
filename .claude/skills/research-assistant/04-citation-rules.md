# Citation Rules

This is the trust layer of the whole workflow. A synthesis report's only value over a
generic web search is that its claims are verifiably grounded. These rules are not
style preferences - breaking them is a correctness bug.

## The Core Rule: Verify Before Cite

**A source may only be cited for a claim that was actually confirmed in its fetched
abstract or content.** Never:
- Cite a paper for a claim inferred from its title alone
- Cite a paper you have not fetched during this run (a source cached from a previous
  `/research` run must still have its content available - if not, re-fetch it or drop
  the citation, don't cite from memory of what a paper "probably says")
- Attribute a specific number, method name, or result to a source that only discusses
  the topic generally

If a claim feels true but can't be pinned to a specific fetched source, either find a
source that actually supports it or state it as the writer's synthesis/inference,
clearly marked as such (e.g. "taken together, these results suggest..." rather than a
false citation).

## BibTeX Entry Format

Every entry in `references.bib` must include, at minimum:
- `author`, `title`, `year`
- `journal`/`booktitle` if published in a venue, or `eprint` + `archivePrefix = arxiv`
  for preprints
- `url` pointing at the actual fetched source (DOI link, arXiv abstract page, or
  Semantic Scholar paper page)
- **`note` recording the evidence basis** - how this source's content was obtained,
  and anything the reader needs in order to weigh the citation. This is required, not
  optional. Two forms:
  - Full text read: `note = {Primary PDF read directly via paper-fetch on YYYY-MM-DD
    - full text, not abstract-only}`
  - Abstract only: `note = {Abstract-only evidence basis: <why no full text - e.g.
    IEEE paywall, no preprint found>; abstract verified via <route>}`

  Add to the same field anything unresolved about the source: a venue confirmed
  against the publisher rather than a database tag, a preprint whose published version
  could not be located, a disclosure label worth surfacing (`self-evaluating`,
  `vendor-report`). These notes render in the bibliography, so a reader sees per source
  how strong the evidence behind it is without having to ask.

  This exists because it was previously done only when a human was in the loop asking
  for it: of four reports produced by this framework, one carries evidence-basis notes
  on 11 of 14 entries and the other three carry none at all.

Never fabricate a field. If a preprint has no venue, the entry is a `@misc` or
`@article` with `eprint`/`archivePrefix` set - it does not get a fake `journal` field
to look more legitimate.

## Citation Style

Use the style set in `01-researcher-profile.md`'s `Citation style` field. Default:
**IEEE** (numbered, `\bibliographystyle{ieeetr}`) since the shipped connectors skew
CS/ML (arXiv especially; OpenAlex is the one with broad non-CS coverage). Other supported values map to standard BibTeX styles:

| Profile value | `\bibliographystyle{}` |
|----------------|------------------------|
| IEEE | `ieeetr` |
| APA | `apalike` |
| Plain/numbered | `plain` |
| Author-year | `plainnat` (requires `natbib`, already loaded per `03-report-templates.md`) |

`natbib`'s citation mode must match the style: numbered styles (`ieeetr`, `plain`)
need `\usepackage[numbers,sort&compress]{natbib}`; author-year styles (`apalike`,
`plainnat`) need plain `\usepackage{natbib}` with no option. Loading `natbib` in its
default author-year mode against a numbered `\bibliographystyle` fails to compile
(`natbib Error: Bibliography not compatible with author-year citations`) - if
`/synthesize` changes the citation style mid-report, update this package option too,
not just `\bibliographystyle`.

**`\citet{}` requires a natbib-compatible `.bst`** (`plainnat`, `apalike`,
`unsrtnat`) that stores author/year data separately in the `.bbl`. Plain numbered
styles like `ieeetr` and `plain` do **not** provide this, and `\citet{}` against one
of them silently renders `(author?)` in the compiled PDF instead of erroring - this
is exactly the kind of defect the Step 5b PDF inspection in `CLAUDE.md`'s
checklist exists to catch, but it's cheaper to just avoid the trap. With `ieeetr`/
`plain`, write the author name in prose and cite with `\citep{}` for the number
(e.g. `Lewis et al.~\citep{lewis2020rag}`) rather than relying on `\citet{}` to
generate it.

## The Fact-Check Pass

`/synthesize` spawns a reviewer agent with fresh context whose only job is checking
citations, not re-drafting prose. For every in-text `\cite{}` in the draft, the
reviewer:

1. Confirms the corresponding `.bib` entry exists and its `url` resolves to a real,
   fetchable source
2. Re-fetches that source and checks the claim in the draft's sentence actually appears
   in (or is a fair restatement of) the source's content
3. Flags any citation that is orphaned (no `.bib` entry), unused (`.bib` entry never
   cited), or unverifiable (claim doesn't match fetched content)

The reviewer's output is a pass/fail list per citation, which the drafter must resolve
- drop the claim, find a better source, or correct the claim - before the report is
considered final. This list is also what gets surfaced to the user in the final
Verification Checklist (see `CLAUDE.md`), so citation-checking is never silent.
