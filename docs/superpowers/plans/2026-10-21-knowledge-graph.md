# Library Knowledge Graph Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a self-contained interactive 3D page of the researcher's whole library
(papers and web sources). It highlights each search's new papers and shows research
labs, subjects, progression and gaps, with information and data clarity first.

**Architecture:** Stdlib Python tools read the state files, the profile, the reports and
an OpenAlex metadata cache. They classify labs (author-graph community detection) and
gaps (report open questions plus computed rules), then inject one JSON data block into
a tracked HTML template that renders with vendored three.js and 3d-force-graph. Two new
state fields (`subareas`, `contribution`) are added through `state.py` and filled at
scoring time, with a one-time backfill.

**Tech Stack:**
- **Python:** 3.10+, stdlib only (`unittest`, the pattern in `tools/` and `tests/`).
- **Connector:** TypeScript under Bun for the OpenAlex extension (`bun test`).
- **Page:** vanilla JS with vendored `three` and `3d-force-graph`, both MIT-licensed.

**Spec:** `docs/superpowers/specs/2026-10-21-knowledge-graph-design.md`. Read it before
any task. Its "First principle: information and data clarity" binds every UI decision.

## Global Constraints

- **Python:** stdlib only. No pip dependencies.
- **Single write path:** `tools/state.py` is the only writer of `research/seen_sources.json`
  and `blog/seen_web_sources.json`. The graph tools never write state.
- **Grounding:** labels (`subareas`, `contribution`) are assigned only from fetched content
  (an abstract or a page), never from a title alone.
- **Offline:** the page makes no network calls at runtime (no CDN, no external fonts),
  and it must open from `file://`.
- **Gitignored output:** `graph/index.html` is gitignored. Tracked files: `graph/template.html`,
  `graph/vendor/*`, `graph/README.md`.
- **Escaping:** the embedded JSON writes every `<` as `<`, since titles and abstracts
  are untrusted (the same rule as `10-html-reports.md`).
- **Plain wording on the page:** never show `ranked`, `synthesized` or `unfetchable`. Use the
  mapping in Task 9.
- **Thresholds:** constants with these defaults: thin sub-area `< 3` scored papers; stale
  sub-area = no paper with `year >= current_year - 2`; no-defence = `>= 3` `attack` papers
  and `0` `defence` papers in a sub-area.
- **Contribution values (exact):** `attack`, `defence`, `measurement`, `user-study`, `survey`,
  `tool`, `position`.
- **Undated nodes:** go in an "undated" lane, are never given an inferred year, and are
  excluded from year filters and staleness rules.
- **"New":** `first_seen >= newSince`, where `newSince` defaults to the latest `first_seen`
  date in either state file.
- **Profile-agnostic:** nothing XR-specific in code. Interests, sub-areas and landmarks come
  from the profile.
- **Performance:** smooth at 1,000 nodes and 5,000 edges on a laptop.
- **Commits:** end each with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Untrusted strings** (a title containing `</script>`, quotes, Unicode, LaTeX braces) must
   neither break the page nor run. Test: `test_titles_are_escaped_in_data_block` (Task 9).
2. **A fresh install** (no web state file, no reports, an interest whose profile entry has no
   sub-area list) must still build a valid page with empty sections, not crash. Test:
   `test_builds_with_missing_inputs` (Task 9).
3. **An OpenAlex failure mid-enrichment** (rate limit, unknown id) must keep earlier results,
   continue, and leave the page buildable with the name fallback. Test:
   `test_enrich_keeps_progress_on_failure` (Task 4).
4. **Stale labels** (a source labelled with a sub-area later removed from the profile) must
   show as "unassigned (label no longer in profile)", not vanish or crash. Test:
   `test_stale_subarea_label_is_unassigned_not_dropped` (Task 9).
5. **Scale:** a 1,000-node synthetic library must render and stay interactive. Check: the
   Task 10 browser step with `--synthetic 1000`.

---

### Task 1: OpenAlex connector returns author positions, institutions and references

**Files:**
- Modify: `.agents/skills/openalex-search/cli/src/helpers.ts` (`OpenAlexAuthor`,
  `OpenAlexWork`, `parseOneWork`)
- Modify: `.agents/skills/openalex-search/SKILL.md` (document the new fields)
- Test: `.agents/skills/openalex-search/cli/tests/parsing.test.ts`

**Interfaces:**
- Produces:
  - **Authors:** each `detail --format json` author carries
    `{name, authorId, orcid, position: "first"|"middle"|"last"|null, institutions: [{id: string, name: string}]}`.
  - **Works:** each work carries `referencedWorks: string[]`, a list of OpenAlex work ids.

