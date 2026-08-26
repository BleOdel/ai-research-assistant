# Source Evaluation Framework

<!-- SETUP: Research interests are personalized by running /setup -->

This framework is used by `/research` (quick triage only, see below), `/rank` (full
scoring for triage - see below), and `/synthesize` (full scoring, authoritative). It
exists so relevance judgments are consistent across a run and across runs - not a
fresh vibe check on every source.

## Scoring Dimensions

Evaluate each source against these four dimensions:

### 1. Relevance (0-100)
Does the source actually address the topic, based on its abstract/content - not its
title alone?

| Score | Meaning |
|-------|---------|
| 80-100 | Topic is the paper's primary subject |
| 60-79 | Topic is a major component or direct application |
| 40-59 | Topic is discussed but secondary to the paper's main contribution |
| 0-39 | Topic is mentioned in passing or only superficially related |

Score from the fetched abstract or full content. A title match with an abstract that
turns out to be about something else scores low, not high - this is the single most
common way a synthesis quietly goes wrong.

### 2. Recency (0-100)
Weighted by field-appropriate half-life, not a flat "newer is better." Fast-moving
subfields (e.g. LLM architectures) decay faster than foundational or slow-moving ones
(e.g. classical algorithms, theory).

| Score | Meaning |
|-------|---------|
| 80-100 | Published within the field's "current" window (e.g. last 12-18 months for fast-moving CS/ML topics) |
| 60-79 | Still broadly current, occasionally superseded in details |
| 40-59 | Foundational or frequently-cited older work that remains a standard reference |
| 0-39 | Superseded by later work and not commonly cited as foundational |

A landmark 2017 paper can legitimately score 80+ here if it's still the standard
reference; a 2019 paper in a fast-moving area can score low if the field has moved on.
Use judgment, and say so in the notes - don't apply a fixed cutoff blindly.

### 3. Rigor (0-100)

Two inputs, scored separately and then combined: **where** the work was published,
and **how** it was done. Venue alone is not rigor. A methodologically weak paper in a
strong venue and a careful one in a workshop are not equivalent, and a rubric that
scores only venue cannot tell them apart - which makes the methodological critique
that expert-level reports are supposed to deliver (see `01-researcher-profile.md`'s
Depth Calibration) impossible to ground.

**3a. Venue signal** - start here:

| Score | Meaning |
|-------|---------|
| 80-100 | Peer-reviewed venue with strong reputation in the field |
| 60-79 | Peer-reviewed venue, workshop, or well-established conference |
| 40-59 | Preprint (e.g. arXiv) with no venue yet |
| 0-39 | No venue, self-published, or predatory-venue red flags |

**3b. Method quality** - then adjust up or down by up to 20 points, based on what the
fetched abstract or full text actually shows:

| Signal | Adjustment |
|--------|-----------|
| Released artifact - code, dataset, or benchmark a reader could re-run | **+10** |
| Findings independently replicated, or the work is itself a replication | **+10** |
| Empirical evaluation with a stated sample size and protocol | **+5** |
| Systematic review or meta-analysis with stated inclusion criteria | **+5** |
| Position paper, vision paper, or survey presented as new evidence | **-5** |
| Simulation-only, or evaluated solely on data the authors also generated | **-5** |
| Central claim rests on a single case study or anecdote | **-10** |
| Evaluation described in the abstract but no method, N, or baseline stated | **-10** |

Cap the combined result at 0-100. **State the adjustment in the scoring notes** -
"78 (venue 68, +10 released artifact)" - so the reader can see which half of the score
is venue prestige and which is demonstrated method. Where the abstract does not say
enough to judge method, apply no adjustment and note that the method basis is
unknown rather than assuming it is sound; if the claim is load-bearing, that is
exactly when to fetch full text (see `07-fulltext.md`).

Preprints are not penalized for being preprints per se (arXiv is one of the four
shipped connectors) - a preprint with a released artifact and a stated protocol can
out-score an unreproducible conference paper, and should.

