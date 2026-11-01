# Library Map, Part 2: Notes as Satellites - Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the researcher write notes next to the evidence on the library map: notes saved as files through a small local helper, drawn as satellites orbiting the globe, written in an editor with a guide (prompts, checks, suggested papers, new evidence), listed and searchable, and read-only (with export) when the helper is not running.

**Architecture:** `tools/kg_notes.py` owns the note file format (read, write, validate). `tools/kg_serve.py` is the helper: a stdlib HTTP server on 127.0.0.1 that serves the built page and the PDFs it links to, and writes notes atomically into `notes/` only, behind a per-run token. `knowledge_graph.py --serve` starts it in the background. The build embeds the notes, so the page shows them read-only without the helper. Two new page parts hold the page side: `notes.js` (the notes model, the helper client, satellites, the notes list) and `editor.js` (the editor, the guide and the matcher).

**Tech Stack:** Python 3 stdlib (`http.server`, `secrets`, `hashlib`, `subprocess`, `webbrowser`, `unittest`), plain browser JavaScript, node for page-logic tests, the Browser pane for real-browser checks.

**Spec:** `docs/superpowers/specs/2026-10-30-library-map-orbit-design.md`, the sections "Notes: satellites in orbit", "Where notes live", "Orbit meaning", "When the library changes", "Notes list", "The editor and the guide", plus the notes lines in "Page structure", "On your map", "How it connects", "Ask", "Status" and "Constraints". Part 1 is built and on master; read `graph/README.md` for how the page is put together.

## Global Constraints

- Stdlib Python only; the page stays one offline file; the only network use is the local helper on 127.0.0.1.
- `notes/` is gitignored, and `tools/security_guards.py` requires the rule (`notes/*`). `graph/.serve.json` is covered by the existing `graph/*`.
- The helper writes only inside `notes/`, through a fixed set of operations (save note, archive note, save prompts); file names come from the note id, never from the request path; writes are atomic (`state.atomic_write` under `state.Lock`).
- Every string from a note or the data reaches the page as text (`el()`, `textContent`), never HTML; every `<` in embedded data is written `<` (the existing `render()` does this).
- A note is never cited in a report; nothing in the report tools reads `notes/`.
- Nothing typed is ever discarded without warning: a failed save keeps the text and says so, minimising the editor keeps it, and leaving the page with unsaved text asks first.
- Profile-agnostic: no interest or sub-area names in code.
- Every browser-storage access goes through `store`; storage holds conveniences only, never notes.
- Existing tests keep passing. Commits end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Work in a worktree made from `~/.ai-research-assistant-build`; never commit from the working clone.

Decisions this plan makes where the spec leaves the builder a choice, or where its literal wording would not work:

- **Note ids and files:** the helper creates ids as `n-YYYYMMDD-xxxxxx` (date, six random hex digits); the file is `notes/<id>.md`.
- **Front matter:** each line is `key: <JSON value>` (strings quoted, lists as JSON arrays), between `---` lines. A hand edit with an unquoted string still reads as that string. Unknown keys are kept, line for line. Field order: `id, title, links, in_report, dismissed, created, updated, archived`.
- **Sub-area links** use `subarea:<interest>::<sub-area>`, not the spec's `<interest>/<sub-area>`: interest and sub-area names both contain `/` in real profiles, so a `/` could not be split back.
- **Tokens:** the token travels in the URL once; the helper then sets an `HttpOnly; SameSite=Strict` cookie so the page's PDF links work. Every write needs the token in an `X-KG-Token` header (a cross-site page cannot set it), a `Host` of `127.0.0.1:<port>` or `localhost:<port>` (against DNS rebinding), and no foreign `Origin`.
- **Version:** a note's version is the first 16 hex digits of the SHA-256 of its file; a save carries the version it was loaded at.
- **New evidence and suggestions are computed in the page**, from the same data and with one matcher, so the editor's suggestions and the pulse never disagree. The spec places the computation in `knowledge_graph.py`; the intent (exact and repeatable) holds, because the same data always gives the same answer.
- **The pulse:** a note with new evidence pulses three times when the map opens, then keeps a steady ring. A pulse that never stops would be motion that carries no new information.
- **Satellite placement:** a note sits above the centre of its linked items, or at a stable hashed direction when it has none, so tethers stay short and a note never moves unless its links change.

## Review Focus

1. **The same note open in two tabs, both edited.** The second save gets a conflict; both versions are shown, the typed text is kept, and the researcher chooses. Tests in Tasks 2 and 6.
2. **A note file hand-edited into something unreadable.** It is listed in Status as "could not read" and never overwritten; a save to it is refused. Tests in Tasks 1 and 2.
3. **The helper stops while the researcher is typing.** The save fails, the editor says "Not saved" and keeps the text, and Export is offered. Test in Task 6.
4. **A hostile request.** A wrong `Host`, a cross-origin `POST`, a PDF path with `..`, a body over the size limit, or a missing token is refused, and nothing outside `notes/` is ever written. Tests in Task 2.
5. **The library rebuilt while the page is open.** The page says "The library was rebuilt" with a Reload button, and an unsaved draft survives until the researcher reloads. Test in Task 4.

---

## File Structure

| File | Responsibility |
|---|---|
| `tools/kg_notes.py` (create) | Note format: parse, render, validate, load a folder, version hashes, ids |
| `tools/kg_serve.py` (create) | The helper: routes, token/host/origin checks, PDF serving, atomic writes, idle stop, `.serve.json` |
| `tools/knowledge_graph.py` (modify) | Embed notes in the build; `--serve` / `--no-open` flags that start the helper |
| `tools/security_guards.py`, `.gitignore` (modify) | Require and add `notes/*` |
| `graph/parts/notes.js` (create) | Notes model, helper client, link resolution, orbits, satellites, notes list |
| `graph/parts/editor.js` (create) | Editor, guide (prompts, checks), matcher, suggestions, new evidence |
| `graph/parts/globe.js`, `overview.js`, `connects.js`, `ask.js`, `status.js`, `graph/template.html` (modify) | Satellite drawing hook, card lines, next step, notes kind, Ask patterns, Status row, hash |
| `.claude/commands/graph.md`, `.claude/commands/reset.md`, `graph/README.md`, `USAGE.md`, `README.md`, the spec's Build status (modify) | The helper, the `notes` reset scope, how to use notes |
| `tests/test_kg_notes.py`, `tests/test_kg_serve.py` (create); `tests/test_graph_template.py`, `tests/test_knowledge_graph.py`, `tests/test_security_guards.py` (modify) | Tests |

---

### Task 1: The note format, and notes in the build

**Files:**
- Create: `tools/kg_notes.py`, `tests/test_kg_notes.py`
- Modify: `tools/knowledge_graph.py` (`build`), `.gitignore`, `tools/security_guards.py` (`REQUIRED_IGNORE_RULES`), `tests/test_security_guards.py` if it pins the list