- [ ] **Step 1: Write failing tests** in `parsing.test.ts`:
  - `parseOneWork` on a raw work with `authorships[i].author_position = "last"` and
    `institutions = [{id:"https://openalex.org/I1", display_name:"Uni A"}]` gives
    `authors[i].position === "last"` and
    `authors[i].institutions[0]` equal to `{id:"https://openalex.org/I1", name:"Uni A"}`.
  - `referenced_works: ["https://openalex.org/W2"]` gives
    `work.referencedWorks` equal to `["https://openalex.org/W2"]`.
  - When those fields are absent: `position === null`, `institutions` is `[]` and
    `referencedWorks` is `[]`.
- [ ] **Step 2:** Run `cd .agents/skills/openalex-search/cli && bun test`. Expected: the new
  tests FAIL.
- [ ] **Step 3:** Extend the types and `parseOneWork`, defensively, matching the existing
  parsing style.
- [ ] **Step 4:** Run `bun test` and `bun run typecheck`. Expected: all pass.
- [ ] **Step 5:** Update SKILL.md's detail output description, then commit
  (`openalex-search: return author position, institutions, referenced works`).

### Task 2: State fields `subareas` and `contribution`, with profile sub-area parsing

**Files:**
- Modify: `tools/state.py`
- Modify: `.claude/commands/rank.md` (the agent output JSON and the "Scored sources:"
  write list, both required by the existing drift test)
- Test: `tests/test_state.py`

**Interfaces:**
- Produces:
  - `CONTRIBUTIONS = ("attack","defence","measurement","user-study","survey","tool","position")`
  - `profile_subareas(interest: str) -> list[str]` parses that interest's
    "Sub-areas of interest" field. It supports a bulleted list (each top-level `  - `
    item, continuation lines joined, and a trailing parenthetical kept) and a single
    comma-separated sentence (split on `,` and on ` and `, then stripped). Unknown
    interest or no field: `[]`.
  - `subareas_all() -> dict[str, list[str]]`, keyed by tracked interest.
  - CLI `state.py subareas [--subject S] [--json]` lists the taxonomy, for agents to copy
    exact names.
  - `SCORED_FIELDS` gains `"subareas"` and `"contribution"`.
- Validation (`validate`):
  - **Sources:** `subareas` must be a list of strings, else an error. `contribution` must
    be in `CONTRIBUTIONS`, else an error.
  - **Web entries:** optional `subareas` (list of strings) and `interest` (a tracked
    interest or `"Uncategorized"`), else an error.
  - **Stale names:** a name not in `profile_subareas` of the entry's interest is **not**
    an error. In `_gaps`, it adds a warning
    `"<key>: sub-area label(s) not in the current profile: <names>"`.
  - **Cross-interest labels:** `"<Interest>: <sub-area>"` labels are checked against that
    interest.

- [ ] **Step 1: Write failing tests** in `tests/test_state.py`:
  - `test_profile_subareas_bulleted_and_sentence_forms`: a fixture profile with one
    bulleted interest (two items, one with a continuation line) and one sentence-form
    interest (`a, b and c`) gives `["Item one (detail)", "Item two"]` and `["a", "b", "c"]`.
  - `test_contribution_enum_enforced`: an upsert with `contribution: "attacker"` is
    refused with `"contribution"` in the error, and `"attack"` is accepted.
  - `test_subareas_must_be_list`: `subareas: "x"` is refused.
  - `test_stale_subarea_is_warning`: a `subareas` name not in the profile is accepted, and
    `check --json` lists a warning containing `"not in the current profile"`.
  - `test_web_entry_interest_and_subareas`: a web upsert with `interest: "XR Security"` and
    `subareas: ["Item one (detail)"]` is accepted, while `interest: "Nope"` is refused.
  - `test_subareas_cli_lists_taxonomy`: `state.py subareas --subject "XR Security" --json`
    returns the list.
- [ ] **Step 2:** Run `python3 -m unittest tests.test_state -q`. Expected: the new tests
  FAIL.
- [ ] **Step 3:** Implement as specified in Interfaces. Extend `SCORED_FIELDS`, then add
  `"subareas"` and `"contribution"` to rank.md's agent output JSON and to its "Scored
  sources:" list.
- [ ] **Step 4:** Run `python3 -m unittest discover -s tests -q` and
  `python3 tools/lint_skills.py`. Expected: all pass, including
  `test_rank_writes_every_scored_field`.
