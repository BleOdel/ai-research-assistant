import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools"))
import kg_enrich  # noqa: E402
kg_enrich.PACE_SECONDS = 0


def work(wid, authors=(("A1", "Ann Author", "last"),), refs=(), title=None):
    """A connector `detail --format json` result, titled as the fixture entry."""
    return {"id": f"https://openalex.org/{wid}", "title": title or f"Paper {wid[-1]}",
            "authors": [{"name": n, "authorId": f"https://openalex.org/{a}", "orcid": None,
                         "position": p, "institutions": [{"id": "https://openalex.org/I1",
                                                          "name": "Uni A"}]}
                        for a, n, p in authors],
            "referencedWorks": [f"https://openalex.org/{r}" for r in refs]}


class LookupIdTests(unittest.TestCase):
    def test_lookup_id_forms(self):
        look = kg_enrich.openalex_lookup_id
        self.assertEqual(look("10.1109/VR.2021.1", {}), "10.1109/vr.2021.1")
        self.assertEqual(look("https://doi.org/10.1145/3.4", {"url": "https://doi.org/10.1145/3.4"}),
                         "10.1145/3.4")
        self.assertEqual(look("2412.14815", {"url": "http://arxiv.org/abs/2412.14815v1"}),
                         "10.48550/arXiv.2412.14815")
        self.assertEqual(look("arxiv:2205.00208", {}), "10.48550/arXiv.2205.00208")
        self.assertEqual(look("openalex:W123", {}), "W123")
        self.assertEqual(look("https://openalex.org/W77", {"url": "https://openalex.org/W77"}), "W77")
        self.assertIsNone(look("https://www.semanticscholar.org/paper/abc",
                               {"url": "https://www.semanticscholar.org/paper/abc"}))

    def test_journal_doi_preferred_over_arxiv(self):
        # A paper with both: the publisher DOI carries the venue version's authorships.
        self.assertEqual(kg_enrich.openalex_lookup_id(
            "arxiv:2401.00001", {"url": "https://doi.org/10.1145/9.9"}), "10.1145/9.9")


class EnrichTests(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.cache = self.dir / "graph_cache.json"
        self.entries = {
            "10.1000/a": {"title": "Paper a", "status": "ranked"},
            "10.1000/b": {"title": "Paper b", "status": "synthesized"},
            "10.1000/c": {"title": "Paper c", "status": "new"},
            "https://www.semanticscholar.org/paper/x": {"title": "X", "status": "ranked"},
        }
        self.calls = []

    def fetch_ok(self, lookup):
        self.calls.append(lookup)
        return work("W" + lookup[-1], refs=("W9",))

    def run_enrich(self, fetch, today="2026-10-21", **kw):
        return kg_enrich.enrich(self.entries, fetch, today, cache=self.cache, **kw)

    def cached(self):
        return json.loads(self.cache.read_text())["works"]

    def test_enrich_fetches_only_missing(self):
        counts = self.run_enrich(self.fetch_ok)
        self.assertEqual(counts["fetched"], 3)
        self.assertEqual(counts["skipped_no_id"], 1)
        rec = self.cached()["10.1000/a"]
        self.assertEqual(rec["openalex"], "https://openalex.org/Wa")
        self.assertEqual(rec["authors"][0]["position"], "last")
        self.assertEqual(rec["authors"][0]["institutions"], [{"id": "https://openalex.org/I1",
                                                               "name": "Uni A"}])
        self.assertEqual(rec["referenced"], ["https://openalex.org/W9"])
        self.calls.clear()
        counts = self.run_enrich(self.fetch_ok)
        self.assertEqual(self.calls, [])
        self.assertEqual(counts["cached"], 3)

    def test_enrich_keeps_progress_on_failure(self):
        def fetch(lookup):
            self.calls.append(lookup)
            if len(self.calls) > 2:
                raise kg_enrich.RateLimited("slow down")
            return work("W" + lookup[-1])
        counts = self.run_enrich(fetch)
        self.assertEqual(counts["stopped"], "rate-limited")
        self.assertEqual(len(self.cached()), 2)
        # The next run picks up where this one stopped.
        self.calls.clear()
        self.run_enrich(self.fetch_ok)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(len(self.cached()), 3)

    def test_enrich_records_not_found_as_error(self):
        counts = self.run_enrich(lambda lookup: None)
        self.assertEqual(counts["errors"], 3)
        rec = self.cached()["10.1000/a"]
        self.assertEqual((rec["openalex"], rec["error"], rec["fetched"]),
                         (None, "not found", "2026-10-21"))
        # Retried only once the error is 30 days old.
        self.calls.clear()
        self.run_enrich(self.fetch_ok, today="2026-11-19")
        self.assertEqual(self.calls, [])
        self.run_enrich(self.fetch_ok, today="2026-11-20")
        self.assertEqual(len(self.calls), 3)

    def test_transient_failure_stops_and_is_retried_next_run(self):
        # A network outage is not a fact about the paper: nothing is recorded, the
        # run stops (every later call would fail too), and the next run retries.
        def down(lookup):
            self.calls.append(lookup)
            raise kg_enrich.FetchFailed("DETAIL_FAILED: network down")
        counts = self.run_enrich(down)
        self.assertEqual((counts["stopped"], len(self.calls)), ("connector-failed", 1))
        self.assertFalse(self.cache.exists() and self.cached())
        self.calls.clear()
        self.run_enrich(self.fetch_ok)
        self.assertEqual(len(self.calls), 3)

    def test_connector_fetch_turns_local_failures_into_fetchfailed(self):
        import subprocess
        real = subprocess.run
        cases = [FileNotFoundError("bun"), subprocess.TimeoutExpired("bun", 60),
                 subprocess.CompletedProcess([], 0, stdout="not json", stderr="")]
        for case in cases:
            def fake(*a, **kw):
                if isinstance(case, BaseException):
                    raise case
                return case
            subprocess.run = fake
            try:
                with self.assertRaises(kg_enrich.FetchFailed, msg=repr(case)):
                    kg_enrich.connector_fetch("10.1000/x")
            finally:
                subprocess.run = real

    def test_wrong_paper_is_rejected(self):
        # OpenAlex resolved some arXiv DOIs to a different work. Its authors and
        # references would put the paper in the wrong lab with the wrong citations.
        def fetch(lookup):
            return work("W" + lookup[-1], title="Energy use of code language models")
        counts = self.run_enrich(fetch)
        rec = self.cached()["10.1000/a"]
        self.assertEqual((rec["authors"], rec["referenced"], rec["openalex"]), ([], [], None))
        self.assertTrue(rec["error"].startswith("title mismatch"), rec["error"])
        self.assertEqual(counts["errors"], 3)
        # A subtitle or punctuation difference is the same paper.
        ok = kg_enrich.enrich({"10.1000/q": {"title": "Heimdall: Eavesdropping in VR", "status": "ranked"}},
                              lambda _: work("Wq", title="Heimdall -- eavesdropping in VR."),
                              "2026-10-21", cache=self.cache)
        self.assertEqual(ok["fetched"], 1)

    def test_skipped_entries_are_not_enriched(self):
        self.entries["10.1000/s"] = {"title": "S", "status": "skipped"}
        self.run_enrich(self.fetch_ok)
        self.assertNotIn("10.1000/s", self.cached())

    def test_limit_caps_fetches(self):
        counts = self.run_enrich(self.fetch_ok, limit=1)
        self.assertEqual(counts["fetched"], 1)
        self.assertEqual(len(self.calls), 1)


if __name__ == "__main__":
    unittest.main()
