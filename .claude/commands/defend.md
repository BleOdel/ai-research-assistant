# /defend - Presentation, Defense & Stress-Test Prep

Builds a prep pack for a `/synthesize` report: the questions a sharp reader will ask,
answers grounded in what the report actually supports, and the problems in the report
that preparing exposes. It serves two kinds of use:

- **Before an event** - presenting or defending the report to a supervisor, in a lab
  meeting, at a conference, or in a thesis viva. The report is the "submitted
  document" whoever is across the table has already read.
- **Stress-testing** - no event at all, just "how well does this report hold up under
  questioning?". This is the default when no context is given.

Analog of `ai-job-search`'s `/interview`, adapted for a research report instead of a
job application.

`$ARGUMENTS` is the topic slug matching an existing `reports/<topic_slug>/` directory,
e.g. `/defend vr-keystroke-inference-side-channel-attacks`, optionally followed by
free-text context, e.g. `/defend retrieval-augmented-generation lab meeting next
Tuesday`. With no context, run as a stress-test.

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
4. **Excluded sources.** Read `research/seen_sources.json`, filtered to entries with
   `subject` matching this topic's area (or cross-referenced by title against the
   report's bibliography). This surfaces sources found but deliberately **not**
   included (`Peripheral`/`Excluded` verdicts, `unfetchable` or `skipped` status) -
   exactly the sources a sharp question might raise ("did you consider X?").
5. **Report issues.** Preparing a defense is a second read of the report against its
   own state, and it finds things a drafter missed. Check, and record every hit for
   Step 3's first section (`06-defense-prep.md`, *Report Issues Come First*):
   - **Scored but never cited.** Run
     ```bash
     python3 tools/state.py unmerged --subject "<subject>" --bib reports/<topic_slug>/references.bib
     ```
     `<subject>` is the report's Research Interest, found as in `/update` Step 1b.
     The list covers the whole interest, so keep only the on-topic entries; a
     Core source the report never cites is the first thing an expert reader notices.
     (On its first run this check found three, including the paper that introduced
     the report's central concept.)
   - **Scope note vs. state.** Do the scope note's counts and stated exclusions
     account for what `seen_sources.json` shows was found for this topic? A scope note
     that leaves out a group of scored sources undercounts the exclusions.
   - **Corpus claims that no longer hold.** List every sentence that claims
     something about the corpus as a whole:
     ```bash
     python3 tools/check_report.py reports/<topic_slug> --claims
     ```
     For each hit, check whether the rest of the report contradicts it: another
     section, a table row, or a `.bib` entry's `evidencebasis`. Examples: "the only
     defense with an adaptive evaluation" while Section 5 lists three others, or a
     count the scope note and the `.bib` disagree on. Most hits will hold. A
     contradicted one is usually an `/update` that merged sources and fixed one copy
     of the claim but not another, and this check is where that first surfaced.
   - **Anything else the read turns up** - a body claim that a source's own
     `evidencebasis` caveat contradicts, a figure quoted without its condition, a
     named benchmark or system that is never cited.
6. **Context.** Use the setting from `$ARGUMENTS` if given; otherwise run as a
   **stress-test** and say so in one line ("No event given - running as a
   stress-test; name a setting to tailor it"). Do not block on a question. Settings:
   stress-test (default) / supervisor meeting / lab meeting / conference talk /
   thesis viva / paper rebuttal / other. For an event, also note **when** (prep
   depth) and any named **audience** member, especially anyone whose own work bears
   on the topic.

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

0. **Report issues found during prep** - always the first section, from Step 1.5.
   One entry per issue: what is wrong, the evidence (the `unmerged` output, the
   counts that disagree, the passage), how it would surface in questioning, and the
   suggested fix. "None found" is a valid and useful result - state it, with what
   was checked.
1. **Likely questions**, derived in priority order: the report's own Open Questions
   section first, then evidence-basis caveats on included sources, then
   excluded/peripheral sources from Step 1.4, then methodological choices the report
   had to make explicit, then the standard hard-question list.
2. **Answer mapping** - one honest, report-grounded answer per likely question.
   Explicit "the report doesn't resolve this" framing where that's the true answer.
   Where a report issue from section 0 bears on a question, the answer says how to
   handle it honestly until it is fixed.
3. **Consistency brief** - the report's specific claims most likely to be probed
   (highest-impact findings, the most surprising conclusion, the weakest-evidence-
   basis source), with the exact figure and the condition that makes it meaningful.
4. **Tough questions, customized** - the generic hard-question list from
   `06-defense-prep.md`, each rephrased against this report's actual content.
5. **Audience-specific questions** (only if Step 2 ran and found something) - framed
   as "if asked about their work directly."
6. **Questions to ask back** - only for settings where it's natural
   (supervisor/lab meeting, conference Q&A). Omit it for a viva, where the user is
   being examined, and for a stress-test, where there is no one to ask.

Present the full pack in chat, then save it to
`reports/<topic_slug>/defense_prep_<context-slug>.md` (e.g.
`defense_prep_stress-test.md`, `defense_prep_viva.md`,
`defense_prep_lab-meeting.md`) - alongside the report itself, which is already the
established, gitignored home for this topic's working files. If a prep file for this
context already exists, ask before overwriting: append a dated section instead if the
user wants to keep prior prep.

---

## Step 4: Offer a Mock Defense

Offer a mock run in either of two modes (`06-defense-prep.md`, *Mock Defense*), and
let the user switch at any question:

- **Practice** - ask, wait for the user's answer, then give brief, specific feedback:
  what was well-grounded, what strayed beyond what the report supports, and which
  passage or source would have made it stronger.
- **Walkthrough** - for each question, show a model answer, why it works, the traps
  to avoid, and the likely follow-up. Use it whenever the user asks to see an answer
  ("show me"), or chooses it up front.

Either way, follow the roleplay structure: warm-up, two or three questions from the
Open-Questions-derived list, one about an excluded source, one genuine curveball. In
a stress-test, play "a sharp, well-read reader" rather than a named role. End with a
short summary - the habits that carried the strong answers and the figures most
likely to be misstated under pressure - never a single pass/fail verdict.

---

## Step 5: Close the Loop

1. **Offer to fix the report issues** from Step 3's section 0, as a step separate from
   `/defend` that the user approves. Scored-but-uncited sources are what `/update`'s
   Step 1b merges. A direct edit follows `/update`'s rules all the same: claims
   revised where they stand, a dated Revision History entry, a scoped reviewer pass
   on the changed claims, then compile and lint. After a fix, refresh the pack
   sections it affects (section 0 at least) so the pack never describes a report
   that no longer exists.
2. Remind the user the prep pack is saved at `reports/<topic_slug>/defense_prep_*.md`
   (gitignored, local-only, matching every other file in `reports/`).
3. For an event (not a stress-test): after it happens, `/outcome` records what
   landed, what didn't, and anything the report should be revised to address -
   useful input for future reports on related topics.

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
4. **This command never modifies the report itself.** Report issues are listed with
   suggested fixes (Step 3, section 0); any fix is a separate, user-approved step
   under `/update`'s rules (Step 5). `/defend` prepares the defense of what's there.
5. **Never assume an event exists.** With no context, run as a stress-test - don't
   invent a meeting, an audience, or a deadline, and don't block on asking for one.
