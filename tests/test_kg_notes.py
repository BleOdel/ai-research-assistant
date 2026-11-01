import copy
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools"))
import kg_notes  # noqa: E402

NOTE = {"id": "n-20261101-a1b2c3", "title": "Gaze noise: \"defences\" <b>",
        "links": ["paper:10.1/x", "subarea:XR/Immersive::Eye/gaze"],
        "in_report": None, "dismissed": [], "created": "2026-11-01T10:00:00Z",
        "updated": "2026-11-01T10:05:00Z", "archived": None,
        "body": "Claim: one line.\n\n---\nnot front matter", "extra": []}


class NoteFormatTests(unittest.TestCase):
    def test_round_trip(self):
        self.assertEqual(kg_notes.parse(kg_notes.render(NOTE)), NOTE)

    def test_hand_edits_are_read_and_kept(self):
        text = "---\nid: n-20261101-a1b2c3\ntitle: Plain words, no quotes\nmood: \"curious\"\nlinks: []\n---\nBody\n"
        n = kg_notes.parse(text)
        self.assertEqual(n["title"], "Plain words, no quotes")
        self.assertEqual(n["extra"], ['mood: "curious"'])
        self.assertIn('mood: "curious"', kg_notes.render(n))
        self.assertEqual(n["dismissed"], [])          # missing fields take their defaults

    def test_unreadable_files_are_reported_not_dropped(self):
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d)
        (d / "n-20261101-a1b2c3.md").write_text(kg_notes.render(NOTE))
        (d / "n-20261101-ffffff.md").write_text("no front matter at all")
        (d / "n-20261101-eeeeee.md").write_text("---\nid: n-20261101-eeeeee\nlinks: [unclosed\n---\n")
        notes, bad = kg_notes.load(d)
        self.assertEqual([n["id"] for n in notes], ["n-20261101-a1b2c3"])
        self.assertEqual(sorted(b["file"].rsplit("/", 1)[1] for b in bad),
                         ["n-20261101-eeeeee.md", "n-20261101-ffffff.md"])
        self.assertTrue(all(b["error"] for b in bad))

    def test_wrong_types_are_unreadable_not_loaded(self):
        # Review: "updated: 20261101" crashed the whole build; "links: paper:abc" (a plain
        # string) broke the satellites, the list and Status; an id that is not a note id
        # loaded a note that could never be saved.
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d)
        good = kg_notes.render(NOTE)
        (d / "n-20261101-a1b2c3.md").write_text(good)
        (d / "n-20261101-aaaaa1.md").write_text(good.replace('"n-20261101-a1b2c3"', '"n-20261101-aaaaa1"').replace('updated: "2026-11-01T10:05:00Z"', "updated: 20261101"))
        (d / "n-20261101-aaaaa2.md").write_text(good.replace('"n-20261101-a1b2c3"', '"n-20261101-aaaaa2"').replace('links: ["paper:10.1/x", "subarea:XR/Immersive::Eye/gaze"]', "links: paper:abc"))
        (d / "foo.md").write_text(good.replace('"n-20261101-a1b2c3"', '"foo"'))
        notes, bad = kg_notes.load(d)
        self.assertEqual([n["id"] for n in notes], ["n-20261101-a1b2c3"])
        self.assertEqual(len(bad), 3)
        self.assertTrue(all(b["error"] for b in bad))

    def test_validation(self):
        self.assertEqual(kg_notes.validate(NOTE), [])
        for change in ({"id": "../etc/passwd"}, {"title": ""}, {"title": "x" * 201}, {"links": ["http://x"]},
                       {"body": "x" * 200_001}, {"updated": "yesterday"}):
            self.assertTrue(kg_notes.validate({**NOTE, **change}), change)

    def test_ids_and_versions(self):
        self.assertRegex(kg_notes.new_id("2026-11-01"), r"^n-20261101-[0-9a-f]{6}$")
        self.assertEqual(len(kg_notes.version("abc")), 16)
        self.assertNotEqual(kg_notes.version("abc"), kg_notes.version("abd"))
        # Review: "$" let a trailing newline through, and "\d" let in other scripts' digits.
        for bad in ("n-20261101-abcdef\n", "n-\uff12\uff10\uff12\uff16\uff11\uff11\uff10\uff11-abcdef", "n-20261101-ABCDEF"):
            self.assertIsNone(kg_notes.ID_RE.match(bad), repr(bad))
            self.assertIn("the note id is not valid", kg_notes.validate({"id": bad, "title": "T", "links": [], "dismissed": []}))
        self.assertIsNotNone(kg_notes.ID_RE.match("n-20261101-abcdef"))

    def test_prompts_file(self):
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d)
        self.assertEqual(kg_notes.load_prompts(d), [])
        (d / "guide.json").write_text("not json")
        self.assertEqual(kg_notes.load_prompts(d), [])
        (d / "guide.json").write_text('[{"name": "Method", "question": "How?"}, {"bad": 1}]')
        self.assertEqual(kg_notes.load_prompts(d), [{"name": "Method", "question": "How?"}])


