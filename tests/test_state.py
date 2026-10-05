import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
STATE_SCRIPT = REPO_ROOT / "tools" / "state.py"
CHECK_REPORT_SCRIPT = REPO_ROOT / "tools" / "check_report.py"  # state.py imports its parse_bib
SKILLS = REPO_ROOT / ".claude" / "skills" / "research-assistant"

sys.path.insert(0, str(REPO_ROOT / "tools"))
import state  # noqa: E402  (imported for its rubric constants)

PROFILE = """# Researcher Profile

## Research Interests

### XR Security
- **Why tracked:** test

### Applied ML
- **Why tracked:** test

## Depth Calibration
"""


def entry(**fields):
    base = {"title": "A Paper", "status": "new", "first_seen": "2026-10-01",
            "subject": "XR Security"}
    base.update(fields)
    return base


class StateFixture(unittest.TestCase):
    """A temp repo tree with state.py and a two-interest profile.

    state.py resolves its paths from its own location, so each test copies it
    into a fresh tree and runs it as a subprocess - the way commands invoke it.
    """

    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        (self.root / "tools").mkdir()
        shutil.copy(STATE_SCRIPT, self.root / "tools" / "state.py")
        shutil.copy(CHECK_REPORT_SCRIPT, self.root / "tools" / "check_report.py")
        profile = self.root / ".claude" / "skills" / "research-assistant" / "01-researcher-profile.md"
        profile.parent.mkdir(parents=True)
        profile.write_text(PROFILE)
        self.sources = self.root / "research" / "seen_sources.json"
        self.index = self.root / "research" / "papers_by_subject.md"
        self.tracker = self.root / "research_tracker.csv"
        self.web = self.root / "blog" / "seen_web_sources.json"

    def run_state(self, *args, env=None, stdin=None):
        return subprocess.run(
            [sys.executable, str(self.root / "tools" / "state.py"), *args],
            capture_output=True, text=True, input=stdin,
            env={**os.environ, **(env or {})},
        )

    def upsert(self, key, fields, file="sources"):
        return self.run_state("upsert", "--file", file, "--key", key, "--json", json.dumps(fields))

    def seen(self, path=None):
        return json.loads((path or self.sources).read_text())["seen"]

    def assertRefused(self, result, fragment):
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        err = json.loads(result.stderr)
        self.assertIn(fragment, json.dumps(err))
        return err


