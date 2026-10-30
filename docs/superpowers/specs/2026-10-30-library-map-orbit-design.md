# Library map: Orbit-style redesign, notes as satellites

Design, 2026-10-30. Builds on the library knowledge graph
(`2026-10-21-knowledge-graph-design.md`), which is live as `graph/index.html`.

## Intent

The library graph works, but the researcher found it busy and generic: two sidebars of
controls, a force-directed cluster that looks like every other graph tool, and no place
to think. They want a distinctive, calm interface modelled on GitLab Orbit's dashboard,
and a place to write ideas next to the evidence, with help that guides their thinking as
they write.

The researcher's own words, in order:
- "the side bar information or controls are much and confusing, we should use a
  minimalistic approach"
- "With the graph I feel u with a more unique UI/UX, lets have a look at gitlab orbit"
- "I like it keep it" (the Orbit-style mockup), "we should also add a tool like this"
  (an annotation toolbar: select, pen, shapes, text, close)
- "we need to add a note take, where users can write ideas and save them. We need a
  smart note taker, that assist by guilding the users thoughts and ideas as they write"
- "lets think about each note like satelites in orbit"
- "can we create custom Guide asides from the 5 preset"
- "Remember we need to be able to minimize tabs also"

### What Orbit taught (researched 2026-10-30)

