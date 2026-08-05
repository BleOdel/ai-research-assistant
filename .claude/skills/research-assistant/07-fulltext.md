# Full-Text Reading Rules

When and how to read a paper's full text instead of working from its abstract.
The mechanism is the `paper-fetch` utility skill
(`.agents/skills/paper-fetch/SKILL.md`): it downloads open-access PDFs into
`research/fulltext/` (gitignored, cached, deterministic filenames), and the Read
tool reads them directly - up to 20 pages per request, so read long papers in
ranges rather than one call.

## Why this exists

Abstract-only evidence is the framework's biggest quality ceiling. It was measured
directly during this framework's development: the Heimdall NDSS 2024 paper's key
claims (attack accuracy, threat-model constraints) could only be verified by
reading the full PDF, and doing so materially changed what the report could
honestly say. An abstract tells you what the authors claim; the full text tells
you what they actually showed.

## When to fetch full text

In priority order:

1. **`/synthesize`'s fact-check pass - always try.** For every source a draft
   cites, the reviewer agent should attempt `paper-fetch` first and verify claims
   against the actual paper, falling back to the abstract (plus WebFetch on the
   landing page) only when no open-access PDF exists. A claim verified against
   full text is a stronger evidence basis than one verified against an abstract -
   and the report's evidence-basis notes should say which one backs each source.
2. **`/synthesize`'s scoring pass - when the abstract can't answer.** If a
   source's Relevance or Rigor score genuinely turns on something the abstract
   doesn't state (the evaluation setup, the sample size, whether a method applies
   to the topic's setting), fetch and read the relevant sections rather than
   guessing a score.
3. **Direct user requests** - "read this paper," "what does the paper actually
   say about X."
4. **`/defend` prep** - when a likely question probes a cited source's details
   (limitations, evaluation scope), reading the actual paper beats paraphrasing
   its abstract confidently.

**`/research` and `/rank` deliberately do NOT fetch full text.** Discovery and
batch triage are cheap by design - abstract-level scoring across many sources is
their entire point, and `/synthesize` re-scores properly anyway. Downloading
dozens of multi-MB PDFs during discovery would be slow and wasteful.

## Rules

1. **Open access only, no exceptions.** `paper-fetch` refuses paywalled sources
   (`NO_OA_PDF`) and never scrapes publisher sites. The honest handling of a
   paywalled source is: verify what you can from the abstract and landing page,
   and record the weaker evidence basis explicitly - "verified against abstract
   only (no open-access full text)" - in the scoring notes and, where it matters,
   the report. Never present abstract-verified claims as if they were
   full-text-verified.
2. **Check the cache first, implicitly.** `fetch` is idempotent - a cached file
   returns instantly with `"cached": true`. Never bypass it with `--force` unless
   the file is corrupt.
3. **Never hand-retry `RATE_LIMITED` or `NO_OA_PDF`.** Same rule as every
   connector: the backoff is built in, and `NO_OA_PDF` is not transient. For an
   OA-but-landing-page failure, the error message includes the landing URL - it
   is legitimate to WebFetch that page, find the direct PDF link, and pass it to
   `fetch` as a URL (that's following the paper's own published open-access
   trail, not scraping a paywall).
4. **Cite what you read.** If a claim in a report was verified against a specific
   section of the full text, the fact-check notes should say so (e.g. "verified
   against §5.2, Table 3") - it makes the next fact-check pass, and any `/defend`
   prep, dramatically cheaper.
5. **Read in ranges.** The Read tool caps PDF reads at 20 pages per request. For
   scoring, the introduction and evaluation sections usually decide the score;
   read those first rather than paging through front-to-back.
