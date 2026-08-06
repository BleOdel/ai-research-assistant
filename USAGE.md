# Usage Guide

How to actually use this framework day to day. For installation and API keys, see
[SETUP.md](SETUP.md) first.

Everything below is written from real runs, including the rate limits and failure
modes you will hit in practice.

---

## Command reference

Type these **inside Claude Code**, not in your shell.

| Command | Purpose |
|---------|---------|
| `/setup` | Build your researcher profile (run once) |
| `/research <topic>` | Discover sources across all connectors, dedup, quick triage |
| `/websearch <topic>` | Grey-literature track: blogs, docs, specs → interactive HTML |
| `/rank` | Batch-score a large haul against the full rubric, return a shortlist |
| `/synthesize <topic> [nums\|all]` | Score → draft → fact-check → compile → verify |
| `/update <topic>` | Refresh an existing report in place, with a dated Revision History |
| `/defend <topic> [context]` | Presentation/viva prep pack + mock Q&A |
| `/outcome [topic]` | Record what happened to a report after the fact |
| `/expand` | Enrich your profile from `documents/`, Google Scholar, GitHub |
| `/add-source` | Generate a new source-database connector |
| `/add-template` | Register a custom LaTeX report format |
| `/reset [scope]` | Wipe profile / documents / research / reports / blog |

---

## 1. First-time setup

```
/setup
```

Offers four paths — pick whichever matches what you already have:

- **A — Documents folder.** Drop your CV, LinkedIn export, and publications into
  `documents/{cv,linkedin,publications}/` first, then let `/setup` read them. Richest
  starting point. Anything it infers rather than reads directly is labeled
  `*[Inferred from ... - review before relying on this]*`.
- **B — Reading list import.** Paste an existing bibliography or notes.
- **C — Free-text.** Describe your interests in a paragraph.
- **D — Interview.** Answer questions one at a time.

This writes `CLAUDE.md` and
`.claude/skills/research-assistant/01-researcher-profile.md`. Your **Research
Interests** matter most: they drive relevance scoring, subject classification, and
how deep reports go. Set `Default report depth` (quick brief ~4-5pp vs. deep review
10+pp) and `Citation style` (IEEE / APA / plain / author-year) here too.

You should not need `/setup` again unless you want to rebuild from scratch.

---

## 2. The core loop

Three commands, in order. This is the 90% case.

### Discover

```
/research retrieval-augmented generation for code search
```

Queries every installed connector **in parallel**, deduplicates against every source
you have ever seen (`research/seen_sources.json`), and returns a table with a cheap
high/medium/low triage.

It deliberately does **not** score properly here — full scoring across raw search
results would be wasteful, and `/synthesize` re-scores anyway.

If a connector is rate-limited or missing its API key, `/research` says so in the
output rather than silently under-reporting coverage. Read that line: it tells you
how complete the sweep actually was.

### Triage (optional)

```
/rank
```

Worth running at roughly **8+ new sources**. It dispatches parallel agents (~5
sources each) to score everything against the full four-dimension rubric, then
returns a ranked shortlist. It never fact-checks or drafts — it exists purely to
help you decide where to spend a full synthesis pass.

Skip it for small hauls.

### Synthesize

```
/synthesize retrieval-augmented generation for code search 1,3,4,7
```

Pass source numbers from the `/research` table, or `all`. This is the expensive
command, and it runs five stages:

1. **Score** each source on Relevance (40%), Rigor (25%), Impact (20%), Recency
   (15%). Shows you the table and asks before drafting — you can veto sources here.
2. **Draft** the LaTeX report: abstract, thematic sections organized by approach
   (never a flat per-paper list), a plain-language Technical Findings section, a
   comparison table where approaches are genuinely comparable, and explicit Open
   Questions.
3. **Fact-check.** A separate agent with fresh context re-fetches every cited source
   — full text via `paper-fetch` where an open-access PDF exists, abstract otherwise
   — and verifies the claim attributed to it actually appears there.
4. **Revise.** Every flagged citation must be resolved before compiling.
5. **Compile and inspect.** 4-pass `pdflatex → bibtex → pdflatex → pdflatex`, then
   the rendered PDF is read back and checked for `??`, layout breaks, and
   bibliography errors.

