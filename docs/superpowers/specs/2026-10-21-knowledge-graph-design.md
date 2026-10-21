# Library Knowledge Graph - Design

Date: 2026-10-21. Status: draft for the researcher's approval.

## Intent

After every search, a researcher wants to see how their literature is structured, not
just a list of new hits. In the researcher's words, the graph must show:

- **which papers come from the same research groups**
- **how subjects connect**
- **the progression of the work, from old papers to new**
- **gaps**

plus "any relevant functionality", with real attention to **user experience,
information access and navigation**. It is an **interactive 3D HTML page**.

The framework is a tool for researchers in general; the researcher's own library is
the test data. The graph must work for any profile, not just this one.

### Why this matters here

Every one of the four needs came up by hand during the XR state-of-the-art synthesis
(2026-10-13):

- Deciding whether a result was "corroborated" meant working out by hand which papers
  shared authors. Two reviewers disagreed on group counts until author lists were
  compared.
- The report's "Open Questions" were written by the drafter. Nothing in the framework
  showed which sub-areas of the researcher's profile had little or no coverage.
- A first mockup on real data showed the obvious approach fails. Linking any two
  papers that share an author chains 27 of the 107 papers into one blob, which is a
  collaboration network, not a lab. **Classification quality is the core of this
  feature, not the 3D rendering.**

## First principle: information and data clarity

**The researcher's top priority for the design is information and data clarity.** It
outranks visual impact, density of features, and the 3D effect itself: when a choice
trades clarity for anything else, clarity wins. In practice:

- **Every encoding is explained where it is seen.** An always-visible legend states
  what colour, shape, size, ring, outline and line style mean in the current view. No
  meaning lives only in documentation.
- **Plain words, not internal states.** The page never shows `ranked`, `synthesized`
  or `unfetchable`. It says "Scored, not yet used in a report", "Used in: <report>"
  and "Abstract could not be retrieved". The same applies to tiers, disclosure labels
  and evidence basis, each with a one-line explanation on hover.
- **Every number is traceable.** Counts on screen (papers in a sub-area, lab sizes,
  "14 new") are exact. They update with filters, and clicking one lists the items
  behind it. Nothing is rounded or estimated without saying so.
- **Derived information shows its derivation.** Labs show the authors and
  institutions that define them. Computed gaps show their rule and threshold.
  Sub-area labels say they were assigned from the abstract. Name-matched authorship
  says "matched by name". Uncertain or weaker data is marked as such and never
  presented like confirmed data.
- **No decoration without information.** No glow, particles, auto-rotation or motion
  that carries no meaning. Animation is used only to show a change the researcher
  caused (for example focusing a node).
- **Uncluttered by default.** The first view shows hubs and labels, and only the edges
  that matter for that view. Dense detail (all collaboration lines, all paper titles)
  appears on focus or by switching it on.
- **A precise view is always one click away.** Alongside the 3D graph, a sortable list
  view shows exactly what the graph shows under the current filters: title, authors,
  year, sub-areas, lab, status and tier. It is the accessible and exact counterpart to
  the spatial view, and the export uses it. The 2D toggle serves the same purpose for
  layout.
- **Consistent vocabulary.** Terms match the reports and the rubric (Core, Supporting,
  "read in full", "abstract only"), so the graph and the reports never describe the
  same thing differently.

Every section below is subject to this principle. The builder's choices left open at
the end (layout, palette, vendoring) are judged against it first.

## Decided by the researcher

1. **Scope: the whole library, with each search's new papers highlighted.** It is one
   graph, not one per search.
2. **Web sources are included, as a visibly different node type.** This relaxes the
   framework's "two tracks, kept separate" rule *for display only*. The two tracks
   stay separate in state, in scoring and in reports.
3. **Interactive 3D HTML.**
4. **Improve the classification, user experience, information access and
   navigation** over the first mockup.

## Goals

- **One page for the whole library.** It covers every research interest and every
  academic source in `research/seen_sources.json` (358 today), plus every web source
  in `blog/seen_web_sources.json` (27 today).
- **New papers stand out.** Papers first seen in the most recent search are
  highlighted. The researcher can widen "new" to the last N days or to a chosen
  search date.
- **Research groups mean labs, not chains.** Same-lab ties are kept apart from
  collaboration ties, and groups are found by community detection on weighted
  co-authorship (see Classification).