**Interfaces:**
- Produces:
  - `NOTES = ROOT / "notes"`, `ID_RE = re.compile(r"^n-\d{8}-[0-9a-f]{6}$")`, `FIELDS = ("id", "title", "links", "in_report", "dismissed", "created", "updated", "archived")`, `LINK_RE = re.compile(r"^(paper|web|group|subarea):.+")`;
  - `class NoteError(ValueError)`;
  - `parse(text: str) -> dict`, which returns the fields plus `"body"` and `"extra"` (a list of the unknown front-matter lines, verbatim) and raises `NoteError` naming the problem;
  - `render(note: dict) -> str`, where `parse(render(n)) == n` for any valid note;
  - `validate(note: dict) -> list[str]`, the plain-words problems: a bad id, a title over 200 characters or empty, a body over 200,000 characters, a link not matching `LINK_RE`, more than 500 links, or dates that are not ISO strings or null;
  - `version(text: str) -> str` (16 hex digits);
  - `new_id(today: str) -> str`;
  - `load(folder: Path) -> tuple[list[dict], list[dict]]`, returning the notes (each with `file`, a repo-relative path, and `version`) and the unreadable files (`{"file", "error"}`); a missing folder gives `([], [])`;
  - `load_prompts(folder) -> list[dict]` from `notes/guide.json`, each `{name, question}`, `[]` if missing or invalid.
- Data block: `data["notes"]` (the notes, sorted by `updated` descending), `data["notesUnreadable"]`, `data["prompts"]`.

- [ ] **Step 1: Write the failing tests** (`tests/test_kg_notes.py`)

```python
NOTE = {"id": "n-20261101-a1b2c3", "title": "Gaze noise: \"defences\" <b>", "links": ["paper:10.1/x", "subarea:XR/Immersive::Eye/gaze"],
        "in_report": None, "dismissed": [], "created": "2026-11-01T10:00:00Z", "updated": "2026-11-01T10:05:00Z",
        "archived": None, "body": "Claim: one line.\n\n---\nnot front matter", "extra": []}

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
        d = Path(tempfile.mkdtemp()); self.addCleanup(shutil.rmtree, d)
        (d / "n-20261101-a1b2c3.md").write_text(kg_notes.render(NOTE))
        (d / "n-20261101-ffffff.md").write_text("no front matter at all")
        (d / "n-20261101-eeeeee.md").write_text("---\nid: n-20261101-eeeeee\nlinks: [unclosed\n---\n")
        notes, bad = kg_notes.load(d)
        self.assertEqual([n["id"] for n in notes], ["n-20261101-a1b2c3"])
        self.assertEqual(sorted(b["file"].rsplit("/", 1)[1] for b in bad), ["n-20261101-eeeeee.md", "n-20261101-ffffff.md"])
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
```

In `tests/test_knowledge_graph.py`, class `BuildTests`:

```python
def test_notes_are_embedded(self):
    (self.root / "notes").mkdir()
    # NOTE: the same dict as tests/test_kg_notes.py's, copied here (an import breaks under discover -s tests)
    (self.root / "notes" / "n-20261101-a1b2c3.md").write_text(kg_notes.render(NOTE))
    (self.root / "notes" / "n-20261101-ffffff.md").write_text("broken")
    (self.root / "notes" / "guide.json").write_text('[{"name": "Method", "question": "How was it measured?"}]')
    data = self.build()
    self.assertEqual([n["id"] for n in data["notes"]], ["n-20261101-a1b2c3"])
    self.assertEqual(len(data["notesUnreadable"]), 1)
    self.assertEqual(data["prompts"], [{"name": "Method", "question": "How was it measured?"}])
    self.assertNotIn("<b>", self.page.read_text().split('id="data"', 1)[1].split("</script>", 1)[0])
```

In `tests/test_security_guards.py`, assert that `"notes/*"` is in `REQUIRED_IGNORE_RULES`.

- [ ] **Step 2: Run them to see them fail**

Run: `python3 -m unittest tests.test_kg_notes tests.test_knowledge_graph tests.test_security_guards -v`
Expected: FAIL (`No module named 'kg_notes'`; no `notes` key; rule missing).

- [ ] **Step 3: Implement**

- `parse`: the text must start with `---\n` and have a closing `---` line, else `NoteError("no front matter")`.
- Each front-matter line splits at the first `": "`. A known key's value goes through `json.loads`; if that fails and the value does not start with `[`, `{` or `"`, it is kept as the plain string. Anything else raises `NoteError` naming the key.
- Unknown keys go into `extra`, verbatim. Missing fields take defaults: `links` and `dismissed` become `[]`, everything else `None`. The body is everything after the closing line, minus one leading newline.
- `render` writes the fields in `FIELDS` order with `json.dumps(ensure_ascii=False)`, then the `extra` lines, then `---`, a newline and the body.
- `load` reads `*.md` in id order. A note whose `id` does not match its file name is unreadable ("id does not match the file name").
- `.gitignore`: add `notes/*` with a comment ("the researcher's notes: personal writing, never committed"); add it to `REQUIRED_IGNORE_RULES`.
- `build()` sets `NOTES_DIR = ROOT / "notes"` and adds the three keys (empty for `--synthetic`).

- [ ] **Step 4: Run the tests**

Run: `python3 -m unittest discover -s tests`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add tools/kg_notes.py tools/knowledge_graph.py tools/security_guards.py .gitignore tests
git commit -m "notes: the note file format, and notes in the build"
```

---

### Task 2: The helper's requests

**Files:**
- Create: `tools/kg_serve.py`, `tests/test_kg_serve.py`

**Interfaces:**
- Consumes: `kg_notes`, `state.atomic_write`, `state.Lock`, `knowledge_graph.PAGE`.
- Produces:
  - `make_server(root: Path, token: str, port: int = 0) -> ThreadingHTTPServer`, bound to 127.0.0.1, with `server.last_activity` (monotonic seconds) updated on every authorised request;
  - `MAX_BODY = 256 * 1024`.
  - Routes (JSON in and out, `Cache-Control: no-store`):

| Route | Needs | Does |
|---|---|---|
| `GET /` and `/index.html` | `?t=` or cookie | Serves `graph/index.html`; with a valid `?t=` sets `kgt=<token>; HttpOnly; SameSite=Strict; Path=/` |
| `GET /research/fulltext/<name>.pdf`, `GET /reports/<slug>/report.pdf` | cookie or `?t=` | Read-only. The resolved path must be inside that folder and end `.pdf`; otherwise 404 |
| `GET /api/state` | header | `{built: <index.html mtime>, notes, unreadable, prompts}`; note dicts include `version` |
| `POST /api/note` | header | Body `{note, version}`. No `note.id` creates one (`new_id`, `created` = `updated` = now). Otherwise the file's current version must equal `version`, or 409 `{conflict: true, disk: <parsed note>, diskVersion}`; force-save by sending `diskVersion`. Validates; sets `updated` = now unless `{keepUpdated: true}` (used by Dismiss). Returns `{note, version}` |
| `POST /api/note/archive` | header | `{id, archived: bool, version}`: sets or clears `archived`, same conflict rule |
| `POST /api/prompts` | header | `{prompts: [{name, question}]}`: at most 50, names 1-24 characters, unique ignoring case and the five presets' names; writes `notes/guide.json` |
| `POST /api/heartbeat` | header | `{built}` |
| `GET /api/ping` | header | `{ok: true}` |

  - Refusals, all with a short plain-words JSON message:
    - 403: a missing or wrong token, or a `Host` that is not `127.0.0.1:<port>` or `localhost:<port>`, or an `Origin` that is present and differs from `http://<host>`;
    - 413: a body over `MAX_BODY`;
    - 400: invalid JSON or a note that fails `kg_notes.validate`;
    - 404: anything not listed;
    - 409 for a save, with message "This note's file could not be read; fix or remove it first.": the target file exists but does not parse.

