#!/usr/bin/env python3
"""Where the library is thin, for the knowledge graph's Gaps view.

Two kinds of gap, kept apart because they rest on different evidence:

- **Report gaps**: the bullets of each report's "Open Questions" section, which a
  reviewer agent checked against the sources. report_index() reads them, with the
  state keys of the papers each one cites, so the graph can hang each question
  off the sub-areas those papers belong to.
- **Computed gaps**: counts over the library's labels (state.py `subareas`,
  `contribution`). Each one carries the exact rule that produced it, because a
  researcher shown "gap" with no reason cannot judge it. The thresholds are the
  constants below.

Imported by tools/knowledge_graph.py. Reads only; stdlib only.
"""

import hashlib
import re
from pathlib import Path

import state
from check_report import _balanced, parse_bib
from evidence_table import plain, surname

THIN_BELOW = 3              # fewer scored papers than this in a sub-area
STALE_YEARS = 2             # no paper from (current year - this) or later
NO_DEFENCE_MIN_ATTACKS = 3  # this many attack papers and no defence
SCORED = ("ranked", "synthesized")
NOT_WHERE_USED = ("Evidence Basis", "Revision History")

CITE = re.compile(r"\\([a-zA-Z]*cite[a-zA-Z]*)\*?(?:\[[^\]]*\])*\{([^}]*)\}")
HEADING = re.compile(r"\\(section|subsection)\*?\{")
LIST_TOKEN = re.compile(r"\\begin\{(?:itemize|enumerate)\}|\\end\{(?:itemize|enumerate)\}|\\item\b")


def _strip_comments(tex: str) -> str:
    return "\n".join(re.sub(r"(?<!\\)%.*", "", line) for line in tex.splitlines())


def _author_label(fields: dict | None, key: str) -> tuple[str, str]:
    if not fields:
        return key, "n.d."
    authors = [a for a in (fields.get("author") or "").split(" and ") if a.strip()]
    if not authors:
        name = plain(fields.get("title") or key)
    elif len(authors) == 1:
        name = surname(authors[0])
    elif len(authors) == 2:
        name = f"{surname(authors[0])} and {surname(authors[1])}"
    else:
        name = f"{surname(authors[0])} et al."
    return name, plain(fields.get("year") or "n.d.")


def latex_to_text(tex: str, bib: dict) -> str:
    """Readable plain text: citations become author-year, markup is dropped."""
    def cite(m):
        command, keys = m.group(1), [k.strip() for k in m.group(2).split(",") if k.strip()]
        labels = [_author_label(bib.get(k), k) for k in keys]
        if command == "citeauthor":
            return "; ".join(n for n, _ in labels)
        if command == "citeyear":
            return "; ".join(y for _, y in labels)
        if command in ("citet", "textcite", "Citet", "Textcite"):
            return " and ".join(f"{n} ({y})" for n, y in labels)
        if command == "citealp":
            return "; ".join(f"{n}, {y}" for n, y in labels)
        if command == "citealt":
            return "; ".join(f"{n} {y}" for n, y in labels)
        return "(" + "; ".join(f"{n}, {y}" for n, y in labels) + ")"

    text = CITE.sub(cite, tex)
    text = text.replace("\\\\", " ").replace("\\ ", " ")  # line break, control space
    text = text.replace("\\%", "%").replace("\\&", "&").replace("\\_", "_").replace("\\$", "$")
    text = text.replace("\\ldots", "…").replace("---", "—").replace("--", "–")
    text = text.replace("``", "“").replace("''", "”").replace("~", " ").replace("\\,", " ")
    previous = None
    while previous != text:
        previous = text
        text = re.sub(r"\\[a-zA-Z]+\*?\{([^{}]*)\}", r"\1", text)
    text = re.sub(r"\\[a-zA-Z]+\*?", "", text)
    return " ".join(text.replace("{", "").replace("}", "").split())


def _state_key_index(entries: dict) -> dict[str, str]:
    index = {}
    for key in sorted(entries):
        for ident in state.identifiers(key, entries[key].get("url")):
            index.setdefault(ident, key)
    return index