if __name__ == "__main__":
    unittest.main()


MARKS = [{"id": "m-00000a", "kind": "pen", "colour": 0, "width": 1, "pts": [[0.1, 0.2], [0.3, 0.4], [0.5, 0.1]]},
         {"id": "m-00000b", "kind": "rect", "colour": 1, "width": 0, "pts": [[-0.5, -0.5], [0.2, 0.3]]},
         {"id": "m-00000c", "kind": "ellipse", "colour": 2, "width": 2, "pts": [[0, 0], [0.4, 0.2]]},
         {"id": "m-00000d", "kind": "arrow", "colour": 3, "width": 1, "pts": [[0, 0], [0.4, 0.2]], "snap": "paper:abc"},
         {"id": "m-00000e", "kind": "text", "colour": 4, "width": 0, "pts": [[0.6, -0.2]], "text": "Gaze cluster"}]
VIEW = {"id": "v-20261101-a1b2c3", "name": "Whole library · 1 Nov", "created": "2026-11-01T10:00:00Z",
        "updated": "2026-11-01T10:05:00Z", "camera": {"yaw": -0.6, "pitch": 0.2, "zoom": 1, "panX": 0, "panY": 0},
        "filters": {"sets": {}, "yMin": None, "yMax": None, "u": True, "n": False, "o": False, "a": False}, "marks": MARKS}


class AnnotationFormatTests(unittest.TestCase):
    def test_a_good_document_validates_and_loads(self):
        self.assertEqual(kg_notes.validate_annotations({"views": [VIEW]}), [])
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d)
        self.assertEqual(kg_notes.load_annotations(d), ({"views": []}, None, None))
        (d / "annotations.json").write_text(json.dumps({"views": [VIEW]}))
        doc, ver, err = kg_notes.load_annotations(d)
        self.assertEqual((doc["views"][0]["id"], len(ver), err), ("v-20261101-a1b2c3", 16, None))

    def test_bad_documents_are_refused(self):
        def broken(fn):
            v = copy.deepcopy(VIEW)
            fn(v)
            return {"views": [v]}
        for doc in (broken(lambda v: v.update(id="../x")), broken(lambda v: v.update(name="")),
                    broken(lambda v: v.update(name="x" * 81)), broken(lambda v: v["camera"].update(zoom=float("nan"))),
                    broken(lambda v: v["camera"].pop("yaw")), broken(lambda v: v["marks"][0].update(kind="highlighter")),
                    broken(lambda v: v["marks"][0].update(colour=5)), broken(lambda v: v["marks"][1].update(pts=[[0, 0]])),
                    broken(lambda v: v["marks"][4].update(text="x" * 61)), broken(lambda v: v["marks"][0].update(pts=[[0, 0]] * 2001)),
                    broken(lambda v: v["marks"][0].update(pts=[[0, 99]] * 2)), broken(lambda v: v["marks"].append(dict(MARKS[0]))),
                    broken(lambda v: v["marks"][1].update(snap="paper:x")), broken(lambda v: v["marks"][0].update(colour=True)),
                    {"views": [VIEW] * 2}, {"views": "no"}, []):
            self.assertTrue(kg_notes.validate_annotations(doc), doc)

    def test_an_unreadable_file_is_reported(self):
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d)
        (d / "annotations.json").write_text("{not json")
        doc, ver, err = kg_notes.load_annotations(d)
        self.assertEqual(doc, {"views": []})
        self.assertEqual(len(ver), 16)
        self.assertIn("could not be read", err)
        (d / "annotations.json").write_text(json.dumps({"views": "no"}))
        self.assertIn("is not valid", kg_notes.load_annotations(d)[2])
