import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "tools" / "check_report.py"

sys.path.insert(0, str(REPO_ROOT / "tools"))
import check_report  # noqa: E402  (imported for its style table)

TEX = r"""\documentclass{article}
\usepackage[numbers]{natbib}
\begin{document}
\noindent\textit{Search scope: arXiv, queried 2026-10-01. Two sources: one Core, one
Supporting.}
\begin{abstract}Abstract~\citep{a}.\end{abstract}
\section*{Revision History}
\paragraph{2026-10-01} Initial synthesis.
\section{Findings} Body~\citep{b}.
\section{Technical Findings (Plain Language)} Plain.
\section{Open Questions} Open.
\section{Evidence Basis} Table.
\bibliographystyle{ieeetr}
\bibliography{references}
\end{document}
"""

BIB = """@article{a,
  author = {A. Author}, title = {First}, journal = {J}, year = {2020},
  evidencebasis = {Abstract-only evidence basis: paywalled}
}
@article{b,
  author = {B. Author}, title = {Second}, journal = {J}, year = {2021},
  evidencebasis = {Full text read via paper-fetch}, note = {NDSS Symposium}
}
"""


class ReportFixture(unittest.TestCase):
    """A temp repo with check_report.py, a profile, and one clean IEEE report.

    Each test breaks one thing and asserts on the script's real exit code and
    JSON output, run as a subprocess the way /synthesize invokes it.
    """

    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        (self.root / "tools").mkdir()
        shutil.copy(SCRIPT, self.root / "tools" / "check_report.py")
        self.profile = self.root / ".claude/skills/research-assistant/01-researcher-profile.md"
        self.profile.parent.mkdir(parents=True)
        self.set_profile_style("IEEE (framework default)")
        self.report = self.root / "reports" / "topic"
        self.report.mkdir(parents=True)
        self.tex, self.bib = self.report / "report.tex", self.report / "references.bib"
        self.tex.write_text(TEX)
        self.bib.write_text(BIB)

    def set_profile_style(self, value):
        self.profile.write_text(f"## Output Preferences\n- **Citation style:** {value}\n")

    def edit_tex(self, old, new):
        text = self.tex.read_text()
        self.assertIn(old, text)
        self.tex.write_text(text.replace(old, new, 1))

    def check(self, *extra):
        result = subprocess.run(
            [sys.executable, str(self.root / "tools" / "check_report.py"),
             str(self.report), "--json", *extra],
            capture_output=True, text=True)
        return result.returncode, json.loads(result.stdout)

    def assertError(self, fragment, *extra):
        code, out = self.check(*extra)
        self.assertEqual(code, 1, out)
        self.assertTrue(any(fragment in e for e in out["errors"]),
                        f"{fragment!r} not in {out['errors']}")
        return out


