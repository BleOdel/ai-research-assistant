# Subject-Organized Paper Index

`research/papers_by_subject.md` is a derived, read-only view of
`research/seen_sources.json`, grouped by which of the researcher's tracked Research
Interests (from `01-researcher-profile.md`) each source belongs to. It exists so the
user can see everything discovered, organized by subject, without reading raw JSON -
XR papers under the XR table, ML papers under the ML table, and so on.

## When it's regenerated

Regenerate the **entire file** from `seen_sources.json` after any write to that file -
`/research` (Step 4), `/rank` (Step 4), `/synthesize` (Step 6). Never hand-edit
`papers_by_subject.md` directly; it will be overwritten on the next regeneration. This
keeps it a pure derived view instead of two sources of truth that can drift apart.

## Classifying a source into a subject

Each `seen_sources.json` entry carries a `"subject"` field, set once when the source
is first discovered by `/research`:

1. Compare the `/research` topic (the query that found this source) against
   `01-researcher-profile.md`'s Research Interests - their names and listed
   sub-areas.
2. If it clearly matches one tracked interest, use that interest's exact name as the
   subject (e.g. `"XR/Immersive Systems Security & Privacy"`).
3. If it plausibly matches sub-areas of more than one interest, pick the closer one -
   this is an organizational aid, not a scored judgment, so don't overthink close
   calls.
4. If it matches no tracked interest, use `"Uncategorized"` rather than inventing a
   new profile interest on the spot - the user can promote a recurring uncategorized
   topic to a tracked interest later via `/setup --section interests` or `/expand`.

Never re-classify an existing entry's subject on a later `/research` or `/rank` run
just because the topic wording differs slightly - stable classification matters more
than perfect classification. Only re-classify if the profile's tracked interests
themselves changed.

## File format

One table per subject, in the same order as `01-researcher-profile.md`'s Research
Interests are listed (`Uncategorized` last, and only included if non-empty):

```markdown
# Papers by Subject

<!-- Auto-generated from research/seen_sources.json by /research, /rank, and
     /synthesize. Do not hand-edit - changes will be overwritten. -->

## <Research Interest name>

| Title | Authors | Year | Venue | Score / Relevance | Status | Link |
|-------|---------|------|-------|--------------------|--------|------|
| ... | ... | ... | ... | ... | ... | ... |

## Uncategorized

| Title | Authors | Year | Venue | Score / Relevance | Status | Link |
|-------|---------|------|-------|--------------------|--------|------|
```

Column rules:

- **Score / Relevance**: the source's `overall_score` and `verdict` if it has been
  `/rank`ed or `/synthesize`d (e.g. `88 - Core`), otherwise its `/research` triage
  relevance (`high`/`medium`/`low`).
- **Status**: `seen_sources.json`'s own `status` field verbatim
  (`new`/`ranked`/`unfetchable`/`synthesized`/`skipped`).
- Sort each table by Score/Relevance descending where a numeric score exists,
  otherwise by `first_seen` descending (newest first).
- `Link` is a markdown hyperlink using the entry's `url` field.
