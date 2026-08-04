#!/usr/bin/env bun
// Self-contained CLI for searching arXiv's public Export API. No external CLI
// framework, so it runs anywhere `bun` is available with zero install beyond the
// repo clone. No authentication, no API key.

import { runSearch, type SearchOpts } from "./commands/search.js"
import { runDetail, type DetailOpts } from "./commands/detail.js"

interface Flags {
  _: string[]
  [k: string]: string | boolean | string[]
}

function parseFlags(argv: string[]): Flags {
  const flags: Flags = { _: [] }
  const alias: Record<string, string> = { q: "query", c: "category", n: "limit" }
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

const HELP = `arxiv-cli — search papers on arXiv (public Export API, no auth)

USAGE
  bun run src/cli.ts search [flags]
  bun run src/cli.ts detail <id|abs-url> [--format json|plain]

SEARCH FLAGS
  --query, -q <text>      Free-text query (matches title/abstract/authors/etc).
  --category, -c <code>   arXiv category, e.g. cs.LG, cs.CL, stat.ML.
  --since <YYYY-MM-DD>     Only papers submitted on or after this date.
  --sort <mode>            relevance (default) | date
  --limit, -n <n>          Max results to return. Default 20.
  --start <n>              Result offset for pagination. Default 0.
  --format <fmt>           json (default) | table | plain

  At least one of --query, --category, or --since is required.

DETAIL FLAGS
  <id|abs-url>             arXiv id (e.g. 2301.12345 or 2301.12345v2) or a full
                            arxiv.org/abs/... URL.
  --format <fmt>            json (default) | plain

EXAMPLES
  bun run src/cli.ts search -q "retrieval augmented generation" -c cs.CL --limit 15 --format table
  bun run src/cli.ts search -c cs.LG --since 2024-01-01 --sort date --format table
  bun run src/cli.ts detail 2301.12345 --format plain
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
    const fmt = (flags.format as string) || "json"
    const sortRaw = (flags.sort as string) || "relevance"

    const parseIntFlag = (name: string, raw: string | boolean | string[], fallback: number): number | null => {
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
    const start = parseIntFlag("start", flags.start, 0)
    if (start === null) return 1

    const opts: SearchOpts = {
      query: typeof flags.query === "string" ? flags.query : undefined,
      category: typeof flags.category === "string" ? flags.category : undefined,
      since: typeof flags.since === "string" ? flags.since : undefined,
      sort: sortRaw === "date" ? "date" : "relevance",
      limit,
      start,
      format: (["json", "table", "plain"].includes(fmt) ? fmt : "json") as SearchOpts["format"],
    }

    if (!opts.query && !opts.category && !opts.since) {
      process.stderr.write(
        JSON.stringify({
          error: "At least one of --query, --category, or --since is required",
          code: "NO_CRITERIA",
        }) + "\n",
      )
      return 1
    }

    return runSearch(opts)
  }

  if (cmd === "detail") {
    const id = (flags._ as string[])[1]
    if (!id) {
      process.stderr.write(JSON.stringify({ error: "detail requires an <id|abs-url>", code: "NO_ID" }) + "\n")
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