- **Subjects** are the sub-areas the profile already lists for each interest, and a
  paper may belong to several. Papers that span research interests are shown as
  bridges between them.
- **Progression** is shown two ways: a time axis, and citation arrows between papers
  in the library (who builds on whom).
- **Gaps** come in two kinds: the Open Questions of each compiled report, and
  structural gaps the graph computes itself (see Gaps).
- **Usable for real work.** Search, filter, focus, follow links out to the source and
  the report section, and export a selection as a reading list.
- **Kept current automatically.** The graph is rebuilt at the end of `/research`,
  `/rank`, `/synthesize`, `/update` and `/websearch`, and on demand with a new
  `/graph` command.

## Non-goals

- **Not a citation manager or a reader.** It links out to papers and does not show
  their content.
- **No editing state from the page.** The page is read-only, and state changes still
  go through `tools/state.py`.
- **No server.** The page opens from `file://`.
- **No network citation analysis beyond the library.** Citation arrows connect only
  papers the researcher already has; references to papers outside the library are
  counted per paper but not drawn.

## Anti-goals (would make it a failure even if it worked)

- **Blurring evidence types.** A web source must never be mistaken for a paper, and
  a scored-but-unread paper must never look the same as one that was read in full.
  Node shape and badge carry this, not colour alone.
- **Presenting computed "gaps" or "groups" as facts.** The page says how each was
  derived. Each group shows the shared authors and institutions behind it, and each
  computed gap shows its rule (for example "fewer than 3 papers since 2024").
- **Leaking the library.** No network calls at runtime: no CDN, no external fonts.
  This is the same rule as `blog/template.html`, since the page lists everything the
  researcher is reading. The output is gitignored.
- **Unreadable at real scale.** At 400+ nodes, a page that only looks impressive but
  cannot be read precisely fails the brief. Hence the 2D mode, focus mode and
  filters.

## Data model

(Node labels and badges below use the plain wording required by the first principle.)

**Node types**, each with a distinct shape:

| Type | Source | Shape |
|---|---|---|
| Paper | `seen_sources.json`, excluding `skipped` (off-topic at triage) by default; a filter shows them | sphere; size by overall score |
| Web source | `seen_web_sources.json`, `included` only by default | cube, labelled "not peer-reviewed" |
| Sub-area | profile sub-areas per interest | ring or label hub |
| Research interest | profile interests | large label hub |
| Report | `reports/*/` | flat card |
| Gap | report Open Questions, plus computed gaps | diamond |

**Paper visual encoding.** Colour follows the active view. Shape and badges stay
fixed:
- **Status:** `synthesized` papers are solid; `ranked` papers are hollow or outlined
  ("scored, not yet used"); `unfetchable` papers are faded.
- **Evidence:** a small marker shows a full-text read versus abstract only.
- **New:** a highlight ring marks papers in the current "new" window.

**Edge types**, each switchable on and off:
- **Same lab**, weighted (see Classification).
- **Collaboration:** a shared co-author who is not the senior author. Drawn thin.
- **Cites:** a directed arrow from the citing paper to the cited one, within the
  library only.
- **Belongs to sub-area** and **belongs to interest.**
- **Cited in report:** from a report node to each source it cites.
- **Gap concerns sub-area** and **gap raised in report.**
- **Web source to sub-area.** Web sources never receive co-authorship or citation
  edges to papers. These edges come from a new optional `subareas` field on web
  entries (see Decisions after review), not from guessing at the free-text topic.

## Classification

### Research groups (labs)

Use OpenAlex authorship data, which is disambiguated: `author.id`, the
`institutions[]` of each authorship, and author position (the last author is
treated as senior). Name strings are not used, since "Wang" and "Li" alone would
merge unrelated people.

**Weight each pair of papers:**
- **Same senior author:** strong (the default lab signal).
- **Senior author of one is a non-senior author of the other:** medium. This catches
  students and postdocs moving between papers of the same lab.
- **Shared institution and a shared author:** medium.
- **Any other shared co-author:** weak. It is drawn as a collaboration edge, not a
  lab edge.

**Find labs.** Run community detection (Louvain, or an equivalent stdlib
implementation) on the strong and medium edges. Collaboration edges are drawn
between labs, not used to merge them.

**Name each lab** after its most frequent senior author and that author's most
frequent institution, for example "Saxena lab, Texas A&M / UAB". Clicking a lab
shows exactly which authors and institutions define it.

