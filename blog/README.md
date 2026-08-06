# blog/ — Web & Grey-Literature Scans

Output folder for `/websearch`, the counterpart to the academic track's `reports/`.

```
blog/
├── README.md            this file (tracked)
├── template.html        the interactive report shell (tracked, shareable)
└── <topic-slug>/        one folder per scan (gitignored)
    ├── index.html       the report — open directly in a browser
    └── sources.json     the same source data, standalone
```

## Why this is separate from `reports/`

A practitioner blog post and a peer-reviewed paper are different kinds of evidence.
Blending them into one pile would let an unreviewed assertion sit beside a
replicated result with nothing marking the difference — so the two tracks stay
separate all the way down: separate discovery state, separate scoring rubric,
separate output.

| | Academic track | Web track |
|---|---|---|
| Command | `/research` → `/synthesize` | `/websearch` |
| Rubric | `02-source-evaluation.md` | `09-web-source-evaluation.md` |
| Weights | Relevance 40 / Rigor 25 / Impact 20 / Recency 15 | Relevance 30 / Authority 25 / Evidence 25 / Recency 20 |
| Core threshold | 75+ | 70+ |
| State | `research/seen_sources.json` | `blog/seen_web_sources.json` |
| Output | LaTeX → PDF | Interactive HTML |

The web rubric replaces *Rigor* (which needs a venue) with **Authority** (who wrote
it, and do they have standing here) and *Impact* (which needs citations) with
**Evidence Quality** (are claims shown or merely asserted). Recency is weighted
higher, because grey literature decays faster — a post pinned to a tool version can
be actively misleading three years on.

**Core here is not Core there.** A web source cannot score on peer review or
citation velocity, so the thresholds sit lower and the ceiling is lower. The
generated page says this in its footer.

## Independence labels

Every source carries one, shown as a badge on its card:

`independent` · `first-party` · `vendor-competitive` · `sponsored` · `unclear`

This is a **label, not a score**. A vendor's own engineering blog is frequently the
single best source on their system — penalizing it numerically would be wrong. The
reader just has to know which they are reading, and comparative claims from
interested parties get attributed in the prose rather than stated as fact.

## The template

`template.html` is a fixed shell with the rendering logic already written.
`/websearch` fills in five tokens; the page renders itself from an embedded JSON
array. It is deliberately self-contained — no CDN, no external fonts, no network
calls — so it opens from `file://`, works offline, and does not leak what you are
researching to a third party.

It is theme-aware, responsive, and keyboard-navigable, with live filtering, tier and
type chips, sorting, and expandable per-source detail.

Editing it is fine and expected — it is yours. Keep it self-contained, keep the
`[TOKEN]` names intact, and keep the independence badge visible. Format details are
in `.claude/skills/research-assistant/10-html-reports.md`.

## Privacy

Everything under `blog/<topic-slug>/` and `blog/seen_web_sources.json` is
gitignored, enforced in CI by `tools/security_guards.py`. Only this README and the
template are tracked. Your scans stay on your machine.
