# /add-template - Register a Custom Report Template

You are helping the user register their own LaTeX report template with the AI
Research Assistant framework. The framework ships with a plain `article`-class
template (`report/report_example.tex`) with a classic-BibTeX bibliography. This
command lets the user swap in their own format - a thesis chapter, an ACM/IEEE
conference paper layout, a lab-specific report structure - store it, verify it
actually compiles (including its bibliography), and wire it into `/synthesize` so
every future report drafts from it.

`$ARGUMENTS` may contain a subcommand, a file path, or nothing.

Follow these steps **in order**.

---

## Step 0: Parse Arguments

- If `$ARGUMENTS` contains `--list`: run **List Mode** below and stop.
- If `$ARGUMENTS` contains `--use <name>`: run **Switch Mode** below, then continue
  to **Step 5: Activate** with the resolved template metadata. `--use default`
  deactivates any custom template and restores the stock guidance.
- If `$ARGUMENTS` contains a file path or @-mentioned file: treat it as the template
  source and carry it into Step 1.
- Otherwise: start the registration flow at Step 1.

### List Mode

Use Glob with `templates/*/TEMPLATE.md` to find registered templates. For each, read
the manifest and print a table:

```
## Registered Templates

| Name | Engine | Bibliography | Page Limit | Active |
|------|--------|--------------|------------|--------|
| <name> | pdflatex/xelatex/lualatex | bibtex/biblatex+biber | <N> pages / none | yes/no |
```

A template is **active** if `03-report-templates.md` contains an `ACTIVE-TEMPLATE`
managed block naming it. If no custom templates exist, say so and explain that
`/add-template` registers one. Stop here.

### Switch Mode

If `$ARGUMENTS` contains `--use <name>`:

1. If `<name>` is `default`, skip template resolution and continue to Step 5 with
   `default` as the activation target.
2. Use Glob with `templates/*/TEMPLATE.md` and find the manifest whose parent folder
   name exactly matches `<name>`.
3. If no manifest matches, stop and say the template is not registered. Suggest
   `/add-template --list`.
4. Read the matching `TEMPLATE.md` and extract: compile engine, bibliography engine,
   page limit, fonts, required section structure.
5. Verify `template.tex` exists in the same folder. If missing, stop with an error -
   the registration is incomplete.
6. Continue to Step 5 using the resolved metadata. Do not re-run Steps 1-4; `--use`
   switches an already-registered template.

---

## Step 1: Template Source

Ask the user (skip anything already answered by `$ARGUMENTS`):

**Source:** Where is the template? Accept any of:
- A path or @-mention of a `.tex` file (plus optional `.cls`/`.sty` files)
- Pasted LaTeX content
- A directory containing the template and its assets (class files, fonts, a
  `.bst`/`.bib` example)

Read every provided file. If the template references a document class or package not
part of standard TeX distributions (a custom `.cls`, a university-branded style
file), confirm the user has the file and ask for it if missing - the template cannot
compile without it.

---

## Step 2: Capture Template Instructions

Interview the user for what `/synthesize` needs to draft from this template
correctly. Infer as much as possible from the LaTeX source first (documentclass,
`\bibliographystyle`/`\usepackage{biblatex}`, `\fontspec` calls, section commands)
and present inferences for confirmation rather than asking blind questions.

Collect:

1. **Name** - short kebab-case identifier (e.g. `thesis-chapter`, `acm-conference`).
   Must not collide with an existing folder in `templates/`.
2. **Compile engine** - `pdflatex`, `xelatex`, or `lualatex`. If the source uses
   `fontspec` or loads font files by path, it requires `xelatex` or `lualatex` - tell
   the user this rather than letting them pick `pdflatex`.
