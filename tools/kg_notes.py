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

Read by tools/knowledge_graph.py (to embed the notes in the page) and written only by
tools/kg_serve.py, the local helper. Stdlib only.
"""

import hashlib
import json
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
