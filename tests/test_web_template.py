"""blog/template.html is filled by /websearch with a replace-all of five tokens.
These tests build a page the way the command does and check what the reader gets."""
import json
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = REPO_ROOT / "blog" / "template.html"
HTML_RULES = REPO_ROOT / ".claude" / "skills" / "research-assistant" / "10-html-reports.md"
TOKENS = ("[TOPIC]", "[RUN_DATE]", "[SCOPE_NOTE]", "[SYNTHESIS]", "[SOURCES_JSON]")

HOSTILE = {
    "title": "Benign title</script><script>window.pwned = 1</script>",
    "url": "javascript:alert(1)", "author": None, "site": "example.com", "date": None,
    "type": "opinion", "tier": "Peripheral", "score": 40,
    "scores": {"relevance": 40, "authority": 40, "evidence": 40, "recency": 40},
    "independence": "unclear", "summary": "Ends --> a comment", "keyPoints": ["<b>x</b>"],
    "caveat": "Hostile fixture",
}


def build(sources):
    """Fill the template as 10-html-reports.md says to."""
    page = TEMPLATE.read_text(encoding="utf-8")
    fill = {
        "[TOPIC]": "Topic --> with arrow", "[RUN_DATE]": "2026-10-06",
        "[SCOPE_NOTE]": "<p>Scope --> note</p>", "[SYNTHESIS]": "<p>Synthesis --> prose</p>",
        "[SOURCES_JSON]": json.dumps(sources, ensure_ascii=False).replace("<", "\\u003c"),
    }
    for token, value in fill.items():
        page = page.replace(token, value)
    return page


class WebTemplateTests(unittest.TestCase):
    def setUp(self):
        self.template = TEMPLATE.read_text(encoding="utf-8")

    def test_tokens_appear_only_in_their_slots(self):
        counts = {t: self.template.count(t) for t in TOKENS}
        self.assertEqual(counts, {"[TOPIC]": 2, "[RUN_DATE]": 1, "[SCOPE_NOTE]": 1,
                                  "[SYNTHESIS]": 1, "[SOURCES_JSON]": 1})
        comment = re.search(r"<!--(.*?)-->", self.template, re.S).group(1)
        self.assertFalse([t for t in TOKENS if t in comment],
                         "a bracketed token in the header comment gets the report pasted into it")

    def test_documented_tokens_match_the_template(self):
        documented = re.findall(r"^\| `(\[[A-Z_]+\])` \|", HTML_RULES.read_text(), re.M)
        self.assertEqual(tuple(documented), TOKENS)

    def test_built_page_keeps_the_comment_closed_and_the_data_block_whole(self):
        page = build([HOSTILE])
        self.assertFalse([t for t in TOKENS if t in page])
        header = page[:page.index("<html")]
        for filled in ("Topic --> with arrow", "Scope --> note", "Synthesis --> prose", "Benign title"):
            self.assertNotIn(filled, header, "report content leaked into the header comment")
        self.assertEqual(header.count("-->"), 1, "header comment must close exactly once")
        blocks = re.findall(r'<script id="data" type="application/json">(.*?)</script>', page, re.S)
        self.assertEqual(len(blocks), 1)
        self.assertNotIn("<", blocks[0])
        self.assertEqual(json.loads(blocks[0]), [HOSTILE])
        self.assertNotIn("<script>window.pwned", page)

    def test_template_is_self_contained(self):
        external = re.findall(r'<(?:script|link|img|iframe)[^>]+(?:src|href)="(?!#)[^"]*"', self.template)
        self.assertEqual(external, [])
        self.assertNotRegex(self.template, r"@import|url\(\s*['\"]?https?:")

    def test_links_are_limited_to_http(self):
        self.assertIn(r"/^https?:\/\//i.test(s.url", self.template)


if __name__ == "__main__":
    unittest.main()
