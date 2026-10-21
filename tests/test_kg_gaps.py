import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools"))
import kg_gaps  # noqa: E402

TAXONOMY = {"XR": ["Side channels", "Auth", "Forensics"], "ML": ["Detection"]}


def paper(sub, contribution="measurement", year=2025, status="ranked", subject="XR", **kw):
    return {"title": "P", "status": status, "subject": subject, "year": year,
            "subareas": [sub] if isinstance(sub, str) else sub,
            "contribution": contribution, **kw}


def gaps_by(entries, kind, year=2026, **kw):
    return {(g["interest"], g["subarea"]): g
            for g in kg_gaps.computed_gaps(entries, year, TAXONOMY, **kw) if g["kind"] == kind}


class ComputedGapTests(unittest.TestCase):
    def test_thin_threshold_edges(self):
        entries = {"a": paper("Auth"), "b": paper("Auth"),
                   "c": paper("Side channels"), "d": paper("Side channels"),
                   "e": paper("Side channels")}
        thin = gaps_by(entries, "thin")
        self.assertIn(("XR", "Auth"), thin)
        self.assertNotIn(("XR", "Side channels"), thin)
        # A listed sub-area with no papers at all is the thinnest of all.
        self.assertIn(("XR", "Forensics"), thin)
        self.assertEqual(thin[("XR", "Auth")]["items"], ["a", "b"])

    def test_only_scored_papers_count(self):
        entries = {k: paper("Side channels") for k in "abc"}
        entries["c"]["status"] = "new"
        self.assertIn(("XR", "Side channels"), gaps_by(entries, "thin"))

    def test_stale_uses_dated_papers_only(self):
        old = {"a": paper("Auth", year=2021), "b": paper("Auth", year=2022)}
        self.assertIn(("XR", "Auth"), gaps_by(old, "stale"))
        # An undated paper does not make the sub-area current...
        self.assertIn(("XR", "Auth"), gaps_by({**old, "u": paper("Auth", year=None)}, "stale"))
        # ...and a sub-area with only undated papers is not called stale.
        self.assertNotIn(("XR", "Auth"), gaps_by({"u": paper("Auth", year=None)}, "stale"))
        self.assertNotIn(("XR", "Auth"), gaps_by({**old, "n": paper("Auth", year=2024)}, "stale"))
        self.assertEqual(gaps_by(old, "stale")[("XR", "Auth")]["rule"],
                         "No paper from 2024 or later")

    def test_no_defence_rule(self):
        attacks = {k: paper("Side channels", "attack") for k in "abc"}
        self.assertIn(("XR", "Side channels"), gaps_by(attacks, "no_defence"))
        self.assertNotIn(("XR", "Side channels"),
                         gaps_by({**attacks, "d": paper("Side channels", "defence")}, "no_defence"))
        self.assertNotIn(("XR", "Side channels"),
                         gaps_by({"a": attacks["a"], "b": attacks["b"]}, "no_defence"))

    def test_cross_interest_label_counts_under_that_interest(self):
        entries = {k: paper(["Side channels", "ML: Detection"]) for k in "abc"}
        self.assertNotIn(("ML", "Detection"), gaps_by(entries, "thin"))

    def test_unlabelled_interest_gets_no_subarea_gaps(self):
        # Before the labels are backfilled every sub-area would read as thin.
        entries = {"a": {"title": "P", "status": "ranked", "subject": "ML", "year": 2025}}
        self.assertEqual([g for g in kg_gaps.computed_gaps(entries, 2026, TAXONOMY)
                          if g["interest"] == "ML" and g["kind"] in ("thin", "stale")], [])

    def test_unused_and_missing_landmarks(self):
        entries = {"10.1000/a": paper("Auth", verdict="Core"),
                   "10.1000/b": paper("Auth", verdict="Core"),
                   "10.1000/c": paper("Auth", verdict="Peripheral")}
        found = kg_gaps.computed_gaps(entries, 2026, TAXONOMY, cited={"doi:10.1000/b"},
                                      landmarks={"XR": ["Some Landmark (2019)"]})
        unused = next(g for g in found if g["kind"] == "unused")
        self.assertEqual(unused["items"], ["10.1000/a"])
        missing = next(g for g in found if g["kind"] == "missing_landmark")
        self.assertEqual(missing["detail"], ["Some Landmark (2019)"])

    def test_every_gap_has_rule_text(self):
        entries = {k: paper("Side channels", "attack", year=2019, verdict="Core") for k in "abc"}
        found = kg_gaps.computed_gaps(entries, 2026, TAXONOMY,
                                      landmarks={"XR": ["L"]})
        self.assertEqual({g["kind"] for g in found},
                         {"thin", "stale", "no_defence", "unused", "missing_landmark"})
        for g in found:
            self.assertTrue(g["rule"].strip(), g)
            self.assertTrue(g["text"].strip(), g)
            self.assertTrue(g["id"].startswith(g["kind"] + ":"), g)