- [ ] **Step 1: Write the failing tests** (`tests/test_kg_serve.py`)

A fixture copies a temp repo layout (`graph/index.html` with any text, `research/fulltext/a.pdf`, `reports/r1/report.pdf`, `secret.txt` at the root), starts `make_server(root, "tok")` on port 0 in a thread, and calls it with `urllib.request` (helper `call(method, path, body=None, headers=None)` that returns `(status, json_or_text, headers)`). The tests:

```python
def test_page_needs_the_token_and_sets_the_cookie(self):
    self.assertEqual(self.call("GET", "/")[0], 403)
    status, _, headers = self.call("GET", "/?t=tok")
    self.assertEqual(status, 200)
    self.assertIn("HttpOnly", headers["Set-Cookie"]); self.assertIn("SameSite=Strict", headers["Set-Cookie"])

def test_pdfs_only_from_their_two_folders(self):
    cookie = {"Cookie": "kgt=tok"}
    self.assertEqual(self.call("GET", "/research/fulltext/a.pdf", headers=cookie)[0], 200)
    self.assertEqual(self.call("GET", "/reports/r1/report.pdf", headers=cookie)[0], 200)
    for bad in ("/research/fulltext/../../secret.txt", "/research/fulltext/%2e%2e/%2e%2e/secret.txt",
                "/reports/r1/../../secret.txt", "/research/seen_sources.json", "/secret.txt"):
        self.assertEqual(self.call("GET", bad, headers=cookie)[0], 404, bad)
    self.assertEqual(self.call("GET", "/research/fulltext/a.pdf")[0], 403)

def test_save_creates_then_conflicts(self):
    st, r, _ = self.api("/api/note", {"note": {"title": "First", "links": [], "body": "Claim: x"}})
    self.assertEqual(st, 200); nid, v1 = r["note"]["id"], r["version"]
    self.assertTrue((self.root / "notes" / f"{nid}.md").exists())
    st, r2, _ = self.api("/api/note", {"note": {**r["note"], "body": "tab A"}, "version": v1})
    self.assertEqual(st, 200)
    st, r3, _ = self.api("/api/note", {"note": {**r["note"], "body": "tab B"}, "version": v1})   # stale
    self.assertEqual(st, 409); self.assertEqual(r3["disk"]["body"], "tab A")
    st, _, _ = self.api("/api/note", {"note": {**r["note"], "body": "tab B"}, "version": r3["diskVersion"]})
    self.assertEqual(st, 200)

def test_dismiss_keeps_updated(self):
    st, r, _ = self.api("/api/note", {"note": {"title": "T", "links": [], "body": ""}})
    st, r2, _ = self.api("/api/note", {"note": {**r["note"], "dismissed": ["paper:k"]}, "version": r["version"], "keepUpdated": True})
    self.assertEqual(r2["note"]["updated"], r["note"]["updated"])

def test_unreadable_note_is_never_overwritten(self):
    (self.root / "notes").mkdir(exist_ok=True)
    (self.root / "notes" / "n-20261101-ffffff.md").write_text("hand-broken")
    st, r, _ = self.api("/api/note", {"note": {"id": "n-20261101-ffffff", "title": "T", "links": [], "body": ""}, "version": None})
    self.assertEqual(st, 409)
    self.assertEqual((self.root / "notes" / "n-20261101-ffffff.md").read_text(), "hand-broken")

def test_hostile_requests_are_refused(self):
    self.assertEqual(self.api("/api/note", {"note": {}}, token=None)[0], 403)
    self.assertEqual(self.api("/api/note", {"note": {}}, extra={"Host": "evil.example:80"})[0], 403)
    self.assertEqual(self.api("/api/note", {"note": {}}, extra={"Origin": "https://evil.example"})[0], 403)
    self.assertEqual(self.api("/api/note", "x" * (300 * 1024))[0], 413)
    self.assertEqual(self.api("/api/note", {"note": {"id": "../../secret", "title": "T", "links": [], "body": ""}})[0], 400)
    self.assertEqual(sorted(p.name for p in self.root.iterdir()), sorted(self.layout))   # nothing new at the root

def test_prompts_are_checked(self):
    self.assertEqual(self.api("/api/prompts", {"prompts": [{"name": "Method", "question": "How?"}]})[0], 200)
    for bad in ([{"name": "claim", "question": ""}], [{"name": "x" * 25, "question": ""}],
                [{"name": "A", "question": ""}, {"name": "a", "question": ""}]):
        self.assertEqual(self.api("/api/prompts", {"prompts": bad})[0], 400, bad)
```

(`api(path, body, token="tok", extra=None)` is `call("POST", ...)` with `X-KG-Token` and a JSON body.)

- [ ] **Step 2: Run them to see them fail**

Run: `python3 -m unittest tests.test_kg_serve -v`
Expected: FAIL (`No module named 'kg_serve'`).

- [ ] **Step 3: Implement `kg_serve.py`**

- Subclass `BaseHTTPRequestHandler`; check the token with `secrets.compare_digest`.
- Resolve PDF paths: `(folder / unquote(rel)).resolve()` must be `relative_to(folder.resolve())` and a file ending `.pdf`.
- Write each note under `state.Lock(path)` with `state.atomic_write`. Read the version inside the lock, so two saves cannot both pass the version check.
- Log nothing that contains the token: `log_message` prints the method and the path without the query.

- [ ] **Step 4: Run the tests**

