#!/usr/bin/env python3
"""The single write path for this framework's discovery state.

Run from anywhere:  python3 tools/state.py <command> ...

Why this exists: every command used to write research/seen_sources.json with
Python improvised inline, per run. That is how one verdict tier came to be
stored under two spellings ("Core" and "Core Source"), how a stored
overall_score drifted away from its own sub-scores after one sub-score was
revised by hand, and why two Claude Code sessions writing at the same moment
could silently drop each other's changes. Routing every write through here
makes it validated, atomic, and locked.

Files - pass the short name or a path:
  sources   research/seen_sources.json     academic track
  web       blog/seen_web_sources.json     web track
  tracker   research_tracker.csv           report outcomes (/outcome)

Commands:
  check [FILE ...] [--fix-derived] [--verbose] [--json]
      Validate. Errors are bad values (wrong enum spelling, out-of-range score,
      overall_score that disagrees with its sub-scores). Gaps are fields an
      older entry never recorded - reported, never fatal. --fix-derived
      recomputes overall_score and verdict/tier from sub-scores and touches
      nothing else. Exit 1 if errors remain.
  upsert --file F --key K (--json '{...}' | --json-file PATH)
      Create or merge one entry. Fields are added or overwritten, never
      removed; `scores` merges key by key.
  batch --file F (--json '{...}' | --json-file PATH)
      Merge many entries, {key: {fields}}, in one locked all-or-nothing write.
  set-status --file F --status S KEY [KEY ...]
  score [--web] --relevance N --rigor N --impact N --recency N
      Print the overall score and verdict for a set of sub-scores, so nobody
      does the weighted sum by hand. Web: --authority/--evidence, no impact.
  regen-index
      Rebuild research/papers_by_subject.md per 05-subject-index.md. Every
      write to `sources` does this automatically.
  unmerged --subject S --bib PATH [--json]
      List `sources` entries for subject S with status "ranked" and verdict
      Core or Supporting that PATH (a report's references.bib) does not cite.
      Read-only. /research's dedup treats every seen source as not new, so a
      source scored for a report but never carried into it is otherwise never
      offered again - /update and /synthesize run this to catch that. Entries
      match on DOI, arXiv id or URL however each side spells it: a state key
      https://doi.org/10.48550/arXiv.2406.13352 matches eprint = {2406.13352}.

Validation applies to every entry a write touches - the merged result, not
just the patch. overall_score and verdict/tier are always recomputed from
sub-scores, so they cannot drift; a patch supplying a value that disagrees
with the computed one is rejected, because it means the caller's arithmetic
is wrong. Missing optional fields on old entries never block a write.

The rubric constants below mirror 02-source-evaluation.md and
09-web-source-evaluation.md; tests/test_state.py parses those files and fails
if the two ever disagree.

Stdlib only. Errors go to stderr as JSON {"error", "code"} - the same shape as
the connector CLIs - and exit 1.
"""

import argparse
import csv
import io
import json
import os
import re
import sys
import tempfile
import time
from datetime import date
from pathlib import Path

from check_report import parse_bib  # one .bib parser for all of tools/

ROOT = Path(__file__).resolve().parent.parent
PROFILE = ROOT / ".claude" / "skills" / "research-assistant" / "01-researcher-profile.md"
INDEX = ROOT / "research" / "papers_by_subject.md"

FILES = {
    "sources": ROOT / "research" / "seen_sources.json",
    "web": ROOT / "blog" / "seen_web_sources.json",
    "tracker": ROOT / "research_tracker.csv",
}