- [ ] **Step 5:** Commit (`state: subareas and contribution fields, profile sub-area taxonomy`).

### Task 3: Scoring commands assign sub-areas and contribution

**Files:**
- Modify:
  - `.claude/commands/synthesize.md` (the Step 1 scoring output; Step 6a writes the fields)
  - `.claude/commands/update.md` (Step 2)
  - `.claude/commands/websearch.md` (Step 3 assigns `interest` and `subareas`; Step 5
    writes them)
- Modify: `.claude/skills/research-assistant/02-source-evaluation.md`. Add a short
  "Classification labels" section saying:
  - labels come from the abstract, as `state.py subareas` names, one or more, `[]` if none
    fits;
  - `contribution` takes one value, from the seven listed;
  - the same grounding rule applies as for scores.
- Modify: `.claude/skills/research-assistant/09-web-source-evaluation.md` (the same rule
  for web `interest` and `subareas`)
- Test: `tests/test_state.py` (extend the drift tests)

**Interfaces:**
- Consumes: `state.py subareas` (Task 2).

- [ ] **Step 1: Write failing tests:**
  - `test_scoring_commands_mention_classification_fields` asserts that `"subareas"` and
    `"contribution"` appear in synthesize.md and update.md.
  - The same test asserts that `"subareas"` and `"interest"` appear in websearch.md's
    state-write JSON block.
- [ ] **Step 2:** Run it. Expected: FAIL.
- [ ] **Step 3:** Edit the docs. Each scoring step tells the agent to run
  `python3 tools/state.py subareas --subject "<interest>"` and copy names exactly.
- [ ] **Step 4:** Run the full suite and `lint_skills`. Expected: pass.
- [ ] **Step 5:** Commit (`commands: assign sub-areas and contribution when scoring`).

### Task 4: OpenAlex enrichment cache

**Files:**
- Create: `tools/kg_enrich.py`
- Test: `tests/test_kg_enrich.py`

**Interfaces:**
- Consumes: the Task 1 connector JSON, and `state.identifiers` and `state.load`.
- Produces:
  - `CACHE = ROOT/"research"/"graph_cache.json"`. Its schema is
    `{"works": {<state key>: {"openalex": str|None, "authors": [{name, authorId, position, institutions:[{id,name}]}], "referenced": [str], "fetched": "YYYY-MM-DD", "error": str|None}}}`.
  - `openalex_lookup_id(state_key: str, entry: dict) -> str | None`:
    - a DOI from the key, url or `doi` field returns it;
    - an arXiv id returns `10.48550/arXiv.<id>`;
    - an OpenAlex `W…` URL returns that id;
    - otherwise (for example a Semantic Scholar URL only) returns `None`.
  - `enrich(entries: dict, fetch: Callable[[str], dict|None], today: str, limit: int|None=None) -> dict`
    fetches only keys missing from the cache, or present with `error` set and `fetched`
    older than 30 days. After each fetch it writes the cache atomically (`state.atomic_write`).
    It returns the counts `{"fetched", "skipped_no_id", "errors", "cached"}`.
  - `connector_fetch(lookup_id: str) -> dict|None` runs
    `bun run .agents/skills/openalex-search/cli/src/cli.ts detail <id> --format json`,
    returns `None` on `NOT_FOUND`, and raises `RateLimited` on `RATE_LIMITED`.
- Errors: when `RateLimited` is raised, `enrich` stops, saves, and records
  `"stopped": "rate-limited"`.
- CLI `python3 tools/kg_enrich.py [--limit N] [--json]` enriches every
  `seen_sources.json` entry whose status is not `skipped` and prints the counts. Task 6
  runs it on the live library; Task 9's `--enrich` calls `enrich` directly.

- [ ] **Step 1: Write failing tests:**
  - `test_lookup_id_forms` covers a DOI key, an arXiv URL, an S2-only URL (`None`) and
    an OpenAlex URL.
  - `test_enrich_fetches_only_missing`: with a fake fetch, a second run makes 0 calls.
  - `test_enrich_keeps_progress_on_failure`: a fake fetch that succeeds on 2 keys then
    raises `RateLimited` leaves the cache holding 2 works, with `stopped == "rate-limited"`.
  - `test_enrich_records_not_found_as_error`.
- [ ] **Step 2:** Run `python3 -m unittest tests.test_kg_enrich -q`. Expected: FAIL.
- [ ] **Step 3:** Implement. Pacing: a 0.2 s sleep between real calls, inside
  `connector_fetch` only.
