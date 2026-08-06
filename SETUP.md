# Setup Guide

Step-by-step instructions for getting the AI Research Assistant framework running.

## 1. Prerequisites

### Claude Code

Install Claude Code (Anthropic's CLI for Claude):

```bash
npm install -g @anthropic-ai/claude-code
```

You'll need an Anthropic API key or a Claude Pro/Team subscription. See the
[Claude Code docs](https://docs.anthropic.com/en/docs/claude-code) for details.

### Python

Python 3.10+ is required for the repo's lint and security-guard tooling. Check with:

```bash
python3 --version
```

On Windows, `py --version` is often the most reliable check. If your system exposes
Python as `python` instead of `python3`, use `python` in the commands below. The
lint tool also needs PyYAML: `pip install pyyaml`.

### Bun (for the connector CLIs)

The source-connector CLIs (`arxiv-search`, `semantic-scholar-search`,
`google-scholar-search`, `openalex-search`) and the `paper-fetch` full-text
downloader are written in TypeScript and run with Bun.

- macOS/Linux:

```bash
curl -fsSL https://bun.sh/install | bash
```

- Windows PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -c "irm https://bun.sh/install.ps1 | iex"
```

If you prefer a package manager, `winget install Oven-sh.Bun` also works on Windows.

All five CLIs have **zero runtime dependencies** — `bun install` only pulls
TypeScript dev types for the typechecker, so you can also just run them directly with
`bun run src/cli.ts` without installing anything.

### Optional API keys

`arxiv-search` and `openalex-search` work with no account at all.
`semantic-scholar-search` also works with no account, but benefits from one (see
below). `google-scholar-search` is different: **every request requires an API key**,
with no unauthenticated tier at all.

**SerpApi account (for `google-scholar-search`).** If you want Google Scholar's
broader cross-publisher coverage and its citation counts, sign up for a free key
(250 searches/month) at
[serpapi.com/users/sign_up](https://serpapi.com/users/sign_up), then:

```bash
export SERPAPI_API_KEY="your-key-here"
```

**Semantic Scholar key (optional, raises the rate limit).** Its unauthenticated pool
is shared globally across every caller and gets rate-limited often; a free key from
[semanticscholar.org/product/api](https://www.semanticscholar.org/product/api) moves
you to a dedicated 1 request/second quota:

```bash
export SEMANTIC_SCHOLAR_API_KEY="your-key-here"
```

**OpenAlex key (optional, raises the daily allowance).** Works with zero setup, but
unauthenticated requests get a small daily allowance (~10 searches/day; single-item
lookups are free regardless). A free key from
[openalex.org/settings/api](https://openalex.org/settings/api) raises this roughly
100x:

```bash
export OPENALEX_API_KEY="your-key-here"
```

Skipping all of these is fine - `/research` and `/synthesize` work with whatever
connectors are configured, and note in their output when one was skipped for lacking
a key or hitting a rate limit.

### Nothing extra for the web track

`/websearch` (blogs, engineering writeups, docs and specs → interactive HTML) needs
**no installation, no API key, and no LaTeX**. It runs on Claude Code's built-in web
search and writes a self-contained HTML page you open in any browser. If you only
want that track, you can skip Bun and LaTeX entirely and go straight to `/setup`.

### LaTeX (for compiling synthesis reports)

Install a LaTeX distribution to compile the generated `.tex` reports to PDF:

- **Windows:** [MiKTeX](https://miktex.org/download)
- **macOS:** [MacTeX](https://tug.org/mactex/)
- **Linux:** `sudo apt install texlive-full` or `sudo dnf install texlive-scheme-full`

Reports compile with `pdflatex` + `bibtex` (the standard 4-pass sequence:
`pdflatex → bibtex → pdflatex → pdflatex`), which every mainstream TeX distribution
ships out of the box — no extra packages required beyond what's in the preamble
(`geometry`, `hyperref`, `natbib`, `booktabs`).

#### Minimal TeX install: TinyTeX/BasicTeX

Full TeX distributions work out of the box. A minimal, user-level install also works
for this repo's report template since it only needs common packages:

```bash
# macOS, user-level, no sudo required
curl -sL "https://yihui.org/tinytex/install-bin-unix.sh" | sh
```

If a package is reported missing on compile, install it directly:

```bash
tlmgr install geometry hyperref natbib booktabs
```

## 2. Get the code

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

## 3. Install connector CLIs

```bash
for tool in arxiv-search semantic-scholar-search google-scholar-search openalex-search paper-fetch; do
  cd .agents/skills/$tool/cli && bun install && cd ../../../..
done
```

## 4. Verify your setup

```bash
python tools/lint_skills.py
python tools/security_guards.py
python -m unittest discover -s tests -t .
```

All three should pass on a fresh clone. Then check the connectors:

```bash
for tool in arxiv-search semantic-scholar-search google-scholar-search openalex-search paper-fetch; do
  (cd .agents/skills/$tool/cli && bun run typecheck && bun test)
done
```

And confirm the LaTeX toolchain works:

```bash
cd report
pdflatex -interaction=nonstopmode report_example.tex
bibtex report_example
pdflatex -interaction=nonstopmode report_example.tex
pdflatex -interaction=nonstopmode report_example.tex
# report_example.pdf should now exist with no `??` unresolved citations
rm -f *.aux *.log *.bbl *.blg *.out *.pdf
cd -
```

## 5. Run `/setup`

```bash
claude
# Then inside Claude Code:
/setup
```

This builds your researcher profile in `CLAUDE.md` and
`.claude/skills/research-assistant/01-researcher-profile.md`. From there, try
`/research <topic>` then `/synthesize <topic>` for the academic track, or
`/websearch <topic>` for the grey-literature one. Day-to-day usage, including the
rate limits that actually bite, is in [USAGE.md](USAGE.md).

## Troubleshooting

**`bun: command not found`** — Bun's installer adds itself to your shell profile, but
you may need to restart your shell or `source` the profile file it modifies.

**arXiv/Semantic Scholar requests failing or rate-limited** — Semantic Scholar's
unauthenticated pool is **shared globally across every unauthenticated caller**, not
per-user, so a `429` can happen even on your very first request of a session; it isn't
necessarily this CLI being over-used. arXiv asks integrators to keep to roughly one
request per 3 seconds with no concurrent connections. Both CLIs retry with exponential
backoff and, if every retry is exhausted, exit with `code: "RATE_LIMITED"` and an
explanatory message — Claude is instructed (see `.claude/commands/research.md`) not to
hand-retry that, but to fall back to the other connector or WebSearch instead. If you
hit this often on Semantic Scholar, get a free API key at
[semanticscholar.org/product/api](https://www.semanticscholar.org/product/api) and set
it as `SEMANTIC_SCHOLAR_API_KEY` in your shell — the CLI picks it up automatically and
moves you onto a dedicated per-key quota instead of the shared pool.

**`natbib Error: Bibliography not compatible with author-year citations`** — the
`natbib` package option must match your `\bibliographystyle`: numbered styles
(`ieeetr`, `plain`) need `\usepackage[numbers,sort&compress]{natbib}`; author-year
styles (`apalike`, `plainnat`) need plain `\usepackage{natbib}`. See
`04-citation-rules.md`.

**A citation renders as `(author?)` in the compiled PDF** — you're using `\citet{}`
with a `.bst` style that isn't natbib-compatible (e.g. `ieeetr`, `plain`). Write the
author name in prose and cite the number with `\citep{}` instead. See
`04-citation-rules.md`.
