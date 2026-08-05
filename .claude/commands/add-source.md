# /add-source - Generate a Connector Skill for a New Source Database

You are helping the user build a connector skill for an academic/research source
database not already covered by `arxiv-search`, `semantic-scholar-search`, or
`google-scholar-search`. This command turns the process already used to build those
three manually into a guided workflow: investigate the database's actual API,
scaffold the skill from the established connector contract, and live-test before
registering anything.

Good candidates if the user has nothing specific in mind: **OpenAlex**
(`api.openalex.org` - fully open, no key, broad cross-field coverage, a natural
complement since it indexes venues/citations similarly to Semantic Scholar but
without the rate-limit problems that connector has shown in practice) and
**PubMed/NCBI E-utilities** (`eutils.ncbi.nlm.nih.gov` - open, rate-limited, the
right choice for biomedical/health topics arXiv and the two Scholar connectors
under-serve).

`$ARGUMENTS` may contain a subcommand, an API name/URL, or nothing.

Follow these steps **in order**.

---

## Step 0: Parse Arguments

- If `$ARGUMENTS` contains `--list`: use Glob with `.agents/skills/*/SKILL.md`, print
  a table of installed connectors (name, data source, auth requirement from each
  `SKILL.md`), and stop.
- If `$ARGUMENTS` contains an API name or URL: treat it as the target and carry it
  into Step 1.
- Otherwise: start the interview at Step 1.

---

## Step 1: Interview - Source Basics

Ask the user (skip anything already answered by `$ARGUMENTS`):

1. **Which database/API?** A name or URL. If they don't have one in mind, offer
   OpenAlex or PubMed/NCBI (above) based on what their `01-researcher-profile.md`
   Research Interests suggest they'd actually use.
2. **Skill name** - kebab-case, suffixed `-search` (e.g. `openalex-search`,
   `pubmed-search`). Must not collide with an existing folder in `.agents/skills/`.
3. **A realistic test query** - a topic the user would actually search for, used for
   the live test in Step 4. Prefer a topic from their tracked Research Interests.

---

## Step 2: Investigate the Source's Actual API

Do reconnaissance before writing any code. Unlike a job portal (usually HTML with no
formal API), an academic source database usually has a real, documented API - find
and read its actual documentation with WebFetch, don't assume a shape from memory or
guess field names from a generic REST convention.

1. **Find the official API documentation.** Search for `"<database name>" API
   documentation`. Read it for: base URL, authentication requirement (none / optional
   key / mandatory key), rate limits (requests per second/hour/day, and whether it's
   per-key or a shared unauthenticated pool - this distinction mattered a great deal
   in practice for `semantic-scholar-search`), and pricing if a key is required
   (`google-scholar-search` needed one for every single request; document the exact
   free-tier limits if any).
2. **Identify the search endpoint and its parameters**: query text, year/date range,
   category/field filters, result limit/pagination, response format (JSON is
   preferred; if the only option is XML like arXiv's, that's fine too - just document
   the parsing approach).
3. **Identify the per-result fields available**: at minimum title, authors, year,
   venue, URL/DOI/id, and (if the API provides it) abstract and citation count. Note
   exactly where each lives in the response shape - do not guess field names.
