#!/usr/bin/env python3
"""The library map's local helper: lets the page save notes, on this computer only.

A page opened from disk cannot write files, so `python3 tools/knowledge_graph.py --serve`
starts this small server. It serves the built page and the PDFs the page links to, and
accepts note, archive, prompt and annotation writes into notes/ - nothing else, nowhere
else.

Safety:
- it binds to 127.0.0.1 and answers only requests whose Host is 127.0.0.1:<port> or
  localhost:<port> (so a web page cannot reach it through a DNS trick);
- every write needs the run's random token in an X-KG-Token header, which a page on
  another site cannot set, and a request carrying a foreign Origin is refused;
- the page and the PDFs need the token in their address (?t=); there is no cookie,
  because browsers send 127.0.0.1 cookies to every local server, so a cookie would hand
  the token to other local web tools;
- the token reaches the background helper through its environment, not its command line
  (which every user on the machine can list), and graph/.serve.json is readable by this
  user only;
- file names come from the note id (checked against kg_notes.ID_RE), never from the
  request path; PDFs are served read-only from research/fulltext/ and
  reports/<slug>/report.pdf only, after resolving the path inside those folders;
- writes are atomic and locked (state.atomic_write under state.Lock), and a save must
  carry the version it loaded: a file changed since (by hand, by Claude, in another
  tab) is never overwritten - the page is sent both versions to choose from.

Stdlib only. It logs nothing, so the token can never end up in a log.
"""

import json
import os
import re
import secrets
import signal
import subprocess
import sys
import tempfile
import time
import urllib.request
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

import kg_notes
import state

MAX_BODY = 256 * 1024
PRESET_NAMES = ("claim", "evidence", "against", "gap", "next step")
MAX_PROMPTS, MAX_PROMPT_NAME, MAX_PROMPT_QUESTION = 50, 24, 200
UNREADABLE = "This note's file could not be read; fix or remove it first."
PDF_FULLTEXT = re.compile(r"^/research/fulltext/(.+)$")
PDF_REPORT = re.compile(r"^/reports/([^/]+)/report\.pdf$")


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Refused(Exception):
    def __init__(self, status: int, message: str, extra: dict | None = None):
        super().__init__(message)
        self.status, self.message, self.extra = status, message, extra or {}


