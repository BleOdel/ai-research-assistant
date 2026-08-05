import {
  WORKS_URL,
  jsonFetch,
  parseSearchResponse,
  authParams,
  writeError,
  RateLimitError,
  type OpenAlexWork,
} from "../helpers.js"

export interface SearchOpts {
  query: string
  yearFrom?: number
  yearTo?: number
  limit: number
  page: number
  format: "json" | "table" | "plain"
}

function buildUrl(opts: SearchOpts): string {
  const params = new URLSearchParams({
    search: opts.query,
    "per-page": String(Math.min(opts.limit, 100)),
    page: String(opts.page),
    ...authParams(),
  })
  const filters: string[] = []
  if (opts.yearFrom !== undefined) filters.push(`from_publication_date:${opts.yearFrom}-01-01`)
  if (opts.yearTo !== undefined) filters.push(`to_publication_date:${opts.yearTo}-12-31`)
  if (filters.length > 0) params.set("filter", filters.join(","))
  return `${WORKS_URL}?${params.toString()}`
}

function renderTable(results: OpenAlexWork[]): string {
  if (results.length === 0) return "No results."
  const rows = results.map((r) => {
    const id = r.id.replace("https://openalex.org/", "").padEnd(12)
    const title = r.title.slice(0, 44).padEnd(44)
    const year = String(r.year ?? "-").padEnd(5)
    const cites = String(r.citedByCount ?? "-")
    return `${id} ${title} ${year} ${cites}`
  })
  const header = "ID".padEnd(12) + " " + "TITLE".padEnd(44) + " YEAR  CITES"
  return [header, "-".repeat(header.length), ...rows].join("\n")
}

function renderPlain(results: OpenAlexWork[]): string {
  return results
    .map((r) => {
      const authors = r.authors.map((a) => a.name).join(", ") || "(no authors listed)"
      const venue = r.venue ?? "(no venue indexed)"
      return `${r.title}\n  ${authors}\n  ${venue} · ${r.year ?? "-"} · ${r.citedByCount ?? 0} citations\n  id: ${r.id}\n  ${r.url ?? "(no url)"}`
    })
    .join("\n\n")
}

export async function runSearch(opts: SearchOpts): Promise<number> {
  try {
    const raw = await jsonFetch(buildUrl(opts))
    const { totalResults, results: all } = parseSearchResponse(raw)
    const results = all.slice(0, opts.limit)

    if (opts.format === "table") {
      process.stdout.write(renderTable(results) + "\n")
    } else if (opts.format === "plain") {
      process.stdout.write((renderPlain(results) || "No results.") + "\n")
    } else {
      process.stdout.write(
        JSON.stringify({ meta: { totalResults, returned: results.length, page: opts.page }, results }, null, 2) +
          "\n",
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
