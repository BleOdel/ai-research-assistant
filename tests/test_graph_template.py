import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools"))
import knowledge_graph  # noqa: E402

TEMPLATE = (REPO_ROOT / "graph" / "template.html").read_text()
PARTS = REPO_ROOT / "graph" / "parts"
PART_NAMES = re.findall(r'<script data-part="([\w.-]+)"></script>', TEMPLATE)
# The template plus every page part, in the order the page loads them.
PAGE_SOURCE = TEMPLATE + "".join("\n" + (PARTS / name).read_text() for name in PART_NAMES)
VENDOR = REPO_ROOT / "graph" / "vendor"
EMPTY = {"meta": {"counts": {}, "summary": "", "newSince": "2026-10-21", "built": "2026-10-21",
                  "thresholds": {}}, "interests": [], "nodes": [], "edges": [], "gaps": [],
         "labs": []}


def page_function(name):
    """The source of one top-level function in the page script or its parts."""
    m = re.search(rf"^function {name}\(.*?^}}$", PAGE_SOURCE, re.S | re.M)
    if not m:
        raise AssertionError(f"function {name} not found in the template")
    return m.group(0)


def run_js(names, prelude, expression):
    """Evaluate EXPRESSION in node after PRELUDE and the named page functions."""
    script = prelude + "\n" + "\n".join(page_function(n) for n in names) + \
        f"\nconsole.log(JSON.stringify({expression}));"
    result = subprocess.run(["node", "-e", script], capture_output=True, text=True)
    if result.returncode:
        raise AssertionError(result.stderr)
    return json.loads(result.stdout)