# --- Academic rubric (02-source-evaluation.md) -------------------------------
VERDICTS = ("Core", "Supporting", "Peripheral", "Excluded")
THRESHOLDS = ((75, "Core"), (55, "Supporting"), (35, "Peripheral"))
WEIGHTS = {"relevance": 0.40, "rigor": 0.25, "impact": 0.20, "recency": 0.15}
RENORMALIZED = {"relevance": 0.50, "rigor": 0.3125, "recency": 0.1875}
INSUFFICIENT = "insufficient data"
STATUSES = ("new", "skipped", "ranked", "unfetchable", "synthesized")
TRIAGE = ("high", "medium", "low", "unknown")
EVIDENCE = ("fulltext", "abstract")
DISCLOSURE = ("academic", "industry", "self-evaluating", "vendor-report", "unclear")
CONNECTORS = (
    "arxiv-search", "semantic-scholar-search", "google-scholar-search",
    "openalex-search", "websearch",
)

# --- Web rubric (09-web-source-evaluation.md) --------------------------------
WEB_WEIGHTS = {"relevance": 0.30, "authority": 0.25, "evidence": 0.25, "recency": 0.20}
WEB_THRESHOLDS = ((70, "Core"), (50, "Supporting"), (30, "Peripheral"))
WEB_STATUSES = ("included", "excluded", "unfetchable")
WEB_INDEPENDENCE = ("independent", "first-party", "vendor-competitive", "sponsored", "unclear")
WEB_TYPES = (
    "engineering-blog", "official-docs", "standard-or-spec", "research-adjacent",
    "talk-writeup", "news", "forum-thread", "tutorial", "opinion", "marketing",
)

# --- Outcome tracker (outcome.md) --------------------------------------------
TRACKER_COLUMNS = ("topic", "subject", "date_synthesized", "status", "last_event_date", "notes")
TRACKER_STATUSES = ("active", "presented", "cited", "needs_revision", "superseded")

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# --- Source identifiers (unmerged) -------------------------------------------
_ARXIV_ID = r"(\d{4}\.\d{4,5}|[a-z][a-z.-]*/\d{7})(?:v\d+)?"
ARXIV_BARE = re.compile(rf"^{_ARXIV_ID}$", re.I)
ARXIV_IN_TEXT = re.compile(rf"arxiv(?:\.org/(?:abs|pdf|html)/|[:.]\s?){_ARXIV_ID}", re.I)
DOI_IN_TEXT = re.compile(r"\b(10\.\d{4,9}/[^\s\"<>{}]+)")
URL_RE = re.compile(r"^https?://(?:www\.)?([^/?#\s]+)([^?#\s]*)", re.I)
# Only fields that identify the entry itself - evidencebasis and note mention
# other papers' ids, and matching on those would hide a source that is missing.
BIB_ID_FIELDS = ("doi", "eprint", "url", "howpublished")


class StateError(Exception):
    def __init__(self, message: str, code: str, problems: list[str] | None = None):
        super().__init__(message)
        self.code = code
        self.problems = problems or []


# ---------------------------------------------------------------------------
# Locking and atomic writes
# ---------------------------------------------------------------------------

class Lock:
    """Exclusive lock on one state file, held as a sidecar <file>.lock.

    Created with O_CREAT|O_EXCL, so exactly one process can hold it. Portable
    (no fcntl - SETUP.md supports Windows). A lock older than `stale` seconds
    is assumed to belong to a crashed session and is broken. Two waiters
    breaking the same stale lock in the same instant could both proceed; that
    needs a crashed session plus two concurrent writers, which a single-user
    research workspace does not realistically produce.
    """

    def __init__(self, target: Path, timeout: float | None = None, stale: float = 120.0):
        self.path = target.with_name(target.name + ".lock")
        # STATE_LOCK_TIMEOUT exists so tests can exercise the LOCKED path quickly.
        self.timeout = timeout if timeout is not None else float(
            os.environ.get("STATE_LOCK_TIMEOUT", "30"))
        self.stale = stale

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)  # first write in a fresh repo
        deadline = time.monotonic() + self.timeout
        while True:
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
            except FileExistsError:
                try:
                    age = time.time() - self.path.stat().st_mtime
                except FileNotFoundError:
                    continue
                if age > self.stale:
                    print(f"state: breaking stale lock {self.path.name} ({age:.0f}s old)",
                          file=sys.stderr)
                    self.path.unlink(missing_ok=True)
                    continue
                if time.monotonic() > deadline:
                    raise StateError(
                        f"{self.path.name} is held by another session - retry once it "
                        "finishes, or delete the .lock file if no session is running",
                        "LOCKED",
                    )
                time.sleep(0.1)
                continue
            with os.fdopen(fd, "w") as f:
                f.write(f"{os.getpid()} {time.time():.0f}\n")
            return self

    def __exit__(self, *exc):
        self.path.unlink(missing_ok=True)