Output: `reports/<topic-slug>/report.tex`, `references.bib`, `report.pdf`.

> **Expect the fact-checker to find things.** In development it caught a citation
> attributed to the wrong paper, a factually wrong claim about a paper's evaluation
> scope, and two cases where a figure was wrongly described as unavailable. That is
> the system working. Findings from the reviewer should themselves be verified
> before you act on them — it is another agent, not an oracle.

---

## 2b. The grey-literature track

Peer-reviewed papers are not the only useful evidence. Practitioner blogs,
engineering writeups, official documentation, and specs are faster, more concrete,
and often the only written record of how something behaves in production. They are
also unreviewed, and frequently written by someone with a commercial interest.

```
/websearch WebXR permission model in production
```

One command does discovery, credibility scoring, and the build. Output is a
**self-contained interactive HTML page** at `blog/<topic-slug>/index.html` — open it
directly in a browser, no server needed. Filter by text, tier, or content type; sort
by score, date, authority, or evidence; click any source to expand its detail.

### Why it's a separate track

|  | Academic | Web |
|---|---|---|
| Rubric | Relevance 40 / **Rigor** 25 / **Impact** 20 / Recency 15 | Relevance 30 / **Authority** 25 / **Evidence** 25 / Recency 20 |
| Core threshold | 75+ | 70+ |
| State | `research/seen_sources.json` | `blog/seen_web_sources.json` |
| Output | LaTeX → PDF | Interactive HTML |

*Rigor* needs a venue and *Impact* needs citations — a blog has neither. They're
replaced by **Authority** (who wrote this, do they have standing here) and
**Evidence Quality** (are claims shown with code, benchmarks, and versions, or
merely asserted). Recency is weighted higher because grey literature decays faster.

**A Core web source is not equivalent to a Core paper.** The thresholds are lower
because the ceiling is lower. The page's footer says so.

### The three rules that matter here

**Independence is labeled on every source** — `independent`, `first-party`,
`vendor-competitive`, `sponsored`, or `unclear`. This is a *label, not a penalty*: a
vendor's own engineering blog is often the single best source on their system.
You just get told which you're reading, and comparative claims from interested
parties are attributed in the prose rather than stated as fact.

**Single-source claims are attributed opinion, not fact.** And the command checks
whether apparent corroboration actually traces back to one origin — the specific
failure mode where one confident post gets quoted by three others until an unsourced
assertion looks like consensus.

**Nothing is evaluated from a search snippet.** Snippets are optimized for your
query, not for accuracy; every source is fetched and read, or recorded as
unfetchable.

### Keep the tracks separate

Don't cite a blog post in a `/synthesize` report as though it were peer-reviewed. If
a web source genuinely belongs in an academic report — a standard, a spec, a dataset
release page — cite it as a `@misc` entry with an access date and say in the prose
that it isn't peer-reviewed.

`/websearch` uses the built-in `WebSearch`, not a connector CLI — deliberately, so
it costs nothing against your 250-per-month SerpApi quota.

---

## 3. The report lifecycle

A synthesis report is a living document, not a one-off.

### `/update` — keep it current

```
/update retrieval-augmented-generation-for-code-search
```

Re-runs discovery, scores what is genuinely new, and **merges it into the existing
report in place** — extending themes, revising contradicted claims, retiring
answered Open Questions — then appends a dated entry to a Revision History section.

Design rules worth knowing:

- **The body is always current; only the Revision History is append-only.** You will
  never find a stale claim sitting next to an "Update: actually…" correction.
- **Fact-check scope matches change scope** — only new and revised claims are
  re-verified, which is what makes an update much cheaper than a fresh synthesis.
- **A contradiction of your headline conclusion stops the run** and asks you. That is
  a rewrite decision, not an update.
- **"Nothing new since <date>" is a valid outcome.** It refreshes the checked-through
  date and stops, rather than padding a changelog.

### `/defend` — prepare to present it

```
/defend retrieval-augmented-generation-for-code-search viva
```

