# graph/ - the library knowledge graph

`graph/index.html` is an interactive map of your whole library: every paper in
`research/seen_sources.json` and every included web source in
`blog/seen_web_sources.json`, with what is new since your last search highlighted.
It is one self-contained file: open it in a browser, with no server and no network.

```bash
python3 tools/knowledge_graph.py --enrich    # fetch missing OpenAlex data, then build
python3 tools/knowledge_graph.py --check     # lint the built page
```

`/graph` runs both, and `/research`, `/rank`, `/synthesize`, `/update` and `/websearch`
rebuild the page when they finish. `graph/index.html` is gitignored: it holds every
title in your library. The tracked files here are `template.html`, the page's own code
in `parts/`, `vendor/` and this README.

## What the page shows

The page has five tabs. **M** minimises the tab bar and every card to small labelled
chips, and restores them; each card also has its own minimise control. On a phone-width
screen the cards start minimised so the globe is visible.

**Overview** opens first: the "On your map" card and the research globe.

- *On your map* gives the number of items shown, a **Show: Both | Papers only | Web
  only** switch with a count on each choice, and the research interests with their
  counts. Click a name to hide or show that interest, and its dot to colour it. At most
  six interests are coloured at once (the six largest by default), so no colour repeats;
  the rest are grey. It also counts what is new since your last search (click that line
  to show only those) and the library's research groups and gaps, each a link to its
  view in Explore.
- The map starts on your **shortlist**: papers and web sources graded Core or
  Supporting, plus everything not yet scored, so new finds always show. "Include
  peripheral and excluded" brings in the rest, and the card says how many that is. The
  same filters apply in every tab, so the globe and the lists never disagree.
- On the **globe**, each region is a research interest (wider for more items, never too
  narrow to read) and height is publication year, newest at the top, with undated items
  at the south pole. Zoomed out, each glow is a sub-area, labelled with its count and how
  many items in it are new. Zoom in (scroll, the toolbar, or double-click) and the glows
  open into items: ● a paper, ■ a web source, a ring around an item that is new since
  your last search. A key names the rings whenever ringed items are in view. At most
  2,500 items are drawn at once, highest scored first; the notice in the corner says
  when it is trimming.
- **Click an item** for its card: interest, sub-area, year, grade, and how many library
  papers it cites and is cited by. Everything else dims, and its citation lines are drawn
  on the globe, amber to
  the papers it cites and blue from the papers that cite it, with an arrowhead on the
  cited paper; the card says what each colour means in words. Next steps highlight what
  it cites, what cites it, its research group's other papers, or its sub-area, and
  "Open full details" takes you to it in Explore. Esc or empty space clears it.
- The toolbar zooms in and out (`+`/`-`), fits the whole globe (`0`), and switches
  dragging between turning the globe and moving it (`H`). Drag it by its grip.

**How it connects** shows the kinds of thing in the library (research interests,
sub-areas, papers, web sources, research groups, reports, gaps), their counts, and how
they link. Click a kind for what it connects to and where to see all of them.

**Explore** holds the detailed views, keys 1-4:

- **Library** - papers and web sources next to the sub-areas they are labelled with,
  from your profile's "Sub-areas of interest" (`python3 tools/state.py subareas`).
- **Research groups** - papers clustered by lab: the group of authors around each
  paper's senior (last) author, found from OpenAlex author records
  (`tools/kg_labs.py`). Grey lines join papers from different labs that share an author.
- **Timeline** - publication year left to right, with an "Undated" lane; arrows show
  which library papers cite which.
- **Gaps** - your reports' open questions, and computed gaps (thin sub-areas, no recent
  work, attacks with no defence, scored papers no report cites, profile landmarks the
  library lacks), each with the rule that produced it (`tools/kg_gaps.py`).

Colour is the research interest in every view. Shape is the kind of source (sphere =
paper, sized by overall score; cube = web source, not peer-reviewed; diamond = gap),
how solid a paper looks is its status, a ring marks new items, and a dot on top marks a
paper read in full. The legend explains each encoding in the view you are in. Every
count is a link to the list of items it counts, and **List view** shows exactly what
the graph shows as a sortable table; the list exports as a Markdown or CSV reading
list. With more than 1,500 items shown, the 3D views draw the highest scored 1,500 and
say so; the list always has everything.

Click anything for its details; the camera stays where it is. Double-click a shape to
zoom to it, and double-click again (on it or on empty space) to go back. The floating
toolbar zooms (`+`/`-`), fits everything (`0`), and switches dragging between turning
the graph and moving it (`H`). Esc leaves focus; Left and Right walk the trail of
recently viewed items.

**Ask** turns a plain question into the same filters and steps you could take by hand,
and shows them, so every answer is exact and repeatable; no AI is used. It reads
questions about interests, kinds of source, contributions (attack, defence, survey,
...), years ("since 2024", "between 2020 and 2023"), new items, "with no defence",
"what cites ...", "what does ... cite", "papers from the same lab as ...", "thin
sub-areas" and "scored but never used in a report". A question with a word it cannot
read says so, rather than answering a different question. Answers open on the map or
as a list you can export.

**Status** says when the map was built, what is shown and hidden and why, OpenAlex
coverage, missing sub-area and contribution labels, and the build's warnings, each
problem with the command that fixes it.

The address bar records the tab, view, selection, filters and date, so a bookmark
reopens the same picture. Bookmarks from the earlier Simple/Advanced page still open, on
Overview or Explore respectively.

## Performance

The page is built for libraries of tens of thousands of items. The limits, measured at
20,000 items with `--synthetic 20000`:

- the first globe frame within 2,000 ms of the page starting to load;
- turning the globe: median frame at most 16 ms, 95th percentile at most 33 ms;
- the built page under 30 MB (a unit test checks this).

To measure, build with `python3 tools/knowledge_graph.py --synthetic 20000`, open the
page with `#perf=1` at the end of the address, keep the window focused for a few
seconds, and read `window.kgPerf` in the browser console: `firstDraw` (ms since the page
started loading) and `frames` (ms per frame for 120 frames of turning). On 2026-10-31 in
the desktop app's browser: first frame about 280 ms, frames 0.6 to 1.2 ms median and
under 2 ms at the 95th percentile.

## How it is built

`tools/knowledge_graph.py` reads state, the profile, `reports/*/` and
`research/graph_cache.json` (OpenAlex authorships and references, fetched by
`tools/kg_enrich.py`), and writes one JSON block into `template.html`. Every `<` in the
data is written as `\u003c`, so a title cannot break out of the page's script, and the
page builds every element from the data as text, never as HTML.

The page's own code is split by tab into `parts/` (`globe.js`, `overview.js`,
`connects.js`, `ask.js`, `status.js`), and `template.html` holds what the tabs share: the
filters, the selection and Explore. The parts and the two renderers in `vendor/` are
inlined into the page; `vendor/LICENSES.md` records
their versions, licences and checksums. three.js 0.160 logs a deprecation warning for
its non-module build, and 3d-force-graph a "multiple instances of Three.js" warning;
both are harmless.

`python3 tools/knowledge_graph.py --synthetic 1000` builds a made-up library of 1,000
papers and 100 web sources over twelve interests instead, for checking that the page
stays responsive at that size (see Performance).