def atomic_write(target: Path, text: str) -> None:
    """Write via a temp file in the same directory, then rename over target.

    A reader sees either the old file or the new one, never a half-written
    one - including a second session reading mid-write.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        mode = target.stat().st_mode & 0o777 if target.exists() else 0o644
        os.chmod(tmp, mode)
        os.replace(tmp, target)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


# ---------------------------------------------------------------------------
# Loading and saving each file kind
# ---------------------------------------------------------------------------

def resolve_file(name: str) -> tuple[str, Path]:
    if name in FILES:
        return name, FILES[name]
    path = Path(name).resolve()
    for kind, known in FILES.items():
        if path == known.resolve():
            return kind, known
    raise StateError(
        f"unknown state file {name!r} - use one of: {', '.join(FILES)}", "BAD_ARG"
    )


def load(kind: str, path: Path) -> dict:
    """Return {key: entry} for any file kind."""
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    if kind == "tracker":
        rows = list(csv.DictReader(io.StringIO(text)))
        return {row["topic"]: dict(row) for row in rows if row.get("topic")}
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise StateError(f"{path.name} is not valid JSON: {exc}", "PARSE_ERROR") from exc
    if not isinstance(data, dict) or not isinstance(data.get("seen"), dict):
        raise StateError(f'{path.name} must be {{"seen": {{...}}}}', "PARSE_ERROR")
    return data["seen"]


def serialize(kind: str, entries: dict) -> str:
    if kind == "tracker":
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=TRACKER_COLUMNS, lineterminator="\n")
        writer.writeheader()
        for row in entries.values():
            writer.writerow({col: row.get(col, "") for col in TRACKER_COLUMNS})
        return buf.getvalue()
    return json.dumps({"seen": entries}, indent=2, ensure_ascii=False) + "\n"


# ---------------------------------------------------------------------------
# Rubric arithmetic
# ---------------------------------------------------------------------------

def _round(x: float) -> int:
    return int(x + 0.5 + 1e-9)  # half-up; Python's round() is banker's


def compute(scores: dict, web: bool = False) -> tuple[int, str] | None:
    """Overall score and verdict/tier from sub-scores, or None if incomplete."""
    weights = WEB_WEIGHTS if web else WEIGHTS
    if not isinstance(scores, dict) or not set(weights) <= set(scores):
        return None
    if not web and scores.get("impact") == INSUFFICIENT:
        weights = RENORMALIZED
    if not all(isinstance(scores[k], (int, float)) for k in weights):
        return None
    overall = _round(sum(scores[k] * w for k, w in weights.items()))
    for floor, label in (WEB_THRESHOLDS if web else THRESHOLDS):
        if overall >= floor:
            return overall, label
    return overall, "Excluded"


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def tracked_interests() -> list[str] | None:
    """Research Interest names from the profile, in order. None if unreadable."""
    if not PROFILE.exists():
        return None
    names, inside = [], False
    for line in PROFILE.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            inside = line.strip() == "## Research Interests"
        elif inside and line.startswith("### "):
            name = line[4:].strip()
            if name and "[" not in name:  # skip /setup's [PLACEHOLDER] headings
                names.append(name)
    return names or None


def _enum(entry, field, allowed, problems, required=False):
    if field not in entry or entry[field] is None:
        if required:
            problems.append(f"missing required field {field!r}")
        return
    if entry[field] not in allowed:
        problems.append(f"{field}={entry[field]!r} is not one of {', '.join(allowed)}")


def _date(entry, field, problems, required=False):
    value = entry.get(field)
    if value in (None, ""):
        if required:
            problems.append(f"missing required field {field!r}")
        return
    if not isinstance(value, str) or not DATE_RE.match(value):
        problems.append(f"{field}={value!r} is not a YYYY-MM-DD date")


def _scores(entry, dims, problems, allow_insufficient):
    scores = entry.get("scores")
    if scores is None:
        return
    if not isinstance(scores, dict):
        problems.append("scores must be an object")
        return
    for key, value in scores.items():
        if key not in dims:
            problems.append(f"unknown score dimension {key!r}")
        elif allow_insufficient and key == "impact" and value == INSUFFICIENT:
            continue
        elif not isinstance(value, (int, float)) or isinstance(value, bool) \
                or not 0 <= value <= 100:
            problems.append(f"scores.{key}={value!r} must be a number 0-100"
                            + (f' or "{INSUFFICIENT}"' if allow_insufficient and key == "impact" else ""))


def validate(kind: str, entry: dict, interests: list[str] | None) -> list[str]:
    """Bad values in one entry. Missing optional fields are not problems."""
    problems: list[str] = []
    if not isinstance(entry, dict):
        return ["entry must be an object"]

    if kind == "tracker":
        unknown = set(entry) - set(TRACKER_COLUMNS)
        if unknown:
            problems.append(f"unknown tracker column(s): {', '.join(sorted(unknown))}")
        _enum(entry, "status", TRACKER_STATUSES, problems, required=True)
        _date(entry, "date_synthesized", problems)
        _date(entry, "last_event_date", problems)
        return problems

    if not isinstance(entry.get("title"), str) or not entry["title"].strip():
        problems.append("missing required field 'title'")
    _date(entry, "first_seen", problems, required=True)

    if kind == "web":
        _enum(entry, "status", WEB_STATUSES, problems, required=True)
        _enum(entry, "tier", VERDICTS, problems)
        _enum(entry, "independence", WEB_INDEPENDENCE, problems)
        _enum(entry, "type", WEB_TYPES, problems)
        _date(entry, "date", problems)
        _scores(entry, WEB_WEIGHTS, problems, allow_insufficient=False)
        return problems

    _enum(entry, "status", STATUSES, problems, required=True)
    _enum(entry, "verdict", VERDICTS, problems)
    _enum(entry, "relevance", TRIAGE, problems)
    _enum(entry, "evidence_basis", EVIDENCE, problems)
    _enum(entry, "disclosure", DISCLOSURE, problems)
    _date(entry, "rank_date", problems)
    _scores(entry, WEIGHTS, problems, allow_insufficient=True)

    subject = entry.get("subject")
    if not isinstance(subject, str) or not subject:
        problems.append("missing required field 'subject'")
    elif interests is not None and subject not in interests and subject != "Uncategorized":
        problems.append(
            f"subject={subject!r} is neither a tracked Research Interest nor "
            "'Uncategorized' (see 05-subject-index.md)"
        )

    authors = entry.get("authors")
    if authors is not None and not (isinstance(authors, list)
                                    and all(isinstance(a, str) for a in authors)):
        problems.append("authors must be a list of strings")
    return problems


def derived_mismatch(kind: str, entry: dict) -> str | None:
    """Describe a stored overall/verdict that disagrees with its sub-scores."""
    if kind == "tracker":
        return None
    web = kind == "web"
    label_field = "tier" if web else "verdict"
    result = compute(entry.get("scores"), web=web)
    if result is None:
        if entry.get("overall_score") is not None and entry.get("scores") is not None:
            return "has an overall_score but incomplete sub-scores"
        return None
    overall, label = result
    stored = entry.get("overall_score")
    parts = []
    if not isinstance(stored, (int, float)) or abs(stored - overall) > 1:
        parts.append(f"overall_score {stored!r} but sub-scores compute to {overall}")
    if entry.get(label_field) not in (None, label):
        parts.append(f"{label_field} {entry.get(label_field)!r} but {overall} is {label}")
    return "; ".join(parts) or None


def settle(kind: str, merged: dict, patch: dict) -> tuple[list[str], list[str]]:
    """Recompute derived fields on a touched entry. Returns (problems, notes)."""
    if kind == "tracker":
        return [], []
    web = kind == "web"
    label_field = "tier" if web else "verdict"
    result = compute(merged.get("scores"), web=web)
    problems, notes = [], []
    if result is None:
        if merged.get("scores") is not None and (
                "overall_score" in patch or label_field in patch):
            problems.append(f"overall_score/{label_field} supplied but sub-scores are "
                            "incomplete - supply all four dimensions")
        return problems, notes
    overall, label = result
    if "overall_score" in patch and isinstance(patch["overall_score"], (int, float)) \
            and abs(patch["overall_score"] - overall) > 1:
        problems.append(f"overall_score {patch['overall_score']} disagrees with the "
                        f"sub-scores, which compute to {overall} - omit it and let "
                        "state.py compute it")
    if label_field in patch and patch[label_field] != label:
        problems.append(f"{label_field} {patch[label_field]!r} disagrees with overall "
                        f"{overall}, which is {label}")
    previous = merged.get("overall_score")
    if "overall_score" not in patch and isinstance(previous, (int, float)) \
            and abs(previous - overall) > 1:
        notes.append(f"recomputed stale overall_score {previous} -> {overall}")
    merged["overall_score"] = overall
    merged[label_field] = label
    return problems, notes


def merge(existing: dict, patch: dict, kind: str) -> dict:
    out = dict(existing)
    for key, value in patch.items():
        if key == "scores" and isinstance(value, dict) and isinstance(out.get("scores"), dict):
            out["scores"] = {**out["scores"], **value}
        elif key == "notes_append" and kind == "tracker":
            note = str(value).strip()
            current = (out.get("notes") or "").strip()
            out["notes"] = f"{current} {note}".strip() if note else current
        else:
            out[key] = value
    return out


# ---------------------------------------------------------------------------
# Subject index (05-subject-index.md)
# ---------------------------------------------------------------------------

INDEX_HEADER = """# Papers by Subject

