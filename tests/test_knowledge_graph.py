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

PROFILE = """# Researcher Profile

## Research Interests

### XR Security
- **Sub-areas of interest:**
  - Side channels
  - Auth (knowledge-based and biometric)
- **Known landmark works (if any):**
  - A Landmark Nobody Has Found (2019)

### Applied ML
- **Why tracked:** no sub-area list on purpose

## Depth Calibration
"""

HOSTILE = "</script><script>window.x=1</script> & \"quotes\" {braces} ünïcode"


def paper(**fields):
    base = {"title": "A Paper", "status": "ranked", "subject": "XR Security",
            "first_seen": "2026-10-01", "year": 2024, "url": "https://example.org/p",
            "authors": ["Ann Author"]}
    base.update(fields)
    return base


SOURCES = {
    "10.1000/a": paper(title=HOSTILE, status="synthesized", subareas=["Side channels"],
                       contribution="attack", verdict="Core", overall_score=80,
                       evidence_basis="fulltext", disclosure="academic"),
    "10.1000/b": paper(title="New and stale", subareas=["Retired Area"],
                       contribution="defence", first_seen="2026-10-20", year=2025),
    "10.1000/c": paper(title="Off topic", status="skipped"),
    "10.1000/d": paper(title="Unlabelled ML", subject="Applied ML", first_seen="2026-10-20",
                       year=None, authors=["Dee Different"]),
    "10.1000/e": paper(title="Could not fetch", status="unfetchable"),
    "10.1000/f": paper(title="Fits nothing listed", subareas=[], contribution="survey",
                       authors=["Fay Other"]),
}

WEB = {
    "https://blog.example.org/post": {
        "title": "A practitioner post", "site": "blog.example.org", "status": "included",
        "first_seen": "2026-10-15", "tier": "Supporting", "independence": "independent",
        "type": "engineering-blog", "interest": "XR Security", "subareas": ["Auth"],
        "date": "2026-09-01"},
    "https://ads.example.org/x": {"title": "An ad", "status": "excluded",
                                  "first_seen": "2026-10-15", "note": "marketing"},
}

SENIOR = {"name": "Sam Senior", "authorId": "https://openalex.org/A9", "position": "last",
          "institutions": [{"id": "https://openalex.org/I1", "name": "Uni A"}]}
CACHE = {"works": {
    "10.1000/a": {"openalex": "https://openalex.org/W1", "referenced": [], "error": None,
                  "fetched": "2026-10-21",
                  "authors": [{"name": "Ann Author", "authorId": "https://openalex.org/A1",
                               "position": "first", "institutions": []}, SENIOR]},
    "10.1000/b": {"openalex": "https://openalex.org/W2", "error": None, "fetched": "2026-10-21",
                  "referenced": ["https://openalex.org/W1", "https://openalex.org/W999"],
                  "authors": [{"name": "Bo Author", "authorId": "https://openalex.org/A2",
                               "position": "first", "institutions": []}, SENIOR]},
}}

REPORT = r"""\documentclass{article}
\title{A Report}
\begin{document}
\section{Side Channels}
Something \citep{a}.
\section{Open Questions and Gaps}
\begin{itemize}
  \item Does it hold? \citet{a}
\end{itemize}
\end{document}
"""
BIB = "@article{a, author={Author, Ann}, title={X}, year={2024}, doi={10.1000/a}}\n"


