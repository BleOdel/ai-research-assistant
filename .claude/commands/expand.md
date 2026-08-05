# /expand - Interest and Landmark-Work Expansion from Documents and Public Presence

You are enriching the researcher profile by discovering research sub-areas and
landmark works hidden in documents and public academic presence. This command is
**additive only** - it never modifies existing profile content, only extends it.

Follow these steps **exactly in order**. Do not skip steps.

---

## Step 0: Read Existing Profile Files

Read these two files in parallel before doing anything else, so you don't propose
duplicates:

- `CLAUDE.md`
- `.claude/skills/research-assistant/01-researcher-profile.md`

Hold this content in context throughout the command. Do not re-read these files
later. Note in particular: the researcher's name (needed for the Scholar search in
Step 1c), current tracked Research Interests and their sub-areas, and current Known
landmark works per interest.

---

## Step 1: Discovery - Scan All Sources

Process sources in this order.

### 1a. documents/publications/

Read all files. For each paper found: extract title, authors, venue/year if visible,
and as much of the abstract/content as the file provides. This is the
highest-confidence source - it's direct evidence of the researcher's actual work, not
a self-description of it.

### 1b. documents/cv/ and documents/linkedin/

Read all files. Extract: thesis title and topic, any publications listed, research
project descriptions, and any research-area framing in an About/summary section. Note
anything that reads like a research focus not yet reflected in tracked Research
Interests.

### 1c. Google Scholar Author Search

Using the researcher's name from `01-researcher-profile.md`'s Identity section, run:

```bash
bun run .agents/skills/google-scholar-search/cli/src/cli.ts search -q 'author:"<Name>"' --limit 20 --format json
```

(Google Scholar's `q` parameter natively supports the `author:` search modifier -
see `.agents/skills/google-scholar-search/SKILL.md`.) This finds the researcher's own
indexed publications even if they aren't in `documents/publications/` - the primary
reason to run this command at all, since it needs no new connector code and no
document upload from the user. Requires `SERPAPI_API_KEY`; if unset, skip this
source, note it in the Step 6 report, and tell the user how to enable it (see
`SETUP.md`).

**Caution:** author name searches can return false positives (a different person with
the same name). Cross-check candidate results against what's already known about the
researcher - field, institution, existing landmark works, co-authors on already-known
papers - before treating a result as genuinely theirs. When in doubt, list it as
"needs manual review" in Step 4 rather than silently including or excluding it.

### 1d. GitHub (optional)

If the profile has a GitHub username or URL anywhere in `CLAUDE.md` or
`01-researcher-profile.md`, use WebFetch/WebSearch to retrieve the public profile and
its repositories. For each repository: name, description, README content, primary
language, topics. Look specifically for research-adjacent tooling (detection
pipelines, XR/security instrumentation, threat-emulation harnesses) that implies a
sub-area not yet listed - matching this profile's "Applied ML for Security /
Detection Engineering" kind of interest, which is about built tooling as much as
published papers.

If no GitHub username or URL is found, skip this source and note it was skipped.

---

## Step 2: Determine Research Area for Each Discovered Item

For each item found in Step 1 (paper, thesis, repo), determine which existing tracked
Research Interest it best fits, using the item's **actual fetched content** (title +
abstract, or README), not a guess from the title alone:

1. Compare against each tracked interest's name and listed sub-areas in
   `01-researcher-profile.md`.
2. If it clearly matches, note it as a candidate **landmark work** or **sub-area**
   addition to that interest.
