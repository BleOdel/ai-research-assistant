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
- **`evidencebasis` recording the evidence basis** - how this source's content was
  obtained, and anything the reader needs in order to weigh the citation. This is
  required, not optional. It opens with one of two forms and ends with two labelled
  parts:
  - Full text read: `evidencebasis = {Primary PDF read via paper-fetch on YYYY-MM-DD;
    abstract read via <connector> on YYYY-MM-DD. Disclosure: <label>. Caveat: <text>.}`
  - Abstract only: `evidencebasis = {Abstract-only evidence basis: <why no full text
    - e.g. IEEE paywall, no preprint found>; abstract read via <connector> on
    YYYY-MM-DD. Disclosure: <label>. Caveat: <text>.}`

  `<label>` is the source's disclosure label from `02-source-evaluation.md`
  (`academic`, `industry`, `self-evaluating`, `vendor-report`, `unclear`). The caveat
  is what a reader must weigh before relying on a claim from this source: a venue
  confirmed against the publisher rather than a database tag, a preprint whose
  published version could not be located, a figure that holds only under one
  condition. Keep `Caveat:` last.

  The Evidence Basis table is generated from these fields, not written by hand:
  ```bash
  python3 tools/evidence_table.py reports/<topic_slug> --write
  ```
  It reads "Full text" or "Abstract" from the opening, the route from the first
  "via", and the label and caveat from their prefixes (a missing part renders as
  "--"). It replaces the report's Evidence Basis section, or inserts one before
  `\bibliographystyle`. The caveat is copied into the table verbatim, so **escape
  `%`, `&`, `#` and `_` in it as `\%`, `\&`, `\#`, `\_`** (an unescaped `%` comments
  out the rest of the row and the compile fails with "Extra alignment tab"); text
  inside `\url{...}` needs no escaping. The generator refuses a field with an
  unescaped character, and `check_report.py` reports the same thing as an error.

  **Use `evidencebasis`, not `note`, deliberately.** `note` is a standard BibTeX field
  that every shipped citation style (`ieeetr`, `plain`, `apalike`, `agsm`, `plainnat`) prints
  inline in the rendered bibliography - which is exactly what produced a wall of
  evidence-basis prose after every reference entry before this rule existed.
  `evidencebasis` is not a field any stock `.bst` style recognizes, so BibTeX silently
  ignores it when typesetting: the data survives in the `.bib` file, machine-readable
  and available to `/gaps`, `/update`, and any future connector, but nothing renders
  next to the citation itself. The reader instead sees this same information collected
  in the **Evidence Basis** section (`03-report-templates.md`, Section 8) - one table,
  once, rather than repeated prose after every single reference.

  `note` remains available for genuinely short bibliographic facts that belong next to
  a citation - a venue clarification like `note = {NDSS Symposium}` when a `.bib`
  entry type doesn't otherwise carry venue - but never for evidence-basis, disclosure,
  or attribution commentary.

  This exists because it was previously done only when a human was in the loop asking
  for it: of four reports produced by this framework, one carries evidence-basis notes
  on 11 of 14 entries and the other three carry none at all.

Never fabricate a field. If a preprint has no venue, the entry is a `@misc` or
`@article` with `eprint`/`archivePrefix` set - it does not get a fake `journal` field
to look more legitimate.

**Brace acronyms and system names in titles.** Every supported style sentence-cases
titles, lowering every word after the first, so an unbraced `LLM` prints as "llm" and
`AgentDojo` as "agentdojo". Write `title = {{AgentDojo}: Defending {LLM} Agents}`. Leave
ordinary capitalised words, including hyphenated ones like `Rule-Based`, unbraced; sentence
case is meant to lower those. `check_report.py` warns about titles that need this.
Harvard (`agsm`) makes the problem most visible, but numbered styles do the same.

## Citation Style

Use the style set in `01-researcher-profile.md`'s `Citation style` field. Default:
**IEEE** (numbered, `\bibliographystyle{ieeetr}`) since the shipped connectors skew
CS/ML (arXiv especially; OpenAlex is the one with broad non-CS coverage). Other
supported values map to standard BibTeX styles:

| Profile value | `\bibliographystyle{}` | Extra install needed? |
|----------------|------------------------|------------------------|
| IEEE | `ieeetr` | No - stock TeX Live |
| APA | `apalike` | No - stock TeX Live |
| Harvard | `agsm` | **Yes** - see below |
| Plain/numbered | `plain` | No - stock TeX Live |
| Author-year | `plainnat` (requires `natbib`, already loaded per `03-report-templates.md`) | No - stock TeX Live |

