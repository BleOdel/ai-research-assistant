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

export interface CitedByOpts {
  citesId: string
  limit: number
  start: number
  format: "json" | "table" | "plain"
}

function buildUrl(opts: CitedByOpts, apiKey: string): string {
  const params = new URLSearchParams({
    engine: "google_scholar",
    api_key: apiKey,
    cites: opts.citesId,
    start: String(opts.start),
  })
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

/** `cites` finds papers that cite a given work - the id comes from a prior
 * `search` result's `citedById` field, not from `resultId`. */
export async function runCitedBy(opts: CitedByOpts): Promise<number> {
  try {
    const apiKey = requireApiKey()
    const raw = await jsonFetch(buildUrl(opts, apiKey))
    const { totalResults, results: all } = parseSearchResponse(raw)
    const results = all.slice(0, opts.limit)

    if (opts.format === "table") {
      process.stdout.write(renderTable(results) + "\n")
    } else if (opts.format === "plain") {
      process.stdout.write(
        (results
          .map((r) => `${r.title}\n  ${r.authors.map((a) => a.name).join(", ") || "(authors not parsed)"}\n  ${r.year ?? "-"}\n  ${r.link ?? "(no link)"}`)
          .join("\n\n") || "No results.") + "\n",
      )
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
    writeError(e instanceof Error ? e.message : String(e), "CITED_BY_FAILED")
    return 1
  }
}
