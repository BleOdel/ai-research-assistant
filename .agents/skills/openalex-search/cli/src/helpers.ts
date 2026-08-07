// Data source: OpenAlex (https://api.openalex.org). No account required to start -
// confirmed empirically (this repo does not have and did not create an OpenAlex
// account): a bare, keyless request against /works returns real, complete results.
// OpenAlex uses a credit-metered daily budget rather than a requests/second cap.
// Measured directly from its own x-ratelimit-* response headers on 2026-08-07:
//
//   unauthenticated   1,000 credits/day  (x-ratelimit-limit-usd 0.10)
//   with a free key  10,000 credits/day  (x-ratelimit-limit-usd 1.00)
//   search           10 credits per call
//   detail (1 work)   1 credit per call
//
// So the practical budgets are ~100 searches/day unauthenticated and ~1,000/day
// with a key - a 10x lift, not the 100x this file previously claimed. A single-work
// lookup is NOT free, but it is 10x cheaper than a search, so preferring `detail`
// over repeated `search` calls still stretches the budget considerably.
// Free key (no payment): https://openalex.org/settings/api
//
// The api_key query-param auth format was originally inferred from OpenAlex's
// query-param-heavy API style and shipped unverified. It is now CONFIRMED
// (2026-08-07): with a real key the limit header rises from 1,000 to 10,000, and a
// deliberately invalid key returns HTTP 401 rather than being ignored.
// https://developers.openalex.org/

export const BASE_URL = "https://api.openalex.org"
export const WORKS_URL = `${BASE_URL}/works`

export function writeError(error: string, code: string): void {
  process.stderr.write(JSON.stringify({ error, code }) + "\n")
}

export class RateLimitError extends Error {}

/** Builds the shared api_key / mailto query params from env vars, if set. Both are
 * optional - OpenAlex works with neither, but a free key raises the daily
 * daily credit budget 10x, from 1,000 to 10,000 (see module header). */
export function authParams(): Record<string, string> {
  const params: Record<string, string> = {}
  const apiKey = process.env.OPENALEX_API_KEY
  const mailto = process.env.OPENALEX_MAILTO
  if (apiKey) params.api_key = apiKey
  if (mailto) params.mailto = mailto
  return params
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
          "OpenAlex's daily credit budget is exhausted. Unauthenticated callers get 1,000 " +
            "credits/day (~100 searches at 10 credits each); an OPENALEX_API_KEY (free, no " +
            "payment required - sign up at https://openalex.org/settings/api) raises this 10x " +
            "to 10,000. Note single-work `detail` lookups cost only 1 credit, so prefer those " +
            "where possible. Do not retry further today - fall back to another connector.",
        )
      }
      const jitter = Math.floor(Math.random() * 750)
      await new Promise((r) => setTimeout(r, delay + jitter))
      delay = Math.min(delay * 2, 12000)
      continue
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
    if (response.status === 404) return null
    if (!response.ok) {
      throw new Error(`Request failed: ${response.status} ${response.statusText}`)
    }
    return response.json()
  }
  throw new Error("Request failed after max retries")
}

export interface OpenAlexAuthor {
  name: string
  authorId: string | null
  orcid: string | null
}

export interface OpenAlexWork {
  id: string
  title: string
  authors: OpenAlexAuthor[]
  year: number | null
  venue: string | null
  citedByCount: number | null
  doi: string | null
  url: string | null
  abstract: string | null
  isOpenAccess: boolean | null
}

/** OpenAlex stores abstracts as an inverted index (word -> list of positions),
 * not plain text, for copyright reasons. Reconstruct the plain text by placing
 * each word at every position it occupies, then joining in position order.
 * Returns null (not a guess) if the field is absent or malformed. */
function reconstructAbstract(invertedIndex: unknown): string | null {
  if (typeof invertedIndex !== "object" || invertedIndex === null) return null
  const entries = Object.entries(invertedIndex as Record<string, unknown>)
  if (entries.length === 0) return null
  const positioned: Array<[number, string]> = []
  for (const [word, positions] of entries) {
    if (!Array.isArray(positions)) continue
    for (const pos of positions) {
      if (typeof pos === "number") positioned.push([pos, word])
    }
  }
  if (positioned.length === 0) return null
  positioned.sort((a, b) => a[0] - b[0])
  return positioned.map(([, word]) => word).join(" ")
}

