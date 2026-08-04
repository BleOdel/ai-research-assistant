// Data source: Google Scholar, via SerpApi's Google Scholar API (SerpApi is a
// third-party proxy - Google Scholar itself has no public API and blocks direct
// scraping). https://serpapi.com/google-scholar-api
//
// Unlike arxiv-search and semantic-scholar-search, EVERY request here requires an
// account and API key - there is no unauthenticated tier at all, only a free tier
// that still needs signup (250 searches/month at the time this was written). Set
// SERPAPI_API_KEY before using this connector.

export const BASE_URL = "https://serpapi.com/search"

export function writeError(error: string, code: string): void {
  process.stderr.write(JSON.stringify({ error, code }) + "\n")
}

export class RateLimitError extends Error {}

/** Thrown when SERPAPI_API_KEY is unset - distinct from a runtime API error so the
 * CLI can point directly at the fix instead of a generic auth failure message. */
export class MissingApiKeyError extends Error {
  constructor() {
    super(
      "SERPAPI_API_KEY is not set. This connector requires a SerpApi account and API " +
        "key for every request (no unauthenticated tier) - sign up for a free key " +
        "(250 searches/month) at https://serpapi.com/users/sign_up, then " +
        'export SERPAPI_API_KEY="your-key".',
    )
  }
}

export function requireApiKey(): string {
  const key = process.env.SERPAPI_API_KEY
  if (!key) throw new MissingApiKeyError()
  return key
}

/** Fetch JSON with exponential backoff on 429/5xx. */
export async function jsonFetch(url: string): Promise<unknown> {
  const maxRetries = 4
  let delay = 1500
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    const response = await fetch(url, { headers: { Accept: "application/json" } })
    if (response.status === 429) {
      if (attempt === maxRetries) {
        throw new RateLimitError(
          "SerpApi is rate-limiting this key (throughput cap, e.g. 50/hour on the free " +
            "tier). Do not retry further - space out queries or fall back to " +
            "arxiv-search / semantic-scholar-search / WebSearch for this query.",
        )
      }
      const jitter = Math.floor(Math.random() * 750)
      await new Promise((r) => setTimeout(r, delay + jitter))
      delay = Math.min(delay * 2, 12000)
      continue
    }
    if (response.status === 401 || response.status === 403) {
      const body = await response.text()
      throw new Error(`SerpApi rejected the request (${response.status}): ${body.slice(0, 300)}`)
    }
    if (response.status >= 500) {
      if (attempt === maxRetries) {
        throw new Error(`Request failed: ${response.status} ${response.statusText}`)
      }
      const jitter = Math.floor(Math.random() * 750)
      await new Promise((r) => setTimeout(r, delay + jitter))
      delay = Math.min(delay * 2, 12000)
      continue
    }
    if (!response.ok) {
      throw new Error(`Request failed: ${response.status} ${response.statusText}`)
    }
    return response.json()
  }
  throw new Error("Request failed after max retries")
}

export interface ScholarAuthor {
  name: string
  authorId: string | null
}

export interface ScholarResult {
  resultId: string
  title: string
  link: string | null
  snippet: string | null
  authors: ScholarAuthor[]
  year: number | null
  venue: string | null
  citedByCount: number | null
  citedById: string | null
  pdfUrl: string | null
}

/** Extract a plausible publication year (1900-2100) from Scholar's loosely
 * structured "A Author, B Author - Venue, 2020 - publisher.com" summary string.
 * Returns null rather than guessing when no confident year is present. */
function extractYear(summary: string): number | null {
  const matches = summary.match(/\b(19|20)\d{2}\b/g)
  if (!matches || matches.length === 0) return null
  const year = parseInt(matches[matches.length - 1], 10)
  return year >= 1900 && year <= 2100 ? year : null
}

/** Best-effort venue extraction: the middle " - "-delimited segment, with the
 * year token stripped out. Returns null if the segment is empty or looks like
 * just a bare year (no venue name at all - common for some preprints). */
function extractVenue(summary: string, year: number | null): string | null {
  const segments = summary.split(" - ")
  if (segments.length < 2) return null
  const middle = segments[1]
  const withoutYear = year ? middle.replace(String(year), "").replace(/,\s*,/g, ",") : middle
  const cleaned = withoutYear.replace(/^,\s*|,\s*$/g, "").trim()
  return cleaned.length > 0 ? cleaned : null
}

function parseOneResult(raw: unknown): ScholarResult | null {
  if (typeof raw !== "object" || raw === null) return null
  const r = raw as Record<string, unknown>
  const resultId = typeof r.result_id === "string" ? r.result_id : null
  const title = typeof r.title === "string" ? r.title : null
  if (!resultId || !title) return null

  const pubInfo = (typeof r.publication_info === "object" && r.publication_info !== null
    ? (r.publication_info as Record<string, unknown>)
    : {}) as Record<string, unknown>
  const summary = typeof pubInfo.summary === "string" ? pubInfo.summary : ""
  const year = summary ? extractYear(summary) : null
  const venue = summary ? extractVenue(summary, year) : null

  const authors: ScholarAuthor[] = []
  if (Array.isArray(pubInfo.authors)) {
    for (const a of pubInfo.authors) {
      if (typeof a === "object" && a !== null && typeof (a as Record<string, unknown>).name === "string") {
        const rec = a as Record<string, unknown>
        authors.push({
          name: rec.name as string,
          authorId: typeof rec.author_id === "string" ? rec.author_id : null,
        })
      }
    }
  }

  const inlineLinks = (typeof r.inline_links === "object" && r.inline_links !== null
    ? (r.inline_links as Record<string, unknown>)
    : {}) as Record<string, unknown>
  const citedBy = (typeof inlineLinks.cited_by === "object" && inlineLinks.cited_by !== null
    ? (inlineLinks.cited_by as Record<string, unknown>)
    : {}) as Record<string, unknown>
  const citedByCount = typeof citedBy.total === "number" ? citedBy.total : null
  const citedById = typeof citedBy.cites_id === "string" ? citedBy.cites_id : null

  let pdfUrl: string | null = null
  if (Array.isArray(r.resources)) {
    for (const res of r.resources) {
      if (typeof res === "object" && res !== null) {
        const rec = res as Record<string, unknown>
        if (rec.file_format === "PDF" && typeof rec.link === "string") {
          pdfUrl = rec.link
          break
        }
      }
    }
  }

  return {
    resultId,
    title,
    link: typeof r.link === "string" ? r.link : null,
    snippet: typeof r.snippet === "string" ? r.snippet : null,
    authors,
    year,
    venue,
    citedByCount,
    citedById,
    pdfUrl,
  }
}

export function parseSearchResponse(raw: unknown): { totalResults: number | null; results: ScholarResult[] } {
  if (typeof raw !== "object" || raw === null) return { totalResults: null, results: [] }
  const r = raw as Record<string, unknown>

  const searchInfo = (typeof r.search_information === "object" && r.search_information !== null
    ? (r.search_information as Record<string, unknown>)
    : {}) as Record<string, unknown>
  const totalResults = typeof searchInfo.total_results === "number" ? searchInfo.total_results : null

  const organic = Array.isArray(r.organic_results) ? r.organic_results : []
  const results: ScholarResult[] = []
  for (const item of organic) {
    const parsed = parseOneResult(item)
    if (parsed) results.push(parsed)
  }
  return { totalResults, results }
}
