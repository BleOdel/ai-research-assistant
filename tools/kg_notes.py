#!/usr/bin/env python3
"""The researcher's notes on the library map: one Markdown file per note in notes/.

A note file is a front-matter block and the body as written:

    ---
    id: "n-20261101-a1b2c3"
    title: "Gaze noise defences"
    links: ["paper:10.1145/...", "subarea:XR/Immersive Systems Security & Privacy::Eye-tracking"]
    in_report: null
    dismissed: []
    created: "2026-11-01T10:00:00Z"
    updated: "2026-11-01T10:05:00Z"
    archived: null
    ---
    Claim: ...

Each front-matter value is JSON, so a title with a colon or a quote survives. A hand
edit that writes a plain unquoted string is read as that string; a key this module does
not know is kept, line for line. Links are typed: paper:<state key>, web:<state key>,
group:<lab id>, subarea:<interest>::<sub-area> ("::" because interest and sub-area names
contain "/"). notes/ is gitignored: the notes are the researcher's own writing.

Marks drawn on the map live beside the notes, in notes/annotations.json: a list of saved
views, each the globe's camera and the filters it was drawn under, with its marks in globe
units (so they stay on what they marked whatever the window size).

Read by tools/knowledge_graph.py (to embed the notes in the page) and written only by
tools/kg_serve.py, the local helper. Stdlib only.
"""

import hashlib
import json
import math
import re
import secrets
from datetime import datetime
from pathlib import Path

import state

ROOT = state.ROOT
NOTES = ROOT / "notes"
ID_RE = re.compile(r"^n-[0-9]{8}-[0-9a-f]{6}\Z")   # \Z: "$" would let a trailing newline through
FIELDS = ("id", "title", "links", "in_report", "dismissed", "created", "updated", "archived")
LINK_RE = re.compile(r"^(paper|web|group|subarea):.+")
DEFAULTS = {"links": [], "dismissed": []}
MAX_TITLE, MAX_BODY, MAX_LINKS = 200, 200_000, 500


class NoteError(ValueError):
    """A note file that cannot be read; the message says why, in plain words."""


def parse(text: str) -> dict:
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        raise NoteError("no front matter (the file must start with a --- line)")
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        raise NoteError("the front matter has no closing --- line") from None
    note = {k: list(DEFAULTS[k]) if k in DEFAULTS else None for k in FIELDS}
    extra = []
    for line in lines[1:end]:
        if not line.strip():
            continue
        key, sep, raw = line.partition(":")
        key, raw = key.strip(), raw.strip()
        if not sep or key not in FIELDS:
            extra.append(line)
            continue
        try:
            note[key] = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            if raw[:1] in "[{\"":
                raise NoteError(f"the value of {key} is not valid") from None
            note[key] = raw  # a hand edit: a plain, unquoted string
    for key in DEFAULTS:
        if note[key] is None:
            note[key] = []
    body = "\n".join(lines[end + 1:])
    note["body"] = body
    note["extra"] = extra
    return note


def render(note: dict) -> str:
    head = [f"{k}: {json.dumps(note.get(k, DEFAULTS.get(k)), ensure_ascii=False)}" for k in FIELDS]
    return "\n".join(["---", *head, *note.get("extra", []), "---", note.get("body", "")])


