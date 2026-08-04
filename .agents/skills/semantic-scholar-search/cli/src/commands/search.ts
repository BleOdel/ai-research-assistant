import {
  SEARCH_URL,
  DEFAULT_FIELDS,
  jsonFetch,
  parseSearchResponse,
  buildYearParam,
  writeError,
  RateLimitError,
  type S2Paper,
} from "../helpers.js"

export interface SearchOpts {
  query: string
  yearFrom?: number
  yearTo?: number
  venue?: string
  limit: number
  offset: number
  format: "json" | "table" | "plain"
}

function buildUrl(opts: SearchOpts): string {
  const params = new URLSearchParams({
    query: opts.query,
    fields: DEFAULT_FIELDS,
    limit: String(opts.limit),
    offset: String(opts.offset),
  })
  const year = buildYearParam({ from: opts.yearFrom, to: opts.yearTo })
  if (year) params.set("year", year)
  if (opts.venue) params.set("venue", opts.venue)
  return `${SEARCH_URL}?${params.toString()}`
}

function renderTable(papers: S2Paper[]): string {
  if (papers.length === 0) return "No results."
  const rows = papers.map((p) => {
    const id = p.paperId.slice(0, 12).padEnd(12)
    const title = p.title.slice(0, 46).padEnd(46)
    const year = String(p.year ?? "-").padEnd(5)
    const cites = String(p.citationCount ?? "-")
    return `${id} ${title} ${year} ${cites}`
  })
  const header = "ID".padEnd(12) + " " + "TITLE".padEnd(46) + " YEAR  CITES"
  return [header, "-".repeat(header.length), ...rows].join("\n")
}

function renderPlain(papers: S2Paper[]): string {
  return papers
    .map((p) => {
      const authors = p.authors.map((a) => a.name).join(", ") || "(no authors listed)"
      const venue = p.venue ?? "(no venue - preprint or unlisted)"
      return `${p.title}\n  ${authors}\n  ${venue} · ${p.year ?? "-"} · ${p.citationCount ?? 0} citations\n  id: ${p.paperId}\n  ${p.url ?? "(no url)"}`
    })
    .join("\n\n")
}

export async function runSearch(opts: SearchOpts): Promise<number> {
  try {
    const raw = await jsonFetch(buildUrl(opts))
    const { total, offset, papers } = parseSearchResponse(raw)

    if (opts.format === "table") {
      process.stdout.write(renderTable(papers) + "\n")
    } else if (opts.format === "plain") {
      process.stdout.write((renderPlain(papers) || "No results.") + "\n")
    } else {
      process.stdout.write(
        JSON.stringify({ meta: { total, returned: papers.length, offset }, results: papers }, null, 2) + "\n",
      )
    }
    return 0
  } catch (e) {
    if (e instanceof RateLimitError) {
      writeError(e.message, "RATE_LIMITED")
      return 1
    }
    writeError(e instanceof Error ? e.message : String(e), "SEARCH_FAILED")
    return 1
  }
}
