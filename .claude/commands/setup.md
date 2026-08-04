# /setup - Researcher Profile Onboarding

You are running onboarding for the AI Research Assistant framework. Your goal is to
populate `CLAUDE.md` and `01-researcher-profile.md` so `/research` and `/synthesize`
work out of the box.

There are three paths in. Step 0 picks the right one; all converge on Step 2 (file
generation) and Step 3 (confirmation).

---

## Step 0: Welcome & Choose Path

If `$ARGUMENTS` contains `--section <name>`, skip directly to an update-only flow for
that section (e.g. `--section interests` to reconfigure just the Research Interests
section without redoing everything else).

Otherwise, welcome the user with a single message offering three paths:

> **Welcome to the AI Research Assistant setup!**
>
> I'll help you build your researcher profile so `/research` and `/synthesize` can
> discover sources and write synthesis reports calibrated to your actual interests and
> expertise. Three ways to start:
>
> **Path A: Paste an existing reading list or notes** - a bibliography, a Zotero/
> Mendeley export, or a plain list of papers/topics you've been tracking. I'll infer
> your interests and expertise level from what's there.
>
> **Path B: Describe your interests** - a short paragraph on what you research or want
> to track, your background, and how deep you want reports to go.
>
> **Path C: Interview mode** - I'll ask a few structured questions if you'd rather not
> free-write.
>
> Which would you like?

Wait for the user's choice.

---

## Path A: Reading List / Notes Import

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

## Path B: Free-Text Interests

1. Read the user's description.
2. Extract: topics, expertise signals (self-described or implied by vocabulary used),
   any named landmark papers/authors, stated depth/audience preference.
3. Ask only for what's missing (don't re-ask what was already stated).
4. Proceed to Step 2.

---

## Path C: Interview Mode

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

- Three onboarding paths converge on the same two files. Path A infers what it can from
  real material; Paths B and C rely on the user's own description.
- Never fabricate an expertise level or interest the user didn't state or clearly imply.
- Can be re-run with `--section <name>` to update just one part of the profile without
  redoing the whole thing.