def _is_iso(value) -> bool:
    if value is None:
        return True
    if not isinstance(value, str):
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def validate(note: dict) -> list[str]:
    """What is wrong with NOTE, in plain words; [] when it can be saved."""
    problems = []
    if not isinstance(note.get("id"), str) or not ID_RE.match(note["id"]):
        problems.append("the note id is not valid")
    title = note.get("title")
    if not isinstance(title, str) or not title.strip():
        problems.append("the note needs a title")
    elif len(title) > MAX_TITLE:
        problems.append(f"the title is longer than {MAX_TITLE} characters")
    if not isinstance(note.get("body", ""), str) or len(note.get("body", "")) > MAX_BODY:
        problems.append(f"the note is longer than {MAX_BODY:,} characters")
    for key in ("links", "dismissed"):
        values = note.get(key)
        if not isinstance(values, list) or len(values) > MAX_LINKS:
            problems.append(f"{key} must be a list of at most {MAX_LINKS}")
        elif any(not isinstance(v, str) or not LINK_RE.match(v) for v in values):
            problems.append(f"{key} holds an entry that is not a paper:, web:, group: or subarea: link")
    if note.get("in_report") is not None and not isinstance(note["in_report"], str):
        problems.append("in_report must be a report name or empty")
    for key in ("created", "updated", "archived"):
        if not _is_iso(note.get(key)):
            problems.append(f"{key} is not a date and time")
    return problems