**A lab is a group of authors, and each paper has a primary lab** (decided after
review). Community detection runs on an author graph, weighted by co-authorship role
and shared institution as above, so each author belongs to one lab.
- **Primary lab:** a paper's primary lab is its senior (last) author's lab, and sets
  its colour.
- **Other labs:** the detail panel lists every lab among a paper's authors.
- **Bridges:** papers whose authors span two or more labs are drawn as bridges
  between them.

This answers the researcher's question ("which papers come from the same research
group?") through the primary lab without losing cross-lab collaborations. It also
gives the later fact-check integration a per-author answer.

**Papers without OpenAlex data** fall back to name matching on the last author only,
flagged "matched by name" in the panel.

**This classification also feeds the reports.** The fact-check's "independent
groups" counts can use the same lab assignments. That is a later integration, not
part of this build.

### Subjects (sub-areas)

**The taxonomy is the profile.** Each interest's "Sub-areas of interest" list in
`01-researcher-profile.md`, parsed the same way `state.py landmarks` parses
landmark lists. For example, XR has 11 sub-areas and AI Security has 6. Applied ML
lists its sub-areas in one comma-separated sentence, which the parser splits.

**Assignment** is a new state field, `subareas: [..]`, holding one or more sub-area
names from the source's own interest. Optional cross-interest entries are written as
`"<interest>: <sub-area>"`.
- **Where it is set:** whenever a source is scored, in `/rank`, `/synthesize` Step 1
  and `/update` Step 2. The scoring agent already reads the abstract, so the label
  costs nothing extra.
- **Grounding:** the label is grounded in the fetched abstract, like every other
  score. A source no listed sub-area fits gets `[]` and appears under "unassigned"
  for its interest.

**Contribution type** is a second new field, `contribution`, with one of: `attack`,
`defence`, `measurement`, `user-study`, `survey`, `tool`, `position`. It is needed
for the "attacks with no defence" gap and for filtering.

**Validation.**
- **`contribution`:** validated against its list. An invalid value is an error, like
  every other enum.
- **Sub-area names not in the current profile:** a `check --verbose` warning, not an
  error (decided after review). The profile's sub-area lists change through `/setup`
  and `/expand`, and a hard error would block every later write to an entry labelled
  under an older list. The graph shows such entries as "unassigned (label no longer
  in profile)", and `/graph` lists them so they can be relabelled.
- **Missing fields on scored entries:** a `check --verbose` gap, the same pattern as
  `evidence_basis`.

**One-time backfill** for the existing scored and synthesized entries (about 290),
using batched agents. The agents get abstracts re-fetched through the connectors,
exactly as the `/rank --all` backfill did. Entries whose abstract cannot be fetched
keep empty fields and are listed.

**Report sections.** Synthesized papers also record the report section that cites
them, read from the `.tex`, as display-only metadata in the detail panel.

### Progression

- **Time:** the year is available for every node. Timeline view places nodes along
  a year axis.
- **Lineage:** citation edges come from OpenAlex `referenced_works`, kept only where
  both papers are in the library.
- **Per-paper counts:** each paper also shows "cites N library papers" and "cited by
  N library papers".
- **Lineage view:** selecting a paper highlights its ancestor and descendant chain.

### Gaps

- **Report gaps:** each Open Questions bullet of each compiled report becomes a gap
  node. It is linked to its report, and to the sub-areas whose papers it cites
  (derived from its `\cite`s, not hand-mapped).
- **Computed gaps,** each with a stated rule and threshold that the panel displays:
  - **Thin sub-area:** a profile sub-area with fewer than 3 scored papers.
  - **Stale sub-area:** a profile sub-area with no paper from the last 2 years.
  - **No defence:** a sub-area with 3 or more `attack` papers and no `defence`
    papers.
  - **Unused:** Core or Supporting papers never cited by any report. This reuses
    `state.py unmerged`.
  - **Missing landmark:** profile landmark works that are still missing. This reuses
    `state.py landmarks --related`.
- **Thresholds** are constants in the build tool, with defaults as above, so they
  can be tuned.

## User experience

### Layout

The page has four regions:
- **Top bar:** view switcher, 2D/3D toggle, search, and "new since" control.
- **Left drawer:** filters and legend.
- **Centre:** the graph.
- **Right panel:** details and a breadcrumb trail.

The page must also work on a laptop screen (1280×800) without horizontal scrolling.

### Views

