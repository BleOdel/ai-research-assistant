#!/usr/bin/env python3
"""The library map's local helper: lets the page save notes, on this computer only.

A page opened from disk cannot write files, so `python3 tools/knowledge_graph.py --serve`
starts this small server. It serves the built page and the PDFs the page links to, and
accepts note, archive and prompt writes into notes/ - nothing else, nowhere else.

Safety:
- it binds to 127.0.0.1 and answers only requests whose Host is 127.0.0.1:<port> or
  localhost:<port> (so a web page cannot reach it through a DNS trick);
- every write needs the run's random token in an X-KG-Token header, which a page on
  another site cannot set, and a request carrying a foreign Origin is refused;
- the page and the PDFs need the token once in the address; the helper then sets an
  HttpOnly, SameSite=Strict cookie so the page's PDF links work;
- file names come from the note id (checked against kg_notes.ID_RE), never from the
  request path; PDFs are served read-only from research/fulltext/ and
  reports/<slug>/report.pdf only, after resolving the path inside those folders;
- writes are atomic and locked (state.atomic_write under state.Lock), and a save must
  carry the version it loaded: a file changed since (by hand, by Claude, in another
  tab) is never overwritten - the page is sent both versions to choose from.

Stdlib only. It logs nothing, so the token can never end up in a log.
"""

import json
import re
import secrets
import sys
import time
from datetime import datetime, timezone
from http import cookies
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

    def page_token_ok(self) -> tuple[bool, bool]:
        """(authorised, came from the address) for the page and its PDFs."""
        q = parse_qs(urlsplit(self.path).query).get("t", [None])[0]
        if self.token_ok(q):
            return True, True
        jar = cookies.SimpleCookie(self.headers.get("Cookie", ""))
        return (self.token_ok(jar["kgt"].value) if "kgt" in jar else False), False

    def require_header_token(self):
        if not self.token_ok(self.headers.get("X-KG-Token")):
            raise Refused(403, "Open the map from the address the helper printed.")
        self.server.last_activity = time.monotonic()

    def read_json(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            raise Refused(413, "That is too large to save.")
        try:
            data = json.loads(self.rfile.read(length) or b"{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise Refused(400, "The request was not valid JSON.") from None
        if not isinstance(data, dict):
            raise Refused(400, "The request was not valid JSON.")
        return data

    def handle_refusals(self, fn):
        try:
            fn()
        except Refused as r:
            self.send_json(r.status, {"error": r.message, **r.extra})

    # ---------- reading ----------
    def do_GET(self):
        self.handle_refusals(self._get)

    def _get(self):
        self.check_host()
        root, path = self.server.root, urlsplit(self.path).path
        if path in ("/", "/index.html"):
            ok, from_address = self.page_token_ok()
            if not ok:
                raise Refused(403, "Open the map from the address the helper printed.")
            self.server.last_activity = time.monotonic()
            page = root / "graph" / "index.html"
            if not page.is_file():
                raise Refused(503, "The map is not built yet: run python3 tools/knowledge_graph.py.")
            cookie = {"Set-Cookie": f"kgt={self.server.token}; HttpOnly; SameSite=Strict; Path=/"} if from_address else None
            return self.send_file(page, "text/html; charset=utf-8", cookie)
        pdf = PDF_FULLTEXT.match(path) or PDF_REPORT.match(path)
        if pdf:
            if not self.page_token_ok()[0]:
                raise Refused(403, "Open the map from the address the helper printed.")
            self.server.last_activity = time.monotonic()
            if PDF_FULLTEXT.match(path):
                folder, rel = root / "research" / "fulltext", unquote(pdf.group(1))
            else:
                folder, rel = root / "reports", unquote(pdf.group(1)) + "/report.pdf"
            target = (folder / rel).resolve()
            if not (target.is_relative_to(folder.resolve()) and target.suffix.lower() == ".pdf" and target.is_file()):
                raise Refused(404, "Not found.")
            return self.send_file(target, "application/pdf")
        if path == "/api/ping":
            self.require_header_token()
            return self.send_json(200, {"ok": True})
        if path == "/api/state":
            self.require_header_token()
            notes, unreadable = kg_notes.load(root / "notes")
            return self.send_json(200, {"built": self.built(), "notes": notes, "unreadable": unreadable,
                                        "prompts": kg_notes.load_prompts(root / "notes")})
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
                  "/api/prompts": self.save_prompts, "/api/heartbeat": self.heartbeat}
        if path not in routes:
            raise Refused(404, "Not found.")
        routes[path](self.read_json())

    def heartbeat(self, _body):
        self.send_json(200, {"built": self.built()})

    def note_path(self, note_id) -> Path:
        if not isinstance(note_id, str) or not kg_notes.ID_RE.match(note_id):
            raise Refused(400, "The note id is not valid.")
        return self.server.root / "notes" / f"{note_id}.md"

    def current(self, path: Path, version) -> dict | None:
        """The note on disk, after checking the save was made against it."""
        if not path.exists():
            return None
        text = path.read_text(encoding="utf-8")
        try:
            disk = kg_notes.parse(text)
        except kg_notes.NoteError:
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


def make_server(root: Path, token: str, port: int = 0) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    server.root, server.token = Path(root), token
    server.last_activity = time.monotonic()
    return server


if __name__ == "__main__":
    print("Start the helper with: python3 tools/knowledge_graph.py --serve", file=sys.stderr)
    sys.exit(2)
