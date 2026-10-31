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
          {source: "e", target: "x", type: "cites"}, {source: "a", target: "h", type: "subarea"}]};"""
        got = run_js(["lineageOf"], prelude, 'lineageOf("d")')
        self.assertEqual(sorted(got["up"]), ["a"])
        self.assertEqual(got["down"], [])
        self.assertEqual(sorted(got["ancestors"]), ["a", "b", "c"])
        self.assertEqual(got["descendants"], [])
        got = run_js(["lineageOf"], prelude, 'lineageOf("b")')
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

    def test_labels_never_overlap_and_big_ones_win(self):
        got = self.js([], "placeLabels([{text: 's', x: 10, y: 10, w: 40, h: 14, priority: 5, big: false}, "
                      "{text: 'B', x: 20, y: 12, w: 60, h: 18, priority: 1e9, big: true}, "
                      "{text: 't', x: 200, y: 10, w: 40, h: 14, priority: 4, big: false}], 1).map((c) => c.text)")
        self.assertEqual(got, ["B", "t"])


if __name__ == "__main__":
    unittest.main()