Each view is a preset of colour, layout forces and visible edges:

1. **Library (default).** Interest and sub-area hubs. Papers cluster around their
   sub-areas, coloured by interest. New papers are ringed and the camera fits them on
   load, so "where did this search land?" is answered on first sight.
2. **Research groups.** Coloured by lab. Lab edges are solid and collaboration edges
   faint. Labs are listed in the left drawer by size, and clicking one focuses it.
3. **Timeline.** One axis is the year, coloured by sub-area, with citation arrows
   shown.
4. **Gaps.** Gap nodes are prominent and linked to their sub-areas and reports.
   Thin, stale and no-defence sub-areas are highlighted.

### Navigation and information access

- **Search:** with autocomplete over titles, authors, labs and sub-areas. Picking a
  result focuses it.
- **Focus mode:** clicking a node keeps it and its neighbours at full strength and
  dims everything else.
  - **Exiting:** Esc, or clicking empty space.
  - **Trail:** the breadcrumb keeps the last 10 focused nodes. Back and forward work
    with the buttons and with the browser history (hash URLs), so a view and focus
    can be bookmarked or shared as a link to the local file.
- **Detail panel for a paper:**
  - **Identity:** title, authors with each author's lab, year and venue.
  - **Assessment:** scores and verdict, status, evidence basis, disclosure, and
    sub-areas and contribution type.
  - **Usage:** the reports that cite it, with the citing section, and its library
    citations in and out.
  - **Links:** to the source URL or DOI, and to the cached PDF in
    `research/fulltext/` when one exists.
  - **Neighbours:** "show labmates" and "show lineage" buttons.
- **Detail panel for other nodes:**
  - **Web source:** its credibility tier, independence label and caveat.
  - **Lab:** its members and the authors and institutions that define it.
  - **Gap:** the rule or report it came from.
- **Filters** in the left drawer: interest, sub-area, year range (slider), node type,
  status, tier (Core, Supporting, Peripheral), evidence basis, disclosure,
  contribution type, and "new only". Filtered-out nodes are hidden, and the counts
  update.
- **2D/3D toggle:** 2D uses the same layout flattened, so it is readable for precise
  inspection and screenshots.
- **Labels:** hub and lab labels are always shown, and paper titles appear on hover
  or in focus mode, which avoids label clutter at 400+ nodes.
- **Export:**
  - **Reading list:** the current selection or filtered set as a Markdown reading
    list (title, authors, year, link, status) and as CSV.
  - **Image:** a PNG of the current view.
- **Keyboard:** `/` searches, `Esc` clears focus, the arrow keys step through the
  trail, and `1`-`4` switch views.
- **Accessibility:** the palette is colour-blind safe, and every encoding also has a
  non-colour channel (shape, ring or badge). Controls are keyboard reachable with
  visible focus, and the page follows the system light or dark theme.
- **Performance:** smooth interaction at 1,000 nodes and 5,000 edges on a laptop.
  Layout positions are cached between view switches.

### First-load "what's new" summary

A dismissible card on load sums up the new papers, for example: "14 new papers since
2026-10-05: 9 in XR (5 in Motion/sensor side channels), 3 from labs already in your
library, 2 in thin sub-areas." This answers the researcher's first question before
any interaction.

## Architecture

- **`tools/knowledge_graph.py`:** stdlib-only, like every tool in `tools/`. It builds
  one self-contained page at `graph/index.html`.
  - **Reads:** state (`seen_sources.json`, `seen_web_sources.json`), the profile,
    `reports/*/report.tex`, and the OpenAlex cache.
  - **Writes:** the page only. It never writes state.
- **Rendering library:** `three` and `3d-force-graph` are vendored as files under
  `graph/vendor/` (tracked; licences checked), or inlined into the page. Either way
  there are no runtime network calls.
- **Template and test fixture:** a `graph/template.html` shell, tracked like
  `blog/template.html`, with the tool injecting data. The rendering logic lives in
  the template, not in Python strings.
- **OpenAlex enrichment:** `knowledge_graph.py --enrich` fetches the authorships,
  institutions and `referenced_works` of library papers it has not seen.
  - **Fetching:** through the existing `openalex-search` connector, not raw HTTP. If
    the connector lacks an authorships or references view, extending it is part of
    this work.
  - **Cache:** `research/graph_cache.json` (gitignored, since `research/*` already
    is), keyed by identifier. Paced and incremental, so later runs fetch only new
    papers.