def report_index(report_dir: Path, entries: dict) -> dict:
    """One report: its title, where each library paper is cited (section >
    subsection), its Open Questions with the papers each cites, and the
    identifiers of everything its .bib holds."""
    tex = _strip_comments((report_dir / "report.tex").read_text(encoding="utf-8"))
    bib_path = report_dir / "references.bib"
    bib = parse_bib(bib_path.read_text(encoding="utf-8"))[0] if bib_path.exists() else {}
    index = _state_key_index(entries)
    to_state, cited_ids = {}, set()
    for bkey, fields in bib.items():
        ids = state.identifiers(*(fields.get(f) for f in state.BIB_ID_FIELDS))
        cited_ids |= ids
        hits = sorted(index[i] for i in ids if i in index)
        if hits:
            to_state[bkey] = hits[0]

    title_match = re.search(r"\\title\{", tex)
    title = report_dir.name
    if title_match:
        title = latex_to_text(_balanced(tex, title_match.end() - 1)[0], bib)

    # Walk the body in order: headings set the location, citations record it.
    events = sorted([(m.start(), "h", m) for m in HEADING.finditer(tex)]
                    + [(m.start(), "c", m) for m in CITE.finditer(tex)], key=lambda e: e[0])
    section = subsection = None
    cites: dict[str, list[str]] = {}
    sections: list[tuple[str, int, int]] = []
    for pos, kind, m in events:
        if kind == "h":
            heading = latex_to_text(_balanced(tex, m.end() - 1)[0], bib)
            if m.group(1) == "section":
                section, subsection = heading, None
                if sections:
                    sections[-1] = (sections[-1][0], sections[-1][1], pos)
                sections.append((heading, m.end(), len(tex)))
            else:
                subsection = heading
            continue
        if section is None or section in NOT_WHERE_USED:
            continue
        where = f"{section} > {subsection}" if subsection else section
        for bkey in (k.strip() for k in m.group(2).split(",")):
            skey = to_state.get(bkey)
            if skey and where not in cites.setdefault(skey, []):
                cites[skey].append(where)

    questions = []
    for heading, start, end in sections:
        if "open questions" not in heading.lower():  # as check_report finds the section
            continue
        body, depth, current = tex[start:end], 0, None
        for m in LIST_TOKEN.finditer(body):
            token = m.group(0)
            if token.startswith("\\begin"):
                depth += 1
            elif token.startswith("\\end"):
                depth -= 1
                if depth == 0 and current is not None:
                    current["end"] = m.start()
                    questions.append(current)
                    current = None
            elif depth == 1:
                if current is not None:
                    current["end"] = m.start()
                    questions.append(current)
                current = {"start": m.end()}
        for q in questions:
            raw = body[q.pop("start"):q.pop("end")]
            keys = []
            for cm in CITE.finditer(raw):
                for bkey in (k.strip() for k in cm.group(2).split(",")):
                    if bkey in to_state and to_state[bkey] not in keys:
                        keys.append(to_state[bkey])
            q.update(text=latex_to_text(raw, bib), keys=keys)
        break
    # Ids end up in bookmarks, so they come from the question's text, not its position.
    seen = {}
    for q in questions:
        base = hashlib.sha1(q["text"].encode()).hexdigest()[:10]
        seen[base] = seen.get(base, 0) + 1
        q["id"] = base if seen[base] == 1 else f"{base}-{seen[base]}"
    return {"slug": report_dir.name, "title": title, "cites": cites,
            "open_questions": questions, "cited_ids": cited_ids}


def report_indexes(reports_dir: Path, entries: dict,
                   warnings: list[str] | None = None) -> list[dict]:
    """Every report under REPORTS_DIR. One that cannot be read is skipped with a
    line in WARNINGS, so a half-written report never stops the graph building."""
    if not reports_dir.is_dir():
        return []
    out = []
    for d in sorted(reports_dir.iterdir()):
        if not (d / "report.tex").is_file():
            continue
        try:
            out.append(report_index(d, entries))
        except (ValueError, OSError, UnicodeDecodeError) as exc:
            if warnings is not None:
                warnings.append(f"report {d.name} could not be read and is left out: {exc}")
    return out


def _owner(label: str, interest: str, taxonomy: dict) -> tuple[str, str]:
    for other in taxonomy:
        if label.startswith(other + ": "):
            return other, label[len(other) + 2:]
    return interest, label