REPORT = r"""\documentclass{article}
\title{XR Privacy: A \emph{Review}}
\begin{document}
\section{Side Channels}
\subsection{Sensors}
Motion leaks keystrokes \citep{luo2024}. % \cite{commented}
\section{Open Questions and Gaps}
\begin{itemize}
  \item \textbf{Do defences hold?} \citet{luo2024} and \citet{kim2023} disagree
    on 80\% of cases.
  \item Nobody has measured \emph{bystanders} \citep{kim2023,ghost}.
\end{itemize}
\section{Evidence Basis}
\citet{luo2024} \citet{kim2023}
\end{document}
"""

BIB = r"""@inproceedings{luo2024, author={Luo, Shiqing and Yan, Zhisheng}, title={Heimdall},
  year={2024}, doi={10.14722/ndss.2024.24100}}
@article{kim2023, author={Kim, Ann}, title={Bystanders}, year={2023},
  eprint={2301.00001}}
@misc{ghost, author={Nobody}, title={Not In State}, year={2020}, url={https://example.org/x}}
"""


class ReportIndexTests(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        (self.dir / "report.tex").write_text(REPORT)
        (self.dir / "references.bib").write_text(BIB)
        self.entries = {"10.14722/ndss.2024.24100": {"title": "Heimdall"},
                        "arxiv:2301.00001": {"title": "Bystanders"}}
        self.index = kg_gaps.report_index(self.dir, self.entries)

    def test_report_open_questions_parsed_with_keys(self):
        qs = self.index["open_questions"]
        self.assertEqual(len(qs), 2)
        self.assertEqual(qs[0]["keys"], ["10.14722/ndss.2024.24100", "arxiv:2301.00001"])
        self.assertEqual(qs[0]["text"],
                         "Do defences hold? Luo and Yan (2024) and Kim (2023) disagree "
                         "on 80% of cases.")
        self.assertEqual(qs[1]["keys"], ["arxiv:2301.00001"])  # ghost is not in state
        self.assertEqual(qs[1]["text"],
                         "Nobody has measured bystanders (Kim, 2023; Nobody, 2020).")

    def test_question_ids_survive_edits_around_them(self):
        first = [q["id"] for q in self.index["open_questions"]]
        (self.dir / "report.tex").write_text(REPORT.replace(
            r"\begin{itemize}", "\\begin{itemize}\n  \\item A new first question.", 1))
        again = kg_gaps.report_index(self.dir, self.entries)["open_questions"]
        self.assertEqual([q["id"] for q in again[1:]], first)
        self.assertEqual(len(set(q["id"] for q in again)), 3)

    def test_sections_recorded_per_cited_key(self):
        self.assertEqual(self.index["title"], "XR Privacy: A Review")
        self.assertEqual(self.index["slug"], self.dir.name)
        cites = self.index["cites"]
        self.assertEqual(cites["10.14722/ndss.2024.24100"],
                         ["Side Channels > Sensors", "Open Questions and Gaps"])
        # The Evidence Basis table cites everything; it says nothing about where
        # a paper is used.
        self.assertNotIn("Evidence Basis", cites["arxiv:2301.00001"])

    def test_refs_and_nested_lists_read_as_text(self):
        # Seen on the live reports: "Section sec:adaptive" and a stray "itemize".
        tex = REPORT.replace(r"\section{Side Channels}", r"\section{Side Channels}\label{sec:side}")
        tex = tex.replace(r"Nobody has measured", r"See Section~\ref{sec:side}. \begin{itemize} \item One \end{itemize} Nobody has measured")
        (self.dir / "report.tex").write_text(tex)
        text = kg_gaps.report_index(self.dir, self.entries)["open_questions"][1]["text"]
        self.assertTrue(text.startswith("See Section Side Channels. One Nobody"), text)
        self.assertNotIn("itemize", text)

    def test_zero_papers_reads_naturally(self):
        gaps = kg_gaps.computed_gaps({"a": paper("Auth")}, 2026, TAXONOMY)
        forensics = next(g for g in gaps if g["subarea"] == "Forensics" and g["kind"] == "thin")
        self.assertEqual(forensics["text"], "No scored papers on Forensics")

    def test_open_questions_heading_anywhere_in_title(self):
        # check_report accepts "Open Questions" anywhere in the heading; so must this.
        (self.dir / "report.tex").write_text(REPORT.replace(
            r"\section{Open Questions and Gaps}", r"\section{Gaps and Open Questions}"))
        self.assertEqual(len(kg_gaps.report_index(self.dir, self.entries)["open_questions"]), 2)

    def test_latex_spacing_and_citealp(self):
        bib = {"k": {"author": "Nair, V. and Smith, A. and Lee, B.", "year": "2023"}}
        self.assertEqual(kg_gaps.latex_to_text(r"XR:\ State\\of the Art", bib),
                         "XR: State of the Art")
        self.assertEqual(kg_gaps.latex_to_text(r"(for example \citealp{k})", bib),
                         "(for example Nair et al., 2023)")
        self.assertEqual(kg_gaps.latex_to_text(r"\citealt{k}", bib), "Nair et al. 2023")

    def test_cited_identifiers_cover_every_bib_entry(self):
        self.assertIn("url:example.org/x", self.index["cited_ids"])


if __name__ == "__main__":
    unittest.main()