3. **Bibliography engine** - `bibtex` (matches the framework's default) or
   `biblatex+biber`. If the template's preamble loads `\usepackage{biblatex}`, it
   needs `biber`, not classic `bibtex` - this changes the compile sequence `/synthesize`
   must run for this template (see `templates/README.md`'s note on bibliographies).
   Do not guess; check the actual preamble.
4. **Fonts** - which font(s) the template uses and where they come from:
   - **Bundled font files**: copy them into the template folder in Step 3 and record
     the relative `Path` used in `\fontspec` calls.
   - **System / TeX-distribution fonts**: record the name; the user's machine must
     have it installed.
5. **Required section structure** - does the template mandate specific sections in a
   specific order (e.g. a thesis chapter's `Introduction, Related Work, Methodology,
   Results, Discussion, Conclusion`)? If so, record it exactly. Then check it against
   `03-report-templates.md`'s standard sections (Abstract, Background, Thematic
   sections, **Technical Findings (Plain Language)**, Comparison table, Open
   Questions, References) and note explicitly where each standard section maps in
   the custom structure, or that it doesn't fit and should be dropped/merged for this
   template. Never silently drop Technical Findings or Open Questions without asking
   - they're core to this framework's honesty discipline, not decoration.
6. **Page limit** - does the template have a genuine hard limit (e.g. a conference
   submission cap)? Unlike a CV, there is **no default page limit** for a report -
   `03-report-templates.md` deliberately ties length to the profile's depth
   preference and actual source coverage. Only record a limit if the template itself
   imposes one; otherwise record `none`.
7. **Citation style compatibility** - does the template's `.bst`/`biblatex` style
   force a specific citation style (e.g. a journal's house style), overriding the
   profile's own `Citation style` preference for reports drafted from this template?
8. **Known pitfalls** (optional) - macros that break with certain content, characters
   needing escaping, sections that must not be reordered.

---

## Step 3: Store the Template

Create the template folder: `templates/<name>/`

Write into it:

1. **`template.tex`** - the template skeleton. Replace topic-specific content with
   `[PLACEHOLDER]` tokens (`[TOPIC_TITLE]`, `[SECTION_CONTENT]`, ...) and keep an
   author line placeholder (`[YOUR_NAME]`) so the template is shareable and
   profile-agnostic. Keep the structure, preamble, and styling exactly as provided.
2. **Class/style files** - copy any `.cls`/`.sty`/`.bst` files alongside
   `template.tex`.
3. **`fonts/`** - copy bundled font files here, preserving the directory layout
   `\fontspec` `Path` options expect. Adjust `Path` values in `template.tex` to be
   relative to the template folder.
4. **`TEMPLATE.md`** - the manifest. Use exactly this format:

```markdown
# Template: <name>

- **Compile engine:** pdflatex | xelatex | lualatex
- **Bibliography engine:** bibtex | biblatex+biber
- **Page limit:** <N> page(s) | none (length follows profile depth preference)
- **Fonts:** <main font> (<bundled in fonts/ | system font - must be installed>)
- **Class/packages:** <documentclass and any non-standard packages, or "standard">
- **Citation style:** <forced style, or "follows profile's Citation style preference">

## Compile command

    cd reports/<topic_slug> && <engine> -interaction=nonstopmode report.tex
    <bibtex report | biber report>
    <engine> -interaction=nonstopmode report.tex
    <engine> -interaction=nonstopmode report.tex

## Required section structure

<exact section list/order the template mandates, and how this framework's standard
sections (Abstract, Background, Thematic sections, Technical Findings (Plain
Language), Comparison table, Open Questions, References) map onto it>

## Style rules

- <rule 1: section order, heading style, spacing conventions, ...>
- <rule 2>

## Known pitfalls

- <pitfall and its fix, or "none recorded">
```

---

## Step 4: Verify the Template Compiles (MANDATORY)

Never register a template without a successful test compile that exercises the
**bibliography**, not just the prose structure - a report template with an untested
citation path is the single most likely thing to break mid-`/synthesize`, since every
report this framework produces has a working bibliography by design.

1. Copy `template.tex` to a scratch file (`_compile_test.tex`) in the same folder and
   fill every `[PLACEHOLDER]` with realistic dummy content: a topic title, one
   thematic section paragraph with a `\cite{}`, a Technical Findings paragraph (or
   note why it doesn't apply to this template's structure), and an Open Questions
   bullet.
2. Write a scratch `_compile_test.bib` with one real or plausible dummy BibTeX entry
   matching the citation key used above.
3. Compile with the declared engine and bibliography engine:
   ```bash
   cd templates/<name>
   <engine> -interaction=nonstopmode _compile_test.tex
   <bibtex _compile_test | biber _compile_test>
   <engine> -interaction=nonstopmode _compile_test.tex
   <engine> -interaction=nonstopmode _compile_test.tex
   ```
4. If any pass fails: show the relevant error lines, diagnose (missing font, wrong
   engine, wrong bibliography engine, missing class), fix what you can, and
   re-compile the full sequence from the top. If the fix needs something only the
   user has (a missing font file, a license-restricted class), ask and wait.
5. On success, Read the PDF and confirm: no overlapping text, fonts loaded, **no `??`
   anywhere** (unresolved citations - the specific failure mode `natbib` with a
   numbered style silently produces as `(author?)` instead of erroring, see
   `04-citation-rules.md`), bibliography section renders with the test entry
   correctly formatted. Record any surprises in the manifest's "Known pitfalls".
6. Delete every scratch artifact: `_compile_test.tex`, `_compile_test.bib`,
   `_compile_test.pdf`, `_compile_test.aux`, `_compile_test.log`,
   `_compile_test.bbl`, `_compile_test.blg`, `_compile_test.out`, and any other
   `_compile_test.*` byproducts (`biber` in particular leaves `.bcf`/`.run.xml`
   files - check for these too).

Do not proceed to Step 5 until the test compile passes cleanly.

---

## Step 5: Activate the Template

Activation wires the template into `/synthesize` by adding a **managed block** to the
top of `.claude/skills/research-assistant/03-report-templates.md`, immediately after
its H1 title.

If Step 5 was reached from Switch Mode, use the metadata resolved from `TEMPLATE.md`.
If reached after registering a new template, use the metadata collected and verified
in Steps 2-4.

Insert (or replace, if one exists) this block:

```markdown
<!-- BEGIN ACTIVE-TEMPLATE (managed by /add-template - do not edit by hand) -->
> **Active template override: `<name>`**
>
> A custom template is active. Where this block conflicts with the stock guidance
> below, this block wins.
>
> - **Template skeleton:** `templates/<name>/template.tex` - use this as the
>   structural reference instead of `report/report_example.tex`
> - **Manifest:** `templates/<name>/TEMPLATE.md` - read this for the required
>   section structure, style rules, and known pitfalls before drafting
> - **Compile with:** `<engine>` + `<bibtex | biber>` (see the manifest's exact
>   compile command - not the stock 4-pass pdflatex+bibtex sequence if this
>   template uses biblatex+biber instead)
> - **Page limit:** <N pages | none - follows profile depth preference as usual>
> - **Citation style:** <forced by template, or "follows profile preference">
> - **Output file:** unchanged (`reports/<topic_slug>/report.tex`); copy any
>   class/font files the template needs into the output directory, or reference
>   them by relative path
<!-- END ACTIVE-TEMPLATE -->
```

Rules:

- Exactly **one** managed block in `03-report-templates.md`. Replace the whole block
  between the `BEGIN`/`END` markers when switching templates; never stack blocks.
- **`--use default`**: remove the managed block entirely. The stock guidance below it
  is untouched and takes over again.
- Do not modify anything outside the markers.

---

## Step 6: Confirm

Present a summary:

> **Template `<name>` registered and activated.**
>
> - Files: `templates/<name>/` (skeleton, manifest<, class files><, fonts>)
> - Test compile: passed with `<engine>` + `<bibtex | biber>` (bibliography verified,
>   no unresolved citations)
> - `/synthesize` will now draft reports from this template.
>
> Useful follow-ups:
> - `/add-template --list` - see all registered templates
> - `/add-template --use <other-name>` - switch templates
> - `/add-template --use default` - go back to the stock `report/report_example.tex`
>   structure

---

## Design Principles

- Registration is idempotent: re-running with the same name offers to update the
  existing template rather than duplicating it.
- Templates are stored profile-agnostic (`[PLACEHOLDER]` tokens) so they can be
  shared or committed without leaking personal data or a specific report's content -
  unlike `documents/` or `reports/`, `templates/` is meant to be tracked in git.
- The compile check in Step 4 is non-negotiable, and it must exercise the
  bibliography specifically - a report template that has never resolved a real
  citation will fail mid-`/synthesize`, which is the worst place to discover it.
- Activation is a small managed block, not a rewrite of
  `03-report-templates.md`: manual edits to the file survive template switches, and
  `--use default` is a clean revert.
- **No default page limit.** This is the one place this command deliberately departs
  from the CV/cover-letter original: a report's length follows the profile's depth
  preference and actual source coverage, never a fixed budget, unless the specific
  template genuinely imposes one (e.g. a conference submission cap).