- [ ] **Step 4:** Run the tests. Expected: PASS.
- [ ] **Step 5:** Commit (`kg_enrich: cached OpenAlex authorship and reference lookup`).

### Task 5: Lab classification

**Files:**
- Create: `tools/kg_labs.py`
- Test: `tests/test_kg_labs.py`

**Interfaces:**
- Consumes: Task 4 cache records, and state entries (for name fallback and `authors`).
- Produces:
  - `author_key(author: dict) -> tuple[str, bool]` returns the OpenAlex `authorId` and
    `False`. With no id, it returns a normalised `"surname initial"` (accents stripped,
    lower case) and `True` (matched by name).
  - `classify_labs(papers: dict[str, list[dict]]) -> dict` takes, per paper id, its
    ordered authors (`name`, `authorId`, `position`, `institutions`). It returns
    `{"author_lab": {akey: lab_id}, "labs": [{id, name, institution, authors:[...], papers:[...], matched_by_name: bool}], "paper_primary": {pid: lab_id}, "paper_labs": {pid: [lab_id,...]}}`.
- Author-graph edge weights, summed over the papers two authors share:
  - **3** if either is that paper's last author;
  - **1** otherwise;
  - **+1** if they share an institution on that paper.
- Community detection: weighted Louvain (modularity, resolution 1.0) with deterministic
  node order (sorted keys). Run the local moving phase, aggregate, and repeat until
  modularity gain `< 1e-9`. Isolated authors form singleton labs.
- Primary lab: the lab of the paper's `position == "last"` author. If no position, use
  the last author in the list.
- Naming: the lab's most frequent last-author display name, as `"<Surname> lab"`, plus
  that author's most frequent institution name. No institution: name only.
- `lab_edges(result) -> list[dict]` returns
  `{"source": pid, "target": pid, "type": "lab"}` linking each lab's papers in
  publication order (a chain, not a clique), plus `{"type": "collab"}` for papers sharing
  any author whose primary labs differ.
- CLI `python3 tools/kg_labs.py [--bib PATH] [--json]` classifies the whole cached
  library and prints the labs. Each lab shows its name, defining authors and
  institutions, papers and the matched-by-name flag, and the cross-lab bridge papers are
  listed after the labs. `--bib` restricts the printout (not the classification) to
  entries matching that `.bib`, by `state.identifiers` and `check_report.parse_bib` as
  `state.unmerged` does.

- [ ] **Step 1: Write failing tests:**
  - `test_two_labs_joined_by_one_student_stay_two_labs`: lab A (senior SA, papers 1-3)
    and lab B (senior SB, papers 4-6) share one non-senior author who appears on paper 3
    and paper 4. Result: two labs, with papers 1-3 in one and 4-6 in the other. This is
    the mockup's chaining failure.
  - `test_name_fallback_flags_matched_by_name`: authors without ids are keyed by
    `"wang y"`, and the lab is flagged `matched_by_name: True`.
  - `test_primary_lab_is_senior_authors`.
  - `test_cross_lab_paper_is_bridge`: a paper with authors from two labs is listed under
    both in `paper_labs`, and a `collab` edge exists.
  - `test_deterministic`: two runs give identical output.
  - `test_lab_naming_uses_senior_and_institution`.
  - `test_cli_bib_filter_restricts_printout_only`: the lab ids in the filtered printout
    equal the unfiltered ones for the same papers.
- [ ] **Step 2:** Run `python3 -m unittest tests.test_kg_labs -q`. Expected: FAIL.
- [ ] **Step 3:** Implement Louvain (about 80 lines). Use node-degree and total-weight
  bookkeeping, and delta-modularity for moving node `i` into community `C`:
  `k_i,in/m - resolution*Σ_tot*k_i/(2m^2)`.
- [ ] **Step 4:** Run the tests. Expected: PASS.
- [ ] **Step 5:** Commit (`kg_labs: author-graph Louvain labs with primary lab per paper`).

### Task 6: Lab acceptance checkpoint with the researcher

**Files:**
- Create: `tests/fixtures/kg_labs_xr.json`, written from the researcher's confirmed
  answers.
- Test: `tests/test_kg_labs.py`, extended.

- [ ] **Step 1:** Run `python3 tools/kg_enrich.py` on the live library, repeating after
  any rate-limit stop, until the cache covers every paper with a lookup id. Report the
  counts, including papers with no id (these fall back to name matching).
