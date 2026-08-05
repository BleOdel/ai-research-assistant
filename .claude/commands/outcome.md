# /outcome - Record What Happened to a Report

Records what happened to a `/synthesize` report after the fact: presented, cited in
your own subsequent work, found to need revision, or superseded by a later
`/research` update on the same topic. Analog of `ai-job-search`'s `/outcome`, adapted
for a research report's lifecycle instead of a job application's.

The data lands in two places:

- `research_tracker.csv` - one row per topic, current status, for a quick overview
  across all reports
- `reports/<topic_slug>/outcome.md` - the per-report append-only log (dated events,
  freeform notes)

`/outcome` writes the data; it does not interpret it. This command never edits
`01-researcher-profile.md`, `02-source-evaluation.md`, or any other skill file -
recalibrating those based on outcome patterns is a judgment call for the user to make
in `/setup`, not something this command does automatically (same separation of
concerns as the original's Step 5 rule).

`$ARGUMENTS` may be empty or a topic slug. Follow these steps in order.

---

## Step 0: Parse Input

- Nothing → list reports with a non-final status (see Step 2's status list) and ask
  which to update. If none exist, say so and stop - nothing to record yet.
- A topic slug (or a close partial match) → target `reports/<topic_slug>/` directly.
  Ambiguous partial matches: list and ask. No match: show available topics from
  `reports/*/` and ask which one, or note that `/synthesize` hasn't produced anything
  for that topic yet.

---

## Step 1: Load State

1. Read `research_tracker.csv`. If it does not exist, create it with the header:
   ```
   topic,subject,date_synthesized,status,last_event_date,notes
   ```
2. Confirm `reports/<topic_slug>/report.tex` exists - `/outcome` only tracks reports
   that were actually synthesized, not raw `/research` discovery runs.
3. Check whether `reports/<topic_slug>/outcome.md` already exists - if so, this is an
   update (append), not a fresh record.

---

## Step 2: Collect What Happened

Ask the user what happened, then classify into a **status**:

- `active` - the default/ongoing state; the report is current and in use, no
  notable event yet
- `presented` - presented to a supervisor, in a lab meeting, at a conference (if a
  `/defend` prep pack exists for this topic, note which one)
- `cited` - cited or built on in the user's own subsequent paper, thesis chapter, or
  other output
- `needs_revision` - a real gap or error was found (via a defense Q&A, reviewer
  feedback, or the user's own re-reading) that the report should be fixed to address
- `superseded` - a later `/research` run on this topic turned up enough new or
  contradicting work that the existing report's conclusions are stale

`presented` and `cited` are not final - a report can be presented, then cited, then
presented again; each is its own dated event. `needs_revision` and `superseded` mark
the report as needing attention but don't retire it - the user can still resynthesize
and return to `active`.

Also collect, without interrogating - one or two open questions are enough:
- Date of the event
- Where/what (venue, paper title, what changed, what needs fixing)
- Any concrete detail worth remembering for a future report on a related topic
  (this is exactly the kind of pattern Step 5 looks for later)

---

## Step 3: Update the Per-Report Log

Create or update `reports/<topic_slug>/outcome.md`:

```markdown
# Outcome: <Topic>

**Current status:** active | presented | cited | needs_revision | superseded

## Usage Log
<!-- Append-only, most recent last. Never rewrite or remove a prior entry. -->
- YYYY-MM-DD - <event type>: <what happened, where, concrete detail>
```

Update rules, matching `/defend`'s and the original's append-only discipline:
- Always append a new dated line for the event just reported; never overwrite or
  reorder prior lines.
- Update `Current status` to whatever was just reported, but the Usage Log keeps
  full history regardless of what the current status is - a report that was
  `needs_revision` last month and is `active` again this month keeps both log lines.

---

## Step 4: Update the Tracker

Update (or add) `research_tracker.csv`'s row for this topic: `status` and
`last_event_date` to what was just recorded, and a short dated note appended to
`notes` (not replacing prior notes - keep it a running, comma-safe summary). Never
restructure the CSV, reorder rows, or touch other rows. Set `subject` from
`research/papers_by_subject.md`'s classification for this topic if not already set.

---

## Step 5: Look for Patterns (suggest only, never write)

Read all rows in `research_tracker.csv` with a status of `needs_revision` or
`superseded`. If three or more share something concrete - the same `subject` area,
the same recurring gap type, reports consistently going stale within a short window -
say so and suggest, in words, what it might mean:

> "Three reports under XR/Immersive Systems Security & Privacy have gone
> `superseded` within a few months of synthesis - that subject area may be moving
> fast enough to warrant a shorter `Default report depth` or more frequent
> `/research` reruns for it. Want to update the profile?"

**Do not edit `01-researcher-profile.md`, `02-source-evaluation.md`, or any other
skill file yourself, even if the user says yes** - point them to `/setup` (rerun) or
make the specific edit only after they confirm exactly what to change. This command's
job is surfacing the pattern, not acting on it unsupervised.

---

## Step 6: Confirm

Summarize what was recorded:

> **Outcome recorded for <Topic>.**
>
> - `reports/<topic_slug>/outcome.md` - status: <status>, logged: <event summary>
> - `research_tracker.csv` - row updated
>
> [Pattern suggestion from Step 5, if triggered]

If the recorded status is `needs_revision` or `superseded`, also suggest:

> "Want to re-run `/research <topic>` to pull in what's changed, then `/synthesize`
> to refresh the report?"

If the recorded status is `presented` and no `/defend` prep pack exists for this
topic yet, note that `/defend <topic>` builds one for next time.

---

## Important Rules

1. **Write data, don't interpret it.** The tracker and per-report log are the
   outputs; recalibrating the profile or scoring rubric from patterns in them is the
   user's call via `/setup`, never this command's own edit.
2. **Never fabricate an event.** Record only what the user actually reports - no
   inferring "probably went well" from silence.
3. **Append-only history.** Re-running `/outcome` on the same topic adds a new dated
   log line and updates the current status; it never rewrites or deletes prior
   entries.
4. **This command never modifies the report itself.** `needs_revision`/`superseded`
   are signals to re-run `/research`/`/synthesize`, not something `/outcome` does on
   its own.
