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

### 3. Rigor / Venue Signal (0-100)
Signal from where and how the work was published.

| Score | Meaning |
|-------|---------|
| 80-100 | Peer-reviewed venue with strong reputation in the field |
| 60-79 | Peer-reviewed venue, workshop, or well-established conference |
| 40-59 | Preprint (e.g. arXiv) with no venue yet, but methodologically sound |
| 0-39 | No venue, no clear methodology, or self-published with red flags |

Preprints are not penalized for being preprints per se (arXiv is one of the four
shipped connectors) - score the methodology and reasoning quality visible in the
abstract/content, and note venue status explicitly in the output so the reader can
weigh it themselves.

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

## Weighting

- Relevance: 40%
- Rigor / Venue Signal: 25%
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

| Source | Relevance | Recency | Rigor | Impact | Overall | Verdict |
|--------|-----------|---------|-------|--------|---------|---------|
| [Author, Year] | XX/100 | XX/100 | XX/100 | XX/100 or n/a | XX/100 | Core/Supporting/Peripheral/Excluded |

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
