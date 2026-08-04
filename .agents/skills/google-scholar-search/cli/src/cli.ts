#!/usr/bin/env bun
// Self-contained CLI for searching Google Scholar via SerpApi. No external CLI
// framework, so it runs anywhere `bun` is available with zero install beyond the
// repo clone - but every request requires SERPAPI_API_KEY (no unauthenticated
// tier at all). See helpers.ts / SKILL.md for setup.

import { runSearch, type SearchOpts } from "./commands/search.js"
import { runCitedBy, type CitedByOpts } from "./commands/cited-by.js"

interface Flags {
  _: string[]
  [k: string]: string | boolean | string[]
}

function parseFlags(argv: string[]): Flags {
  const flags: Flags = { _: [] }
  const alias: Record<string, string> = { q: "query", n: "limit" }
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i]
    if (a.startsWith("--") || a.startsWith("-")) {
      const key = alias[a.replace(/^-+/, "")] ?? a.replace(/^-+/, "")
      const next = argv[i + 1]
      if (next === undefined || next.startsWith("-")) {
        flags[key] = true
      } else {
        flags[key] = next
        i++
      }
    } else {
      ;(flags._ as string[]).push(a)
    }
  }
  return flags
}

const HELP = `google-scholar-cli — search Google Scholar via SerpApi

Requires SERPAPI_API_KEY (free tier: 250 searches/month, sign up at
https://serpapi.com/users/sign_up). No unauthenticated tier exists.

USAGE
  bun run src/cli.ts search --query "<text>" [flags]
  bun run src/cli.ts cited-by <cites-id> [flags]

SEARCH FLAGS
  --query, -q <text>      Free-text query. Required.
  --year-from <year>      Only results published on or after this year.
  --year-to <year>        Only results published on or before this year.
  --limit, -n <n>         Cap results returned (client-side). Default 20.
  --start <n>             Result offset for pagination. Default 0.
  --format <fmt>          json (default) | table | plain

CITED-BY FLAGS
  <cites-id>              A search result's citedById field (NOT its resultId) -
                            lists papers that cite that work.
  --limit, -n <n>         Cap results returned. Default 20.
  --start <n>             Result offset. Default 0.
  --format <fmt>          json (default) | table | plain

EXAMPLES
  bun run src/cli.ts search -q "retrieval augmented generation" --year-from 2022 --limit 15 --format table
  bun run src/cli.ts cited-by uNijGkgAAAAJ:abc123 --format table
`

async function main(): Promise<number> {
  const argv = process.argv.slice(2)
  const flags = parseFlags(argv)
  const cmd = (flags._ as string[])[0]

  if (!cmd || flags.help || flags.h) {
    process.stdout.write(HELP)
    return cmd ? 0 : 1
  }

  const parseIntFlag = (name: string, raw: string | boolean | string[] | undefined, fallback: number): number | null => {
    if (raw === undefined) return fallback
    const val = parseInt(raw as string, 10)
    if (isNaN(val)) {
      process.stderr.write(JSON.stringify({ error: `--${name} must be a number, got "${raw}"`, code: "BAD_ARG" }) + "\n")
      return null
    }
    return val
  }

  if (cmd === "search") {
    const fmt = (flags.format as string) || "json"
    if (!flags.query) {
      process.stderr.write(JSON.stringify({ error: "--query/-q is required", code: "NO_QUERY" }) + "\n")
      return 1
    }

    const limit = parseIntFlag("limit", flags.limit, 20)
    if (limit === null) return 1
    const start = parseIntFlag("start", flags.start, 0)
    if (start === null) return 1
    let yearFrom: number | undefined
    if (flags["year-from"] !== undefined) {
      const v = parseIntFlag("year-from", flags["year-from"], 0)
      if (v === null) return 1
      yearFrom = v
    }
    let yearTo: number | undefined
    if (flags["year-to"] !== undefined) {
      const v = parseIntFlag("year-to", flags["year-to"], 0)
      if (v === null) return 1
      yearTo = v
    }

    const opts: SearchOpts = {
      query: flags.query as string,
      yearFrom,
      yearTo,
      limit,
      start,
      format: (["json", "table", "plain"].includes(fmt) ? fmt : "json") as SearchOpts["format"],
    }
    return runSearch(opts)
  }

  if (cmd === "cited-by") {
    const citesId = (flags._ as string[])[1]
    if (!citesId) {
      process.stderr.write(JSON.stringify({ error: "cited-by requires a <cites-id>", code: "NO_ID" }) + "\n")
      return 1
    }
    const fmt = (flags.format as string) || "json"
    const limit = parseIntFlag("limit", flags.limit, 20)
    if (limit === null) return 1
    const start = parseIntFlag("start", flags.start, 0)
    if (start === null) return 1

    const opts: CitedByOpts = {
      citesId,
      limit,
      start,
      format: (["json", "table", "plain"].includes(fmt) ? fmt : "json") as CitedByOpts["format"],
    }
    return runCitedBy(opts)
  }

  process.stderr.write(JSON.stringify({ error: `Unknown command "${cmd}"`, code: "BAD_CMD" }) + "\n")
  return 1
}

main().then((code) => process.exit(code))