def computed_gaps(entries: dict, current_year: int, taxonomy: dict[str, list[str]],
                  cited: set | frozenset = frozenset(),
                  landmarks: dict[str, list[str]] | None = None) -> list[dict]:
    """Thin, stale and no-defence sub-areas; scored papers no report cites; and
    profile landmarks the library lacks. TAXONOMY is state.subareas_all();
    CITED the identifiers of every report's .bib; LANDMARKS {interest: [text]}
    of landmarks with no matching entry."""
    members = {(i, s): [] for i, subs in taxonomy.items() for s in subs}
    labelled = set()
    for key in sorted(entries):
        e = entries[key]
        if e.get("status") not in SCORED or not isinstance(e.get("subareas"), list):
            continue
        labelled.add(e.get("subject"))
        for label in e["subareas"]:
            spot = _owner(label, e.get("subject"), taxonomy)
            if spot in members:
                members[spot].append(key)
                labelled.add(spot[0])

    gaps = []
    cutoff = current_year - STALE_YEARS
    for (interest, sub), keys in members.items():
        if interest not in labelled:
            continue  # no labels yet: every sub-area would read as thin
        where = f"{interest}:{sub}"
        if len(keys) < THIN_BELOW:
            gaps.append({"id": f"thin:{where}", "kind": "thin", "interest": interest,
                         "subarea": sub, "items": keys,
                         "text": f"Only {len(keys)} scored paper{'s' if len(keys) != 1 else ''} "
                                 f"on {sub}",
                         "rule": f"Fewer than {THIN_BELOW} scored papers in this sub-area"})
        years = [entries[k]["year"] for k in keys if isinstance(entries[k].get("year"), int)]
        if years and max(years) < cutoff:
            gaps.append({"id": f"stale:{where}", "kind": "stale", "interest": interest,
                         "subarea": sub, "items": keys,
                         "text": f"Newest paper on {sub} is from {max(years)}",
                         "rule": f"No paper from {cutoff} or later"})
        attacks = [k for k in keys if entries[k].get("contribution") == "attack"]
        defences = [k for k in keys if entries[k].get("contribution") == "defence"]
        if len(attacks) >= NO_DEFENCE_MIN_ATTACKS and not defences:
            gaps.append({"id": f"no_defence:{where}", "kind": "no_defence",
                         "interest": interest, "subarea": sub, "items": attacks,
                         "text": f"{len(attacks)} attack papers and no defence on {sub}",
                         "rule": f"{NO_DEFENCE_MIN_ATTACKS} or more attack papers and no "
                                 "defence papers"})

    for interest in taxonomy:
        unused = [k for k in sorted(entries)
                  if entries[k].get("subject") == interest
                  and entries[k].get("status") == "ranked"
                  and entries[k].get("verdict") in ("Core", "Supporting")
                  and not (state.identifiers(k, entries[k].get("url")) & cited)]
        if unused:
            gaps.append({"id": f"unused:{interest}", "kind": "unused", "interest": interest,
                         "subarea": None, "items": unused,
                         "text": f"{len(unused)} Core or Supporting paper"
                                 f"{'s' if len(unused) != 1 else ''} scored but not cited "
                                 "in any report",
                         "rule": "Scored Core or Supporting, not cited in any report"})
        missing = (landmarks or {}).get(interest) or []
        if missing:
            gaps.append({"id": f"missing_landmark:{interest}", "kind": "missing_landmark",
                         "interest": interest, "subarea": None, "items": [],
                         "detail": list(missing),
                         "text": f"{len(missing)} landmark work{'s' if len(missing) != 1 else ''} "
                                 "in your profile not found in the library",
                         "rule": "Listed under Known landmark works in your profile, with no "
                                 "matching title in the library"})
    return gaps


def missing_landmarks(interests: list[str]) -> dict[str, list[str]]:
    """{interest: [landmark text]} for profile landmarks no entry's title matches."""
    out = {}
    for interest in interests:
        try:
            found = state.landmarks(interest, related=True)
        except state.StateError:
            continue
        out[interest] = [w["text"] for w in found if w["match"] is None]
    return out