`natbib`'s citation mode must match the style: numbered styles (`ieeetr`, `plain`)
need `\usepackage[numbers,sort&compress]{natbib}`; author-year styles (`apalike`,
`agsm`, `plainnat`) need plain `\usepackage{natbib}` with no option. Loading `natbib`
in its default author-year mode against a numbered `\bibliographystyle` fails to
compile (`natbib Error: Bibliography not compatible with author-year citations`) - if
`/synthesize` changes the citation style mid-report, update this package option too,
not just `\bibliographystyle`.

**`\citet{}` requires a natbib-compatible `.bst`** (`plainnat`, `apalike`, `agsm`,
`unsrtnat`) that stores author/year data separately in the `.bbl`. Plain numbered
styles like `ieeetr` and `plain` do **not** provide this, and `\citet{}` against one
of them silently renders `(author?)` in the compiled PDF instead of erroring - this
is exactly the kind of defect the Step 5b PDF inspection in `CLAUDE.md`'s
checklist exists to catch, but it's cheaper to just avoid the trap. With `ieeetr`/
`plain`, write the author name in prose and cite with `\citep{}` for the number
(e.g. `Lewis et al.~\citep{lewis2020rag}`) rather than relying on `\citet{}` to
generate it.

### Harvard style specifically

`agsm.bst` is the standard UK Harvard author-year style (Author, Initial. (Year)
'Title', Journal.). It is **not** part of a stock/minimal TeX Live install
(`scheme-basic`, TinyTeX, BasicTeX) - it ships in the separate `harvard` bundle,
originally written to pair with a `harvard.sty` package this framework does not use.
Empirically verified (2026-08-27): `natbib` alone, already loaded by every report
this framework produces, provides compatibility shims for `agsm.bst`'s
`\harvarditem`/`\harvardand`/`\harvardyearleft` commands, so **`harvard.sty` itself is
never needed** - only the `.bst` file. `\citet{}` and `\citep{}` both render
correctly against it; confirmed by a real compile with zero undefined-control-sequence
errors.

If `\bibliographystyle{agsm}` fails to compile with "I couldn't open style file
agsm.bst," the bundle isn't installed on that machine. Fix, no admin/sudo required:

```bash
tlmgr --usermode install harvard
```

(`tlmgr init-usertree` first, one-time, if user mode hasn't been set up before.) A
full TeX Live install (`scheme-full`, full MacTeX) may already include it. **Do not
silently fall back to `apalike` if `agsm` fails to compile** - `apalike` is APA
formatting, not Harvard, and a user who asked for Harvard would get a different style
labeled as the one they chose. Tell the user the exact command above instead.

**Every Harvard report redefines `\harvardurl`.** `agsm.bst` prints each entry's
`url` field as `\harvardurl{...}`, and natbib's shim for it is plain italic text
(`\textbf{URL:} \textit{#1}`), so the first URL containing `_`, `%` or `#` breaks the
build - `_` gives "Missing $ inserted" in the `.bbl`, `%` "File ended while scanning
use of \harvardurl", `#` "Illegal parameter number". Found 2026-10-02 on a real
`/update`. Put this line right after `\usepackage{natbib}`, with `hyperref` (which
provides `\url`) loaded before it:

```latex
\renewcommand{\harvardurl}{\textbf{URL:} \url}
```

It deliberately takes **no argument**: `\url` then reads the URL itself, with its
own catcodes, so all three characters survive. The tempting
`\renewcommand{\harvardurl}[1]{\textbf{URL:} \url{#1}}` fixes `_` but still fails
on `%` and `#`, because the URL was already tokenized when `\harvardurl` grabbed it
(verified by compiling each case). `tools/check_report.py` fails a Harvard report
without the override, and warns on the one-argument form.

**Every Harvard report also sets the author-year comma.** `agsm` writes
"(Karpukhin et al. 2020)"; most UK guides, Cite Them Right among them, want
"(Karpukhin et al., 2020)" and a semicolon between citations. One line, after the
`\harvardurl` override, gives both:

```latex
\setcitestyle{aysep={,}}
```

Textual citations are unaffected: `\citet` still prints "Karpukhin et al. (2020)".
Verified 2026-10-04 by compiling the prompt-injection report with and without it (no
layout change). `tools/check_report.py` warns when a Harvard report lacks it.

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
