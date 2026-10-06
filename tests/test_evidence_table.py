import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLS = REPO_ROOT / "tools"
SKILLS = REPO_ROOT / ".claude" / "skills" / "research-assistant"

sys.path.insert(0, str(TOOLS))
import evidence_table  # noqa: E402

TEX = r"""\documentclass{article}
\usepackage{hyperref}
\usepackage{natbib}
\usepackage{array,longtable}
\begin{document}
Body~\citep{zeta2024,alpha2025}.
\section{Evidence Basis}
Old hand-made table.
\section*{Appendix}
Kept.
\bibliographystyle{agsm}
\bibliography{references}
\end{document}
"""

BIB = r"""@article{zeta2024,
  author = {Zoe Zeta and Bo Beta}, title = {Z}, journal = {J}, year = {2024},
  evidencebasis = {Primary PDF read via paper-fetch on 2026-10-04; abstract read via openalex-search on 2026-10-01. Disclosure: academic. Caveat: 12.5\% ASR on one model.}
}
@misc{alpha2025,
  author = {Ana {\'A}lvarez}, title = {A}, year = {2025},
  evidencebasis = {Abstract-only evidence basis: paywalled; abstract read via arxiv-search on 2026-10-01. Disclosure: self-evaluating. Caveat: Code at \url{github.com/a_b}.}
}
"""


