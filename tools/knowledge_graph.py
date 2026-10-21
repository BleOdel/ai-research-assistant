#!/usr/bin/env python3
"""Build the library knowledge graph: graph/index.html, one self-contained page.

Run from anywhere:
    python3 tools/knowledge_graph.py [--enrich] [--new-since YYYY-MM-DD] [--json]
    python3 tools/knowledge_graph.py --check
    python3 tools/knowledge_graph.py --synthetic N

Draws the whole library - every paper in research/seen_sources.json and every
included web source in blog/seen_web_sources.json - with what is new since the
last search highlighted. Papers sit under the profile's sub-areas (state.py
`subareas`), grouped into research labs (kg_labs.py), linked by citation
(OpenAlex referenced_works, kept to the library) and to the reports that cite
them, next to the gaps (kg_gaps.py). Web sources are their own node type, marked
not peer-reviewed; the two tracks stay separate in state.

The data is one JSON block injected into graph/template.html, every "<" written
as \\u003c so a title cannot close the script element. Status and evidence are
shown in plain words, never as internal state names (see STATUS_LABELS).

--enrich fetches missing OpenAlex authorship first (kg_enrich.py). --new-since
sets what counts as new; the default is the latest first_seen date in either
state file, i.e. the most recent search. --check lints the built page and exits
1 on errors. --synthetic N builds an N-paper made-up library instead, for the
scale check. graph/index.html is gitignored: it holds the library's titles.

Reads state, the profile, reports/*/ and research/graph_cache.json; writes only
graph/index.html. Stdlib only.
"""

import argparse
import json
import random
import re
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

import kg_enrich
import kg_gaps
import kg_labs
import state

ROOT = state.ROOT
TEMPLATE = ROOT / "graph" / "template.html"
PAGE = ROOT / "graph" / "index.html"
FULLTEXT = ROOT / "research" / "fulltext"
VENDOR = ROOT / "graph" / "vendor"
SLOT = "[GRAPH_JSON]"
VENDOR_TAG = re.compile(r'<script data-vendor="([\w.-]+)"></script>')

# Plain words for the page. The internal names (ranked, synthesized, ...) mean
# nothing to a reader who has not read state.py.
STATUS_LABELS = {
    "new": "Found, not yet scored",
    "skipped": "Judged off-topic at triage",
    "ranked": "Scored, not yet used in a report",
    "synthesized": "Used in a report",
    "unfetchable": "Abstract could not be retrieved",
}
EVIDENCE_LABELS = {"fulltext": "Read in full", "abstract": "Abstract only"}
NOT_ASSESSED = "Not yet assessed"
WEB_KIND = "Web source, not peer-reviewed"
# Three kinds of "no profile sub-area": never labelled yet (e.g. straight after
# /research), labelled [] because nothing in the profile fits (a taxonomy signal),
# and labelled with a sub-area the profile no longer lists.
UNLABELLED, UNASSIGNED, STALE = "__unlabelled", "__unassigned", "__stale"
NOT_A_SUBAREA = (UNLABELLED, UNASSIGNED, STALE)
DATA_BLOCK = re.compile(r'<script id="data" type="application/json">(.*?)</script>', re.S)
EXTERNAL = [re.compile(r"""\b(?:src|href)\s*=\s*["']?\s*(?:https?:)?//""", re.I),
            re.compile(r"""url\(\s*["']?\s*(?:https?:)?//""", re.I),
            re.compile(r"""@import\s+["']?\s*(?:https?:)?//""", re.I)]


def hub_id(interest: str, sub: str) -> str:
    return f"subarea:{interest}:{sub}"


def _year(entry: dict) -> int | None:
    y = entry.get("year")
    if isinstance(y, int):
        return y
    if isinstance(y, str) and re.fullmatch(r"\d{4}", y):
        return int(y)
    d = entry.get("date")
    if isinstance(d, str) and re.match(r"\d{4}-", d):
        return int(d[:4])
    return None


def _pdf_index() -> dict[str, str]:
    if not FULLTEXT.is_dir():
        return {}
    return {p.name.lower(): p.name for p in FULLTEXT.glob("*.pdf")}


