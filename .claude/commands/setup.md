# /setup - Researcher Profile Onboarding

You are running onboarding for the AI Research Assistant framework. Your goal is to
populate `CLAUDE.md` and `01-researcher-profile.md` so `/research` and `/synthesize`
work out of the box.

There are four paths in. Step 0 picks the right one; all converge on Step 2 (file
generation) and Step 3 (confirmation).

---

## Step 0: Welcome & Choose Path

If `$ARGUMENTS` contains `--section <name>`, skip directly to an update-only flow for
that section (e.g. `--section interests` to reconfigure just the Research Interests
section without redoing everything else).

Otherwise, scan `documents/` first (Glob `documents/**/*`, count files per subfolder:
`cv/`, `linkedin/`, `publications/`). The wording changes based on what's found.

**If `documents/` has files** in one or more subfolders, lead with Path A:

> **Welcome to the AI Research Assistant setup!**
>
> I'll help you build your researcher profile so `/research` and `/synthesize` can
> discover sources and write synthesis reports calibrated to your actual interests and
> expertise. I see files in your `documents/` folder: [list per subfolder, e.g. "1 in
> cv/, 3 in publications/"]. Four ways to start:
>
> **Path A: Read my documents folder** (recommended for what you have) - I'll read your
> CV, LinkedIn export, and publications, and build your identity/background and
> research interests from real material. Idempotent and safe to re-run as you add more.
>
> **Path B: Paste an existing reading list or notes** - a bibliography, a Zotero/
> Mendeley export, or a plain list of papers/topics you've been tracking. I'll infer
> your interests and expertise level from what's there.
>
> **Path C: Describe your interests** - a short paragraph on what you research or want
> to track, your background, and how deep you want reports to go.
>
> **Path D: Interview mode** - I'll ask a few structured questions if you'd rather not
> free-write.
>
> Which would you like?

**If `documents/` is empty**, surface Path A as a "do this if you have materials"
option instead of leading with it:

> **Welcome to the AI Research Assistant setup!**
>
> I'll help you build your researcher profile so `/research` and `/synthesize` can
> discover sources and write synthesis reports calibrated to your actual interests and
> expertise. Four ways to start:
>
> **Path A: Documents folder** (best signal if you have materials) - Drop your CV/
> LinkedIn export/publications in the `documents/` folder, then say "go". See
> `documents/README.md` for the layout.
>
> **Path B: Paste an existing reading list or notes** - a bibliography, a Zotero/
> Mendeley export, or a plain list of papers/topics you've been tracking. I'll infer
> your interests and expertise level from what's there.
>
> **Path C: Describe your interests** - a short paragraph on what you research or want
> to track, your background, and how deep you want reports to go.
>
> **Path D: Interview mode** - I'll ask a few structured questions if you'd rather not
> free-write.
>
> Which would you like?

Wait for the user's choice. If they pick A but the folder is still empty, tell them
what to add (point at `documents/README.md`) and stop.

---

## Path A: Documents Folder

Reads `documents/cv/`, `documents/linkedin/`, `documents/publications/`, merges
extracted signal into `CLAUDE.md` and `01-researcher-profile.md`. Read-before-write
and idempotent.

### Step A1: Inventory

Glob `documents/**/*`. Print:

```
## Documents Found

**cv/**: [list files, or "(empty)"]
**linkedin/**: [list files, or "(empty)"]
**publications/**: [list files, or "(empty)"]

I will read these and cross-reference before proposing any changes.
```

If every subfolder is empty, stop and point at `documents/README.md`.

### Step A2: Read Existing Profile Files

Read `CLAUDE.md` and `.claude/skills/research-assistant/01-researcher-profile.md`
before extracting anything, and hold their content in context - do not re-read.

### Step A3: Parse Documents

**`cv/`:** name, current role/affiliation, education (degree, institution, dates,
thesis), employment history relevant to research context, technical/domain skills.

**`linkedin/`:** role/affiliation, education, skills, publications listed on the
profile, About/summary text (source for research-interest framing, not verbatim
copy). If multiple exports are present, use the most recently modified file.

**`publications/`:** for each paper - title, venue, year, and the research sub-area(s)
it demonstrates. This is the highest-value source: it's direct evidence of actual
research interests and expertise, not a self-description.

### Step A4: Cross-Reference Check

Check for inconsistencies across documents: name/affiliation mismatches, education
mismatches (degree name, graduation date), employer name variations. If found, present
as a numbered list and wait for the user to resolve each one before continuing. If
none, state "No cross-reference issues found." and continue.

### Step A5: Build and Present Change Sets

Compare extracted content against the current `CLAUDE.md`/`01-researcher-profile.md`
content from Step A2. Split into:

- **Additive**: genuinely new (a publication-derived sub-area not yet listed, a
  landmark work not yet recorded, an education entry missing).
- **Conflicting**: touches something already recorded but disagrees (a different
  degree date, a different role title).

Label every publications/linkedin-derived research-interest or landmark-work addition
`*[Inferred from documents/<subfolder>/<file> - review before relying on this]*` -
same discipline as the original job-search template's LinkedIn-inference labeling.
Present additive changes as a single grouped list and ask "Apply all additive changes?
Reply yes, or list the numbers to skip." Present conflicts one at a time with
`[keep]`/`[replace]`/`[manual]` options. Apply only confirmed items with the Edit tool.

Documents cover identity, background, and inferred interests - they don't cover
output preferences or standing exclusions. After writes, ask the Path C/D questions
for those (citation style, default report depth, audience, standing exclusions), then
proceed to Step 2 (which will detect the two files are already populated and skip
redundant work).

---

## Path B: Reading List / Notes Import

1. Read the pasted content or referenced file thoroughly.
2. Extract topic clusters (group related papers/entries under inferred topic names),
   and for each cluster note the earliest/latest dates present (signal for how long
   they've tracked it) and any recurring authors or venues.
3. Present the inferred clusters and ask the user to confirm, rename, or merge any
   before writing:

```
## Inferred Research Interests

1. **[Inferred topic name]** - N entries, [date range], recurring: [authors/venues]
2. **[Inferred topic name]** - N entries, [date range]

Does this grouping look right? Reply with corrections, or "looks good" to continue.
```

4. Ask the remaining profile questions not inferable from a reading list: expertise
   level per topic, citation style preference, default report depth, audience, standing
   exclusions.
5. Proceed to Step 2.

---

## Path C: Free-Text Interests

1. Read the user's description.
2. Extract: topics, expertise signals (self-described or implied by vocabulary used),
   any named landmark papers/authors, stated depth/audience preference.
3. Ask only for what's missing (don't re-ask what was already stated).
4. Proceed to Step 2.

---

## Path D: Interview Mode

Ask conversationally, not as a rigid form:

### Section 1: Identity
- Name, field(s), current role
- Languages (if relevant to source material)

### Section 2: Research Interests
For each topic (repeat until the user is done adding topics):
- Topic name and why they track it
- Expertise level: beginner / working knowledge / expert
- Any landmark papers or authors they already know in this area

### Section 3: Output Preferences
- Citation style (default IEEE if they have no preference)
- Default report depth: quick brief (2-3 pages) or deep review (8+ pages)
- Audience: self / team / publication draft

### Section 4: Standing Exclusions
- Any hard constraints on what counts as usable evidence (e.g. "skip preprints with no
  venue after 18 months", "only English-language sources")

---

## Step 2: Generate Profile Files

### 1. Update `CLAUDE.md`
Replace all `[PLACEHOLDER]` tokens with the user's actual information. Keep the
structure, workflow, and verification checklist intact.

### 2. Populate `.claude/skills/research-assistant/01-researcher-profile.md`
Write the full structured profile: Identity, one subsection per Research Interest
(with why-tracked, expertise level, sub-areas, landmark works), Output Preferences,
Standing Exclusions.

Keep `CLAUDE.md`'s profile section and `01-researcher-profile.md` in sync - they should
never disagree.

---

## Step 3: Confirm & Next Steps

> **Setup complete!** Here's what was generated:
>
> - `CLAUDE.md` - Your researcher profile
> - `.claude/skills/research-assistant/01-researcher-profile.md` - Structured profile
>
> **Try it out:**
> - Run `/research <topic>` to discover sources on one of your tracked interests
> - Run `/setup --section interests` later to add or update topics as your focus shifts

---

## Design Principles

- Four onboarding paths converge on the same two files. Paths A and B infer what they
  can from real material (documents, a reading list); Paths C and D rely on the user's
  own description.
- Path A is read-before-write and idempotent, and labels every inferred addition with
  its source document so the user can review before trusting it.
- Never fabricate an expertise level or interest the user didn't state or clearly imply.
- Can be re-run with `--section <name>` to update just one part of the profile without
  redoing the whole thing.
