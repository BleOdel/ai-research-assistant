# Defense/Presentation Prep Framework

Used by `/defend` to turn a compiled `/synthesize` report into a prep pack for
presenting or defending it out loud - to a supervisor, in a lab meeting, at a
conference, or in a thesis viva - or for stress-testing it with no event in view. The
report is this framework's equivalent of a submitted CV/cover letter: whoever is on
the other side of the table has (or will have) read it, so every prepared answer must
be consistent with what it actually claims - never a stronger or different claim than
the paper on record.

## Settings

The setting shapes the register and which sections the pack includes, not the
honesty rules, which never change.

| Setting | Questioner | Questions to ask back |
|---|---|---|
| **Stress-test** (default, no event) | A sharp, well-read reader | Omitted - no one to ask |
| Supervisor / lab meeting | Collegial, probing, wants next steps | Included |
| Conference Q&A | Short, pointed, may not know the area | Included, brief |
| Thesis viva / paper rebuttal | Examining, not exchanging | Omitted |

A stress-test is a full pack without the event framing: the same questions, answers
and report issues, written for someone checking whether their report holds up rather
than rehearsing for a date. Never assume an event the user did not name.

## Report Issues Come First

Preparing a defense means reading the report the way a sharp questioner will, against
the state it was built from, and that read finds problems drafting missed. They go in
the pack's first section, ahead of any question, because a defense is weakest where
the report itself is wrong. Look for:

- **Scored but never cited.** Core/Supporting sources for this topic that the
  `.bib` does not cite (`state.py unmerged`). An expert notices a missing
  foundational paper before anything else. On this framework's first stress-test the
  check found three, including the paper that introduced the report's central concept
  and a benchmark the report named about 30 times.
- **A scope note that undercounts.** Exclusions or found-but-unassessed sources that
  `seen_sources.json` records but the scope note does not mention.
- **Claims a source's own caveat undercuts,** figures quoted without their
  conditions, and named systems or benchmarks that are never cited.

Each issue gets the evidence, how it would come up in questioning, and a suggested
fix. `/defend` never applies the fix itself; it is a separate, user-approved step
under `/update`'s rules, after which the affected pack sections are refreshed. Until
it is fixed, the answer mapping says how to handle the issue honestly if it comes up:
name it first rather than be caught on it. "No issues found" is a valid result, stated
with what was checked.

## Where Likely Questions Come From

In priority order - the report's own honesty discipline is the single best predictor
of what a sharp questioner will ask, because a reviewer's first move is almost always
to probe exactly the gaps the source material already discloses:

1. **The report's own Open Questions section.** This is the highest-value source,
   not an afterthought - `03-report-templates.md` requires every report to state
   disagreements and gaps explicitly rather than smoothing them over, which means
   the report has effectively already drafted the hard questions for you. Take each
   bullet and rephrase it as a spoken question.
2. **Evidence-basis caveats.** Any source flagged with a weaker evidence basis (an
   abstract-only source, one a reviewer's fact-check pass had to correct, one with a
   citation count that couldn't be verified) is a specific, concrete thing to be
   ready to address honestly - not to hide.
3. **Sources that were scored but excluded**, per `research/seen_sources.json` for
   this topic (`Peripheral`/`Excluded` verdicts, or sources marked `unfetchable`).
   "Why didn't you include X?" is a standard challenge; the honest answer is the
   actual score/reason, not a retroactive justification invented on the spot.
4. **Methodological choices the report had to make explicit** - a renormalized
   scoring weight when Impact data was unavailable, a citation style forced by a
   custom template, a source's Rigor score deliberately not upgraded on an
   unconfirmed secondary-database tag (see the keystroke-inference report's VRSafe
   handling for a worked example of exactly this kind of defensible, disclosed
   judgment call).
5. **Standard hard questions for a research synthesis**, generic but always worth
   having answers ready for:
   - "What's the practical impact of this, beyond the literature review itself?"
   - "How does this generalize beyond the sources/scope you actually covered?"
   - "What would change your conclusion?"
   - "How do you know your source selection wasn't cherry-picked?"
   - "What's the single weakest claim in this report, and why did you include it
     anyway?"

## Answering Honestly

For every likely question, the drafted answer must be traceable to something the
report or its sources actually say - the same `04-citation-rules.md` discipline,
extended from written citations to spoken defense:

- If the report's own Open Questions section already states the honest answer is "we
  don't know" or "this can't be determined from the literature surveyed," the
  prepared answer says exactly that, confidently - not hedged into sounding weaker
  than the report already is, and not inflated into false certainty either.
- If a question probes a source with a disclosed weaker evidence basis, the honest
  answer states the caveat plainly (what was and wasn't verified) rather than
  glossing over it under pressure.
- **Never draft an answer that claims something the report doesn't support.** A gap
  gets acknowledged with the report's own reasoning for why it was left as a gap,
  never invented confidence.

## Consistency Brief

A short list of the report's specific claims most likely to be probed - the highest-
citation-count findings, the most surprising or counterintuitive conclusion, the
weakest-evidence-basis source, any claim the fact-check pass in `/synthesize` had to
correct during drafting (if that history is known). The rule, stated plainly: no
claim in the room that isn't in the report, and every claim in the report must be
defensible in depth if pushed.

## Mock Defense / Roleplay Guidelines

Two modes, switchable at any question:

- **Practice** - the user answers first; feedback follows (below). This is the better
  rehearsal for a real event.
- **Walkthrough** - for each question, a model answer, then why it works, the traps
  to avoid (the overclaims and mis-stated figures this report invites), and the
  likely follow-up. Users often want this first, especially for a stress-test or an
  unfamiliar report; "show me" on any question switches to it for that question.

A model answer is held to the same rule as any other: nothing beyond what the report
supports, at the report's own strength ("mostly held", "one static study"), with the
weaknesses volunteered rather than waiting to be found.

Structure, in either mode:

1. Warm-up: one easy, expected question (e.g. "summarize your headline finding in
   two sentences").
2. Two or three questions from the Open-Questions-derived list, in the order they'd
   plausibly come up (most obvious gap first).
3. One question about an excluded/peripheral source - "why not X?"
4. One genuine curveball - a standard hard question from the list above, or (if a
   specific audience member's own work was researched in `/defend`'s Step 2) a
   question grounded in a real tension between their work and the report's
   conclusion.

In practice mode, after each answer, give brief feedback: what was well-grounded,
what strayed beyond what the report actually supports, and which specific report
passage or source would have made the answer stronger. Calibrate register to the
profile's expertise level for this topic (`01-researcher-profile.md`'s Depth
Calibration) - an expert-level defense should sound like peer-level engagement with
what's contestable, not a rehearsed elevator pitch.

End the run with a short summary rather than a verdict: the habits that carried the
strong answers (naming who did the work and their stake in it, using the report's own
verbs, volunteering weaknesses, keeping open tensions open) and the figures most
likely to be misstated under pressure. If the user only saw model answers, say so,
and offer a practice run before any real event.