def _pdf_for(key: str, entry: dict, pdfs: dict[str, str]) -> str | None:
    for ident in sorted(state.identifiers(key, entry.get("url"))):
        kind, _, value = ident.partition(":")
        if kind not in ("arxiv", "doi"):
            continue
        name = f"{kind}-{re.sub(r'[^a-zA-Z0-9.-]+', '-', value).strip('-')}.pdf".lower()
        if name in pdfs:
            return f"../research/fulltext/{pdfs[name]}"
    return None


class Hubs:
    """Interest and sub-area hub nodes, created as papers and web sources need them."""

    def __init__(self, taxonomy: dict, details: dict):
        self.taxonomy, self.nodes, self.edges = taxonomy, {}, []
        for interest, subs in taxonomy.items():
            self.interest(interest)
            for sub in subs:
                self._hub(interest, sub, sub, "profile", details.get(interest, {}).get(sub))

    def interest(self, name: str) -> str:
        nid = f"interest:{name}"
        if nid not in self.nodes:
            self.nodes[nid] = {"id": nid, "type": "interest", "label": name}
        return nid

    def _hub(self, interest, key, label, kind, detail=None) -> str:
        nid = hub_id(interest, key)
        if nid not in self.nodes:
            self.nodes[nid] = {"id": nid, "type": "subarea", "label": label, "interest": interest,
                               "kind": kind, "detail": detail}
            self.edges.append({"source": nid, "target": self.interest(interest),
                               "type": "interest"})
        return nid

    def for_labels(self, labels, interest: str | None) -> list[str]:
        interest = interest or "Uncategorized"
        if not isinstance(labels, list):
            return [self._hub(interest, UNLABELLED, f"{interest}: not yet labelled", "unlabelled")]
        if not labels:
            return [self._hub(interest, UNASSIGNED, f"{interest}: fits no listed sub-area",
                              "unassigned")]
        out = []
        for label in labels:
            owner, name = kg_gaps._owner(label, interest, self.taxonomy)
            if name in self.taxonomy.get(owner, []):
                hub = hub_id(owner, name)
            else:
                hub = self._hub(owner, STALE, f"{owner}: unassigned (label no longer in profile)",
                                "stale")
            if hub not in out:
                out.append(hub)
        return out


def _library() -> dict:
    entries = state.load("sources", state.FILES["sources"])
    taxonomy = state.subareas_all()
    warnings: list[str] = []
    return {
        "warnings": warnings,
        "entries": entries,
        "web": state.load("web", state.FILES["web"]),
        "cache": kg_enrich.load_cache(),
        "reports": kg_gaps.report_indexes(ROOT / "reports", entries, warnings),
        "taxonomy": taxonomy,
        "details": {i: {s["name"]: s["detail"] for s in state.subarea_entries(i)}
                    for i in taxonomy},
        "landmarks": kg_gaps.missing_landmarks(list(taxonomy)),
        "pdfs": _pdf_index(),
    }


