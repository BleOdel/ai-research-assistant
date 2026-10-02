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


HARVARD_PREAMBLE = ("\\usepackage{hyperref}\n\\usepackage{natbib}\n"
                    + check_report.HARVARD_URL_FIX)


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

    def make_harvard(self, preamble=HARVARD_PREAMBLE):
        self.edit_tex(r"\usepackage[numbers]{natbib}", preamble)
        self.edit_tex(r"\bibliographystyle{ieeetr}", r"\bibliographystyle{agsm}")
        self.set_profile_style("Harvard (agsm)")

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

    def test_unbraced_acronym_in_title_is_a_warning(self):
        self.bib.write_text(BIB.replace("title = {First}", "title = {Securing LLM Agents}"))
        code, out = self.check()
        self.assertEqual(code, 0)
        self.assertTrue(any("outside braces" in w and w.endswith(": a")
                            for w in out["warnings"]), out["warnings"])

    def test_braced_names_and_hyphenated_title_case_pass(self):
        self.bib.write_text(BIB.replace(
            "title = {First}",
            "title = {{AgentDojo}: A Rule-Based Defense for {LLM} Agents}"))
        code, out = self.check()
        self.assertEqual((code, out["warnings"]), (0, []))

    def test_unprotected_caps_ignores_braced_text(self):
        f = check_report.unprotected_caps
        self.assertEqual(f("{MELON}: Provable Defense in {AI} Agents"), [])
        self.assertEqual(f("Order-Oblivious Prompt Injection"), [])
        self.assertEqual(f("MELON and AgentDojo for LLM-Integrated Apps"),
                         ["MELON", "AgentDojo", "LLM-Integrated"])

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
        self.make_harvard()
        code, out = self.check()
        self.assertEqual((code, out["errors"], out["warnings"]), (0, [], []))

    def test_harvard_without_harvardurl_override(self):
        self.make_harvard("\\usepackage{hyperref}\n\\usepackage{natbib}")
        self.assertError("\\harvardurl")

    def test_harvardurl_override_must_use_url(self):
        self.make_harvard("\\usepackage{natbib}\n"
                          "\\renewcommand{\\harvardurl}[1]{\\textbf{URL:} \\textit{#1}}")
        self.assertError("breaks the build on any URL")

    def test_harvardurl_override_before_natbib(self):
        self.make_harvard("\\usepackage{hyperref}\n" + check_report.HARVARD_URL_FIX
                          + "\n\\usepackage{natbib}")
        self.assertError("comes before \\usepackage{natbib}")

    def test_harvardurl_override_needs_hyperref_or_url(self):
        self.make_harvard("\\usepackage{natbib}\n" + check_report.HARVARD_URL_FIX)
        self.assertError("neither hyperref nor url")
        self.edit_tex(r"\usepackage{natbib}", "\\usepackage{url}\n\\usepackage{natbib}")
        self.assertEqual(self.check()[0], 0)

    def test_harvardurl_one_argument_form_is_a_warning(self):
        self.make_harvard("\\usepackage{hyperref}\n\\usepackage{natbib}\n"
                          "\\renewcommand{\\harvardurl}[1]{\\textbf{URL:} \\url{#1}}")
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertTrue(any("still fails on % and #" in w for w in out["warnings"]), out)

    def test_harvardurl_check_is_harvard_only(self):
        self.edit_tex(r"\usepackage[numbers]{natbib}", r"\usepackage{natbib}")
        self.edit_tex(r"\bibliographystyle{ieeetr}", r"\bibliographystyle{apalike}")
        self.assertEqual(self.check("--style", "APA")[0], 0)

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

    TALL_ROWS = "\n".join(f"Row {i} & value {i}\\\\" for i in range(70))

    def tall_table(self, placement):
        self.edit_tex(r"\section{Evidence Basis} Table.",
                      "\\section{Evidence Basis}\n\\begin{table}" + placement + "\\centering\n"
                      "\\begin{tabular}{ll}\n" + self.TALL_ROWS + "\n\\end{tabular}\\end{table}")

    def test_H_float_taller_than_page_is_an_error(self):
        # Logged as "Overfull \vbox (...pt too high) has occurred while \output is active"
        self.edit_tex(r"\usepackage[numbers]{natbib}",
                      "\\usepackage[numbers]{natbib}\n\\usepackage{float}")
        self.tall_table("[H]")
        out = self.assertError("overfull vbox", "--compile")
        self.assertTrue(any("longtable" in e for e in out["errors"]), out)

    def test_placed_float_taller_than_page_is_an_error(self):
        # Logged as "Float too large for page by ...pt"
        self.tall_table("[ht]")
        out = self.assertError("float too large for page", "--compile")
        self.assertTrue(any("longtable" in e for e in out["errors"]), out)

    def test_long_table_as_longtable_passes(self):
        self.edit_tex(r"\usepackage[numbers]{natbib}",
                      "\\usepackage[numbers]{natbib}\n\\usepackage{longtable}")
        self.edit_tex(r"\section{Evidence Basis} Table.",
                      "\\section{Evidence Basis}\n\\begin{longtable}{ll}\n"
                      + self.TALL_ROWS + "\n\\end{longtable}")
        code, out = self.check("--compile")
        self.assertEqual((code, out["errors"]), (0, []))


@unittest.skipUnless(shutil.which("pdflatex") and shutil.which("bibtex")
                     and subprocess.run(["kpsewhich", "agsm.bst"], capture_output=True,
                                        text=True).stdout.strip(),
                     "needs a TeX install with the harvard bundle (agsm.bst)")
class HarvardCompileTests(ReportFixture):
    """agsm prints URLs via \\harvardurl; these URLs broke a real report's build."""

    URLS = {"a": "https://example.com/attack_surface_v2",
            "b": "https://example.com/a%20b/page#sec_1"}

    def setUp(self):
        super().setUp()
        bib = BIB
        for key, url in self.URLS.items():
            bib = bib.replace(f"@article{{{key},\n", f"@article{{{key},\n  url = {{{url}}},\n")
        self.bib.write_text(bib)

    def test_underscore_url_breaks_without_override(self):
        self.make_harvard("\\usepackage{hyperref}\n\\usepackage{natbib}")
        self.assertError("Missing $ inserted", "--compile")

    def test_underscore_percent_and_hash_urls_compile_with_override(self):
        self.make_harvard()
        code, out = self.check("--compile")
        self.assertEqual((code, out["errors"]), (0, []))


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


class HarvardUrlFixDriftTests(unittest.TestCase):
    """The override check_report.py demands is the one the docs tell /synthesize to write."""

    def test_docs_quote_the_override(self):
        for doc in (".claude/skills/research-assistant/04-citation-rules.md",
                    ".claude/skills/research-assistant/03-report-templates.md", "SETUP.md"):
            self.assertIn(check_report.HARVARD_URL_FIX, (REPO_ROOT / doc).read_text(), doc)


class RealExampleTest(unittest.TestCase):
    """report/report_example.tex is what /synthesize copies - it must pass."""

    def test_example_passes_statically(self):
        result = subprocess.run([sys.executable, str(SCRIPT), str(REPO_ROOT / "report"),
                                 "--style", "IEEE", "--json"], capture_output=True, text=True)
        out = json.loads(result.stdout)
        self.assertEqual((result.returncode, out["errors"]), (0, []))


if __name__ == "__main__":
    unittest.main()
