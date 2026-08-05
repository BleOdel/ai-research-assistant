# Defense/Presentation Prep Framework

Used by `/defend` to turn a compiled `/synthesize` report into a prep pack for
presenting or defending it out loud - to a supervisor, in a lab meeting, at a
conference, or in a thesis viva. The report is this framework's equivalent of a
submitted CV/cover letter: whoever is on the other side of the table has (or will
have) read it, so every prepared answer must be consistent with what it actually
claims - never a stronger or different claim than the paper on record.

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

If the user wants to practice:

1. Warm-up: one easy, expected question (e.g. "summarize your headline finding in
   two sentences").
2. Two or three questions from the Open-Questions-derived list, in the order they'd
   plausibly come up (most obvious gap first).
3. One question about an excluded/peripheral source - "why not X?"
4. One genuine curveball - a standard hard question from the list above, or (if a
   specific audience member's own work was researched in `/defend`'s Step 2) a
   question grounded in a real tension between their work and the report's
   conclusion.

After each answer, give brief feedback: what was well-grounded, what strayed beyond
what the report actually supports, and which specific report passage or source would
have made the answer stronger. Calibrate register to the profile's expertise level
for this topic (`01-researcher-profile.md`'s Depth Calibration) - an expert-level
defense should sound like peer-level engagement with what's contestable, not a
rehearsed elevator pitch.
