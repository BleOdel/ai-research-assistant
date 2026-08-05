# Templates Folder

Custom LaTeX report templates registered via `/add-template`, used in place of the
stock `report/report_example.tex` structure when drafting a `/synthesize` report.

---

## Folder Structure

```
templates/
├── <template-name>/
│   ├── template.tex       # The template skeleton ([PLACEHOLDER] tokens, not real content)
│   ├── TEMPLATE.md        # Manifest: compile engine, bibliography engine, required
│   │                      # sections, style rules, known pitfalls
│   ├── *.cls / *.sty      # Any custom class/style files the template needs
│   └── fonts/             # Any bundled font files
└── README.md               # This file
```

---

## Why this exists

The stock report template (`report/report_example.tex`) is a plain `article`-class
document with a BibTeX bibliography - deliberately generic so it compiles anywhere
with zero extra setup. If you need a specific format instead - a university thesis
chapter with a mandated section structure, an ACM/IEEE two-column conference paper
format, a lab-specific report template - register it with `/add-template` instead of
hand-editing `03-report-templates.md` every time.

Only one template can be **active** at a time. `/synthesize` checks
`.claude/skills/research-assistant/03-report-templates.md` for an
`ACTIVE-TEMPLATE` managed block before drafting; if one is present, it drafts from
the registered template instead of the stock structure.

## Commands

- `/add-template` - register a new template (interviews you for its requirements,
  runs a mandatory test compile including a working bibliography, then activates it)
- `/add-template --list` - see all registered templates and which one (if any) is
  active
- `/add-template --use <name>` - switch the active template
- `/add-template --use default` - deactivate any custom template and revert to the
  stock `report/report_example.tex` structure

## A note on bibliographies

Report templates are different from CV/cover-letter templates in one important way:
they have a working bibliography, and this framework's default compile sequence
assumes classic BibTeX (`\bibliographystyle` + `\bibliography`), not `biblatex`/
`biber` - a deliberate choice so the toolchain stays what's on a stock TeX Live
install (see `04-citation-rules.md`). If your template requires `biblatex`/`biber`
(many modern thesis templates do), `/add-template` supports it, but the mandatory
test compile in Step 4 has to actually exercise the bibliography with the declared
engine before the template is registered - a template whose bibliography path was
never tested is the single most likely thing to break mid-`/synthesize`.