- [ ] **Step 2:** For the 107 papers cited in
  `reports/xr-security-and-privacy-state-of-the-art`, run
  `python3 tools/kg_labs.py --bib reports/xr-security-and-privacy-state-of-the-art/references.bib`
  to print the proposed labs. For each
  lab, show:
  - its name;
  - its defining authors and institutions;
  - its papers;
  - whether it was matched by name.

  Also show the cross-lab bridges, and report how the mockup's 27-paper chain is now split.
- [ ] **Step 3:** Present this to the researcher, and wait for confirmation or
  corrections.
- [ ] **Step 4:** Encode the confirmed splits as a regression fixture: an anonymised
  author graph plus the expected partition. Add
  `test_confirmed_xr_lab_split_is_reproduced`, and adjust the edge weights or resolution
  until it passes, then run the full suite.
- [ ] **Step 5:** Commit (`kg_labs: regression fixture from researcher-confirmed XR lab split`).

### Task 7: One-time classification backfill (operational, live state)

**Files:** none tracked. The work changes live state through `state.py`; scripts go in the
scratchpad.

- [ ] **Step 1: Tell the researcher what will be written, and get a go-ahead.**
  - **Scope:** `subareas` and `contribution` on every scored entry (status `ranked` or
    `synthesized`, about 290), and `interest` and `subareas` on the 19 included web
    sources.
  - **Method:** abstracts and pages are re-fetched by agents; nothing is assigned from a
    title.
- [ ] **Step 2:** Batch the entries about 8 at a time per interest. Fetch abstracts as
  `/rank --all` did:
  - **Connectors:** Semantic Scholar paced at 1.1 s, then the arXiv and OpenAlex
    fallbacks.
  - **Agents:** dispatch at most 4 agents at once. Each one writes a result file holding
    exact `state.py subareas` names and one `contribution`.
- [ ] **Step 3:** Validate the results (names in the taxonomy, contribution in the enum),
  then write them all with one `state.py batch --file sources` and one
  `state.py batch --file web`.
- [ ] **Step 4:** Run `python3 tools/state.py check --verbose`. Expected: no errors, and
  the "scored entry missing subareas/contribution" gap lists only entries with no
  retrievable abstract. Those are listed for the researcher.

### Task 8: Report parsing and gap rules

**Files:**
- Create: `tools/kg_gaps.py`
- Test: `tests/test_kg_gaps.py`

**Interfaces:**
- Consumes: `check_report.parse_bib`, `state.identifiers`, `state.unmerged`,
  `state.landmarks`, `state.profile_subareas`.
- Produces:
  - `report_index(report_dir: Path, entries: dict) -> dict` returns
    `{"slug", "title", "cites": {state_key: [section titles]}, "open_questions": [{"text", "keys": [state_key]}]}`.
    Bib keys map to state keys through identifiers, as `unmerged` does. Open questions
    are the `\item` bullets under the section whose title starts "Open Questions", with
    LaTeX stripped to plain text.
  - `computed_gaps(entries: dict, current_year: int) -> list[dict]` returns gaps of the
    form `{"id", "kind", "interest", "subarea", "text", "rule", "items": [state_key]}`,
    where `kind` is one of `thin`, `stale`, `no_defence`, `unused` or
    `missing_landmark`.
    - **`rule` holds the exact human-readable rule**, for example
      `"Fewer than 3 scored papers in this sub-area"`,
      `"No paper from 2024 or later"`, or
      `"3 or more attack papers and no defence papers"`.
    - **Scored** means status `ranked` or `synthesized`.
    - **`unused`** uses `state.unmerged` per interest, against the union of all
      reports' `.bib` identifiers.
    - **`missing_landmark`** uses `state.landmarks(interest, related=True)` entries with
      no match.
- Constants: `THIN_BELOW = 3`, `STALE_YEARS = 2`, `NO_DEFENCE_MIN_ATTACKS = 3`.

- [ ] **Step 1: Write failing tests:**
  - `test_thin_threshold_edges`: 2 scored papers are thin, 3 are not.
  - `test_stale_uses_dated_papers_only`: undated papers neither cause nor prevent
    staleness.
  - `test_no_defence_rule`: 3 attacks and 0 defences is a gap; 3 attacks and 1 defence
    is not.
  - `test_every_gap_has_rule_text`.
  - `test_report_open_questions_parsed_with_keys`: a fixture `report.tex` and `.bib` give
    two bullets and their mapped state keys.
  - `test_sections_recorded_per_cited_key`.
- [ ] **Step 2:** Run `python3 -m unittest tests.test_kg_gaps -q`. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run the tests. Expected: PASS.
- [ ] **Step 5:** Commit (`kg_gaps: report open questions and computed gap rules`).