4. **Identify a detail/lookup-by-id endpoint** if the API has one (fetching a single
   item's full abstract by its id/DOI). Not all APIs have this separately from
   search; if there isn't one, note that `detail` will just re-use `search` with an
   id-based query, and say so plainly in the generated `SKILL.md`.
5. **Decide the access verdict:**
   - **No free or public tier of any kind, and no reasonable individual-researcher
     paid tier** (e.g. institutional-subscription-only APIs with no self-serve
     signup) - **decline**. Tell the user this database isn't a good fit for a
     self-service connector and explain why.
   - **Free tier with rate limits, no key required** (like arXiv, or
     Semantic Scholar's unauthenticated pool) - proceed, document the limits
     prominently.
   - **Requires an account/API key for any access** (like Google Scholar via
     SerpApi) - proceed, but the connector must fail fast with a distinct
     `NO_API_KEY` error pointing at signup rather than attempting a keyless request
     (see the connector contract below) - this is not something to design around
     later, build it in from the start.

Record everything found - base URL, auth model, rate limits, field paths - you will
write it into `SKILL.md` and `helpers.ts`'s header comment in Step 3.

---

## Step 3: Scaffold the Connector

**Canonical reference:** read `.agents/skills/semantic-scholar-search/cli/` before
generating - it's the most complete worked example of this contract (optional API
key, `RATE_LIMITED` handling, defensive parsing with fixture tests). Read
`.agents/skills/arxiv-search/cli/` too if the target API is XML-based rather than
JSON. Copy their architecture and conventions, not their API-specific parsing.

Create `.agents/skills/<name>/` with:

```
<name>/
├── SKILL.md
└── cli/
    ├── package.json
    ├── tsconfig.json
    ├── README.md
    ├── src/
    │   ├── cli.ts          # Arg parsing, help text, command dispatch
    │   ├── helpers.ts      # Fetch with backoff, parsers, error writer, error classes
    │   └── commands/
    │       ├── search.ts
    │       └── detail.ts
    └── tests/
        ├── helpers.ts               # runCLI + parseJSON utilities (copy from an existing connector)
        ├── parsing.test.ts          # fixture-based parsing tests, no live network calls
        └── cli-flag-validation.test.ts  # flag validation + NO_API_KEY path if applicable
```

### The connector-skill contract (every generated connector MUST honor this)

These conventions are what make connectors interchangeable for `/research`, `/rank`,
and `/synthesize`, and what let `/research`'s dynamic-discovery design (it globs
`.agents/skills/*/SKILL.md` - **no separate registration file to edit**, unlike a
job-portal's `search-queries.md`) actually work:

- **Commands:** `search` and `detail <id>` (or `detail <id> --format ...`; if the API
  has no separate detail endpoint, `detail` re-implements the lookup via a
  query-by-id search and says so in `SKILL.md`).
- **Search flags:** `--query`/`-q` (required unless the API supports scope-only
  queries), `--year-from <year>` / `--year-to <year>` if the API supports year
  filtering, `--limit <n>` / `-n <n>` (client-side cap, default 20), `--format
  json|table|plain` (default `json`). Add other filters (category, venue) as the
  target API supports, following existing connectors' flag-naming style.
- **JSON output shape:** `{ "meta": { ... }, "results": [...] }` where each result
  has at minimum `title`, `authors` (or a normalized author array), `year`, `venue`,
  `url` - missing values are `null`, **never fabricated or omitted**. If the API
  provides citation counts, include them (`citedByCount` or similar, matching
  `02-source-evaluation.md`'s Impact dimension needs) - and if a field is
  loosely-structured text rather than a clean field (a Scholar-style "Author - Venue,
  Year - publisher.com" summary string), parse it defensively and return `null`
  rather than a guessed value when it doesn't parse confidently (see
  `google-scholar-search/cli/src/helpers.ts`'s `extractYear`/`extractVenue` for the
  worked example, including the regression test for the bug that pattern was built
  to catch).
- **Errors:** written to **stderr** as `{ "error": "...", "code": "..." }`, exit code
  `1`. Never write errors to stdout. Use distinct error codes so callers can react
  differently:
  - `RATE_LIMITED` - retries exhausted on 429. **Required if the API can rate-limit
    at all.** The error message should say whether the pool is shared/global (like
    Semantic Scholar's) or per-key, and whether setting/upgrading an API key helps.
  - `NO_API_KEY` - required env var is unset, for any connector where auth is
    mandatory. Fail before making any request, not after a 401.
  - `NOT_FOUND` - `detail` found no matching item.
  - `SEARCH_FAILED` / `DETAIL_FAILED` - anything else.
- **Fetching:** exponential backoff with jitter on 429/5xx (4-6 retries), `null` on
  404 rather than a crash - see any existing connector's `jsonFetch`/`atomFetch` for
  the exact pattern to copy.
- **Rate-limit pacing is the *caller's* responsibility, not the CLI's.** A single
  invocation only makes one request, so it's always within any per-request budget on
  its own - `/research`/`/rank`/`/synthesize`'s own guidance is what has to space out
  *sequential* invocations (see `semantic-scholar-search/SKILL.md`'s 1 req/sec note
  for the pattern to follow if the target API documents a similar hard limit).
- **Dependencies:** default to **zero runtime dependencies** (plain `bun` + `fetch`),
  matching all three existing connectors - `bun install` should only pull dev types.

### File specifics

- **`SKILL.md` frontmatter:** `name`, `version: 1.0.0`, a `description` written for
  skill triggering - name the database, what fields/topics it's strong for, and when
  to prefer it over the existing connectors; `context: fork`; `allowed-tools:
  Bash(bun run .agents/skills/<name>/cli/src/cli.ts *)`.
- **`SKILL.md` body:** what the connector searches, the auth/rate-limit situation
  from Step 2 (prominently, following `google-scholar-search/SKILL.md`'s "Requires an
  account" framing if applicable), command reference with flags, 3-5 usage examples,
  output-format table, error-code table, and a Notes section on parsing quirks found
  in Step 2.
- **`package.json`:** name `<name>-cli`, `"type": "module"`, scripts `start`, `test`
  (`bun test --timeout 30000`), `typecheck` (`tsc --noEmit`); **no lifecycle scripts**
  (`security_guards.py` blocks `preinstall`/`install`/`postinstall`/`prepare`/
  `prepack` and `trustedDependencies` - a connector's `package.json` must not need
  any of them).
- **`tests/`:** fixture-based parsing tests using representative response shapes from
  Step 2 (not live calls - CI doesn't have network access to arbitrary APIs, and a
  live-only test suite is what the existing connectors deliberately avoid), plus flag
  validation tests for every pre-network failure path (missing required flag, bad
  numeric arg, `NO_API_KEY` if applicable). Copy `runCLI`/`parseJSON` from an
  existing connector's `tests/helpers.ts`.

---

## Step 4: Test-Run a Live Query (MANDATORY)

Never register a connector that has not returned real results. Documentation and
fixture assumptions from Step 2/3 routinely miss quirks that only show up live - this
step already caught a real venue-parsing bug in `google-scholar-search` (see its
`helpers.ts` and the regression test named after it) that no amount of reading docs
would have found.

1. Install dev types, typecheck, and run the fixture test suite:
   ```bash
   cd .agents/skills/<name>/cli && bun install && bun run typecheck && bun test
   ```
2. Run the live search with the user's test query:
   ```bash
   bun run src/cli.ts search -q "<test query>" --limit 5 --format table
   ```
   If the connector requires an API key the user doesn't have yet, this is as far as
   verification can go - say so explicitly in Step 6, do not claim the connector is
   live-verified when it wasn't (see `google-scholar-search`'s original build for the
   precedent: it shipped typecheck+fixture-verified only, then was live-verified
   later once the user supplied a key).
3. Verify results are real and complete: titles/authors are populated (not empty or
   garbled), URLs resolve, years/venues parse. If fields come back `null` where the
   raw API response clearly has the data, fix the parser and re-run - do not ship a
   parser that silently drops available data.
4. Take one id from the results and run `detail`:
   ```bash
   bun run src/cli.ts detail <id> --format plain
   ```
   Verify the abstract/content is real, readable text - not truncated mid-sentence,
   not HTML entities left undecoded.
5. If the API can rate-limit, deliberately trigger it if practical (or reason from
   the documented limit) and confirm the `RATE_LIMITED` error path actually fires
   with a useful message, not a generic fetch error.

Do not proceed to Step 5 until search, detail, and the fixture test suite all pass -
and until you've been explicit with the user about whether live verification
actually happened or was blocked on a missing key.

---

## Step 5: Register

Unlike a job-portal skill, **no query-list file needs editing** - `/research` and
`/rank` discover connectors dynamically by globbing `.agents/skills/*/SKILL.md`, so
creating the files in Step 3 is the whole of "registration" for those commands. Two
things still need manual wiring:

1. **Add the connector to CI's matrix** in `.github/workflows/ci.yml`'s `cli-checks`
   job (`strategy.matrix.tool`), so its typecheck/fixture-test suite runs on every
   push, same as the other three.
2. **Update `README.md`'s "Source connectors" section** and its file-structure
   listing to mention the new connector, following the existing three entries'
   format (name, what it covers, auth requirement).
3. If the connector needs an API key, mention it in `SETUP.md` alongside the existing
   `SEMANTIC_SCHOLAR_API_KEY`/`SERPAPI_API_KEY` notes.

---

## Step 6: Confirm

Present a summary:

> **Connector `<name>` generated<, live-verified | - typecheck/fixture-verified only, live verification blocked on a missing API key>.**
>
> - Files: `.agents/skills/<name>/` (SKILL.md, CLI with fixture tests)
> - Auth: <none | optional key (env var) | mandatory key (env var), free tier: ...>
> - Rate limits: <summary, and whether `RATE_LIMITED` handling was exercised>
> - Live test: `search "<test query>"` returned <N> results; `detail` verified on one
>   item <or: blocked on missing API key>
>
> Try it: `bun run .agents/skills/<name>/cli/src/cli.ts search -q "<test query>" --format table`
>
> No further wiring needed for `/research`/`/rank` - they'll pick this connector up
> automatically. CI matrix and README updated in Step 5.

---

## Design Principles

- Investigation before scaffolding: Step 2 reads the target API's actual
  documentation, never generates parsers from a guessed generic-REST shape - and
  Step 4 verifies against live data before anything is registered.
- The connector contract keeps every generated connector interchangeable with the
  shipped three: same commands, same flags, same output shape, same error-code
  conventions (including the harder-won ones - `RATE_LIMITED` and `NO_API_KEY` as
  distinct codes - that came from real incidents during this framework's own
  development, not speculative design).
- Zero runtime dependencies by default, matching all three existing connectors.
- Access rules are surfaced, not silently bypassed: no-access-path databases are
  declined outright; mandatory-key databases are built with `NO_API_KEY` handling
  from the start rather than an afterthought; rate limits are documented with their
  actual numbers, not a vague "be considerate."
- Dynamic discovery means registration is nearly free - the real work is Steps 2-4,
  not wiring.
