#!/usr/bin/env python3
"""Lint a /websearch page: blog/<topic_slug>/index.html and its sources.json.

    python3 tools/check_webscan.py blog/<topic_slug> [--json]

The web track's counterpart to check_report.py. /websearch fills blog/template.html
by replacing five tokens, and until this existed its verification list
(10-html-reports.md) was done by hand. That is how a template comment that copied
every report into itself, and a scope note claiming sources "recorded as
unfetchable" that the state file never held, both went unnoticed for weeks.

Errors (exit 1):
- a [TOKEN] placeholder left anywhere in the page
- no single <script id="data"> block, or one that does not parse as a JSON array
- a literal "<" in that block: titles and summaries are fetched, untrusted text,
  and "</script>" would end the block and run what follows (write "<" as \\u003c)
- a source missing a schema field, with a type, independence label, tier or date
  outside 10-html-reports.md's schema, or a url that is not http(s)
- a score or tier that disagrees with its own sub-scores (state.py's web rubric)
- a vendor-competitive, sponsored, unclear or Peripheral source with no caveat
- sources.json missing, or parsing to different data than the page
- a source not in blog/seen_web_sources.json as "included", or recorded there
  with different scores, tier or independence
- an empty scope note or synthesis
- a script, stylesheet, image or frame loaded from outside the page

Warnings: the header comment differs from the current template (pages built before
2026-10-06 carry a second copy of the report there), or the synthesis uses tags
outside the documented set (p, h3, ul, li, strong, em, a, code).

The linter does not read prose: whether the synthesis attributes contested claims
and checks that corroboration is independent is still the drafter's job.
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_report import Findings  # noqa: E402
from state import (ROOT, WEB_INDEPENDENCE, WEB_THRESHOLDS, WEB_TYPES,  # noqa: E402
                   compute)

TEMPLATE = ROOT / "blog" / "template.html"
STATE = ROOT / "blog" / "seen_web_sources.json"
TOKENS = ("[TOPIC]", "[RUN_DATE]", "[SCOPE_NOTE]", "[SYNTHESIS]", "[SOURCES_JSON]")
FIELDS = ("title", "url", "author", "site", "date", "type", "tier", "score", "scores",
          "independence", "summary", "keyPoints", "caveat")
TIERS = tuple(label for _, label in WEB_THRESHOLDS)
NEEDS_CAVEAT = ("vendor-competitive", "sponsored", "unclear")
SYNTHESIS_TAGS = {"p", "h3", "ul", "li", "strong", "em", "a", "code"}
DATA_BLOCK = re.compile(r'<script id="data" type="application/json">(.*?)</script>', re.S)
COMMENT = re.compile(r"^\s*<!DOCTYPE[^>]*>\s*<!--(.*?)-->", re.S | re.I)


def locate(target: Path) -> Path:
    page = target / "index.html" if target.is_dir() else target
    if not page.is_file():
        raise FileNotFoundError(f"{page} not found")
    return page


def norm_url(url: str) -> str:
    return re.sub(r"^https?://(www\.)?", "", (url or "").strip()).rstrip("/").lower()


def label(source: dict, i: int) -> str:
    return (source.get("title") or source.get("url") or f"source {i + 1}")[:60] \
        if isinstance(source, dict) else f"source {i + 1}"


def section(page: str, css_class: str, tag: str) -> str | None:
    m = re.search(rf'<{tag} class="{css_class}">(.*?)</{tag}>', page, re.S)
    return m.group(1) if m else None


def check_sources(sources: list, f: Findings) -> None:
    missing, enums, urls, dates, tiers, caveats = {}, [], [], [], [], []
    for i, s in enumerate(sources):
        name = label(s, i)
        if not isinstance(s, dict):
            f.error("schema", f"element {i + 1} is not an object")
            continue
        for field in FIELDS:
            if field not in s:
                missing.setdefault(field, []).append(name)
        if s.get("type") not in WEB_TYPES or s.get("independence") not in WEB_INDEPENDENCE \
                or s.get("tier") not in TIERS:
            enums.append(f"{name} ({s.get('type')}, {s.get('independence')}, {s.get('tier')})")
        if not re.match(r"^https?://", str(s.get("url") or ""), re.I):
            urls.append(name)
        if s.get("date") is not None and not re.match(r"^\d{4}-\d{2}-\d{2}$", str(s["date"])):
            dates.append(f"{name} ({s['date']})")
        computed = compute(s.get("scores"), web=True)
        if computed is None or computed != (s.get("score"), s.get("tier")):
            want = f"{computed[0]} {computed[1]}" if computed else "incomplete sub-scores"
            tiers.append(f"{name} (page {s.get('score')} {s.get('tier')}, sub-scores give {want})")
        if (s.get("independence") in NEEDS_CAVEAT or s.get("tier") == "Peripheral") \
                and not s.get("caveat"):
            caveats.append(name)
    for field, names in missing.items():
        f.error("schema", f"sources missing '{field}' (use null, never omit)", names)
    if enums:
        f.error("schema", "type, independence or tier outside 10-html-reports.md's schema", enums)
    if urls:
        f.error("schema", "url is not http(s) - the template will not link it", urls)
    if dates:
        f.error("schema", "date is neither YYYY-MM-DD nor null - never infer a date", dates)
    if tiers:
        f.error("scores", "score/tier disagrees with the sub-scores - get both from "
                          "state.py score --web", tiers)
    if caveats:
        f.error("caveat", "flagged-independence or Peripheral sources with no caveat", caveats)


def check_state(sources: list, f: Findings) -> None:
    if not STATE.exists():
        f.error("state", f"{STATE.relative_to(ROOT)} not found - /websearch Step 6 never ran")
        return
    seen = json.loads(STATE.read_text(encoding="utf-8")).get("seen", {})
    by_url = {norm_url(k): v for k, v in seen.items()}
    absent, status, differs = [], [], []
    for i, s in enumerate(sources):
        if not isinstance(s, dict):
            continue
        entry = by_url.get(norm_url(s.get("url")))
        name = label(s, i)
        if entry is None:
            absent.append(name)
        elif entry.get("status") != "included":
            status.append(f"{name} ({entry.get('status')})")
        elif (entry.get("scores"), entry.get("tier"), entry.get("independence")) != \
                (s.get("scores"), s.get("tier"), s.get("independence")):
            differs.append(name)
    if absent:
        f.error("state", "on the page but not in seen_web_sources.json - run Step 6's write", absent)
    if status:
        f.error("state", "on the page but not 'included' in seen_web_sources.json", status)
    if differs:
        f.error("state", "scores, tier or independence differ from seen_web_sources.json", differs)


def run(target: Path) -> Findings:
    f = Findings()
    page_path = locate(target)
    page = page_path.read_text(encoding="utf-8")

    left = sorted({t for t in TOKENS if t in page})
    if left:
        f.error("tokens", "placeholders left - the build did not finish", left)

    if TEMPLATE.exists():
        want = COMMENT.search(TEMPLATE.read_text(encoding="utf-8"))
        got = COMMENT.search(page)
        if want and (not got or got.group(1) != want.group(1)):
            f.warn("template", "header comment differs from blog/template.html - pages built "
                               "before 2026-10-06 carry a second copy of the report there; "
                               "rebuild from the current template to drop it")

    for css_class, tag, name in (("scope", "div", "scope note"),
                                 ("synthesis", "section", "synthesis")):
        body = section(page, css_class, tag)
        text = re.sub(r"<[^>]+>|<strong>.*?</strong>", " ", body or "")
        if body is None or not text.replace("Search scope &amp; limitations", "").strip():
            f.error("content", f"{name} is missing or empty")
    synthesis = section(page, "synthesis", "section") or ""
    extra = sorted({t.lower() for t in re.findall(r"</?\s*([a-zA-Z][\w-]*)", synthesis)}
                   - SYNTHESIS_TAGS)
    if extra:
        f.warn("synthesis", "tags outside 10-html-reports.md's set (p, h3, ul, li, strong, em, a, code)",
               extra)

    loaded = re.findall(r'<(?:script|link|img|iframe)\b[^>]*\b(?:src|href)="(?!#)([^"]+)"', page)
    if loaded:
        f.error("offline", "resources loaded from outside the page - it must work offline and "
                           "not leak the topic", loaded)

    blocks = DATA_BLOCK.findall(page)
    if len(blocks) != 1:
        f.error("data", f'expected one <script id="data"> block, found {len(blocks)}')
        return f
    if "<" in blocks[0]:
        f.error("data", 'literal "<" in the embedded source JSON - fetched text can end the '
                        'script block; write every "<" as \\u003c')
    try:
        sources = json.loads(blocks[0])
    except json.JSONDecodeError as exc:
        f.error("data", f"embedded source JSON does not parse: {exc}")
        return f
    if not isinstance(sources, list) or not sources:
        f.error("data", "embedded source JSON is not a non-empty array")
        return f

    check_sources(sources, f)

    standalone = page_path.parent / "sources.json"
    if not standalone.exists():
        f.error("sources.json", "missing - /websearch writes the same array beside the page")
    else:
        try:
            if json.loads(standalone.read_text(encoding="utf-8")) != sources:
                f.error("sources.json", "parses to different data than the page's embedded array")
        except json.JSONDecodeError as exc:
            f.error("sources.json", f"does not parse: {exc}")

    check_state(sources, f)
    return f


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("target", help="blog/<topic_slug> or its index.html")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    target = Path(args.target)
    try:
        f = run(target)
    except FileNotFoundError as exc:
        print(json.dumps({"error": str(exc), "code": "NOT_FOUND"}), file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps({"target": str(target),
                          "errors": [Findings.render(e, True) for e in f.errors],
                          "warnings": [Findings.render(w, True) for w in f.warnings]}, indent=2))
    else:
        print(f"{'FAIL' if f.errors else 'PASS'}  {target}  "
              f"({len(f.errors)} errors, {len(f.warnings)} warnings)")
        for item in f.errors:
            print(f"  ERROR  {Findings.render(item, False)}")
        for item in f.warnings:
            print(f"  warn   {Findings.render(item, False)}")
    return 1 if f.errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