class WriteTests(StateFixture):
    def test_upsert_creates_file_and_regenerates_index(self):
        result = self.upsert("k1", entry())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.seen()["k1"]["title"], "A Paper")
        self.assertIn("## XR Security", self.index.read_text())

    def test_overall_and_verdict_are_computed_not_trusted(self):
        self.upsert("k1", entry(status="ranked", scores={
            "relevance": 90, "rigor": 82, "impact": 45, "recency": 100}))
        e = self.seen()["k1"]
        self.assertEqual((e["overall_score"], e["verdict"]), (81, "Core"))

    def test_insufficient_impact_renormalizes(self):
        self.upsert("k1", entry(status="ranked", scores={
            "relevance": 90, "rigor": 87, "impact": "insufficient data", "recency": 90}))
        # 90*.5 + 87*.3125 + 90*.1875 = 45 + 27.19 + 16.88 = 89.06
        self.assertEqual(self.seen()["k1"]["overall_score"], 89)

    def test_second_spelling_of_a_verdict_is_refused(self):
        self.upsert("k1", entry())
        before = self.sources.read_bytes()
        result = self.upsert("k1", {"verdict": "Core Source"})
        self.assertRefused(result, "Core Source")
        self.assertEqual(self.sources.read_bytes(), before)

    def test_wrong_caller_arithmetic_is_refused(self):
        result = self.upsert("k1", entry(scores={
            "relevance": 90, "rigor": 82, "impact": 45, "recency": 100}, overall_score=70))
        self.assertRefused(result, "compute to 81")
        self.assertFalse(self.sources.exists())

    def test_touching_a_stale_entry_heals_it(self):
        self.sources.parent.mkdir()
        stale = entry(status="ranked", scores={"relevance": 90, "rigor": 82, "impact": 45,
                                               "recency": 100},
                      overall_score=74, verdict="Supporting")
        self.sources.write_text(json.dumps({"seen": {"k1": stale}}))
        result = self.upsert("k1", {"evidence_basis": "fulltext"})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("recomputed stale overall_score 74 -> 81", result.stdout)
        self.assertEqual(self.seen()["k1"]["verdict"], "Core")

    def test_scores_merge_key_by_key(self):
        self.upsert("k1", entry(scores={"relevance": 90, "rigor": 60, "impact": 45,
                                        "recency": 100}))
        self.upsert("k1", {"scores": {"rigor": 82}})
        scores = self.seen()["k1"]["scores"]
        self.assertEqual((scores["relevance"], scores["rigor"]), (90, 82))
        self.assertEqual(self.seen()["k1"]["overall_score"], 81)

    def test_fields_are_never_removed(self):
        self.upsert("k1", entry(evidence_basis="abstract"))
        self.upsert("k1", {"status": "ranked"})
        self.assertEqual(self.seen()["k1"]["evidence_basis"], "abstract")

    def test_subject_must_be_tracked_or_uncategorized(self):
        self.assertRefused(self.upsert("k1", entry(subject="XR stuff")), "XR stuff")
        self.assertEqual(self.upsert("k2", entry(subject="Uncategorized")).returncode, 0)
        self.assertEqual(self.upsert("k3", entry(subject="Applied ML")).returncode, 0)

    def test_placeholder_profile_skips_subject_check(self):
        profile = self.root / ".claude/skills/research-assistant/01-researcher-profile.md"
        profile.write_text("## Research Interests\n\n### [TOPIC 1]\n")
        self.assertEqual(self.upsert("k1", entry(subject="Anything")).returncode, 0)

    def test_new_entry_needs_required_fields(self):
        self.assertRefused(self.upsert("k1", {"title": "x"}), "status")

    def test_batch_is_all_or_nothing(self):
        result = self.run_state("batch", "--file", "sources", "--json", json.dumps({
            "good": entry(), "bad": entry(status="read-later")}))
        self.assertRefused(result, "read-later")
        self.assertFalse(self.sources.exists())

    def test_batch_from_stdin(self):
        result = self.run_state("batch", "--file", "sources", "--json-file", "-",
                                stdin=json.dumps({"a": entry(), "b": entry()}))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(set(self.seen()), {"a", "b"})

    def test_set_status(self):
        self.upsert("k1", entry())
        result = self.run_state("set-status", "--file", "sources", "--status", "synthesized", "k1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.seen()["k1"]["status"], "synthesized")
        self.assertRefused(self.run_state("set-status", "--file", "sources",
                                          "--status", "synthesized", "nope"), "NOT_FOUND")

    def test_no_lock_or_temp_files_left_behind(self):
        self.upsert("k1", entry())
        self.upsert("k1", {"verdict": "Nonsense"})
        leftovers = [p.name for p in self.sources.parent.iterdir()
                     if p.name.endswith((".lock", ".tmp"))]
        self.assertEqual(leftovers, [])


class ConcurrencyTests(StateFixture):
    def test_concurrent_writers_lose_nothing(self):
        script = (
            "import json,subprocess,sys\n"
            "for i in range(8):\n"
            "    r=subprocess.run([sys.executable, sys.argv[1], 'upsert', '--file', 'sources',"
            " '--key', f'{sys.argv[2]}-{i}', '--json', json.dumps({'title':'t','status':'new',"
            "'first_seen':'2026-10-01','subject':'Uncategorized'})])\n"
            "    sys.exit(r.returncode) if r.returncode else None\n"
        )
        procs = [subprocess.Popen([sys.executable, "-c", script,
                                   str(self.root / "tools" / "state.py"), name])
                 for name in ("A", "B", "C")]
        self.assertEqual([p.wait() for p in procs], [0, 0, 0])
        self.assertEqual(len(self.seen()), 24)

    def test_held_lock_times_out_with_LOCKED(self):
        self.sources.parent.mkdir()
        (self.sources.parent / "seen_sources.json.lock").write_text("123\n")
        result = self.run_state("upsert", "--file", "sources", "--key", "k1",
                                "--json", json.dumps(entry()),
                                env={"STATE_LOCK_TIMEOUT": "0.3"})
        self.assertRefused(result, "LOCKED")

    def test_stale_lock_is_broken(self):
        self.sources.parent.mkdir()
        lock = self.sources.parent / "seen_sources.json.lock"
        lock.write_text("123\n")
        old = time.time() - 600
        os.utime(lock, (old, old))
        result = self.upsert("k1", entry())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("breaking stale lock", result.stderr)


class CheckTests(StateFixture):
    def write_raw(self, seen):
        self.sources.parent.mkdir(exist_ok=True)
        self.sources.write_text(json.dumps({"seen": seen}))

    def test_reports_errors_and_gaps_and_exits_1(self):
        self.write_raw({
            "stale": entry(status="ranked", scores={"relevance": 90, "rigor": 82, "impact": 45,
                                                    "recency": 100}, overall_score=74),
            "badspelling": entry(verdict="Core Source"),
            "oldscored": entry(status="synthesized", url="http://x"),
        })
        result = self.run_state("check", "sources", "--json")
        self.assertEqual(result.returncode, 1)
        report = json.loads(result.stdout)["research/seen_sources.json"]
        joined = " ".join(report["errors"])
        self.assertIn("compute to 81", joined)
        self.assertIn("Core Source", joined)
        self.assertIn("oldscored", report["gaps"]["scored entry missing evidence_basis"])

    def test_gaps_alone_do_not_fail(self):
        self.write_raw({"old": entry(status="synthesized", url="http://x")})
        self.assertEqual(self.run_state("check", "sources").returncode, 0)

    def test_fix_derived_repairs_only_derived_fields(self):
        stale = entry(status="ranked", scores={"relevance": 90, "rigor": 82, "impact": 45,
                                               "recency": 100},
                      overall_score=74, verdict="Supporting", evidence_basis="abstract")
        self.write_raw({"stale": stale})
        result = self.run_state("check", "sources", "--fix-derived")
        self.assertEqual(result.returncode, 0, result.stdout)
        fixed = self.seen()["stale"]
        self.assertEqual((fixed["overall_score"], fixed["verdict"]), (81, "Core"))
        self.assertEqual({k: v for k, v in fixed.items()
                          if k not in ("overall_score", "verdict")},
                         {k: v for k, v in stale.items()
                          if k not in ("overall_score", "verdict")})

    def test_nonstandard_connector_is_a_warning_not_error(self):
        self.write_raw({"k": entry(source_connector="semantic-scholar-search (by DOI)")})
        result = self.run_state("check", "sources", "--json")
        self.assertEqual(result.returncode, 0)
        self.assertTrue(json.loads(result.stdout)["research/seen_sources.json"]["warnings"])


class OtherFileTests(StateFixture):
    def test_web_uses_web_weights_and_thresholds(self):
        result = self.upsert("https://x", {
            "title": "Post", "status": "included", "first_seen": "2026-10-01",
            "scores": {"relevance": 70, "authority": 70, "evidence": 70, "recency": 70}},
            file="web")
        self.assertEqual(result.returncode, 0, result.stderr)
        e = self.seen(self.web)["https://x"]
        self.assertEqual((e["overall_score"], e["tier"]), (70, "Core"))  # academic would say Supporting

    def test_tracker_notes_append_and_status_enum(self):
        self.assertEqual(self.upsert("topic-a", {"status": "active", "notes": "first."},
                                     file="tracker").returncode, 0)
        self.upsert("topic-a", {"notes_append": "second."}, file="tracker")
        self.assertIn("topic-a,,,active,,first. second.", self.tracker.read_text())
        self.assertRefused(self.upsert("topic-a", {"status": "done"}, file="tracker"), "done")
        self.assertRefused(self.upsert("topic-a", {"colour": "red"}, file="tracker"), "colour")

    def test_score_command(self):
        result = self.run_state("score", "--relevance", "90", "--rigor", "82",
                                "--impact", "45", "--recency", "100")
        self.assertEqual(json.loads(result.stdout), {"overall_score": 81, "verdict": "Core"})
        result = self.run_state("score", "--web", "--relevance", "70", "--authority", "70",
                                "--evidence", "70", "--recency", "70")
        self.assertEqual(json.loads(result.stdout), {"overall_score": 70, "tier": "Core"})


class IndexTests(StateFixture):
    def test_index_format_and_ordering(self):
        self.run_state("batch", "--file", "sources", "--json", json.dumps({
            "lo": entry(title="Low", status="ranked", url="http://lo",
                        scores={"relevance": 50, "rigor": 50, "impact": 50, "recency": 50}),
            "hi": entry(title="High | piped", status="ranked", url="http://hi",
                        authors=["A", "B", "C", "D"], year=2025, venue="V",
                        scores={"relevance": 90, "rigor": 90, "impact": 90, "recency": 90}),
            "old": entry(title="Old unscored", relevance="high", first_seen="2026-01-01"),
            "new": entry(title="New unscored", relevance="low", first_seen="2026-09-01",
                         year=None),
            "unc": entry(title="Elsewhere", subject="Uncategorized"),
        }))
        text = self.index.read_text()
        xr = text.split("## XR Security")[1].split("##")[0]
        titles = re.findall(r"^\| (.*?) \|", xr, re.M)[1:]  # skip header row
        self.assertEqual(titles, ["High \\| piped", "Low", "New unscored", "Old unscored"])
        self.assertIn("| High \\| piped | A, B, C et al. | 2025 | V | 90 - Core | ranked | "
                      "[Link](http://hi) |", text)
        self.assertIn("| New unscored |  |  |  | low | new |  |", text)
        self.assertNotIn("None", text)
        self.assertIn("## Applied ML", text)  # tracked interests always listed
        self.assertTrue(text.rstrip().endswith("|  |"))  # Uncategorized is last
        self.assertLess(text.index("## Applied ML"), text.index("## Uncategorized"))


CORE = {"relevance": 90, "rigor": 82, "impact": 45, "recency": 100}  # 81
SUPPORTING = {"relevance": 60, "rigor": 60, "impact": 60, "recency": 60}  # 60
PERIPHERAL = {"relevance": 40, "rigor": 40, "impact": 40, "recency": 40}  # 40

BIB = """@inproceedings{agentdojo,
  title = {{AgentDojo}},
  eprint = {2406.13352},
  archivePrefix = {arxiv},
  url = {https://arxiv.org/abs/2406.13352},
  evidencebasis = {Compared against arXiv:2501.00001, which is not cited here.}
}
@inproceedings{greshake,
  title = {Not What You've Signed Up For},
  doi = {10.1145/3605764.3623985},
}
@misc{injecagent,
  title = {{InjecAgent}},
  url = {https://arxiv.org/abs/2403.02691v2},
}
@misc{oldkey,
  title = {Old},
  howpublished = {arXiv preprint arXiv:2205.00208},
}
"""


class UnmergedTests(StateFixture):
    """The drop this command exists to catch: sources scored Core for a report,
    left status "ranked", and never cited - invisible to /research's dedup."""

    def setUp(self):
        super().setUp()
        self.bib = self.root / "references.bib"
        self.bib.write_text(BIB)

    def seed(self, entries):
        result = self.run_state("batch", "--file", "sources", "--json", json.dumps(entries))
        self.assertEqual(result.returncode, 0, result.stderr)

    def unmerged(self, *extra, subject="XR Security"):
        return self.run_state("unmerged", "--subject", subject, "--bib", str(self.bib), *extra)

    def test_lists_ranked_core_and_supporting_missing_from_the_bib(self):
        self.seed({
            # cited, each under a different spelling of its identifier
            "https://doi.org/10.48550/arXiv.2406.13352": entry(status="ranked", scores=CORE),
            "https://doi.org/10.1145/3605764.3623985": entry(status="ranked", scores=CORE),
            "2403.02691": entry(status="ranked", scores=CORE),
            "arxiv:2205.00208": entry(status="ranked", scores=CORE,
                                      url="https://www.semanticscholar.org/paper/abc"),
            # not cited - only mentioned in another entry's evidencebasis
            "https://arxiv.org/abs/2501.00001": entry(title="Missing core", status="ranked",
                                                      scores=CORE),
            "10.1000/missing": entry(title="Missing supporting", status="ranked",
                                     scores=SUPPORTING),
            # not cited, but out of scope
            "10.1000/peripheral": entry(status="ranked", scores=PERIPHERAL),
            "10.1000/synthesized": entry(status="synthesized", scores=CORE),
            "10.1000/unscored": entry(status="new"),
            "10.1000/elsewhere": entry(subject="Applied ML", status="ranked", scores=CORE),
        })
        result = self.unmerged("--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        found = json.loads(result.stdout)["unmerged"]
        self.assertEqual([(e["key"], e["verdict"], e["overall_score"]) for e in found],
                         [("https://arxiv.org/abs/2501.00001", "Core", 81),
                          ("10.1000/missing", "Supporting", 60)])
        text = self.unmerged().stdout
        self.assertIn("2 ranked Core/Supporting source(s) for 'XR Security' not in "
                      "references.bib", text)
        self.assertIn("Missing core", text)

    def test_nothing_missing_says_so(self):
        self.seed({"2406.13352": entry(status="ranked", scores=CORE)})
        result = self.unmerged()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("none - every ranked Core/Supporting source", result.stdout)

    def test_bad_subject_and_missing_bib_are_refused(self):
        self.seed({"k": entry()})
        err = self.assertRefused(self.unmerged(subject="XR"), "BAD_ARG")
        self.assertIn("XR Security", " ".join(err["problems"]))
        self.bib.unlink()
        self.assertRefused(self.unmerged(), "NOT_FOUND")

    def test_unparseable_bib_is_refused(self):
        self.bib.write_text("@misc{broken, title = {unclosed}\n")
        self.assertRefused(self.unmerged(), "PARSE_ERROR")


LANDMARK_PROFILE = """# Researcher Profile

## Research Interests

### XR Security
- **Why tracked:** test
- **Known landmark works (if any):**

  *Side channels*
  - Going Through the Motions: AR/VR Keylogging from User Head
    Motions
  - LookUnlock
  - Inception Attacks: Immersive Hijacking

  *Surveys*
  - Odeleye, Loukas, Heartfield. 2023. Virtually Secure: A taxonomic assessment of
    cybersecurity challenges in virtual reality environments. Computers & Security.
    *(Own work - confirmed by researcher, 2026-08-05)*
  - Security and Privacy Approaches in Mixed Reality: A Literature Survey
- **Expertise level:** expert

### Applied ML
- **Why tracked:** test
- **Known landmark works (if any):** none yet.

## Depth Calibration
"""


class LandmarkTests(StateFixture):
    def setUp(self):
        super().setUp()
        (self.root / ".claude/skills/research-assistant/01-researcher-profile.md").write_text(
            LANDMARK_PROFILE)
        self.run_state("batch", "--file", "sources", "--json", json.dumps({
            "k1": entry(title="Going through the motions: AR/VR keylogging from user head motions"),
            "k2": entry(title="Virtually secure: A taxonomic assessment of cybersecurity challenges "
                              "in virtual reality environments", status="skipped",
                        subject="Applied ML"),
            "k3": entry(title="Security and Privacy Approaches in Mixed Reality"),
            "k4": entry(title="Unlock"),
            "k5": entry(title="Inception Attacks: Immersive Hijacking in Virtual Reality Systems"),
        }))

    def landmarks(self, subject="XR Security"):
        result = self.run_state("landmarks", "--subject", subject, "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)["landmarks"]

    def test_lists_each_landmark_with_its_group_and_match(self):
        found = self.landmarks()
        self.assertEqual([(w["group"], (w["match"] or {}).get("key")) for w in found], [
            ("Side channels", "k1"), ("Side channels", None), ("Side channels", "k5"),
            ("Surveys", "k2"), ("Surveys", "k3")])

    def test_continuation_lines_join_and_provenance_note_is_dropped(self):
        found = self.landmarks()
        self.assertEqual(found[0]["text"],
                         "Going Through the Motions: AR/VR Keylogging from User Head Motions")
        self.assertTrue(found[3]["text"].endswith("Computers & Security."), found[3]["text"])

    def test_matches_across_subjects_and_statuses(self):
        self.assertEqual(self.landmarks()[3]["match"]["subject"], "Applied ML")

    def test_short_title_needs_a_close_match_not_containment(self):
        self.assertIsNone(self.landmarks()[1]["match"])  # "Unlock" is inside "LookUnlock"

    def test_text_output_lists_missing_first(self):
        out = self.run_state("landmarks", "--subject", "XR Security").stdout
        self.assertIn("5 landmark work(s) for 'XR Security': 4 in seen_sources.json, 1 missing", out)
        self.assertLess(out.index("MISSING  LookUnlock"), out.index("present"))

    def test_interest_without_landmarks(self):
        self.assertEqual(self.landmarks("Applied ML"), [])
        self.assertIn("none -", self.run_state("landmarks", "--subject", "Applied ML").stdout)

    def test_unknown_subject_is_refused(self):
        self.assertRefused(self.run_state("landmarks", "--subject", "XR"), "BAD_ARG")


def ranked(rank_date, **fields):
    base = entry(status="ranked", rank_date=rank_date, evidence_basis="abstract",
                 disclosure="academic", rigor_basis="70 (venue 70)",
                 scores={"relevance": 80, "rigor": 70, "impact": 60, "recency": 70})
    base.update(fields)
    return base


class CandidateTests(StateFixture):
    def setUp(self):
        super().setUp()
        from datetime import date, timedelta
        day = lambda n: (date.today() - timedelta(days=n)).isoformat()
        result = self.run_state("batch", "--file", "sources", "--json", json.dumps({
            "fresh": ranked(day(3), title="Fresh"),
            "stale": ranked(day(45), title="Stale"),
            "partial": {k: v for k, v in ranked(day(1), title="Partial").items()
                        if k != "evidence_basis"},
            "new": entry(title="New", relevance="high"),
            "skipped": entry(title="Skipped", status="skipped", relevance="low"),
            "done": ranked(day(1), title="Done", status="synthesized"),
            "other": ranked(day(1), title="Other", subject="Applied ML"),
        }))
        self.assertEqual(result.returncode, 0, result.stderr)

    def candidates(self, *extra):
        result = self.run_state("candidates", "--subject", "XR Security", "--json", *extra)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_splits_fresh_complete_rankings_from_the_rest(self):
        found = self.candidates()
        self.assertEqual([r["key"] for r in found["reusable"]], ["fresh"])
        self.assertEqual({r["key"]: r["reason"] for r in found["to_score"]}, {
            "new": "new (triage: high)",
            "skipped": "skipped (triage: low)",
            "partial": "ranked but missing evidence_basis",
            "stale": f"ranked {found['to_score'][-1]['rank_date']}, 45 days ago (over 30)",
        })

    def test_max_age_moves_the_cutoff(self):
        found = self.candidates("--max-age", "60")
        self.assertEqual(sorted(r["key"] for r in found["reusable"]), ["fresh", "stale"])
        self.assertEqual(self.candidates("--max-age", "2")["reusable"], [])

    def test_text_output(self):
        out = self.run_state("candidates", "--subject", "XR Security").stdout
        self.assertIn("5 candidate(s) - 1 with reusable /rank scoring (at most 30 days old), "
                      "4 to score", out)

    def test_bad_arguments_are_refused(self):
        self.assertRefused(self.run_state("candidates", "--subject", "XR"), "BAD_ARG")
        self.assertRefused(self.run_state("candidates", "--subject", "XR Security",
                                          "--max-age", "-1"), "BAD_ARG")


class RubricDriftTests(unittest.TestCase):
    """state.py's constants must match the rubric documents they enforce."""

    def doc(self, name):
        return (SKILLS / name).read_text()

    def test_academic_weights(self):
        found = dict(re.findall(r"^- (Relevance|Rigor|Impact|Recency): (\d+)%$",
                                self.doc("02-source-evaluation.md"), re.M))
        self.assertEqual({k.lower(): int(v) / 100 for k, v in found.items()}, state.WEIGHTS)

    def test_academic_renormalized_weights(self):
        found = dict(re.findall(r"^\| (Relevance|Rigor|Recency) \| \d+% \| \*\*([\d.]+)%\*\* \|$",
                                self.doc("02-source-evaluation.md"), re.M))
        self.assertEqual({k.lower(): float(v) / 100 for k, v in found.items()},
                         state.RENORMALIZED)

    def test_academic_verdicts_and_thresholds(self):
        found = re.findall(r"^- \*\*(\w+)\*\* \((?:<)?(\d+)", self.doc("02-source-evaluation.md"),
                           re.M)
        self.assertEqual(tuple(name for name, _ in found), state.VERDICTS)
        self.assertEqual(tuple((int(n), name) for name, n in found[:3]), state.THRESHOLDS)

    def test_disclosure_labels(self):
        found = re.findall(r"^\| `([\w-]+)` \|", self.doc("02-source-evaluation.md"), re.M)
        self.assertEqual(tuple(found), state.DISCLOSURE)

    def test_web_weights_thresholds_labels(self):
        doc = self.doc("09-web-source-evaluation.md")
        weights = dict(re.findall(r"^### \d\. (\w+)(?: Quality)? \((\d+)%\)$", doc, re.M))
        self.assertEqual({k.lower(): int(v) / 100 for k, v in weights.items()}, state.WEB_WEIGHTS)
        thresholds = re.findall(r"^\| (\d+)(?:\+|-\d+) \| \*\*(\w+)\*\* \|", doc, re.M)
        self.assertEqual(tuple((int(n), name) for n, name in thresholds), state.WEB_THRESHOLDS)
        labels = re.findall(r"^\| `([\w-]+)` \|", doc, re.M)
        self.assertEqual(tuple(labels), state.WEB_INDEPENDENCE)
        types = re.findall(r"`([\w-]+)`", doc.split("## Content Type")[1].split("##")[0])
        self.assertEqual(tuple(types[:len(state.WEB_TYPES)]), state.WEB_TYPES)

    def test_statuses(self):
        research = (REPO_ROOT / ".claude/commands/research.md").read_text()
        found = re.search(r'"status": "([\w/]+)"', research).group(1).split("/")
        self.assertEqual(tuple(found), state.STATUSES)
        outcome = (REPO_ROOT / ".claude/commands/outcome.md").read_text()
        found = re.search(r"\*\*Current status:\*\* ([\w| ]+)", outcome).group(1)
        self.assertEqual(tuple(s.strip() for s in found.split("|")), state.TRACKER_STATUSES)
        websearch = (REPO_ROOT / ".claude/commands/websearch.md").read_text()
        found = re.search(r'"status": "([\w| ]+)"', websearch).group(1)
        self.assertEqual(tuple(s.strip() for s in found.split("|")), state.WEB_STATUSES)

    def test_documented_invocations_exist(self):
        """Every `tools/state.py <command> --flag` a command doc tells Claude to run
        must be a real subcommand and flag - a typo there fails at run time."""
        parser = state.build_parser()
        commands = parser._subparsers._group_actions[0].choices
        docs = sorted((REPO_ROOT / ".claude/commands").glob("*.md"))
        docs += sorted(SKILLS.glob("*.md"))
        seen = set()
        for doc in docs:
            for line in doc.read_text().splitlines():
                for match in re.finditer(r"tools/state\.py ([a-z][\w-]*)([^`\n]*)", line):
                    command, rest = match.groups()
                    seen.add(command)
                    self.assertIn(command, commands, f"{doc.name}: {line.strip()}")
                    flags = set(commands[command]._option_string_actions)
                    for flag in re.findall(r"(?<![\w-])(--[a-z][\w-]*)", rest):
                        self.assertIn(flag, flags, f"{doc.name}: {line.strip()}")
        self.assertIn("unmerged", seen)
        self.assertIn("landmarks", seen)
        self.assertIn("candidates", seen)

    def test_rank_writes_every_scored_field(self):
        """/rank is how sources get scored. If its documented agent output or its
        state write leaves out a field `check` expects on every scored entry, each
        run creates that gap anew - evidence_basis was missing this way, leaving 68
        sources without one."""
        rank = (REPO_ROOT / ".claude/commands/rank.md").read_text()
        output = re.search(r"Each agent returns a JSON array.*?```json\n(.*?)```", rank, re.S)
        write = re.search(r"^- Scored sources:(.*?)(?=^- |\Z)", rank, re.S | re.M)
        self.assertIsNotNone(output, "rank.md: agent output JSON block not found")
        self.assertIsNotNone(write, "rank.md: 'Scored sources:' write list not found")
        for field in state.SCORED_FIELDS:
            self.assertIn(f'"{field}"', output.group(1), f"rank.md agent output lacks {field}")
            self.assertIn(f'"{field}"', write.group(1), f"rank.md state write lacks {field}")


if __name__ == "__main__":
    unittest.main()
