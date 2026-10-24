# graph/ - the library knowledge graph

`graph/index.html` is an interactive 3D map of your whole library: every paper in
`research/seen_sources.json` and every included web source in
`blog/seen_web_sources.json`, with what is new since your last search highlighted.
It is one self-contained file: open it in a browser, with no server and no network.

```bash
python3 tools/knowledge_graph.py --enrich    # fetch missing OpenAlex data, then build
python3 tools/knowledge_graph.py --check     # lint the built page
```

`/graph` runs both, and `/research`, `/rank`, `/synthesize`, `/update` and `/websearch`
rebuild the page when they finish. `graph/index.html` is gitignored: it holds every
title in your library. The tracked files here are `template.html`, `vendor/` and this
README.

## What the page shows

The page opens in **Simple** mode: the graph, one key that is also the filter, and a
small summary card for whatever you click. The key shows colour per research interest
and shape per kind of source (papers, web sources, gaps, your reports), with counts;
untick to hide, or leave two interests ticked to see them together. If a filter set in
Advanced is also in effect, the key names it and offers to clear it. **More details**
on a card, or the **Advanced** switch in the top bar, opens the full interface below;
the page remembers which one you used last.

To keep text off the graph, only the research-interest names are always shown. Sub-area,
report and lab names appear as you zoom in close, or next to whatever you click; long
names are shortened with "…", and the full name is in the hover tooltip and the card.

In **Advanced**, four views, keys 1-4:

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
the graph shows as a sortable table. The list exports as a Markdown or CSV reading
list.

Click anything for its details; the camera stays where it is. Double-click a shape to
zoom to it, and double-click again (on it or on empty space) to go back. The floating
toolbar - drag it by its grip, or focus the grip and use the arrow keys - zooms in and
out (`+`/`-`), fits everything (`0`), and switches dragging between turning the graph
and moving it with a hand (`H`). Esc leaves focus; Left and Right walk the trail of
recently viewed items. The address bar records the view, focus, filters and date, so a
bookmark reopens the same picture.

## How it is built

`tools/knowledge_graph.py` reads state, the profile, `reports/*/` and
`research/graph_cache.json` (OpenAlex authorships and references, fetched by
`tools/kg_enrich.py`), and writes one JSON block into `template.html`. Every `<` in the
data is written as `\u003c`, so a title cannot break out of the page's script, and the
page builds every element from the data as text, never as HTML.

The two renderers in `vendor/` are inlined into the page; `vendor/LICENSES.md` records
their versions, licences and checksums. three.js 0.160 logs a deprecation warning for
its non-module build, and 3d-force-graph a "multiple instances of Three.js" warning;
both are harmless.

`python3 tools/knowledge_graph.py --synthetic 1000` builds a made-up 1,000-paper
library instead, for checking that the page stays responsive at that size.