### Task 9: Graph builder, data block and linter

**Files:**
- Create: `tools/knowledge_graph.py`
- Modify:
  - `.gitignore`: add `graph/*` plus `!graph/template.html`, `!graph/vendor/` and
    `!graph/README.md`.
  - `tools/security_guards.py`: add `graph/*` to `REQUIRED_IGNORE_RULES` and a
    `graph/index.html` must-be-ignored path.
- Test: `tests/test_knowledge_graph.py`

**Interfaces:**
- Consumes: Tasks 2, 4, 5 and 8, plus `graph/template.html`. The template has a single
  `<script id="data" type="application/json">[GRAPH_JSON]</script>` slot (Task 10 fills
  out the rest).
- Produces:
  - `build(root: Path, new_since: str|None=None, synthetic: int=0) -> dict` returns the
    data object, with this schema:
    - **`meta`:** `{built, latestDate, newSince, counts:{papers, web, new, labs, gaps}, thresholds}`
    - **`interests`:** `[{name, subareas:[...]}]`
    - **`nodes`:**
      `[{id, type: "paper"|"web"|"subarea"|"interest"|"report"|"gap", label, ...type fields}]`
      - **Paper fields:**
        - **Identity:** `title, authors, year|null, venue, url, pdf|null`, where `pdf` is
          a relative path to `research/fulltext/` if a cached file exists.
        - **Classification:** `interest, subareas, contribution|null`.
        - **Assessment:** `statusLabel, verdict|null, score|null, evidenceLabel,
          disclosure|null`.
        - **Provenance:** `firstSeen, primaryLab|null, labs:[...], matchedByName`.
        - **Usage:** `reports:[{slug, sections:[...]}], citesIn:int, citedByIn:int`.
      - **Web fields:** `title, site, url, date|null, tier, independence, caveat,
        interest|null, subareas, firstSeen, kindLabel: "Web source, not peer-reviewed"`.
    - **`edges`:** `[{source, target, type: "lab"|"collab"|"cites"|"subarea"|"interest"|"report"|"gap_subarea"|"gap_report"|"web_subarea"}]`
    - **`labs`:** the Task 5 `labs` list.
    - **`gaps`:** the Task 8 gaps, plus report gaps `{kind: "report", report: slug, text, rule: "Open question in report <title>", subareas}`.
  - `render(data: dict, template: str) -> str` injects the JSON with every `<` as
    `<`.
  - `check(html: str) -> list[str]` returns error strings. It checks that:
    - the data block parses and every edge's endpoints exist;
    - no `src`/`href` attribute is external;
    - every gap has non-empty `rule`;
    - there is no literal `<` inside the data block.
  - CLI `python3 tools/knowledge_graph.py [--enrich] [--new-since YYYY-MM-DD] [--check] [--json] [--synthetic N]`:
    - **Default:** builds `graph/index.html` atomically, then prints the "what's new"
      summary and the path.
    - **`--enrich`:** runs Task 4 first.
    - **`--check`:** lints the existing page and exits 1 on errors.
    - **`--json`:** prints `{path, counts, summary}`.
    - **`--synthetic N`:** builds an N-paper synthetic library, for the scale check.
- Plain-wording maps (exact strings):
  - **Status:**
    - `new` → "Found, not yet scored"
    - `skipped` → "Judged off-topic at triage"
    - `ranked` → "Scored, not yet used in a report"
    - `synthesized` → "Used in a report"
    - `unfetchable` → "Abstract could not be retrieved"
  - **Evidence:**
    - `fulltext` → "Read in full"
    - `abstract` → "Abstract only"
    - missing → "Not yet assessed"
- Stale labels: a sub-area not in the profile maps to the hub
  `"<interest>: unassigned (label no longer in profile)"`. An empty `subareas` maps to
  `"<interest>: unassigned"`. `Uncategorized` sources go under an `"Uncategorized"`
  interest hub.
- `skipped` papers are included with `statusLabel` set, and the page hides them by
  default (Task 10). `excluded` and `unfetchable` web sources are omitted.
- Summary text (exact form): `"<n> new since <date>: <per-interest counts, largest
  sub-area first>; <m> from labs already in your library; <k> in thin sub-areas."`
  Omit any clause whose count is 0.

