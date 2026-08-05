# Living-Update Rules

Used by `/update` to refresh an existing `/synthesize` report with what's changed
since it was written, instead of producing a fresh report each time. The result is a
single living document: the body stays current, and a dated Revision History section
records what changed and why.

## The Core Principle: Revise In Place, Log the Change

A living report is not an append-only diary - a reader opening it today should get
today's accurate synthesis without mentally patching the body against a stack of
addenda. So:

- **The body is always current.** New findings are merged into the thematic sections
  where they belong; claims that new work contradicts are revised where they stand.
- **The Revision History records the delta.** Every update run appends one dated
  entry summarizing what changed and, critically, *why* - which new sources drove
  each change. History is append-only; body sections are not.

Never do the reverse (append "Update: actually..." paragraphs into the body while
leaving stale claims standing) - that's how a report quietly becomes wrong in its
own main text.

## Classifying a New Source's Impact

For each new source that scores Core or Supporting (per `02-source-evaluation.md` -
Peripheral/Excluded sources are logged in `seen_sources.json` but don't trigger
report changes), classify what it does to the existing report. One source can match
more than one category:

1. **Extends an existing theme** - new work squarely inside an existing thematic
   section. Merge: add the citation and a sentence-to-paragraph of prose in that
   section, adjusting the section's framing only if the new work shifts it (e.g.
   what was "the only demonstrated attack" is now one of two).
2. **Opens a new theme** - work that doesn't fit any existing section. Merge: new
   subsection in the thematic body, plus a Technical Findings entry (per
   `03-report-templates.md`'s standard section) and a comparison-table row where the
   table exists.
3. **Contradicts or weakens an existing claim** - the highest-priority category.
   Merge: revise the claim where it stands to reflect the current state of evidence
   (both sources cited, disagreement stated per the framework's honesty rules -
   never silently pick a winner). The Revision History entry must name the specific
   claim that changed, since a reader of a prior version may be relying on it.
4. **Answers or reshapes an Open Question** - merge: update the Open Questions
   section (remove/reword the question, citing what answered it) and add the answer
   to the relevant body section. Open Questions that get *partially* answered stay
   listed, reworded to what genuinely remains open.
5. **Strengthens an existing claim** - new independent evidence for something
   already stated. Merge: add the citation; only expand prose if the strengthening
   is itself notable (e.g. first replication).

If a category-3 contradiction would invert the report's headline conclusion (the
abstract's own claim), say so to the user before drafting - that's no longer an
update, it's a rewrite decision the user should make deliberately (`/synthesize`
fresh, with the old report archived, may serve better than in-place surgery).

## Revision History Section Format

Lives immediately after the Abstract (a reader should see the report's currency
before its content). LaTeX-wise it's a plain unnumbered section
(`\section*{Revision History}`) with one `\paragraph{}` per update run:

```latex
\section*{Revision History}
\paragraph{YYYY-MM-DD} Initial synthesis. N sources across M databases.
\paragraph{YYYY-MM-DD} Update: K new sources since YYYY-MM-DD. <one sentence per
substantive change, naming the section revised and the driving citation(s)>.
```

The initial-synthesis line is added retroactively on a report's first `/update` run
(sourced from the report's own metadata block date). The metadata block's search
scope line is also refreshed each run: date range extended, any newly-queried
connectors added.

## Scope Discipline

- **An update run only touches what the new sources justify.** No opportunistic
  rewrites of unaffected sections, however tempting - unchanged prose is what makes
  the Revision History a trustworthy record of what actually changed between
  versions.
- **Fact-check scope matches change scope.** The reviewer pass covers new and
  revised claims (and any claim whose citation set changed), not the full report -
  claims untouched since the last verified version stay verified. This is what
  makes updates materially cheaper than a fresh `/synthesize`.
- **Superseded sources stay cited where historically apt.** If new work supersedes
  an older source, the older one isn't scrubbed - the prose says "X first showed
  ..., later superseded by Y" where the lineage matters, or drops to the comparison
  table where it doesn't. Only genuinely wrong-in-hindsight claims lose citations.
- **Update `seen_sources.json` statuses additively** as ever: new sources carried
  into the report get `status: "synthesized"`; scored-but-not-carried ones keep
  their scored status.