def version(text: str) -> str:
    """A note file's version: what a save must match so it never overwrites an edit made
    elsewhere since the page loaded it."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def new_id(today: str) -> str:
    return f"n-{today.replace('-', '')}-{secrets.token_hex(3)}"


def load(folder: Path) -> tuple[list[dict], list[dict]]:
    """The notes in FOLDER, each with its repo-relative file and version, and the files
    that could not be read. A missing folder holds no notes."""
    notes, unreadable = [], []
    if not folder.is_dir():
        return notes, unreadable
    for path in sorted(folder.glob("*.md")):
        rel = path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else f"{folder.name}/{path.name}"
        try:
            text = path.read_text(encoding="utf-8")
            note = parse(text)
            if note["id"] != path.stem:
                raise NoteError("the id does not match the file name")
            # A hand edit can parse yet hold the wrong kinds of value ("updated: 20261101",
            # "links: paper:abc"); such a note is listed as unreadable, never loaded.
            problems = validate(note)
            if problems:
                raise NoteError("; ".join(problems))
        except (NoteError, OSError, UnicodeDecodeError) as exc:
            unreadable.append({"file": rel, "error": str(exc)})
            continue
        note["file"] = rel
        note["version"] = version(text)
        notes.append(note)
    return notes, unreadable


def load_prompts(folder: Path) -> list[dict]:
    """The researcher's own guide prompts (notes/guide.json); [] if there are none."""
    try:
        data = json.loads((folder / "guide.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(data, list):
        return []
    return [{"name": p["name"], "question": p.get("question", "")} for p in data
            if isinstance(p, dict) and isinstance(p.get("name"), str) and isinstance(p.get("question", ""), str)]


# ---------- annotations: marks drawn on saved views ----------
ANNOTATIONS = "annotations.json"
MAX_VIEWS, MAX_MARKS, MAX_POINTS, MAX_VIEW_NAME, MAX_LABEL = 200, 500, 2000, 80, 60
MAX_ANNOT_BYTES = 4 * 1024 * 1024
VIEW_ID_RE = re.compile(r"^v-[0-9]{8}-[0-9a-f]{6}\Z")
MARK_ID_RE = re.compile(r"^m-[0-9a-f]{6}\Z")
MARK_KINDS = ("pen", "rect", "ellipse", "arrow", "text")
CAMERA_KEYS = ("yaw", "pitch", "zoom", "panX", "panY")
POINTS_PER_KIND = {"rect": (2, 2), "ellipse": (2, 2), "arrow": (2, 2), "text": (1, 1), "pen": (2, MAX_POINTS)}


def _number(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _small_int(v, top) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= top


def _mark_problems(mark, where) -> list[str]:
    if not isinstance(mark, dict):
        return [f"{where} is not a mark"]
    out, kind = [], mark.get("kind")
    if not isinstance(mark.get("id"), str) or not MARK_ID_RE.match(mark["id"]):
        out.append(f"{where} has no valid id")
    if kind not in MARK_KINDS:
        return out + [f"{where} is not a pen, rectangle, ellipse, arrow or label"]
    if not _small_int(mark.get("colour"), 4) or not _small_int(mark.get("width"), 2):
        out.append(f"{where} has a colour or width out of range")
    pts, (lo, hi) = mark.get("pts"), POINTS_PER_KIND[kind]
    if not isinstance(pts, list) or not lo <= len(pts) <= hi:
        out.append(f"{where} has the wrong number of points")
    elif any(not isinstance(p, list) or len(p) != 2 or not all(_number(c) and abs(c) <= 50 for c in p) for p in pts):
        out.append(f"{where} has a point that is not two numbers within 50")
    text = mark.get("text")
    if kind == "text":
        if not isinstance(text, str) or not 1 <= len(text) <= MAX_LABEL:
            out.append(f"{where} needs a label of 1 to {MAX_LABEL} characters")
    elif "text" in mark:
        out.append(f"{where} has a label but is not one")
    snap = mark.get("snap")
    if snap is not None and (kind != "arrow" or not isinstance(snap, str) or len(snap) > 300):
        out.append(f"{where} snaps to something but is not an arrow")
    return out


def validate_annotations(doc) -> list[str]:
    """What is wrong with an annotations document, in plain words; [] when it can be saved."""
    if not isinstance(doc, dict) or not isinstance(doc.get("views"), list):
        return ["the annotations are not a list of views"]
    views, out, seen = doc["views"], [], set()
    if len(views) > MAX_VIEWS:
        out.append(f"more than {MAX_VIEWS} saved views")
    for i, view in enumerate(views[:MAX_VIEWS + 1]):
        where = f"view {i + 1}"
        if not isinstance(view, dict):
            out.append(f"{where} is not a view")
            continue
        vid = view.get("id")
        if not isinstance(vid, str) or not VIEW_ID_RE.match(vid):
            out.append(f"{where} has no valid id")
        elif vid in seen:
            out.append(f"{where} repeats the id {vid}")
        seen.add(vid)
        name = view.get("name")
        if not isinstance(name, str) or not name.strip() or len(name) > MAX_VIEW_NAME:
            out.append(f"{where} needs a name of 1 to {MAX_VIEW_NAME} characters")
        cam = view.get("camera")
        if not isinstance(cam, dict) or not all(_number(cam.get(k)) for k in CAMERA_KEYS) or not 1 <= cam["zoom"] <= 14:
            out.append(f"{where} has no valid camera")
        filters = view.get("filters")
        if not isinstance(filters, dict) or len(json.dumps(filters)) > 20_000:
            out.append(f"{where} has no valid filters")
        for key in ("created", "updated"):
            if not _is_iso(view.get(key)):
                out.append(f"{where}: {key} is not a date and time")
        marks = view.get("marks")
        if not isinstance(marks, list) or len(marks) > MAX_MARKS:
            out.append(f"{where} must hold a list of at most {MAX_MARKS} marks")
            continue
        mark_ids = set()
        for k, mark in enumerate(marks):
            out += _mark_problems(mark, f"{where}, mark {k + 1}")
            mid = mark.get("id") if isinstance(mark, dict) else None
            if mid in mark_ids:
                out.append(f"{where}, mark {k + 1} repeats the id {mid}")
            mark_ids.add(mid)
    return out


def load_annotations(folder: Path) -> tuple[dict, str | None, str | None]:
    """notes/annotations.json as (document, version, error). A missing file holds no views;
    a file that cannot be used gives no views, its version (so it is never overwritten
    unseen) and why, in plain words."""
    path = Path(folder) / ANNOTATIONS
    empty = {"views": []}
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return empty, None, None
    except OSError as exc:
        return empty, None, f"notes/{ANNOTATIONS} could not be read: {exc.strerror or exc}"
    ver = hashlib.sha256(raw).hexdigest()[:16]
    try:
        doc = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return empty, ver, f"notes/{ANNOTATIONS} could not be read: {exc}"
    problems = validate_annotations(doc)
    if problems:
        return empty, ver, f"notes/{ANNOTATIONS} is not valid: " + "; ".join(problems[:3])
    return doc, ver, None
