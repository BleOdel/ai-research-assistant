# Web / Grey-Literature Source Evaluation

Used by `/websearch`. This is a **separate rubric from
`02-source-evaluation.md`**, not a variant of it - applying the academic
four-dimension rubric to a blog post produces nonsense, because a blog has no
venue to signal rigor and no citation count to signal impact.

Grey literature earns its place for reasons academic sources cannot: it is faster
(published in days, not the 12-18 months of a review cycle), more concrete (real
configurations, real failure modes, real numbers from production), and often the
only written record of practice. It also has no peer review, no obligation to
disclose limitations, and frequently a commercial motive. Both facts have to be
carried into the output.

## Scoring Dimensions

### 1. Relevance (30%)
Does the page actually address the topic, judged from its **fetched content**, not
its title or search-result snippet?

| Score | Meaning |
|-------|---------|
| 80-100 | The topic is the page's primary subject |
| 60-79 | A major section addresses it directly |
| 40-59 | Mentioned substantively but incidental to the page's purpose |
| 0-39 | Passing mention, or the page turned out to be about something else |

SEO-optimized pages are engineered to match queries they do not answer. A title
match with thin body content scores low here - this is the most common failure
mode in web search, exactly as abstract-vs-title mismatch is for papers.

### 2. Authority (25%)
Who wrote it, and what standing do they have on *this specific* subject?

| Score | Meaning |
|-------|---------|
| 80-100 | Named author with demonstrable first-hand standing: they built the system, maintain the project, published research in the area, or the page is official documentation from the maintainers |
| 60-79 | Named practitioner at a relevant organization, writing from evident direct experience |
| 40-59 | Named author, credible outlet, but no specific expertise demonstrated on this topic |
| 0-39 | Anonymous, no attributable author, content-farm patterns, or evident AI-generated filler |

Named authorship is close to a precondition for anything above 40. If the author
cannot be identified, say so explicitly rather than scoring around it.

### 3. Evidence Quality (25%)
Are the claims *shown* or merely *asserted*?

| Score | Meaning |
|-------|---------|
| 80-100 | Reproducible: code, configs, benchmark methodology, datasets, or measurements a reader could re-run and check |
| 60-79 | Concrete specifics - version numbers, real figures, named tools, described setup - but not fully reproducible |
| 40-59 | Experience-based narrative with no verifiable specifics |
| 0-39 | Pure assertion, opinion, or unattributed claims presented as fact |

This dimension does most of the work separating a valuable engineering writeup from
a plausible-sounding one, and it is where grey literature most often outperforms
papers: a post with a working repository is more checkable than a paper whose
artifact was never released.

### 4. Recency (20%)
Weighted higher than in the academic rubric, because grey literature decays faster:
a post about a specific tool version can be actively misleading three years later,
where a foundational paper stays useful.

| Score | Meaning |
|-------|---------|
| 80-100 | Current for the topic's pace, or explicitly maintained/updated |
| 60-79 | Slightly dated but the substance still holds |
| 40-59 | Dated; some specifics are now wrong but the reasoning survives |
| 0-39 | Superseded - version-specific details no longer apply |

**An undated page scores no higher than 50 and must be flagged as undated.** Never
infer a date from surrounding design, a copyright footer, or the search engine's
guess.

## Independence: A Label, Not a Score

Every source carries a mandatory independence label. This is deliberately **not** a
scored dimension - a vendor's own engineering blog is often the single best source
on their system, and penalizing it numerically would be wrong. The reader simply
has to know which they are reading.

| Label | Meaning |
|-------|---------|
| `independent` | No commercial relationship to what is being evaluated |
| `first-party` | Written by the makers about their own work (official docs, engineering blogs). Frequently the most authoritative source *and* the least neutral one |
| `vendor-competitive` | Discusses or benchmarks a competitor's product. Treat comparative claims as marketing until independently corroborated |
| `sponsored` | Paid placement, affiliate content, or undisclosed-but-evident promotion |
| `unclear` | Relationship could not be determined from the page |

A `vendor-competitive` or `sponsored` source may still be cited - but its
comparative claims must be attributed in the output ("X's own benchmark reports
…"), never restated as established fact.

## Content Type

Classify each source; the type sets reader expectations more than any score does:

`engineering-blog` · `official-docs` · `standard-or-spec` · `research-adjacent`
(preprint summaries, lab blogs) · `talk-writeup` · `news` · `forum-thread`
(HN/Reddit/Stack Overflow) · `tutorial` · `opinion` · `marketing`

`marketing` content is recorded and excluded rather than silently dropped, so a
later run does not rediscover and re-evaluate it.

## Weighting and Thresholds

- Relevance 30% · Authority 25% · Evidence Quality 25% · Recency 20%

| Overall | Tier | Meaning |
|---------|------|---------|
| 70+ | **Core** | Cite substantively; safe to build an argument on |
| 50-69 | **Supporting** | Cite for context, corroboration, or a specific detail |
| 30-49 | **Peripheral** | Include only if it fills a genuine gap; label the weakness |
| <30 | **Excluded** | Record in state, do not include in the output |

Thresholds sit lower than the academic rubric's (75/55/35) because the ceiling is
lower: a blog post cannot score on venue prestige or citation velocity. A Core web
source is not equivalent to a Core paper, and the HTML output says so.

## Cross-Checking Rule

**A factual claim that appears in only one grey-literature source, with no
reproducible evidence behind it, is reported as attributed opinion - never as
fact.** Where two or more independent sources agree, say so; where they conflict,
present both and state that the conflict is unresolved.

This is the grey-literature equivalent of `04-citation-rules.md`'s
verify-before-cite rule. The failure mode it guards against is specific and common:
one confident blog post gets quoted by three others, and an unsourced assertion
acquires the appearance of consensus. Check whether apparent corroboration traces
back to a single origin.

## Relationship to the Academic Track

`/websearch` and `/research` are deliberately separate: separate state files,
separate output folders, separate rubrics. Do not merge web sources into
`research/seen_sources.json`, and do not cite a blog post in a `/synthesize` report
as though it were peer-reviewed.

Where a web source genuinely belongs in an academic report - a widely-referenced
technical standard, an official specification, a dataset release page - cite it in
the LaTeX report as a `@misc` entry with an access date, and note in the prose that
it is not peer-reviewed.
