# /defend - Presentation & Defense Prep

Builds a prep pack for presenting or defending a `/synthesize` report out loud - to a
supervisor, in a lab meeting, at a conference, or in a thesis viva. Analog of
`ai-job-search`'s `/interview`, adapted for a research report instead of a job
application: the report itself is the "submitted document" whoever is on the other
side of the table has already read (or will read).

`$ARGUMENTS` is the topic slug matching an existing `reports/<topic_slug>/` directory,
e.g. `/defend vr-keystroke-inference-side-channel-attacks`. Optionally followed by
free-text context, e.g. `/defend retrieval-augmented-generation lab meeting next
Tuesday`.

Follow these steps in order.

---

## Step 0: Parse Input & Match the Report

1. List `reports/*/` and match `$ARGUMENTS` against the topic slugs.
   - **Exact or unambiguous partial match**: proceed with that report.
   - **Multiple plausible matches**: list them and ask which one.
   - **No match, and `reports/` has entries**: show the available topics and ask which
     to prep.
   - **No match, and `reports/` is empty**: say so and suggest running `/research`
     then `/synthesize` on a topic first - there's nothing to defend yet.
2. Confirm `reports/<topic_slug>/report.tex` and `references.bib` both exist. If only
   a partial report exists (e.g. `/synthesize` was interrupted), say so and suggest
   finishing it first.

---

## Step 1: Load Context

1. Read the report itself: `reports/<topic_slug>/report.tex` and
   `references.bib`. Pay specific attention to the **Open Questions** section - it is
   the primary seed for Step 3.
2. Read `.claude/skills/research-assistant/06-defense-prep.md` (the framework this
   command follows) once.
3. Read `.claude/skills/research-assistant/01-researcher-profile.md` for expertise
   level (calibrates register) and `02-source-evaluation.md` for score/verdict
   meanings (needed to explain why a source was included, excluded, or scored the way
   it was).
4. Read `research/seen_sources.json`, filtered to entries with `subject` matching this
   topic's area (or cross-reference by title against the report's bibliography) - this
   surfaces sources that were found and scored but **not** included in the final
   report (`Peripheral`/`Excluded` verdicts, `unfetchable` status). These are exactly
   the sources a sharp question might raise ("did you consider X?").
5. Ask the user for presentation context if not already given in `$ARGUMENTS`:
   - **Setting**: supervisor meeting / lab meeting / conference talk / thesis viva /
     paper rebuttal / other
   - **When** (if relevant for prep depth/urgency)
   - **Audience**: anyone specific by name, especially anyone whose own work might be
     relevant to this topic

---

## Step 2: Research the Audience (optional)

Only if the user named a specific audience member.

1. Look up their public research work via `google-scholar-search search -q
   'author:"<Name>"'` (same zero-new-code pattern `/expand` uses) or `WebSearch`/
   `WebFetch` for a personal/lab page.
2. **Verify before using** - the same discipline as every other command in this
   framework: only state something about the audience member's work that was actually
   fetched and read, never inferred from a title alone.
3. Look specifically for: any paper of theirs that's directly relevant to this
   report's topic but wasn't cited (a likely "why didn't you cite my work?" moment),
   or any finding of theirs that appears to conflict with a claim in the report (a
   likely challenge point).
4. If nothing relevant turns up, say so plainly rather than padding the prep pack with
   generic bio facts.

Skip this step entirely if no specific audience member was named - do not invent a
generic "the audience might think X" without a real basis.

---

## Step 3: Build the Defense Pack

Per `06-defense-prep.md`'s framework, assemble:

1. **Likely questions**, derived in priority order: the report's own Open Questions
   section first, then evidence-basis caveats on included sources, then
   excluded/peripheral sources from Step 1.4, then methodological choices the report
   had to make explicit, then the standard hard-question list.
2. **Answer mapping** - one honest, report-grounded answer per likely question.
   Explicit "the report doesn't resolve this" framing where that's the true answer.
3. **Consistency brief** - the report's specific claims most likely to be probed
   (highest-impact findings, the most surprising conclusion, the weakest-evidence-
   basis source).
4. **Tough questions, customized** - the generic hard-question list from
   `06-defense-prep.md`, each rephrased against this report's actual content.
5. **Audience-specific questions** (only if Step 2 ran and found something) - framed
   as "if asked about their work directly."
6. **Questions to ask back** - only include this for settings where it's natural
   (supervisor/lab meeting, conference Q&A); omit for a viva, where the user is being
   examined, not exchanging feedback.

Present the full pack in chat, then save it to
`reports/<topic_slug>/defense_prep_<context-slug>.md` (e.g.
`defense_prep_viva.md`, `defense_prep_lab-meeting.md`) - alongside the report itself,
which is already the established, gitignored home for this topic's working files. If a
prep file for this context already exists, ask before overwriting: append a dated
section instead if the user wants to keep prior prep.

---

## Step 4: Offer a Mock Defense

Ask if the user wants to practice out loud. If yes, follow
`06-defense-prep.md`'s roleplay structure: warm-up question, two or three from the
Open-Questions-derived list, one about an excluded source, one genuine curveball. Give
brief, specific feedback after each answer - what was well-grounded, what strayed
beyond what the report supports - rather than a single pass/fail verdict at the end.

---

## Step 5: Close the Loop

Remind the user the prep pack is saved at `reports/<topic_slug>/defense_prep_*.md`
(gitignored, local-only, matching every other file in `reports/`). If it would help,
note that after the actual presentation/defense happens, recording how it went (what
landed, what didn't, anything the report should be revised to address) is useful input
for future reports on related topics.

---

## Important Rules

1. **Never draft an answer that claims more than the report supports.** A gap gets the
   report's own honest reasoning, never invented confidence - this is the same rule
   `04-citation-rules.md` applies to written citations, extended to spoken defense.
2. **Verify before using any claim about a named audience member's work.** Only state
   what was actually fetched and read (Step 2), never inferred from a title.
3. **Ground every "likely question" in something real** - the report's own Open
   Questions, an actual excluded source from `seen_sources.json`, or a documented
   methodological choice. Generic hard questions (Step 3.4) are the one category that
   doesn't need a specific source, but even those should be rephrased against this
   report's actual content, not left as boilerplate.
4. **This command never modifies the report itself.** If prep surfaces something the
   report genuinely got wrong, say so and suggest re-running `/synthesize` or editing
   the report directly - `/defend` only prepares the defense of what's already there.