Builds a prep pack for a supervisor meeting, lab talk, conference, or thesis viva.
Likely questions are seeded, in priority order, from:

1. **Your report's own Open Questions section** — a sharp questioner's first move is
   almost always to probe the gaps the report already discloses.
2. Sources with a weaker (abstract-only) evidence basis.
3. Sources that were scored but **excluded** — "why didn't you include X?" gets the
   real score as an answer, not an improvised justification.
4. Disclosed methodological choices.
5. Standard hard questions, rephrased against your actual content.

Name a specific audience member and it will research their published work for
genuine tensions with your conclusions. It also offers a mock Q&A roleplay with
feedback after each answer. Saves to
`reports/<topic-slug>/defense_prep_<context>.md`.

Answers are grounded only in what the report supports — where the honest answer is
"the literature doesn't resolve this," that is what it prepares you to say.

### `/outcome` — close the loop

```
/outcome retrieval-augmented-generation-for-code-search
```

Records what happened: `presented`, `cited` (in your own later work),
`needs_revision`, `superseded`, or back to `active`. Writes to
`research_tracker.csv` (created on first use) and an append-only
`reports/<topic-slug>/outcome.md` log.

If several reports in one subject area keep going stale, it will say so and suggest
recalibrating — but it never edits your profile or scoring rubric itself. That stays
your decision.

---

## 4. Maintenance and extension

### `/expand` — grow your profile

```
/expand
```

Scans `documents/`, runs a Google Scholar `author:"<Your Name>"` search for your own
publications, and optionally checks a GitHub username. Proposes new research
sub-areas and landmark works. **Additive only, source-labeled, and confirms before
writing anything.**

### `/add-source` — add a database

```
/add-source PubMed
```

Investigates the target API's real documentation, then scaffolds a connector
matching the established contract (same commands, flags, JSON shape, and error
codes as the shipped four), with fixture tests and a mandatory live test run before
it is registered. `/research` discovers connectors dynamically, so there is no
query-list file to update afterwards.

Declines databases with no free/public access path.

### `/add-template` — custom report formats

```
/add-template
```

```
/add-template --list
```

```
/add-template --use thesis-chapter
```

Registers a custom LaTeX format (thesis chapter, ACM/IEEE two-column) with a
mandatory test compile that exercises a real bibliography. Supports classic `bibtex`
or `biblatex`+`biber`. Once active, `/synthesize` drafts into it instead of the stock
`article` structure.

### `/reset` — start over

```
/reset research
```

Scopes: `profile`, `documents`, `research`, `reports`, `blog`, `all`. Shows exactly
what will be deleted and requires you to type `RESET` — nothing is removed until you
do.

`blog` clears `/websearch` scans and their discovery state while preserving
`blog/template.html` and `blog/README.md` — those are framework files, not your data,
and deleting them would break the next scan. The academic and web tracks are separate
scopes, so `/reset research` never touches your web scans and vice versa; only `all`
clears both.

---

## 5. Operational rules that matter

### Rate limits

| Connector | Limit | Notes |
|-----------|-------|-------|
| **arXiv** | No key, generous | Your workhorse for CS/physics/math/stats |
| **Semantic Scholar** | 1 req/sec with a key | Unauthenticated pool is shared **globally** and often limited |
| **Google Scholar** | 250 searches/month (SerpApi) | Your scarcest resource — do not burn it on exploration |
| **OpenAlex** | ~10 searches/day unauthenticated | Single-paper lookups are **free and unlimited** regardless |

A free `OPENALEX_API_KEY` raises its allowance roughly 100×. If you use this
framework more than occasionally, get one.

**Never hand-retry a `RATE_LIMITED` or `NO_API_KEY` error.** The CLI already
exhausted its own exponential backoff; a manual retry burns time against a limit
that needs real wall-clock recovery. `NO_API_KEY` is not transient at all. The
commands know this — if you see a retry loop, stop it.

**One well-formed query per connector beats four variants at one connector.** Firing
several phrasings at the same database is the fastest way to trip its rate limit,
and the marginal coverage is small. Breadth comes from using *all* the connectors,
not from re-asking one of them.

