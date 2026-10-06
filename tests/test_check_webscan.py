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

SOURCE = {
    "title": "Designing for privacy", "url": "https://developers.example.com/privacy/",
    "author": None, "site": "developers.example.com", "date": "2026-07-02",
    "type": "official-docs", "tier": "Core", "score": 80,
    "scores": {"relevance": 80, "authority": 80, "evidence": 80, "recency": 80},
    "independence": "first-party", "summary": "What the platform documents.",
    "keyPoints": ["A point"], "caveat": None,
}
SECOND = {**SOURCE, "title": "Forum thread", "url": "https://forum.example.org/t/1",
          "type": "forum-thread", "tier": "Peripheral", "score": 40,
          "scores": {"relevance": 40, "authority": 40, "evidence": 40, "recency": 40},
          "independence": "unclear", "caveat": "Anonymous thread."}


class CheckWebscanTests(unittest.TestCase):
    """Build a page from the real template into a temp repo and lint it there."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        (self.root / "tools").mkdir()
        for name in ("check_webscan.py", "check_report.py", "state.py"):
            shutil.copy(TOOLS / name, self.root / "tools" / name)
        (self.root / "blog").mkdir()
        shutil.copy(REPO_ROOT / "blog" / "template.html", self.root / "blog" / "template.html")
        self.scan = self.root / "blog" / "topic"
        self.scan.mkdir()
        self.write([SOURCE, SECOND])

    def write(self, sources, synthesis="<p>Findings with <code>xr-spatial-tracking</code>.</p>",
              state=None, standalone=None):
        page = (self.root / "blog" / "template.html").read_text()
        for token, value in {"[TOPIC]": "Topic", "[RUN_DATE]": "2026-10-06",
                             "[SCOPE_NOTE]": "<p>Searched X; excluded Y.</p>",
                             "[SYNTHESIS]": synthesis,
                             "[SOURCES_JSON]": json.dumps(sources).replace("<", "\\u003c")}.items():
            page = page.replace(token, value)
        (self.scan / "index.html").write_text(page)
        (self.scan / "sources.json").write_text(json.dumps(sources if standalone is None else standalone))
        seen = state if state is not None else {
            s["url"]: {"title": s["title"], "status": "included", "first_seen": "2026-10-06",
                       "scores": s["scores"], "independence": s["independence"],
                       "tier": s["tier"], "overall_score": s["score"]} for s in sources}
        (self.root / "blog" / "seen_web_sources.json").write_text(json.dumps({"seen": seen}))

    def edit(self, old, new):
        page = self.scan / "index.html"
        text = page.read_text()
        self.assertIn(old, text)
        page.write_text(text.replace(old, new, 1))

    def lint(self, *args, target=None):
        result = subprocess.run([sys.executable, str(self.root / "tools" / "check_webscan.py"),
                                 str(target or self.scan), "--json", *args],
                                capture_output=True, text=True)
        out = json.loads(result.stdout) if result.stdout else None
        return result.returncode, out, result.stderr

    def assertError(self, fragment):
        code, out, _ = self.lint()
        self.assertEqual(code, 1, out)
        self.assertTrue(any(fragment in e for e in out["errors"]), out["errors"])
        return out

    def test_clean_page_passes_with_no_warnings(self):
        code, out, _ = self.lint()
        self.assertEqual((code, out["errors"], out["warnings"]), (0, [], []))

    def test_leftover_token(self):
        self.edit("<h1>Topic</h1>", "<h1>[TOPIC]</h1>")
        self.assertError("placeholders left")

    def test_literal_lt_in_data_block(self):
        self.edit('"title": "Designing for privacy"', '"title": "Designing <b>for</b> privacy"')
        self.assertError('literal "<"')

    def test_score_tier_must_match_sub_scores(self):
        self.write([{**SOURCE, "tier": "Supporting"}])
        self.assertError("score/tier disagrees")

    def test_flagged_or_peripheral_source_needs_caveat(self):
        self.write([SOURCE, {**SECOND, "caveat": None}])
        self.assertError("no caveat")

    def test_schema_fields_urls_and_dates(self):
        broken = {k: v for k, v in SOURCE.items() if k != "author"}
        self.write([broken, {**SECOND, "url": "javascript:alert(1)", "date": "c. 2024"}])
        out = self.assertError("missing 'author'")
        self.assertTrue(any("not http(s)" in e for e in out["errors"]))
        self.assertTrue(any("never infer a date" in e for e in out["errors"]))

    def test_sources_json_must_match(self):
        self.write([SOURCE, SECOND], standalone=[SOURCE])
        self.assertError("parses to different data")
        (self.scan / "sources.json").unlink()
        self.assertError("sources.json: missing")

    def test_page_must_agree_with_state(self):
        self.write([SOURCE, SECOND], state={})
        self.assertError("not in seen_web_sources.json")
        self.write([SOURCE], state={SOURCE["url"]: {"title": "x", "status": "excluded",
                                                   "first_seen": "2026-10-06"}})
        self.assertError("not 'included'")
        self.write([SOURCE], state={"http://www.developers.example.com/privacy": {
            "title": "x", "status": "included", "first_seen": "2026-10-06",
            "scores": {**SOURCE["scores"], "evidence": 60}, "independence": "first-party",
            "tier": "Core"}})
        self.assertError("differ from seen_web_sources.json")  # matched despite scheme/www/slash

    def test_external_resource(self):
        self.edit("</head>", '<script src="https://cdn.example.com/x.js"></script></head>')
        self.assertError("outside the page")

    def test_empty_synthesis(self):
        self.write([SOURCE, SECOND], synthesis="  ")
        self.assertError("synthesis is missing or empty")

    def test_old_template_comment_and_unlisted_tags_warn(self):
        self.edit("Replace each token below", "Replace these tokens: Topic copied here")
        code, out, _ = self.lint()
        self.assertEqual(code, 0)
        self.assertTrue(any("header comment differs" in w for w in out["warnings"]))
        self.write([SOURCE, SECOND], synthesis="<p>x</p><table><tr><td>y</td></tr></table>")
        _, out, _ = self.lint()
        self.assertTrue(any("tags outside" in w and "table" in w for w in out["warnings"]), out)

    def test_missing_page(self):
        code, _, err = self.lint(target=self.root / "blog" / "nope")
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(err)["code"], "NOT_FOUND")

    def test_documented_invocations_use_real_flags(self):
        flags = {"--json"}
        docs = sorted((REPO_ROOT / ".claude" / "commands").glob("*.md")) + sorted(SKILLS.glob("*.md"))
        seen = 0
        for doc in docs:
            for line in doc.read_text().splitlines():
                for match in re.finditer(r"tools/check_webscan\.py([^`\n]*)", line):
                    seen += 1
                    for flag in re.findall(r"(?<![\w-])(--[a-z][\w-]*)", match.group(1)):
                        self.assertIn(flag, flags, f"{doc.name}: {line.strip()}")
        self.assertGreater(seen, 0, "no command doc tells Claude to run check_webscan.py")


if __name__ == "__main__":
    unittest.main()
