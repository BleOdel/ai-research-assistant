# AI Research Assistant

*The research assistant that runs on your machine.*

An AI-powered research framework built on [Claude Code](https://claude.com/claude-code).
Fork it, describe what you research, and let Claude discover academic sources, score
their relevance, and synthesize a cited, compiled state-of-the-art report.

## What this is

A structured workflow that turns Claude Code into a literature-discovery and
synthesis assistant. The core loop — discover sources, score them, draft a cited
report, fact-check every citation with a second agent, compile to PDF — is
field-agnostic. The three shipped connector skills (arXiv, Semantic Scholar, Google
Scholar) cover academic search broadly; the pattern is designed to extend to other
source databases.

```
/setup          /research <topic>        /synthesize <topic>
  |                    |                        |
  v                    v                        v
Fill in          Search arXiv +           Score sources,
your profile     Semantic Scholar         draft LaTeX report
  |                    |                        |
  v                    v                        v
Profile           Present matches          Reviewer agent
ready              with relevance          fact-checks every
                   triage                  citation
                       |                        |
                       v                        v
                  Pick sources             Compile + verify
                  -> /synthesize           -> cited PDF report
```

The framework's central rule: **every claim in a synthesis report traces to a source
that was actually fetched during the run.** A citation that can't be verified against
fetched content is a defect, not a stylistic nitpick.

## Prerequisites

- [Claude Code](https://claude.com/claude-code) (CLI)
- [Bun](https://bun.sh) (for the connector CLI tools)
- Python 3.10+ (for the repo's lint/security-guard tooling)
- LaTeX distribution with `pdflatex` and `bibtex`: [TeX Live](https://tug.org/texlive/),
  [MacTeX](https://tug.org/mactex/), [MiKTeX](https://miktex.org/), or
  [TinyTeX](https://yihui.org/tinytex/)/[BasicTeX](https://tug.org/mactex/morepackages.html)
  for a minimal install. See [SETUP.md](SETUP.md) for details.

## Quick start

### 1. Get the code

If this is your own repo, just clone it:

```bash
git clone https://github.com/BleOdel/ai-research-assistant.git
cd ai-research-assistant
```

If you're starting from someone else's copy of this framework, fork it instead (a
GitHub account can't fork its own repo):

```bash
gh repo fork <owner>/ai-research-assistant --clone
cd ai-research-assistant
```

### 2. Install connector tools

```bash
for tool in arxiv-search semantic-scholar-search google-scholar-search; do
  cd .agents/skills/$tool/cli && bun install && cd ../../../..
done
```

All three connectors have **zero runtime dependencies** — `bun install` only pulls
TypeScript dev types, so this step is optional if you just want to run them with
plain `bun`. `google-scholar-search` additionally needs a `SERPAPI_API_KEY` (a free
SerpApi account, 250 searches/month) before it'll actually run - see
[Source connectors](#source-connectors) below. Without it, `/research` and
`/synthesize` still work fine with the other two.

### 3. Set up your profile

```bash
claude
# Then inside Claude Code:
/setup
```

`/setup` offers four paths: point it at your `documents/` folder (CV, LinkedIn
export, your own publications - see `documents/README.md`), paste an existing reading
list or notes, describe your interests in a paragraph, or walk through an interview.

### 4. Discover sources

```bash
/research retrieval-augmented generation
```

Searches arXiv and Semantic Scholar for the topic, deduplicates against prior runs,
and presents matches with a quick relevance triage.

### 5. Synthesize a report

```bash
/synthesize retrieval-augmented generation
```

Scores the discovered sources against the full evaluation rubric, drafts a cited
LaTeX report, spawns a fact-checking agent to verify every citation against its
actual source, compiles the report to PDF, and runs a verification checklist before
presenting it.

## Commands

- **`/setup`** builds your researcher profile (interests, expertise level, citation
  style, output preferences).
- **`/research <topic>`** discovers sources via the connector CLIs, deduplicates
  against previous runs, and triages by relevance.
- **`/rank`** batch-scores a large `/research` haul against the full evaluation
  rubric via parallel agent dispatch, returning a ranked shortlist before you commit
  to a full `/synthesize` pass. Bridges `/research` and `/synthesize` the way triage
  scores bridge a rough list and a real decision.
- **`/synthesize <topic>`** runs the full drafter-reviewer workflow: score sources,
  draft a report, fact-check every citation, compile and verify the PDF.
- **`/reset [profile|documents|research|reports|all]`** wipes profile data,
  `documents/` content, discovery state, or compiled reports back to a blank slate.
  Shows exactly what will be deleted and requires typing `RESET` to confirm - nothing
  is deleted until you do.

## File structure

```
ai-research-assistant/
├── CLAUDE.md                              # Researcher profile + workflow rules
├── .claude/
│   ├── commands/
│   │   ├── setup.md                       # /setup onboarding
│   │   ├── research.md                    # /research source discovery
│   │   ├── rank.md                        # /rank batch-triage into a shortlist
│   │   ├── synthesize.md                  # /synthesize drafter-reviewer workflow
│   │   └── reset.md                       # /reset wipe profile/documents/research/reports
│   ├── skills/
│   │   └── research-assistant/            # Core research skill
│   │       ├── SKILL.md
│   │       ├── 01-researcher-profile.md   # Interests, expertise, preferences
│   │       ├── 02-source-evaluation.md    # Relevance/rigor/recency/impact scoring
│   │       ├── 03-report-templates.md     # LaTeX report structure
│   │       ├── 04-citation-rules.md       # Citation style, verify-before-cite rule
│   │       └── 05-subject-index.md        # Subject-organized paper index format/rules
│   └── settings.json                      # Claude Code permissions (scoped)
├── .agents/skills/                        # Source connector CLIs
│   ├── arxiv-search/                      # arXiv Export API (preprints, CS/physics/math/stats)
│   ├── semantic-scholar-search/           # Semantic Scholar Graph API (cross-field, citations)
│   └── google-scholar-search/             # Google Scholar via SerpApi (broadest coverage, needs API key)
├── report/
│   ├── report_example.tex                 # LaTeX report template (article + BibTeX)
│   └── references.bib                     # Example bibliography
├── documents/                              # Your CV, LinkedIn export, publications - /setup Path A
│   ├── README.md
│   ├── cv/
│   ├── linkedin/
│   └── publications/
├── research/                              # Discovery state (seen_sources.json, papers_by_subject.md)
├── reports/                               # Compiled synthesis reports (per topic)
├── tools/
│   ├── lint_skills.py                     # CI lint for skills, commands, settings.json
│   └── security_guards.py                 # CI guards: permission allowlist, gitignore rules, manifests
├── tests/
│   └── test_security_guards.py
├── .github/workflows/ci.yml               # CI: LaTeX smoke compile, skill lint, CLI typechecks
└── SETUP.md                               # Detailed setup guide
```

## How `/synthesize` works

1. **Score** every candidate source against `02-source-evaluation.md`'s four
   dimensions (Relevance, Recency, Rigor, Impact).
2. **Draft** a LaTeX report: abstract, background, thematic sections (organized by
   approach, not a flat per-paper list), a comparison table where approaches are
   genuinely comparable, and an explicit Open Questions section.
3. **Fact-check.** A second agent, spawned with fresh context, re-fetches every
   cited source and verifies the claim attributed to it actually appears there. This
   is the drafter-reviewer split, applied to citation accuracy instead of prose
   critique.
4. **Revise** based on the reviewer's findings — every flagged citation must be
   resolved before compiling.
5. **Compile and inspect.** The 4-pass `pdflatex → bibtex → pdflatex → pdflatex`
   sequence, then Claude reads the rendered PDF and fixes any layout or citation
   rendering defects before presenting it.

### What makes this different from asking an LLM to "write a literature review"

- **Citations are verified, not generated.** The reviewer agent's only job is
  checking that every `\cite{}` resolves to a real, fetched source whose content
  actually supports the claim next to it — the single most common way an AI-written
  literature review goes wrong.
- **Compiled PDF verification is mandatory.** A `.tex`/`.bib` pair that looks correct
  can still fail to compile, mis-render the bibliography, or leave `??` where a
  citation should resolve. The workflow never presents an uncompiled or unverified
  draft as done.
- **Structured relevance scoring, not vibes.** Every source that enters a report is
  scored against a fixed four-dimension rubric, so relevance judgments are
  consistent across a run and across runs.

## Customization

### Citation style and report depth

Set in your profile (`.claude/skills/research-assistant/01-researcher-profile.md`,
populated by `/setup`): citation style (IEEE/APA/plain/author-year), default report
depth (quick brief vs. deep review), and audience. `04-citation-rules.md` documents
which `\bibliographystyle` and `natbib` package option each citation style maps to.

### Source connectors

Three shipped connectors cover academic search from different angles:

- **`arxiv-search`** — arXiv Export API. No account needed. Preprints only, CS/
  physics/math/stats coverage.
- **`semantic-scholar-search`** — Semantic Scholar Graph API. No account needed for
  basic use, but its unauthenticated pool is shared globally across every caller and
  is often rate-limited; an optional free `SEMANTIC_SCHOLAR_API_KEY` gets a dedicated
  quota.
- **`google-scholar-search`** — Google Scholar via SerpApi. Broadest cross-publisher
  coverage and the most reliable citation counts, but **requires a SerpApi account
  and API key for every single request** (free tier: 250 searches/month) - there is
  no unauthenticated option at all. It also has a `cited-by` command the other two
  don't: find papers that cite a specific work.

All three are self-contained TypeScript CLIs under `.agents/skills/` with zero
runtime dependencies — see each one's `SKILL.md` for exact flags
(`.agents/skills/<name>/SKILL.md`). `/research` discovers installed connectors by
globbing `.agents/skills/*/SKILL.md`, so a connector missing its API key (or not
installed at all) doesn't break discovery - it's just skipped in favor of the others,
with the gap noted in the output. Adding a new source database (PubMed, OpenAlex, a
domain-specific archive) means writing a new connector skill in the same shape; there
is no generator command for this yet (see below).

## Scope

This is a lean build: profile setup, three academic connectors, source discovery,
and synthesis with citation verification. Deliberately not (yet) built:

- A `/rank` command to batch-triage a large `/research` haul before committing to a
  full `/synthesize` pass
- Further connectors (OpenAlex, PubMed, GitHub/HN for industry signal)
- An `/add-source` generator for scaffolding new connector skills
- Living-document mode (re-synthesizing a tracked topic to append only what's new)
- Contradiction/consensus flagging across sources
- Scheduled monitoring of tracked topics

## Acknowledgements

Architecture and workflow pattern adapted from
[ai-job-search](https://github.com/MadsLorentzen/ai-job-search) by Mads Lorentzen —
the same drafter-reviewer, compile-and-inspect, and connector-skill patterns,
retargeted from job applications to literature synthesis.

Built with [Claude Code](https://claude.com/claude-code) by [Anthropic](https://anthropic.com).

## License

MIT
