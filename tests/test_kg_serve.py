import json
import os
import shutil
import signal
import subprocess
import sys
import time
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools"))
import kg_serve  # noqa: E402


class HelperFixture(unittest.TestCase):
    """A helper serving a temp repo layout on a free port, called over real HTTP."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        (self.root / "graph").mkdir()
        (self.root / "graph" / "index.html").write_text("<html>map</html>")
        (self.root / "research" / "fulltext").mkdir(parents=True)
        (self.root / "research" / "fulltext" / "a.pdf").write_bytes(b"%PDF-1.4 a")
        (self.root / "research" / "seen_sources.json").write_text("{}")
        (self.root / "reports" / "r1").mkdir(parents=True)
        (self.root / "reports" / "r1" / "report.pdf").write_bytes(b"%PDF-1.4 r")
        (self.root / "secret.txt").write_text("secret")
        self.layout = sorted(p.name for p in self.root.iterdir())
        self.server = kg_serve.make_server(self.root, "tok")
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def call(self, method, path, body=None, headers=None):
        data = body if isinstance(body, bytes) else (None if body is None else json.dumps(body).encode())
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", data=data, method=method,
                                     headers={"Content-Type": "application/json", **(headers or {})})
        try:
            with urllib.request.urlopen(req) as r:
                status, raw, hdrs = r.status, r.read(), r.headers
        except urllib.error.HTTPError as e:
            status, raw, hdrs = e.code, e.read(), e.headers
        try:
            payload = json.loads(raw)
        except ValueError:
            payload = raw.decode("utf-8", "replace")
        return status, payload, hdrs

    def api(self, path, body, token="tok", extra=None):
        headers = dict(extra or {})
        if token:
            headers["X-KG-Token"] = token
        data = body.encode() if isinstance(body, str) else body
        return self.call("POST", path, data, headers)


class RequestTests(HelperFixture):
    def test_page_needs_the_token_and_sets_the_cookie(self):
        self.assertEqual(self.call("GET", "/")[0], 403)
        status, _, headers = self.call("GET", "/?t=tok")
        self.assertEqual(status, 200)
        self.assertIn("HttpOnly", headers["Set-Cookie"])
        self.assertIn("SameSite=Strict", headers["Set-Cookie"])
        self.assertEqual(self.call("GET", "/index.html", headers={"Cookie": "kgt=tok"})[0], 200)

    def test_pdfs_only_from_their_two_folders(self):
        cookie = {"Cookie": "kgt=tok"}
        self.assertEqual(self.call("GET", "/research/fulltext/a.pdf", headers=cookie)[0], 200)
        self.assertEqual(self.call("GET", "/reports/r1/report.pdf", headers=cookie)[0], 200)
        for bad in ("/research/fulltext/../../secret.txt", "/research/fulltext/%2e%2e/%2e%2e/secret.txt",
                    "/reports/r1/../../secret.txt", "/research/seen_sources.json", "/secret.txt",
                    "/reports/r1/notes.pdf"):
            self.assertEqual(self.call("GET", bad, headers=cookie)[0], 404, bad)
        self.assertEqual(self.call("GET", "/research/fulltext/a.pdf")[0], 403)

    def test_state(self):
        status, body, _ = self.call("GET", "/api/state", headers={"X-KG-Token": "tok"})
        self.assertEqual(status, 200)
        self.assertEqual(set(body), {"built", "notes", "unreadable", "prompts"})
        self.assertEqual(self.call("GET", "/api/ping", headers={"X-KG-Token": "tok"})[1], {"ok": True})

    def test_save_creates_then_conflicts(self):
        st, r, _ = self.api("/api/note", {"note": {"title": "First", "links": [], "body": "Claim: x"}})
        self.assertEqual(st, 200, r)
        nid, v1 = r["note"]["id"], r["version"]
        self.assertTrue((self.root / "notes" / f"{nid}.md").exists())
        st, r2, _ = self.api("/api/note", {"note": {**r["note"], "body": "tab A"}, "version": v1})
        self.assertEqual(st, 200)
        st, r3, _ = self.api("/api/note", {"note": {**r["note"], "body": "tab B"}, "version": v1})   # stale
        self.assertEqual(st, 409)
        self.assertEqual(r3["disk"]["body"], "tab A")
        st, _, _ = self.api("/api/note", {"note": {**r["note"], "body": "tab B"}, "version": r3["diskVersion"]})
        self.assertEqual(st, 200)

    def test_dismiss_keeps_updated(self):
        st, r, _ = self.api("/api/note", {"note": {"title": "T", "links": [], "body": ""}})
        st, r2, _ = self.api("/api/note", {"note": {**r["note"], "dismissed": ["paper:k"]}, "version": r["version"],
                                           "keepUpdated": True})
        self.assertEqual(st, 200)
        self.assertEqual(r2["note"]["updated"], r["note"]["updated"])
        self.assertEqual(r2["note"]["dismissed"], ["paper:k"])

    def test_archive_and_restore(self):
        st, r, _ = self.api("/api/note", {"note": {"title": "T", "links": [], "body": ""}})
        st, r2, _ = self.api("/api/note/archive", {"id": r["note"]["id"], "archived": True, "version": r["version"]})
        self.assertEqual(st, 200)
        self.assertTrue(r2["note"]["archived"])
        st, r3, _ = self.api("/api/note/archive", {"id": r["note"]["id"], "archived": False, "version": r2["version"]})
        self.assertIsNone(r3["note"]["archived"])

    def test_unreadable_note_is_never_overwritten(self):
        (self.root / "notes").mkdir(exist_ok=True)
        (self.root / "notes" / "n-20261101-ffffff.md").write_text("hand-broken")
        st, r, _ = self.api("/api/note", {"note": {"id": "n-20261101-ffffff", "title": "T", "links": [], "body": ""},
                                          "version": None})
        self.assertEqual(st, 409)
        self.assertIn("could not be read", r["error"])
        self.assertEqual((self.root / "notes" / "n-20261101-ffffff.md").read_text(), "hand-broken")

    def test_hostile_requests_are_refused(self):
        self.assertEqual(self.api("/api/note", {"note": {}}, token=None)[0], 403)
        self.assertEqual(self.api("/api/note", {"note": {}}, token="wrong")[0], 403)
        self.assertEqual(self.api("/api/note", {"note": {}}, extra={"Host": "evil.example:80"})[0], 403)
        self.assertEqual(self.api("/api/note", {"note": {}}, extra={"Origin": "https://evil.example"})[0], 403)
        self.assertEqual(self.api("/api/note", "x" * (300 * 1024))[0], 413)
        self.assertEqual(self.api("/api/note", "{not json")[0], 400)
        st, _, _ = self.api("/api/note", {"note": {"id": "../../secret", "title": "T", "links": [], "body": ""}})
        self.assertEqual(st, 400)
        self.assertEqual(self.call("GET", "/api/state")[0], 403)
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), self.layout)   # nothing new at the root

    def test_prompts_are_checked(self):
        st, r, _ = self.api("/api/prompts", {"prompts": [{"name": "Method", "question": "How?"}]})
        self.assertEqual(st, 200)
        self.assertEqual(json.loads((self.root / "notes" / "guide.json").read_text()), [{"name": "Method", "question": "How?"}])
        for bad in ([{"name": "claim", "question": ""}], [{"name": "x" * 25, "question": ""}],
                    [{"name": "A", "question": ""}, {"name": "a", "question": ""}], [{"name": "", "question": ""}]):
            self.assertEqual(self.api("/api/prompts", {"prompts": bad})[0], 400, bad)



class LifecycleTests(unittest.TestCase):
    """--serve run the way /graph runs it: a real background helper in a temp repo."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        shutil.copytree(REPO_ROOT / "tools", self.root / "tools", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(REPO_ROOT / "graph", self.root / "graph", ignore=shutil.ignore_patterns("index.html", ".serve.json"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.addCleanup(self.stop_helper)
        self.record = self.root / "graph" / ".serve.json"

    def stop_helper(self):
        try:
            os.kill(json.loads(self.record.read_text())["pid"], signal.SIGTERM)
        except (OSError, ValueError, KeyError):
            pass

    def run_graph(self, *args, env=None):
        return subprocess.run([sys.executable, str(self.root / "tools" / "knowledge_graph.py"), *args],
                              capture_output=True, text=True, env=env, timeout=60)

    def wait_until_stopped(self, seconds=15):
        deadline = time.time() + seconds
        while self.record.exists() and time.time() < deadline:
            time.sleep(0.5)
        self.assertFalse(self.record.exists(), "the helper did not stop when idle")

    def test_start_reuses_a_live_helper_and_stops_when_idle(self):
        env = dict(os.environ, KG_IDLE_SECONDS="3")
        first = self.run_graph("--serve", "--no-open", env=env)
        self.assertEqual(first.returncode, 0, first.stderr)
        addr = first.stdout.strip().splitlines()[-1]
        self.assertRegex(addr, r"^http://127\.0\.0\.1:\d+/\?t=[0-9a-f]{32}$")
        second = self.run_graph("--serve", "--no-open", env=env)
        self.assertEqual(second.stdout.strip().splitlines()[-1], addr)        # same helper, not a new one
        self.assertTrue((self.root / "graph" / "index.html").exists())          # it rebuilt on start
        self.wait_until_stopped()                                               # stopped itself when idle

    def test_a_stale_record_is_replaced(self):
        self.record.write_text(json.dumps({"port": 1, "token": "x", "pid": 999999, "started": 0}))
        r = self.run_graph("--serve", "--no-open", env=dict(os.environ, KG_IDLE_SECONDS="2"))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn(":1/", r.stdout)
        self.wait_until_stopped()        # so no helper outlives the temp folder


if __name__ == "__main__":
    unittest.main()