class TemplateTests(unittest.TestCase):
    def test_template_has_single_data_slot(self):
        self.assertEqual(TEMPLATE.count(knowledge_graph.SLOT), 1)

    def test_no_external_resources(self):
        self.assertEqual(knowledge_graph.check(knowledge_graph.render(EMPTY, TEMPLATE)), [])

    def test_required_ui_regions_present(self):
        for region in ("topbar", "drawer", "graph", "detail", "trail", "listview", "legend",
                       "summary", "filters", "search", "since"):
            self.assertRegex(TEMPLATE, rf'id="{region}"', region)

    def test_no_internal_status_words_in_template(self):
        # The page speaks in plain words (knowledge_graph.STATUS_LABELS); a raw state
        # name anywhere in the template would leak onto the page.
        for word in ("ranked", "synthesized", "unfetchable"):
            self.assertNotRegex(TEMPLATE, rf"(?i)\b{word}\b", word)

    def test_every_status_label_has_an_encoding(self):
        # The legend explains each status by how solid the paper looks; a status
        # label the template does not know would render with no explanation.
        order = re.search(r"const STATUS_ORDER = \[(.*?)\];", TEMPLATE, re.S).group(1)
        opacity = re.search(r"const STATUS_OPACITY = \{(.*?)\};", TEMPLATE, re.S).group(1)
        expected = set(knowledge_graph.STATUS_LABELS.values())
        self.assertEqual(set(re.findall(r'"([^"]+)"', order)), expected)
        self.assertEqual(set(re.findall(r'"([^"]+)":', opacity)), expected)
        self.assertIn(knowledge_graph.WEB_KIND, TEMPLATE)

    def test_vendor_files_inlined_and_licensed(self):
        page = knowledge_graph.render(EMPTY, TEMPLATE)
        self.assertNotIn("data-vendor", page)
        self.assertIn("ForceGraph3D", page)
        self.assertIn("Three.js Authors", page)
        self.assertNotRegex(page, r"<script[^>]*\bsrc=")
        licences = (VENDOR / "LICENSES.md").read_text()
        for name in ("three 0.160.0", "3d-force-graph 1.73.3"):
            self.assertIn(f"## {name}", licences)
        self.assertEqual(licences.count("- Licence: MIT"), 2)

    def test_inlined_script_cannot_close_its_element(self):
        # A vendored file containing "</script" would end the inline script early.
        page = knowledge_graph.render(EMPTY, TEMPLATE.replace(
            '<script data-vendor="three.min.js"></script>',
            '<script data-vendor="three.min.js"></script><script data-vendor="x.js"></script>'),
            vendor={"x.js": 'var s = "</script><b>";'})
        self.assertNotIn('"</script><b>"', page)
        self.assertIn('"<\\/script><b>"', page)

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_unknown_lab_id_is_not_a_crash(self):
        # A bookmark or hand-edited address can name a lab the current build does
        # not have; every lookup goes through labOf(), which answers null.
        self.assertNotIn("labById.get(id.slice(4))", TEMPLATE.replace(page_function("labOf"), ""))
        got = run_js(["labOf"], 'const labById = new Map([["L-1", {name: "A"}]]);',
                     '[labOf("lab:L-1"), labOf("lab:L-nope"), labOf("paper:x"), labOf(null)]')
        self.assertEqual(got, [{"name": "A"}, None, None, None])

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_lineage_follows_the_whole_chain(self):
        # a cites b, b cites c, c cites a (a cycle), d cites a, e is unrelated.
        prelude = """const D = {edges: [
          {source: "a", target: "b", type: "cites"}, {source: "b", target: "c", type: "cites"},
          {source: "c", target: "a", type: "cites"}, {source: "d", target: "a", type: "cites"},
          {source: "e", target: "x", type: "cites"}, {source: "a", target: "h", type: "subarea"}]};
        let CITE_MAPS = null;"""
        got = run_js(["lineageOf", "citeMaps"], prelude, 'lineageOf("d")')
        self.assertEqual(sorted(got["up"]), ["a"])
        self.assertEqual(got["down"], [])
        self.assertEqual(sorted(got["ancestors"]), ["a", "b", "c"])
        self.assertEqual(got["descendants"], [])
        got = run_js(["lineageOf", "citeMaps"], prelude, 'lineageOf("b")')
        self.assertEqual(sorted(got["descendants"]), ["a", "c", "d"])
        self.assertNotIn("b", got["all"])

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_csv_cells_cannot_become_formulas(self):
        # Titles come from untrusted pages; a spreadsheet runs a cell starting with
        # = + - or @ as a formula.
        got = run_js(["csvCell"], "", '["=HYPERLINK(1)", "+1", "-x", "@SUM(A1)", "plain, comma", 2019, null]'
                     '.map(csvCell)')
        self.assertEqual(got, ["'=HYPERLINK(1)", "'+1", "'-x", "'@SUM(A1)", '"plain, comma"', "2019", ""])

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_lab_lines_stronger_than_cross_lab_lines(self):
        # Spec: lab edges solid, collaboration edges faint. Tokens from faint to strong.
        prelude = ('const S = {focus: null, highlight: null}; function css(n) { return n; } '
                   'function isLit() { return true; } function hexA(c) { return c; }')
        got = run_js(["linkColor"], prelude,
                     '["labmember", "collab"].map((type) => linkColor({type, source: "a", target: "b"}))')
        strength = ["--hair", "--axis", "--muted", "--ink-2", "--ink"]
        self.assertGreater(strength.index(got[0]), strength.index(got[1]), got)

    def test_stale_rule_shown_with_its_cutoff_year(self):
        # "No paper in the last 2 years" misstates the rule, which counts from a
        # calendar year (2024 or later, in 2026); the page prints that year.
        self.assertNotIn('in the last " + th.staleYears', TEMPLATE)
        self.assertIn("th.staleFrom", TEMPLATE)

    def test_overview_counts_are_links(self):
        overview = page_function("overview")
        for label in ("Labs (2+ papers)", "Gaps"):
            row = re.search(rf'\["{re.escape(label)}", (.*?)\]', overview).group(1)
            self.assertTrue(row.startswith(('el("button"', "countBtn(")), f"{label}: {row[:60]}")

    def test_selecting_never_moves_the_camera(self):
        # Researcher, 2026-10-24: a click that zooms on its own is not user friendly.
        # Single click selects; the camera moves only on double-click, the toolbar,
        # or the panel's "Zoom to it" button.
        for name in ("select", "highlightSet"):
            body = page_function(name)
            self.assertNotIn("cameraPosition", body, name)
            self.assertNotIn("zoomToFit", body, name)
            self.assertNotIn("zoomToHighlight()", body, name)

    def test_navigation_toolbar_present(self):
        for region in ("navtools", "nav-grip", "nav-zoom-in", "nav-zoom-out", "nav-fit",
                       "nav-rotate", "nav-pan"):
            self.assertRegex(TEMPLATE, rf'id="{region}"', region)
        keys = page_function("onKey")
        for key in ('"+"', '"="', '"-"', '"0"', '"h"'):
            self.assertIn(key, keys, key)

    def test_zoom_buttons_are_magnifying_glasses(self):
        # Researcher, 2026-10-24: a magnifying glass (with + or -) for zoom in and out.
        for button, label in (("nav-zoom-in", "Zoom in"), ("nav-zoom-out", "Zoom out")):
            m = re.search(rf'<button id="{button}"[^>]*>(.*?)</button>', TEMPLATE, re.S)
            self.assertIsNotNone(m, button)
            tag = re.search(rf'<button id="{button}"[^>]*>', TEMPLATE).group(0)
            self.assertIn(f'aria-label="{label}"', tag)
            self.assertIn("<svg", m.group(1), button)
            self.assertIn("<circle", m.group(1), button)  # the lens
            self.assertIn('aria-hidden="true"', m.group(1), button)

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_overview_names_filters_it_cannot_show(self):
        # Clarity: the Overview never hides something that is shaping the picture.
        base = '{sets: {}, yearMin: null, yearMax: null, undated: true, newOnly: false, offTopic: false}'
        got = run_js(["exploreOnlyFilters"], "", f"""[
          exploreOnlyFilters({base}),
          exploreOnlyFilters(Object.assign({base}, {{sets: {{interest: new Set(["XR"]), type: new Set(["Paper"])}}}})),
          exploreOnlyFilters(Object.assign({base}, {{sets: {{status: new Set(["Used in a report"])}}, yearMin: 2020, newOnly: true}}))]""")
        self.assertEqual(got[0], [])
        self.assertEqual(got[1], [])  # interest and kind are shown on the Overview itself
        self.assertEqual(got[2], ["Status", "Publication year"])  # and so is "only new"

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
    def test_explore_is_fitted_only_when_shown(self):
        # Fitting the camera while Explore was hidden measured an empty graph and left
        # it off-centre; the fit waits until the tab is shown.
        prelude = ('let FIT_PENDING = true; const S = {tab: "overview"}; '
                   'const G = {getGraphBbox() { throw new Error("measured while hidden"); }};')
        self.assertTrue(run_js(["fitCamera"], prelude, "(fitCamera(), FIT_PENDING)"))
        self.assertIn("if (FIT_PENDING) setTimeout(fitCamera", page_function("setTab"))

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_hidden_explore_does_no_graph_work(self):
        # At 20,000 items, laying out Explore's 3D graph behind the Overview held the
        # first globe frame back by six seconds. Explore's work waits until it is shown.
        got = run_js(["deferExplore"], 'let EXPLORE_DIRTY = false; const S = {tab: "overview"};',
                     '[deferExplore(), EXPLORE_DIRTY, (S.tab = "explore", deferExplore())]')
        self.assertEqual(got, [True, True, False])
        for name in ("setView", "refreshData"):
            self.assertIn("deferExplore()", page_function(name), name)
        self.assertIn("EXPLORE_DIRTY", page_function("setTab"))

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_blocked_storage_is_not_an_error(self):
        prelude = ('const localStorage = {getItem() { throw new Error("blocked"); }, '
                   'setItem() { throw new Error("blocked"); }};')
        store = re.search(r"^const store = \{.*?^\};$", PAGE_SOURCE, re.S | re.M)
        self.assertIsNotNone(store, "const store not found")
        got = run_js([], prelude + "\n" + store.group(0), '[store.get("x"), store.set("x", "1")]')
        self.assertEqual(got, [None, None])
        # Every storage access goes through store.
        self.assertNotRegex(PAGE_SOURCE.replace(store.group(0), ""), r"localStorage\.")

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_unticked_interest_hides_its_hubs(self):
        prelude = 'const S = {filters: {sets: {interest: new Set(["XR"])}}};'
        got = run_js(["hubShown"], prelude, '[hubShown({type: "interest", label: "XR"}), '
                     'hubShown({type: "subarea", interest: "AI"}), hubShown({type: "subarea", interest: "XR"}), '
                     'hubShown({type: "report"})]')
        self.assertEqual(got, [True, False, True, True])

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_focus_drops_when_filtered_out(self):
        # A focused node that a filter hides left every visible node dimmed.
        got = run_js(["focusStillShown"], "", '[focusStillShown("a", [{id: "a"}, {id: "b"}]), '
                     'focusStillShown("z", [{id: "a"}]), focusStillShown(null, [])]')
        self.assertEqual(got, [True, False, True])
        for name in ("refreshData", "setView", "select"):
            self.assertIn("focusStillShown(", page_function(name), name)

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_long_names_are_shortened_on_the_graph(self):
        # Researcher, 2026-10-24: less text on the graph. Full names stay in the
        # hover tooltip and the card.
        got = run_js(["shortLabel"], "", '[shortLabel("Control / monitoring"), '
                     'shortLabel("XR/Immersive Systems Security & Privacy: not yet labelled"), '
                     'shortLabel("Supercalifragilisticexpialidocious-and-then-some-more-letters")]')
        self.assertEqual(got[0], "Control / monitoring")
        self.assertTrue(got[1].endswith("…") and len(got[1]) <= 33, got[1])
        self.assertFalse(got[1][:-1].endswith(" "), got[1])  # cut at a word, no dangling space
        self.assertTrue(got[2].endswith("…") and len(got[2]) <= 33, got[2])

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_graph_labels_stay_distinct_when_shortened(self):
        # Shortening made an interest hub and its "not yet labelled" and "fits no
        # listed sub-area" hubs all read "XR/Immersive Systems Security…".
        interest = "XR/Immersive Systems Security & Privacy"
        got = run_js(["graphLabel", "shortLabel"], "", f"""[
          graphLabel({{type: "interest", label: "{interest}"}}),
          graphLabel({{type: "subarea", kind: "unlabelled", label: "{interest}: not yet labelled"}}),
          graphLabel({{type: "subarea", kind: "unassigned", label: "{interest}: fits no listed sub-area"}}),
          graphLabel({{type: "subarea", kind: "stale", label: "{interest}: unassigned (label no longer in profile)"}}),
          graphLabel({{type: "subarea", kind: "profile", label: "Eye-tracking privacy & differential privacy"}}),
          graphLabel({{type: "paper", title: "A paper", label: "A paper"}})]""")
        self.assertEqual(len(set(got[:4])), 4, got)
        self.assertEqual(got[1:4], ["Not yet labelled", "Fits no listed sub-area", "Label not in profile"])
        self.assertEqual(got[5], "A paper")

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_hub_labels_appear_when_close_or_focused(self):
        prelude = 'const S = {focus: null}; let FOCUS_NEIGHBOURS = new Set();'
        got = run_js(["labelVisible"], prelude, """[
          labelVisible({id: "i", type: "interest"}, 5000),
          labelVisible({id: "s", type: "subarea"}, 5000),
          labelVisible({id: "s", type: "subarea"}, 200),
          labelVisible({id: "r", type: "report"}, 5000),
          labelVisible({id: "y", type: "year"}, 5000),
          labelVisible({id: "p", type: "paper"}, 100),
          (() => { S.focus = "s"; return labelVisible({id: "s", type: "subarea"}, 5000); })(),
          (() => { S.focus = "p"; FOCUS_NEIGHBOURS = new Set(["s"]); return labelVisible({id: "s", type: "subarea"}, 5000); })(),
          labelVisible({id: "p", type: "paper"}, 5000)]""")
        self.assertEqual(got, [True, False, True, False, True, False, True, True, True])
        # Interest names stay readable at any zoom: a constant on-screen size.
        self.assertIn("sizeAttenuation: !fixed", page_function("textSprite"))
        self.assertIn('n.type === "interest" ? 34 : 26, n.type === "interest")', page_function("buildObject"))

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_double_click_detection(self):
        got = run_js(["clickKind"], "", """(() => {
          const a = clickKind(null, "n1", 1000);
          const b = clickKind(a.last, "n1", 1250);         // same node, quick: double
          const c = clickKind(b.last, "n1", 1400);         // third click starts afresh
          const d = clickKind(c.last, "n2", 1500);         // other node: single
          const e = clickKind(d.last, "n2", 2000);         // too slow: single
          return [a.double, b.double, c.double, d.double, e.double];
        })()""")
        self.assertEqual(got, [False, True, False, False, False])

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_zoom_step_moves_along_the_view_line(self):
        got = run_js(["zoomStep"], "", '[zoomStep({x: 0, y: 0, z: 100}, {x: 0, y: 0, z: 0}, 0.5), '
                     'zoomStep({x: 10, y: 0, z: 0}, {x: 0, y: 0, z: 0}, 2)]')
        self.assertEqual(got, [{"x": 0, "y": 0, "z": 50}, {"x": 20, "y": 0, "z": 0}])

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_toolbar_stays_inside_the_graph(self):
        got = run_js(["clampToolbar"], "", '[clampToolbar(-50, 900, 200, 40, 800, 600), '
                     'clampToolbar(100, 100, 200, 40, 800, 600), clampToolbar(700, 10, 200, 40, 800, 600)]')
        self.assertEqual(got, [{"x": 4, "y": 556}, {"x": 100, "y": 100}, {"x": 596, "y": 10}])

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_shortlist_rule(self):
        got = run_js(["shortlisted"], "", "[shortlisted({verdict: 'Core'}), shortlisted({verdict: 'Supporting'}), "
                     "shortlisted({verdict: null}), shortlisted({verdict: 'Peripheral'}), "
                     "shortlisted({verdict: 'Excluded'}), shortlisted({type: 'web', tier: 'Peripheral'}), "
                     "shortlisted({type: 'web', tier: 'Core'})]")
        self.assertEqual(got, [True, True, True, False, False, False, True])
        self.assertIn("shortlisted(", page_function("passes"))

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

    def test_line_colours_are_not_interest_colours(self):
        # Amber and blue lines must never be mistaken for an interest's colour.
        root = re.search(r":root \{(.*?)\n\}", TEMPLATE, re.S).group(1)
        dark = re.search(r"prefers-color-scheme: dark\).*?\{(.*?)\n  \}", TEMPLATE, re.S).group(1)
        forced = re.search(r':root\[data-theme="dark"\] \{(.*?)\n\}', TEMPLATE, re.S).group(1)
        for block in (root, dark, forced):
            tokens = dict(re.findall(r"--([\w-]+):\s*(#[0-9a-fA-F]{6})", block))
            interest = {tokens[f"i{i}"].lower() for i in range(1, 7)}
            self.assertNotIn(tokens["cites"].lower(), interest)
            self.assertNotIn(tokens["citedby"].lower(), interest)
            self.assertNotEqual(tokens["cites"], tokens["citedby"])

    def test_globe_regions_present(self):
        for region in ("globe", "globe-nav", "gnav-grip", "gnav-zoom-in", "gnav-zoom-out", "gnav-fit",
                       "gnav-rotate", "gnav-pan"):
            self.assertRegex(TEMPLATE, rf'id="{region}"', region)
        self.assertIn("TAB_HOOKS.overview", PAGE_SOURCE)
        self.assertIn("ON_FILTERS.push(globeRefresh)", PAGE_SOURCE)
        # Showing the Overview refreshes what is visible: the start-up shows the tab before
        # it has worked out the filters, which once left the globe empty.
        hook = re.search(r"^TAB_HOOKS\.overview = .*$", (PARTS / "globe.js").read_text(), re.M).group(0)
        self.assertIn("globeRefresh()", hook)

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

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_card_chips(self):
        got = run_js(["cardChip"], "", "[cardChip('On your map', 325), cardChip('Selected', null, "
                     "'A rather long paper title that goes on and on'), cardChip('Legend')]")
        self.assertEqual(got, ["▸ On your map · 325", "▸ Selected: A rather long paper title…", "▸ Legend"])

    def test_null_never_reaches_the_page(self):
        # replaceChildren(null) writes the word "null": cards and the hover label once did.
        self.assertIn("body.filter((x) => x != null)", page_function("cardFrame"))
        self.assertNotIn(": null", page_function("globeTip"))

    def test_overview_regions_and_phone_width(self):
        for region in ("mapcard", "selcard", "ringkey", "globe-tip", "globe-legend", "globe-notice",
                       "highlight-chip"):
            self.assertRegex(TEMPLATE, rf'id="{region}"', region)
        # On a phone-width screen the cards start as chips, so the globe is visible.
        self.assertIn('matchMedia("(max-width: 600px)")', PAGE_SOURCE)
        self.assertIn("Nothing in your library yet. Run /research to start.", PAGE_SOURCE)
        # A card for an item the filters hide says so, rather than pointing at nothing.
        self.assertIn("Hidden by the current filters.", page_function("renderSelCard"))
        self.assertIn("selcard", page_function("renderSelCard"))

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_schema_counts(self):
        # "Uncategorized" and the "no sub-area" hubs are placeholders, not interests or sub-areas.
        d = ('{nodes: [{type:"interest", label:"XR"},{type:"interest", label:"Uncategorized"},'
             '{type:"subarea", id:"subarea:XR:Gaze"},{type:"subarea", id:"subarea:XR:Auth"},'
             '{type:"subarea", id:"subarea:XR:__unlabelled"},{type:"subarea", id:"subarea:XR:__stale"},'
             '{type:"paper"},{type:"web"},'
             '{type:"report"},{type:"gap"}], edges: [{type:"cites"},{type:"cites"},{type:"subarea"}], '
             'labs: [{papers:[1,2]},{papers:[3]}]}')
        got = run_js(["schemaCounts"], "", f"schemaCounts({d})")
        self.assertEqual(got, {"interests": 1, "subareas": 2, "papers": 1, "web": 1, "groups": 1,
                               "reports": 1, "gaps": 1, "cites": 2})

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_status_rows_pair_problems_with_fixes(self):
        d = ('{meta: {built: "2026-10-31", newSince: "2026-10-24", warnings: ["report r2 could not be read"], '
             'coverage: {found: 291, notFound: 2, mismatch: 5, noId: 3, notFetched: 0}, '
             'labels: {notLabelled: 71, fitsNone: 59, stale: 0, noContribution: 4}, counts: {}}, '
             'edges: [{type: "cites"}, {type: "subarea"}]}')
        rows = run_js(["statusRows"], "", f"statusRows({d}, {{shown: 325, shortlist: 38, offTopic: 51, other: 0}})")
        by = {r["label"]: r for r in rows}
        self.assertEqual(by["Last built"]["value"], "2026-10-31")
        self.assertIn("325 shown", by["Items"]["value"])
        self.assertIn("38 by the shortlist", by["Items"]["value"])
        self.assertIn("python3 tools/knowledge_graph.py --enrich", by["OpenAlex coverage"]["fix"])
        self.assertIn("python3 tools/state.py subareas", by["Sub-area labels"]["fix"])
        self.assertEqual(by["Citation links"]["value"], "1")
        self.assertIn("report r2 could not be read", by["Warnings from the build"]["value"])
        self.assertTrue(all(r["fix"] for r in rows if r["problem"]))
        self.assertFalse(by["Last built"]["problem"])

    def test_connects_and_status_regions(self):
        self.assertIn("TAB_HOOKS.connects", PAGE_SOURCE)
        self.assertIn("TAB_HOOKS.status", PAGE_SOURCE)
        self.assertIn("function svgEl(", TEMPLATE)

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
        q = lambda text: f"parseQuestion({json.dumps(text)}, {ctx})"
        got = run_js(["parseQuestion", "askExamples"], prelude, "[" + ", ".join(q(t) for t in [
            "attack papers in XR since 2024 with no defence",
            "papers from the same lab as Heimdall",
            "what cites the Unique Identification paper?",
            "thin sub-areas",
            "new since my last search",
            "what is the meaning of life",
            "scored but never used in a report",
            "papers about cooking"]) + "]")
        self.assertEqual(got[0]["ids"], ["p2"])
        self.assertEqual(sorted(got[1]["ids"]), ["p1", "p3"])
        self.assertEqual(got[2]["ids"], ["p1"])
        self.assertEqual(got[3]["ids"], ["p1"])
        self.assertEqual(sorted(got[4]["ids"]), ["p1", "w1"])
        self.assertFalse(got[5]["ok"])
        self.assertTrue(got[5]["closest"])
        self.assertTrue(got[6]["ok"])
        self.assertTrue(all(g["ok"] and g["steps"] for g in got[:5]))
        self.assertIn("Interest: XR Security", got[0]["steps"])
        # A word the patterns cannot read makes the question unsupported; ignoring it
        # would answer a different question ("all papers").
        self.assertFalse(got[7]["ok"])
        self.assertIn("cooking", got[7]["message"])

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_ask_examples_come_from_the_library(self):
        # Profile-agnostic: the examples are written from the library, never hard-coded,
        # and each one is a question the patterns answer.
        for word in ("Heimdall", "Unique Identification", "XR "):
            self.assertNotIn(word, (PARTS / "ask.js").read_text(), word)
        ctx = """{since: "2026-10-01", interests: [{name: "Gaze Privacy"}], gaps: [], labs: [{id: "L1", name: "Lab", papers: ["a", "b"]}],
          items: [{id: "a", type: "paper", title: "Eye movements leak identity", interest: "Gaze Privacy", year: 2025,
                   contribution: "attack", subareas: [], primaryLab: "L1", citesOut: ["b"]},
                  {id: "b", type: "paper", title: "Blink patterns as biometrics", interest: "Gaze Privacy", year: 2023,
                   contribution: "measurement", subareas: [], primaryLab: "L1", citesOut: []}]}"""
        prelude = "function passes() { return true; } function isNew() { return false; } const S = {};"
        got = run_js(["parseQuestion", "askExamples"], prelude,
                     f"(() => {{ const c = {ctx}; return askExamples(c).map((q) => [q, parseQuestion(q, c).ok]); }})()")
        self.assertEqual(len(got), 6)
        self.assertTrue(all(ok for _, ok in got), got)

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_ask_hides_what_the_map_hides(self):
        ctx = """{since: "2026-10-01", interests: [{name: "XR Security"}], gaps: [], labs: [],
          items: [{id: "a", type: "paper", title: "One", interest: "XR Security", contribution: "attack", citesOut: []},
                  {id: "b", type: "paper", title: "Two", interest: "XR Security", contribution: "attack", citesOut: []}]}"""
        prelude = ("function passes(n) { return n.id !== 'b'; } function isNew() { return false; } "
                   "const S = {since: '2026-10-01'};")
        got = run_js(["parseQuestion", "askExamples"], prelude, f"parseQuestion('attack papers in XR', {ctx})")
        self.assertEqual(got["ids"], ["a"])
        self.assertEqual(got["steps"][-1], "1 more is hidden by the current filters")

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_escape_on_the_overview_clears_its_selection(self):
        # Esc reached Explore's clearFocus, which nulled the state but left the Overview's
        # card, highlight chip and dimmed globe standing; with Explore's list open it
        # closed the hidden list instead.
        prelude = ('const document = {activeElement: {tagName: "BODY", blur() {}}}; let called = []; '
                   'function globeClear() { called.push("globe"); } function closeList() { called.push("list"); } '
                   'function clearFocus() { called.push("focus"); } function toggleMinimiseAll() {}')
        got = run_js(["onKey"], prelude, """[
          (S0 => { globalThis.S = S0; called = []; onKey({key: "Escape"}); return called; })({tab: "overview", current: "p", highlight: null, listOpen: true}),
          (S0 => { globalThis.S = S0; called = []; onKey({key: "Escape"}); return called; })({tab: "overview", current: null, highlight: null, listOpen: true}),
          (S0 => { globalThis.S = S0; called = []; onKey({key: "Escape"}); return called; })({tab: "explore", current: "p", highlight: null, listOpen: true})]""")
        self.assertEqual(got, [["globe"], [], ["list"]])

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_lineage_is_fast_at_scale(self):
        # Clicking a paper on the globe built Explore's lineage, which rebuilt the citation
        # maps and walked them with queue.shift(): 1-4 s at 20,000 items.
        # 20,000 papers each citing up to six others at random, like --synthetic 20000.
        prelude = ('let seed = 7; const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647; const edges = []; '
                   'for (let i = 0; i < 20000; i++) { const k = Math.floor(rnd() * 7); for (let j = 0; j < k; j++) '
                   'edges.push({type: "cites", source: "p" + i, target: "p" + Math.floor(rnd() * 20000)}); } '
                   'const D = {edges}; let CITE_MAPS = null;')
        names = ["lineageOf"] + (["citeMaps"] if "function citeMaps(" in PAGE_SOURCE else [])
        got = run_js(names, prelude, "(() => { lineageOf('p1'); const t = Date.now(); "
                     "const r = [2, 3, 10].map((k) => lineageOf('p' + k).ancestors.length); return [r[0] > 1000, (Date.now() - t) / 3]; })()")
        self.assertTrue(got[0])
        self.assertLess(got[1], 60, "a lineage took %d ms" % got[1])
        # And none of it runs while Explore is hidden.
        self.assertIn("deferExplore()", page_function("select"))
        self.assertIn("renderDetail(S.current)", page_function("setTab"))

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_show_on_map_says_what_will_show(self):
        got = run_js(["showOnMapLabel"], "", "[showOnMapLabel(1038, 2000), showOnMapLabel(358, 358), showOnMapLabel(1, 3)]")
        self.assertEqual(got[0], {"label": "Show 1,038 on the map",
                                  "note": "962 of the 2,000 are hidden by the current filters, such as the shortlist."})
        self.assertEqual(got[1], {"label": "Show all 358 on the map", "note": ""})
        self.assertEqual(got[2]["note"], "2 of the 3 are hidden by the current filters, such as the shortlist.")

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_selection_dims_everything_else(self):
        # Spec: click a dot, its citation arcs light up, everything else dims.
        prelude = "const OUT = [[1], [], [], []], INN = [[], [0], [], []];"
        got = run_js(["globeLit"], prelude, "[0, 1, 2].map((i) => globeLit(i, 0, null, OUT, INN)).concat("
                     "[globeLit(2, null, null, OUT, INN), globeLit(2, null, (i) => i === 2, OUT, INN), globeLit(1, 0, (i) => i === 2, OUT, INN)])")
        self.assertEqual(got, [True, True, False, True, True, False])

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_highlight_count_is_what_shows(self):
        got = run_js(["highlightChipText"], "", "[highlightChipText('x', ['a', 'b', 'c'], new Set(['a'])), "
                     "highlightChipText('y', ['a', 'b'], new Set(['a', 'b']))]")
        self.assertEqual(got, ["Highlighted: x · 1 shown, 2 hidden by the filters", "Highlighted: y · 2"])

    def test_notice_never_covers_the_map_card(self):
        narrow = re.search(r"@media \(max-width: 900px\) \{\n(.*?)\n\}", TEMPLATE, re.S).group(1)
        rule = re.search(r"#globe-notice \{([^}]*)\}", narrow).group(1)
        self.assertNotIn("top:", rule.replace("top: auto", ""))
        # Nor do the card's long list and the legend run into each other: under 900 px the
        # card stops short of the bottom row and the legend starts as a chip.
        self.assertIn("max-height", re.search(r"#mapcard \{([^}]*)\}", narrow).group(1))
        self.assertIn('matchMedia("(max-width: 900px)")', page_function("renderOverview"))

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_ask_examples_answer_on_a_many_interest_library(self):
        # Interest names that share words ("Interest A", "Interest B") and titles that
        # share words ("Synthetic paper 1", ...) once made half the examples fail.
        ctx = """{since: "2026-10-01", interests: [{name: "Interest A"}, {name: "Interest B"}, {name: "AI Security"}, {name: "AI Ethics"}],
          gaps: [], labs: [{id: "L1", name: "Lab", papers: ["p1", "p2"]}],
          items: [1, 2, 3, 4].map((k) => ({id: "p" + k, type: "paper", title: "Synthetic paper " + k, interest: k < 3 ? "Interest A" : "Interest B",
            year: 2020 + k, contribution: "attack", subareas: [], primaryLab: k < 3 ? "L1" : null, citesOut: k === 1 ? ["p2"] : []}))}"""
        prelude = "function passes() { return true; } function isNew() { return false; } const S = {};"
        got = run_js(["parseQuestion", "askExamples"], prelude,
                     f"(() => {{ const c = {ctx}; return askExamples(c).map((q) => [q, parseQuestion(q, c).ok]); }})()")
        self.assertGreaterEqual(len(got), 3)
        self.assertTrue(all(ok for _, ok in got), got)

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_library_line_on_the_card(self):
        got = run_js(["libraryLine"], "", "[libraryLine(39, 23), libraryLine(1, 1), libraryLine(0, 0)]")
        self.assertEqual(got, ["39 research groups · 23 gaps", "1 research group · 1 gap", "0 research groups · 0 gaps"])
        self.assertIn("libraryLine(", page_function("renderMapCard"))

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_interest_counts_in_one_pass(self):
        # The card counted each interest with its own pass over every item: about 37 ms
        # at 20,000 items and 12 interests, on every keystroke in its search box.
        got = run_js(["interestCounts"], "function interestOf(n) { return n.interest || 'Uncategorized'; }",
                     "(() => { let calls = 0; const items = [{interest: 'A', ok: 1}, {interest: 'A', ok: 0}, {interest: 'B', ok: 1}, {ok: 1}]; "
                     "const c = interestCounts(items, (n) => { calls++; return n.ok; }); return [c, calls]; })()")
        self.assertEqual(got, [{"A": 1, "B": 1, "Uncategorized": 1}, 4])
        self.assertIn("interestCounts(", page_function("renderMapCard"))
        self.assertNotRegex(page_function("renderMapCard"), r"ITEMS\.filter\(\(n\) => interestOf\(n\) === name")

    def test_start_up_draws_only_the_tab_it_opens(self):
        # The start-up ran the Overview's hook (building the globe) before it knew which
        # tab the address asked for.
        start = TEMPLATE.split("/* ---------- start: after the parts", 1)[1].split("</script>", 1)[0]
        self.assertNotIn("applyMin(", start)
        self.assertIn('classList.toggle("tabs-min"', start)

    def test_dark_mode_uses_the_prototype_colours(self):
        # Researcher, 2026-10-31: "I like the way the prototype looked in terms of the
        # lines and dots colors". Dark is the reference look.
        forced = re.search(r':root\[data-theme="dark"\] \{(.*?)\n\}', TEMPLATE, re.S).group(1)
        tokens = dict(re.findall(r"--([\w-]+):\s*(#[0-9a-fA-F]{6})", forced))
        self.assertEqual([tokens[f"i{k}"].lower() for k in range(1, 7)],
                         ["#3987e5", "#e07a3c", "#21b07d", "#d44fa0", "#c9b037", "#8b80f5"])
        self.assertEqual((tokens["cites"].lower(), tokens["citedby"].lower()), ("#ffb040", "#5ac8ff"))
        self.assertEqual(re.search(r"const SLOT_TOKENS = \[(.*?)\];", PAGE_SOURCE).group(1),
                         '"--i1", "--i2", "--i3", "--i4", "--i5", "--i6"')

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_dark_is_the_default_theme(self):
        got = run_js(["initialTheme"], "", '[initialTheme(null), initialTheme("light"), initialTheme("dark"), initialTheme("bogus")]')
        self.assertEqual(got, ["dark", "light", "dark", "dark"])
        self.assertRegex(TEMPLATE, r'id="theme-toggle"')
        # The theme is set before Explore's renderer reads its background colour.
        self.assertLess(TEMPLATE.index("initialTheme(store.get"), TEMPLATE.index("const G = ForceGraph3D"))

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_m_restores_when_every_shown_card_is_minimised(self):
        # The selection card counted as open while it had never been shown, so the first
        # M after minimising the visible cards minimised again: nothing happened.
        prelude = ('const MIN_CARDS = ["mapcard", "selcard", "globe-legend"]; let saved = false; '
                   'const document = {getElementById: (id) => ({hidden: id === "selcard"})}; '
                   'function applyMin() { saved = true; } '
                   'const S = {min: {tabs: true, cards: {mapcard: true, "globe-legend": true}}};')
        got = run_js(["toggleMinimiseAll"], prelude, "(toggleMinimiseAll(), [S.min.tabs, S.min.cards.mapcard, saved])")
        self.assertEqual(got, [False, False, True])

    def test_no_duplicated_decorators(self):
        lines = (REPO_ROOT / "tests" / "test_graph_template.py").read_text().splitlines()
        dupes = [i + 1 for i in range(1, len(lines)) if lines[i].strip().startswith("@") and lines[i] == lines[i - 1]]
        self.assertEqual(dupes, [])

    def test_page_script_parses(self):
        script = TEMPLATE.split("<script>", 1)[1].split("</script>", 1)[0]
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
            f.write(script)
        try:
            result = subprocess.run(["node", "--check", f.name], capture_output=True, text=True)
        finally:
            Path(f.name).unlink()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_every_part_parses(self):
        self.assertEqual(PART_NAMES, ["globe.js", "overview.js", "connects.js", "ask.js", "status.js"])
        for name in PART_NAMES:
            code = (PARTS / name).read_text()
            r = subprocess.run(["node", "--check", "-"], input=code, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, f"{name}: {r.stderr}")

    def test_data_strings_never_reach_innerhtml(self):
        # Titles and abstracts are untrusted. The page builds DOM with textContent
        # (el()); the only HTML string it builds is the hover label, and that
        # passes every data string through esc().
        self.assertNotRegex(PAGE_SOURCE, r"\.innerHTML\s*=(?!=)")
        hover = TEMPLATE.split("function hoverLabel", 1)[1].split("\n}\n", 1)[0]
        for field in ("title", "kind", "bits"):
            self.assertRegex(hover, rf"esc\({field}", field)



