#!/usr/bin/env bun
// Self-contained CLI that resolves a paper identifier (arXiv id, DOI, OpenAlex
// work id, or direct URL) to an open-access PDF and downloads it into the
// repo's full-text cache. NOT a search connector - no `search` command, and
// /research's connector discovery skips it. See SKILL.md.

import { runFetch, type FetchOpts } from "./commands/fetch.js"
import { runResolve, type ResolveOpts } from "./commands/resolve.js"
import { join } from "node:path"

// Default cache dir is <repo-root>/research/fulltext, located from this file's
// own position (src/ -> cli/ -> paper-fetch/ -> skills/ -> .agents/ -> root) so
// the CLI writes to the same place regardless of the caller's CWD.
const DEFAULT_OUT = join(import.meta.dir, "..", "..", "..", "..", "..", "research", "fulltext")

interface Flags {
  _: string[]
  [k: string]: string | boolean | string[]
}

function parseFlags(argv: string[]): Flags {
  const flags: Flags = { _: [] }
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i]
    if (a.startsWith("--") || a.startsWith("-")) {
      const key = a.replace(/^-+/, "")
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

const HELP = `paper-fetch — download open-access paper PDFs for full-text reading

Resolves an arXiv id, DOI, OpenAlex work id, or direct URL to an open-access
PDF and saves it under research/fulltext/ (gitignored). Never scrapes paywalled
publisher sites - a work with no known open-access PDF fails with NO_OA_PDF.

USAGE
  bun run src/cli.ts fetch <id|doi|url> [flags]
  bun run src/cli.ts resolve <id|doi|url> [--format json|plain]

FETCH FLAGS
  <id|doi|url>            arXiv id (2401.12345), DOI (10.xxxx/yyyy), OpenAlex
                          work id (W1234567), or a direct PDF URL. arXiv/DOI/
                          OpenAlex URLs are also accepted.
  --out <dir>             Cache directory. Default: <repo>/research/fulltext
  --force                 Re-download even if the file is already cached.
  --format <fmt>          json (default) | plain

RESOLVE
  Prints the PDF URL the fetch would download, without downloading - use it to
  check whether an open-access PDF exists before committing to the transfer.

EXAMPLES
  bun run src/cli.ts fetch 2401.08998
  bun run src/cli.ts fetch 10.14722/ndss.2024.24100 --format plain
  bun run src/cli.ts resolve https://doi.org/10.1371/journal.pone.0266462
`

async function main(): Promise<number> {
  const argv = process.argv.slice(2)
  const flags = parseFlags(argv)
  const cmd = (flags._ as string[])[0]

  if (!cmd || flags.help || flags.h) {
    process.stdout.write(HELP)
    return cmd ? 0 : 1
  }

  const fmtOf = (raw: string | boolean | string[] | undefined): "json" | "plain" =>
    raw === "plain" ? "plain" : "json"

  if (cmd === "fetch") {
    const id = (flags._ as string[])[1]
    if (!id) {
      process.stderr.write(JSON.stringify({ error: "fetch requires an <id|doi|url>", code: "NO_ID" }) + "\n")
      return 1
    }
    const opts: FetchOpts = {
      id,
      out: typeof flags.out === "string" ? flags.out : DEFAULT_OUT,
      force: flags.force === true,
      format: fmtOf(flags.format),
    }
    return runFetch(opts)
  }

  if (cmd === "resolve") {
    const id = (flags._ as string[])[1]
    if (!id) {
      process.stderr.write(JSON.stringify({ error: "resolve requires an <id|doi|url>", code: "NO_ID" }) + "\n")
      return 1
    }
    const opts: ResolveOpts = { id, format: fmtOf(flags.format) }
    return runResolve(opts)
  }

  process.stderr.write(JSON.stringify({ error: `Unknown command "${cmd}"`, code: "BAD_CMD" }) + "\n")
  return 1
}

main().then((code) => process.exit(code))