- [ ] **Step 1: Write failing tests** on a fixture root (profile, two state files, one
  report, one cache):
  - `test_titles_are_escaped_in_data_block`: a title
    `</script><script>window.x=1</script>` gives `check()` returning `[]`, and the page
    contains no `<script>window.x`.
  - `test_builds_with_missing_inputs`: no web file, no reports, and one interest with no
    sub-area field still build, and `check()` returns `[]`.
  - `test_stale_subarea_label_is_unassigned_not_dropped`.
  - `test_plain_wording_no_internal_status_strings`: the data block has no `statusLabel`
    equal to a raw status.
  - `test_new_since_defaults_to_latest_first_seen`, and `test_new_count_matches_nodes`.
  - `test_every_edge_endpoint_exists` (via `check`).
  - `test_summary_omits_zero_clauses`.
  - `test_cli_json_and_check_exit_codes`.
- [ ] **Step 2:** Run `python3 -m unittest tests.test_knowledge_graph -q`. Expected: FAIL.
- [ ] **Step 3:** Implement. Use a minimal `graph/template.html` containing only the data
  slot for now; Task 10 replaces it.
- [ ] **Step 4:** Run the full suite and `security_guards.py`. Expected: pass.
- [ ] **Step 5:** Commit (`knowledge_graph: build data block, render, lint; gitignore graph output`).

### Task 10: The page (template, vendored libraries, UI)