def synthetic_library(n: int, seed: int = 7) -> dict:
    """A made-up library of N papers with labs, citations and gaps, for the scale
    check. Nothing in it is real."""
    rng = random.Random(seed)
    taxonomy = {f"Interest {c}": [f"Sub-area {c}{i}" for i in range(1, 7)] for c in "ABC"}
    statuses = ["ranked"] * 5 + ["synthesized"] * 4 + ["new", "skipped", "unfetchable"]
    contributions = ["attack", "defence", "measurement", "user-study", "survey", "tool",
                     "position"]
    labs = [[f"https://openalex.org/A{lab}x{m}" for m in range(5)] for lab in range(max(3, n // 6))]
    entries, works = {}, {}
    for i in range(n):
        key = f"10.9999/synthetic.{i}"
        interest = rng.choice(list(taxonomy))
        lab = rng.choice(labs)
        team = rng.sample(lab[1:], 2) + [lab[0]]
        if rng.random() < 0.15:
            team.insert(1, rng.choice(rng.choice(labs)))
        year = rng.randint(2012, 2026) if rng.random() > 0.05 else None
        entries[key] = {
            "title": f"Synthetic paper {i}", "subject": interest, "status": rng.choice(statuses),
            "year": year, "first_seen": f"2026-{rng.randint(1, 10):02d}-{rng.randint(1, 28):02d}",
            "subareas": rng.sample(taxonomy[interest], rng.choice([1, 1, 2])),
            "contribution": rng.choice(contributions), "overall_score": rng.randint(20, 95),
            "verdict": rng.choice(["Core", "Supporting", "Peripheral"]),
            "evidence_basis": rng.choice(["abstract", "fulltext"]),
            "url": f"https://doi.org/{key}", "authors": [a.rsplit("/", 1)[1] for a in team],
        }
        works[key] = {"openalex": f"https://openalex.org/W{i}", "error": None,
                      "fetched": "2026-10-21",
                      "referenced": [f"https://openalex.org/W{rng.randrange(n)}"
                                     for _ in range(rng.randint(0, 6))],
                      "authors": [{"name": a.rsplit("/", 1)[1], "authorId": a,
                                   "position": "last" if j == len(team) - 1 else "middle",
                                   "institutions": [{"id": f"I{labs.index(lab)}",
                                                     "name": f"Institute {labs.index(lab)}"}]}
                                  for j, a in enumerate(team)]}
    return {"warnings": [], "entries": entries, "web": {}, "cache": {"works": works}, "reports": [],
            "taxonomy": taxonomy, "details": {}, "landmarks": {}, "pdfs": {}}


def _summary(new_nodes: list[dict], new_since: str, interests: list[str],
             thin_hubs: set, lab_sizes: Counter) -> str:
    if not new_nodes:
        return f"Nothing new since {new_since}."
    by_interest = Counter(n.get("interest") or "Uncategorized" for n in new_nodes)
    order = {name: i for i, name in enumerate(interests)}
    parts = []
    for interest, count in sorted(by_interest.items(),
                                  key=lambda kv: (-kv[1], order.get(kv[0], 99), kv[0])):
        subs = Counter(h for n in new_nodes if (n.get("interest") or "Uncategorized") == interest
                       for h in n.get("_hubs", []) if not h.endswith(NOT_A_SUBAREA))
        top = ""
        if subs:
            hub, k = sorted(subs.items(), key=lambda kv: (-kv[1], kv[0]))[0]
            top = f" (most on {hub.split(':', 2)[2]})"
        parts.append(f"{count} in {interest}{top}")
    text = f"{len(new_nodes)} new since {new_since}: {', '.join(parts)}"
    from_known = sum(1 for n in new_nodes if n.get("primaryLab")
                     and lab_sizes[n["primaryLab"]] > 0)
    in_thin = sum(1 for n in new_nodes if set(n.get("_hubs", [])) & thin_hubs)
    clauses = []
    if from_known:
        clauses.append(f"{from_known} from labs already in your library")
    if in_thin:
        clauses.append(f"{in_thin} in thin sub-areas")
    return text + "".join(f"; {c}" for c in clauses) + "."


def build(new_since: str | None = None, synthetic: int = 0, today: str | None = None) -> dict:
    """The page's data object (see graph/README.md for the schema)."""
    lib = synthetic_library(synthetic) if synthetic else _library()
    entries, web, cache, taxonomy = lib["entries"], lib["web"], lib["cache"], lib["taxonomy"]
    today = today or date.today().isoformat()
    dates = [e.get("first_seen") for e in list(entries.values()) + list(web.values())
             if isinstance(e.get("first_seen"), str)]
    latest = max(dates) if dates else today
    new_since = new_since or latest
    hubs = Hubs(taxonomy, lib["details"])

    labs = kg_labs.classify_labs(kg_labs.library_papers(entries, cache))
    pid = lambda key: f"paper:{key}"  # noqa: E731

    reports = lib["reports"]
    used_in = defaultdict(list)
    for r in reports:
        for key, sections in r["cites"].items():
            used_in[key].append({"slug": r["slug"], "title": r["title"], "sections": sections})

    by_openalex = {rec["openalex"]: key for key, rec in cache.get("works", {}).items()
                   if rec.get("openalex") and key in entries}
    cites = []
    for key, rec in sorted(cache.get("works", {}).items()):
        if key not in entries:
            continue
        for ref in rec.get("referenced") or []:
            target = by_openalex.get(ref)
            if target and target != key:
                cites.append((key, target))
    cites = sorted(set(cites))
    cites_out, cited_by = Counter(a for a, _ in cites), Counter(b for _, b in cites)

    nodes, edges = [], []
    for key in sorted(entries):
        e = entries[key]
        authors = [a.get("name") for a in (cache.get("works", {}).get(key) or {}).get("authors", [])]
        status = e.get("status")
        node = {
            "id": pid(key), "type": "paper", "label": e.get("title") or key,
            "title": e.get("title") or key, "authors": authors or e.get("authors") or [],
            "year": _year(e), "venue": e.get("venue"), "url": e.get("url"),
            "pdf": _pdf_for(key, e, lib["pdfs"]),
            "interest": e.get("subject"), "subareas": e.get("subareas"),
            "contribution": e.get("contribution"),
            "statusLabel": STATUS_LABELS.get(status, status or "Unknown"),
            "hiddenByDefault": status == "skipped",
            "verdict": e.get("verdict"), "score": e.get("overall_score"),
            "evidenceLabel": EVIDENCE_LABELS.get(e.get("evidence_basis"), NOT_ASSESSED),
            "disclosure": e.get("disclosure"), "firstSeen": e.get("first_seen"),
            "isNew": status != "skipped" and (e.get("first_seen") or "") >= new_since,
            "primaryLab": labs["paper_primary"].get(key),
            "labs": labs["paper_labs"].get(key, []),
            "matchedByName": labs["paper_named"].get(key, False),
            "reports": used_in.get(key, []),
            "citesIn": cites_out[key], "citedByIn": cited_by[key],
        }
        node["_hubs"] = hubs.for_labels(e.get("subareas"), e.get("subject"))
        edges += [{"source": node["id"], "target": h, "type": "subarea"} for h in node["_hubs"]]
        edges += [{"source": node["id"], "target": f"report:{r['slug']}", "type": "report"}
                  for r in node["reports"]]
        nodes.append(node)

    for key in sorted(web):
        w = web[key]
        if w.get("status") != "included":
            continue
        node = {
            "id": f"web:{key}", "type": "web", "label": w.get("title") or key,
            "title": w.get("title") or key, "site": w.get("site"), "url": key,
            "date": w.get("date"), "year": _year(w), "tier": w.get("tier"),
            "score": w.get("overall_score"), "independence": w.get("independence"),
            "contentType": w.get("type"), "caveat": w.get("caveat") or w.get("note"),
            "interest": w.get("interest"), "subareas": w.get("subareas"),
            "firstSeen": w.get("first_seen"), "isNew": (w.get("first_seen") or "") >= new_since,
            "kindLabel": WEB_KIND,
        }
        node["_hubs"] = hubs.for_labels(w.get("subareas"), w.get("interest"))
        edges += [{"source": node["id"], "target": h, "type": "web_subarea"}
                  for h in node["_hubs"]]
        nodes.append(node)

    for r in reports:
        pdf = ROOT / "reports" / r["slug"] / "report.pdf"
        nodes.append({"id": f"report:{r['slug']}", "type": "report", "label": r["title"],
                      "title": r["title"], "slug": r["slug"],
                      "pdf": f"../reports/{r['slug']}/report.pdf" if pdf.exists() else None,
                      "papers": sum(1 for k in r["cites"] if k in entries)})

    years = {k: _year(e) for k, e in entries.items()}
    for edge in kg_labs.lab_edges(labs, years):
        edges.append({"source": pid(edge["source"]), "target": pid(edge["target"]),
                      "type": edge["type"]})
    edges += [{"source": pid(a), "target": pid(b), "type": "cites"} for a, b in cites]

    cited_ids = set().union(*(r["cited_ids"] for r in reports)) if reports else set()
    gaps = kg_gaps.computed_gaps(entries, int(today[:4]), taxonomy, cited=cited_ids,
                                 landmarks=lib["landmarks"])
    for g in gaps:
        g["items"] = [pid(k) for k in g["items"]]
    for r in reports:
        for q in r["open_questions"]:
            q_hubs = []
            for key in q["keys"]:
                for h in hubs.for_labels(entries[key].get("subareas"), entries[key].get("subject")):
                    if not h.endswith(NOT_A_SUBAREA) and h not in q_hubs:
                        q_hubs.append(h)
            gaps.append({"id": f"report:{r['slug']}:{q['id']}", "kind": "report", "report": r["slug"],
                         "interest": None, "subarea": None, "subareas": q_hubs,
                         "items": [pid(k) for k in q["keys"]], "text": q["text"],
                         "rule": f"Open question in report {r['title']}"})
    for g in gaps:
        gid = f"gap:{g['id']}"
        nodes.append({"id": gid, "type": "gap", "label": g["text"], **{
            k: g.get(k) for k in ("kind", "text", "rule", "interest", "subarea", "items",
                                  "detail", "report")}})
        if g["kind"] == "report":
            edges.append({"source": gid, "target": f"report:{g['report']}", "type": "gap_report"})
            edges += [{"source": gid, "target": h, "type": "gap_subarea"} for h in g["subareas"]]
        elif g.get("subarea"):
            edges.append({"source": gid, "target": hub_id(g["interest"], g["subarea"]),
                          "type": "gap_subarea"})
        else:
            edges.append({"source": gid, "target": hubs.interest(g["interest"]),
                          "type": "gap_interest"})

    new_nodes = [n for n in nodes if n.get("isNew")]
    known = Counter(n["primaryLab"] for n in nodes
                    if n["type"] == "paper" and not n["isNew"] and n["primaryLab"]
                    and not n["hiddenByDefault"])
    thin_hubs = {hub_id(g["interest"], g["subarea"]) for g in gaps if g["kind"] == "thin"}
    summary = _summary(new_nodes, new_since, list(taxonomy), thin_hubs, known)
    for n in nodes:
        n.pop("_hubs", None)

    lab_list = [{"id": l["id"], "name": l["name"], "institution": l["institution"],
                 "senior": l["senior"], "namedPapers": l["named_papers"],
                 "authors": [{"name": a["name"], "papers": a["papers"],
                              "matchedByName": a["matched_by_name"]} for a in l["authors"]],
                 "papers": [pid(p) for p in l["papers"]],
                 "bridges": [pid(p) for p in l["bridges"]]} for l in labs["labs"]]
    all_nodes = list(hubs.nodes.values()) + nodes
    return {
        "meta": {
            "built": today, "latestDate": latest, "newSince": new_since, "summary": summary,
            "warnings": lib["warnings"],
            "synthetic": bool(synthetic),
            "counts": {"papers": sum(1 for n in nodes if n["type"] == "paper"),
                       "web": sum(1 for n in nodes if n["type"] == "web"),
                       "new": len(new_nodes),
                       "labs": sum(1 for l in lab_list if len(l["papers"]) > 1),
                       "gaps": len(gaps)},
            "thresholds": {"thinBelow": kg_gaps.THIN_BELOW, "staleYears": kg_gaps.STALE_YEARS,
                           "staleFrom": int(today[:4]) - kg_gaps.STALE_YEARS,
                           "noDefenceMinAttacks": kg_gaps.NO_DEFENCE_MIN_ATTACKS},
        },
        "interests": [{"name": i, "subareas": s} for i, s in taxonomy.items()],
        "nodes": all_nodes,
        "edges": hubs.edges + edges,
        "labs": lab_list,
        "gaps": gaps,
    }


def render(data: dict, template: str, vendor: dict[str, str] | None = None) -> str:
    """TEMPLATE with DATA in its one slot and each <script data-vendor="NAME"> filled
    with graph/vendor/NAME (or VENDOR[NAME]), so the page is one offline file.
    Every "<" in the data becomes \\u003c and every "</script" in vendored code
    "<\\/script", so neither can end its script element early."""
    if template.count(SLOT) != 1:
        raise ValueError(f"template must contain {SLOT} exactly once")
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")

    def inline(m: re.Match) -> str:
        name = m.group(1)
        if vendor is not None and name in vendor:
            code = vendor[name]
        elif (VENDOR / name).is_file():
            code = (VENDOR / name).read_text(encoding="utf-8")
        else:
            raise ValueError(f"vendored script {name} not found in {VENDOR}")
        code = re.sub(r"</(script)", r"<\\/\1", code, flags=re.I).replace("<!--", "<\\!--")
        return f"<script>{code}</script>"

    # The slot is filled first: vendored code is never searched for it.
    return VENDOR_TAG.sub(inline, template.replace(SLOT, payload))


def extract_data(html: str) -> dict:
    blocks = DATA_BLOCK.findall(html)
    if len(blocks) != 1:
        raise ValueError(f"expected one data block, found {len(blocks)}")
    return json.loads(blocks[0])


def check(html: str) -> list[str]:
    """Problems with a built page: data that does not parse or references missing
    nodes, a gap with no rule, a literal "<" in the data, or anything the page
    would load from the network."""
    errors = []
    blocks = DATA_BLOCK.findall(html)
    if len(blocks) != 1:
        return [f"expected one data block, found {len(blocks)}"]
    if "<" in blocks[0]:
        errors.append("literal '<' inside the data block (must be written as \\u003c)")
    try:
        data = json.loads(blocks[0])
    except json.JSONDecodeError as exc:
        return errors + [f"data block is not valid JSON: {exc}"]
    ids = [n.get("id") for n in data.get("nodes", [])]
    dupes = [i for i, c in Counter(ids).items() if c > 1]
    if dupes:
        errors.append(f"duplicate node ids: {', '.join(map(str, dupes[:5]))}")
    known = set(ids)
    for e in data.get("edges", []):
        for end in ("source", "target"):
            if e.get(end) not in known:
                errors.append(f"{e.get('type')} edge {end} {e.get(end)!r} is not a node")
    for g in data.get("gaps", []):
        if not str(g.get("rule") or "").strip():
            errors.append(f"gap {g.get('id')!r} has no rule")
    outside = DATA_BLOCK.sub("", html)
    for pattern in EXTERNAL:
        for m in pattern.finditer(outside):
            errors.append(f"external resource: {outside[m.start():m.start() + 80]!r}")
    return errors


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--enrich", action="store_true",
                        help="fetch missing OpenAlex authorship first (kg_enrich.py)")
    parser.add_argument("--new-since", help="YYYY-MM-DD; default: the latest first_seen")
    parser.add_argument("--check", action="store_true", help="lint the built page")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--synthetic", type=int, default=0, metavar="N")
    return parser


def main(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)

    if args.check:
        if not PAGE.exists():
            print(f"{PAGE.relative_to(ROOT)} not built - run python3 tools/knowledge_graph.py")
            return 1
        errors = check(PAGE.read_text(encoding="utf-8"))
        for e in errors:
            print(f"ERROR {e}")
        print(f"{PAGE.relative_to(ROOT)}: {'PASS' if not errors else 'FAIL'} ({len(errors)} errors)")
        return 1 if errors else 0

    if args.new_since and not state.DATE_RE.match(args.new_since):
        print("--new-since must be YYYY-MM-DD", file=sys.stderr)
        return 1
    if args.enrich and not args.synthetic:
        # Enrichment is an improvement, never a precondition: whatever goes wrong,
        # the page is still built from what is cached.
        try:
            entries = state.load("sources", state.FILES["sources"])
            counts = kg_enrich.enrich(entries, kg_enrich.connector_fetch,
                                      date.today().isoformat())
            note = {"rate-limited": " (stopped: rate limit; run again later)",
                    "connector-failed": f" (stopped: {counts.get('failure')}; run again later)"
                    }.get(counts["stopped"], "")
            line = (f"OpenAlex: {counts['fetched']} fetched, {counts['cached']} cached, "
                    f"{counts['errors']} not found, {counts['skipped_no_id']} without an id{note}")
        except Exception as exc:  # noqa: BLE001 - see above
            line = f"OpenAlex: enrichment failed ({exc}); building from the cache"
        if not args.json:
            print(line)
    data = build(new_since=args.new_since, synthetic=args.synthetic)
    html = render(data, TEMPLATE.read_text(encoding="utf-8"))
    state.atomic_write(PAGE, html)
    path = str(PAGE.relative_to(ROOT))
    if args.json:
        print(json.dumps({"path": path, "counts": data["meta"]["counts"],
                          "summary": data["meta"]["summary"]}))
    else:
        c = data["meta"]["counts"]
        print(data["meta"]["summary"])
        print(f"{c['papers']} papers, {c['web']} web sources, {c['labs']} labs with more than "
              f"one paper, {c['gaps']} gaps -> {path}")
        for w in data["meta"]["warnings"]:
            print(f"WARNING {w}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
