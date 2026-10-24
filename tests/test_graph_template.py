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
VENDOR = REPO_ROOT / "graph" / "vendor"
EMPTY = {"meta": {"counts": {}, "summary": "", "newSince": "2026-10-21", "built": "2026-10-21",
                  "thresholds": {}}, "interests": [], "nodes": [], "edges": [], "gaps": [],
         "labs": []}


def page_function(name):
    """The source of one top-level function in the page script."""
    m = re.search(rf"^function {name}\(.*?^}}$", TEMPLATE, re.S | re.M)
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

    def test_simple_mode_regions_present(self):
        # Researcher, 2026-10-24: a minimal Simple interface as the default, with
        # Advanced holding the full controls.
        for region in ("simplekey", "nodecard", "ui-simple", "ui-advanced"):
            self.assertRegex(TEMPLATE, rf'id="{region}"', region)
        self.assertIn('body.simple', TEMPLATE)
        # On a phone-width screen the key starts folded, so the graph is visible.
        self.assertRegex(TEMPLATE, r'max-width: 600px\)"\)\.matches\) \$\("#simplekey"\)\.classList\.add\("collapsed"\)')

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_simple_is_the_default_mode(self):
        got = run_js(["initialUi"], "", '[initialUi(null, null), initialUi(null, "advanced"), '
                     'initialUi("simple", "advanced"), initialUi("advanced", null), initialUi("bogus", "nope")]')
        self.assertEqual(got, ["simple", "advanced", "simple", "advanced", "simple"])

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_simple_names_filters_it_cannot_show(self):
        # Clarity: Simple never hides something that is shaping the picture.
        base = '{sets: {}, yearMin: null, yearMax: null, undated: true, newOnly: false, offTopic: false}'
        got = run_js(["advancedOnlyFilters"], "", f"""[
          advancedOnlyFilters({base}),
          advancedOnlyFilters(Object.assign({base}, {{sets: {{interest: new Set(["XR"]), type: new Set(["Paper"])}}}})),
          advancedOnlyFilters(Object.assign({base}, {{sets: {{status: new Set(["Used in a report"])}}, yearMin: 2020, newOnly: true}}))]""")
        self.assertEqual(got[0], [])
        self.assertEqual(got[1], [])  # interest and kind are shown in Simple itself
        self.assertEqual(got[2], ["Status", "Publication year", "Only new items"])

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_unticked_interest_hides_its_hubs(self):
        prelude = 'const S = {filters: {sets: {interest: new Set(["XR"])}}};'
        got = run_js(["hubShown"], prelude, '[hubShown({type: "interest", label: "XR"}), '
                     'hubShown({type: "subarea", interest: "AI"}), hubShown({type: "subarea", interest: "XR"}), '
                     'hubShown({type: "report"})]')
        self.assertEqual(got, [True, False, True, True])

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_no_tooltip_over_the_open_card(self):
        # The hover tooltip repeated the title of the card already open beside it.
        prelude = ('const S = {ui: "simple", focus: "p1", since: "2026-01-01"}; function css() { return "#000"; } '
                   'function esc(s) { return String(s); } function isNew() { return false; } const KIND_NAMES = {};')
        got = run_js(["hoverLabel"], prelude, '[hoverLabel({id: "p1", type: "paper", title: "T"}), '
                     'hoverLabel({id: "p2", type: "paper", title: "U"}).includes("U")]')
        self.assertEqual(got, ["", True])

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_focus_drops_when_filtered_out(self):
        # A focused node that a filter hides left every visible node dimmed.
        got = run_js(["focusStillShown"], "", '[focusStillShown("a", [{id: "a"}, {id: "b"}]), '
                     'focusStillShown("z", [{id: "a"}]), focusStillShown(null, [])]')
        self.assertEqual(got, [True, False, True])
        for name in ("refreshData", "setView", "select"):
            self.assertIn("focusStillShown(", page_function(name), name)
        # A card for a node the filters hide says so, rather than pointing at nothing.
        self.assertIn("hidden by the current filters", page_function("renderNodeCard"))

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
    def test_page_script_parses(self):
        script = TEMPLATE.split("<script>", 1)[1].split("</script>", 1)[0]
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
            f.write(script)
        try:
            result = subprocess.run(["node", "--check", f.name], capture_output=True, text=True)
        finally:
            Path(f.name).unlink()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_data_strings_never_reach_innerhtml(self):
        # Titles and abstracts are untrusted. The page builds DOM with textContent
        # (el()); the only HTML string it builds is the hover label, and that
        # passes every data string through esc().
        self.assertNotRegex(TEMPLATE, r"\.innerHTML\s*=(?!=)")
        hover = TEMPLATE.split("function hoverLabel", 1)[1].split("\n}\n", 1)[0]
        for field in ("title", "kind", "bits"):
            self.assertRegex(hover, rf"esc\({field}", field)


if __name__ == "__main__":
    unittest.main()