Run: `python3 -m unittest tests.test_kg_serve -v && python3 -m unittest discover -s tests`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tools/kg_serve.py tests/test_kg_serve.py
git commit -m "notes: the local helper - token, host and origin checks, notes-only writes, PDFs"
```

---

### Task 3: Starting and stopping the helper

**Files:**
- Modify: `tools/kg_serve.py` (`serve_forever_until_idle`, `start`), `tools/knowledge_graph.py` (`build_parser`, `main`), `.claude/commands/graph.md`
- Test: `tests/test_kg_serve.py`

**Interfaces:**
- Produces:
  - `SERVE_FILE = ROOT / "graph" / ".serve.json"` (`{port, token, pid, started}`);
  - `IDLE_SECONDS = int(os.environ.get("KG_IDLE_SECONDS", "1800"))`;
  - `running(root) -> dict | None`: the record, if its pid is alive and `GET /api/ping` with its token answers 200;
  - `start(root, open_browser: bool) -> str`, which returns the address `http://127.0.0.1:<port>/?t=<token>`;
  - `run_foreground(root, token)`, the child: it rebuilds the page, writes `.serve.json`, serves until idle, then deletes `.serve.json`.
  - CLI:
    - `python3 tools/knowledge_graph.py --serve [--no-open]` prints the address on one line and exits 0 once the helper answers, or within 10 s with exit 1 and the reason;
    - `--serve-foreground --token T` is the hidden child entry point.

- [ ] **Step 1: Write the failing tests**

```python
class LifecycleTests(unittest.TestCase):          # in tests/test_kg_serve.py; temp repo copy as in GraphFixture
    def test_start_reuses_a_live_helper_and_stops_when_idle(self):
        env = dict(os.environ, KG_IDLE_SECONDS="3")
        first = self.run_graph("--serve", "--no-open", env=env)
        self.assertEqual(first.returncode, 0, first.stderr)
        addr = first.stdout.strip().splitlines()[-1]
        self.assertRegex(addr, r"^http://127\.0\.0\.1:\d+/\?t=[0-9a-f]{32}$")
        second = self.run_graph("--serve", "--no-open", env=env)
        self.assertEqual(second.stdout.strip().splitlines()[-1], addr)        # same helper, not a new one
        self.assertTrue((self.root / "graph" / "index.html").exists())          # it rebuilt on start
        deadline = time.time() + 15
        while (self.root / "graph" / ".serve.json").exists() and time.time() < deadline:
            time.sleep(0.5)
        self.assertFalse((self.root / "graph" / ".serve.json").exists())        # stopped itself when idle

    def test_a_stale_record_is_replaced(self):
        (self.root / "graph").mkdir(exist_ok=True)
        (self.root / "graph" / ".serve.json").write_text(json.dumps({"port": 1, "token": "x", "pid": 999999, "started": 0}))
        r = self.run_graph("--serve", "--no-open", env=dict(os.environ, KG_IDLE_SECONDS="2"))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn(":1/", r.stdout)
        self.wait_until_stopped()        # the same wait as above, so no helper outlives the temp folder
```

- [ ] **Step 2: Run them to see them fail**

Run: `python3 -m unittest tests.test_kg_serve.LifecycleTests -v`
Expected: FAIL (`unrecognized arguments: --serve`).

- [ ] **Step 3: Implement**

- **`start`:** if `running()` finds a live helper, return its address. Otherwise generate a token with `secrets.token_hex(16)` and spawn the child with `subprocess.Popen([sys.executable, tools/knowledge_graph.py, "--serve-foreground", "--token", token], start_new_session=True)`, all streams to `DEVNULL`. Poll `.serve.json` and `/api/ping` for up to 10 s, then `webbrowser.open(address)` unless `--no-open`.
- **The child:** rebuild with the same code path as a plain build (no `--enrich`). Bind port 0 and write `.serve.json` atomically. Loop `handle_request()` with a 1 s timeout until `time.monotonic() - last_activity > IDLE_SECONDS`, then remove `.serve.json`.
- **`/graph`:** Step 1 still builds with `--enrich` and Step 2 checks. A new Step 3, "Open it with saving on", runs `python3 tools/knowledge_graph.py --serve`. The present step then says "Open <the address it printed> - notes are saved while it is open; it stops by itself after 30 minutes with the page closed." For no helper, opening `graph/index.html` still works, read-only.

- [ ] **Step 4: Run the tests**

Run: `python3 -m unittest discover -s tests`
Expected: all PASS (`DocsDriftTests` checks that `--serve` and `--no-open` are real flags).

- [ ] **Step 5: Commit**

```bash
git add tools/kg_serve.py tools/knowledge_graph.py .claude/commands/graph.md tests
git commit -m "notes: --serve starts the helper in the background, reuses a live one, stops when idle"
```

---

### Task 4: The notes model and the helper client in the page

**Files:**
- Create: `graph/parts/notes.js`
- Modify: `graph/template.html` (part tags after `overview.js`: `notes.js`, then `editor.js` as an empty header for now; `#rebuilt` banner markup; hash `note=`), `tests/test_graph_template.py` (`PART_NAMES` list)

**Interfaces:**
- Produces, in `notes.js`:
  - `NT = { serving, token, notes: Map<id, note>, versions: Map<id, string>, unreadable: [], prompts: [], open: null | id, built: null }`;
  - `parseLink(link) -> {kind, key} | null`;
  - `linkNodeId(link) -> string | null`, the page id: `paper:<key>`, `web:<key>`, `lab:<key>`, and `subarea:<interest>:<sub>` from `subarea:<interest>::<sub>`;
  - `resolveLinks(note, has) -> [{link, kind, id, missing, label}]`, where `has(id)` says whether this build has it;
  - `noteOrbit(note, has) -> "inner" | "middle" | "outer"`;
  - `orbitWords(note, has) -> string`;
  - `notesInit()`, which loads the embedded notes, then the helper's if serving;
  - `noteApi(path, body) -> Promise<{status, data}>`;
  - `beatAndCheck()`, which sends the heartbeat and shows `#rebuilt` when `built` changed.
- The hash gains `note`.

- [ ] **Step 1: Write the failing tests**