@unittest.skipUnless(shutil.which("node"), "node not installed")
class GlobeMathTests(unittest.TestCase):
    """The globe's positions carry meaning, so its maths are pinned here; the drawing
    is checked in a real browser."""

    def js(self, names, expr, prelude=""):
        return run_js(["hash01", "yearLat", "bands", "clusterKey", "clusterName", "buildGlobe",
                       "rotation", "project", "pickDots", "clusterStats", "zoomBlend",
                       "flyTarget", "yearMarks", "arcPath", "placeLabels"] + names,
                      "const MIN_BAND_DEG = 8, DOT_CAP = 2500;" + prelude, expr)

    def test_hash_spreads_ids_that_differ_at_the_end(self):
        # Library keys often differ only in their last characters (10.1000/x.1, .2, ...);
        # a weak hash bunched those items together on the globe.
        got = self.js([], "(() => { const h = Array.from({length: 200}, (_, i) => hash01('paper:10.1000/x.' + i)); "
                      "const q = [0, 0, 0, 0]; h.forEach((v) => q[Math.floor(v * 4)]++); return q; })()")
        self.assertTrue(all(30 <= c <= 70 for c in got), got)

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
        self.assertEqual(got[0][0]["start"], 0)
        self.assertEqual(got[1], [])
        self.assertAlmostEqual(got[2][0]["width"], 7.2, places=6)  # 50 x 8 > 360: equal shares

    def test_cluster_keys(self):
        subs = "['Side channels', 'Auth']"
        got = self.js([], f"[clusterKey({{interest: 'X', subareas: ['Auth', 'Side channels']}}, {subs}), "
                      f"clusterKey({{interest: 'X', subareas: null}}, {subs}), "
                      f"clusterKey({{interest: 'X', subareas: []}}, {subs}), "
                      f"clusterKey({{interest: 'X', subareas: ['Gone']}}, {subs}), "
                      f"clusterName('X::__unlabelled'), clusterName('X::Auth'), clusterName('X::__none')]")
        self.assertEqual(got, ["X::Auth", "X::__unlabelled", "X::__none", "X::__none",
                               "Not yet labelled", "Auth", "Fits no listed sub-area"])

    def test_empty_library(self):
        got = self.js([], "(() => { const m = buildGlobe([], [], {}); "
                      "return [m.n, m.bands.length, pickDots(m, new Uint8Array(0), rotation(0, 0), "
                      "() => true, 10).inView, clusterStats(m, new Uint8Array(0), new Uint8Array(0)).length]; })()")
        self.assertEqual(got, [0, 0, 0, 0])

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

    def test_items_stay_inside_their_interest_band(self):
        got = self.js([], "(() => { const items = Array.from({length: 300}, (_, i) => ({id: 'p' + i, "
                      "interest: ['A', 'B', 'C'][i % 3], year: 2000 + i % 27, subareas: [['s', 't', null][i % 3]].filter(Boolean), score: i})); "
                      "const m = buildGlobe(items, ['A', 'B', 'C'], {A: ['s', 't'], B: ['s'], C: []}); "
                      "return [...Array(m.n).keys()].every((i) => { const b = m.bands[m.interest[i]]; "
                      "let lon = Math.atan2(m.vz[i], m.vx[i]) * 180 / Math.PI; if (lon < 0) lon += 360; "
                      "return lon >= b.start - 1e-6 && lon <= b.start + b.width + 1e-6; }); })()")
        self.assertTrue(got)

    def test_pick_dots_caps_by_priority_and_counts_everything(self):
        got = self.js([], "(() => { const items = Array.from({length: 50}, (_, i) => "
                      "({id: 'p' + i, interest: 'A', year: 2020, subareas: [], score: i})); "
                      "const m = buildGlobe(items, ['A'], {A: []}); const mask = new Uint8Array(50).fill(1); "
                      "const r = pickDots(m, mask, rotation(0, 0), () => true, 5); "
                      "const front = [...Array(50).keys()].filter((i) => project(rotation(0, 0), m.vx[i], m.vy[i], m.vz[i])[2] > 0.02); "
                      "const top5 = front.sort((a, b) => items[b].score - items[a].score).slice(0, 5); "
                      "return [r.drawn.length, r.inView === front.length, JSON.stringify(r.drawn) === JSON.stringify(top5)]; })()")
        self.assertEqual(got, [5, True, True])  # the five highest scored in view, in that order

    def test_cluster_stats_count_and_new(self):
        got = self.js([], "(() => { const items = [{id: 'a', interest: 'A', year: 2020, subareas: ['s']}, "
                      "{id: 'b', interest: 'A', year: 2021, subareas: ['s']}, {id: 'c', interest: 'A', year: 2021, subareas: null}]; "
                      "const m = buildGlobe(items, ['A'], {A: ['s']}); "
                      "const st = clusterStats(m, Uint8Array.from([1, 1, 0]), Uint8Array.from([0, 1, 1])); "
                      "return m.clusters.map((c, k) => [c.name, st[k].count, st[k].fresh, Math.round(Math.hypot(st[k].x, st[k].y, st[k].z) * 1000) / 1000]); })()")
        self.assertEqual(got, [["s", 2, 1, 1], ["Not yet labelled", 0, 0, 0]])

    def test_zoom_blend(self):
        got = self.js([], "[zoomBlend(1), zoomBlend(2), zoomBlend(3)]")
        self.assertEqual(got[0], {"regions": 1, "dots": 0})
        self.assertGreater(got[1]["regions"], 0)
        self.assertGreater(got[1]["dots"], 0)
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

    def test_arc_path_runs_end_to_end_above_the_surface(self):
        got = self.js([], "(() => { const p = arcPath([1, 0, 0], [0, 0, 1], 10); "
                      "return [p.length, p[0], p[10].map((v) => Math.round(v * 1e6) / 1e6), Math.hypot(...p[5]) > 1]; })()")
        self.assertEqual(got, [11, [1, 0, 0], [0, 0, 1], True])

    def test_the_globe_turns_a_full_circle_both_ways(self):
        # Researcher, 2026-10-31: "i cant seem to rotate it 360 fully". Dragging up and
        # down stopped at about 80 degrees; it now rolls over the poles.
        got = self.js(["dragRotate", "wrapAngle"], "(() => { let v = {yaw: 0, pitch: 0}; const steps = [];"
                      " for (let k = 0; k < 400; k++) { v = dragRotate(v.yaw, v.pitch, 0, 10, 1); steps.push(v.pitch); }"
                      " const maxP = Math.max(...steps), minP = Math.min(...steps);"
                      " const up = dragRotate(0, 0, 10, 0, 1), flipped = dragRotate(0, Math.PI, 10, 0, 1);"
                      " return [maxP > 3.1, minP < -3.1, steps.every((p) => p > -Math.PI - 1e-9 && p <= Math.PI + 1e-9),"
                      " Math.sign(up.yaw) === -Math.sign(flipped.yaw)]; })()")
        # past the pole and all the way round, kept within one turn, and left-right
        # dragging still follows the hand when the globe is upside down
        self.assertEqual(got, [True, True, True, True])

    def test_labels_never_overlap_and_big_ones_win(self):
        got = self.js([], "placeLabels([{text: 's', x: 10, y: 10, w: 40, h: 14, priority: 5, big: false}, "
                      "{text: 'B', x: 20, y: 12, w: 60, h: 18, priority: 1e9, big: true}, "
                      "{text: 't', x: 200, y: 10, w: 40, h: 14, priority: 4, big: false}], 1).map((c) => c.text)")
        self.assertEqual(got, ["B", "t"])


if __name__ == "__main__":
    unittest.main()
