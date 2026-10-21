#!/usr/bin/env python3
"""Group the library's papers into research labs, for the knowledge graph.

Run from anywhere:  python3 tools/kg_labs.py [--bib PATH] [--json]

A lab is a group of authors, found by community detection on an author graph:
two authors are linked once per paper they share, more strongly when one of them
is that paper's senior (last) author or they list the same institution on it.
Grouping papers directly by "shares an author" fails: one student who moves
between two labs chains both into a single blob (the first mockup of the graph
merged 27 XR papers that way). Grouping authors keeps the two labs apart, and a
paper belongs to the lab of its senior author, with the labs of its other
authors listed as bridges.

Author identity comes from OpenAlex ids in research/graph_cache.json
(tools/kg_enrich.py). A paper with no cached record falls back to the names in
state; a name is joined to an OpenAlex id when exactly one id in the library
carries that name, and every lab holding a name-matched author is flagged.

--bib restricts the printout to the papers a report cites; the classification
always covers the whole library. Reads state and the cache, writes nothing.
Stdlib only.
"""

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

import state
from check_report import parse_bib

RESOLUTION = 1.0
SENIOR_WEIGHT = 3
OTHER_WEIGHT = 1
SHARED_INSTITUTION_BONUS = 1


def _norm_name(name: str) -> str:
    plain = unicodedata.normalize("NFKD", name or "")
    plain = "".join(c for c in plain if not unicodedata.combining(c)).lower()
    tokens = [t for t in re.split(r"[\s.]+", plain) if t]
    if not tokens:
        return ""
    if len(tokens) == 1:
        return tokens[0]
    return f"{tokens[-1]} {tokens[0][0]}"


def author_key(author: dict) -> tuple[str, bool]:
    """(key, matched_by_name): the OpenAlex author id, else "surname initial"."""
    if author.get("authorId"):
        return author["authorId"], False
    return _norm_name(author.get("name", "")), True


def _senior_index(authors: list[dict]) -> int:
    for i, a in enumerate(authors):
        if a.get("position") == "last":
            return i
    return len(authors) - 1


def louvain(nodes: list[str], weights: dict[tuple[str, str], float],
            resolution: float = RESOLUTION) -> dict[str, str]:
    """Weighted Louvain modularity communities, {node: community label}.
    Deterministic: nodes are visited in sorted order and ties keep the first."""
    adj = {n: {} for n in nodes}
    self_w = {n: 0.0 for n in nodes}
    for (a, b), w in weights.items():
        adj[a][b] = adj[a].get(b, 0.0) + w
        adj[b][a] = adj[b].get(a, 0.0) + w
    membership = {n: n for n in nodes}
    level = sorted(nodes)
    for _ in range(50):
        k = {n: sum(adj[n].values()) + 2 * self_w[n] for n in level}
        m2 = sum(k.values())
        if m2 == 0:
            break
        comm = {n: n for n in level}
        tot = dict(k)
        moved = False
        for _ in range(100):
            improved = False
            for n in level:
                current = comm[n]
                tot[current] -= k[n]
                links = defaultdict(float)
                for nb, w in adj[n].items():
                    links[comm[nb]] += w
                best = current
                best_gain = links.get(current, 0.0) - resolution * tot[current] * k[n] / m2
                for c in sorted(links):
                    gain = links[c] - resolution * tot[c] * k[n] / m2
                    if gain > best_gain + 1e-9:
                        best, best_gain = c, gain
                comm[n] = best
                tot[best] += k[n]
                if best != current:
                    improved = moved = True
            if not improved:
                break
        if not moved:
            break
        new_level = sorted(set(comm.values()))
        new_adj = {c: {} for c in new_level}
        new_self = {c: 0.0 for c in new_level}
        for n in level:
            new_self[comm[n]] += self_w[n]
            for nb, w in adj[n].items():
                a, b = comm[n], comm[nb]
                if a == b:
                    new_self[a] += w / 2  # each internal edge is seen from both ends
                else:
                    new_adj[a][b] = new_adj[a].get(b, 0.0) + w
        membership = {orig: comm[c] for orig, c in membership.items()}
        adj, self_w, level = new_adj, new_self, new_level
    return membership