class EvidenceTableTests(unittest.TestCase):
    """Run the script as /synthesize and /update do, against a temp report."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        (self.root / "tools").mkdir()
        for name in ("evidence_table.py", "check_report.py", "state.py"):
            shutil.copy(TOOLS / name, self.root / "tools" / name)
        self.report = self.root / "reports" / "topic"
        self.report.mkdir(parents=True)
        self.tex, self.bib = self.report / "report.tex", self.report / "references.bib"
        self.tex.write_text(TEX)
        self.bib.write_text(BIB)

    def run_tool(self, *args):
        return subprocess.run([sys.executable, str(self.root / "tools" / "evidence_table.py"),
                               str(self.report), *args], capture_output=True, text=True)

    def rows(self, text):
        return [line for line in text.splitlines() if line.startswith(("\\citet", "Zeta", "Álvarez", "Alvarez"))]

    def test_rows_sorted_by_first_author_with_parsed_cells(self):
        out = self.run_tool()
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(self.rows(out.stdout), [
            r"\citet{alpha2025} & Abstract (arxiv-search) & self-evaluating & "
            r"Code at \url{github.com/a_b} \\",
            r"\citet{zeta2024} & Full text (paper-fetch) & academic & 12.5\% ASR on one model \\",
        ])
        self.assertIn("the PDF was read on 2026-10-04;", out.stdout)

    def test_numbered_style_names_authors_instead_of_citet(self):
        self.tex.write_text(TEX.replace(r"\bibliographystyle{agsm}", r"\bibliographystyle{ieeetr}"))
        out = self.run_tool()
        self.assertIn(r"Zeta and Beta~\citep{zeta2024} & Full text", out.stdout)
        self.assertIn(r"Alvarez~\citep{alpha2025} & Abstract", out.stdout)
        self.assertNotIn(r"\citet", out.stdout)

    def test_numbered_style_with_three_authors_and_route_ending_a_sentence(self):
        self.tex.write_text(TEX.replace(r"\bibliographystyle{agsm}", r"\bibliographystyle{ieeetr}"))
        self.bib.write_text(BIB.replace("Zoe Zeta and Bo Beta", "Zoe Zeta and Bo Beta and Cy Gamma")
                            .replace("abstract read via arxiv-search on 2026-10-01.",
                                     "abstract found via arxiv-search."))
        out = self.run_tool().stdout
        self.assertIn(r"Zeta et al.~\citep{zeta2024}", out)
        self.assertIn("Abstract (arxiv-search) &", out)

    def test_write_replaces_only_the_section_and_is_idempotent(self):
        first = self.run_tool("--write")
        self.assertEqual(first.returncode, 0, first.stderr)
        text = self.tex.read_text()
        self.assertNotIn("Old hand-made table", text)
        self.assertIn("\\section*{Appendix}\nKept.", text)
        self.assertEqual(text.count(r"\begin{longtable}"), 1)
        second = self.run_tool("--write", "--json")
        self.assertFalse(json.loads(second.stdout)["changed"])

    def test_write_inserts_before_bibliographystyle_when_absent(self):
        self.tex.write_text(TEX.replace("\\section{Evidence Basis}\nOld hand-made table.\n", ""))
        self.assertEqual(self.run_tool("--write").returncode, 0)
        text = self.tex.read_text()
        self.assertLess(text.index(r"\section{Evidence Basis}"), text.index(r"\bibliographystyle"))

    def test_generated_report_passes_the_linter_row_check(self):
        self.run_tool("--write")
        lint = subprocess.run([sys.executable, str(self.root / "tools" / "check_report.py"),
                               str(self.report), "--style", "Harvard", "--json"],
                              capture_output=True, text=True)
        errors = json.loads(lint.stdout)["errors"]
        self.assertFalse([e for e in errors if "Evidence Basis" in e or "evidencebasis" in e], errors)

    def test_unescaped_caveat_is_refused(self):
        self.bib.write_text(BIB.replace(r"12.5\% ASR", "12.5% ASR"))
        out = self.run_tool("--json")
        self.assertEqual(out.returncode, 1)
        self.assertTrue(any("zeta2024" in p and "%" in p for p in json.loads(out.stdout)["problems"]))

    def test_unstructured_field_and_bad_label(self):
        self.bib.write_text(BIB.replace(" Disclosure: academic. Caveat: 12.5\\% ASR on one model.", ""))
        self.assertIn(r"\citet{zeta2024} & Full text (paper-fetch) & -- & -- \\", self.run_tool().stdout)
        self.bib.write_text(BIB.replace("Disclosure: academic", "Disclosure: independent"))
        out = self.run_tool("--json")
        self.assertEqual(out.returncode, 1)
        self.assertIn("independent", " ".join(json.loads(out.stdout)["problems"]))

    def test_missing_longtable_or_array_is_refused(self):
        for packages, missing in (("array", "longtable"), ("longtable", "array")):
            self.tex.write_text(TEX.replace("array,longtable", packages))
            out = self.run_tool()
            self.assertEqual(out.returncode, 1)
            self.assertIn(f"does not load {missing}", out.stderr)
        self.tex.write_text(TEX.replace("array,longtable", "tabularx,longtable"))
        self.assertEqual(self.run_tool().returncode, 0)  # tabularx loads array

    def test_biblatex_uses_textcite(self):
        self.tex.write_text(TEX.replace("\\usepackage{natbib}", "\\usepackage[style=authoryear]{biblatex}")
                            .replace("\\bibliographystyle{agsm}\n\\bibliography{references}",
                                     "\\printbibliography"))
        out = self.run_tool("--write")
        self.assertEqual(out.returncode, 0, out.stderr)
        text = self.tex.read_text()
        self.assertIn(r"\textcite{zeta2024} & Full text", text)
        self.assertNotIn(r"\citet", text)
        self.assertIn(r"\section*{Appendix}", text)

    def test_documented_invocations_use_real_flags(self):
        """Every `tools/evidence_table.py ... --flag` in the docs is a real flag."""
        flags = {"--write", "--json"}
        docs = sorted((REPO_ROOT / ".claude" / "commands").glob("*.md")) + sorted(SKILLS.glob("*.md"))
        seen = 0
        for doc in docs:
            for line in doc.read_text().splitlines():
                for match in re.finditer(r"tools/evidence_table\.py([^`\n]*)", line):
                    seen += 1
                    for flag in re.findall(r"(?<![\w-])(--[a-z][\w-]*)", match.group(1)):
                        self.assertIn(flag, flags, f"{doc.name}: {line.strip()}")
        self.assertGreater(seen, 0, "no command doc tells Claude to run evidence_table.py")


if __name__ == "__main__":
    unittest.main()
