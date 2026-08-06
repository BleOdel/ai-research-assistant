# /reset - Reset Profile and Research Data

You are resetting parts of the research assistant framework back to a blank state so
the user can start fresh with `/setup` and/or `/research`.

**This command is destructive.** Nothing is deleted until the user explicitly
confirms. Follow these steps exactly in order.

---

## Step 0: Parse Scope from Arguments

Check `$ARGUMENTS` for a scope keyword:

- `profile` - clears researcher profile data from `CLAUDE.md` and
  `01-researcher-profile.md` only
- `documents` - deletes user-provided files from the `documents/` folder only
- `research` - clears discovery state (`research/seen_sources.json`,
  `research/papers_by_subject.md`) only
- `reports` - deletes all compiled synthesis reports under `reports/` only
- `blog` - deletes web-scan output and discovery state under `blog/` only
- `all` - all five of the above

If `$ARGUMENTS` is empty or does not contain a recognized scope keyword, ask:

> **What would you like to reset?**
>
> - **`profile`** - Clears your researcher profile (identity, research interests,
>   output preferences, standing exclusions) from `CLAUDE.md` and
>   `01-researcher-profile.md`. Framework structure, workflow rules, and the
>   verification checklist are preserved. Use this to re-run `/setup` from scratch.
>
> - **`documents`** - Deletes all files you've placed in the `documents/` folder (CV,
>   LinkedIn export, publications). The folder structure and `README.md` are
>   preserved.
>
> - **`research`** - Clears discovery state: `research/seen_sources.json` (every
>   source `/research` and `/rank` have found and scored) and
>   `research/papers_by_subject.md` (the derived subject index). Compiled reports
>   under `reports/` are NOT affected.
>
> - **`reports`** - Deletes all compiled synthesis reports under `reports/` (`.tex`,
>   `.bib`, `.pdf` per topic). Discovery state under `research/` is NOT affected.
>
> - **`blog`** - Deletes all `/websearch` output (`blog/<topic>/index.html` and
>   `sources.json`) and the web discovery state `blog/seen_web_sources.json`. The
>   tracked `blog/template.html` and `blog/README.md` are NOT deleted. The academic
>   track under `research/` and `reports/` is NOT affected.
>
> - **`all`** - All five of the above.
>
> Reply with `profile`, `documents`, `research`, `reports`, `blog`, or `all`.

Wait for the user's response before continuing.

---

## Step 1: Show Exactly What Will Be Cleared

Before doing anything, show the user precisely what will be wiped.

### If scope includes `profile`:

Read the current state of `CLAUDE.md` and
`.claude/skills/research-assistant/01-researcher-profile.md` and report whether each
has real content or is already blank (still has `[PLACEHOLDER]` tokens).

```
## Profile reset will clear:

- CLAUDE.md - [has content / already blank]
  Only the "## Researcher Profile" section (Identity, Research Interests, Output
  Preferences, Standing Exclusions) is replaced with placeholder tokens. Role, Repo
  Structure, Workflow, and the Verification Checklist are NOT touched.

- 01-researcher-profile.md - [has content / already blank]
  Full file replaced with a blank template. The generic Depth Calibration guidance
  (beginner/working-knowledge/expert descriptions) is preserved; only your specific
  interests, expertise levels, and any calibration summary /setup added are cleared.
```

### If scope includes `documents`:

Use Glob to list all files present in `documents/cv/`, `documents/linkedin/`, and
`documents/publications/`. Present as:

```
## Documents reset will delete:

documents/cv/
  - [filename] or "(empty)"

documents/linkedin/
  - [filename] or "(empty)"

documents/publications/
  - [filename] or "(empty)"

documents/README.md - NOT deleted (instructions file)
```

If all subfolders are already empty, state "All document subfolders are already
empty - nothing to delete." and skip the confirmation step for this scope.

### If scope includes `research`:

