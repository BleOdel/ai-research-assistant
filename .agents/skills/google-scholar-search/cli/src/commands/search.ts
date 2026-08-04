import {
  BASE_URL,
  jsonFetch,
  parseSearchResponse,
  requireApiKey,
  writeError,
  RateLimitError,
  MissingApiKeyError,
  type ScholarResult,
} from "../helpers.js"

export interface SearchOpts {
  query: string
  yearFrom?: number
  yearTo?: number
  limit: number
  start: number
  format: "json" | "table" | "plain"
}

function buildUrl(opts: SearchOpts, apiKey: string): string {
  const params = new URLSearchParams({
    engine: "google_scholar",
    api_key: apiKey,
    q: opts.query,
    start: String(opts.start),
  })
  if (opts.yearFrom !== undefined) params.set("as_ylo", String(opts.yearFrom))
  if (opts.yearTo !== undefined) params.set("as_yhi", String(opts.yearTo))
  return `${BASE_URL}?${params.toString()}`
}

function renderTable(results: ScholarResult[]): string {
  if (results.length === 0) return "No results."
  const rows = results.map((r) => {
    const id = r.resultId.slice(0, 14).padEnd(14)
    const title = r.title.slice(0, 44).padEnd(44)
    const year = String(r.year ?? "-").padEnd(5)
    const cites = String(r.citedByCount ?? "-")
    return `${id} ${title} ${year} ${cites}`
  })
  const header = "ID".padEnd(14) + " " + "TITLE".padEnd(44) + " YEAR  CITES"
  return [header, "-".repeat(header.length), ...rows].join("\n")
}

function renderPlain(results: ScholarResult[]): string {
  return results
    .map((r) => {
      const authors = r.authors.map((a) => a.name).join(", ") || "(authors not parsed)"
      const venue = r.venue ?? "(no venue parsed)"
      return `${r.title}\n  ${authors}\n  ${venue} · ${r.year ?? "-"} · ${r.citedByCount ?? 0} citations\n  id: ${r.resultId}\n  ${r.link ?? "(no link)"}`
    })
    .join("\n\n")
}

export async function runSearch(opts: SearchOpts): Promise<number> {
  try {
    const apiKey = requireApiKey()
    const raw = await jsonFetch(buildUrl(opts, apiKey))
    const { totalResults, results: all } = parseSearchResponse(raw)
    const results = all.slice(0, opts.limit)

    if (opts.format === "table") {
      process.stdout.write(renderTable(results) + "\n")
    } else if (opts.format === "plain") {
      process.stdout.write((renderPlain(results) || "No results.") + "\n")
    } else {
      process.stdout.write(
        JSON.stringify({ meta: { totalResults, returned: results.length, start: opts.start }, results }, null, 2) +
          "\n",
      )
    }
    return 0
  } catch (e) {
    if (e instanceof MissingApiKeyError) {
      writeError(e.message, "NO_API_KEY")
      return 1
    }
    if (e instanceof RateLimitError) {
      writeError(e.message, "RATE_LIMITED")
      return 1
    }
    writeError(e instanceof Error ? e.message : String(e), "SEARCH_FAILED")
    return 1
  }
}