- **Integration:**
  - **Automatic rebuild:** `/research`, `/rank`, `/synthesize`, `/update` and
    `/websearch` each end by running `python3 tools/knowledge_graph.py --enrich`.
  - **On demand:** a new `/graph` command runs it and reports where the page is,
    plus the "what's new" summary in chat.
- **Gitignore and guards:** `graph/*` is gitignored except the template, the vendored
  libraries and a README. `security_guards.py` gains the new ignore rule, and the
  tool goes on the permission allowlist (this needs the researcher's approval at
  implementation time, as before).
- **Linter:** `check_graph.py`, or a `--check` flag on the tool, covers:
  - the data block parses and every edge references an existing node;
  - no external resources are loaded;
  - every computed gap carries its rule;
  - the same embedded-JSON `<` escaping as `/websearch` pages, since titles are
    untrusted text.
- **Tests,** in the repo's existing style:
  - classification on fixtures: a known lab split, name-only fallback,
    multi-sub-area, and a cross-interest bridge;
  - gap rules at the threshold edges;
  - page build and lint;
  - a drift test that documented invocations use real flags.

## Constraints

- **Python:** stdlib only.
- **Single write path:** `state.py` is the only writer of state, so the new
  `subareas` and `contribution` fields are added there with validation and tests.
  The OpenAlex cache is derived data, not state, so the graph tool writes it
  atomically itself.
- **Grounding:** every classification label is grounded in fetched content, never
  in a title alone. This is the same verify-before-cite discipline as scoring.
- **Two tracks:** state, rubrics and reports stay separate. Only the display joins
  them.
- **Offline and private:** the page makes no network calls, and its output is
  gitignored.
- **Profile-agnostic:** the taxonomy, interests and thresholds come from the
  profile and constants. Nothing is specific to XR.

## Left to the builder

- **Clustering:** the community-detection algorithm and its resolution, as long as
  the 27-paper chain from the mockup splits into recognisable labs. The test data is
  the XR report's 107 papers.
- **Layout:** force strengths, the exact visual design, and the palette, within the
  accessibility rules above.
- **Vendoring:** whether the libraries are inlined into the page or kept as separate
  vendored files.
- **Ordering and the `/graph` command:**
  - **Ordering:** backfill, then build, then integrate.
  - **Command:** `/graph`'s exact wording.

## Decisions after review

A builder read this document and raised five questions. Each was settled as below.
These are the drafter's calls, not the researcher's, and are listed for the
researcher to check.

1. **Web sources get an optional `subareas` field, plus their interest.** `/websearch`
   sets it when it scores a source, since the agent already reads the page. It is
   backfilled once for the 19 included web sources, and `state.py` validates it as for
   papers. `check_webscan.py` is unaffected, because the page schema does not change.
   This is preferred to guessing attachment from the free-text `topic`, which would
   leave web nodes floating or wrongly placed.
2. **The researcher accepts the labs; no numeric threshold does.** No reference split
   exists, so the plan includes a checkpoint after classification.
   - **What the builder shows:** the proposed labs for the XR report's 107 papers, with
     each lab's defining authors and institutions.
   - **What the researcher does:** confirms or corrects them before the page and the
     command integrations are built.
   - **What happens to corrections:** they become regression fixtures.
3. **A lab is a group of authors, and each paper has a primary lab:** its senior
   author's. See Classification.
4. **The builder runs the backfill on the researcher's live state,** through
   `state.py`, the same way the `/rank --all` backfill was run. Before writing, it
   tells the researcher what will be written and gets a go-ahead at that step.
   Entries whose abstract cannot be fetched keep empty fields and are listed.
5. **Stale sub-area labels are a warning, not an error.** See Classification.

Smaller points, also settled:
- **Undated nodes** (17 papers and 8 web sources have no year) go in an "undated" lane
  in the Timeline view. They are left out of year filters and staleness rules, and are
  never given an inferred year.
- **"Most recent search"** means the latest `first_seen` date in either state file,
  since state records dates, not search IDs. The "new since" control can pick any
  earlier date.
- **Landmark groups are not the taxonomy.** Sub-areas come only from each interest's
  "Sub-areas of interest" list; landmark group headings are not used for
  classification.
- **`Uncategorized` sources** (16) appear under their own hub with an "unassigned"
  sub-area, so they stay visible and countable instead of hidden.