Read `research/seen_sources.json` if it exists and report the count of sources by
status (new/ranked/unfetchable/synthesized). Report whether
`research/papers_by_subject.md` exists.

```
## Research reset will clear:

- research/seen_sources.json - N sources (X new, Y ranked, Z synthesized) / "(missing
  or empty)"
- research/papers_by_subject.md - [exists / missing]

Note: this does NOT delete compiled reports under reports/ - a report already
written stays on disk even after its source's discovery-state entry is cleared. Use
the `reports` scope (or `all`) to also clear those. The web track under blog/ is a
separate scope and is also unaffected.
```

### If scope includes `blog`:

Read `blog/seen_web_sources.json` if it exists and report the count of web sources by
tier. List the topic folders under `blog/` (excluding the tracked `template.html` and
`README.md`).

```
## Blog reset will clear:

- blog/seen_web_sources.json - N web sources (X Core, Y Supporting, Z Peripheral) /
  "(missing or empty)"
- blog/<topic-slug>/ - K scan folder(s): [list them]

Preserved: blog/template.html and blog/README.md (tracked framework files, not your
data).
```

If the state file is missing or empty, state "Nothing to clear - no discovery state
exists yet." and skip the confirmation step for this scope.

### If scope includes `reports`:

Use Glob (`reports/**/*`) to list every topic subdirectory and its files.

```
## Reports reset will delete:

reports/<topic-slug-1>/
  - report.tex, references.bib, report.pdf

reports/<topic-slug-2>/
  - ...

(or "reports/ is already empty - nothing to delete.")
```

---

## Step 2: Require Explicit Confirmation

Present the confirmation prompt:

> **This cannot be undone.**
>
> Type **`RESET`** (all caps) to confirm, or anything else to cancel.

Wait for the user's response.

- If the user types exactly `RESET`: proceed to Step 3.
- If the user types anything else: abort and tell them "Reset cancelled. Nothing was
  changed."

---

## Step 3: Execute the Reset

### Profile reset

**In `CLAUDE.md`**, replace only the content between `## Researcher Profile` and the
next `## Repo Structure` heading with:

```markdown
## Researcher Profile

<!-- This section is auto-populated by /setup. You can also fill it in manually. -->

### Identity
- **Name:** [YOUR_NAME]
- **Role / field:** [YOUR_FIELD] ([YOUR_CURRENT_ROLE])
- **Languages:** [YOUR_LANGUAGES]

### Research Interests
<!-- List active or recurring topics, most active first -->
- **[TOPIC_1]** - [WHY_YOU_TRACK_THIS] - expertise: [beginner/working knowledge/expert]
- **[TOPIC_2]** - [WHY_YOU_TRACK_THIS] - expertise: [beginner/working knowledge/expert]

### Output Preferences
- **Citation style:** [YOUR_CITATION_STYLE] (default: IEEE)
- **Default depth:** [quick brief (2-3 pages) / deep review (10+ pages)]
- **Audience:** [self / team / publication draft]

### Standing Exclusions
<!-- Hard constraints on what counts as usable evidence -->
- [EXCLUSION_1, e.g. "skip preprints with no venue after 18 months"]
- [EXCLUSION_2]

```

