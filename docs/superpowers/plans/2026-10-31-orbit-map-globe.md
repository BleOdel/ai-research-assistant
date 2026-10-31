# Library Map, Part 1: Tabs and the Research Globe - Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Simple/Advanced page with the Orbit-style tabbed map: an Overview tab with the "On your map" card and a research globe that stays readable and smooth at 20,000 items, the current Advanced views moved intact into an Explore tab, and the How it connects, Ask and Status tabs.

**Architecture:** `graph/template.html` keeps the shared state (`S`, `passes`, `select`, the Explore renderer) and gains a tab shell. New page code lives in focused files under `graph/parts/`, inlined by `tools/knowledge_graph.py` exactly as `graph/vendor/` is, so the built page is still one offline file. The globe is a 2D canvas with an orthographic projection (the throwaway prototype measured 1-3 ms per frame at 20,000 and 50,000 items); its maths are pure functions tested in node, its drawing is checked in a real browser.

**Tech Stack:** Python 3 stdlib (`unittest`), plain browser JavaScript (no new libraries), node for page-logic tests, the Browser pane for real-browser checks.

**Spec:** `docs/superpowers/specs/2026-10-30-library-map-orbit-design.md`

**Scope.** The design is three pieces of work that each ship on their own. This plan is **Part 1**. Part 2 (notes as satellites: the `--serve` helper, note files, the editor and guide, new-evidence, `/reset notes`) and Part 3 (the annotation toolbar, which saves through Part 2's helper) get their own plans after Part 1 ships. Part 1 leaves out everything about notes: no "Write a note about this" step, no notes line on the card, no notes kind in How it connects, no notes row in Status, no notes questions in Ask. Part 2 adds each of those.

## Global Constraints

- Stdlib Python; the page stays one offline file with inlined code; no network use (`knowledge_graph.check` must stay clean).
- Every string from the data goes into the DOM as text through `el()`, never `innerHTML`; every `<` in embedded data is written as `<`.
- Plain words on the page, never internal state names (`ranked`, `synthesized`, `unfetchable`).
- Works in light and dark; dark is the reference look; colours come from CSS tokens on `:root`.
- Profile-agnostic: no interest or sub-area name in code.
- Every browser-storage access goes through `store.get` / `store.set` (Task 3), which swallow errors: storage is a convenience, never data.
- Existing tests keep passing, except the Simple/Advanced tests, which Task 3 rewrites for the tabs.
- Commits end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Work in the worktree `orbit-map`, made from `~/.ai-research-assistant-build`; never commit from the working clone.

Decisions this plan makes where the spec leaves the builder a choice:

- **Globe technology:** 2D canvas, orthographic projection; no three.js on the Overview.
- **Data:** the existing data block, unchanged in shape; the page derives the globe's arrays at load. At 20,000 synthetic papers the page is about 26 MB and builds in about 5 s; Task 2 pins a 30 MB budget.
- **The shortlist is a shared filter** (`S.filters.all`, default `false`), applied in `passes()`, so the globe, the Explore views and the list never disagree. Explore's filter panel shows it.
- **The Papers / Web switch is the existing "Kind of source" facet** (`S.filters.sets.type`), so Explore already follows it.
- **Performance check:** CI has no browser, so CI pins the page-size budget (Task 2) and the cap logic (Task 5); time to first draw and frame rate are measured in a real browser in Task 10 against the limits written in `graph/README.md`: first draw within 2,000 ms of load, median frame at most 16 ms and 95th percentile at most 33 ms while rotating, both at 20,000 items.

## Review Focus

1. **An empty library** (straight after `/setup`): the Overview shows the empty globe and the card says "Nothing in your library yet. Run /research to start."; no `NaN`, no exception. Tests in Tasks 5 and 7.
2. **Every item undated, or every item from one year:** `yearLat` and the year marks never divide by zero. Test in Task 5.
3. **A bookmark from the old page** (`#ui=simple...` or `#ui=advanced...`, or a focus id this build lacks): opens on Overview or Explore respectively, without an error. Test in Task 3.
4. **Browser storage blocked** (private window, `localStorage` throws): the page still opens, minimise and colour choices simply are not remembered. Test in Task 3.
5. **Phone width** (under 600 px): cards start minimised to chips so the globe is visible, and nothing scrolls sideways. Test in Task 7 plus the Task 10 browser check.

---

## File Structure

| File | Responsibility |
|---|---|
| `tools/knowledge_graph.py` (modify) | Inline `graph/parts/*.js`; add `meta.coverage` and `meta.labels`; a richer synthetic library |
| `graph/template.html` (modify) | Tab shell, shared state and filters, Explore (today's Advanced UI); Simple mode removed |
| `graph/parts/globe.js` (create) | Globe maths (pure) and the canvas renderer with its input handling |
| `graph/parts/overview.js` (create) | The Overview tab: "On your map" card, selection card, ring key, hover label, legend, globe toolbar, minimise chips |
| `graph/parts/connects.js` (create) | The How it connects tab |
| `graph/parts/ask.js` (create) | The Ask tab: question patterns and results |
| `graph/parts/status.js` (create) | The Status tab |
| `tests/test_graph_template.py` (modify) | Harness reads the parts too; new page-logic tests |
| `tests/test_knowledge_graph.py` (modify) | Parts inlining, coverage, labels, synthetic, size budget |
| `graph/README.md`, `.claude/commands/graph.md` (modify) | The new page, in plain words; the performance limits |

---

### Task 1: Page parts, inlined like the vendored code

**Files:**
- Modify: `tools/knowledge_graph.py` (constants near `VENDOR_TAG`; `render()`)
- Create: `graph/parts/globe.js`, `graph/parts/overview.js`, `graph/parts/connects.js`, `graph/parts/ask.js`, `graph/parts/status.js` (each a one-line header comment for now)
- Modify: `graph/template.html` (five part tags after the main script)
- Test: `tests/test_knowledge_graph.py`, `tests/test_graph_template.py`

**Interfaces:**
- Produces: `PARTS = ROOT / "graph" / "parts"`, `PART_TAG = re.compile(r'<script data-part="([\w.-]+)"></script>')`; `render(data, template, vendor=None, parts=None)` where `parts` maps a name to code, as `vendor` does. Test helpers `PAGE_SOURCE` (template plus every part, in tag order) and `page_function(name)` searching `PAGE_SOURCE`.

- [ ] **Step 1: Write the failing tests**

In `tests/test_knowledge_graph.py`, class `RenderTests` (the class holding `test_render_has_one_slot`):

```python
def test_parts_are_inlined_in_order(self):
    tpl = '<script data-part="a.js"></script><script data-part="b.js"></script>[GRAPH_JSON]'
    html = knowledge_graph.render({}, tpl, parts={"a.js": "var A=1;", "b.js": "var B='</script>';"})
    self.assertNotIn("data-part", html)
    self.assertLess(html.index("var A=1;"), html.index("var B="))
    self.assertIn("<\\/script>", html)

def test_missing_part_is_an_error(self):
    with self.assertRaisesRegex(ValueError, "nope.js"):
        knowledge_graph.render({}, '<script data-part="nope.js"></script>[GRAPH_JSON]', parts={})
```

In `tests/test_graph_template.py`: replace `page_function`'s search target with `PAGE_SOURCE`, built from `TEMPLATE` plus each `graph/parts/<name>` named by a `data-part` tag, in tag order. Add:

```python
def test_every_part_parses(self):
    for name in re.findall(r'data-part="([\w.-]+)"', TEMPLATE):
        code = (REPO_ROOT / "graph" / "parts" / name).read_text()
        r = subprocess.run(["node", "--check", "-"], input=code, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, f"{name}: {r.stderr}")
```

and extend `test_data_strings_never_reach_innerhtml` to assert the `innerHTML` rule over `PAGE_SOURCE`, not only `TEMPLATE`.

- [ ] **Step 2: Run them to see them fail**

Run: `python3 -m unittest tests.test_knowledge_graph tests.test_graph_template -v`
Expected: FAIL (`render()` has no `parts` argument; the part files do not exist).

- [ ] **Step 3: Implement**

In `render()`, after the vendor substitution, substitute `PART_TAG` the same way: code from `parts[name]` if given, else `PARTS / name`, else `ValueError` naming the file; the same `</script` and `<!--` escaping. Add the five part files and, in `template.html`, the five tags right after the main `<script>` element, in the order globe, overview, connects, ask, status. Parts share the page's global scope: top-level `function` declarations only, each closing `}` at column 0 (the harness's `page_function` relies on it).

- [ ] **Step 4: Run the tests**

Run: `python3 -m unittest discover -s tests`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add tools/knowledge_graph.py graph/parts graph/template.html tests
git commit -m "graph: page code in graph/parts/, inlined like the vendored code"
```

---

### Task 2: Build data for Status and a synthetic library at scale

**Files:**
- Modify: `tools/knowledge_graph.py` (`synthetic_library`, `build`)
- Test: `tests/test_knowledge_graph.py`

**Interfaces:**
- Produces: `data["meta"]["coverage"] = {"found", "notFound", "mismatch", "noId", "notFetched"}` (ints, over every paper in state that is not `skipped`), and `data["meta"]["labels"] = {"notLabelled", "fitsNone", "stale", "noContribution"}` (ints, over the same papers). Web nodes are unchanged: the page reads a web item's grade from `tier`.

- [ ] **Step 1: Write the failing tests** (class `BuildTests`, using the fixture data)

```python
def test_openalex_coverage_counts(self):
    self.write("research/graph_cache.json", {"works": dict(CACHE["works"], **{
        "10.1000/d": {"openalex": None, "error": "not found", "fetched": "2026-10-21"},
        "10.1000/f": {"openalex": None, "error": "title mismatch: OpenAlex returned 'X'",
                      "fetched": "2026-10-21"}})})
    cov = self.build()["meta"]["coverage"]
    # a, b found; d not found; f rejected; e has a DOI but was never fetched
    self.assertEqual(cov, {"found": 2, "notFound": 1, "mismatch": 1, "noId": 0, "notFetched": 1})

def test_label_counts(self):
    labels = self.build()["meta"]["labels"]
    # d never labelled; f labelled with no fit; b's "Retired Area" is no longer listed
    self.assertEqual(labels["notLabelled"], 2)   # d and e
    self.assertEqual(labels["fitsNone"], 1)
    self.assertEqual(labels["stale"], 1)
```

In the existing `test_synthetic_library_builds`, keep the paper count of 60 and add:

```python
    web = [n for n in data["nodes"] if n["type"] == "web"]
    self.assertEqual(len(web), 6)
    self.assertEqual(len(data["interests"]), 12)
    verdicts = {n.get("verdict") for n in data["nodes"] if n["type"] == "paper"}
    self.assertTrue({"Peripheral", "Excluded", None} <= verdicts)
```

and a new size-budget test:

```python
def test_twenty_thousand_items_fit_the_page_budget(self):
    self.build("--synthetic", "20000")
    self.assertLess(self.page.stat().st_size, 30 * 1024 * 1024)
```

- [ ] **Step 2: Run them to see them fail**

Run: `python3 -m unittest tests.test_knowledge_graph.BuildTests -v`
Expected: FAIL (`KeyError: 'coverage'`; 3 interests, no web sources).

- [ ] **Step 3: Implement**

Coverage: for each non-skipped paper key, `rec = cache works[key]`; no record and `kg_enrich.openalex_lookup_id(key, entry)` is `None` is `noId`, no record otherwise `notFetched`, `error` `None` is `found`, an error starting `"title mismatch"` is `mismatch`, any other error `notFound`. Labels: `subareas` `None` is `notLabelled`, `[]` is `fitsNone`, any label not in the interest's taxonomy is `stale`; `contribution` missing is `noContribution`.

Synthetic: 12 interests `"Interest A"` … `"Interest L"`, item counts weighted `1 / (k + 0.6) ** 1.1` (k = 0..11) so a few interests are large and most are small; six sub-areas each; verdicts drawn from Core, Supporting, Peripheral, Excluded and `None` (status `new`, no score) in the ratio 1 : 3 : 7 : 5 : 9; plus `n // 10` web sources in `web`, status `included`, tiers drawn from Core, Supporting, Peripheral, with `interest`, `subareas`, `first_seen` and `date`. The same seed gives the same library.

- [ ] **Step 4: Run the tests**

Run: `python3 -m unittest tests.test_knowledge_graph -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tools/knowledge_graph.py tests/test_knowledge_graph.py
git commit -m "graph: OpenAlex coverage and label counts; a 12-interest synthetic library with web sources"
```

---

### Task 3: The tab shell; Simple mode removed; Explore holds today's Advanced page

**Files:**
- Modify: `graph/template.html` (markup, CSS, `writeHash`, `readHash`, `restoreFromHash`, `onKey`, `viewGraph`, `setView`, `hoverLabel`, `refreshData`; delete `initialUi`, `setUi`, `renderSimpleKey`, `renderNodeCard`, `hideNodeCard`, `#simplekey`, `#nodecard`, `#ui-switch`, every `body.simple` rule)
- Test: `tests/test_graph_template.py`

**Interfaces:**
- Produces: `const TABS = ["overview", "connects", "explore", "ask", "status"]`; `TAB_NAMES = { overview: "Overview", connects: "How it connects", explore: "Explore", ask: "Ask", status: "Status" }`; `S.tab` (default `"overview"`); `initialTab(hashTab, hashUi, saved) -> string`; `setTab(tab, push)`; `TAB_HOOKS`, a `{tab: fn}` map that parts fill in (`TAB_HOOKS.overview = renderOverview`), each called after its tab is shown; `store.get(key) -> string|null`, `store.set(key, value)`; `S.min = { tabs: false, cards: {} }`; `toggleMinimiseAll()`; `exploreOnlyFilters(f) -> string[]` (renamed from `advancedOnlyFilters`).

- [ ] **Step 1: Rewrite the Simple tests as tab tests**

Delete `test_simple_mode_regions_present`, `test_simple_is_the_default_mode`, `test_no_tooltip_over_the_open_card` and `test_unticked_interest_hides_its_hubs` is kept unchanged. Rewrite `test_simple_names_filters_it_cannot_show` as `test_overview_names_filters_it_cannot_show` against `exploreOnlyFilters` with the same three cases, except that the third expects `["Status", "Publication year"]` (the card shows "only new" itself). Add:

```python
def test_tab_regions_present(self):
    for region in ("tabs", "tab-overview", "tab-connects", "app", "tab-ask", "tab-status",
                   "tabs-min"):
        self.assertRegex(TEMPLATE, rf'id="{region}"', region)
    for gone in ("simplekey", "nodecard", "ui-simple", "ui-advanced", "body.simple"):
        self.assertNotIn(gone, TEMPLATE, gone)

@unittest.skipUnless(shutil.which("node"), "node not installed")
def test_initial_tab(self):
    got = run_js(["initialTab"], 'const TABS = ["overview","connects","explore","ask","status"];',
                 '[initialTab(null, null, null), initialTab("ask", null, "explore"), '
                 'initialTab(null, "advanced", null), initialTab(null, "simple", "status"), '
                 'initialTab(null, null, "status"), initialTab("bogus", "bogus", "bogus")]')
    self.assertEqual(got, ["overview", "ask", "explore", "overview", "status", "overview"])

@unittest.skipUnless(shutil.which("node"), "node not installed")
def test_blocked_storage_is_not_an_error(self):
    prelude = ('const localStorage = {getItem() { throw new Error("blocked"); }, '
               'setItem() { throw new Error("blocked"); }};')
    got = run_js([], prelude + "\n" + re.search(r"^const store = \{.*?^\};$", PAGE_SOURCE,
                 re.S | re.M).group(0), '[store.get("x"), store.set("x", "1")]')
    self.assertEqual(got, [None, None])
```

- [ ] **Step 2: Run them to see them fail**

Run: `python3 -m unittest tests.test_graph_template -v`
Expected: FAIL (no `#tabs`, no `initialTab`, no `store`).

- [ ] **Step 3: Implement**

Markup: a top `<header id="tabs">` with the title "Library map", one `<button role="tab">` per tab, and a minimise button; `#tabs-min`, the thin bar shown instead when the tab area is minimised (the tab names as buttons; clicking one restores the bar on that tab). Under it, `<section id="tab-overview">`, the existing `#app` (Explore, unchanged inside apart from the removals), `<section id="tab-connects">`, `<section id="tab-ask">`, `<section id="tab-status">`; exactly one is shown. `#app`'s height becomes the viewport minus the tab bar.

`setTab(tab, push)`: shows that section, sets `aria-selected`, saves it with `store.set("kg-tab", tab)`, calls `G.pauseAnimation()` when leaving Explore and `G.resumeAnimation(); fitCanvas()` when entering it, runs `TAB_HOOKS[tab]` if set, and writes the hash. `initialTab`: the hash's `tab` if it is in `TABS`; else `ui=advanced` gives `"explore"` and `ui=simple` gives `"overview"`; else the saved tab; else `"overview"`. The hash gains `tab` and loses `ui`; `S.advView` becomes the Explore view and `S.ui` goes everywhere it was read (Explore always behaves as Advanced did).

`store`: `const store = { get(k) {…}, set(k, v) {…} };` (top-level `const`, closing `};` at column 0), both wrapped in `try/catch` returning `null`. Replace every existing `localStorage` call with it.

Minimise: `S.min.tabs` toggles `body.tabs-min`; `S.min.cards[id]` is set by Task 7's cards. Key `m` (when not typing) runs `toggleMinimiseAll()`: if anything is open, minimise the tab area and every card; else restore all. Both saved under `kg-min` as JSON.

- [ ] **Step 4: Run the tests**

Run: `python3 -m unittest discover -s tests`
Expected: all PASS.

- [ ] **Step 5: Check it in a browser**

Build the live page in the worktree (`python3 tools/knowledge_graph.py`), serve the worktree's `graph/` on 127.0.0.1 through `.claude/launch.json` in the worktree (delete the file afterwards), and check: the page opens on Overview (empty for now); Explore shows today's Advanced page with all four views, filters, list and export working; switching Explore → Overview → Explore leaves the force graph sized to its area; `#ui=simple` and `#ui=advanced` bookmarks open Overview and Explore; `m` minimises and restores the tab area. No console errors.

- [ ] **Step 6: Commit**

```bash
git add graph/template.html tests/test_graph_template.py
git commit -m "graph: five tabs; Explore holds the former Advanced page; Simple mode removed"
```

---

### Task 4: Shared rules: shortlist, six colours, Explore caps, a virtualised list

**Files:**
- Modify: `graph/template.html` (`S.filters`, `passes`, `renderFilters`, `interestColor`, `viewGraph`, `setView`, `renderList`)
- Test: `tests/test_graph_template.py`

**Interfaces:**
- Produces: `shortlisted(n) -> bool`; `S.filters.all` (bool, in the hash as `a`); `colourSlots(names, counts, chosen) -> Object<name, 1..6 | 0>`; `S.colours` (array of chosen names or `null` for "six largest"), saved under `kg-colours`; `interestColor(name)` reading the slots (`--s1`..`--s6`, else `--uncat`); `EXPLORE_CAP = 1500`; `capItems(ids, cap) -> {keep: Set, total: number}` (highest `score` first, `null` scores ranked as 50, ties by id); `visibleRange(scrollTop, viewH, rowH, total, overscan) -> [start, end]`.

- [ ] **Step 1: Write the failing tests**

```python
@unittest.skipUnless(shutil.which("node"), "node not installed")
def test_shortlist_rule(self):
    got = run_js(["shortlisted"], "", "[shortlisted({verdict: 'Core'}), shortlisted({verdict: 'Supporting'}), "
                 "shortlisted({verdict: null}), shortlisted({verdict: 'Peripheral'}), "
                 "shortlisted({verdict: 'Excluded'}), shortlisted({type: 'web', tier: 'Peripheral'}), "
                 "shortlisted({type: 'web', tier: 'Core'})]")
    self.assertEqual(got, [True, True, True, False, False, False, True])

@unittest.skipUnless(shutil.which("node"), "node not installed")
def test_at_most_six_interests_coloured(self):
    names = '["A","B","C","D","E","F","G","H"]'
    counts = '{A: 1, B: 9, C: 5, D: 7, E: 2, F: 8, G: 6, H: 3}'
    got = run_js(["colourSlots"], "", f"[colourSlots({names}, {counts}, null), "
                 f"colourSlots({names}, {counts}, ['A', 'H'])]")
    self.assertEqual(got[0], {"A": 0, "B": 1, "C": 5, "D": 3, "E": 0, "F": 2, "G": 4, "H": 6})
    self.assertEqual(got[1], {"A": 1, "B": 0, "C": 0, "D": 0, "E": 0, "F": 0, "G": 0, "H": 2})

@unittest.skipUnless(shutil.which("node"), "node not installed")
def test_explore_cap_keeps_the_highest_scored(self):
    prelude = ('const byId = new Map([["a",{score:90}],["b",{score:null}],["c",{score:20}],'
               '["d",{score:70}]]);')
    got = run_js(["capItems"], prelude, '(() => { const r = capItems(["a","b","c","d"], 2); '
                 'return [[...r.keep].sort(), r.total]; })()')
    self.assertEqual(got, [["a", "d"], 4])

@unittest.skipUnless(shutil.which("node"), "node not installed")
def test_virtual_list_range(self):
    got = run_js(["visibleRange"], "", "[visibleRange(0, 300, 30, 1000, 5), "
                 "visibleRange(3000, 300, 30, 1000, 5), visibleRange(29700, 300, 30, 1000, 5), "
                 "visibleRange(0, 300, 30, 4, 5)]")
    self.assertEqual(got, [[0, 15], [95, 115], [985, 1000], [0, 4]])
```

- [ ] **Step 2: Run them to see them fail**

Run: `python3 -m unittest tests.test_graph_template -v`
Expected: FAIL (functions not defined).

- [ ] **Step 3: Implement**

`shortlisted(n)`: the grade is `n.tier` for web, `n.verdict` for papers; false only for `Peripheral` and `Excluded`. `passes()` drops non-shortlisted items unless `S.filters.all`. `renderFilters()` shows the toggle at the top: "Include peripheral and excluded (N more)", N being what it would add under the other filters.

`colourSlots`: with `chosen` null, the six names with the largest counts, slots in descending count order (ties by name); with `chosen`, its first six names in order; everyone else 0. `interestColor` uses it with counts over all items, so a colour never changes when filters change, and never repeats.

`viewGraph()`: after building `keep`, apply `capItems` to its paper and web ids; when it trims, `#viewnote` starts with "Showing 1,500 of 9,330 items, highest scored first. Filter to see more." The Timeline and Gaps views apply the same cap.

`renderList()`: above 500 rows, the table body keeps a fixed 30 px row height and draws only `visibleRange(...)` rows (overscan 5) between two spacer rows, redrawn on scroll; sorting, export and highlighting still use every row.

- [ ] **Step 4: Run the tests**

Run: `python3 -m unittest discover -s tests`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add graph/template.html tests/test_graph_template.py
git commit -m "graph: shared shortlist filter, six colours at most, Explore caps, virtual list"
```

---

### Task 5: Globe maths

**Files:**
- Modify: `graph/parts/globe.js`
- Test: `tests/test_graph_template.py` (new class `GlobeMathTests`)

**Interfaces:**
- Produces, all top-level functions in `globe.js`:
  - `MIN_BAND_DEG = 8`, `DOT_CAP = 2500`, `ARC_CAP = 300`, `ZOOM_MIN = 1`, `ZOOM_MAX = 14`;
  - `hash01(s) -> number in [0, 1)` (FNV-1a over the string);
  - `yearLat(year, lo, hi) -> degrees`;
  - `bands(entries) -> [{name, start, width}]`, `entries` = `[[name, count], …]` in display order;
  - `clusterKey(item, subareasOfInterest) -> string` and `clusterName(key) -> string`;
  - `buildGlobe(items, interestOrder, subareasByInterest) -> Model` where `Model = {n, ids, vx, vy, vz (Float32Array), interest (Uint16Array, index into model.interests), cluster (Uint16Array, index into model.clusters), interests: [name], clusters: [{key, name, interest, members: [index]}], bands, lo, hi, order (Uint32Array, by score then id)}`;
  - `rotation(yaw, pitch) -> {cy, sy, cp, sp}`; `project(rot, x, y, z) -> [sx, sy, depth]` in unit-sphere coordinates (caller scales);
  - `pickDots(model, mask, rot, inView, cap) -> {drawn: number[], inView: number}`, where `inView(sx, sy)` says whether a unit-sphere point is on screen;
  - `clusterStats(model, mask, isNewFlags) -> [{count, fresh, x, y, z}]` (centroid normalised; `count` 0 when empty);
  - `zoomBlend(zoom) -> {regions, dots}`;
  - `flyTarget(x, y, z) -> {yaw, pitch}`;
  - `yearMarks(lo, hi) -> number[]`;
  - `arcPath(a, b, steps) -> [[x, y, z], …]` (great-circle, lifted by `1 + 0.16 * sin(pi * t) * angle`);
  - `placeLabels(cands, maxSmall) -> cands kept`, each candidate `{text, x, y, w, h, priority, big}`.

- [ ] **Step 1: Write the failing tests**

```python
@unittest.skipUnless(shutil.which("node"), "node not installed")
class GlobeMathTests(unittest.TestCase):
    def js(self, names, expr, prelude=""):
        return run_js(["hash01", "yearLat", "bands", "clusterKey", "clusterName", "buildGlobe",
                       "rotation", "project", "pickDots", "clusterStats", "zoomBlend",
                       "flyTarget", "yearMarks", "arcPath", "placeLabels"] + names,
                      "const MIN_BAND_DEG = 8, DOT_CAP = 2500;" + prelude, expr)

    def test_year_scale(self):
        got = self.js([], "[yearLat(2026, 2003, 2026), yearLat(2003, 2003, 2026), "
                      "yearLat(2017, 2003, 2026), yearLat(2020, 2020, 2020), yearLat(null, 2003, 2026), "
                      "yearLat(2024, 2020, 2026)]")
        self.assertEqual([round(v, 1) for v in got], [62.0, -62.0, -12.4, 0.0, -80.0, 20.7])

    def test_bands_have_a_minimum_and_fill_the_sphere(self):
        got = self.js([], "[bands([['A', 900], ['B', 1], ['C', 99]]), bands([]), "
                      "bands(Array.from({length: 50}, (_, i) => ['I' + i, 1]))]")
        self.assertAlmostEqual(sum(b["width"] for b in got[0]), 360, places=6)
        self.assertGreaterEqual(min(b["width"] for b in got[0]), 8)
        self.assertEqual([b["start"] for b in got[0]][0], 0)
        self.assertEqual(got[1], [])
        self.assertAlmostEqual(got[2][0]["width"], 7.2, places=6)  # 50 x 8 > 360: equal shares

    def test_cluster_keys(self):
        subs = "['Side channels', 'Auth']"
        got = self.js([], f"[clusterKey({{interest: 'X', subareas: ['Auth', 'Side channels']}}, {subs}), "
                      f"clusterKey({{interest: 'X', subareas: null}}, {subs}), "
                      f"clusterKey({{interest: 'X', subareas: []}}, {subs}), "
                      f"clusterKey({{interest: 'X', subareas: ['Gone']}}, {subs}), "
                      f"clusterName('X::__unlabelled'), clusterName('X::Auth')]")
        self.assertEqual(got, ["X::Auth", "X::__unlabelled", "X::__none", "X::__none",
                               "Not yet labelled", "Auth"])

    def test_empty_library(self):
        got = self.js([], "(() => { const m = buildGlobe([], [], {}); "
                      "return [m.n, m.bands.length, pickDots(m, new Uint8Array(0), rotation(0, 0), "
                      "() => true, 10).inView]; })()")
        self.assertEqual(got, [0, 0, 0])

    def test_positions_are_stable_and_on_the_sphere(self):
        items = ("[{id: 'p1', interest: 'A', year: 2020, subareas: ['s'], score: 80}, "
                 "{id: 'p2', interest: 'B', year: null, subareas: null, score: null}]")
        got = self.js([], f"(() => {{ const a = buildGlobe({items}, ['A', 'B'], {{A: ['s'], B: []}}); "
                      f"const b = buildGlobe({items}, ['A', 'B'], {{A: ['s'], B: []}}); "
                      f"return [a.vx[0] === b.vx[0], Math.hypot(a.vx[0], a.vy[0], a.vz[0]), "
                      f"Math.asin(a.vy[1]) * 180 / Math.PI <= -74, [...a.order]]; }})()")
        self.assertTrue(got[0])
        self.assertAlmostEqual(got[1], 1, places=5)
        self.assertTrue(got[2])            # undated items sit at the south pole
        self.assertEqual(got[3], [0, 1])   # higher score first

    def test_pick_dots_caps_by_priority_and_counts_everything(self):
        got = self.js([], "(() => { const items = Array.from({length: 50}, (_, i) => "
                      "({id: 'p' + i, interest: 'A', year: 2020, subareas: [], score: i})); "
                      "const m = buildGlobe(items, ['A'], {A: []}); const mask = new Uint8Array(50).fill(1); "
                      "const r = pickDots(m, mask, rotation(0, 0), () => true, 5); "
                      "const front = [...Array(50).keys()].filter((i) => project(rotation(0, 0), m.vx[i], m.vy[i], m.vz[i])[2] > 0.02); "
                      "const top5 = front.sort((a, b) => items[b].score - items[a].score).slice(0, 5); "
                      "return [r.drawn.length, r.inView === front.length, JSON.stringify(r.drawn) === JSON.stringify(top5)]; })()")
        self.assertEqual(got, [5, True, True])  # the five highest scored in view, in that order

    def test_zoom_blend(self):
        got = self.js([], "[zoomBlend(1), zoomBlend(2), zoomBlend(3)]")
        self.assertEqual(got[0], {"regions": 1, "dots": 0})
        self.assertGreater(got[1]["regions"], 0); self.assertGreater(got[1]["dots"], 0)
        self.assertEqual(got[2], {"regions": 0, "dots": 1})

    def test_fly_target_brings_the_point_to_the_front(self):
        got = self.js([], "(() => { const p = [0.3, 0.5, -0.81]; const t = flyTarget(...p); "
                      "return project(rotation(t.yaw, t.pitch), ...p); })()")
        self.assertAlmostEqual(got[0], 0, places=5)
        self.assertAlmostEqual(got[1], 0, places=5)
        self.assertGreater(got[2], 0.99)

    def test_year_marks(self):
        got = self.js([], "[yearMarks(2003, 2026), yearMarks(2020, 2020), yearMarks(null, null)]")
        self.assertEqual(got, [[2003, 2010, 2015, 2020, 2026], [2020], []])

    def test_labels_never_overlap_and_big_ones_win(self):
        got = self.js([], "placeLabels([{text: 's', x: 10, y: 10, w: 40, h: 14, priority: 5, big: false}, "
                      "{text: 'B', x: 20, y: 12, w: 60, h: 18, priority: 1e9, big: true}, "
                      "{text: 't', x: 200, y: 10, w: 40, h: 14, priority: 4, big: false}], 1).map((c) => c.text)")
        self.assertEqual(got, ["B", "t"])
```

- [ ] **Step 2: Run them to see them fail**

Run: `python3 -m unittest tests.test_graph_template.GlobeMathTests -v`
Expected: FAIL ("function hash01 not found in the template").

- [ ] **Step 3: Implement the functions in `graph/parts/globe.js`**

- `yearLat`: undated is -80. Dated latitudes run from -62 (oldest) to +62 (newest). When `hi - lo <= 10` the scale is linear (one year: 0). Otherwise the newest ten years (`hi - 9` to `hi`) take the top 60% of that range and every earlier year shares the bottom 40%, so a long tail never squashes recent work.
- `bands`: width `MIN_BAND_DEG + share * (360 - MIN_BAND_DEG * k)`; when `MIN_BAND_DEG * k > 360` every band gets `360 / k`.
- `clusterKey`: `interest + "::" + ` the first label that is in the interest's sub-area list; `__unlabelled` when `subareas` is `null`; `__none` when nothing listed fits. `clusterName` gives "Not yet labelled" and "Fits no listed sub-area" for those two.
- `buildGlobe`: band order is `interestOrder` filtered to interests with items, then any other interest name found on items (for example "Uncategorized"), last. Within a band, each cluster gets an equal slot in the order of the interest's sub-area list, then `__none`, then `__unlabelled`. An item's longitude is its slot centre plus `(hash01(id) - 0.5) * 0.8 * slotWidth`. Its latitude is `yearLat` plus `(hash01(id + "y") - 0.5) * 4` degrees; undated items get `-80 + hash01(id + "y") * 6`. `order` sorts by score descending, `null` scores ranked as 50, ties by id.
- `pickDots`: walk `order`. Skip masked items and items with depth ≤ 0.02 or off screen. Count every item still in view, and draw only the first `cap`.
- `zoomBlend`: `regions = clamp((2.4 - z) / 1.0, 0, 1)`, `dots = clamp((z - 1.3) / 0.9, 0, 1)`.
- `flyTarget`: `yaw = atan2(z, x) - pi / 2`, `pitch = atan2(y, hypot(x, z))`, with `project` defined as `x1 = x*cy + z*sy`, `z1 = -x*sy + z*cy`, `[x1, y*cp - z1*sp, y*sp + z1*cp]`.
- `yearMarks`: `lo`, `hi`, and every multiple of 5 strictly between them that is at least 3 years from both ends, so labels never crowd. An empty range gives `[]`.
- `placeLabels`: sort by priority descending. Keep a candidate if its box overlaps no kept box. Big labels don't count toward `maxSmall`.

- [ ] **Step 4: Run the tests**

Run: `python3 -m unittest tests.test_graph_template -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add graph/parts/globe.js tests/test_graph_template.py
git commit -m "graph: globe maths - bands, year scale, clusters, dot cap, labels"
```

---

### Task 6: The globe renderer and its controls

**Files:**
- Modify: `graph/parts/globe.js` (renderer), `graph/template.html` (globe tokens, `#globe` canvas, `#globe-nav` toolbar markup; generalise `initToolbar` to `initToolbar(root, storageKey)`)
- Test: `tests/test_graph_template.py`

**Interfaces:**
- Consumes: Task 5's functions; `S`, `passes`, `isNew`, `interestColor`, `css`, `store`, `clampToolbar`.
- Produces: `GL` (one object holding `model, mask, yaw, pitch, zoom, panX, panY, hover, hits, clusterHits, arcHits, lastDraw`); `globeInit()` (builds the model once, attaches input handlers); `globeRefresh()` (recomputes `GL.mask` from `passes()` and redraws; call after any filter change); `globeDraw()`; `globeSelect(id)` and `globeClear()`; `globeFly(x, y, z, zoom)`; events the overview consumes: `GL.onSelect(id)`, `GL.onHover(info)` with `info = {kind: "item", id} | {kind: "line", from, to} | null`, `GL.onView()` (after any move or zoom). CSS tokens `--cites` and `--citedby`: dark `#ffd27a` and `#8fe3ff`, light `#8a5a00` and `#00728f`.

- [ ] **Step 1: Write the failing test**

```python
def test_line_colours_are_not_interest_colours(self):
    root = re.search(r":root \{(.*?)\n\}", TEMPLATE, re.S).group(1)
    dark = re.search(r"prefers-color-scheme: dark\).*?\{(.*?)\n  \}", TEMPLATE, re.S).group(1)
    for block in (root, dark):
        tokens = dict(re.findall(r"--([\w-]+):\s*(#[0-9a-fA-F]{6})", block))
        interest = {tokens[f"s{i}"].lower() for i in range(1, 7)}
        self.assertNotIn(tokens["cites"].lower(), interest)
        self.assertNotIn(tokens["citedby"].lower(), interest)
        self.assertNotEqual(tokens["cites"], tokens["citedby"])

def test_globe_regions_present(self):
    for region in ("globe", "globe-nav", "gnav-zoom-in", "gnav-zoom-out", "gnav-fit",
                   "gnav-rotate", "gnav-pan"):
        self.assertRegex(TEMPLATE, rf'id="{region}"', region)
```

- [ ] **Step 2: Run them to see them fail**

Run: `python3 -m unittest tests.test_graph_template -v`
Expected: FAIL.

- [ ] **Step 3: Implement the renderer** (what each layer draws, in order):

1. **Sphere.** A soft radial-gradient sphere centred in the free area. On wide screens that area is the canvas minus the left card's width, and minus the selection card's when one is open. Radius `0.36 * min(freeWidth, 0.95 * height) * zoom`, offset by the pan.
2. **Meridians and year rings.** Faint meridians at band starts. Faint latitude rings at `yearMarks`, each labelled at its leftmost visible point.
3. **Regions.** At `zoomBlend.regions > 0`, one radial glow per non-empty cluster (from `clusterStats`), in its interest colour. Glow radius `R * (0.028 + 0.003 * sqrt(count))`, alpha scaled by depth.
4. **Lines.** With an item selected: amber `--cites` lines from it to what it cites and blue `--citedby` lines from what cites it, each with an arrowhead at the cited end, drawn only when both ends pass the mask. With nothing selected, and zoom between 1.15 and 4, the 300 citation lines whose cited paper is most cited within the mask, faint and without colour coding. Polylines are kept in `GL.arcHits` for hovering.
5. **Dots.** At `zoomBlend.dots > 0`, `pickDots(..., DOT_CAP)`: circles for papers, squares for web sources, radius `2.3 * zoom^0.3` scaled by depth, in the interest colour. A white ring is drawn only for `isNew` items. With `S.highlight` set, everything else is drawn at 0.1 alpha.
6. **The selected item.** A filled white dot (squares stay square) with a soft white glow, never a ring, drawn at every zoom.
7. **Labels** through `placeLabels`:
   - interest names at their band centre on the equator, bold, while zoom < 3.2;
   - cluster labels `"<name> · <count>"`, plus `" · <n> new"` when it has new items, at most 16 when zoom < 1.5 and 60 beyond;
   - all with a dark halo.

Input:
- **Drag** rotates (or pans in Move mode, `H`), with speed `0.0055 / zoom^0.75` radians per pixel and pitch clamped to ±1.4.
- **Wheel** zooms by `exp(-deltaY * 0.0016)`, clamped to the zoom limits.
- **Click** on a dot within 12 px selects it. A click on a cluster glow flies there (`globeFly`, zoom `max(zoom, 3.4)`). Empty space clears the selection.
- **Double-click** a dot or cluster: fly there and remember the view. Double-click again (anywhere): go back.
- **Hover** finds a dot within 9 px, else a line within 6 px, and calls `GL.onHover`.

`globeFly` tweens over 650 ms with `requestAnimationFrame`, but jumps straight there when `document.hidden`. `#globe-nav` copies the Explore toolbar: zoom in/out (×1.5), Fit (reset view), Rotate and Move, and it is draggable by its grip through the generalised `initToolbar`. Redraw on demand only: input, resize, theme change, or a `globeRefresh()`. Never redraw on an idle animation loop.

`GL.lastDraw` records the last frame's draw time in ms. With `#perf=1` in the hash, after the first draw, rotate 120 frames by 0.02 rad and store `window.kgPerf = {firstDraw: ms since navigation start, frames: [ms…]}`.

- [ ] **Step 4: Run the tests**

Run: `python3 -m unittest discover -s tests`
Expected: all PASS.

- [ ] **Step 5: Check it in a browser**

Build `--synthetic 20000` and the live library in turn and serve them as in Task 3. Check each of these:
- Overview shows glowing regions with counts when zoomed out.
- Zooming in opens them into dots, with the notice when the cap trims.
- Clicking a paper draws amber and blue arrowed lines.
- The selected dot glows and has no ring.
- Drag, wheel, double-click there and back, Fit, and Move all work.
- Dark and light both read clearly.
- No console errors.

- [ ] **Step 6: Commit**

```bash
git add graph/parts/globe.js graph/template.html tests/test_graph_template.py
git commit -m "graph: the research globe - regions, dots, directional lines, controls"
```

---

### Task 7: The Overview tab: cards, keys and minimising

**Files:**
- Modify: `graph/parts/overview.js`, `graph/template.html` (Overview markup and CSS)
- Test: `tests/test_graph_template.py`

**Interfaces:**
- Consumes: `GL` and its events, `S`, `passes`, `shortlisted`, `colourSlots`, `select`, `setTab`, `highlightSet`, `exploreOnlyFilters`, `store`.
- Produces: `shortDate(iso) -> "24 Oct"`; `lineSentences(outN, inN) -> [string, string]`; `hiddenLinesNote(hidden) -> string`; `ringKey(newInView, since) -> string`; `cardChip(name, count, extra) -> string`; `kindCounts(items, passIgnoringType) -> {both, paper, web}`; `renderMapCard()`, `renderSelCard(id)`, `renderOverview()` (registered as `TAB_HOOKS.overview`).

- [ ] **Step 1: Write the failing tests** (exact copy from the spec)

```python
@unittest.skipUnless(shutil.which("node"), "node not installed")
def test_line_sentences(self):
    got = run_js(["lineSentences"], "", "[lineSentences(2, 1), lineSentences(0, 0), lineSentences(1, 3)]")
    self.assertEqual(got[0], ["Amber, going out: this paper cites 2 papers in your library.",
                              "Blue, coming in: 1 paper in your library cites this one."])
    self.assertEqual(got[1], ["Amber, going out: none, because none of this paper's references are in your library.",
                              "Blue, coming in: none, because no paper in your library cites this one yet."])
    self.assertEqual(got[2], ["Amber, going out: this paper cites 1 paper in your library.",
                              "Blue, coming in: 3 papers in your library cite this one."])

@unittest.skipUnless(shutil.which("node"), "node not installed")
def test_ring_key_and_dates(self):
    got = run_js(["shortDate", "ringKey", "hiddenLinesNote"], "",
                 "[shortDate('2026-10-24'), ringKey(82, '2026-10-24'), ringKey(1, '2026-03-02'), "
                 "hiddenLinesNote(0), hiddenLinesNote(1), hiddenLinesNote(2)]")
    self.assertEqual(got, ["24 Oct", "○ ring = new since your last search (24 Oct) · 82 in view",
                           "○ ring = new since your last search (2 Mar) · 1 in view", "",
                           "1 more is hidden by the current filters.",
                           "2 more are hidden by the current filters."])

@unittest.skipUnless(shutil.which("node"), "node not installed")
def test_kind_counts_follow_the_other_filters(self):
    got = run_js(["kindCounts"], "", "kindCounts([{type: 'paper', ok: true}, {type: 'paper', ok: false}, "
                 "{type: 'web', ok: true}], (n) => n.ok)")
    self.assertEqual(got, {"both": 2, "paper": 1, "web": 1})

def test_overview_regions_and_phone_width(self):
    for region in ("mapcard", "selcard", "ringkey", "globe-tip", "globe-legend", "globe-notice",
                   "highlight-chip"):
        self.assertRegex(TEMPLATE, rf'id="{region}"', region)
    # On a phone-width screen the cards start as chips, so the globe is visible.
    self.assertIn('matchMedia("(max-width: 600px)")', PAGE_SOURCE)
    self.assertIn("Nothing in your library yet. Run /research to start.", PAGE_SOURCE)
```

- [ ] **Step 2: Run them to see them fail**

Run: `python3 -m unittest tests.test_graph_template -v`
Expected: FAIL.

- [ ] **Step 3: Implement**

**`#mapcard` ("On your map"), top left, in this order:**
- "On your map" and a minimise control.
- The big number of items shown, and "of N in the library, across K research interests".
- **Show: Both | Papers only | Web only**, a segmented switch carrying `kindCounts` under the other filters. It sets `S.filters.sets.type` to empty, `{"Paper"}` or `{"Web source (not peer-reviewed)"}`.
  - Under "Papers only": "Papers only means peer-reviewed sources: no web pages."
  - Under "Web only": "Web sources are not peer-reviewed and have no citation lines."
- The shortlist checkbox: "Include peripheral and excluded", with "N more are hidden · the map starts with Core, Supporting and not yet scored" or "showing everything".
- A line "○ N new since 24 Oct". Clicking it toggles `S.filters.newOnly`.
- "Research interests (click a name to hide it; click its dot to colour it)". A search box appears above eight interests. One row per interest with its colour dot and the count it would show.
  - Clicking a grey dot colours it if fewer than six are coloured. Otherwise the card shows "Six interests are coloured; uncolour one first."
  - The choice is saved under `kg-colours`.
- Below the rows: "The six largest are coloured by default, the rest grey, so no colour repeats."
- If `exploreOnlyFilters` is non-empty: "Also filtered in Explore: …" with "Clear those".
- "See how your library connects →", which opens the How it connects tab.
- With no items at all, the card shows only "Nothing in your library yet. Run /research to start."

**`#selcard`, top right, on selection:**
- Title, then chips for interest, sub-area, year, grade and kind, then "Cites a · cited by b (within the library)".
- For a paper: the two `lineSentences`, each with a coloured `━▶` key; then "The arrowhead points at the paper being cited. A line only appears when both papers are in your library. This paper may cite others you have not collected." and `hiddenLinesNote`.
- For a web item instead: "Web sources are not peer-reviewed and have no citation lines, so nothing is drawn from this one."
- Next steps, each setting `S.highlight` through `highlightSet`: "Show what it cites", "Show what cites it", "Show its research group's other papers" (only when it has a `primaryLab`), "Show the same sub-area". Then "Open full details", which runs `setTab("explore")` and `select(id)`.
- Esc or × clears it.
- If the selected item is hidden by the filters, the card says "Hidden by the current filters."

**Other parts of the tab:**
- `#ringkey`, near the top of the globe: `ringKey(...)`, shown only when ringed items are in view and dots are showing.
- `#globe-tip`, the hover label:
  - over an item: its title, then year and kind, then "○ New since your last search (24 Oct)" when it is new;
  - over a line: "<citing title> cites <cited title>".
- `#globe-legend`, bottom left, minimisable. It reads: "Each glow is a sub-area, sized by its items. Zoom in to see the items: ● paper, ■ web source. North = newer, south = older; undated at the south pole. Ring = new since your last search." When lines are drawn it adds: "Lines are citations between papers in your library: click a paper to see them, amber for what it cites, blue for what cites it."
- `#globe-notice`, bottom right, with one of:
  - "Zoomed out: showing sub-area totals. Zoom in to see items."
  - "2,500 of 3,018 items in view drawn, highest scored first. Zoom in or filter to see more."
  - "N items in view, all drawn."
- `#highlight-chip`: "Highlighted: <why> · N · Clear".

**Minimising:** every card has a minimise control. Minimised, it becomes a chip that still says what it is and its key count, using `cardChip`, for example "▸ On your map · 325" and "▸ Selected: <short title>". A minimised card is remembered in `S.min.cards` and saved through `store`. Under 600 px wide, every card starts minimised.

- [ ] **Step 4: Run the tests**

Run: `python3 -m unittest discover -s tests`
Expected: all PASS.

- [ ] **Step 5: Check it in a browser** (live library, then `--synthetic 20000`)

Check each of these:
- The switch counts add up to the number shown.
- Web only leaves only squares and no lines.
- The shortlist toggle changes the number and the notice.
- Colouring a seventh interest is refused, with the message.
- The ring key appears while ringed dots are in view.
- The hover label shows title, year, kind and the "new" line.
- Line hover shows "A cites B".
- Each next step highlights its answer.
- "Open full details" lands on the same item in Explore.
- `m` minimises every card to chips and restores them.
- At 375 px wide the cards start as chips and nothing scrolls sideways.

- [ ] **Step 6: Commit**

```bash
git add graph/parts/overview.js graph/template.html tests/test_graph_template.py
git commit -m "graph: Overview - On your map, selection card, ring key, hover, minimising"
```

---

### Task 8: How it connects, and Status

**Files:**
- Modify: `graph/parts/connects.js`, `graph/parts/status.js`, `graph/template.html` (an `svgEl(tag, attrs, ...kids)` helper beside `el()`)
- Test: `tests/test_graph_template.py`

**Interfaces:**
- Consumes: `D`, `ITEMS`, `VISIBLE`, `setTab`, `setView`, `S`.
- Produces: `schemaCounts(D) -> {interests, subareas, papers, web, groups, reports, gaps, cites}` (groups = labs with more than one paper; sub-areas = sub-area hubs); `SCHEMA_LINKS` (`[from, to, label]`, the eight kinds' relations: paper→sub-area "labelled with", web→sub-area "labelled with", sub-area→interest "part of", paper→paper "cites", paper→group "from", paper→report "used in", gap→sub-area "about", gap→report "open question in"); `statusRows(D, shown, hidden) -> [{label, value, problem, fix}]`; `renderConnects()`, `renderStatus()` (tab hooks).

- [ ] **Step 1: Write the failing tests**

```python
@unittest.skipUnless(shutil.which("node"), "node not installed")
def test_schema_counts(self):
    d = ('{nodes: [{type:"interest"},{type:"subarea"},{type:"subarea"},{type:"paper"},{type:"web"},'
         '{type:"report"},{type:"gap"}], edges: [{type:"cites"},{type:"cites"},{type:"subarea"}], '
         'labs: [{papers:[1,2]},{papers:[3]}]}')
    got = run_js(["schemaCounts"], "", f"schemaCounts({d})")
    self.assertEqual(got, {"interests": 1, "subareas": 2, "papers": 1, "web": 1, "groups": 1,
                           "reports": 1, "gaps": 1, "cites": 2})

@unittest.skipUnless(shutil.which("node"), "node not installed")
def test_status_rows_pair_problems_with_fixes(self):
    d = ('{meta: {built: "2026-10-31", newSince: "2026-10-24", warnings: [], '
         'coverage: {found: 291, notFound: 2, mismatch: 5, noId: 3, notFetched: 0}, '
         'labels: {notLabelled: 71, fitsNone: 59, stale: 0, noContribution: 4}, counts: {}}, edges: []}')
    rows = run_js(["statusRows"], "", f"statusRows({d}, 325, 51)")
    by = {r["label"]: r for r in rows}
    self.assertEqual(by["Last built"]["value"], "2026-10-31")
    self.assertIn("python3 tools/knowledge_graph.py --enrich", by["OpenAlex coverage"]["fix"])
    self.assertIn("python3 tools/state.py subareas", by["Sub-area labels"]["fix"])
    self.assertTrue(all(r["fix"] for r in rows if r["problem"]))
```

- [ ] **Step 2: Run them to see them fail**

Run: `python3 -m unittest tests.test_graph_template -v`
Expected: FAIL.

- [ ] **Step 3: Implement**

**How it connects.**
- **The diagram.** An SVG with one labelled box per kind ("Research interests 3", "Sub-areas 22", "Papers 358", "Web sources 18", "Research groups 39", "Your reports 4", "Gaps 23") and the links from `SCHEMA_LINKS`, each labelled. The paper-to-paper link reads "cites (683)".
- **Clicking a kind** shows its count, what it connects to, and one action:
  - papers or web sources: "Show all N on the map" sets the Papers/Web switch and opens Overview;
  - interests or sub-areas: opens Overview zoomed out;
  - research groups, reports or gaps: opens Explore in the Research groups, Library or Gaps view.
- **One-line explanation** above the diagram: "The kinds of thing in your library, how many there are, and how they link. Counts are the whole library, before filters."

**Status.** A two-column table of `statusRows`, in this order:
- Last built.
- Items shown and hidden. Hidden is split into "by the shortlist", "off-topic" and "by other filters".
- OpenAlex coverage, listing found, not found, title rejected, without an id, and not yet fetched.
- Sub-area labels: missing, fits none and stale.
- Contribution labels missing.
- Citation links.
- When it next refreshes: "after your next /research, /rank, /synthesize, /update or /websearch".
- The build's warnings.

A row with a problem gets a "Fix:" cell with the command to run:
- missing OpenAlex data: `python3 tools/knowledge_graph.py --enrich`;
- missing labels: the `/rank` or `python3 tools/state.py subareas` route that `graph/README.md` already names.

- [ ] **Step 4: Run the tests**

Run: `python3 -m unittest discover -s tests`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add graph/parts/connects.js graph/parts/status.js graph/template.html tests/test_graph_template.py
git commit -m "graph: How it connects and Status tabs"
```

---

### Task 9: Ask

**Files:**
- Modify: `graph/parts/ask.js`, `graph/template.html` (Ask markup)
- Test: `tests/test_graph_template.py`

**Interfaces:**
- Consumes: `ITEMS`, `D.labs`, `D.gaps`, `D.interests`, `passes`, `isNew`, `highlightSet`, `openList`, `setTab`.
- Produces: `parseQuestion(q, ctx) -> {ok: true, ids: string[], steps: string[]} | {ok: false, message: string, closest: string}`, with `ctx = {items, interests, labs, gaps, since}`; `ASK_EXAMPLES` (the spec's six examples, as written); `renderAsk()`.

The grammar, all case-insensitive, matched in this order:

1. **Lab.** "(papers) from the same lab as <title words>": the best title match's `primaryLab`, then that lab's papers.
2. **Cites.** "what cites <title words>" or "what does <title words> cite": the cites edges of the best title match. A title match is the item with the most shared words of three letters or more. With no word in common, or a tie between two or more, the answer is not ok and the message lists up to three candidate titles.
3. **Thin.** "thin sub-areas": the items in sub-areas named by gaps of kind `thin`.
4. **Unused.** "scored but never used in a report": status "Scored, not yet used in a report".
5. **Filters.** Anything else is read as filter words:
   - "new (since my last search)": `isNew`.
   - An interest: any word of four letters or more, or any capitalised acronym, that appears in exactly one interest name (for example "XR").
   - A contribution word: "attack" or "attacks", "defence", "defense" or "defences", "survey", "measurement", "user study", "tool", "position".
   - Year words: "since YYYY", "before YYYY", "in YYYY", "between YYYY and YYYY".
   - "papers" or "web sources": the kind.
   - "with no defence": keeps attack items whose sub-areas hold no item with contribution `defence`.
   - If no filter word is recognised, the answer is not ok.

`steps` explains each step in words, for example "Interest: XR/Immersive Systems Security & Privacy", "Contribution: attack", "Year: 2024 or later", "Only sub-areas with no defence paper". Every answer goes through `passes()` before it is returned, so Ask never shows an item the map hides. When that drops items, the last step says "N more are hidden by the current filters".

- [ ] **Step 1: Write the failing test**

```python
@unittest.skipUnless(shutil.which("node"), "node not installed")
def test_ask_patterns(self):
    ctx = """{since: "2026-10-01", interests: [{name: "XR Security"}, {name: "AI Security"}],
      gaps: [{kind: "thin", interest: "XR Security", subarea: "Gaze"}],
      labs: [{id: "L1", papers: ["p1", "p3"]}],
      items: [
        {id: "p1", type: "paper", title: "Heimdall gaze defence", interest: "XR Security", year: 2025,
         contribution: "defence", subareas: ["Gaze"], primaryLab: "L1", firstSeen: "2026-10-02", citesOut: ["p2"]},
        {id: "p2", type: "paper", title: "Unique Identification of VR users", interest: "XR Security",
         year: 2024, contribution: "attack", subareas: ["Motion"], firstSeen: "2026-09-01", citesOut: []},
        {id: "p3", type: "paper", title: "Old attack", interest: "XR Security", year: 2019,
         contribution: "attack", subareas: ["Motion"], primaryLab: "L1", firstSeen: "2026-09-01", citesOut: []},
        {id: "w1", type: "web", title: "A blog", interest: "AI Security", year: 2025, firstSeen: "2026-10-03", citesOut: []}]}"""
    prelude = ("function passes() { return true; } "
               "function isNew(n) { return (n.firstSeen || '') >= '2026-10-01'; } "
               "const S = {since: '2026-10-01'};")
    q = lambda s: f"parseQuestion({json.dumps(s)}, {ctx})"
    got = run_js(["parseQuestion"], prelude, "[" + ", ".join(q(s) for s in [
        "attack papers in XR since 2024 with no defence",
        "papers from the same lab as Heimdall",
        "what cites the Unique Identification paper?",
        "thin sub-areas",
        "new since my last search",
        "what is the meaning of life"]) + "]")
    self.assertEqual(got[0]["ids"], ["p2"])
    self.assertEqual(sorted(got[1]["ids"]), ["p1", "p3"])
    self.assertEqual(got[2]["ids"], ["p1"])
    self.assertEqual(got[3]["ids"], ["p1"])
    self.assertEqual(sorted(got[4]["ids"]), ["p1", "w1"])
    self.assertFalse(got[5]["ok"])
    self.assertTrue(got[5]["closest"])
    self.assertTrue(all(g["steps"] for g in got[:5]))
```

(`citesOut` is the test's stand-in for the cites edges; `parseQuestion` reads citations through `ctx.citesOf(id)` when given, else `item.citesOut`. The page passes `citesOf` built from `D.edges`.)

- [ ] **Step 2: Run it to see it fail**

Run: `python3 -m unittest tests.test_graph_template -v`
Expected: FAIL.

- [ ] **Step 3: Implement `parseQuestion` and the tab**

The tab has:
- **The question box,** whose placeholder is the first example.
- **The six examples** as buttons.
- **The answer,** which shows:
  - the numbered `steps` and the count;
  - "Show on the map", which runs `highlightSet(ids, question)` and opens Overview;
  - "Open as a list", which runs `openList(ids, question)` and opens Explore, where Export works;
  - "Clear".
- **An unsupported question** shows the message, "Try: <closest example>" and "Or filter by hand in Explore". The closest example is the one sharing the most words with the question.
- **A note under the box:** "Questions become the same filters and steps you could do by hand, so every answer is exact and repeatable. No AI is used."

The question's own text is shown with `textContent`.

- [ ] **Step 4: Run the tests**

Run: `python3 -m unittest discover -s tests`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add graph/parts/ask.js graph/template.html tests/test_graph_template.py
git commit -m "graph: Ask - plain questions as exact filters and steps"
```

---

### Task 10: Documentation, scale check, release

**Files:**
- Modify: `graph/README.md`, `.claude/commands/graph.md`
- Test: `tests/test_knowledge_graph.py` (`test_documented_invocations_use_real_flags` already covers the commands)

- [ ] **Step 1: Rewrite the README's "What the page shows"**

Write it for the tabs, in plain words: what each tab is for, how to read the globe (regions, year height, ● and ■, rings, amber and blue lines), the shortlist, the Papers/Web switch, minimising (`m`), and what Ask can and cannot answer. Add a "Performance" section with the limits from Global Constraints and the command that measures them (`--synthetic 20000`, then open the page with `#perf=1` and read `window.kgPerf`). Remove every mention of Simple and Advanced. In `.claude/commands/graph.md`, replace the Simple/Advanced description with the tabs.

- [ ] **Step 2: Measure at scale in a real browser**

Build with `python3 tools/knowledge_graph.py --synthetic 20000`, serve it as in Task 3, and open `#perf=1`. Record `firstDraw`, the median frame and the 95th percentile in the commit message. Then run Review Focus 1 and 5 by hand: an empty library (temporarily point the build at empty state in a temp copy) and 375 px width.
Expected: within the README's limits. If not, stop and report the measurements rather than raising the limits.

- [ ] **Step 3: Run everything**

Run: `python3 -m unittest discover -s tests && python3 tools/knowledge_graph.py && python3 tools/knowledge_graph.py --check`
Expected: all tests PASS; `graph/index.html: PASS (0 errors)`.

- [ ] **Step 4: Commit, then release** (after the whole-branch review)

```bash
git add graph/README.md .claude/commands/graph.md
git commit -m "graph: document the tabbed map and its performance limits"
git fetch origin && git rebase origin/master && git push origin HEAD:master
gh run watch "$(gh run list --repo BleOdel/ai-research-assistant --limit 1 --json databaseId -q '.[0].databaseId')" --repo BleOdel/ai-research-assistant --interval 30 --exit-status
```

Then pull both clones, rebuild the live page in the working clone (`python3 tools/knowledge_graph.py` and `--check`), and remove the worktree.