**Check for preprint drift.** An arXiv entry may since have been published,
superseded by a later version, or withdrawn. Where a preprint is load-bearing, check
whether a DOI now resolves for it before scoring venue - the framework has already
been caught twice here: two bibliography entries carry a 2025 year against a 2026
DOI, and one source's venue took two manual passes to confirm. Never upgrade venue on
a secondary database's tag alone; confirm against the publisher or the venue's own
proceedings.

### 4. Impact (0-100)
Citation signal, normalized by paper age (a 2024 paper with 20 citations is not less
impactful than a 2015 paper with 20 citations).

| Score | Meaning |
|-------|---------|
| 80-100 | High citation velocity relative to age, or explicitly noted as influential |
| 60-79 | Above-average citation velocity for the field and age |
| 40-59 | Average or unremarkable citation count for its age |
| 0-39 | Very low or no citations, and old enough that this is meaningful (recent papers should not be penalized here - see Recency instead) |

Semantic Scholar's `citationCount` and `influentialCitationCount` fields are the
primary signal when available. Semantic Scholar's unauthenticated API is frequently
rate-limited (see `04-citation-rules.md`'s connector notes), so when it's unavailable
for a run, fall back **in this order**, taking the first that is configured and
responding:

1. `semantic-scholar-search` - `citationCount` + `influentialCitationCount`
2. `openalex-search` - `citedByCount`. Prefer this over Google Scholar: it needs no
   paid account, and a single-work lookup by DOI costs 1 credit against a search's
   10, so it is cheap even when its daily budget is tight.
3. `google-scholar-search` - `citedByCount`. Requires a SerpApi key with a
   250-searches/month free tier, so treat it as the scarcest of the three.
4. None available - score Impact `"insufficient data"` and renormalize per
   *Computing the Overall Score* below.

Every command that scores a source uses this same chain. Do not silently drop a
connector from it.

**These three counts will not agree, sometimes by a lot** - each source indexes
independently, and citation counts are not a fungible number across them. Directly
observed for the same paper at the same point in time during this framework's
development: Semantic Scholar 36, Google Scholar 47, OpenAlex 20 - roughly a 2x
spread on the same underlying fact. Always note which connector a citation count
came from, and never mix counts from different connectors within one comparison
table without labeling each. If none is available, score this dimension
"insufficient data" rather than defaulted to 0 - say so explicitly rather than
silently zeroing a real paper.

## Disclosure: A Label, Not a Score

Every scored source carries a `disclosure` label, recorded alongside its scores in
`research/seen_sources.json`. Like the web track's independence label
(`09-web-source-evaluation.md`), this is deliberately **not** scored - industry
research is often the only work with access to production systems at scale, and
penalizing it numerically would be wrong. The reader has to know which they are
reading.

| Label | Meaning |
|-------|---------|
| `academic` | University or public-institute authorship, no product being evaluated |
| `industry` | Company-authored, but not evaluating the company's own product |
| `self-evaluating` | Authors evaluate their own system, tool, or benchmark. The overwhelmingly common case for systems papers - not a criticism, but their headline numbers are unreplicated by construction |
| `vendor-report` | Company technical report or whitepaper with no peer review, evaluating something the company sells |
| `unclear` | Affiliation or interest could not be determined from what was fetched |

A `self-evaluating` or `vendor-report` source may absolutely be cited - but its
performance claims are **attributed in the prose** ("the authors report 87%…"), never
restated as established fact. The `ai-security` report already does this by hand for
a vendor report claiming an 85% attack success rate with no independent review; this
label exists so the discipline is systematic rather than dependent on a drafter
noticing.

## Corroboration

Scores rate a source. This rates a **claim** - and it is checked at drafting time, not
scoring time.

**A load-bearing claim resting on a single source, with no released artifact behind
it, is attributed in the prose - never stated flatly as fact.** Write "Luo et al.
report 96.51% accuracy", not "the attack achieves 96.51% accuracy". A claim carrying
two or more genuinely independent sources may be stated directly, and the report
should say that they agree - convergence is a finding, not a redundancy to be
compressed away.

Before treating agreement as corroboration, **check that it does not trace back to a
single origin.** Three papers citing one earlier result is one source, not three. This
is the same rule `09-web-source-evaluation.md` applies to grey literature, and there
is no principled reason a peer-reviewed claim should face a weaker standard than a
blog post - which, until this section existed, is exactly what happened.

## Weighting

- Relevance: 40%
- Rigor: 25%
- Impact: 20%
- Recency: 15%

Relevance is weighted highest because an irrelevant source is worthless regardless of
how well-cited or rigorous it is.

## Thresholds

Four verdict tiers. **Write the verdict exactly as `Core`, `Supporting`,
`Peripheral`, or `Excluded`** - one word, no suffix - everywhere a verdict is
recorded: the Output Format table below, `research/seen_sources.json`, and
`research/papers_by_subject.md`. Anything else ("Core Source", "core", "Supporting
Source") is a defect, not a stylistic variant: verdicts are counted and filtered
downstream, and two spellings of one tier silently split every total.

- **Core** (75+): Central to the synthesis, cite substantively
- **Supporting** (55-74): Cite for context or a specific claim
- **Peripheral** (35-54): Mention only if it fills a genuine gap, otherwise omit
- **Excluded** (<35): Do not cite

## Computing the Overall Score

Multiply each dimension by its weight and sum. When Impact is `"insufficient data"`
(see the Impact section above), **do not treat it as zero** - a recent paper with no
citation history yet is not a low-impact paper. Renormalize the remaining three
weights proportionally:

| Dimension | Normal weight | Weight when Impact is unavailable |
|-----------|---------------|-----------------------------------|
| Relevance | 40% | **50%** |
| Rigor | 25% | **31.25%** |
| Recency | 15% | **18.75%** |
| Impact | 20% | (excluded) |

Record `"impact": "insufficient data"` in the source's `scores` object so the
renormalization is visible rather than implied.

This rule is authoritative for **every** command that scores a source - `/research`,
`/rank`, `/synthesize` and `/update` alike - so the same source scores the same
regardless of which command reached it first. Zeroing a missing Impact instead of
renormalizing drags sources across the 75/55/35 verdict boundaries, which is exactly
the kind of silent inconsistency this file exists to prevent.

## Output Format (used by `/synthesize`)

```
## Source Evaluation

| Source | Relevance | Recency | Rigor | Impact | Overall | Verdict | Disclosure |
|--------|-----------|---------|-------|--------|---------|---------|------------|
| [Author, Year] | XX/100 | XX/100 | XX/100 (venue XX, +/-X reason) | XX/100 or n/a | XX/100 | Core/Supporting/Peripheral/Excluded | academic/industry/self-evaluating/vendor-report/unclear |

### Notes
- [1 line per source explaining any non-obvious score, e.g. "high Recency despite 2019
  date - still the standard reference for X"]
```

## Quick Triage (used by `/research` only)

`/research` does not run the full four-dimension scoring above - that's `/rank` and
`/synthesize`'s job, and running it on every raw search result would be wasteful.
Instead, `/research` does a cheap 3-tier signal from title + abstract only:

- **High**: Topic is clearly the paper's primary subject
- **Medium**: Topic is a plausible component, needs a closer read
- **Low**: Title matched the query but the abstract suggests a different focus

This triage exists to help the user pick what to carry into `/rank` or `/synthesize`,
both of which re-score properly. Triage scores are never presented as final relevance
judgments.

## Full Scoring as Triage vs. as Final (`/rank` vs. `/synthesize`)

`/rank` and `/synthesize` both run the full four-dimension rubric above, but at
different depths: `/rank` scores from the abstract and profile only, cheaply, across
many sources at once, to produce a shortlist - it never fact-checks or drafts.
`/synthesize` re-runs the same rubric per source (never trusting a `/rank` score as
final) as part of a deeper pass that also fact-checks every citation against
actually-fetched content before anything is written. A `/rank` verdict is a strong
signal for where to spend `/synthesize` effort, not a substitute for `/synthesize`'s
own scoring pass.