Also replace the `[YOUR_NAME]` occurrences in the title line and the `## Role`
paragraph (both currently hold the researcher's actual name) back to `[YOUR_NAME]`.
Leave every other section of `CLAUDE.md` untouched.

**Replace the full content of `.claude/skills/research-assistant/01-researcher-profile.md`** with:

```markdown
# Researcher Profile for [YOUR_NAME]

<!-- SETUP: This file is populated by running /setup -->
<!-- Structured version of the profile in CLAUDE.md. Keep the two in sync. -->

## Identity
- **Name:** [YOUR_NAME]
- **Field(s):** [YOUR_FIELD]
- **Current role:** [YOUR_CURRENT_ROLE]
- **Background:** [1-2 sentences on relevant training/experience that shapes how deep
  or technical a synthesis should go]

## Research Interests
<!-- One entry per topic you track or expect to query. /research and /synthesize use
     this to calibrate scope and default query terms when a topic is under-specified. -->

### [TOPIC_1]
- **Why tracked:** [YOUR_REASON]
- **Expertise level:** [beginner / working knowledge / expert]
- **Sub-areas of interest:** [SUB_AREA_A, SUB_AREA_B]
- **Known landmark works (if any):** [PAPER_OR_AUTHOR_1, PAPER_OR_AUTHOR_2]

### [TOPIC_2]
- **Why tracked:** [YOUR_REASON]
- **Expertise level:** [beginner / working knowledge / expert]
- **Sub-areas of interest:** [SUB_AREA_A, SUB_AREA_B]

## Depth Calibration

Expertise level changes how a synthesis report should read:
- **Beginner:** define terms on first use, favor well-established results over the
  newest preprints, more background section
- **Working knowledge:** assume field vocabulary, focus on what's changed recently,
  brief background
- **Expert:** skip background entirely, focus on disagreements, open problems, and
  methodological critique - the value is in what's contestable, not a survey

## Output Preferences
- **Citation style:** [YOUR_CITATION_STYLE] (default IEEE if unset)
- **Default report depth:** [quick brief (2-3 pages) / deep review (10+ pages)]
- **Audience:** [self / team / publication draft] - affects how much hedging and
  methodology detail belongs in the prose vs. footnotes

## Standing Exclusions
<!-- Hard constraints that apply to every synthesis unless overridden per-run -->
- [EXCLUSION_1]
- [EXCLUSION_2]
```

### Documents reset

For each non-empty document subfolder, delete all files within it using Bash `rm`. Do
not delete the folder itself, `documents/README.md`, or any `.gitkeep` file.

```bash
find documents/cv -type f ! -name '.gitkeep' -delete
find documents/linkedin -type f ! -name '.gitkeep' -delete
find documents/publications -type f ! -name '.gitkeep' -delete
```

### Research reset

```bash
rm -f research/seen_sources.json research/papers_by_subject.md
```

### Blog reset

Deletes per-topic scan folders and the web discovery state, but never the tracked
template or README - `find` with `-mindepth 1 -type d` targets only subdirectories,
leaving files directly under `blog/` alone.

```bash
find blog -mindepth 1 -type d -exec rm -rf {} +
rm -f blog/seen_web_sources.json
```

### Reports reset

```bash
rm -rf reports/*/
```

Do not delete `reports/.gitkeep` if present.

---

## Step 4: Confirm What Was Done and Next Steps

After the reset is complete, report:

```
## Reset complete

### Cleared
[List each file/folder that was actually modified or cleared]

### Unchanged
[List anything that was already empty or was intentionally preserved]
```

Then tell the user what to do next based on what was reset:

**If profile was reset:**
> Your researcher profile is now blank. Run `/setup` to repopulate it - it auto-detects
> any files in your `documents/` folder and offers to read from there, or walks you
> through a reading-list import, free-text description, or interview.

**If documents were reset:**
> The `documents/` folder is now empty. Add your CV/LinkedIn export/publications and
> run `/setup` (Path A) to populate your profile from them. See `documents/README.md`.

**If research was reset:**
> Discovery state is cleared. Run `/research <topic>` to start finding sources again -
> any previously compiled reports under `reports/` are untouched.

**If reports was reset:**
> All compiled reports are deleted. Discovery state under `research/` is untouched, so
> `/synthesize` can re-draft from previously-scored sources without re-running
> `/research`.

**If blog was reset:**
> Web scans and their discovery state are cleared. `blog/template.html` and
> `blog/README.md` are preserved. Run `/websearch <topic>` to start a new scan - the
> academic track under `research/` and `reports/` is untouched.

**If all was reset:**
> Profile, documents, discovery state, reports, and web scans are all cleared - a fully blank
> slate. Run `/setup` to start over.