function extractVenue(primaryLocation: unknown): string | null {
  if (typeof primaryLocation !== "object" || primaryLocation === null) return null
  const loc = primaryLocation as Record<string, unknown>
  const source = loc.source
  if (typeof source === "object" && source !== null) {
    const name = (source as Record<string, unknown>).display_name
    if (typeof name === "string" && name.length > 0) return name
  }
  // OpenAlex sets `source` to null for some records (e.g. Crossref-only entries)
  // even though a human-readable venue name is available under raw_source_name -
  // fall back rather than reporting no venue when one is actually present.
  const raw = loc.raw_source_name
  return typeof raw === "string" && raw.length > 0 ? raw : null
}

function extractDoi(raw: Record<string, unknown>): string | null {
  const doi = raw.doi
  return typeof doi === "string" && doi.length > 0 ? doi : null
}

export function parseOneWork(raw: unknown): OpenAlexWork | null {
  if (typeof raw !== "object" || raw === null) return null
  const r = raw as Record<string, unknown>

  const id = typeof r.id === "string" ? r.id : null
  const title = typeof r.title === "string" ? r.title : typeof r.display_name === "string" ? r.display_name : null
  if (!id || !title) return null

  const authors: OpenAlexAuthor[] = []
  if (Array.isArray(r.authorships)) {
    for (const a of r.authorships) {
      if (typeof a !== "object" || a === null) continue
      const authorship = a as Record<string, unknown>
      const author = authorship.author
      if (typeof author !== "object" || author === null) continue
      const authorRec = author as Record<string, unknown>
      const name = authorRec.display_name
      if (typeof name !== "string") continue
      authors.push({
        name,
        authorId: typeof authorRec.id === "string" ? authorRec.id : null,
        orcid: typeof authorRec.orcid === "string" ? authorRec.orcid : null,
      })
    }
  }

  const doi = extractDoi(r)
  const primaryLocation = r.primary_location
  const url =
    doi ??
    (typeof primaryLocation === "object" && primaryLocation !== null
      ? (() => {
          const landing = (primaryLocation as Record<string, unknown>).landing_page_url
          return typeof landing === "string" ? landing : id
        })()
      : id)

  return {
    id,
    title,
    authors,
    year: typeof r.publication_year === "number" ? r.publication_year : null,
    venue: extractVenue(primaryLocation),
    citedByCount: typeof r.cited_by_count === "number" ? r.cited_by_count : null,
    doi,
    url,
    abstract: reconstructAbstract(r.abstract_inverted_index),
    isOpenAccess:
      typeof r.open_access === "object" && r.open_access !== null
        ? Boolean((r.open_access as Record<string, unknown>).is_oa)
        : null,
  }
}

export function parseSearchResponse(raw: unknown): { totalResults: number | null; results: OpenAlexWork[] } {
  if (typeof raw !== "object" || raw === null) return { totalResults: null, results: [] }
  const r = raw as Record<string, unknown>
  const meta = typeof r.meta === "object" && r.meta !== null ? (r.meta as Record<string, unknown>) : {}
  const totalResults = typeof meta.count === "number" ? meta.count : null

  const items = Array.isArray(r.results) ? r.results : []
  const results: OpenAlexWork[] = []
  for (const item of items) {
    const parsed = parseOneWork(item)
    if (parsed) results.push(parsed)
  }
  return { totalResults, results }
}

/** Accepts a bare OpenAlex work id (W1234567), a full openalex.org URL, or a DOI
 * (bare `10.xxxx/yyyy` or a full doi.org URL) and returns the path segment
 * OpenAlex's /works/<id> endpoint expects. */
export function normalizeWorkId(input: string): string {
  const trimmed = input.trim()
  if (/^https?:\/\/(dx\.)?doi\.org\//i.test(trimmed)) return trimmed
  if (/^10\.\d{4,9}\//.test(trimmed)) return `https://doi.org/${trimmed}`
  if (/^https?:\/\/openalex\.org\/W\d+/i.test(trimmed)) return trimmed
  if (/^W\d+$/i.test(trimmed)) return trimmed
  return trimmed
}
