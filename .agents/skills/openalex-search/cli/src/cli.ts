#!/usr/bin/env bun
// Self-contained CLI for searching OpenAlex (api.openalex.org). No external CLI
// framework, so it runs anywhere `bun` is available with zero install beyond the
// repo clone. No account required to start; see helpers.ts / SKILL.md for the
// optional API key that raises the daily rate limit.

import { runSearch, type SearchOpts } from "./commands/search.js"
import { runDetail, type DetailOpts } from "./commands/detail.js"

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

const HELP = `openalex-cli — search OpenAlex (api.openalex.org)

No account required to start. OpenAlex meters a daily credit budget: 1,000
credits/day unauthenticated (a search costs 10, a single-work "detail" lookup
costs 1 - so ~100 searches/day). An optional OPENALEX_API_KEY (free, no payment
required - sign up at https://openalex.org/settings/api) raises it 10x to 10,000.

USAGE
  bun run src/cli.ts search --query "<text>" [flags]
  bun run src/cli.ts detail <id|doi> [--format json|plain]

SEARCH FLAGS
  --query, -q <text>      Free-text query. Required.
  --year-from <year>      Only results published on or after this year.
  --year-to <year>        Only results published on or before this year.
  --limit, -n <n>         Cap results returned. Default 20 (max 100/request).
  --page <n>              1-indexed page. Default 1.
  --format <fmt>          json (default) | table | plain

DETAIL FLAGS
  <id|doi>                An OpenAlex work id (W1234567), a bare DOI
                          (10.xxxx/yyyy), or a full doi.org/openalex.org URL.
  --format <fmt>          json (default) | plain

EXAMPLES
  bun run src/cli.ts search -q "retrieval augmented generation" --year-from 2022 --limit 15 --format table
  bun run src/cli.ts detail 10.14722/ndss.2024.24100 --format plain
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
    const page = parseIntFlag("page", flags.page, 1)
    if (page === null) return 1
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
      page,
      format: (["json", "table", "plain"].includes(fmt) ? fmt : "json") as SearchOpts["format"],
    }
    return runSearch(opts)
  }

  if (cmd === "detail") {
    const id = (flags._ as string[])[1]
    if (!id) {
      process.stderr.write(JSON.stringify({ error: "detail requires an <id|doi>", code: "NO_ID" }) + "\n")
      return 1
    }
    const fmt = (flags.format as string) || "json"
    const opts: DetailOpts = {
      id,
      format: (fmt === "plain" ? "plain" : "json") as DetailOpts["format"],
    }
    return runDetail(opts)
  }

  process.stderr.write(JSON.stringify({ error: `Unknown command "${cmd}"`, code: "BAD_CMD" }) + "\n")
  return 1
}

main().then((code) => process.exit(code))
