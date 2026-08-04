// Data source: Semantic Scholar's public Graph API. No authentication required for
// unauthenticated use, but the shared unauthenticated pool is tightly rate-limited -
// this module backs off aggressively on 429 rather than retrying fast.
// https://api.semanticscholar.org/api-docs/graph

export const BASE_URL = "https://api.semanticscholar.org/graph/v1"
export const SEARCH_URL = `${BASE_URL}/paper/search`
export const DETAIL_URL = `${BASE_URL}/paper`

export const DEFAULT_FIELDS =
  "title,abstract,year,venue,citationCount,influentialCitationCount,authors,externalIds,url"

export function writeError(error: string, code: string): void {
  process.stderr.write(JSON.stringify({ error, code }) + "\n")
}

/** Fetch JSON with exponential backoff on 429/5xx. Unauthenticated S2 traffic is rate-limited, so backoff starts slow. */
export async function jsonFetch(url: string): Promise<unknown> {
  const maxRetries = 5
  let delay = 2000
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    const response = await fetch(url, {
      headers: { Accept: "application/json" },
    })
    if (response.status === 429 || response.status >= 500) {
      if (attempt === maxRetries) {
        throw new Error(`Request failed: ${response.status} ${response.statusText}`)
      }
      const jitter = Math.floor(Math.random() * 1000)
      await new Promise((r) => setTimeout(r, delay + jitter))
      delay = Math.min(delay * 2, 16000)
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

export interface S2Author {
  authorId: string | null
  name: string
}

export interface S2ExternalIds {
  DOI?: string
  ArXiv?: string
  PubMed?: string
  [key: string]: string | undefined
}

export interface S2Paper {
  paperId: string
  title: string
  abstract: string | null
  year: number | null
  venue: string | null
  citationCount: number | null
  influentialCitationCount: number | null
  authors: S2Author[]
  externalIds: S2ExternalIds
  url: string | null
}

interface RawSearchResponse {
  total: number
  offset: number
  next?: number
  data?: unknown[]
}

function coercePaper(raw: unknown): S2Paper | null {
  if (!raw || typeof raw !== "object") return null
  const r = raw as Record<string, unknown>
  if (typeof r.paperId !== "string" || typeof r.title !== "string") return null
  return {
    paperId: r.paperId,
    title: r.title,
    abstract: typeof r.abstract === "string" ? r.abstract : null,
    year: typeof r.year === "number" ? r.year : null,
    venue: typeof r.venue === "string" && r.venue.length > 0 ? r.venue : null,
    citationCount: typeof r.citationCount === "number" ? r.citationCount : null,
    influentialCitationCount:
      typeof r.influentialCitationCount === "number" ? r.influentialCitationCount : null,
    authors: Array.isArray(r.authors)
      ? (r.authors as unknown[])
          .filter((a): a is Record<string, unknown> => !!a && typeof a === "object")
          .map((a) => ({
            authorId: typeof a.authorId === "string" ? a.authorId : null,
            name: typeof a.name === "string" ? a.name : "(unknown)",
          }))
      : [],
    externalIds:
      r.externalIds && typeof r.externalIds === "object"
        ? (r.externalIds as S2ExternalIds)
        : {},
    url: typeof r.url === "string" ? r.url : null,
  }
}

export interface ParsedSearch {
  total: number
  offset: number
  papers: S2Paper[]
}

/** Parse a /paper/search response. Entries that don't match the expected shape are skipped, not fabricated. */
export function parseSearchResponse(raw: unknown): ParsedSearch {
  if (!raw || typeof raw !== "object") return { total: 0, offset: 0, papers: [] }
  const r = raw as RawSearchResponse
  const papers = (r.data ?? []).map(coercePaper).filter((p): p is S2Paper => p !== null)
  return { total: r.total ?? papers.length, offset: r.offset ?? 0, papers }
}

/** Parse a single /paper/{id} response. Returns null if the shape is unrecognized. */
export function parsePaperResponse(raw: unknown): S2Paper | null {
  return coercePaper(raw)
}

/** Accept a bare S2 paper id, or a prefixed external id like "arxiv:2301.12345" or "doi:10.1234/x". */
export function normalizeId(input: string): string {
  const trimmed = input.trim()
  const prefixMatch = trimmed.match(/^(arxiv|doi|pubmed|mag|acl|corpusid)\s*:\s*(.+)$/i)
  if (prefixMatch) {
    return `${prefixMatch[1].toUpperCase()}:${prefixMatch[2]}`
  }
  return trimmed
}

export interface YearRange {
  from?: number
  to?: number
}

/** Build the S2 `year` query param from a from/to pair (S2 accepts "2020", "2020-2024", "2020-", "-2024"). */
export function buildYearParam(range: YearRange): string | null {
  if (range.from === undefined && range.to === undefined) return null
  if (range.from !== undefined && range.to !== undefined) return `${range.from}-${range.to}`
  if (range.from !== undefined) return `${range.from}-`
  return `-${range.to}`
}
