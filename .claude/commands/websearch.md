# /websearch - Blog & Website Discovery

Searches practitioner blogs, engineering writeups, official documentation, specs,
and technical discussion for a topic, evaluates each source for credibility, and
produces a **self-contained interactive HTML page** under `blog/<topic_slug>/`.

This is the grey-literature counterpart to `/research` + `/synthesize`. The two
tracks are deliberately separate - separate state, separate output folder, separate
rubric - because a blog post and a peer-reviewed paper are different kinds of
evidence and must not be blended into one undifferentiated pile.

`$ARGUMENTS` is the topic (free text). If empty, use the first Research Interest
from `01-researcher-profile.md` and confirm before proceeding.

Follow these steps in order.

---

## Step 0: Load State and Frameworks

1. Read `blog/seen_web_sources.json` (create as `{"seen": {}}` if missing). Keyed by
   normalized URL.
2. Read `.claude/skills/research-assistant/09-web-source-evaluation.md` (credibility
   rubric) and `10-html-reports.md` (output format) - once each.
3. Read `01-researcher-profile.md` for expertise level (sets the depth the synthesis
   is pitched at) and standing exclusions.

---

## Step 1: Search

**The mechanism here is `WebSearch`, not a connector CLI.** This is a deliberate
choice, not a gap: the four `.agents/skills/*` connectors are academic-database
clients with no useful notion of blog search, and the one general web-search API
already configured (SerpApi, behind `google-scholar-search`) has a 250-searches per
month free tier that is better spent on Google Scholar. `WebSearch` needs no key and
no quota. Do **not** route this command through `google-scholar-search`.

Run **three to five** targeted searches, varying the angle rather than rephrasing
the same query:

- The topic in practitioner phrasing (how someone who *does* this would say it)
- The topic plus an evidence marker: `benchmark`, `postmortem`, `in production`,
  `lessons learned`
- The topic scoped to documentation or specs
- The topic plus a discussion venue where the field actually argues
  (`site:news.ycombinator.com`, a relevant subreddit, a standards mailing list)

Use `allowed_domains` / `blocked_domains` to steer when a first pass returns
content-farm results.

Collect candidate URLs with their titles. **Do not evaluate from search snippets** -
snippets are optimized for the query, not for accuracy.

---

## Step 2: Fetch and Filter

Skip any URL already in `blog/seen_web_sources.json`.

`WebFetch` each remaining candidate and read the actual page. From the fetched
content extract: the real title, a named author (or `null`), the publication date
(or `null` - **never infer one** from a copyright footer or the search result), the
site, and enough substance to score.

Drop immediately, recording `status: "excluded"` with a one-line reason:

- Paywalled or login-gated with no readable content
- Content-farm or evidently AI-generated filler
- The page turned out to be about a different subject

If `WebFetch` returns a cross-host redirect, follow it once with the redirect URL;
if that also fails, record the source as `unfetchable` rather than scoring it from
its snippet.

Aim to fully evaluate **8-15** sources. Beyond that the marginal source rarely
changes the picture, and the page gets harder to read.

---

## Step 3: Score

Score every fetched source against `09-web-source-evaluation.md`: Relevance (30%),
Authority (25%), Evidence Quality (25%), Recency (20%). Assign a `type` and a
mandatory `independence` label.

Present the scoring table in chat before building anything:

```
| # | Source | Site | Type | Independence | Rel | Auth | Evid | Rec | Overall | Tier |
```

Then ask:

> "Build the HTML report from the Core and Supporting sources? Reply yes, or tell me
> which to drop or promote."

**If the user says no, stop here** - the state file is still updated, so nothing is
re-fetched next time.

---

## Step 4: Synthesize and Build

Per `10-html-reports.md`:

1. Copy `blog/template.html` to `blog/<topic_slug>/index.html`.
2. Replace all five tokens (`[TOPIC]` appears twice).
3. Write `[SYNTHESIS]` organized by theme or claim - never as a list of pages
   visited. Attribute contested claims in the prose. Say where independent sources
   agree, where they conflict, and what the scan did not find.
4. Write `[SOURCES_JSON]` to the documented schema, and the identical array to
   `blog/<topic_slug>/sources.json`.
5. `[SCOPE_NOTE]` must state what was searched, what was excluded, and the coverage
   gaps - including any paywalled sources that could not be read.

---

## Step 5: Verify

Run `10-html-reports.md`'s verification list and report it as a pass/fail checklist:

1. No `[TOKEN]` placeholders remain (grep the file - a leftover token is this
   track's equivalent of a `??` in a compiled PDF).
2. The embedded JSON parses.
3. Every `score`/`tier` pair is consistent with its own sub-scores.
4. Every flagged-independence and every Peripheral source has a non-null `caveat`.
5. `sources.json` matches the embedded array.

Then read the file back and sanity-check the rendered structure.

---

## Step 6: Update State and Present

Write every fetched source to `blog/seen_web_sources.json`:

```json
{
  "seen": {
    "<normalized url>": {
      "title": "...", "site": "...", "author": "... or null",
      "date": "YYYY-MM-DD or null", "type": "...", "independence": "...",
      "first_seen": "YYYY-MM-DD", "topic": "<topic>",
      "scores": { "relevance": 0, "authority": 0, "evidence": 0, "recency": 0 },
      "overall_score": 0, "tier": "Core|Supporting|Peripheral|Excluded",
      "status": "included | excluded | unfetchable"
    }
  }
}
```

Present:

```
## Web Scan: <topic> - YYYY-MM-DD

Evaluated N sources (X Core, Y Supporting, Z Peripheral; W excluded).

### Headline findings
[2-4 bullets - the actual conclusions, not a description of the process]

### Credibility picture
[One or two lines: how much is independent vs. first-party, how much carries
reproducible evidence, and whether any claim rests on a single unverified source]

### Verification
[the Step 5 checklist, pass/fail]

Open: blog/<topic_slug>/index.html
```

Tell the user the page opens directly in a browser - no server needed - and that
filtering, sorting, and per-source detail are interactive.

---

## Important Rules

1. **Never fabricate a source, an author, or a date.** `null` is the correct value
   for an unidentifiable author or an undated page, and the template renders it
   honestly.
2. **Never evaluate from a search snippet.** Fetch the page or record it as
   unfetchable.
3. **Independence is always labeled.** A first-party source is often the best
   available and is not penalized - but the reader is told. Comparative claims from
   `vendor-competitive` or `sponsored` sources are attributed in the prose, never
   restated as fact.
4. **A single-source claim with no reproducible evidence is attributed opinion, not
   fact** - and check that apparent corroboration is not three pages quoting one
   origin.
5. **Do not merge web sources into `research/seen_sources.json`**, and do not cite a
   blog post in a `/synthesize` report as though it were peer-reviewed. If a web
   source genuinely belongs in an academic report (a standard, a spec, a dataset
   release), cite it there as `@misc` with an access date and say in the prose that
   it is not peer-reviewed.
6. **Grey-literature tiers are not academic tiers.** A Core web source is not
   equivalent to a Core paper; the page's footer says so and the synthesis should
   not imply otherwise.