### Evidence basis

Every source carries a `fulltext` or `abstract` marker. `paper-fetch` downloads
open-access PDFs automatically during scoring and fact-checking, but paywalled
papers stay abstract-only — and the report says so explicitly rather than presenting
abstract-level claims as full-text-verified.

**When citing this framework's output in your own work, check that marker.**

`paper-fetch` never scrapes paywalled publisher sites. When it reports `NO_OA_PDF`
for an open-access paper whose landing page serves HTML, the error includes that
URL — visiting it, finding the direct PDF link, and passing it back in is following
the paper's own published open-access trail, and is fine.

### Citation counts are not one number

Databases index independently and diverge substantially. Observed on the same paper
on the same day: **25 (OpenAlex) / 34 (Semantic Scholar) / 58 (Google Scholar)**.
Always note which database a count came from, and never mix sources in one
comparison table without labeling each.

### Venue claims need primary sources

A secondary database tagging a preprint with a conference is *not* confirmation.
Check the venue's own proceedings site, or a registered DOI that resolves. In
development this mattered twice: one preprint's tag was genuinely unconfirmed for
months (and was deliberately not upgraded), while another paper's tag turned out to
be correct and verifiable on the publisher's own site.

### Your research output stays local

Reports, `research/seen_sources.json`, `research/fulltext/`, `documents/`, and
`research_tracker.csv` are all gitignored — enforced in CI by
`tools/security_guards.py`. Only the framework itself goes to GitHub.

If you want your reports version-controlled, use a **separate private repo** rather
than loosening these ignore rules.

---

## 6. Where everything lives

```
reports/<topic-slug>/
    report.tex, report.pdf, references.bib   the report itself
    defense_prep_<context>.md                from /defend
    outcome.md                               from /outcome
research/
    seen_sources.json     every source ever seen, with scores and verdicts
    papers_by_subject.md  master index, grouped by research interest
    fulltext/             cached open-access PDFs
documents/
    cv/ linkedin/ publications/   your own materials (for /setup and /expand)
research_tracker.csv      report status overview (created by /outcome)
blog/
    template.html         interactive report shell (tracked, editable)
    seen_web_sources.json web discovery state
    <topic-slug>/         index.html + sources.json from /websearch
templates/                custom formats from /add-template
```

**`research/papers_by_subject.md` is the file to open** when you want to see
everything you have covered — one table per research interest, with scores,
verdicts, evidence basis, and status. It is fully regenerated from
`seen_sources.json` on every run, so never hand-edit it.

### Source statuses and verdicts

`seen_sources.json` statuses: `new`, `skipped`, `ranked`, `unfetchable`,
`synthesized`.

Score verdicts: **Core** (75+, cite substantively), **Supporting** (55-74, cite for
context), **Peripheral** (35-54, only if it fills a real gap), **Excluded** (<35).

---

## 7. How the reasoning is configured

The rules the assistant follows live in
`.claude/skills/research-assistant/` and are worth reading — and editing — if you
want to change its judgment:

| File | Controls |
|------|----------|
| `01-researcher-profile.md` | Your interests, expertise level, output preferences |
| `02-source-evaluation.md` | The four-dimension rubric, weights, thresholds |
| `03-report-templates.md` | Report structure, section rules, length calibration |
| `04-citation-rules.md` | Citation styles, BibTeX rules, verify-before-cite |
| `05-subject-index.md` | How papers are classified into subject areas |
| `06-defense-prep.md` | Where `/defend`'s questions come from |
| `07-fulltext.md` | When full text is fetched instead of abstracts |
| `08-living-updates.md` | How `/update` merges new work |
| `09-web-source-evaluation.md` | The web credibility rubric and independence labels |
| `10-html-reports.md` | The interactive HTML output format |

Changing the scoring weights in `02-source-evaluation.md`, for example, changes how
every future `/rank` and `/synthesize` judges sources.

---

## Troubleshooting

See [SETUP.md](SETUP.md#troubleshooting) for LaTeX errors (`natbib` style
mismatches, `(author?)` citations), Bun installation, and connector rate-limit
recovery.