3. If it plausibly matches sub-areas of more than one interest, note the closer one -
   this is an organizational aid, not a scored judgment (same rule as
   `05-subject-index.md`'s subject classification).
4. If it matches no tracked interest but multiple discovered items cluster around a
   common theme, note it as a **candidate new Research Interest** rather than forcing
   it under an existing one.

---

## Step 3: Build Enrichment Map

Group findings into:

**New landmark works** (papers not yet in a tracked interest's "Known landmark
works") - grouped by which interest they'd be added to.

**New sub-areas** (a discovered item's focus reveals a sub-area not yet listed under
an existing interest) - grouped by interest.

**Candidate new Research Interest** (if warranted per Step 2.4) - with the discovered
items that would seed it.

For each item, record:
- What it is (title, or repo name)
- The source it came from (`documents/publications/<file>`, `Google Scholar author
  search`, `GitHub - <repo>`, etc.)
- Confidence: direct (read the actual abstract/README) or inferred (title/context
  only - e.g. a Scholar result with no fetchable abstract)

Remove anything already present in `CLAUDE.md` or `01-researcher-profile.md`.

---

## Step 4: Present Grouped Summary

Present everything for review before writing anything:

```
## /expand found [N] new signals across [M] sources

**NEW LANDMARK WORKS - <Research Interest name>**
Source: [Google Scholar author search / documents/publications/<file>]
  + [Paper title] ([year], [venue if known]) - confidence: direct/inferred
  ...

**NEW SUB-AREAS - <Research Interest name>**
Source: [item that revealed this]
  + [Sub-area name] - based on: [1-line reasoning grounded in fetched content]
  ...

**CANDIDATE NEW RESEARCH INTEREST**
Source: [items that seed it]
  + Proposed name: [name]
  + Seeded by: [N items, listed]

**NEEDS MANUAL REVIEW**
  + [Item] - [why it's ambiguous: name-collision risk, no fetchable content, etc.]
```

Then ask:

> **How would you like to proceed?**
>
> - **`all`** - Add everything above to your profile
> - **`review`** - Walk through each group one at a time
> - **`skip`** - Cancel without writing anything
>
> Or list specific groups to skip (e.g. "skip GitHub, add everything else").

Wait for the user's response before writing anything.

---

## Step 5: Write Confirmed Additions

Apply only confirmed items using the Edit tool - targeted edits, never a full-file
rewrite. Keep `CLAUDE.md`'s Researcher Profile section and
`01-researcher-profile.md` in sync, per `CLAUDE.md`'s own stated rule.

- **New landmark works** → append to the relevant interest's "Known landmark works"
  list in `01-researcher-profile.md` (and the corresponding summary in `CLAUDE.md` if
  it lists landmark works there too).
- **New sub-areas** → append to the relevant interest's "Sub-areas of interest" list.
- **New Research Interest** → add as a new `###` entry under Research Interests in
  both files, with `Why tracked`, `Expertise level` (ask the user if not inferable),
  `Sub-areas of interest`, and `Known landmark works` populated from the seeding
  items.

Label every addition with its source, same discipline as `/setup` Path A:
`*[Inferred from <source> - review before relying on this]*` for anything not
directly read (Scholar results with no fetched abstract, GitHub inferences), and a
plain source note (no "inferred" caveat) for anything read directly in full.

---

## Step 6: Summary Report

```
## /expand Complete

### Added to profile
[List each addition, with source]

### Sources processed
[List each source scanned and how many additions it yielded]

### Sources skipped
[List any sources missing, empty, or skipped (e.g. no SERPAPI_API_KEY, no GitHub
username) - with reason]

### Needs manual review
[Any items left unresolved from Step 4]
```

---

## Design Principles

- **Additive only.** This command never modifies existing profile content beyond
  adding new entries.
- **Source-traceable.** Every addition records where it came from, so future runs are
  idempotent and the user can verify or remove individual items later.
- **Direct content over inference, wherever possible.** A paper's own abstract beats
  guessing a research area from its title - same rule as everywhere else in this
  framework.
- **User confirms before writing.** The full enrichment map is shown and confirmed
  before a single file is touched.
- **Name-collision risk is flagged, not silently resolved.** An author-name search
  can return someone else's papers; ambiguous matches go to manual review rather than
  being guessed into the profile.
