# Documents Folder

This folder holds your actual identity/background documents. `/setup`'s Path A reads
everything here and uses it to populate `CLAUDE.md` and
`.claude/skills/research-assistant/01-researcher-profile.md`. It is safe to re-run
`/setup` as you add new documents - it merges intelligently and never overwrites
existing content without asking first.

---

## Folder Structure

```
documents/
├── cv/              # Your CV/resume (PDF or LaTeX)
├── linkedin/         # LinkedIn profile export (PDF)
├── publications/     # Papers you've authored (PDFs)
└── README.md          # This file
```

---

## cv/

Your CV/resume - the most complete, unedited version of your professional record.

**Supported formats:** `.pdf`, `.tex`

**What `/setup` extracts:** name, current role/affiliation, education (degrees,
institutions, dates, thesis titles), technical/domain skills, employment history
relevant to research context.

**Naming:** any filename works.

---

## linkedin/

Your LinkedIn profile exported as a PDF (Profile → More → Save to PDF).

**Supported formats:** `.pdf`

**What `/setup` extracts:** role/affiliation, education, skills, publications listed
on the profile, About/summary text (used to infer research-interest framing).

**Naming:** any filename works. Only one export is expected; if multiple are present,
`/setup` uses the most recently modified one.

---

## publications/

Papers you've authored or co-authored. This is the most valuable folder for a
researcher's profile specifically: it's direct evidence of your actual research
interests and expertise level, not a self-description of them.

**Supported formats:** `.pdf`

**What `/setup` extracts:** for each paper - title, venue, year, and (most
importantly) the research sub-area(s) it demonstrates, which get proposed as
`Known landmark works` entries or new `Research Interests` sub-areas in
`01-researcher-profile.md`, each labeled `[Inferred from documents/publications/<file>
- review before relying on this]` so you can confirm or correct the inference.

**Naming:** any filename works. `/setup` reads all files present and cross-references
them (e.g. a thesis chapter vs. the published paper it became) rather than treating
duplicates as separate signals.

---

## File Format Notes

| Format | Readable by `/setup` | Notes |
|--------|----------------------|-------|
| `.pdf` | Yes | Parsed directly with the Read tool |
| `.tex` | Yes | LaTeX source - structure and content both readable |
| `.docx` | No | Convert to PDF before placing here |
| `.png` / `.jpg` | No | Scanned documents won't be parsed - use text-layer PDFs |

---

## Re-running `/setup`

Designed to be re-run as your document collection grows. Each run reads the current
state of `CLAUDE.md` and `01-researcher-profile.md`, compares extracted content
against what's already there, and only proposes changes for content that's genuinely
new or conflicting - never a silent overwrite.

**When to re-run:** after adding a new publication, updating your CV, or refreshing
your LinkedIn export.
