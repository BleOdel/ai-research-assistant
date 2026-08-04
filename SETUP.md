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

The source-connector CLIs (`arxiv-search`, `semantic-scholar-search`) are written in
TypeScript and run with Bun.

- macOS/Linux:

```bash
curl -fsSL https://bun.sh/install | bash
```

- Windows PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -c "irm https://bun.sh/install.ps1 | iex"
```

If you prefer a package manager, `winget install Oven-sh.Bun` also works on Windows.

Both connectors have **zero runtime dependencies** — `bun install` only pulls
TypeScript dev types for the typechecker, so you can also just run them directly with
`bun run src/cli.ts` without installing anything.

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
for tool in arxiv-search semantic-scholar-search; do
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
cd .agents/skills/arxiv-search/cli && bun run typecheck && bun test && cd -
cd .agents/skills/semantic-scholar-search/cli && bun run typecheck && bun test && cd -
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
`/research <topic>` and `/synthesize <topic>`.

## Troubleshooting

**`bun: command not found`** — Bun's installer adds itself to your shell profile, but
you may need to restart your shell or `source` the profile file it modifies.

**arXiv/Semantic Scholar requests failing or rate-limited** — Semantic Scholar's
unauthenticated pool is tightly rate-limited; the CLI retries with exponential
backoff, but keep query volume low. arXiv asks integrators to be considerate of
request volume as well.

**`natbib Error: Bibliography not compatible with author-year citations`** — the
`natbib` package option must match your `\bibliographystyle`: numbered styles
(`ieeetr`, `plain`) need `\usepackage[numbers,sort&compress]{natbib}`; author-year
styles (`apalike`, `plainnat`) need plain `\usepackage{natbib}`. See
`04-citation-rules.md`.

**A citation renders as `(author?)` in the compiled PDF** — you're using `\citet{}`
with a `.bst` style that isn't natbib-compatible (e.g. `ieeetr`, `plain`). Write the
author name in prose and cite the number with `\citep{}` instead. See
`04-citation-rules.md`.