class GraphFixture(unittest.TestCase):
    """A temp repo tree with the graph tools, run as a subprocess the way the
    commands run them - the tools resolve every path from their own location."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        shutil.copytree(REPO_ROOT / "tools", self.root / "tools",
                        ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(REPO_ROOT / "graph", self.root / "graph",
                        ignore=shutil.ignore_patterns("index.html"))
        profile = self.root / ".claude" / "skills" / "research-assistant" / "01-researcher-profile.md"
        profile.parent.mkdir(parents=True)
        profile.write_text(PROFILE)
        self.write("research/seen_sources.json", {"seen": SOURCES})
        self.write("blog/seen_web_sources.json", {"seen": WEB})
        self.write("research/graph_cache.json", CACHE)
        (self.root / "reports" / "r1").mkdir(parents=True)
        (self.root / "reports" / "r1" / "report.tex").write_text(REPORT)
        (self.root / "reports" / "r1" / "references.bib").write_text(BIB)
        self.page = self.root / "graph" / "index.html"

    def write(self, rel, data):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data))

    def run_graph(self, *args):
        return subprocess.run([sys.executable, str(self.root / "tools" / "knowledge_graph.py"),
                               *args], capture_output=True, text=True)

    def build(self, *args):
        result = self.run_graph(*args)
        self.assertEqual(result.returncode, 0, result.stderr)
        return knowledge_graph.extract_data(self.page.read_text())

    def node(self, data, nid):
        return next(n for n in data["nodes"] if n["id"] == nid)


class BuildTests(GraphFixture):
    def test_titles_are_escaped_in_data_block(self):
        data = self.build()
        html = self.page.read_text()
        self.assertNotIn("<script>window.x", html)
        self.assertEqual(knowledge_graph.check(html), [])
        self.assertEqual(self.node(data, "paper:10.1000/a")["title"], HOSTILE)

    def test_builds_with_missing_inputs(self):
        shutil.rmtree(self.root / "reports")
        (self.root / "blog" / "seen_web_sources.json").unlink()
        (self.root / "research" / "graph_cache.json").unlink()
        data = self.build()
        self.assertEqual(knowledge_graph.check(self.page.read_text()), [])
        self.assertFalse([n for n in data["nodes"] if n["type"] in ("web", "report")])
        # No OpenAlex cache: labs come from the names state records.
        self.assertIsNotNone(self.node(data, "paper:10.1000/a")["primaryLab"])

    def test_stale_subarea_label_is_unassigned_not_dropped(self):
        data = self.build()
        hub = "subarea:XR Security:__stale"
        self.assertEqual(self.node(data, hub)["label"],
                         "XR Security: unassigned (label no longer in profile)")
        self.assertIn({"source": "paper:10.1000/b", "target": hub, "type": "subarea"},
                      data["edges"])
    def test_not_yet_labelled_is_not_the_same_as_fits_nothing(self):
        # No `subareas` field yet (e.g. straight after /research) is "not yet
        # labelled"; a scored `[]` means no profile sub-area fits - a taxonomy signal.
        data = self.build()
        self.assertIn({"source": "paper:10.1000/d", "target": "subarea:Applied ML:__unlabelled",
                       "type": "subarea"}, data["edges"])
        self.assertEqual(self.node(data, "subarea:Applied ML:__unlabelled")["label"],
                         "Applied ML: not yet labelled")
        self.assertIn({"source": "paper:10.1000/f", "target": "subarea:XR Security:__unassigned",
                       "type": "subarea"}, data["edges"])
        self.assertEqual(self.node(data, "subarea:XR Security:__unassigned")["label"],
                         "XR Security: fits no listed sub-area")
        self.assertIsNone(self.node(data, "paper:10.1000/d")["subareas"])
        self.assertEqual(self.node(data, "paper:10.1000/f")["subareas"], [])
        self.assertEqual(self.node(data, "subarea:XR Security:Auth")["detail"],
                         "knowledge-based and biometric")

    def test_plain_wording_no_internal_status_strings(self):
        data = self.build()
        labels = {n["id"]: n["statusLabel"] for n in data["nodes"] if n["type"] == "paper"}
        self.assertEqual(labels["paper:10.1000/a"], "Used in a report")
        self.assertEqual(labels["paper:10.1000/b"], "Scored, not yet used in a report")
        self.assertEqual(labels["paper:10.1000/c"], "Judged off-topic at triage")
        self.assertEqual(labels["paper:10.1000/e"], "Abstract could not be retrieved")
        self.assertFalse(set(labels.values()) & {"new", "skipped", "ranked", "synthesized",
                                                 "unfetchable"})
        self.assertEqual(self.node(data, "paper:10.1000/a")["evidenceLabel"], "Read in full")
        self.assertEqual(self.node(data, "paper:10.1000/b")["evidenceLabel"], "Not yet assessed")

    def test_new_since_defaults_to_latest_first_seen(self):
        data = self.build()
        self.assertEqual(data["meta"]["newSince"], "2026-10-20")
        new = sorted(n["id"] for n in data["nodes"] if n.get("isNew"))
        self.assertEqual(new, ["paper:10.1000/b", "paper:10.1000/d"])
        data = self.build("--new-since", "2026-10-15")
        self.assertIn("web:https://blog.example.org/post",
                      [n["id"] for n in data["nodes"] if n.get("isNew")])

    def test_new_count_matches_nodes(self):
        data = self.build("--new-since", "2026-10-15")
        self.assertEqual(data["meta"]["counts"]["new"],
                         sum(1 for n in data["nodes"] if n.get("isNew")))

    def test_web_sources_are_their_own_node_type(self):
        data = self.build()
        web = self.node(data, "web:https://blog.example.org/post")
        self.assertEqual((web["type"], web["kindLabel"]),
                         ("web", "Web source, not peer-reviewed"))
        self.assertIn({"source": web["id"], "target": "subarea:XR Security:Auth",
                       "type": "web_subarea"}, data["edges"])
        self.assertNotIn("web:https://ads.example.org/x", [n["id"] for n in data["nodes"]])

    def test_citations_labs_and_reports(self):
        data = self.build()
        self.assertIn({"source": "paper:10.1000/b", "target": "paper:10.1000/a", "type": "cites"},
                      data["edges"])
        a, b = self.node(data, "paper:10.1000/a"), self.node(data, "paper:10.1000/b")
        self.assertEqual((a["citedByIn"], b["citesIn"]), (1, 1))
        self.assertEqual(a["primaryLab"], b["primaryLab"])  # same senior author
        lab = next(l for l in data["labs"] if l["id"] == a["primaryLab"])
        self.assertEqual((lab["name"], lab["institution"]), ("Senior lab", "Uni A"))
        self.assertEqual(a["reports"], [{"slug": "r1", "title": "A Report",
                                         "sections": ["Side Channels", "Open Questions and Gaps"]}])
        self.assertIn({"source": "paper:10.1000/a", "target": "report:r1", "type": "report"},
                      data["edges"])

    def test_gaps_carry_rules_and_links(self):
        data = self.build()
        kinds = {g["kind"] for g in data["gaps"]}
        self.assertTrue({"report", "missing_landmark", "thin"} <= kinds, kinds)
        q = next(g for g in data["gaps"] if g["kind"] == "report")
        self.assertEqual((q["text"], q["rule"]), ("Does it hold? Author (2024)",
                                                  "Open question in report A Report"))
        self.assertIn({"source": f"gap:{q['id']}", "target": "report:r1", "type": "gap_report"},
                      data["edges"])
        self.assertIn({"source": f"gap:{q['id']}", "target": "subarea:XR Security:Side channels",
                       "type": "gap_subarea"}, data["edges"])

    def test_cached_pdf_is_linked(self):
        # paper-fetch names its cache <kind>-<sanitised id>.pdf, keeping the DOI's case.
        (self.root / "research" / "fulltext").mkdir()
        (self.root / "research" / "fulltext" / "doi-10.1000-A.pdf").write_bytes(b"%PDF")
        data = self.build()
        self.assertEqual(self.node(data, "paper:10.1000/a")["pdf"],
                         "../research/fulltext/doi-10.1000-A.pdf")
        self.assertIsNone(self.node(data, "paper:10.1000/b")["pdf"])

    def test_summary_omits_zero_clauses(self):
        data = self.build()
        self.assertEqual(data["meta"]["summary"],
                         "2 new since 2026-10-20: 1 in XR Security, 1 in Applied ML; "
                         "1 from labs already in your library.")
        data = self.build("--new-since", "2026-12-01")
        self.assertEqual(data["meta"]["summary"], "Nothing new since 2026-12-01.")

    def test_page_builds_when_enrichment_cannot_run(self):
        # The fixture has no connector and PATH has no bun: enrichment fails, the
        # page is still built, and the failure is reported.
        result = subprocess.run([sys.executable, str(self.root / "tools" / "knowledge_graph.py"),
                                 "--enrich"], capture_output=True, text=True,
                                env={"PATH": "/nonexistent", "HOME": str(self.root)})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("OpenAlex", result.stdout)
        self.assertEqual(knowledge_graph.check(self.page.read_text()), [])

    def test_unreadable_report_is_skipped_not_fatal(self):
        bad = self.root / "reports" / "r2"
        bad.mkdir()
        (bad / "report.tex").write_text(r"\title{Unbalanced \begin{document}")
        data = self.build()
        self.assertIn("report:r1", [n["id"] for n in data["nodes"]])
        self.assertTrue(any("r2" in w for w in data["meta"]["warnings"]), data["meta"])

    def test_synthetic_library_builds(self):
        data = self.build("--synthetic", "60")
        self.assertEqual(sum(1 for n in data["nodes"] if n["type"] == "paper"), 60)
        self.assertEqual(knowledge_graph.check(self.page.read_text()), [])


class CliTests(GraphFixture):
    def test_cli_json_and_check_exit_codes(self):
        result = self.run_graph("--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        out = json.loads(result.stdout)
        self.assertEqual(set(out), {"path", "counts", "summary"})
        self.assertEqual(self.run_graph("--check").returncode, 0)
        html = self.page.read_text()
        self.page.write_text(html.replace('"id":"paper:10.1000/a"', '"id":"paper:gone"', 1))
        bad = self.run_graph("--check")
        self.assertEqual(bad.returncode, 1)
        self.assertIn("paper:10.1000/a", bad.stdout)

    def test_check_without_page_fails_clearly(self):
        result = self.run_graph("--check")
        self.assertEqual(result.returncode, 1)
        self.assertIn("not built", result.stdout + result.stderr)


class CheckTests(unittest.TestCase):
    """check() on hand-made pages."""

    def page(self, data, extra=""):
        return knowledge_graph.render(data, '<html><head>' + extra + '</head><body>'
                                      '<script id="data" type="application/json">[GRAPH_JSON]'
                                      '</script></body></html>')

    def good(self):
        return {"meta": {}, "nodes": [{"id": "a", "type": "paper"}, {"id": "b", "type": "gap"}],
                "edges": [{"source": "b", "target": "a", "type": "gap_subarea"}],
                "gaps": [{"id": "g", "rule": "r", "text": "t"}], "labs": []}

    def test_every_edge_endpoint_exists(self):
        self.assertEqual(knowledge_graph.check(self.page(self.good())), [])
        bad = self.good()
        bad["edges"].append({"source": "a", "target": "zzz", "type": "cites"})
        self.assertTrue(any("zzz" in e for e in knowledge_graph.check(self.page(bad))))

    def test_gap_without_rule_fails(self):
        bad = self.good()
        bad["gaps"][0]["rule"] = " "
        self.assertTrue(knowledge_graph.check(self.page(bad)))

    def test_external_resources_fail(self):
        for extra in ('<script src="https://cdn.example.org/x.js"></script>',
                      "<link href='//fonts.example.org/f.css' rel=stylesheet>",
                      "<style>@import url(https://x.org/y.css);</style>"):
            self.assertTrue(knowledge_graph.check(self.page(self.good(), extra)), extra)

    def test_literal_lt_in_data_block_fails(self):
        html = self.page(self.good()).replace('"type":"paper"', '"type":"<b>"', 1)
        self.assertTrue(any("<" in e for e in knowledge_graph.check(html)))

    def test_render_has_one_slot(self):
        with self.assertRaises(ValueError):
            knowledge_graph.render({}, "<html>no slot</html>")


class DocsDriftTests(unittest.TestCase):
    """Commands and docs tell agents how to run the graph builder; a flag that does
    not exist fails the run that follows them."""

    DOCS = [*(REPO_ROOT / ".claude" / "commands").glob("*.md"),
            *(REPO_ROOT / ".claude" / "skills").rglob("*.md"),
            REPO_ROOT / "README.md", REPO_ROOT / "USAGE.md", REPO_ROOT / "CLAUDE.md",
            REPO_ROOT / "graph" / "README.md"]

    def test_documented_invocations_use_real_flags(self):
        real = {o for a in knowledge_graph.build_parser()._actions for o in a.option_strings}
        for doc in self.DOCS:
            for line in doc.read_text().splitlines():
                if "tools/knowledge_graph.py" not in line:
                    continue
                for flag in re.findall(r"(?<![\w-])--[a-z][a-z-]*", line.split("knowledge_graph.py", 1)[1]):
                    self.assertIn(flag, real, f"{doc.relative_to(REPO_ROOT)}: {line.strip()}")

    def test_every_search_command_refreshes_the_graph(self):
        commands = REPO_ROOT / ".claude" / "commands"
        for name in ("research", "rank", "synthesize", "update", "websearch", "graph"):
            text = (commands / f"{name}.md").read_text()
            self.assertIn("python3 tools/knowledge_graph.py --enrich", text, name)


if __name__ == "__main__":
    unittest.main()
