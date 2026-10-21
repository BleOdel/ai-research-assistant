# /graph - Build and Open the Library Knowledge Graph

Builds `graph/index.html`, an interactive 3D map of the whole library: every paper in
`research/seen_sources.json` and every included web source in
`blog/seen_web_sources.json`, with what is new since the last search highlighted. It
shows the research groups papers come from, how sub-areas connect, how the field
progressed year by year, and where the gaps are. `graph/README.md` describes the page.

`/research`, `/rank`, `/synthesize`, `/update` and `/websearch` already rebuild it when
they finish. Run `/graph` to rebuild it on demand, to look at a different "new since"
date, or to check the labels behind it.

`$ARGUMENTS` may be empty or a date, `YYYY-MM-DD`: items first seen on or after it
count as new. The default is the date of the most recent search.

## Step 1: Build

```bash
python3 tools/knowledge_graph.py --enrich
```

With a date: `python3 tools/knowledge_graph.py --enrich --new-since YYYY-MM-DD`.

`--enrich` first fetches OpenAlex author records and references for papers not yet in
`research/graph_cache.json` (`tools/kg_enrich.py`). If OpenAlex rate-limits it, the
fetch stops with its progress saved and the page still builds; papers without OpenAlex
data fall back to the author names state records, and the page marks their labs
"matched by name". Say how many were fetched and whether it stopped early.

## Step 2: Check

```bash
python3 tools/knowledge_graph.py --check
```

It must print PASS. It checks that the page's data parses, every link joins two
existing nodes, every gap states its rule, no title can break out of the page's
script, and nothing loads from the network. A failure is a bug in the builder: report
it, do not hand-edit the page.

## Step 3: Labels that need attention

```bash
python3 tools/state.py check --verbose
```

From its output, report two things:

- **Stale sub-area labels** (warnings ending "not in the current profile"): sources
  labelled with a sub-area the profile no longer lists. The page shows them under
  "unassigned (label no longer in profile)". Offer to relabel them: re-read each
  source's abstract and pick names from `python3 tools/state.py subareas`, then write
  them with `state.py batch`. Never relabel from the title alone.
- **Scored sources with no labels** (gaps "scored entry missing subareas" or
  "missing contribution"): they sit under "unassigned" and are left out of the
  sub-area gap rules. Offer the same relabelling.

## Step 4: Present

```
## Library graph - YYYY-MM-DD

<the summary line the build printed>

<papers> papers, <web> web sources, <labs> labs with more than one paper, <gaps> gaps.
OpenAlex: <fetched> fetched (<stopped early, if it did>).
Check: PASS
Labels: <n> stale, <m> missing (or "all current")

Open graph/index.html in a browser.
```

## Important Rules

1. **The graph never writes state.** Relabelling goes through `tools/state.py`, from
   fetched abstracts, like every other label.
2. **`graph/index.html` holds every title in the library** and is gitignored. Never
   commit it or publish it.
3. **Computed labs and gaps are derived, and the page says how.** When reporting them,
   give the rule (a gap's `rule`, a lab's "matched by name" flag) with the claim.
