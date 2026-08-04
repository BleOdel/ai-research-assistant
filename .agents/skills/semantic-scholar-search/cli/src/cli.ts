#!/usr/bin/env bun
// Self-contained CLI for searching Semantic Scholar's public Graph API. No external
// CLI framework, so it runs anywhere `bun` is available with zero install beyond the
// repo clone. No authentication required, but the unauthenticated pool is tightly
// rate-limited - keep query volume reasonable.

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

const HELP = `semantic-scholar-cli — search papers on Semantic Scholar (public Graph API, no auth)

USAGE
  bun run src/cli.ts search --query "<text>" [flags]
  bun run src/cli.ts detail <id> [--format json|plain]

SEARCH FLAGS
  --query, -q <text>       Free-text query. REQUIRED.
  --year-from <year>       Only papers published in or after this year.
  --year-to <year>         Only papers published in or before this year.
  --venue <name>           Filter by venue name (exact match per S2's API).
  --limit, -n <n>          Max results to return. Default 20 (S2 caps at 100/request).
  --offset <n>             Result offset for pagination. Default 0.
  --format <fmt>           json (default) | table | plain

DETAIL FLAGS
  <id>                     Semantic Scholar paper id, or a prefixed external id:
                            "arxiv:2301.12345", "doi:10.1234/x", "pubmed:12345".
  --format <fmt>           json (default) | plain

EXAMPLES
  bun run src/cli.ts search -q "retrieval augmented generation" --year-from 2023 --limit 15 --format table
  bun run src/cli.ts search -q "graph neural networks" --venue "NeurIPS" --format table
  bun run src/cli.ts detail arxiv:2301.12345 --format plain

Unauthenticated Semantic Scholar traffic is rate-limited to a small shared pool.
The CLI retries 429/5xx with exponential backoff - keep batch sizes reasonable.
`

async function main(): Promise<number> {
  const argv = process.argv.slice(2)
  const flags = parseFlags(argv)
  const cmd = (flags._ as string[])[0]

  if (!cmd || flags.help || flags.h) {
    process.stdout.write(HELP)
    return cmd ? 0 : 1
  }

  if (cmd === "search") {
    const query = typeof flags.query === "string" ? flags.query : undefined
    if (!query) {
      process.stderr.write(JSON.stringify({ error: "--query/-q is required", code: "NO_QUERY" }) + "\n")
      return 1
    }
    const fmt = (flags.format as string) || "json"

    const parseIntFlag = (name: string, raw: string | boolean | string[] | undefined, fallback: number): number | null => {
      if (raw === undefined) return fallback
      const val = parseInt(raw as string, 10)
      if (isNaN(val)) {
        process.stderr.write(JSON.stringify({ error: `--${name} must be a number, got "${raw}"`, code: "BAD_ARG" }) + "\n")
        return null
      }
      return val
    }

    const limit = parseIntFlag("limit", flags.limit, 20)
    if (limit === null) return 1
    const offset = parseIntFlag("offset", flags.offset, 0)
    if (offset === null) return 1

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
      query,
      yearFrom,
      yearTo,
      venue: typeof flags.venue === "string" ? flags.venue : undefined,
      limit,
      offset,
      format: (["json", "table", "plain"].includes(fmt) ? fmt : "json") as SearchOpts["format"],
    }
    return runSearch(opts)
  }

  if (cmd === "detail") {
    const id = (flags._ as string[])[1]
    if (!id) {
      process.stderr.write(JSON.stringify({ error: "detail requires an <id>", code: "NO_ID" }) + "\n")
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
