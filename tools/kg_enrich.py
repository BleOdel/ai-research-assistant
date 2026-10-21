#!/usr/bin/env python3
"""OpenAlex authorship and reference data for the library knowledge graph.

Run from anywhere:  python3 tools/kg_enrich.py [--limit N] [--json]

The knowledge graph groups papers into research labs by who wrote them - the
senior (last) author and shared institutions - and links papers that cite each
other. State records neither: `authors` is a list of display names, which is
not enough to tell two "Y. Wang"s apart. OpenAlex has author ids, positions,
institutions and each work's referenced_works, so this fetches them once per
paper through the openalex-search connector's `detail` command (free of the
search allowance) and keeps them in research/graph_cache.json.

A fetched record is used only when its title matches the library's: OpenAlex
resolves some arXiv DOIs to a different work, whose authors and references would
put the paper in the wrong lab. A mismatch is recorded like "not found".

Only papers missing from the cache are fetched, plus papers OpenAlex did not
know 30 or more days ago. A rate limit or any other connector failure (network
down, bun missing, a hung call) stops the run with everything fetched so far
saved and records nothing against the paper; the next run carries on. A paper with no DOI, arXiv id or OpenAlex id (one known
only by a Semantic Scholar URL) is skipped and falls back to name matching.

Reads research/seen_sources.json; never writes state. Stdlib only.
"""

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import date
from pathlib import Path
from typing import Callable

import state

ROOT = state.ROOT
CACHE = ROOT / "research" / "graph_cache.json"
CONNECTOR = ROOT / ".agents" / "skills" / "openalex-search" / "cli" / "src" / "cli.ts"
RETRY_AFTER_DAYS = 30
PACE_SECONDS = 0.2
TIMEOUT_SECONDS = 60
OPENALEX_WORK = re.compile(r"(?:openalex:|openalex\.org/)(W\d+)", re.I)


class RateLimited(Exception):
    """OpenAlex refused for rate: stop, keep what was fetched."""


class FetchFailed(Exception):
    """Any other connector failure. Transient as far as we can tell: stop the run,
    record nothing, retry next time."""


def openalex_lookup_id(state_key: str, entry: dict) -> str | None:
    """What to pass the connector's `detail` for this entry: an OpenAlex work id,
    else a publisher DOI, else the arXiv DOI. None if there is no such id."""
    values = (state_key, entry.get("url"), entry.get("doi"))
    for value in values:
        m = OPENALEX_WORK.search(value) if isinstance(value, str) else None
        if m:
            return m.group(1)
    ids = state.identifiers(*values)
    dois = sorted(i[4:] for i in ids if i.startswith("doi:"))
    publisher = [d for d in dois if not d.startswith("10.48550/")]
    if publisher:
        return publisher[0]
    arxiv = sorted(i[6:] for i in ids if i.startswith("arxiv:"))
    if arxiv:
        return f"10.48550/arXiv.{arxiv[0]}"
    if dois:
        return dois[0]
    return None


def connector_fetch(lookup_id: str) -> dict | None:
    """The connector's parsed work, or None if OpenAlex has no such work."""
    time.sleep(PACE_SECONDS)
    try:
        proc = subprocess.run(["bun", "run", str(CONNECTOR), "detail", lookup_id, "--format", "json"],
                              capture_output=True, text=True, cwd=ROOT, timeout=TIMEOUT_SECONDS)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise FetchFailed(f"connector could not run: {exc}") from exc
    if proc.returncode == 0:
        try:
            return json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise FetchFailed(f"connector printed invalid JSON: {exc}") from exc
    try:
        err = json.loads(proc.stderr.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        err = {"error": proc.stderr.strip()[:200], "code": "UNKNOWN"}
    if err.get("code") == "RATE_LIMITED":
        raise RateLimited(err.get("error", ""))
    if err.get("code") == "NOT_FOUND" or "404" in str(err.get("error", "")):
        return None
    raise FetchFailed(f"{err.get('code')}: {err.get('error')}")


def load_cache(cache: Path = CACHE) -> dict:
    if not cache.exists():
        return {"works": {}}
    return json.loads(cache.read_text(encoding="utf-8"))


def _record(work: dict | None, today: str, error: str | None = None) -> dict:
    if work is None or error:
        return {"openalex": None, "authors": [], "referenced": [], "fetched": today,
                "error": error or "not found"}
    return {
        "openalex": work.get("id"),
        "authors": [{"name": a.get("name"), "authorId": a.get("authorId"),
                     "position": a.get("position"), "institutions": a.get("institutions") or []}
                    for a in work.get("authors") or []],
        "referenced": list(work.get("referencedWorks") or []),
        "title": work.get("title"),
        "fetched": today,
        "error": None,
    }


def _due(record: dict | None, today: str) -> bool:
    if record is None:
        return True
    if not record.get("error"):
        return False
    try:
        age = (date.fromisoformat(today) - date.fromisoformat(record["fetched"])).days
    except (KeyError, TypeError, ValueError):
        return True
    return age >= RETRY_AFTER_DAYS


def enrich(entries: dict, fetch: Callable[[str], dict | None], today: str,
           limit: int | None = None, cache: Path = CACHE) -> dict:
    """Fetch authorship data for every non-skipped entry not yet cached. The cache
    is rewritten after each fetch, so an interrupted run loses nothing."""
    data = load_cache(cache)
    works = data.setdefault("works", {})
    counts = {"fetched": 0, "skipped_no_id": 0, "errors": 0, "cached": 0, "stopped": None}
    calls = 0
    for key in sorted(entries):
        entry = entries[key]
        if entry.get("status") == "skipped":
            continue
        if not _due(works.get(key), today):
            counts["cached"] += 1
            continue
        lookup = openalex_lookup_id(key, entry)
        if lookup is None:
            counts["skipped_no_id"] += 1
            continue
        if limit is not None and calls >= limit:
            counts["stopped"] = "limit"
            break
        calls += 1
        try:
            work = fetch(lookup)
        except RateLimited:
            counts["stopped"] = "rate-limited"
            break
        except FetchFailed as exc:
            counts["stopped"] = "connector-failed"
            counts["failure"] = str(exc)
            break
        else:
            mismatch = None
            if work is not None and entry.get("title") and \
                    not state.title_matches(entry["title"], work.get("title") or ""):
                mismatch = f"title mismatch: OpenAlex returned {str(work.get('title'))[:120]!r}"
            works[key] = _record(work, today, error=mismatch)
            counts["errors" if work is None or mismatch else "fetched"] += 1
        state.atomic_write(cache, json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    return counts


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--limit", type=int, help="fetch at most N papers this run")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    entries = state.load("sources", state.FILES["sources"])
    counts = enrich(entries, connector_fetch, date.today().isoformat(), limit=args.limit)
    if args.json:
        print(json.dumps(counts))
    else:
        print(f"OpenAlex enrichment: {counts['fetched']} fetched, {counts['cached']} already "
              f"cached, {counts['errors']} not found or failed, {counts['skipped_no_id']} with "
              "no DOI/arXiv/OpenAlex id (matched by name instead)")
        if counts["stopped"] == "rate-limited":
            print("Stopped: OpenAlex rate limit. Progress is saved; run again later.")
        elif counts["stopped"] == "connector-failed":
            print(f"Stopped: {counts['failure']}. Progress is saved; run again later.")
        elif counts["stopped"] == "limit":
            print("Stopped at --limit. Run again to continue.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
