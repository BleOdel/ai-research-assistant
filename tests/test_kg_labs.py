import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools"))
import kg_labs  # noqa: E402


def au(aid, name, position="middle", inst=None, with_id=True):
    return {"name": name, "authorId": f"https://openalex.org/{aid}" if with_id else None,
            "position": position,
            "institutions": [{"id": f"https://openalex.org/{inst}", "name": inst}] if inst else []}


def two_labs():
    """Lab A (senior SA at UniA, papers 1-3) and lab B (senior SB at UniB, papers
    4-6), joined only by student ST, who is on paper 3 and paper 4. A plain
    shared-author grouping chains both labs into one - the mockup's 27-paper
    chain failed this way."""
    a = lambda pos="middle": au("SA", "Sam Alpha", pos, "UniA")
    b = lambda pos="middle": au("SB", "Sue Beta", pos, "UniB")
    st = au("ST", "Stu Dent", "first", "UniA")
    return {
        "p1": [au("A1", "Ann One", "first", "UniA"), au("A2", "Al Two", "middle", "UniA"), a("last")],
        "p2": [au("A2", "Al Two", "first", "UniA"), au("A1", "Ann One", "middle", "UniA"), a("last")],
        "p3": [st, au("A1", "Ann One", "middle", "UniA"), a("last")],
        "p4": [{**st, "institutions": [{"id": "https://openalex.org/UniB", "name": "UniB"}]},
               au("B1", "Bo One", "middle", "UniB"), b("last")],
        "p5": [au("B1", "Bo One", "first", "UniB"), au("B2", "Bea Two", "middle", "UniB"), b("last")],
        "p6": [au("B2", "Bea Two", "first", "UniB"), au("B1", "Bo One", "middle", "UniB"), b("last")],
    }


def lab_of(result, pid):
    return result["paper_primary"][pid]


class AuthorKeyTests(unittest.TestCase):
    def test_id_or_normalised_name(self):
        self.assertEqual(kg_labs.author_key(au("X1", "Yi Wang")), ("https://openalex.org/X1", False))
        self.assertEqual(kg_labs.author_key({"name": "Yí Wang", "authorId": None}), ("wang y", True))
        self.assertEqual(kg_labs.author_key({"name": "Y. Wang"}), ("wang y", True))


class ClassifyTests(unittest.TestCase):
    def test_two_labs_joined_by_one_student_stay_two_labs(self):
        r = kg_labs.classify_labs(two_labs())
        self.assertEqual(len({lab_of(r, p) for p in ("p1", "p2", "p3")}), 1)
        self.assertEqual(len({lab_of(r, p) for p in ("p4", "p5", "p6")}), 1)
        self.assertNotEqual(lab_of(r, "p1"), lab_of(r, "p4"))

    def test_primary_lab_is_senior_authors(self):
        r = kg_labs.classify_labs(two_labs())
        # p4's first author is the student, whose own lab is A; the senior is SB.
        self.assertEqual(lab_of(r, "p4"), r["author_lab"]["https://openalex.org/SB"])
        # No positions recorded: the last-listed author is the senior one.
        papers = {"q": [{"name": "First Person"}, {"name": "Last Person"}]}
        r = kg_labs.classify_labs(papers)
        self.assertEqual(lab_of(r, "q"), r["author_lab"]["person l"])

    def test_cross_lab_paper_is_bridge(self):
        r = kg_labs.classify_labs(two_labs())
        # The student is tied evenly to both labs, so whichever paper they are not
        # the home-lab author of spans two labs, with its senior's lab first.
        bridge = [p for p in ("p3", "p4") if len(r["paper_labs"][p]) == 2]
        self.assertEqual(len(bridge), 1)
        self.assertEqual(r["paper_labs"][bridge[0]][0], lab_of(r, bridge[0]))
        edges = kg_labs.lab_edges(r, {p: 2020 + i for i, p in enumerate(sorted(two_labs()))})
        collab = {frozenset((e["source"], e["target"])) for e in edges if e["type"] == "collab"}
        self.assertIn(frozenset(("p3", "p4")), collab)
        lab = [(e["source"], e["target"]) for e in edges if e["type"] == "lab"]
        self.assertIn(("p1", "p2"), lab)
        self.assertIn(("p2", "p3"), lab)
        self.assertNotIn(("p1", "p3"), lab)  # a chain in publication order, not a clique

    def test_name_fallback_flags_matched_by_name(self):
        papers = {"n1": [{"name": "Yi Wang"}, {"name": "Li Chen"}],
                  "n2": [{"name": "Y. Wang"}, {"name": "Li Chen"}]}
        r = kg_labs.classify_labs(papers)
        self.assertEqual(lab_of(r, "n1"), lab_of(r, "n2"))
        lab = next(l for l in r["labs"] if l["id"] == lab_of(r, "n1"))
        self.assertTrue(lab["matched_by_name"])
        self.assertIn("wang y", r["author_lab"])

    def test_unambiguous_name_joins_its_openalex_id(self):
        # A paper known only by a Semantic Scholar URL has names, no ids; the same
        # person elsewhere in the library has an id.
        papers = {"id1": [au("Z1", "Zoe Zed", "first"), au("Q9", "Quinn Q", "last")],
                  "name1": [{"name": "Z. Zed"}, {"name": "Quinn Q"}]}
        r = kg_labs.classify_labs(papers)
        self.assertEqual(lab_of(r, "id1"), lab_of(r, "name1"))

    def test_deterministic(self):
        first = kg_labs.classify_labs(two_labs())
        second = kg_labs.classify_labs(dict(reversed(list(two_labs().items()))))
        self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(second, sort_keys=True))

    def test_lab_naming_uses_senior_and_institution(self):
        r = kg_labs.classify_labs(two_labs())
        lab = next(l for l in r["labs"] if l["id"] == lab_of(r, "p5"))
        self.assertEqual((lab["name"], lab["institution"]), ("Beta lab", "UniB"))
        self.assertEqual(sorted(lab["papers"]), ["p4", "p5", "p6"])

    def test_lab_name_tie_goes_to_the_author_on_most_papers(self):
        # Two papers, two different seniors (one each); Bea is on both, so the lab
        # is hers, not whichever senior sorts first alphabetically.
        papers = {"x1": [au("BB", "Bea Baggili", "middle"), au("AY", "Ann Yarr", "last")],
                  "x2": [au("BB", "Bea Baggili", "middle"), au("CB", "Cy Breit", "last")]}
        r = kg_labs.classify_labs(papers)
        lab = next(l for l in r["labs"] if l["id"] == lab_of(r, "x1"))
        self.assertEqual(lab["name"], "Baggili lab")

    def test_lab_ids_survive_the_library_growing(self):
        # Ids end up in bookmarks; a new, bigger lab must not renumber the others.
        before = kg_labs.classify_labs(two_labs())
        bigger = dict(two_labs())
        for i in range(5):
            bigger[f"z{i}"] = [au(f"Z{i}", f"Zed Member{i}", "first"), au("ZS", "Zara Senior", "last")]
        after = kg_labs.classify_labs(bigger)
        for pid in ("p1", "p5"):
            self.assertEqual(lab_of(before, pid), lab_of(after, pid))
        self.assertNotEqual(lab_of(after, "z0"), lab_of(after, "p1"))

    def test_paper_with_no_authors_has_no_lab(self):
        r = kg_labs.classify_labs({"empty": []})
        self.assertIsNone(r["paper_primary"]["empty"])
        self.assertEqual(r["paper_labs"]["empty"], [])