```python
@unittest.skipUnless(shutil.which("node"), "node not installed")
def test_links_and_orbits(self):
    has = "(id) => ['paper:p1', 'web:w1', 'web:w2', 'lab:L1', 'subarea:XR/Immersive:Eye/gaze'].includes(id)"
    got = run_js(["parseLink", "linkNodeId", "resolveLinks", "noteOrbit", "orbitWords"], "",
                 f"""(() => {{ const has = {has};
      const n = (links, in_report) => ({{links, in_report: in_report || null}});
      return [linkNodeId('subarea:XR/Immersive::Eye/gaze'), linkNodeId('group:L1'), parseLink('nonsense'),
        noteOrbit(n([]), has), noteOrbit(n(['web:w1', 'lab:L1']), has), noteOrbit(n(['paper:p1']), has),
        noteOrbit(n(['paper:gone']), has), noteOrbit(n([], 'r1'), has),
        resolveLinks(n(['paper:gone']), has)[0].missing,
        orbitWords(n(['paper:p1']), has), orbitWords(n(['web:w1', 'web:w2']), has), orbitWords(n([]), has)]; }})()""")
    self.assertEqual(got, ["subarea:XR/Immersive:Eye/gaze", "lab:L1", None,
                           "outer", "outer", "middle", "outer", "inner", True,
                           "Middle orbit · backed by 1 paper",
                           "Outer orbit · linked to 2 web sources, no papers yet",
                           "Outer orbit · an idea, no papers yet"])

def test_rebuilt_banner_and_note_in_the_address(self):
    self.assertRegex(TEMPLATE, r'id="rebuilt"')
    self.assertIn("The library was rebuilt", PAGE_SOURCE)
    self.assertIn("note:", page_function("writeHash"))
    self.assertIn("beforeunload", PAGE_SOURCE)
```

- [ ] **Step 2: Run them to see them fail**

Run: `python3 -m unittest tests.test_graph_template -v`
Expected: FAIL.

- [ ] **Step 3: Implement**

- **Missing links** count toward no orbit. `orbitWords` gives:
  - "Inner orbit · in a report: <title>";
  - "Middle orbit · backed by N paper(s)";
  - "Outer orbit · linked to N web source(s), no papers yet" (or "... to N other item(s) ...");
  - "Outer orbit · an idea, no papers yet".
- **Serving:** the page is serving when `location.protocol` is `http:` and `?t=` is in the address. Read the token once at load, then remove it from the address with `history.replaceState`, so a bookmark or a shared screenshot never carries it.
- **`noteApi`:** sends `X-KG-Token`. A network failure resolves to `{status: 0}`; it never throws.
- **Heartbeat:** `beatAndCheck` runs every 60 s while serving. When `built` changes, it shows `#rebuilt`: "The library was rebuilt. Reload" (a button). If a draft is unsaved, the banner adds "Save or export your note first", and Reload asks before leaving.
- **`beforeunload`:** warns while a draft has unsaved text.

- [ ] **Step 4: Run the tests**

Run: `python3 -m unittest discover -s tests`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add graph tests/test_graph_template.py
git commit -m "notes: the notes model, link resolution, orbits and the helper client in the page"
```

---

### Task 5: Satellites on the globe

**Files:**
- Modify: `graph/parts/notes.js` (satellites), `graph/parts/globe.js` (a `GL.overlays` list drawn after the dots, and its hit-testing first), `graph/parts/overview.js` (hover text for a satellite)
- Test: `tests/test_graph_template.py`

**Interfaces:**
- Consumes: `GL`, `project`, `rotation`, `globeGeometry`, `hash01`, `noteOrbit`, `resolveLinks`.
- Produces:
  - `SAT_ALT = {inner: 1.17, middle: 1.38, outer: 1.62}`, `SAT_CAP = 30`;
  - `satDirection(note, positions) -> [x, y, z]`: the unit-length mean of the linked items' vectors (`positions(link)` takes a link string and returns a unit vector or `null`), or a direction from `hash01(note.id)` and `hash01(note.id + "z")` when none resolve;
  - `pickSatellites(notes, ctx) -> {shown: id[], more: {inner, middle, outer}}`, where `ctx = {selected, hasNewEvidence(id), linkedVisible(id), orbit(id)}`;
  - `GL.overlays.push({draw(g, P, R, cx, cy), hit(x, y) -> {kind: "note", id} | null})`.

- [ ] **Step 1: Write the failing tests**

```python
@unittest.skipUnless(shutil.which("node"), "node not installed")
def test_satellite_placement_and_cap(self):
    got = run_js(["hash01", "satDirection", "pickSatellites"], "const SAT_CAP = 30;",
                 """(() => { const pos = (id) => ({a: [1, 0, 0], b: [0, 1, 0]})[id] || null;
      const d1 = satDirection({id: 'n-1', links: ['paper:a', 'paper:b']}, (l) => pos(l.split(':')[1]));
      const d2 = satDirection({id: 'n-2', links: []}, pos), d3 = satDirection({id: 'n-2', links: []}, pos);
      const notes = Array.from({length: 50}, (_, i) => ({id: 'n' + i, updated: '2026-10-' + String(10 + (i % 20)).padStart(2, '0'), archived: i === 3 ? '2026-10-01' : null}));
      const r = pickSatellites(notes, {selected: 'n49', hasNewEvidence: (id) => id === 'n7', linkedVisible: (id) => id === 'n8',
        orbit: (id) => (Number(id.slice(1)) % 3 === 0 ? 'outer' : 'middle')});
      return [d1.map((v) => Math.round(v * 1000) / 1000), JSON.stringify(d2) === JSON.stringify(d3), Math.round(Math.hypot(...d2) * 1000) / 1000,
        r.shown.length, r.shown.slice(0, 3), r.shown.includes('n3'), r.more.outer + r.more.middle + r.more.inner]; })()""")
    self.assertEqual(got[0], [0.707, 0.707, 0])
    self.assertTrue(got[1]); self.assertEqual(got[2], 1)
    self.assertEqual(got[3], 30)
    self.assertEqual(got[4], ["n49", "n7", "n8"])          # selected, new evidence, linked to what is shown
    self.assertFalse(got[5])                                # archived notes never orbit
    self.assertEqual(got[6], 49 - 30)                       # every other unarchived note is counted
```

- [ ] **Step 2: Run it to see it fail**

Run: `python3 -m unittest tests.test_graph_template -v`
Expected: FAIL.

- [ ] **Step 3: Implement**

- **Shells.** Three faint circles of radius `R * SAT_ALT[orbit]` around the globe's centre, each labelled at its top in small muted text: "in a report", "backed by papers", "an idea, no papers yet". When an orbit holds more notes than are shown, its label adds "+N more", and clicking the label opens the notes list filtered to that orbit (Task 8 provides `openNotesList(filter)`).
- **Satellites.** Each sits at `satDirection * SAT_ALT[orbit]`, projected with the globe's rotation. It is drawn only when it faces the viewer or lies outside the globe's disc, so a satellite behind the globe is hidden by it.
  - Shape: a 6 px dot, hollow for the outer orbit.
  - Colour: the interest colour of its first resolvable linked item, else `--muted`.
  - Selected: drawn larger with a ring.
- **Tethers.** A 1 px line from the satellite to each visible linked item: faint normally, full strength and lighting the items when the note is selected.
- **New evidence.** A ring in `--cites` around the satellite. It pulses (grows and fades) three times over about 3 s when the map opens; this is the only animation loop and it ends. After that the ring stays still.
- **Moving inward.** When a save changes a note's orbit, its altitude moves from the old shell to the new over 800 ms, once.
- **Interaction.** Hovering a satellite shows its title in `#globe-tip`. Clicking one opens it in the editor (Task 6's `openEditor(id)`).