def classify_labs(papers: dict[str, list[dict]]) -> dict:
    """Labs for PAPERS, {paper id: [authors in byline order]}. Each author is
    {name, authorId, position, institutions}; only name is required."""
    ids_by_name = defaultdict(set)
    for authors in papers.values():
        for a in authors:
            if a.get("authorId"):
                ids_by_name[_norm_name(a.get("name", ""))].add(a["authorId"])

    by_name, names, insts = set(), defaultdict(Counter), defaultdict(Counter)
    paper_authors, paper_senior = {}, {}
    weights = defaultdict(float)
    # Doubt sits with the authorship, not the person. A paper's lab is its senior
    # author's, so a paper is flagged when its senior author was matched by name; an
    # author is flagged only when no OpenAlex id was ever found for them.
    paper_named = {}
    for pid in sorted(papers):
        authors = [a for a in papers[pid] if a.get("name") or a.get("authorId")]
        keys, inst_ids, named_at = [], [], []
        for a in authors:
            key, named = author_key(a)
            named_at.append(named)
            if named:
                if len(ids_by_name.get(key, ())) == 1:
                    key = next(iter(ids_by_name[key]))
                else:
                    by_name.add(key)
            keys.append(key)
            inst_ids.append({i["id"] for i in a.get("institutions") or [] if i.get("id")})
            names[key][a.get("name") or key] += 1
            for i in a.get("institutions") or []:
                if i.get("name"):
                    insts[key][i["name"]] += 1
        senior = keys[_senior_index(authors)] if keys else None
        paper_named[pid] = bool(keys) and named_at[_senior_index(authors)]
        paper_senior[pid] = senior
        paper_authors[pid] = list(dict.fromkeys(keys))
        for i in range(len(keys)):
            for j in range(i + 1, len(keys)):
                a, b = keys[i], keys[j]
                if a == b:
                    continue
                w = SENIOR_WEIGHT if senior in (a, b) else OTHER_WEIGHT
                if inst_ids[i] & inst_ids[j]:
                    w += SHARED_INSTITUTION_BONUS
                weights[tuple(sorted((a, b)))] += w

    all_keys = sorted({k for ks in paper_authors.values() for k in ks})
    community = louvain(all_keys, dict(weights))

    def display(key):
        return sorted(names[key].items(), key=lambda kv: (-kv[1], kv[0]))[0][0]

    members = defaultdict(list)
    for key in all_keys:
        members[community[key]].append(key)
    primary_by_comm = defaultdict(list)
    for pid in sorted(papers):
        if paper_senior[pid] is not None:
            primary_by_comm[community[paper_senior[pid]]].append(pid)
    order = sorted(members, key=lambda c: (-len(primary_by_comm[c]), -len(members[c]), c))

    def head_of(c):
        """The author a lab is named after (and identified by)."""
        seniors = Counter(paper_senior[p] for p in primary_by_comm[c])
        on_papers = Counter(k for p in primary_by_comm[c] for k in paper_authors[p]
                            if community[k] == c)
        if seniors and max(seniors.values()) >= 2:
            return sorted(seniors.items(), key=lambda kv: (-kv[1], -on_papers[kv[0]],
                                                           display(kv[0])))[0][0]
        if on_papers:
            # Every senior author leads one paper: name the lab after whoever is on
            # most of its papers, not whichever senior sorts first.
            return sorted(on_papers, key=lambda k: (-on_papers[k], -seniors[k], display(k)))[0]
        return sorted(members[c], key=lambda k: (-sum(names[k].values()), display(k)))[0]

    heads = {c: head_of(c) for c in order}
    # Ids end up in bookmarks, so they come from the head author, not from rank.
    lab_id = {c: "L-" + hashlib.sha1(heads[c].encode()).hexdigest()[:8] for c in order}
    rank = {lab_id[c]: i for i, c in enumerate(order)}
    paper_primary, paper_labs = {}, {}
    for pid in sorted(papers):
        senior = paper_senior[pid]
        primary = lab_id[community[senior]] if senior is not None else None
        others = {lab_id[community[k]] for k in paper_authors[pid]} - {primary}
        paper_primary[pid] = primary
        paper_labs[pid] = ([primary] if primary else []) + sorted(others, key=rank.get)

    labs, seen_names = [], Counter()
    for c in order:
        lid = lab_id[c]
        head = heads[c]
        surname = display(head).split()[-1] if display(head).split() else head
        institution = (sorted(insts[head].items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
                       if insts[head] else None)
        name = f"{surname} lab"
        seen_names[(name, institution)] += 1
        if seen_names[(name, institution)] > 1:
            name = f"{name} ({seen_names[(name, institution)]})"
        labs.append({
            "id": lid, "name": name, "institution": institution, "senior": display(head),
            "authors": [{"key": k, "name": display(k), "papers": sum(names[k].values()),
                         "matched_by_name": k in by_name}
                        for k in sorted(members[c], key=lambda k: (-sum(names[k].values()),
                                                                    display(k)))],
            "papers": primary_by_comm[c],
            "bridges": [p for p in sorted(papers) if lid in paper_labs[p][1:]],
            "named_papers": sum(paper_named[p] for p in primary_by_comm[c]),
            "matched_by_name": any(paper_named[p] for p in primary_by_comm[c]),
        })
    return {"author_lab": {k: lab_id[community[k]] for k in all_keys}, "labs": labs,
            "paper_primary": paper_primary, "paper_labs": paper_labs, "paper_named": paper_named,
            "paper_authors": paper_authors}


def lab_edges(result: dict, years: dict[str, int | None]) -> list[dict]:
    """"lab" edges chain each lab's papers in publication order; "collab" edges join
    papers that share an author but belong to different labs."""
    edges = []
    for lab in result["labs"]:
        chain = sorted(lab["papers"], key=lambda p: (years.get(p) or 9999, p))
        edges += [{"source": a, "target": b, "type": "lab"} for a, b in zip(chain, chain[1:])]
    by_author = defaultdict(list)
    for pid, keys in sorted(result["paper_authors"].items()):
        for k in keys:
            by_author[k].append(pid)
    collab = set()
    primary = result["paper_primary"]
    for pids in by_author.values():
        for i, a in enumerate(pids):
            for b in pids[i + 1:]:
                if primary[a] and primary[b] and primary[a] != primary[b]:
                    collab.add(tuple(sorted((a, b))))
    edges += [{"source": a, "target": b, "type": "collab"} for a, b in sorted(collab)]
    return edges


def library_papers(entries: dict, cache: dict) -> dict[str, list[dict]]:
    """{state key: authors} for every non-skipped entry: OpenAlex authorships where
    cached, else the names state records."""
    works = cache.get("works", {})
    out = {}
    for key, entry in entries.items():
        if entry.get("status") == "skipped":
            continue
        rec = works.get(key)
        if rec and rec.get("authors"):
            out[key] = rec["authors"]
        else:
            out[key] = [{"name": n} for n in entry.get("authors") or [] if isinstance(n, str)]
    return out


def bib_keys(bib: Path, entries: dict) -> set[str]:
    """State keys of the entries BIB cites, matched on DOI, arXiv id or URL."""
    parsed, _ = parse_bib(bib.read_text(encoding="utf-8"))
    cited = set()
    for fields in parsed.values():
        cited |= state.identifiers(*(fields.get(f) for f in state.BIB_ID_FIELDS))
    return {k for k, e in entries.items() if state.identifiers(k, e.get("url")) & cited}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--bib", help="print only the papers this .bib cites")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    import kg_enrich
    entries = state.load("sources", state.FILES["sources"])
    result = classify_labs(library_papers(entries, kg_enrich.load_cache()))
    shown = bib_keys(Path(args.bib), entries) if args.bib else set(result["paper_primary"])
    labs = []
    for lab in result["labs"]:
        papers = [p for p in lab["papers"] if p in shown]
        bridges = [p for p in lab["bridges"] if p in shown]
        if papers or bridges:
            labs.append({**lab, "papers": papers, "bridges": bridges})
    if args.json:
        print(json.dumps({"papers_shown": len(shown), "labs": labs}, indent=2))
        return 0
    multi = [l for l in labs if len(l["papers"]) > 1]
    print(f"{len(shown)} papers; {len(labs)} labs, {len(multi)} with more than one paper "
          f"(classified across the whole library of {len(result['paper_primary'])}).\n")
    for lab in labs:
        where = f", {lab['institution']}" if lab["institution"] else ""
        flag = (f"  [{lab['named_papers']} paper(s) with authors matched by name]"
                if lab["named_papers"] else "")
        print(f"{lab['id']}  {lab['name']}{where} - {len(lab['papers'])} paper(s){flag}")
        core = [a["name"] for a in lab["authors"][:6]]
        print(f"    authors: {', '.join(core)}"
              + (f" +{len(lab['authors']) - 6} more" if len(lab["authors"]) > 6 else ""))
        for p in lab["papers"]:
            e = entries.get(p, {})
            print(f"    - {e.get('title', p)} ({e.get('year', 'n.d.')})")
        for p in lab["bridges"]:
            e = entries.get(p, {})
            print(f"    ~ bridge: {e.get('title', p)} (senior author's lab: "
                  f"{result['paper_primary'][p]})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