class ConfirmedSplitTests(unittest.TestCase):
    """The researcher's confirmed lab split of the 104 library papers cited in the
    XR state-of-the-art report (2026-10-21), as an anonymised author graph of the
    whole 307-paper library - labs are classified across the library, so the
    fixture needs all of it. A change to the weights or the community detection
    that regroups these papers has to be re-checked with the researcher."""

    def test_confirmed_xr_lab_split_is_reproduced(self):
        fixture = json.loads((REPO_ROOT / "tests" / "fixtures" / "kg_labs_xr.json").read_text())
        result = kg_labs.classify_labs(fixture["papers"])
        groups = {}
        for pid in fixture["report_papers"]:
            groups.setdefault(result["paper_primary"][pid], set()).add(pid)
        self.assertEqual(sorted(sorted(g) for g in groups.values()),
                         sorted(sorted(g) for g in fixture["expected_groups"]))


class CliTests(unittest.TestCase):
    """The CLI the lab-acceptance checkpoint uses: classify the whole cached
    library, print one report's papers."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        (self.root / "tools").mkdir()
        for name in ("state.py", "check_report.py", "kg_enrich.py", "kg_labs.py"):
            shutil.copy(REPO_ROOT / "tools" / name, self.root / "tools" / name)
        (self.root / "research").mkdir()
        seen = {f"10.1000/{p}": {"title": f"Paper {p}", "status": "ranked", "subject": "X",
                                  "first_seen": "2026-10-01", "year": 2020 + i}
                for i, p in enumerate(sorted(two_labs()))}
        (self.root / "research" / "seen_sources.json").write_text(json.dumps({"seen": seen}))
        works = {f"10.1000/{p}": {"openalex": None, "authors": a, "referenced": [],
                                  "fetched": "2026-10-21", "error": None}
                 for p, a in two_labs().items()}
        (self.root / "research" / "graph_cache.json").write_text(json.dumps({"works": works}))
        self.bib = self.root / "refs.bib"
        self.bib.write_text("@article{k5, title={Paper p5}, doi={10.1000/p5}}\n"
                            "@article{k6, title={Paper p6}, doi={10.1000/p6}}\n")

    def run_labs(self, *args):
        result = subprocess.run([sys.executable, str(self.root / "tools" / "kg_labs.py"), *args,
                                 "--json"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_cli_bib_filter_restricts_printout_only(self):
        full = self.run_labs()
        some = self.run_labs("--bib", str(self.bib))
        self.assertEqual(sorted(p for l in some["labs"] for p in l["papers"]),
                         ["10.1000/p5", "10.1000/p6"])
        lab_ids = {p: l["id"] for l in full["labs"] for p in l["papers"]}
        for lab in some["labs"]:
            for paper in lab["papers"]:
                self.assertEqual(lab["id"], lab_ids[paper])
        # p4, p5 and p6 share a lab in the full classification even though the
        # filtered view prints only p5 and p6.
        self.assertEqual(lab_ids["10.1000/p4"], lab_ids["10.1000/p5"])


if __name__ == "__main__":
    unittest.main()
