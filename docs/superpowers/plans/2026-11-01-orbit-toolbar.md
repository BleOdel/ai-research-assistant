# Library Map, Part 3: The Annotation Toolbar - Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the researcher mark up the research globe the way they would a slide (pen, shapes, arrows that snap to a dot, short labels), with marks that belong to a saved view, save themselves, can be turned into notes, and can be saved as a picture.

**Architecture:** `tools/kg_notes.py` gains the annotations file format (`notes/annotations.json`: saved views, each with its camera, filters and marks), and `tools/kg_serve.py` one more write route for it, with the same token, lock and conflict rules as notes. Two new page parts: `marks.js` (the model: geometry in globe units, views, undo history, drawing and hit-testing, the save client) and `annotate.js` (the toolbar, the tools' pointer handling, the "Back to it" chip, views in the notes list, Make a note from this, Save as image). The globe gives the toolbar its pointer through one new hook, `GL.input`, and draws the marks as an overlay.

**Tech Stack:** Python 3 stdlib, `unittest`; plain browser JavaScript on the existing 2D canvas; node for page-logic tests; the Browser pane for real-browser checks.

**Spec:** `docs/superpowers/specs/2026-10-30-library-map-orbit-design.md`, sections "Annotation toolbar" (tools table, "Saved views, saved automatically", the helper fallback, designer's call 6 and 16), "Where notes live" (annotations through the helper), "Minimising" (the toolbar is a card that minimises to a chip), "Constraints" and "Anti-goals". Parts 1 and 2 are on master (4adfb04); read `graph/README.md` for how the page is put together, and Part 2's plan for the helper's rules.

## Global Constraints

- Stdlib Python only; the page stays one offline file; the only network use is the local helper on 127.0.0.1.
- Annotations live in `notes/annotations.json`, inside the gitignored `notes/` (`notes/*` is already required by `tools/security_guards.py`). `/reset notes` already deletes the file (`.claude/commands/reset.md` line 363); keep it that way.
- The helper writes only inside `notes/`, through a fixed set of operations; this plan adds exactly one, save annotations. Writes are atomic (`state.atomic_write` under `state.Lock`), need the token in `X-KG-Token`, a local `Host` and no foreign `Origin` (the existing `check_host`/`require_header_token`).
- A save over a file changed since the page loaded it is refused (409) and the page shows the choice; a file that cannot be read is never overwritten; a file deleted elsewhere is never silently recreated.
- Nothing is lost silently: without the helper, marks work for the session, the toolbar says plainly they will not be kept, and Save as image is offered.
- Five fixed mark colours, distinct from the interest colours (designer's call 16). One tool at a time, the active one highlighted, Esc returns to Select.
- Every string from the data or the file reaches the page as text (`el()`, `textContent`, canvas `fillText`), never HTML.
- Not in this version (spec): highlighter, sticky pins on dots, compare-two-dots.
- Profile-agnostic: no interest or sub-area names in code.
- Browser storage (through `store`) holds conveniences only (toolbar position, minimised state, last tool); never marks.
- Existing tests keep passing. Commits end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Work in the worktree `~/ara-orbit-toolbar` (branch `orbit-toolbar`, from `~/.ai-research-assistant-build`); never commit from the working clone.

Decisions this plan makes where the spec leaves the builder a choice:

- **Mark coordinates are in globe units**, `u = (x - cx) / R`, `v = (y - cy) / R`, taken from `globeGeometry()` when drawn. A resized window or a card that changes the globe's insets moves and scales the marks with the globe, so they stay on what they marked.
- **A view is its camera and its filters.** The camera is `GL.yaw, pitch, zoom, panX, panY`; the filters are the hash's filter state (`filterState()`, extracted in Task 3). A view is active when both match the page's within tolerance (angles 0.002 rad, zoom 0.2 %, pan 1 px; filters by a stable key). The first mark drawn where no view is active creates one; later marks there join it. Marks are drawn only for the active view.
- **The default name** is `<filter summary> · <date>`: one interest shown gives its name; several give "N interests"; none filtered gives "Whole library"; a Papers only or Web only choice adds "papers only" or "web only". Example: "XR/Immersive Systems Security & Privacy · papers only · 1 Nov". Names can be renamed (80 characters at most).
- **"Drag across dots to select a group of papers" is Shift+drag in Select.** A plain drag in Select still turns or moves the globe as the navigation toolbar says, so a drag never does something unexpected; the toolbar's hint line says "Shift+drag across dots to pick papers" whenever Select is active. The picked items (papers and web sources in view, on the near side) become the page's highlight, "Highlighted: picked on the globe · N shown", using the existing `highlightSet`.
- **What a mark holds**, for "Make a note from this": the visible near-side items inside a rectangle, an ellipse, or a pen stroke treated as a closed loop; an arrow holds the dot it snapped to; a text label holds nothing. A note starts linked to at most 100 of them, highest scored first, and the toolbar says so when it trims ("Linked the 100 highest-scored of 340 items in the mark.").
- **"＋ Note"** links, in order of preference: the selected mark's items; else the highlight; else the selected item; else nothing.
- **Colours:** tokens `--mk1`..`--mk5`, named Ink, Red, Lime, Green, Violet. Dark: `--ink`'s value, `#ff2d55`, `#a3e635`, `#40e040`, `#b45cff`. Light: `--ink`'s value, `#d70f3a`, `#5e8f00`, `#128a12`, `#8a2be2`. In dark mode every chromatic mark colour is at least 25 degrees of hue from each interest colour and both citation-line colours, and at least 30 degrees from each other.
- **Line widths:** Thin, Medium, Thick = 2, 4, 7 px, for the pen and the shapes. Labels are 14 px, at most 60 characters ("Anything longer belongs in a note").
- **Undo/redo** keeps up to 100 steps of whole-view snapshots, so undoing a view's first mark also removes the view it created.
- **Saving** is the whole file, 800 ms after the last change, one save at a time (the `saveDraft` pattern). The file is limited to 4 MB, 200 views, 500 marks a view, 2,000 points a mark; the pen drops points closer than 2 px.
- **The toolbar** sits at the bottom centre by default (the navigation toolbar's default moves to the bottom right; saved positions are kept). Close and minimise both collapse it to a chip "▸ Draw"; `M` includes it.
- **The chip** "Annotated view: <name> · Back to it" shows whenever a view with marks exists and is not the active one; it names the most recently active or updated view. "Back to it" restores the filters, then turns the globe to the camera.
- **Views in the notes list** appear as a "Views" filter chip; each row shows the name, marks, date, and Go to / Rename / Delete (delete asks first).

## Review Focus

1. **The window is resized, or a card opens, after marks are drawn.** The marks stay on the dots they marked. Test in Task 3 (`test_marks_follow_the_globe`).
2. **The same marks edited in two tabs.** The second save gets a conflict, nothing is overwritten, and the toolbar offers Keep mine / Use the file's. Tests in Tasks 2 and 3.
3. **No helper (page opened from disk, or the helper stopped).** Drawing still works, no request is sent while saving is off, the toolbar says marks are not kept, and Save as image works. Test in Task 3 (`test_marks_without_the_helper`).
4. **A hand-broken `notes/annotations.json`.** It is never overwritten; the page says why it cannot save marks; Status names the file. Tests in Tasks 1, 2 and 6.
5. **A view from an older library**: its filters name an interest the library no longer has, or an arrow snapped to a paper that is gone. "Back to it" restores what still exists without an error, and the arrow draws at its stored end. Test in Task 5 (`test_old_views_still_open`).

---

## File Structure

| File | Responsibility |
|---|---|
| `tools/kg_notes.py` (modify) | Annotations format: limits, `validate_annotations`, `load_annotations` |
| `tools/kg_serve.py` (modify) | `POST /api/annotations`; annotations in `/api/state` |
| `tools/knowledge_graph.py` (modify) | Embed `annotations`, `annotationsError` in the build |
| `graph/parts/marks.js` (create) | Model: units, cameras, views, names, geometry, hit-tests, history, drawing, save client |
| `graph/parts/annotate.js` (create) | Toolbar, tools, pointer handling, chip, views in the list, notes from marks, Save as image |
| `graph/parts/globe.js` (modify) | `GL.input` hook; navigation toolbar's default position |
| `graph/template.html` (modify) | Toolbar markup and styles, `--mk1..5` tokens, part tags, `filterState`/`filtersFromState`, Esc order |
| `graph/parts/notes.js`, `status.js` (modify) | Load marks with the notes; Views chip in the list; Status row |
| `graph/README.md`, `USAGE.md`, `README.md`, the spec's Build status (modify) | How to draw on the map |
| `tests/test_kg_notes.py`, `tests/test_kg_serve.py`, `tests/test_knowledge_graph.py`, `tests/test_graph_template.py` (modify) | Tests |

---

### Task 1: The annotations file format, and annotations in the build

**Files:**
- Modify: `tools/kg_notes.py`, `tools/knowledge_graph.py` (`build`, next to the notes keys)
- Test: `tests/test_kg_notes.py`, `tests/test_knowledge_graph.py`

**Interfaces:**
- Produces in `kg_notes`:
  - `ANNOTATIONS = "annotations.json"`; `MAX_VIEWS, MAX_MARKS, MAX_POINTS, MAX_VIEW_NAME, MAX_LABEL, MAX_ANNOT_BYTES = 200, 500, 2000, 80, 60, 4 * 1024 * 1024`;
  - `VIEW_ID_RE = re.compile(r"^v-[0-9]{8}-[0-9a-f]{6}\Z")`, `MARK_ID_RE = re.compile(r"^m-[0-9a-f]{6}\Z")`, `MARK_KINDS = ("pen", "rect", "ellipse", "arrow", "text")`;
  - `validate_annotations(doc) -> list[str]`, the plain-words problems;
  - `load_annotations(folder: Path) -> tuple[dict, str | None, str | None]`, which returns `(doc, version, error)`. A missing file gives `({"views": []}, None, None)`. A file that cannot be read or fails validation gives `({"views": []}, version_of_its_text_or_None, "<why>")`. A good file gives `(doc, version(text), None)`.
- The document shape (Tasks 2-5 rely on it):
  - `{"views": [view, ...]}`;
  - a view is `{"id", "name", "created", "updated", "camera": {"yaw", "pitch", "zoom", "panX", "panY"}, "filters": {...}, "marks": [mark, ...]}`;
  - a mark is `{"id", "kind", "colour": 0-4, "width": 0-2, "pts": [[u, v], ...], "text"?: str, "snap"?: str | null}`.
- Data block: `data["annotations"]` (the doc; `{"views": []}` for `--synthetic`) and `data["annotationsError"]` (str or null).

- [ ] **Step 1: Write the failing tests**

In `tests/test_kg_notes.py`, new class `AnnotationFormatTests`, with a module-level `VIEW` (one view holding one mark of every kind):

```python
MARKS = [{"id": "m-00000a", "kind": "pen", "colour": 0, "width": 1, "pts": [[0.1, 0.2], [0.3, 0.4], [0.5, 0.1]]},
         {"id": "m-00000b", "kind": "rect", "colour": 1, "width": 0, "pts": [[-0.5, -0.5], [0.2, 0.3]]},
         {"id": "m-00000c", "kind": "ellipse", "colour": 2, "width": 2, "pts": [[0, 0], [0.4, 0.2]]},
         {"id": "m-00000d", "kind": "arrow", "colour": 3, "width": 1, "pts": [[0, 0], [0.4, 0.2]], "snap": "paper:abc"},
         {"id": "m-00000e", "kind": "text", "colour": 4, "width": 0, "pts": [[0.6, -0.2]], "text": "Gaze cluster"}]
VIEW = {"id": "v-20261101-a1b2c3", "name": "Whole library · 1 Nov", "created": "2026-11-01T10:00:00Z",
        "updated": "2026-11-01T10:05:00Z", "camera": {"yaw": -0.6, "pitch": 0.2, "zoom": 1, "panX": 0, "panY": 0},
        "filters": {"sets": {}, "yMin": None, "yMax": None, "u": True, "n": False, "o": False, "a": False}, "marks": MARKS}

def test_a_good_document_validates_and_loads(self):
    self.assertEqual(kg_notes.validate_annotations({"views": [VIEW]}), [])
    d = Path(tempfile.mkdtemp()); self.addCleanup(shutil.rmtree, d)
    self.assertEqual(kg_notes.load_annotations(d), ({"views": []}, None, None))
    (d / "annotations.json").write_text(json.dumps({"views": [VIEW]}))
    doc, ver, err = kg_notes.load_annotations(d)
    self.assertEqual((doc["views"][0]["id"], len(ver), err), ("v-20261101-a1b2c3", 16, None))

def test_bad_documents_are_refused(self):
    import copy
    def broken(fn):
        v = copy.deepcopy(VIEW); fn(v); return {"views": [v]}
    for doc in (broken(lambda v: v.update(id="../x")), broken(lambda v: v.update(name="")),
                broken(lambda v: v.update(name="x" * 81)), broken(lambda v: v["camera"].update(zoom=float("nan"))),
                broken(lambda v: v["camera"].pop("yaw")), broken(lambda v: v["marks"][0].update(kind="highlighter")),
                broken(lambda v: v["marks"][0].update(colour=5)), broken(lambda v: v["marks"][1].update(pts=[[0, 0]])),
                broken(lambda v: v["marks"][4].update(text="x" * 61)), broken(lambda v: v["marks"][0].update(pts=[[0, 0]] * 2001)),
                broken(lambda v: v["marks"][0].update(pts=[[0, 99]] * 2)), broken(lambda v: v["marks"].append(dict(MARKS[0]))),
                {"views": [VIEW] * 2}, {"views": "no"}, []):
        self.assertTrue(kg_notes.validate_annotations(doc), doc)

def test_an_unreadable_file_is_reported(self):
    d = Path(tempfile.mkdtemp()); self.addCleanup(shutil.rmtree, d)
    (d / "annotations.json").write_text("{not json")
    doc, ver, err = kg_notes.load_annotations(d)
    self.assertEqual(doc, {"views": []}); self.assertEqual(len(ver), 16); self.assertIn("could not be read", err)
```

The case `{"views": [VIEW] * 2}` is a duplicate view id. The case appending `MARKS[0]` again is a duplicate mark id. The 99 case is a coordinate beyond ±50.

In `tests/test_knowledge_graph.py`, `BuildTests`: `test_annotations_are_embedded` writes `notes/annotations.json` holding one view, builds, and asserts `data["annotations"]["views"][0]["id"]` and `data["annotationsError"] is None`. Then it writes `"{"` to the file, rebuilds, and asserts `data["annotations"] == {"views": []}` and that `data["annotationsError"]` mentions "annotations.json". Build the view inline (do not import from `test_kg_notes`, which breaks under `discover -s tests`).

- [ ] **Step 2: Run them to see them fail**

Run: `python3 -m unittest tests.test_kg_notes tests.test_knowledge_graph -v 2>&1 | tail -5`
Expected: FAIL (`module 'kg_notes' has no attribute 'validate_annotations'`; no `annotations` key).

- [ ] **Step 3: Implement**

Rules for `validate_annotations`:
- Numbers must be finite (`math.isfinite`, not `bool`). `zoom` is between 1 and 14. Each coordinate is within ±50.
- Points per kind: `rect`, `ellipse` and `arrow` take exactly 2; `text` takes exactly 1; `pen` takes 2 to `MAX_POINTS`.
- `text` is required for `text` marks (1 to `MAX_LABEL` characters) and absent otherwise. `snap` is allowed only on arrows and is a string of at most 300 characters, or null.
- `filters` is a dict whose `json.dumps` is at most 20,000 characters.
- `created` and `updated` use the notes' `_is_iso`.
- View ids are unique in the file; mark ids are unique within a view.

The error for unreadable JSON or bad UTF-8 is "notes/annotations.json could not be read: <reason>". The error for a document that fails validation is "notes/annotations.json is not valid: <first three problems>".

- [ ] **Step 4: Run the tests**

Run: `python3 -m unittest discover -s tests 2>&1 | tail -3`
Expected: OK.

- [ ] **Step 5: Commit**

```bash
git add tools/kg_notes.py tools/knowledge_graph.py tests
git commit -m "annotations: the file format, and annotations in the build"
```

---

### Task 2: The helper saves annotations

**Files:**
- Modify: `tools/kg_serve.py` (`_get` for `/api/state`, `_post` routes, `read_json`)
- Test: `tests/test_kg_serve.py`

**Interfaces:**
- Consumes: Task 1's `load_annotations`, `validate_annotations`, `ANNOTATIONS`, `MAX_ANNOT_BYTES`.
- Produces:
  - `GET /api/state` adds `"annotations"`, `"annotationsVersion"` and `"annotationsError"`.
  - `POST /api/annotations` takes `{"annotations": doc, "version": str | null}`. On success it returns 200 `{"version": str}`.
  - A version mismatch returns 409 `{"error": "Your marks changed somewhere else since this page loaded them.", "conflict": true, "disk": doc, "diskVersion": str}`.
  - A saved file that has since been deleted (version not null, file missing) returns 409 `{"error": "Your saved marks were deleted elsewhere.", "deleted": true}`.
  - An unreadable file returns 409 `{"error": "notes/annotations.json could not be read; fix or remove it first."}`.
  - A document that fails validation returns 400 `"Not saved: <problems>."`.
  - `read_json(self, limit: int = MAX_BODY)`: the annotations route passes `kg_notes.MAX_ANNOT_BYTES`.

- [ ] **Step 1: Write the failing tests** (in `RequestTests`; a small module-level `VIEW` like Task 1's with one rect mark)

```python
def test_annotations_save_and_conflict(self):
    st, r, _ = self.api("/api/annotations", {"annotations": {"views": [VIEW]}, "version": None})
    self.assertEqual(st, 200)
    v1 = r["version"]
    self.assertEqual(json.loads((self.root / "notes" / "annotations.json").read_text())["views"][0]["id"], VIEW["id"])
    _, s, _ = self.call("GET", "/api/state", headers={"X-KG-Token": "tok"})
    self.assertEqual((s["annotationsVersion"], s["annotationsError"]), (v1, None))
    st, r, _ = self.api("/api/annotations", {"annotations": {"views": []}, "version": "stale"})
    self.assertEqual((st, r["conflict"], r["diskVersion"]), (409, True, v1))
    self.assertEqual(len(json.loads((self.root / "notes" / "annotations.json").read_text())["views"]), 1)   # not overwritten

def test_annotations_never_overwrite_a_broken_or_deleted_file(self):
    (self.root / "notes").mkdir(exist_ok=True)
    (self.root / "notes" / "annotations.json").write_text("{hand-broken")
    st, r, _ = self.api("/api/annotations", {"annotations": {"views": []}, "version": None})
    self.assertEqual(st, 409); self.assertIn("could not be read", r["error"])
    self.assertEqual((self.root / "notes" / "annotations.json").read_text(), "{hand-broken")
    (self.root / "notes" / "annotations.json").unlink()
    st, r, _ = self.api("/api/annotations", {"annotations": {"views": []}, "version": "abc"})
    self.assertEqual((st, r.get("deleted")), (409, True))
    self.assertFalse((self.root / "notes" / "annotations.json").exists())

def test_annotations_are_checked(self):
    self.assertEqual(self.api("/api/annotations", {"annotations": {"views": "no"}, "version": None})[0], 400)
    self.assertEqual(self.api("/api/annotations", {"annotations": {"views": []}}, token=None)[0], 403)
    big = {"annotations": {"views": []}, "pad": "x" * (300 * 1024)}
    self.assertEqual(self.api("/api/annotations", big)[0], 200)          # over a note's limit, under the 4 MB one
    self.assertEqual(self.api("/api/note", big)[0], 413)
```

The last test's pad line checks that the route has its own size limit. The `pad` key is ignored.

- [ ] **Step 2: Run them to see them fail**

Run: `python3 -m unittest tests.test_kg_serve -v 2>&1 | tail -5`
Expected: FAIL (404 for `/api/annotations`; `KeyError: 'annotationsVersion'`).

- [ ] **Step 3: Implement `save_annotations(self, body)`**

- Hold `state.Lock` on `notes/annotations.json`.
- Read the file's text (missing means `None`). If it exists but fails `json.loads` or `validate_annotations`, refuse it as unreadable. Otherwise apply the deleted and conflict rules above.
- Write with `json.dumps(doc, ensure_ascii=False, separators=(",", ":"))` through `state.atomic_write`. Answer with `kg_notes.version` of the written text.
- `_post` reads the body with the larger limit for this route only. Update the module docstring's list of writes.

- [ ] **Step 4: Run the tests**

Run: `python3 -m unittest discover -s tests 2>&1 | tail -3`
Expected: OK.

- [ ] **Step 5: Commit**

```bash
git add tools/kg_serve.py tests/test_kg_serve.py
git commit -m "annotations: the helper saves them, with the notes' conflict rules"
```

---

### Task 3: The marks model, drawing, and the save client

**Files:**
- Create: `graph/parts/marks.js`
- Modify: `graph/template.html` (add `<script data-part="marks.js"></script>` after `editor.js`; `--mk1..5` tokens in every theme block, from Global Constraints; extract `filterState()` and `filtersFromState(flt)` from `writeHash`/`readHash`, which then call them), `graph/parts/globe.js` (`GL.input`), `graph/parts/notes.js` (`notesInit` calls `marksLoad`)
- Test: `tests/test_graph_template.py` (new class `MarksTests`; update `test_every_part_parses`'s list)

**Interfaces:**
- Consumes: `globeGeometry()`, `GL`, `wrapAngle`, `shortDate`, `noteApi`, `NT.serving`, `css`, `hexA`, the data keys from Task 1 and `/api/state` from Task 2.
- Produces (`marks.js`):
  - `MARK_TOKENS = ["--mk1", "--mk2", "--mk3", "--mk4", "--mk5"]`, `MARK_NAMES = ["Ink", "Red", "Lime", "Green", "Violet"]`, `PEN_WIDTHS = [2, 4, 7]`, `LABEL_MAX = 60`, `HISTORY_MAX = 100`;
  - `toUnits(x, y, geo) -> [u, v]` and `fromUnits(u, v, geo) -> [x, y]`, where `geo` is `{cx, cy, R}`;
  - `cameraOf(gl) -> {yaw, pitch, zoom, panX, panY}` and `sameCamera(a, b) -> bool` (tolerances in Global Constraints);
  - `filterKey(flt) -> string`: the same key for the same filters whatever the order of sets, keys or values;
  - `viewAt(views, camera, fkey) -> view | null`;
  - `viewName(flt, today) -> string` (rule in Global Constraints; `flt.sets.type` holds the kind labels `KIND_PAPER`/`KIND_WEB`);
  - `simplify(pts, minUnits) -> pts`: drops a point closer than `minUnits` to the last kept point, always keeps the last, and caps at 2,000 points;
  - `markBox(mark, R) -> {x0, y0, x1, y1}` in units; a label's width is `0.6 * 14 * text.length / R`;
  - `hitMark(mark, u, v, tol, R) -> bool`: within `tol` of a pen stroke, an outline or an arrow; inside a label's box;
  - `insideMark(mark, u, v) -> bool`: inside a rectangle, an ellipse, or a pen stroke as a closed loop (ray casting); false for arrows and labels;
  - `itemsInMark(mark, cands, cap) -> {ids, total}`, where `cands` is `[{id, u, v, score}]` (visible, near side). It returns the `cap` highest-scored, ties by id. An arrow gives `[mark.snap]` when set;
  - `snapTarget(u, v, cands, tol) -> cand | null`;
  - `newHistory() -> {undo: [], redo: []}`; `record(h, id, before, after)`, where `before` and `after` are a view's JSON or null, capped at `HISTORY_MAX` and clearing redo; `undoStep(views, h) -> views` and `redoStep(views, h) -> views`, which apply the snapshot (null removes the view);
  - `drawMarks(g, view, geo, colours, selectedId)`, where `colours` is the five resolved colours, plus the overlay registration `GL.overlays.push({draw: ..., hit: () => null})`. It draws only the active view's marks, and a selected mark gets a dashed box and a resize handle (8 px square at the box's bottom-right);
  - `AN`, the state: `{views, version, error, active, last, tool, shape, colour, width, selected, history, save: "saved"|"saving"|"unsaved"|"failed"|"conflict"|"deleted"|"off", msg, conflict, inFlight, pending}`;
  - `marksLoad({annotations, annotationsVersion, annotationsError})`;
  - `marksChanged(viewId, before)`, which records history, sets `updated`, schedules a save 800 ms later and redraws;
  - `saveMarks() -> Promise`: one at a time, and `"off"` with no request when `!NT.serving`;
  - `keepMine()` and `useFilesMarks()`;
  - `activeView() -> view | null`, recomputed from `cameraOf(GL)`, `filterKey(filterState())` and `AN.views`.
- Produces (`template.html`):
  - `filterState() -> flt`, the object `writeHash` serialises;
  - `filtersFromState(flt)`, which sets `S.filters` exactly as `readHash` did, ignores values the library does not have, and does not throw on a partial, hand-edited or null object.

  The hash format does not change: existing bookmarks keep opening, and `test_the_open_note_is_in_the_address` still passes.
- Produces (`globe.js`): `GL.input = null`. When set to `{down(x, y, e) -> bool, move(x, y, e), up(x, y, e)}` and `down` returns true, that drag goes to it instead of turning the globe.

- [ ] **Step 1: Write the failing tests** (node, via `run_js`; each prelude stubs what it needs)

```python
def test_marks_follow_the_globe(self):
    # Review Focus 1: drawn at one window size, the mark's point must land where its dot lands at another.
    got = run_js(["toUnits", "fromUnits"], "", """(() => { const a = {cx: 400, cy: 300, R: 200}, b = {cx: 700, cy: 380, R: 260};
      const dot = (geo) => [geo.cx + 0.3 * geo.R, geo.cy - 0.5 * geo.R];
      const uv = toUnits(...dot(a), a); return [uv, fromUnits(...uv, b), dot(b)]; })()""")
    self.assertEqual(got[0], [0.3, -0.5]); self.assertEqual(got[1], got[2])
```

`test_views_cameras_and_names` asserts:
- `sameCamera({yaw: 0.1, ...}, {yaw: 0.1 + 2 * Math.PI, ...})` is true;
- a zoom that differs by 1 % is false;
- `viewName({sets: {}}, "2026-11-01")` is `"Whole library · 1 Nov"`;
- `viewName({sets: {interest: ["A"], type: [KIND_PAPER]}}, "2026-11-01")` is `"A · papers only · 1 Nov"`;
- `viewName({sets: {interest: ["A", "B"]}}, …)` starts `"2 interests"`;
- `filterKey({sets: {interest: ["B", "A"]}, u: true})` equals `filterKey({u: true, sets: {interest: ["A", "B"]}})`;
- `viewAt` finds a view by camera and key, and returns null when only the filters differ.

Further tests:
- **`test_geometry`**:
  - `simplify` keeps the endpoints, drops near points and caps a 5,000-point stroke at 2,000;
  - `hitMark` is true on a rectangle's edge and false at its centre, true at a label's centre;
  - `insideMark` is true inside an ellipse and false outside;
  - `insideMark` on a U-shaped pen loop is false in the notch and true in the body;
  - `itemsInMark` caps at 2 of 3 by score, gives `{ids: ["paper:x"], total: 1}` for an arrow with `snap: "paper:x"`, and an empty result for a label;
  - `snapTarget` returns the nearest candidate within `tol`, else null.
- **`test_history`**: record a view's creation (before null), then a second mark. One undo restores the one-mark view; a second removes the view; redo twice brings both back. A new record after an undo clears redo. The history caps at 100.
- **`test_mark_colours`**:
  - parse the dark-theme block (as `test_dark_mode_uses_the_prototype_colours` does);
  - every `--mk2..5` is at least 25 degrees of hue from each of `--i1..--i6`, `--cites` and `--citedby`, and at least 30 degrees from each other;
  - `--mk1` is `var(--ink)` in every theme block;
  - all five tokens exist in the light, dark and system-dark blocks.
- **`test_filter_state_round_trip`**: `filtersFromState(filterState())` leaves `S.filters` unchanged, with sets, years, undated and newOnly all set.
- **`test_marks_without_the_helper`** (Review Focus 3): with `NT.serving = false` and a `noteApi` stub that counts calls, `saveMarks()` resolves with `AN.save === "off"` and zero calls.
- **`test_marks_save_one_at_a_time_and_conflict`**: the `test_a_save_waits_for_the_one_in_flight` shape. A second `saveMarks` during the first sends nothing until the first resolves, then sends once with the first's returned version. A 409 `{conflict: true, disk, diskVersion}` sets `AN.save = "conflict"` and keeps `AN.views`. `useFilesMarks()` sets `AN.views` to `disk` and `AN.version` to `diskVersion`. `keepMine()` saves with `diskVersion`. A 409 `{deleted: true}` sets `AN.save = "deleted"`.

In `GlobeMathTests` or a new test, check that `GL.input` exists and is consulted in `globeInput`'s `pointerdown`. That one is a source check, acceptable for wiring; the behaviour is checked in the browser in Task 4.

- [ ] **Step 2: Run them to see them fail**

Run: `python3 -m unittest tests.test_graph_template -v 2>&1 | tail -5`
Expected: FAIL (`function toUnits not found in the template`; `marks.js` missing from the part list).

- [ ] **Step 3: Implement `marks.js`, the tokens and the hook**

Match the parts' style: a header comment saying what the part is and why marks belong to a view, short comments on the non-obvious functions, and no interest names. `globe.js`'s `pointerdown` asks `GL.input.down(x, y, e)` first (the coordinates are relative to the canvas, as `at(e)` gives them). When it returns true, the drag is marked `captured`, and `pointermove`/`pointerup` forward to `GL.input` without turning, hovering or selecting. `notesInit` calls `marksLoad` with the embedded data before the helper answers, and again with `/api/state`'s.

- [ ] **Step 4: Run the tests**

Run: `python3 -m unittest discover -s tests 2>&1 | tail -3`
Expected: OK.

- [ ] **Step 5: Commit**

```bash
git add graph tests
git commit -m "annotations: marks in globe units, views, history, drawing and saving"
```

---

### Task 4: The toolbar and its tools

**Files:**
- Create: `graph/parts/annotate.js`
- Modify: `graph/template.html` (toolbar markup inside `#tab-overview`, styles beside `#globe-nav`'s, the part tag after `marks.js`, `onKey`'s Esc order), `graph/parts/globe.js` (navigation toolbar default: bottom right)
- Test: `tests/test_graph_template.py`

**Interfaces:**
- Consumes: Task 3's `marks.js` API and `GL.input`; `makeToolbar`, `MIN_CARDS`, `applyMin`, `store`, `highlightSet`, `renderHighlightChip`, `globeGeometry`, `GL.model`/`GL.mask`/`GL.index`, `project`/`rotation`.
- Produces:
  - markup: `#annotbar` (`role="toolbar"`, `aria-label="Draw on the map"`) holding `#ann-grip`, buttons `#ann-select`, `#ann-pen`, `#ann-shape` with `<select id="ann-shape-kind">` (Rectangle, Ellipse, Arrow), `#ann-text`, `#ann-note`, `#ann-undo`, `#ann-redo`, five `.ann-colour` buttons (`aria-label` from `MARK_NAMES`), `<select id="ann-width">` (Thin, Medium, Thick), `#ann-eraser`, `#ann-clear`, `#ann-image`, `#ann-close`; a status line `#ann-msg` (`aria-live="polite"`); and `#mark-actions`, the floating bar beside a selected mark with "Make a note from this" and "Delete";
  - `setTool(tool)`, where `tool` is one of `"select"`, `"pen"`, `"shape"`, `"text"`, `"eraser"`. It sets `aria-pressed` on exactly one tool button and remembers the last tool in `store` (`kg-ann-tool`);
  - `annotEsc() -> bool`: a drawing in progress is cancelled; else a tool other than Select returns to Select; else a selected mark is deselected. It returns whether it did anything;
  - `annotHint(tool, save) -> string`: the status-line words;
  - `visibleCands() -> [{id, u, v, score}]`: the visible, near-side items in units, for snapping, picking and "what a mark holds";
  - `GL.input = {down, move, up}`, set by `annotate.js`.
- The status line's exact words:
  - Select: "Click a mark to move, resize, recolour or delete it. Shift+drag across dots to pick papers."
  - Pen: "Draw freehand. Esc returns to Select."
  - Shapes: "Drag to draw. An arrow snaps to the dot it points at."
  - Text: "Click where the label goes. Anything longer belongs in a note."
  - Eraser: "Click a mark to remove it."
  - Then a save sentence:
    - "Marks saved." or "Saving…";
    - for `"off"`: "Marks are not kept: saving is off (run /graph to save). Save as image keeps a picture.";
    - for `"failed"`: "Not saved: <msg> Save as image keeps a picture.";
    - for `"conflict"`: "Your marks changed somewhere else." plus Keep mine / Use the file's buttons;
    - for `"deleted"`: "Your saved marks were deleted elsewhere." plus a "Save them again" button;
    - when `AN.error` is set: "Marks cannot be saved: <error>".

Tool behaviour (`GL.input.down` returns true when the tool takes the drag):
- **Select**: on a mark's resize handle, drag resizes (scales the mark's points about its box's top-left; an arrow's end follows); on a mark, a drag moves it and a click selects it (the colour buttons and width then apply to it; Delete or Backspace removes it); with Shift held, the drag draws a dashed box and, on release, `highlightSet(ids of visibleCands() inside the box, "picked on the globe")`, then `renderHighlightChip()` and `globeRequestDraw()`; otherwise it returns false, so the globe turns or moves.
- **Pen**: points in units through `simplify(pts, 2 / R)`.
- **Shapes**: the box or line from press to release. An arrow's end snaps with `snapTarget(…, 14 / R)` and stores `snap`. A drag under 4 px draws nothing.
- **Text**: a click opens a small input at that point (`maxlength=60`); Enter or leaving it places the label, and Esc or empty text cancels.
- **Eraser**: a click on a mark removes it.
- **Clear**: `window.confirm("Remove all N marks in this view?")`, then empties the active view.
- Every change goes through `marksChanged`, so it can be undone.
- Cmd/Ctrl+Z undoes and Cmd/Ctrl+Shift+Z redoes, on the Overview, when not typing in a field. The buttons do the same and are disabled when there is nothing to undo or redo.
- Close and minimise set `S.min.cards.annotbar = true`; the toolbar then shows only the chip "▸ Draw", which restores it. `M` includes it (`MIN_CARDS.push("annotbar")`). Collapsing returns the tool to Select.
- `onKey`'s Esc on the Overview closes the editor first, then `annotEsc()`, then `globeClear()`.

- [ ] **Step 1: Write the failing tests**

- **`test_one_tool_at_a_time`**: with a stub `document` of five tool buttons and a `store` stub, `setTool("pen")` presses only `#ann-pen`, and `setTool("bogus")` leaves Select pressed.
- **`test_esc_steps_back_one_thing`**: `annotEsc()` with `{drawing: {...}}` clears the drawing first; next, `AN.tool = "pen"` returns to select; next, `AN.selected = "m-1"` clears it; then it returns false. Check also that `page_function("onKey")` calls `annotEsc()` after `closeEditor()` and before `globeClear()`. That is an order check, so a source check is acceptable.
- **`test_hints`**: `annotHint` gives the exact strings above for each tool and for `"off"`, `"conflict"` and an `AN.error`.
- **`test_toolbar_markup`**: every id listed above is in `TEMPLATE`, there are five `.ann-colour` buttons, and `annotbar` is in `MIN_CARDS`.
- **`test_spec_tools_only`**: the toolbar has no highlighter, pin or compare control (`assertNotRegex(TEMPLATE, r'id="ann-(highlight|pin|compare)')`).

- [ ] **Step 2: Run them to see them fail**

Run: `python3 -m unittest tests.test_graph_template -v 2>&1 | tail -5`
Expected: FAIL (`function setTool not found`; ids missing).

- [ ] **Step 3: Implement**

The toolbar uses `makeToolbar(tb, $("#tab-overview"), $("#ann-grip"), "kg-annotbar", …)`. Its default position is the bottom centre, 14 px from the bottom; `#globe-nav`'s default moves to the bottom right. Icons are inline SVG in `#globe-nav`'s style, each with a `title` that names the tool. Pressed tools use the existing `[aria-pressed="true"]` look. Re-render `#mark-actions` after every draw, beside the selected mark's box (kept on screen), and hide it otherwise.

- [ ] **Step 4: Run the tests, then check in the browser**

Run: `python3 -m unittest discover -s tests 2>&1 | tail -3`
Expected: OK.

Then build a throwaway page with `--synthetic 20000` and the live library: `scratchpad/mklive.sh` pointed at this worktree, a helper on it, and the Browser pane. Check the following, and write each result in the ledger:
- every tool draws;
- Select moves, resizes and recolours a mark;
- Shift+drag highlights the dots inside;
- a plain drag in Select still turns the globe;
- an arrow snaps;
- Esc steps back;
- undo and redo work by key and by button;
- Clear asks first;
- M and Close collapse the toolbar to "▸ Draw";
- a frame with 50 marks still draws in under 4 ms (`GL.lastDraw`).

- [ ] **Step 5: Commit**

```bash
git add graph tests
git commit -m "annotations: the toolbar - select, pen, shapes, text, eraser, undo"
```

---

### Task 5: Saved views, the chip, notes from marks, Save as image

**Files:**
- Modify: `graph/template.html` (`<div id="view-chip" hidden></div>` beside `#highlight-chip`, styled like it), `graph/parts/annotate.js`, `graph/parts/notes.js` (the Views chip and rows in the notes list)
- Test: `tests/test_graph_template.py`

**Interfaces:**
- Consumes: Tasks 3-4, including `filterState`/`filtersFromState`; `openEditor(id, links)`, `refreshData()`, `globeTween`, `download(name, type, dataUrl)`, `renderNotesList`, `NL`.
- Produces:
  - `ensureView() -> view`: the active view, or a new one (`id` `v-<date>-<6 hex>`, `name` from `viewName`, the camera and filter state), recorded in history so undo removes it;
  - `backToView(id)`: `filtersFromState(view.filters)`, `refreshData()`, then `globeTween` to the camera; afterwards `activeView()` is that view;
  - `renderViewChip()`: `#view-chip` with "Annotated view: <name> · " and a "Back to it" button, shown when `AN.last` names a view with marks that is not active;
  - `noteFromMark(markId)` and `noteFromToolbar()`: call `openEditor(null, links)` with the links rule from Global Constraints, and set `#ann-msg` when trimmed;
  - `saveImage()`: a PNG of the globe with its marks on the theme's background colour (`--plane`), downloaded as `library-map-<slug of the view name, or "view">.png`;
  - in the notes list: a "Views" chip (`NL.filter = {views: true}`) whose rows show the name, "N marks", the updated date, and Go to (`backToView`), Rename (an inline input, 80 characters, saved through `marksChanged`) and Delete (`window.confirm("Delete the view <name> and its N marks?")`). `notesLine` stays about notes only.

- [ ] **Step 1: Write the failing tests**

- **`test_old_views_still_open`** (Review Focus 5):
  - `filtersFromState({sets: {interest: ["Gone interest"]}, yMin: "x"})` does not throw and leaves `yearMin` null;
  - `filtersFromState(null)` does not throw;
  - a `drawMarks` call on a context stub with an arrow whose `snap` names an id not in `GL.index` still draws its line to the stored end.
- **`test_note_from_a_mark`**:
  - with stub `openEditor`, `visibleCands` and `AN` holding one rectangle around two of three candidates, `noteFromMark` opens the editor with those two ids, highest score first;
  - with 150 candidates inside, it links 100 and `#ann-msg` reads "Linked the 100 highest-scored of 150 items in the mark.";
  - `noteFromToolbar()` with no mark selected and `S.highlight = new Set(["paper:h"])` links `["paper:h"]`, and with neither, `S.current = "paper:c"`, it links `["paper:c"]`.
- **`test_view_chip`**: with `AN.last` set to a view with marks and a different active view, the chip text starts "Annotated view: "; with the last view active, or with no marks in it, the chip is hidden.
- **`test_first_mark_creates_a_view`**: `ensureView()` with no active view adds one named by `viewName`; a second call at the same camera and filters returns the same view; `undoStep` after the first mark removes the view.

- [ ] **Step 2: Run them to see them fail**

Run: `python3 -m unittest tests.test_graph_template -v 2>&1 | tail -5`
Expected: FAIL (`function ensureView not found`, …).

- [ ] **Step 3: Implement**

For `saveImage`, draw onto a canvas the size of `#globe`'s backing store: fill it with `css("--plane")`, then `drawImage(#globe)`. The globe's canvas already holds the satellites and marks because both are overlays. Call `download(name, "image/png", canvas.toDataURL("image/png"))`.

- [ ] **Step 4: Run the tests, then check in the browser**

Run: `python3 -m unittest discover -s tests 2>&1 | tail -3`
Expected: OK.

In the throwaway page, check the following, and write each result in the ledger:
- a first mark creates a view named by the rule;
- turning the globe hides the marks and shows the chip;
- "Back to it" restores the filters and the camera, and the marks reappear on the same dots;
- a resized window keeps them on those dots;
- the Views rows can be renamed and deleted (with a confirmation);
- Make a note from this opens the editor with the right links;
- Save as image downloads a PNG that shows the marks;
- after a reload, marks and views are back from `notes/annotations.json`;
- a second tab's edit gives the conflict choice;
- with the helper stopped, the toolbar says marks are not kept, and drawing and Save as image still work.

- [ ] **Step 5: Commit**

```bash
git add graph tests
git commit -m "annotations: saved views, Back to it, notes from marks, Save as image"
```

---

### Task 6: Status, docs, and the full check

**Files:**
- Modify: `graph/parts/status.js` (an "Annotations" row), `graph/README.md` (a "Drawing on the map" section under Notes), `USAGE.md` (the toolbar in the map section), `README.md` (diagram: `notes/annotations.json` beside the notes, through the helper), the spec's Build status (Part 3 built 2026-11-0x, with this plan's decisions in one bullet each), `CLAUDE.md` only if its repo-structure line for `graph/parts/` needs the new parts
- Test: `tests/test_graph_template.py`

**Interfaces:**
- Consumes: `statusRows(data, counts, notesInfo)` (Part 2); `AN`.
- Produces: `statusRows` takes an optional fourth argument `marksInfo = {views, marks, error}`. It adds a row `{label: "Annotations"}` whose value is "N saved views, M marks" (singular forms at one), or "none yet". When `error` is set, the value is that error and `problem: true`.

- [ ] **Step 1: Write the failing test**

`test_status_reports_annotations`: with `{views: 2, marks: 7, error: null}` the value is "2 saved views, 7 marks"; with `{views: 1, marks: 1, error: null}` it is "1 saved view, 1 mark"; with `{views: 0, marks: 0, error: "notes/annotations.json could not be read: …"}` the row is a problem whose value is the error (Review Focus 4).

- [ ] **Step 2: Run it to see it fail**

Run: `python3 -m unittest tests.test_graph_template -k status -v 2>&1 | tail -3`
Expected: FAIL (no Annotations row).

- [ ] **Step 3: Implement the row, then write the docs**

The docs describe:
- the tools as a table;
- Shift+drag to pick papers;
- that marks belong to the view (camera and filters) and hide when the globe moves;
- "Back to it";
- where marks are saved, and that they are never committed;
- what happens without the helper;
- Save as image;
- that `/reset notes` also deletes saved marks.

Plain words, matching Part 2's Notes section.

- [ ] **Step 4: The full check**

Run, and read every output:
- `python3 -m unittest discover -s tests 2>&1 | tail -3`, expecting OK;
- `python3 tools/knowledge_graph.py --check` in the throwaway live folder, expecting PASS;
- `python3 tools/security_guards.py`, expecting PASS;
- `git status --short`, expecting no `notes/`, `graph/index.html` or `.serve.json`;
- a final browser pass in dark and light mode, at 600 px and 1,400 px wide. The toolbar must not cover the "On your map" card or the selection card at its default position; if it does at 600 px, it opens minimised there and the ledger says so.

- [ ] **Step 5: Commit**

```bash
git add graph tests docs README.md USAGE.md
git commit -m "annotations: Status row, docs and build status"
```