class Handler(BaseHTTPRequestHandler):
    server_version = "kg-serve"

    # ---------- plumbing ----------
    def log_message(self, fmt, *args):  # silent: a request line can carry the token
        pass

    def send_json(self, status: int, payload: dict, headers: dict | None = None):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, path: Path, ctype: str, headers: dict | None = None):
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def check_host(self):
        port = self.server.server_address[1]
        allowed = {f"127.0.0.1:{port}", f"localhost:{port}"}
        if self.headers.get("Host") not in allowed:
            raise Refused(403, "This helper answers only on this computer.")
        origin = self.headers.get("Origin")
        if origin and origin not in {f"http://{h}" for h in allowed}:
            raise Refused(403, "Requests from other sites are refused.")

    def token_ok(self, value) -> bool:
        return isinstance(value, str) and secrets.compare_digest(value, self.server.token)

    def page_token_ok(self) -> bool:
        """The page and its PDFs carry the token in their address."""
        return self.token_ok(parse_qs(urlsplit(self.path).query).get("t", [None])[0])

    def require_header_token(self):
        if not self.token_ok(self.headers.get("X-KG-Token")):
            raise Refused(403, "Open the map from the address the helper printed.")
        self.server.last_activity = time.monotonic()

    def read_json(self, limit: int = MAX_BODY) -> dict:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            raise Refused(400, "The request's length was not valid.") from None
        if length < 0 or length > limit:
            raise Refused(413, "That is too large to save.")
        try:
            data = json.loads(self.rfile.read(length) or b"{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise Refused(400, "The request was not valid JSON.") from None
        if not isinstance(data, dict):
            raise Refused(400, "The request was not valid JSON.")
        return data

    def handle_refusals(self, fn):
        """Every request gets an answer the page can show: a dropped connection would read
        as "the helper is not answering" whatever the real reason was."""
        try:
            fn()
        except Refused as r:
            self.send_json(r.status, {"error": r.message, **r.extra})
        except state.StateError:   # the note's lock is held: another save is still writing
            self.send_json(503, {"error": "Another save is still writing this note; try again in a moment."})
        except Exception as exc:
            try:   # the type only: a message can quote a path or the note's text
                self.send_json(500, {"error": f"The helper hit an unexpected error ({type(exc).__name__})."})
            except OSError:
                pass

    # ---------- reading ----------
    def do_GET(self):
        self.handle_refusals(self._get)

    def _get(self):
        self.check_host()
        root, path = self.server.root, urlsplit(self.path).path
        if path in ("/", "/index.html"):
            if not self.page_token_ok():
                raise Refused(403, "Open the map from the address the helper printed.")
            self.server.last_activity = time.monotonic()
            page = root / "graph" / "index.html"
            if not page.is_file():
                raise Refused(503, "The map is not built yet: run python3 tools/knowledge_graph.py.")
            return self.send_file(page, "text/html; charset=utf-8")
        pdf = PDF_FULLTEXT.match(path) or PDF_REPORT.match(path)
        if pdf:
            if not self.page_token_ok():
                raise Refused(403, "Open the map from the address the helper printed.")
            self.server.last_activity = time.monotonic()
            if PDF_FULLTEXT.match(path):
                folder, rel = root / "research" / "fulltext", unquote(pdf.group(1))
            else:
                folder, rel = root / "reports", unquote(pdf.group(1)) + "/report.pdf"
            try:
                target = (folder / rel).resolve()
            except (ValueError, OSError):   # a NUL byte or a path the system refuses
                raise Refused(404, "Not found.") from None
            if not (target.is_relative_to(folder.resolve()) and target.suffix.lower() == ".pdf" and target.is_file()):
                raise Refused(404, "Not found.")
            return self.send_file(target, "application/pdf")
        if path == "/api/ping":
            self.require_header_token()
            return self.send_json(200, {"ok": True})
        if path == "/api/state":
            self.require_header_token()
            notes, unreadable = kg_notes.load(root / "notes")
            marks, marks_version, marks_error = kg_notes.load_annotations(root / "notes")
            return self.send_json(200, {"built": self.built(), "notes": notes, "unreadable": unreadable,
                                        "prompts": kg_notes.load_prompts(root / "notes"), "annotations": marks,
                                        "annotationsVersion": marks_version, "annotationsError": marks_error})
        raise Refused(404, "Not found.")

    def built(self):
        page = self.server.root / "graph" / "index.html"
        return page.stat().st_mtime if page.is_file() else None

    # ---------- writing ----------
    def do_POST(self):
        self.handle_refusals(self._post)

    def _post(self):
        self.check_host()
        self.require_header_token()
        path = urlsplit(self.path).path
        routes = {"/api/note": self.save_note, "/api/note/archive": self.archive_note,
                  "/api/prompts": self.save_prompts, "/api/annotations": self.save_annotations,
                  "/api/heartbeat": self.heartbeat}
        if path not in routes:
            raise Refused(404, "Not found.")
        # Marks are one file holding every saved view, so they get a larger limit than a note.
        routes[path](self.read_json(kg_notes.MAX_ANNOT_BYTES if path == "/api/annotations" else MAX_BODY))

    def heartbeat(self, _body):
        self.send_json(200, {"built": self.built()})

    def note_path(self, note_id) -> Path:
        if not isinstance(note_id, str) or not kg_notes.ID_RE.match(note_id):
            raise Refused(400, "The note id is not valid.")
        return self.server.root / "notes" / f"{note_id}.md"

    def current(self, path: Path, version) -> dict | None:
        """The note on disk, after checking the save was made against it."""
        if not path.exists():
            # Saved against a version, yet gone: deleted elsewhere (/reset notes, by hand).
            # Never bring it back silently.
            if version is not None:
                raise Refused(409, "This note was deleted elsewhere since you opened it.", {"deleted": True})
            return None
        try:
            text = path.read_text(encoding="utf-8")
            disk = kg_notes.parse(text)
        except (kg_notes.NoteError, UnicodeDecodeError):
            raise Refused(409, UNREADABLE) from None
        if version != kg_notes.version(text):
            raise Refused(409, "This note changed since you opened it.",
                          {"conflict": True, "disk": disk, "diskVersion": kg_notes.version(text)})
        return disk

    def write(self, path: Path, note: dict):
        problems = kg_notes.validate(note)
        if problems:
            raise Refused(400, "Not saved: " + "; ".join(problems) + ".")
        text = kg_notes.render(note)
        state.atomic_write(path, text)
        self.send_json(200, {"note": {**note, "version": kg_notes.version(text)}, "version": kg_notes.version(text)})

    def save_note(self, body):
        given = body.get("note")
        if not isinstance(given, dict):
            raise Refused(400, "There was no note to save.")
        now = now_iso()
        if not given.get("id"):
            for _ in range(20):
                note_id = kg_notes.new_id(now[:10])
                if not (self.server.root / "notes" / f"{note_id}.md").exists():
                    break
            path = self.note_path(note_id)
            note = {**{k: given.get(k) for k in kg_notes.FIELDS}, "id": note_id, "created": now, "updated": now,
                    "archived": None, "body": given.get("body", ""), "extra": []}
            for key in ("links", "dismissed"):
                note[key] = note[key] or []
            with state.Lock(path):
                return self.write(path, note)
        path = self.note_path(given["id"])
        with state.Lock(path):
            disk = self.current(path, body.get("version"))
            note = {k: given.get(k) for k in kg_notes.FIELDS}
            note["body"] = given.get("body", "")
            note["extra"] = disk["extra"] if disk else []
            note["created"] = (disk or {}).get("created") or given.get("created") or now
            # Archiving belongs to /api/note/archive; an edit never changes it.
            note["archived"] = (disk or {}).get("archived")
            note["updated"] = ((disk or {}).get("updated") or given.get("updated") or now) if body.get("keepUpdated") else now
            for key in ("links", "dismissed"):
                note[key] = note[key] if note[key] is not None else []
            self.write(path, note)

    def archive_note(self, body):
        path = self.note_path(body.get("id"))
        with state.Lock(path):
            disk = self.current(path, body.get("version"))
            if disk is None:
                raise Refused(404, "That note no longer exists.")
            disk["archived"] = now_iso() if body.get("archived") else None
            self.write(path, disk)

    def save_prompts(self, body):
        prompts = body.get("prompts")
        if not isinstance(prompts, list) or len(prompts) > MAX_PROMPTS:
            raise Refused(400, f"Keep to {MAX_PROMPTS} prompts or fewer.")
        seen, clean = set(PRESET_NAMES), []
        for p in prompts:
            name = (p.get("name") if isinstance(p, dict) else None) or ""
            question = p.get("question", "") if isinstance(p, dict) else ""
            if not isinstance(name, str) or not name.strip():
                raise Refused(400, "Give each prompt a name.")
            name = name.strip()
            if len(name) > MAX_PROMPT_NAME:
                raise Refused(400, f"Keep prompt names to {MAX_PROMPT_NAME} characters or fewer.")
            if name.casefold() in seen:
                raise Refused(400, f"The prompt {name} already exists.")
            if not isinstance(question, str) or len(question) > MAX_PROMPT_QUESTION:
                raise Refused(400, "Keep each guiding question to 200 characters or fewer.")
            seen.add(name.casefold())
            clean.append({"name": name, "question": question})
        path = self.server.root / "notes" / "guide.json"
        with state.Lock(path):
            state.atomic_write(path, json.dumps(clean, ensure_ascii=False, indent=2) + "\n")
        self.send_json(200, {"prompts": clean})


    def save_annotations(self, body):
        """Save notes/annotations.json whole, against the version the page loaded: the same
        rules as a note - never over a change made elsewhere, never over a file that cannot
        be read, never bringing back a file deleted elsewhere."""
        doc = body.get("annotations")
        problems = kg_notes.validate_annotations(doc)
        if problems:
            raise Refused(400, "Not saved: " + "; ".join(problems[:3]) + ".")
        path = self.server.root / "notes" / kg_notes.ANNOTATIONS
        with state.Lock(path):
            disk, disk_version, error = kg_notes.load_annotations(path.parent)
            if error:
                raise Refused(409, f"notes/{kg_notes.ANNOTATIONS} could not be read; fix or remove it first.")
            given = body.get("version")
            if disk_version is None and given is not None:
                raise Refused(409, "Your saved marks were deleted elsewhere.", {"deleted": True})
            if disk_version != given:
                raise Refused(409, "Your marks changed somewhere else since this page loaded them.",
                              {"conflict": True, "disk": disk, "diskVersion": disk_version})
            text = json.dumps(doc, ensure_ascii=False, separators=(",", ":"))
            state.atomic_write(path, text)
        self.send_json(200, {"version": kg_notes.version(text)})


def make_server(root: Path, token: str, port: int = 0) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    server.root, server.token = Path(root), token
    server.last_activity = time.monotonic()
    return server


# ---------- starting and stopping ----------
def serve_file(root: Path) -> Path:
    """Where a running helper records its port, token and process: graph/.serve.json,
    gitignored with the rest of graph/."""
    return Path(root) / "graph" / ".serve.json"


def idle_seconds() -> int:
    """Stop after this long with no request: the open page sends a heartbeat every
    minute, so 30 minutes idle means the map has been closed."""
    return int(os.environ.get("KG_IDLE_SECONDS", "1800"))


def address(record: dict) -> str:
    return f"http://127.0.0.1:{record['port']}/?t={record['token']}"


def _alive(pid) -> bool:
    try:
        os.kill(int(pid), 0)
    except (OSError, ValueError, TypeError):
        return False
    return True


def _answers(record: dict) -> bool:
    req = urllib.request.Request(f"http://127.0.0.1:{record['port']}/api/ping",
                                 headers={"X-KG-Token": record["token"]})
    try:
        with urllib.request.urlopen(req, timeout=2) as r:
            return r.status == 200
    except OSError:
        return False


def running(root: Path) -> dict | None:
    """The helper already serving ROOT, if its process is alive and it answers."""
    try:
        record = json.loads(serve_file(root).read_text())
    except (OSError, ValueError):
        return None
    if not isinstance(record, dict) or not {"port", "token", "pid"} <= set(record):
        return None
    return record if _alive(record["pid"]) and _answers(record) else None


def start(root: Path, open_browser: bool) -> str:
    """Start the helper in the background (or find the one running) and return the
    address to open. Raises RuntimeError, in plain words, if it does not come up."""
    record = running(root)
    if record is None:
        token = secrets.token_hex(16)
        subprocess.Popen([sys.executable, str(Path(root) / "tools" / "knowledge_graph.py"), "--serve-foreground"],
                         cwd=root, env={**os.environ, "KG_SERVE_TOKEN": token}, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            try:
                candidate = json.loads(serve_file(root).read_text())
            except (OSError, ValueError):
                candidate = None
            if candidate and candidate.get("token") == token and _answers(candidate):
                record = candidate
                break
            time.sleep(0.2)
        if record is None:
            raise RuntimeError("The helper did not start within 10 seconds; "
                               "run python3 tools/knowledge_graph.py --serve again.")
    if open_browser:
        webbrowser.open(address(record))
    return address(record)


def _write_private(path: Path, text: str) -> None:
    """Write atomically, readable by this user only: the record holds the token."""
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")   # mode 0600
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def run_foreground(root: Path, token: str, rebuild) -> None:
    """The helper itself: rebuild the page, serve until idle, then tidy up."""
    rebuild()
    server = make_server(root, token)
    server.timeout = 1
    record = {"port": server.server_address[1], "token": token, "pid": os.getpid(), "started": time.time()}
    _write_private(serve_file(root), json.dumps(record) + "\n")
    # kill, a logout or a shutdown sends SIGTERM: leave through the tidy-up below.
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    try:
        while time.monotonic() - server.last_activity <= idle_seconds():
            server.handle_request()
    finally:
        server.server_close()
        try:
            if json.loads(serve_file(root).read_text()).get("token") == token:
                serve_file(root).unlink()
        except (OSError, ValueError):
            pass


if __name__ == "__main__":
    print("Start the helper with: python3 tools/knowledge_graph.py --serve", file=sys.stderr)
    sys.exit(2)