GitLab Orbit's dashboard (docs.gitlab.com/orbit/dashboard) has four tabs, each with one
job: **Overview** ("On your map": one big count, a short breakdown by area with a
coloured dot and a count, and what is still indexing), **Schema** ("How your data
connects": the kinds of thing, their counts and how they link, as a type-level map),
**Query editor** (examples, AI help to write and fix, CSV export) and **Status**. The
overview's centrepiece, built with Three.js, is a globe: points spread over a sphere,
fine glowing arcs between them, dark background, drag to spin. A selected item gets a
card with its type, connection count and suggested next questions. Summary before
detail; a type-level map before the millions of items; honest about what is incomplete.

### What exists now

`graph/index.html`, built by `tools/knowledge_graph.py` from `graph/template.html`
(vendored three.js 0.160 and 3d-force-graph 1.73, inlined; offline; one file). It has a
Simple mode (default: graph, one key that is also the filter, a card per click) and an
Advanced mode (four views: Library, Research groups, Timeline, Gaps; full filters; a
sortable list; Markdown/CSV/PNG export; details panel; trail; bookmarkable address).
A floating, movable toolbar zooms, fits, and switches drag between rotate and move;
double-click zooms to a node and back; labels appear as you zoom in. Data: 358 papers
(325 shown by default), 18 web sources, 683 citation links inside the library, 39 labs
with more than one paper, 23 gaps, 3 interests plus Uncategorized.

A throwaway mockup of this redesign, with the researcher's real data, was reviewed and
kept: `scratchpad/orbit_mock3.html` + `orbit_notes_script.js` in the session that wrote
this document. It is a reference for look and feel, not code to ship.

## First principle (unchanged): information and data clarity

Carried over in full from the knowledge-graph design. In particular: every encoding is
explained where it appears; plain words, never internal state names; every count exact
and clickable to its items; anything derived shows how; uncertain data is marked;
nothing hidden shapes the picture without saying so; motion only when it carries
information or follows a user action; a precise list always one click from any picture.

## Decided by the researcher

1. The Orbit-style redesign, as mocked up: tabs, an "On your map" summary, the research
   globe, a selected-item card with next steps. ("I like it keep it")
2. An annotation toolbar like the one they showed: select, pen, shapes (with a
   dropdown), text, close.
3. A note taker. Notes are satellites orbiting the globe.
4. Guidance while writing, with five preset prompts (Claim, Evidence, Against, Gap,
   Next step) and the researcher's own custom prompts.
5. Custom prompts are one list that appears on every note, not templates (they chose
   option 1, 2026-10-30).
6. Tabs and panels can be minimised.
7. Two open points decided by the designer and accepted when the researcher said "yes,
   write up the design plan": notes are saved as files in the project; satellites stay
   still unless hovered.

## Goals

- **G1 Calm overview first.** The page opens on a summary and the globe, nothing else.
- **G2 The globe informs.** Every position on it means something (below), and the
  legend says what.
- **G3 Think next to the evidence.** Write a note without leaving the map; link it to
  papers; see it in relation to them.
- **G4 Guidance that is checkable.** Every suggestion and warning comes from the
  library and says what it is based on. No AI runs inside the page.
- **G5 Nothing lost.** Notes and custom prompts are saved as files the researcher owns,
  that Claude Code can read later.
- **G6 Everything in the current page stays reachable** (the four views, filters, list,
  export, details), in the Explore tab.
- **G7 Out of the way.** Every tab area and card can be minimised to a labelled chip.
- **G8 Built for a large library.** A researcher with several areas can hold thousands to
  tens of thousands of items. The map stays readable and smooth there, by showing the right
  amount of detail for the zoom level, never by telling the researcher their library is too
  big. (Added 2026-10-30.)

## Non-goals

- Running an AI model from the page. (Claude reads the note files through Claude Code
  later; that integration is a separate project.)
- Per-subject maps in their own folders. Discussed 2026-10-24 (recommended: a home map
  plus one map per subject); not decided, and not part of this build. The zoom-based
  detail above is what lets one map hold a large library; per-subject maps would be an
  addition later, not a rescue.
- Collaboration, sharing or syncing notes between machines.
- Replacing the reports: notes feed thinking, not citations. A note is never cited.
- Mobile-first design. It must work at phone width (no sideways scroll; panels
  minimised) but the target is a laptop or desktop.

## Anti-goals (a failure even if it works)

- A globe that looks impressive but whose positions mean nothing.
- Satellites or arcs that move, glow or pulse without carrying information.
- A "smart" suggestion the researcher cannot check (no basis shown).
- A note silently lost (closed tab, failed save, cleared browser).
- The researcher's notes or annotations committed to git or loaded from the network.
- Losing anything the current page can do.

## Page structure

Top: the title ("Library map") and five tabs, Orbit-style.

| Tab | Job |
|---|---|
| **Overview** (default) | "On your map" summary, the research globe, notes as satellites, the annotation toolbar |
| **How it connects** | The kinds of thing in the library, their counts and how they link |
| **Explore** | The current Advanced views, unchanged: Library (sub-area hubs, unassigned and stale hubs), Research groups, Timeline, Gaps, List (with filters and export), full details |
| **Ask** | A question box that turns plain questions into exact filters and graph steps |
| **Status** | When it was built, OpenAlex coverage, labels, notes saving, what to fix |

The current Simple/Advanced switch goes: Overview is the simple view, Explore holds the
advanced ones. Filters remain shared across tabs, and Overview names any filter set
elsewhere that it cannot show (the existing rule, `advancedOnlyFilters`).

The address bar keeps the tab, focus, filters and the selected note, so a bookmark
reopens the same picture (extends the existing hash state).

### Minimising

- **The tab area** has a minimise control. Minimised, it is one thin bar with the tab
  names; clicking a name restores it on that tab.
- **Every floating card** ("On your map", a selected item's card, the note editor, the
  notes list, the toolbar) has a minimise control. Minimised, it becomes a small chip in
  place that still says what it is and its key count, e.g. "▸ On your map · 325",
  "▸ Note: Gaze noise defences…", "▸ Notes · 6 · 1 with new evidence". One click
  restores it.
- One keyboard shortcut minimises or restores everything, leaving the globe alone.
- Minimised state is remembered per viewer (browser storage is fine for this:
  it is a convenience, not data).
- Minimising the editor never discards what has been typed.

## Overview tab

### "On your map" card

One big number (items shown), then: papers and web sources; each research interest with
its colour and count (click to hide or show it, as the Simple key does now); one line
for new items, research groups, gaps and notes ("✦ 6 notes · 1 with new evidence");
any hidden filter set elsewhere, named, with "Clear"; a link "See how your library
connects →" to the second tab.

### The research globe

Positions carry meaning:

| Encoding | Meaning |
|---|---|
| Region (longitude band) | Research interest. Each interest gets a band whose width is proportional to its item count |
| Height (latitude) | Publication year: newest at the top, oldest towards the bottom; **undated items at the south pole** |
| Dot / small square | Paper / web source (not peer-reviewed) |
| Colour | Research interest (see "Many interests" for the cap) |
| Arc over the surface | One library paper citing another (OpenAlex references, library only). Drawn from the citing paper to the cited one; see "Reading the citation lines" |
| White ring | New since the last search |
| Faint meridians | Region boundaries |
| Year marks on the rim | The latitude scale |

Within a band, position along it is spread deterministically (a stable hash of the
item), so the picture is the same on every build for the same data. Each interest's name
is drawn over its region where its papers are. Drag to spin, scroll to zoom; the
existing toolbar functions (zoom in/out, fit, rotate/move) and double-click zoom carry
over.

Click a dot: its citation arcs light up (see "Reading the citation lines" below), everything else dims, and a card opens with the
title, interest, year, status, cites/cited-by counts, and **next steps**, each one click
that highlights the answer on the globe: "Show what it cites", "Show what cites it",
"Show its research group's other papers", "Show the same sub-area", "Write a note about this"
(opens the editor with this item already linked), "Open full details" (Explore tab,
details panel). Click empty space or Esc to leave.

### Reading the citation lines

A line on the globe always means one thing: **this paper cites that paper**. Nothing on the
page may leave that to be guessed.

- **Two colours, one meaning each.** Lines from the selected paper to papers it *cites*
  are one colour (amber); lines from papers that *cite it* to the selected paper are
  another (blue). The colours are chosen to be distinguishable for colour-blind viewers and
  never reuse an interest colour. A small arrowhead at the cited end shows the direction
  without relying on colour.
- **A label next to the card says so in words**, on every selection: "Amber lines: papers
  this one cites (6). Blue lines: papers that cite it (0)." The counts match the card's
  "Cites 6 · cited by 0", and a zero count says "none in your library".
- **The legend names the lines** whenever any are drawn, including the faint "strongest
  arcs" shown with nothing selected: "Lines are citations between papers in your library".
  Those faint lines carry no direction colour; selecting a paper turns its own lines into
  amber and blue.
- **Hovering a line** shows "<citing title> cites <cited title>".
- **What a missing line means** is written in the card: "A line only appears when both
  papers are in your library. This paper may cite others you have not collected."
- **Lines to hidden items** are not drawn, and the label says how many were left out by the
  current filters ("2 more are hidden by the shortlist").

### Scale: thousands to tens of thousands of items

The globe is a fixed size. Adding items or interests makes it denser, never bigger, so the
detail shown depends on how far the researcher has zoomed. The design target is a library
of **20,000 items and 50,000 citation links**, smooth to rotate and zoom. (The live library
today has 325 items and 683 links; a PhD student working across several areas for a few
years could reach 5,000 to 20,000, because the framework stores every source it finds, not
only what was read.)

Four rules:

1. **Zoomed out shows regions, not papers.** Each interest is a region sized by its count;
   its sub-areas are labelled clusters. Every region and cluster shows its exact count, so
   aggregating never hides what is there.
2. **Zoom in and clusters open into dots.** Dots are drawn only for what is in view, the
   highest-scoring first, and more appear as the researcher zooms. A cap on dots drawn at
   once keeps the frame rate smooth; when the cap hides some, the cluster says "showing 400
   of 2,300; zoom in or filter to see more".
3. **Citation arcs are drawn for the selection.** Clicking a dot shows its own arcs. With
   nothing selected, only the strongest arcs are drawn, up to a small cap, and none when
   zoomed far out.
4. **Show only the shortlist by default.** The globe opens on papers scored Core or
   Supporting, plus items not yet scored, so new finds are never hidden. A visible toggle
   ("Include peripheral and excluded: 14,200 more") brings in the rest. The count of what
   is hidden is always on screen. *(Designer's call, confirmed in discussion 2026-10-30.)*

Smaller rules that keep it readable:
- Every interest keeps at least a readable minimum band width, however small its count;
  its label shows on zoom.
- The year scale uses the library's real range and does not leave empty bands; if the
  range is wide, the most recent years get no less than a set share of the height.
- The Explore tab's List is virtualised (only visible rows are drawn); the other
  Explore views apply the same caps and say so when they do.
- Colouring rule from "Many interests" below still applies.

Performance is tested at the target size with a synthetic library (20,000 items, 50,000
links) as well as the live one. The test records time to first draw and frame rate while
rotating, and fails the build's check if either regresses past a stated limit. The
builder sets the limits after measuring in a real browser. Render technology is the
builder's choice within the constraints.

### Many interests

Colour must never repeat across interests. At most **six** interests are coloured at
once: by default the six largest; the researcher can choose which in the "On your map"
card. The rest are drawn in neutral grey and keep their region name label. The card's
list gets a search box when there are more than eight interests. *(Designer's call,
2026-10-24 discussion; the current page cycles colours after eight, which this fixes.)*

## Notes: satellites in orbit

### What a note is

A note needs no minimum or maximum number of links: zero (a free idea), one (a note about a
single paper), or many. The first link can be added later or removed.

A title, a body (free text), a list of linked library items (papers or web sources, by
their state key), whether it has been written into a report (and which), and created,
updated and archived dates. A note can also link to a research group or a sub-area. A
note is never cited in a report.

Each link is typed: `paper:<state key>`, `web:<state key>`, `group:<lab id>` or
`subarea:<interest>/<sub-area>`. A note also keeps `dismissed`, the state keys of
new-evidence suggestions the researcher dismissed. Dismissing does not change `updated`,
so it never resets which papers count as new.

### Where notes live

Saved as files in the project, one note per file:
`notes/<slug>.md`, Markdown with a small front-matter block (id, title, links,
in_report, dismissed, created, updated, archived) and the body as written. The folder is
gitignored (personal data, same rule as `research/`, `reports/` and `blog/`).
Custom guide prompts live in `notes/guide.json`. Annotations live in
`notes/annotations.json`.

A page opened from disk cannot write files, so saving needs a small helper that runs
only on the researcher's computer while the map is open, e.g.
`python3 tools/knowledge_graph.py --serve`. It serves the page on 127.0.0.1 and accepts
note, prompt and annotation writes into `notes/` only. Requirements:
- binds to 127.0.0.1 only; a random token in the URL that every write must carry;
- writes only inside `notes/`, through a fixed set of operations (save note, archive
  note, save prompts, save annotations); file names derived from the id, never from the
  request path; size limits;
- writes atomically (the `state.py` pattern); stdlib only.

**Starting and stopping the helper.** `/graph` builds the map, starts the helper in
the background and opens the served address (`http://127.0.0.1:<port>/?t=<token>`),
so the researcher never handles the token. The helper rebuilds `graph/index.html` when it
starts and prints the address. It records its port, token and process in
`graph/.serve.json` (gitignored with the rest of `graph/`); a second start finds a live
helper there and prints its address instead of starting another. The open page sends a
heartbeat every minute; the helper stops itself after 30 minutes with no heartbeat and no
request. The rebuild step in `/research`, `/rank`, `/synthesize`, `/update` and
`/websearch` only rebuilds; the helper serves the current file on every request, and an
open page that sees a newer build says "The library was rebuilt" with a Reload button.

**PDF links.** The helper also serves, read-only and only with the token, the two kinds
of file the page already links to: `research/fulltext/*.pdf` and
`reports/<slug>/report.pdf`. Each request path is resolved and must land inside those
folders with a `.pdf` name; nothing else is served and no folder is listed. This keeps
the current "open the PDF" links working on the same computer the files already live on.

**Edits made outside the page.** Note files may be edited by hand or by Claude. Every
save sends the version (content hash) the page loaded; if the file changed on disk since,
the helper refuses the save and the page shows both versions side by side with the typed
text kept, and the researcher chooses. The front-matter parser is a small stdlib one
for the subset the helper writes (scalars and flow lists); keys it does not know are
kept as they are, and a file it cannot parse is listed in Status as "could not read",
never overwritten.

When the page is opened from disk without the helper, notes from the last build are
shown read-only, the editor says so in plain words and shows the one command that turns
saving on, and an Export button downloads the unsaved note as Markdown. Nothing typed is
ever discarded without warning.

### Orbit meaning

| Orbit | Meaning |
|---|---|
| **Outer** | An idea: no papers linked yet |
| **Middle** | Backed by papers: one or more academic papers linked |
| **Inner** | Written into a report: the researcher marked it as used in a named report |

Distance from the globe is distance from evidence. A note moves inward as it gains
links, and the change is animated once so the researcher sees it happen. A thin line
(tether) runs from the satellite to each paper it links; the selected note's tethers and
papers are highlighted. An outer-orbit satellite is drawn hollow. Colour: the interest of
its first linked item, else neutral. The orbits are drawn as faint labelled shells
("an idea, no papers yet", "backed by papers", "in a report").

**Motion:** satellites stay still. Position along an orbit carries no meaning, so no
drift. Hovering a satellite shows its title; moving the globe moves the satellites with
it. The only animations are the inward move when a note gains evidence and the
new-evidence pulse.

**New evidence pulse:** after a rebuild, a note pulses when a paper first seen since the
note was last updated looks related. A paper counts as related when it shares a sub-area
with any linked paper, or when the note's text matches it strongly (the matching rule
below, score at or above the suggestion threshold). The note shows which paper and why
("shares the sub-area Eye-tracking privacy"), with "Link it" and "Dismiss". Computed by
`knowledge_graph.py` at build time, so it is exact and repeatable.

**How many:** no limit on saved notes. The globe shows at most about 30 satellites at
once: the selected note, notes with new evidence, notes linked to the current filters,
then the most recently updated. Each orbit says how many more it holds ("+12 more in the
outer orbit"), which opens the notes list filtered to them. Archived notes are never on
the globe.

Links to web sources, research groups or sub-areas draw tethers but do not move a note
to the middle orbit: only a paper does, so a blog post never looks like peer-reviewed
backing. Such a note says so in its card ("linked to 2 web sources, no papers yet").

### When the library changes

- A link whose target no longer exists after a rebuild (a removed source, a changed key,
  a renamed sub-area or regrouped lab) is kept in the file and shown in the note as
  "missing: <what it was>", with an option to remove it. Missing links do not count
  toward the orbit, so the note may move outward; the Status tab counts notes with
  missing links.
- `/reset` gains a `notes` scope that clears `notes/`, listing the number of notes
  first. `all` includes it, but notes are the researcher's own writing and cannot be
  rebuilt, so `all` asks a separate confirmation for them naming the count.

### Notes list

A card listing every note: title, orbit, linked count, updated date, new-evidence mark;
search, sort, filter by orbit or interest; open, archive, restore. It is the precise
counterpart to the satellites.

### The editor and the guide

Opens beside the globe when a satellite is clicked or "＋ Note" is pressed. It shows the
orbit in words ("Middle orbit · backed by 2 papers"), the title and body, and the guide:

- **Prompts**: five presets (Claim, Evidence, Against, Gap, Next step) plus the
  researcher's own, as chips. Click adds `Name:` to the body; a chip shows ✓ once the
  body has a line starting with it; hover shows its guiding question. "＋ Custom" adds a
  prompt (a name up to 24 characters and an optional guiding question); custom prompts
  can be removed, presets cannot; duplicates are refused with a message. One list for
  every note.
- **Checks**, each with its basis shown:
  - *Claim with no source*: the body reads like a factual claim (a figure, or words such
    as only, every, never, none, first, proves) and nothing is linked;
  - *One research group*: two or more linked papers, all from the same research group;
  - *Only web sources*: everything linked is a web source (not peer-reviewed);
  - *Nothing against yet*: two or more linked papers and no "Against:" line;
  - *New evidence*: as above, with Link it and Dismiss.
- **Suggested papers**: the library items the note seems to be about, ranked, each with
  "link". Matching uses the note's title and body against each item's title, sub-areas
  and, where available, its abstract; words are stemmed and weighted by rarity across
  the library, so a rare shared word counts more than a common one. Abstracts are not in
  state today; the builder may cache them (OpenAlex returns them during `--enrich`).
- **Linked papers**: each with "remove".

## Annotation toolbar

On the Overview tab, at the bottom, movable like the current navigation toolbar. It can be
minimised to a chip like every other panel. One tool is active at a time, the active tool is
highlighted, and Esc returns to Select, so it is always clear whether a drag draws or rotates
the globe.

### Tools

| Tool | Behaviour |
|---|---|
| **Select** | Click a mark to move, resize, recolour or delete it. Drag across dots to select a group of papers. |
| **Pen** | Freehand, three line widths. |
| **Shapes** | Rectangle, ellipse, arrow (from a dropdown). An arrow snaps to the dot it points at. |
| **Text label** | A short label placed on the view. Anything longer belongs in a note. |
| **＋ Note** | Opens the editor; if a mark or dot is selected the note starts linked to it. |
| **Undo / redo** | Ctrl/Cmd+Z and Ctrl/Cmd+Shift+Z, plus buttons. |
| **Colour** | Five fixed colours, chosen to differ from the interest colours so a mark is never mistaken for data. |
| **Eraser / clear** | Remove one mark, or every mark in the current view (asks first). |
| **Save as image** | Downloads the view with its marks as a PNG, for slides or a viva. |
| **Close** | Collapses the toolbar to a chip. |

Not in this version: highlighter (a pen style), sticky pins on dots (overlaps notes) and
compare-two-dots (belongs in Ask).

### Saved views, saved automatically

Annotations belong to a **saved view**: the globe's orientation and zoom plus the active
filters. There is no Save button and no naming step. The first mark in a view captures it,
named by default "<filter summary> · <date>" (for example "XR security · 30 Oct"), and it
can be renamed later. Marks are drawn over that view and hidden when the globe moves, with
a chip "Annotated view · Back to it" that returns to exactly that view. A view can carry
many marks; views are listed with the notes and can be renamed or deleted.

Any mark can be turned into a note: "Make a note from this" sits beside a selected mark, not
in a menu, and pre-fills the note's links with the papers inside the mark. Saved in
`notes/annotations.json` through the helper, writes atomic, same token and `notes/`-only
rules as notes.

Without the helper, marks work for the session, the toolbar says plainly that they will not
be kept, and Save as image is offered. Nothing is lost silently.

*(Designer's calls: anchoring marks to a rotating sphere would make them drift off what they
marked, so they belong to a view; saving is automatic so the researcher never has to think
about it.)*

## How it connects tab

A small diagram of the kinds of thing and how they link, each with its exact count:
research interests, sub-areas, papers, web sources, research groups, reports, gaps,
notes, and the citation link among papers. Clicking a kind shows its count, what it
connects to, and "Show all N on the map". Drawn from the built data, so the counts match
everything else on the page.

## Ask tab

A question box and example questions. A question is turned into the same filters and
graph steps a person could do by hand, so the answer is exact and repeatable; the result
is highlighted on the globe with a count and a list that exports. The supported
questions are a fixed set of patterns over things the data holds (interest, sub-area,
contribution, year range, status, research group, citations, new, gaps, notes), for
example:
- "attack papers in XR since 2024 with no defence"
- "papers from the same lab as Heimdall"
- "what cites the Unique Identification paper?"
- "thin sub-areas" / "new since my last search" / "scored but never used in a report"

A question the patterns do not cover says so plainly and offers the closest example and
the Explore filters. No AI model is called. *(Designer's call.)*

## Status tab

Last built; items shown and hidden; OpenAlex coverage (found, not found, no id, title
mismatches rejected); labels present and missing; citation links; notes (count, saving
on or off, the helper command); when it next refreshes. Each problem has its fix next to
it.

## Constraints

- Stdlib Python; the page stays one offline file with inlined vendored libraries; the
  only network use is the local helper on 127.0.0.1.
- `graph/index.html` and `notes/` are gitignored; `tools/security_guards.py` must
  require both rules.
- The helper runs through `python3 tools/knowledge_graph.py --serve`, which the
  existing `Bash(python3 tools/knowledge_graph.py:*)` allowlist entry already covers; no
  allowlist change.
- `.claude/commands/reset.md` gains the `notes` scope; `.claude/commands/graph.md`
  starts the helper.
- The tests that pin the Simple/Advanced switch are rewritten for the tabs; every other
  existing test keeps passing.
- No regressions: the existing tests keep passing (apart from the Simple/Advanced ones
  noted below); the current Advanced features move
  to Explore intact.
- Escaping as now: every `<` in embedded data written as `\u003c`; every string from the
  data or a note inserted as text, never HTML.
- Works in light and dark; Orbit's look is dark, so dark is the reference and light must
  still meet contrast.
- Profile-agnostic: nothing specific to this researcher's interests in code.

## Left to the builder

- Rendering technology for the globe (three.js, already vendored, or 2D canvas as in the
  mockup) and how the Explore views are embedded.
- Exact visual values (sizes, opacities, glow), the shells' spacing, the chip designs.
- The question patterns' grammar, provided the listed examples work.
- Whether to cache abstracts for matching, and the suggestion threshold.
- How the 20,000-item data reaches the page without making the file unmanageable (for
  example: titles, years, scores and keys embedded, abstracts and full details loaded only
  on demand from the helper, or aggregated counts precomputed at build). The one offline
  file must still open without the helper.
- How the build passes saved notes into the page (embedded at build time, read from the
  helper at runtime, or both).
- Test strategy, following the repo's: unittest for Python, node checks for page logic,
  real-browser checks for interaction.

## Designer's calls (for the researcher to check)

1. Notes saved as files through a local helper; read-only plus export without it.
2. Satellites still; only the inward move and the new-evidence pulse animate.
3. "Written into a report" is marked by the researcher, not inferred.
4. New-evidence rule: shares a sub-area with a linked paper, or strong text match.
5. At most about 30 satellites on the globe; the rest counted per orbit.
6. Annotations belong to a saved view rather than to the sphere, and are saved automatically
   with a default name.
7. Ask is pattern-based and exact; no AI model.
8. At most six interests coloured at once; the rest grey with labels.
9. The Simple/Advanced switch is replaced by the Overview and Explore tabs.
10. `/graph` starts the helper and opens its address; it stops after 30 idle minutes.
11. The helper serves the fulltext and report PDFs read-only behind the token, so those
    links keep working.
12. The Library view stays, as a view in Explore.
13. Note files may be edited outside the page; a save over a changed file is refused and
    both versions are shown.
14. Missing links are kept and shown, not counted; `/reset` gets a `notes` scope, and
    `all` asks separately before clearing notes.
15. Only a linked academic paper moves a note to the middle orbit; web, group and
    sub-area links do not.
16. The annotation toolbar's first version is the table above; highlighter, sticky pins and
    compare-two-dots are left out. Marks use five fixed colours distinct from interest colours.
    Save as image is included.
17. The globe is built for 20,000 items: regions when zoomed out, dots as the researcher zooms,
    arcs for the selection, shortlist (Core, Supporting and unscored) shown by default with
    a visible toggle for the rest. Tested at 20,000 items and 50,000 links.
18. Citation lines are directional: amber for what the selected paper cites, blue for what cites
    it, arrowheads at the cited end, always with a plain-words label and counts beside the
    card.