class StaticTests(ReportFixture):
    def test_clean_report_passes(self):
        code, out = self.check()
        self.assertEqual((code, out["errors"], out["warnings"]), (0, [], []))

    def test_missing_evidence_basis_section(self):
        self.edit_tex(r"\section{Evidence Basis} Table.", "")
        self.assertError("no Evidence Basis section")

    def test_missing_revision_history(self):
        self.edit_tex("\\section*{Revision History}\n\\paragraph{2026-10-01} Initial synthesis.", "")
        self.assertError("no Revision History")

    def test_revision_history_needs_a_dated_entry(self):
        self.edit_tex(r"\paragraph{2026-10-01}", r"\paragraph{Initial}")
        self.assertError("no dated")

    def test_missing_open_questions_and_scope(self):
        self.edit_tex(r"\section{Open Questions} Open.", "")
        self.edit_tex("Search scope", "Coverage")
        out = self.assertError("no Open Questions")
        self.assertTrue(any("search-scope" in e for e in out["errors"]))

    def test_scope_without_tier_composition_is_a_warning(self):
        self.edit_tex("Two sources: one Core, one\nSupporting.", "Two sources.")
        code, out = self.check()
        self.assertEqual(code, 0)
        self.assertTrue(any("composition" in w for w in out["warnings"]))

    def test_missing_evidencebasis_field_lists_keys(self):
        self.bib.write_text(BIB.replace("evidencebasis = {Abstract-only evidence basis: paywalled}",
                                        "note = {x}"))
        out = self.assertError("no evidencebasis")
        self.assertTrue(any(e.endswith(": a") for e in out["errors"]))

    def test_evidence_commentary_in_note_is_an_error(self):
        self.bib.write_text(BIB.replace("note = {NDSS Symposium}",
                                        "note = {Abstract-only evidence basis: paywalled}"))
        self.assertError("note fields holding evidence-basis commentary")

    def test_long_note_is_a_warning(self):
        self.bib.write_text(BIB.replace("note = {NDSS Symposium}", "note = {" + "x" * 150 + "}"))
        code, out = self.check()
        self.assertEqual(code, 0)
        self.assertTrue(any("over 100 characters" in w for w in out["warnings"]))

    def test_cite_without_bib_entry(self):
        self.edit_tex(r"Body~\citep{b}", r"Body~\citep{b,ghost}")
        self.assertError("cited but not in references.bib")

    def test_unused_bib_entry_unless_nocite_star(self):
        self.edit_tex(r"Body~\citep{b}", "Body")
        self.assertError("never cited")
        self.edit_tex(r"\bibliographystyle", "\\nocite{*}\n\\bibliographystyle")
        self.assertEqual(self.check()[0], 0)

    def test_style_must_match_profile(self):
        self.set_profile_style("Harvard (agsm)")
        self.assertError("citation style is Harvard")

    def test_style_flag_overrides_profile(self):
        self.set_profile_style("Harvard (agsm)")
        self.assertEqual(self.check("--style", "IEEE")[0], 0)

    def test_unknown_style_name(self):
        self.assertError("unknown citation style", "--style", "Chicago")

    def test_numbered_style_needs_numbers_option(self):
        self.edit_tex(r"\usepackage[numbers]{natbib}", r"\usepackage{natbib}")
        self.assertError("needs the [numbers] option")

    def test_author_year_style_must_not_have_numbers(self):
        self.edit_tex(r"\bibliographystyle{ieeetr}", r"\bibliographystyle{agsm}")
        self.assertError("must not have [numbers]", "--style", "Harvard")

    def test_harvard_report_passes(self):
        self.edit_tex(r"\usepackage[numbers]{natbib}", r"\usepackage{natbib}")
        self.edit_tex(r"\bibliographystyle{ieeetr}", r"\bibliographystyle{agsm}")
        self.assertEqual(self.check("--style", "Harvard")[0], 0)

    def test_citet_with_numbered_style(self):
        self.edit_tex(r"Body~\citep{b}", r"\citet{b} said")
        self.assertError("(author?)")

    def test_commented_out_text_is_ignored(self):
        self.edit_tex(r"\bibliographystyle{ieeetr}", "% \\citet{b}\n\\bibliographystyle{ieeetr}")
        self.assertEqual(self.check()[0], 0)

    def test_H_float_needs_float_package(self):
        self.edit_tex(r"\section{Evidence Basis} Table.",
                      "\\section{Evidence Basis}\n\\begin{table}[H]x\\end{table}")
        self.assertError("[H] placement")
        self.edit_tex(r"\usepackage[numbers]{natbib}",
                      "\\usepackage[numbers]{natbib}\n\\usepackage{float}")
        self.assertEqual(self.check()[0], 0)

    def test_report_dir_or_tex_path_both_work(self):
        result = subprocess.run([sys.executable, str(self.root / "tools" / "check_report.py"),
                                 str(self.tex)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout)


@unittest.skipUnless(shutil.which("pdflatex") and shutil.which("bibtex"), "needs a TeX install")
class CompileTests(ReportFixture):
    def test_clean_report_compiles_and_leaves_nothing_behind(self):
        code, out = self.check("--compile")
        self.assertEqual((code, out["errors"]), (0, []))
        self.assertEqual(sorted(p.name for p in self.report.iterdir()),
                         ["references.bib", "report.tex"])

    def test_visible_overfull_box_is_an_error(self):
        self.edit_tex("Plain.", r"\noindent\texttt{" + "x" * 120 + "}")
        self.assertError("overfull box", "--compile")


class StyleTableDriftTests(unittest.TestCase):
    """check_report.STYLES must match 04-citation-rules.md."""

    def test_style_table(self):
        doc = (REPO_ROOT / ".claude/skills/research-assistant/04-citation-rules.md").read_text()
        rows = dict(re.findall(r"^\| ([\w/-]+) \| `(\w+)`", doc, re.M))
        self.assertEqual(rows, {name: bst for name, (bst, _) in check_report.STYLES.items()})

    def test_numbered_vs_author_year(self):
        doc = (REPO_ROOT / ".claude/skills/research-assistant/04-citation-rules.md").read_text()
        numbered = re.findall(r"`(\w+)`", re.search(r"numbered styles \(([^)]*)\)", doc).group(1))
        author_year = re.findall(r"`(\w+)`",
                                 re.search(r"author-year styles \(([^)]*)\)", doc).group(1))
        expected_numbered = sorted(b for b, n in check_report.STYLES.values() if n)
        expected_author_year = sorted(b for b, n in check_report.STYLES.values() if not n)
        self.assertEqual(sorted(numbered), expected_numbered)
        self.assertEqual(sorted(author_year), expected_author_year)


class RealExampleTest(unittest.TestCase):
    """report/report_example.tex is what /synthesize copies - it must pass."""

    def test_example_passes_statically(self):
        result = subprocess.run([sys.executable, str(SCRIPT), str(REPO_ROOT / "report"),
                                 "--style", "IEEE", "--json"], capture_output=True, text=True)
        out = json.loads(result.stdout)
        self.assertEqual((result.returncode, out["errors"]), (0, []))


if __name__ == "__main__":
    unittest.main()