- [ ] **Step 4: Run the tests, then check in a browser**

Run: `python3 -m unittest discover -s tests`. Then build the live library, add three hand-written notes in a temp copy (one with no links, one linked to two papers, one with `in_report`), serve the copy, and check:
- the three shells are drawn and labelled;
- each note sits on its shell above its papers;
- its tethers follow the globe as it turns;
- a hidden note behind the globe disappears;
- hover shows the title;
- there are no console errors.

- [ ] **Step 5: Commit**

```bash
git add graph tests/test_graph_template.py
git commit -m "notes: satellites in three orbits, tethers, the new-evidence ring"
```

---

### Task 6: The editor and the guide's prompts and checks

**Files:**
- Modify: `graph/parts/editor.js`, `graph/template.html` (`#noteeditor` card markup and styles; `MIN_CARDS` gets it)
- Test: `tests/test_graph_template.py`

**Interfaces:**
- Consumes: `NT`, `noteApi`, `resolveLinks`, `noteOrbit`, `orbitWords`, `cardFrame`, `cardChip`, `byId`, `labById`.
- Produces:
  - `PRESETS = [["Claim", "What are you saying, in one sentence?"], ["Evidence", "Which papers or results back it up?"], ["Against", "What disagrees, or could?"], ["Gap", "What is missing or untested?"], ["Next step", "What would you do next?"]]`;
  - `promptDone(body, name) -> bool`, true when a line starts with `name:`, ignoring case;
  - `addPromptLine(body, name) -> string`;
  - `customPromptError(name, existing) -> string`;
  - `checksFor(note, ctx) -> [{kind, text, basis}]`;
  - `openEditor(id | null, links = [])`, `closeEditor()`;
  - `saveDraft(opts) -> Promise`, with `NT.saveState` one of `"saved" | "saving" | "unsaved" | "conflict" | "readonly" | "failed"`.

- [ ] **Step 1: Write the failing tests** (copy fixed by the spec)

```python
@unittest.skipUnless(shutil.which("node"), "node not installed")
def test_prompts(self):
    got = run_js(["promptDone", "addPromptLine", "customPromptError"], 'const PRESETS = [["Claim", ""], ["Evidence", ""], ["Against", ""], ["Gap", ""], ["Next step", ""]];',
                 """[promptDone('Claim: x', 'Claim'), promptDone('text\\nnext step: y', 'Next step'), promptDone('I claim: no', 'Claim'),
        addPromptLine('', 'Gap'), addPromptLine('One line', 'Gap'),
        customPromptError('Method', []), customPromptError('claim', []), customPromptError('Method', [{name: 'method'}]),
        customPromptError('', []), customPromptError('x'.repeat(25), [])]""")
    self.assertEqual(got, [True, True, False, "Gap: ", "One line\n\nGap: ", "",
                           "That prompt already exists.", "That prompt already exists.",
                           "Give the prompt a name.", "Keep the name to 24 characters or fewer."])

@unittest.skipUnless(shutil.which("node"), "node not installed")
def test_checks_show_their_basis(self):
    ctx = """{kind: (l) => l.split(':')[0], lab: (l) => ({'paper:a': 'L1', 'paper:b': 'L1', 'paper:c': 'L2'})[l] || null,
              labName: () => 'Lab One', newEvidence: () => []}"""
    got = run_js(["checksFor", "promptDone"], "", f"""(() => {{ const c = {ctx}; const k = (n) => checksFor(n, c).map((x) => [x.kind, x.basis]);
      return [k({{body: 'Only 3% of systems detect it.', links: []}}),
        k({{body: 'x', links: ['paper:a', 'paper:b']}}),
        k({{body: 'Against: y', links: ['paper:a', 'paper:c']}}),
        k({{body: 'x', links: ['web:w1', 'web:w2']}})]; }})()""")
    self.assertEqual(got[0], [["claim", 'the words "Only", "3%"']])
    self.assertEqual(got[1], [["onegroup", "both linked papers are from Lab One"], ["noagainst", "2 linked papers, no \\"Against:\\" line"]])
    self.assertEqual(got[2], [])
    self.assertEqual(got[3], [["webonly", "every linked item is a web source (not peer-reviewed)"]])

def test_failed_save_keeps_the_text(self):
    # Review Focus 3: the helper stops while the researcher types.
    src = page_function("saveDraft")
    self.assertIn('"failed"', src)
    self.assertIn("Not saved", PAGE_SOURCE)
    self.assertIn("Export", PAGE_SOURCE)
```

The claim check uses `/(\d+(?:\.\d+)?\s?%|\d+(?:\.\d+)?|\b(?:only|every|never|none|first|proves?)\b)/gi` and fires only when nothing is linked. Its basis lists the distinct matches in order of appearance, each quoted as written, joined with ", ", after "the words ". The group check's basis reads "both linked papers are from <lab>" for two papers and "all N linked papers are from <lab>" for more. Checks come in the order claim, onegroup, webonly, noagainst, newevidence. The check texts are:
- **claim:** "Reads like a factual claim, and nothing is linked."
- **onegroup:** "Every linked paper comes from one research group."
- **webonly:** "Only web sources are linked."
- **noagainst:** "Nothing against it yet."
- **newevidence:** "New evidence: <title>" (Task 7).

- [ ] **Step 2: Run them to see them fail**

Run: `python3 -m unittest tests.test_graph_template -v`
Expected: FAIL.

- [ ] **Step 3: Implement the editor** (`#noteeditor`, top right; it replaces the selection card while open)

- **The header** gives `orbitWords`, then the title input (at most 200 characters) and the body textarea.
- **Prompt chips:** the presets, then the custom prompts. A chip shows ✓ once its line exists. Hovering shows its question. Clicking appends the line and focuses the end of the body.
- **"＋ Custom":** an inline form with a name and an optional question, using `customPromptError`; custom prompts have ×. Prompts save through `/api/prompts` while serving. Without the helper, adding one says "Custom prompts are saved by the helper; run python3 tools/knowledge_graph.py --serve".
- **Checks:** shown as rows with their basis.
- **Linked items:** each with "remove". A missing one shows "missing: <link>" with "remove". When filters hide some linked items (the Papers / Web switch, the shortlist), a line says so: "1 linked source is hidden by the current filters". Their tethers return when they are shown again.
- **"Written into a report":** a select of the library's reports, plus "not yet".
- **Buttons:** Archive/Restore, Export (downloads `<id or "new-note">.md` built from the same format as `kg_notes.render`), Close.
- **Saving:** autosave 1.5 s after the last keystroke while serving. The state line reads "Saved", "Saving…", "Not saved: <reason>" (in red, with Export), "Saving is off: run python3 tools/knowledge_graph.py --serve to save. Export keeps a copy." or a conflict.
- **A 409** shows the file's version and the typed one side by side, with "Keep mine" (re-saves with `diskVersion`) and "Use the file's" (replaces the draft).
- **Minimising** the card keeps the draft. **Esc** closes the editor only when nothing is unsaved; otherwise it asks.
- The selection card's "Write a note about this" (Task 8) calls `openEditor(null, [link])`.