**Files:**
- Create: `graph/template.html` (full UI; replaces Task 9's minimal one)
- Create: `graph/vendor/three.min.js` and `graph/vendor/3d-force-graph.min.js`
  - **Versions:** pinned at three 0.160.0 and 3d-force-graph 1.73.3, the ones used in the
    approved mockup.
  - **Licences:** each library's MIT licence goes in `graph/vendor/LICENSES.md`.
  - **Approval:** downloading these two files needs the researcher's OK at execution
    time. Report the URLs and sizes first.
- Create: `graph/README.md` (what the page is, how to open it, how it is built)
- Modify: `tools/knowledge_graph.py`, so `render` inlines the two vendor files into the
  page (the page stays a single self-contained file)
- Test: `tests/test_graph_template.py`

**Interfaces:**
- Consumes: the Task 9 data schema.
- UI requirements (from the spec's User experience and First principle; every item
  checked in Step 5):
  - **Regions:**
    - **Top bar:** views 1-4, a 2D/3D toggle, search with autocomplete, and a
      "New since" date control.
    - **Left drawer:** filters and an always-visible legend for the active view.
    - **Centre:** the graph.
    - **Right panel:** details and a breadcrumb trail.
    - **Fit:** no horizontal scroll at 1280×800.
  - **Views:**
    - **Library:** interest and sub-area hubs; new papers ringed; the camera fits the new
      papers on load.
    - **Research groups:** coloured by primary lab; lab edges solid, collab edges faint;
      labs listed by size in the drawer, and clicking one focuses it.
    - **Timeline:** year axis, an "undated" lane, citation arrows.
    - **Gaps:** gap diamonds linked to sub-areas and reports; thin, stale and no-defence
      sub-areas highlighted.
  - **Encodings, each with a non-colour channel:**
    - **Shapes:** paper = sphere sized by score; web = cube; hub = labelled ring;
      gap = diamond.
    - **Status:** solid = "Used in a report"; outlined = "Scored, not yet used"; faded =
      "Abstract could not be retrieved".
    - **Markers:** a small marker for "Read in full"; a ring for new.
    - **Palette:** Okabe-Ito colour-blind-safe; light and dark via `prefers-color-scheme`.
  - **Navigation:**
    - **Focus mode:** clicking a node dims non-neighbours, and Esc or clicking empty space
      exits.
    - **Trail:** a breadcrumb of the last 10 nodes, with back/forward synced to
      `location.hash`.
    - **Hash state:** `#view=<v>&focus=<id>&since=<date>&filters=<…>` restores the state.
  - **Detail panel:**
    - **Paper:** every field in the Task 9 paper node, plain wording, links to the URL,
      the local PDF and each citing report section, and "Show labmates" and "Show lineage"
      buttons.
    - **Lab:** its defining authors and institutions, and "matched by name" when flagged.
    - **Gap:** its `rule` and source.
  - **Filters:**
    - **Selectors:** interest, sub-area, year range (with the undated toggle), node type,
      status, tier, evidence, disclosure and contribution.
    - **Toggles:** "new only"; "show papers judged off-topic" (off by default).
    - **Counts:** live counts per filter value.
  - **Precise list view:** a sortable table of exactly the currently visible papers and
    web sources (title, authors, year, sub-areas, lab, status, tier). Every count on the
    page is a link that opens this view filtered to its items.
  - **Export:** the visible set as Markdown and CSV reading lists, and a PNG of the canvas.
  - **First-load card:** `meta`'s summary text, dismissible.
  - **Keyboard:** `/` search, `Esc`, `←`/`→` trail, `1`-`4` views. Controls are reachable
    by keyboard with visible focus.
  - **No decoration:** no auto-rotation, particles or glow. Motion only on user action.
  - **Labels:** hub and lab labels always shown; paper titles on hover and in focus mode.

- [ ] **Step 1: Write failing tests** in `test_graph_template.py`:
  - `test_template_has_single_data_slot`.
  - `test_no_external_resources` after render, reusing `check`.
  - `test_required_ui_regions_present`: element ids `topbar`, `drawer`, `graph`, `detail`,
    `trail`, `listview`, `legend` and `summary`.
  - `test_no_internal_status_words_in_template`: no literal `ranked`, `synthesized` or
    `unfetchable` in UI text.
  - `test_vendor_files_inlined_and_licensed`.
- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3:** Build the template.
  - **Libraries:** fix the canvas sizing issue found in the mockup by setting
    `.width()`/`.height()` from the container and refitting on resize.
  - **Dimensions:** the 2D/3D toggle uses `numDimensions(2|3)`.
  - **Performance:** cache node positions per view.
- [ ] **Step 4:** Run `python3 tools/knowledge_graph.py` on the live library and on
  `--synthetic 1000`, then `--check`. Expected: exit 0.
- [ ] **Step 5: Browser verification.** Open each page in the Browser pane and check
  every UI requirement above, one by one:
  - **Views and controls:** each view; 2D/3D; focus and Esc; the trail and back/forward;
    a hash reload restores the state; every filter, with matching counts; the list view
    matches the visible set; the exports open.
  - **Fit and theme:** no horizontal scroll at 1280×800; dark and light.
  - **Scale:** the 1,000-node page stays interactive (rotate and filter respond within
    about 1 s).
  - **Recording:** record each item pass/fail in the commit message body.
- [ ] **Step 6:** Commit (`graph: interactive 3D library page, clarity-first UI, vendored renderer`).

### Task 11: Command integration and docs

**Files:**
- Create: `.claude/commands/graph.md`. It runs
  `python3 tools/knowledge_graph.py --enrich` (which builds the page), then
  `python3 tools/knowledge_graph.py --check`, and reports:
  - the page path;
  - the "what's new" summary;
  - stale-label warnings from `state.py check --verbose`, with an offer to relabel them.
- Modify the commands: `research.md`, `rank.md`, `synthesize.md`, `update.md` and
  `websearch.md` each end with a "Refresh the library graph" step running
  `python3 tools/knowledge_graph.py --enrich` and quoting its summary line.
- Modify the docs:
  - `README.md` (the commands list, plus the file tree entries for the tools, `graph/` and
    tests);
  - `USAGE.md` (a new "Your library graph" section);
  - `CLAUDE.md` (the Repo Structure `graph/` line and the tools line);
  - `.claude/skills/research-assistant/SKILL.md` (Quick Commands).
- Modify: `.claude/settings.json` and `tools/security_guards.py` `ALLOWED_PERMISSIONS`,
  adding `Bash(python3 tools/knowledge_graph.py:*)`. Ask the researcher first.
- Test: `tests/test_knowledge_graph.py`.

- [ ] **Step 1: Write a failing test,**
  `test_documented_invocations_use_real_flags`. Every `tools/knowledge_graph.py …--flag`
  in the commands and skills uses a real flag, and at least six commands mention the
  tool.
- [ ] **Step 2:** Run it. Expected: FAIL.
- [ ] **Step 3:** Edit the docs. Once the allowlist is approved, update the allowlist
  files.
- [ ] **Step 4:** Run the full suite, `lint_skills` and `security_guards`. Expected: pass.
- [ ] **Step 5:** Commit (`commands: /graph and automatic graph refresh after each search`).

### Task 12: Final build, verification and release

- [ ] **Step 1:** Build the live graph, run `--check`, then repeat the Task 10 Step 5
  browser checks on the live page.
- [ ] **Step 2:** Run the full suite, `lint_skills`, `security_guards`, and every
  connector's `bun test` and typecheck.
- [ ] **Step 3:** Rebase on `origin/master`, push, and watch CI with `gh run watch <id>
  --repo BleOdel/ai-research-assistant --interval 30 --exit-status`.
- [ ] **Step 4:** Pull in the working clone, remove the worktree, and report to the
  researcher.
  - **Report:** the page path, the "what's new" summary, and the browser-check results.
  - **Calls:** any calls made during the build that were not in the spec.