<!-- Auto-generated from research/seen_sources.json by /research, /rank, and
     /synthesize. Do not hand-edit - changes will be overwritten. -->
"""
INDEX_TABLE = ("| Title | Authors | Year | Venue | Score / Relevance | Status | Link |\n"
               "|-------|---------|------|-------|--------------------|--------|------|")


def _cell(value) -> str:
    return "" if value is None else str(value).replace("|", "\\|").replace("\n", " ")


def _row(entry: dict) -> str:
    authors = entry.get("authors") or []
    names = ", ".join(authors[:3]) + (" et al." if len(authors) > 3 else "")
    score = entry.get("overall_score")
    if isinstance(score, (int, float)):
        rank = f"{score} - {entry['verdict']}" if entry.get("verdict") else str(score)
    else:
        rank = entry.get("relevance") or ""
    url = entry.get("url")
    link = f"[Link]({url})" if url else ""
    cells = [_cell(entry.get("title")), _cell(names), _cell(entry.get("year")),
             _cell(entry.get("venue")), _cell(rank), _cell(entry.get("status")), link]
    return "| " + " | ".join(cells) + " |"


def render_index(entries: dict, interests: list[str] | None) -> str:
    groups: dict[str, list[dict]] = {}
    for entry in entries.values():
        groups.setdefault(entry.get("subject") or "Uncategorized", []).append(entry)

    order = list(interests or [])
    order += sorted(s for s in groups if s not in order and s != "Uncategorized")
    if groups.get("Uncategorized"):
        order.append("Uncategorized")

    def sort_key(entry):
        score = entry.get("overall_score")
        scored = isinstance(score, (int, float))
        return (0 if scored else 1, -(score if scored else 0),
                _neg_date(entry.get("first_seen")), entry.get("title") or "")

    sections = [INDEX_HEADER]
    for subject in order:
        rows = [_row(e) for e in sorted(groups.get(subject, []), key=sort_key)]
        sections.append(f"## {subject}\n\n{INDEX_TABLE}" + "".join("\n" + r for r in rows) + "\n")
    return "\n".join(sections)


def _neg_date(value) -> int:
    """Sort key putting newer YYYY-MM-DD dates first."""
    try:
        return -date.fromisoformat(value).toordinal()
    except (TypeError, ValueError):
        return 0


def regen_index() -> int:
    entries = load("sources", FILES["sources"])
    atomic_write(INDEX, render_index(entries, tracked_interests()))
    return len(entries)


# ---------------------------------------------------------------------------
# Report coverage
# ---------------------------------------------------------------------------

def identifiers(*values) -> set[str]:
    """Canonical arxiv:<id>, doi:<doi> and url:<host/path> forms in VALUES.

    State keys and .bib fields spell one identifier many ways - bare arXiv
    ids, arxiv.org URLs with or without a version, arXiv DOIs, doi.org URLs -
    so both sides reduce to these forms and match if any one is shared.
    """
    ids = set()
    for value in values:
        if not isinstance(value, str) or not value.strip():
            continue
        value = value.strip()
        bare = ARXIV_BARE.match(value)
        if bare:
            ids.add(f"arxiv:{bare.group(1).lower()}")
        ids.update(f"arxiv:{m.group(1).lower()}" for m in ARXIV_IN_TEXT.finditer(value))
        ids.update(f"doi:{m.group(1).rstrip('.,;)').lower()}"
                   for m in DOI_IN_TEXT.finditer(value))
        url = URL_RE.match(value)
        if url:
            ids.add(f"url:{url.group(1).lower()}{url.group(2).rstrip('/')}")
    return ids


def unmerged(subject: str, bib: Path) -> list[dict]:
    """Ranked Core/Supporting entries for SUBJECT that BIB does not cite."""
    interests = tracked_interests()
    if interests is not None and subject not in interests + ["Uncategorized"]:
        raise StateError(f"subject {subject!r} is not a tracked Research Interest",
                         "BAD_ARG", [f"tracked: {', '.join(interests)}, Uncategorized"])
    if not bib.is_file():
        raise StateError(f"{bib} not found", "NOT_FOUND")
    bib_entries, problems = parse_bib(bib.read_text(encoding="utf-8"))
    if problems:
        raise StateError(f"could not parse {bib.name}", "PARSE_ERROR", problems)
    cited = set()
    for fields in bib_entries.values():
        cited |= identifiers(*(fields.get(f) for f in BIB_ID_FIELDS))

    found = []
    for key, entry in load("sources", FILES["sources"]).items():
        if (entry.get("subject") != subject or entry.get("status") != "ranked"
                or entry.get("verdict") not in ("Core", "Supporting")):
            continue
        if identifiers(key, entry.get("url")) & cited:
            continue
        found.append({"key": key, **{f: entry.get(f) for f in (
            "title", "year", "verdict", "overall_score", "rank_date", "url")}})
    found.sort(key=lambda e: (VERDICTS.index(e["verdict"]), -(e["overall_score"] or 0),
                              e["title"] or ""))
    return found


def print_unmerged(found: list[dict], subject: str, bib: Path) -> None:
    if not found:
        print(f"none - every ranked Core/Supporting source for {subject!r} is in {bib.name}")
        return
    print(f"{len(found)} ranked Core/Supporting source(s) for {subject!r} not in {bib.name}:")
    for e in found:
        year = f" ({e['year']})" if e.get("year") else ""
        print(f"  {e['verdict']:<10} {e['overall_score'] or '':>3}  {e['title']}{year}")
        print(f"             key: {e['key']}")


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def write_entries(kind: str, path: Path, patches: dict) -> dict:
    """Merge {key: patch} into the file under lock; all-or-nothing."""
    if not isinstance(patches, dict) or not patches:
        raise StateError("expected a non-empty JSON object of entries", "BAD_ARG")
    interests = tracked_interests() if kind == "sources" else None
    with Lock(path):
        entries = load(kind, path)
        problems, notes = [], []
        for key, patch in patches.items():
            if not isinstance(patch, dict):
                problems.append(f"{key}: patch must be a JSON object")
                continue
            if kind == "tracker":
                patch = {**patch, "topic": key}
            merged = merge(entries.get(key, {}), patch, kind)
            settle_problems, settle_notes = settle(kind, merged, patch)
            problems += [f"{key}: {p}" for p in validate(kind, merged, interests) + settle_problems]
            notes += [f"{key}: {n}" for n in settle_notes]
            entries[key] = merged
        if problems:
            raise StateError(f"refused - nothing written to {path.name}", "INVALID", problems)
        atomic_write(path, serialize(kind, entries))
    if kind == "sources":
        regen_index()
    return {"ok": True, "file": str(path.relative_to(ROOT)), "written": len(patches),
            "total": len(entries), "notes": notes}


def check(names: list[str], fix_derived: bool) -> dict:
    report = {}
    interests = tracked_interests()
    for name in names:
        kind, path = resolve_file(name)
        if not path.exists():
            continue
        if fix_derived and kind != "tracker":
            with Lock(path):
                entries = load(kind, path)
                fixed = 0
                for entry in entries.values():
                    if derived_mismatch(kind, entry):
                        settle(kind, entry, {})
                        fixed += 1
                if fixed:
                    atomic_write(path, serialize(kind, entries))
            if fixed and kind == "sources":
                regen_index()
        entries = load(kind, path)
        errors, gaps, warnings = [], {}, []
        for key, entry in entries.items():
            for problem in validate(kind, entry, interests if kind == "sources" else None):
                errors.append(f"{key}: {problem}")
            mismatch = derived_mismatch(kind, entry)
            if mismatch:
                errors.append(f"{key}: {mismatch}")
            if kind == "sources":
                _gaps(key, entry, gaps, warnings)
        report[str(path.relative_to(ROOT))] = {
            "entries": len(entries), "errors": errors, "gaps": gaps, "warnings": warnings,
        }
    return report


def _gaps(key, entry, gaps, warnings):
    def gap(label):
        gaps.setdefault(label, []).append(key)

    if entry.get("status") in ("ranked", "synthesized"):
        for field in ("scores", "evidence_basis", "disclosure", "rigor_basis"):
            if entry.get(field) in (None, ""):
                gap(f"scored entry missing {field}")
    if entry.get("status") == "synthesized" and not entry.get("authors"):
        gap("synthesized entry with no authors")
    if not entry.get("url") and entry.get("status") != "unfetchable":
        gap("no url")
    connector = entry.get("source_connector")
    if connector and connector not in CONNECTORS:
        warnings.append(f"{key}: non-standard source_connector {connector[:60]!r}")


def print_check(report: dict, verbose: bool) -> None:
    for name, result in report.items():
        print(f"{name} - {result['entries']} entries")
        if result["errors"]:
            print(f"  errors ({len(result['errors'])}):")
            for line in result["errors"]:
                print(f"    {line}")
        else:
            print("  errors: none")
        for label, keys in sorted(result["gaps"].items()):
            print(f"  gap: {label}: {len(keys)}")
            if verbose:
                for key in keys:
                    print(f"      {key}")
        if result["warnings"]:
            print(f"  warnings ({len(result['warnings'])}):")
            for line in result["warnings"] if verbose else result["warnings"][:5]:
                print(f"    {line}")
            if not verbose and len(result["warnings"]) > 5:
                print("    ... (--verbose for all)")


def read_json_arg(args) -> object:
    if args.json is not None:
        raw = args.json
    elif args.json_file == "-":
        raw = sys.stdin.read()
    elif args.json_file:
        raw = Path(args.json_file).read_text(encoding="utf-8")
    else:
        raise StateError("pass --json or --json-file", "BAD_ARG")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise StateError(f"invalid JSON input: {exc}", "BAD_ARG") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)

    p_check = sub.add_parser("check")
    p_check.add_argument("files", nargs="*", default=list(FILES))
    p_check.add_argument("--fix-derived", action="store_true")
    p_check.add_argument("--verbose", action="store_true")
    p_check.add_argument("--json", action="store_true")

    for name in ("upsert", "batch"):
        p = sub.add_parser(name)
        p.add_argument("--file", required=True)
        if name == "upsert":
            p.add_argument("--key", required=True)
        p.add_argument("--json")
        p.add_argument("--json-file")

    p_status = sub.add_parser("set-status")
    p_status.add_argument("--file", required=True)
    p_status.add_argument("--status", required=True)
    p_status.add_argument("keys", nargs="+")

    p_score = sub.add_parser("score")
    p_score.add_argument("--web", action="store_true")
    for dim in ("relevance", "rigor", "impact", "recency", "authority", "evidence"):
        p_score.add_argument(f"--{dim}")

    sub.add_parser("regen-index")

    p_unmerged = sub.add_parser("unmerged")
    p_unmerged.add_argument("--subject", required=True)
    p_unmerged.add_argument("--bib", required=True)
    p_unmerged.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "check":
            report = check(args.files, args.fix_derived)
            if args.json:
                print(json.dumps(report, indent=2))
            else:
                print_check(report, args.verbose)
            return 1 if any(r["errors"] for r in report.values()) else 0

        if args.command in ("upsert", "batch"):
            kind, path = resolve_file(args.file)
            data = read_json_arg(args)
            patches = {args.key: data} if args.command == "upsert" else data
            print(json.dumps(write_entries(kind, path, patches)))
            return 0

        if args.command == "set-status":
            kind, path = resolve_file(args.file)
            entries = load(kind, path)
            missing = [k for k in args.keys if k not in entries]
            if missing:
                raise StateError("no such entries", "NOT_FOUND", missing)
            print(json.dumps(write_entries(kind, path, {k: {"status": args.status}
                                                        for k in args.keys})))
            return 0

        if args.command == "score":
            dims = WEB_WEIGHTS if args.web else WEIGHTS
            scores = {}
            for dim in dims:
                raw = getattr(args, dim)
                if raw is None:
                    raise StateError(f"--{dim} is required", "BAD_ARG")
                if not args.web and dim == "impact" and raw.strip().lower() in (
                        INSUFFICIENT, "insufficient", "n/a"):
                    scores[dim] = INSUFFICIENT
                    continue
                try:
                    scores[dim] = float(raw)
                except ValueError as exc:
                    raise StateError(f"--{dim} must be a number", "BAD_ARG") from exc
            problems = []
            _scores({"scores": scores}, dims, problems, allow_insufficient=not args.web)
            if problems:
                raise StateError("invalid scores", "INVALID", problems)
            overall, label = compute(scores, web=args.web)
            print(json.dumps({"overall_score": overall,
                              ("tier" if args.web else "verdict"): label}))
            return 0

        if args.command == "regen-index":
            print(json.dumps({"ok": True, "file": str(INDEX.relative_to(ROOT)),
                              "entries": regen_index()}))
            return 0

        if args.command == "unmerged":
            bib = Path(args.bib)
            found = unmerged(args.subject, bib)
            if args.json:
                print(json.dumps({"subject": args.subject, "bib": str(bib),
                                  "unmerged": found}, indent=2))
            else:
                print_unmerged(found, args.subject, bib)
            return 0
    except StateError as exc:
        out = {"error": str(exc), "code": exc.code}
        if exc.problems:
            out["problems"] = exc.problems
        print(json.dumps(out), file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