- [ ] **Step 4: Run the tests, then check in a browser**

Run: `python3 -m unittest discover -s tests`. Then, with the helper serving a temp copy:
- a new note is created and saved, and its file appears;
- prompt chips tick;
- adding a duplicate custom prompt is refused with the message;
- a second tab editing the same note gets the side-by-side choice;
- after killing the helper, typing shows "Not saved" and Export downloads the text.

- [ ] **Step 5: Commit**

```bash
git add graph tests/test_graph_template.py
git commit -m "notes: the editor - prompts, custom prompts, checks, autosave, conflicts, export"
```

---

### Task 7: Suggested papers and new evidence

**Files:**
- Modify: `graph/parts/editor.js`
- Test: `tests/test_graph_template.py`

**Interfaces:**
- Produces:
  - `STOPWORDS` (the mockup's two lists merged);
  - `stem(w)`: for words over five letters, strip one of `ing|ed|es|s`;
  - `tokens(text) -> string[]`, lowercase words of four or more letters, stopwords removed, stemmed;
  - `buildIndex(items) -> {n, df: Map, docs: Map<id, Set>}`, built from each item's title and sub-area names;
  - `matchScore(noteTokens, id, idx) -> {score, words}`, the sum of `Math.log(idx.n / df)` over the shared distinct tokens;
  - `SUGGEST_AT = 5`;
  - `suggestPapers(note, idx, linked, limit = 8) -> [{id, score, words}]`;
  - `newEvidence(note, items, idx, subOf) -> [{id, why}]`, where `subOf(id)` gives the item's sub-areas.

- [ ] **Step 1: Write the failing test**

```python
@unittest.skipUnless(shutil.which("node"), "node not installed")
def test_matcher_and_new_evidence(self):
    prelude = "const SUGGEST_AT = 5;" + re.search(r"^const STOPWORDS = .*?;$", PAGE_SOURCE, re.M | re.S).group(0)
    got = run_js(["stem", "tokens", "buildIndex", "matchScore", "suggestPapers", "newEvidence"], prelude,
                 """(() => { const items = [
        {id: 'paper:a', type: 'paper', title: 'Gaze tracking leaks identity', subareas: ['Eye-tracking privacy'], firstSeen: '2026-09-01'},
        {id: 'paper:b', type: 'paper', title: 'Keystroke inference from headset motion', subareas: ['Side channels'], firstSeen: '2026-10-20'},
        {id: 'paper:c', type: 'paper', title: 'Gaze identity attacks revisited', subareas: ['Eye-tracking privacy'], firstSeen: '2026-10-21'},
        {id: 'paper:d', type: 'paper', title: 'Unrelated databases', subareas: [], firstSeen: '2026-10-22'}]
        .concat(Array.from({length: 40}, (_, i) => ({id: 'paper:z' + i, type: 'paper', title: 'filler study number ' + i, subareas: [], firstSeen: '2026-01-01'})));
      const idx = buildIndex(items);
      const note = {title: 'Gaze identity', body: 'Claim: gaze tracking leaks identity', links: ['paper:a'], dismissed: [], updated: '2026-10-01T00:00:00Z'};
      const sub = (id) => (items.find((x) => x.id === id) || {}).subareas || [];
      return [tokens('Tracking trackers tracked'), suggestPapers(note, idx, new Set(note.links)).map((s) => s.id),
        newEvidence(note, items, idx, sub), newEvidence({...note, dismissed: ['paper:c']}, items, idx, sub)]; })()""")
    self.assertEqual(got[0], ["track", "tracker", "track"])
    self.assertEqual(got[1], ["paper:c"])                       # a is linked; b and d share nothing rare
    self.assertEqual(got[2], [{"id": "paper:c", "why": "shares the sub-area Eye-tracking privacy"}])
    self.assertEqual(got[3], [])                                 # dismissed
```

New-evidence rule (spec): an item counts when it is a paper, first seen after the note's `updated` date (`firstSeen > updated.slice(0, 10)`), not linked and not dismissed, and it either shares a sub-area with a linked paper or scores at least `SUGGEST_AT`. The `why` reads "shares the sub-area <name>" (preferred), else "shares the words <w1>, <w2>, <w3>".

- [ ] **Step 2: Run it to see it fail**

Run: `python3 -m unittest tests.test_graph_template -v`
Expected: FAIL.

- [ ] **Step 3: Implement**

- **The index** is built once when the editor first opens, over all papers and web sources.
- **Suggested papers:** a section in the editor, recomputed 400 ms after typing stops. Each row shows the title, then "shares <words>" in muted text, then "link".
- **New evidence:** computed for every note at load, and again after a save. It feeds the satellite ring (Task 5), the editor's check row with "Link it" and "Dismiss", and the card's "· N with new evidence".
- **"Link it"** adds the link and saves normally.
- **"Dismiss"** adds to `dismissed` and saves with `keepUpdated: true`. Without the helper, both are disabled with the saving-is-off message.

- [ ] **Step 4: Run the tests**

Run: `python3 -m unittest discover -s tests`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add graph/parts/editor.js tests/test_graph_template.py
git commit -m "notes: suggested papers and new evidence, with the reason for each"
```

---

### Task 8: The notes list and the notes everywhere else on the page

**Files:**
- Modify: `graph/parts/notes.js` (`#noteslist` card), `graph/parts/overview.js` (notes line on "On your map"; "Write a note about this" step), `graph/parts/connects.js` (Notes kind), `graph/parts/status.js` (notes rows), `graph/parts/ask.js` (two patterns), `graph/template.html` (markup)
- Test: `tests/test_graph_template.py`

**Interfaces:**
- Produces:
  - `notesLine(total, withEvidence) -> string`;
  - `filterNotes(notes, q, filter) -> note[]`, where `filter` is `{orbit, interest, archived}` and `q` matches the title and body, ignoring case;
  - `openNotesList(filter)`.
  - `SCHEMA_LINKS` gains `["notes", "papers", "linked to"]` and `["notes", "reports", "written into"]`, and `SCHEMA_KINDS` gains Notes.
  - `statusRows` gains the rows "Notes" and "Saving".
  - `parseQuestion` gains "notes with new evidence" and "notes with no papers" (or "ideas with no papers"). They read `ctx.notes = [{id, orbit, evidence}]` (computed by the page), answer with note ids, skip `passes()` (filters do not apply to notes), and Ask's "Show on the map" opens them in the notes list.
  - `statusRows(data, counts, notesInfo)`: the third argument is optional (`{serving: false, missing: 0}`), so Part 1's calls keep working.

- [ ] **Step 1: Write the failing tests**

```python
@unittest.skipUnless(shutil.which("node"), "node not installed")
def test_notes_line_and_filter(self):
    got = run_js(["notesLine", "filterNotes"], "", """[notesLine(6, 1), notesLine(1, 0), notesLine(0, 0),
      filterNotes([{id: 'a', title: 'Gaze', body: '', orbit: 'outer', archived: null}, {id: 'b', title: 'x', body: 'gaze too', orbit: 'middle', archived: null},
                   {id: 'c', title: 'Gaze old', body: '', orbit: 'outer', archived: '2026-10-01'}], 'GAZE', {}).map((n) => n.id),
      filterNotes([{id: 'a', orbit: 'outer', title: '', body: '', archived: null}, {id: 'c', orbit: 'outer', title: '', body: '', archived: '2026-01-01'}], '', {archived: true}).map((n) => n.id)]""")
    self.assertEqual(got, ["✦ 6 notes · 1 with new evidence", "✦ 1 note", "No notes yet", ["a", "b"], ["c"]])

@unittest.skipUnless(shutil.which("node"), "node not installed")
def test_status_reports_notes(self):
    d = ('{meta: {built: "2026-11-01", newSince: "2026-10-24", warnings: [], coverage: {}, labels: {}, counts: {}}, edges: [], '
         'notes: [{}, {}], notesUnreadable: [{file: "notes/n-x.md", error: "no front matter"}]}')
    rows = run_js(["statusRows"], "", f"statusRows({d}, {{shown: 1, shortlist: 0, offTopic: 0, other: 0}}, {{serving: false, missing: 1}})")
    by = {r["label"]: r for r in rows}
    self.assertIn("2 notes", by["Notes"]["value"])
    self.assertIn("1 could not be read: notes/n-x.md", by["Notes"]["value"])
    self.assertIn("1 with missing links", by["Notes"]["value"])
    self.assertIn("python3 tools/knowledge_graph.py --serve", by["Saving"]["fix"])
```

Plus, in `test_ask_patterns`, with `ctx.notes = [{id: "n1", orbit: "outer", evidence: 0}, {id: "n2", orbit: "middle", evidence: 2}]`: "notes with new evidence" answers `["n2"]` with the step "Notes with new evidence", and "notes with no papers" answers `["n1"]` with the step "Notes in the outer orbit: no papers linked".

- [ ] **Step 2: Run them to see them fail**

Run: `python3 -m unittest tests.test_graph_template -v`
Expected: FAIL.

- [ ] **Step 3: Implement**

- **The notes list.** A card (minimisable, chip "▸ Notes · N · M with new evidence") opened from the "On your map" line, a shell's "+N more", or Ask.
  - Each row: title, orbit word, linked count, updated date (`shortDate`), and a new-evidence mark.
  - Search box; sort by updated, title or orbit; filter chips for each orbit and each interest; a "Show archived" switch.
  - Row actions: open, archive and restore.
- **On your map.** The card adds the `notesLine` and "＋ Note" (`openEditor(null)`).
- **The selection card** adds "Write a note about this" before "Open full details".
- **Status.**
  - Notes: "N notes · M archived · K with missing links · U could not be read: <files>".
  - Saving: "on (the helper is running)", or "off: the page was opened from disk" with the fix "Run python3 tools/knowledge_graph.py --serve, then open the address it prints."
- `statusRows` takes a third argument, `notesInfo = {serving, missing}`.

- [ ] **Step 4: Run the tests**

Run: `python3 -m unittest discover -s tests`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add graph tests/test_graph_template.py
git commit -m "notes: the notes list, and notes on the card, the selection card, How it connects, Status and Ask"
```

---

### Task 9: `/reset notes`, the docs, and the full check

**Files:**
- Modify: `.claude/commands/reset.md`, `graph/README.md`, `USAGE.md`, `README.md`, the spec's "Build status"
- Test: `tests/test_knowledge_graph.py` (`DocsDriftTests`)

- [ ] **Step 1: Write the failing test**

```python
def test_reset_has_a_notes_scope(self):
    text = (REPO_ROOT / ".claude" / "commands" / "reset.md").read_text()
    self.assertIn("`notes`", text)
    self.assertIn("Notes reset will delete", text)
    self.assertRegex(text, r"(?s)`all`.*separate.*notes")     # all asks separately before clearing notes
```

- [ ] **Step 2: Run it to see it fail**

Run: `python3 -m unittest tests.test_knowledge_graph.DocsDriftTests -v`
Expected: FAIL.

- [ ] **Step 3: Write**

- **`reset.md`:**
  - a `notes` scope: it lists the number of note files, custom prompts and annotations, then deletes `notes/*`;
  - `all` covers the other five scopes, then asks a separate question for notes, naming the count: "Your N notes are your own writing and cannot be rebuilt. Type `DELETE NOTES` to delete them too, or anything else to keep them."
- **`graph/README.md`:** a "Notes" section (satellites and orbits, the editor and guide, the helper and its safety, read-only and export, where files live). Its "Performance" section gains the satellite cap.
- **`USAGE.md` and `README.md`:** the notes paragraph; the README diagram gains "notes/ <-> --serve helper".
- **The spec's "Build status":** Part 2 built, with this plan's decisions listed.

- [ ] **Step 4: The full check in a real browser**

Build the live library in a temp copy and run `--serve` against it. Then:
- write a note from a paper's card;
- link a second paper and watch it move inward;
- mark it as written into a report and watch it move to the inner orbit;
- dismiss a new-evidence suggestion;
- archive it and restore it;
- open the page from disk and confirm the notes show read-only with Export;
- confirm Status reports saving on and off correctly.

Run: `python3 -m unittest discover -s tests && python3 tools/knowledge_graph.py && python3 tools/knowledge_graph.py --check && python3 tools/security_guards.py`
Expected: all PASS, `graph/index.html: PASS (0 errors)`, `security_guards: OK`.

- [ ] **Step 5: Commit, then release** (after the whole-branch review)

```bash
git add .claude/commands/reset.md graph/README.md USAGE.md README.md docs tests
git commit -m "notes: /reset notes, docs, build status"
git fetch origin && git rebase origin/master && git push origin HEAD:master
```

Then watch CI (`gh run watch <id> --repo BleOdel/ai-research-assistant --interval 30 --exit-status`), pull both clones, rebuild the live page, and remove the worktree.
