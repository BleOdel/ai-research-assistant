# Interactive HTML Report Format

Used by `/websearch`. The web track's output is a self-contained interactive HTML
page rather than a compiled PDF - the reasons are practical, not stylistic: web
sources are read *by following links*, the source count varies far more than in a
literature review, and filtering by credibility tier is the main thing a reader
wants to do with a grey-literature scan.

## Files

For a topic, `/websearch` writes:

- `blog/<topic_slug>/index.html` - the report (open directly in a browser)
- `blog/<topic_slug>/sources.json` - the same source array, standalone, so it can be
  re-used without parsing HTML

`<topic_slug>` follows the same convention as `reports/`: lowercased, spaces to
hyphens.

Both are gitignored (`blog/*/`). The template and README directly under `blog/`
stay tracked.

## Building the Page

**Start from `blog/template.html` - do not author a page from scratch.** The
template is a fixed shell with a rendering script already written; the command's job
is only to replace five tokens. Hand-writing per-source HTML is the failure mode
this design exists to prevent.

| Token | Replace with |
|-------|--------------|
| `[TOPIC]` | Human-readable topic. Appears in `<title>` and `<h1>` |
| `[RUN_DATE]` | `YYYY-MM-DD` |
| `[SCOPE_NOTE]` | One paragraph: what was searched, what was excluded and why, known coverage gaps. Plain text or a single `<p>` |
| `[SYNTHESIS]` | The findings prose. HTML fragment - `<p>`, `<h3>`, `<ul>`, `<li>`, `<strong>`, `<em>`, `<a>` only |
| `[SOURCES_JSON]` | A JSON array matching the schema below |

`[TOPIC]` appears twice (title and heading) - replace both.

**After writing, verify no `[TOKEN]` placeholders remain.** A leftover token is the
HTML equivalent of a `??` in a compiled PDF: it means the build did not complete.

## Source Schema

Every element of `[SOURCES_JSON]`:

```json
{
  "title": "Page title as published",
  "url": "https://…",
  "author": "Name, or null if none is identifiable",
  "site": "example.com",
  "date": "YYYY-MM-DD, or null if the page is undated",
  "type": "engineering-blog | official-docs | standard-or-spec | research-adjacent | talk-writeup | news | forum-thread | tutorial | opinion | marketing",
  "tier": "Core | Supporting | Peripheral",
  "score": 82,
  "scores": { "relevance": 88, "authority": 80, "evidence": 85, "recency": 75 },
  "independence": "independent | first-party | vendor-competitive | sponsored | unclear",
  "summary": "One or two sentences on what this source actually contributes",
  "keyPoints": ["Specific findings, one per string"],
  "caveat": "Why to read this one with care, or null"
}
```

Rules that the schema cannot enforce but the output depends on:

- **`author` and `date` are `null`, never invented.** The template renders "no named
  author" and "undated" for null, which is honest. A guessed date is worse than no
  date, and undated pages are capped at Recency 50 by
  `09-web-source-evaluation.md`.
- **`score` must equal the weighted sum** of `scores` (Relevance 30%, Authority 25%,
  Evidence 25%, Recency 20%), and `tier` must match it (70+ Core, 50-69 Supporting,
  30-49 Peripheral). A card showing a tier inconsistent with its own sub-scores
  destroys trust in every other card on the page.
- **`caveat` is required** whenever `independence` is `vendor-competitive`,
  `sponsored`, or `unclear`, or when `tier` is `Peripheral`. The template gives it a
  highlighted block; leaving it null in these cases hides the thing the reader most
  needs.
- **Excluded sources (<30) do not appear in the array.** They are recorded in
  `blog/seen_web_sources.json` with `status: "excluded"` so a later run does not
  rediscover and re-evaluate them.

## Writing the Synthesis

Same discipline as a `/synthesize` report, with grey literature's specific hazards:

- Organize by **theme or claim**, never as a list of pages visited.
- Attribute contested claims to their source in the prose ("Vendor X's own benchmark
  reports …"), rather than stating them flat.
- Where independent sources agree, say so - that is the strongest signal available
  in a corpus with no peer review. Where they conflict, present both and say the
  conflict is unresolved.
- **Check whether apparent corroboration traces to a single origin** before
  presenting it as consensus (see `09-web-source-evaluation.md`'s cross-checking
  rule).
- State what the scan did *not* find. A topic where practitioners have written
  nothing substantive is a real finding, and often more useful than a thin summary.

## Rendering Constraints

The template is deliberately self-contained: no CDN, no external fonts, no network
calls at runtime. It opens from `file://` and works offline. Preserve this - adding
an external stylesheet or script would break offline use and leak the reader's
topic to a third party.

It is theme-aware (`prefers-color-scheme`, plus `data-theme` overrides), responsive,
and keyboard-navigable. The interactive layer provides text filtering, tier and type
chips, sorting by score/date/authority/evidence, and expandable per-source detail.

**If the source list is edited by hand afterwards, edit `sources.json` and rebuild
rather than editing the JSON embedded in the HTML** - keeping the two in sync
matters, since `sources.json` is what a later `/websearch` run reads back.

## Verification Before Presenting

1. No `[TOKEN]` placeholders remain anywhere in the file.
2. The embedded JSON parses (the template shows a parse-failure message rather
   than a blank page, so a silent break is visible - but check anyway).
3. Every `score`/`tier` pair is internally consistent with its sub-scores.
4. Every source with a flagged independence label has a non-null `caveat`.
5. `sources.json` and the embedded array are identical.
