// paper-fetch: resolves a paper identifier (arXiv ID, DOI, or direct URL) to an
// open-access PDF URL and downloads it for full-text reading. This is a utility
// skill, NOT a search connector - it has no `search` command and is skipped by
// /research's connector discovery.
//
// Resolution sources, in order of preference:
// - arXiv IDs go straight to arxiv.org/pdf/<id> - arXiv always serves a PDF for
//   every record, no lookup call needed.
// - DOIs (and OpenAlex work ids) are resolved through OpenAlex's single-work
//   endpoint, which is free regardless of API key (see openalex-search's notes),
//   reading best_oa_location.pdf_url and its fallbacks. If OpenAlex knows no
//   open-access PDF for the work, that is a hard stop (NO_OA_PDF) - this tool
//   never scrapes paywalled publisher sites.
// - Direct URLs are downloaded as-is (the caller already knows where the PDF is).
//
// Every downloaded file is verified to actually start with the %PDF magic bytes
// before being written - a publisher's HTML error page saved as .pdf would
// silently poison the full-text cache.

export const OPENALEX_WORKS_URL = "https://api.openalex.org/works"
export const ARXIV_PDF_BASE = "https://arxiv.org/pdf"

export function writeError(error: string, code: string): void {
  process.stderr.write(JSON.stringify({ error, code }) + "\n")
}

export class RateLimitError extends Error {}
export class NoOpenAccessPdfError extends Error {}
export class NotPdfError extends Error {}

export type IdKind = "arxiv" | "doi" | "openalex" | "url"

export interface ClassifiedId {
  kind: IdKind
  /** Normalized identifier: bare arXiv id (with version if given), bare DOI,
   * bare OpenAlex W-id, or the URL unchanged. */
  value: string
}

// New-style arXiv ids: YYMM.NNNNN with optional vN. Old-style: archive/NNNNNNN
// (e.g. cs/0601001), also with optional vN.
const ARXIV_NEW_RE = /^(\d{4}\.\d{4,5})(v\d+)?$/
const ARXIV_OLD_RE = /^([a-z-]+(?:\.[A-Z]{2})?\/\d{7})(v\d+)?$/
const ARXIV_URL_RE = /^https?:\/\/(?:www\.)?arxiv\.org\/(?:abs|pdf)\/(.+?)(?:\.pdf)?(?:[?#].*)?$/i

/** Classifies an input identifier. Returns null only for empty input - any
 * non-empty string classifies as *something* (unrecognized shapes fall through
 * to "url" only if they look like URLs, otherwise null so the caller can give a
 * real error instead of a garbage request). */
export function classifyId(input: string): ClassifiedId | null {
  const trimmed = input.trim()
  if (trimmed.length === 0) return null

  const arxivUrl = trimmed.match(ARXIV_URL_RE)
  if (arxivUrl) {
    const bare = arxivUrl[1]
    if (ARXIV_NEW_RE.test(bare) || ARXIV_OLD_RE.test(bare)) {
      return { kind: "arxiv", value: bare }
    }
  }
  if (ARXIV_NEW_RE.test(trimmed) || ARXIV_OLD_RE.test(trimmed)) {
    return { kind: "arxiv", value: trimmed }
  }

  const doiUrl = trimmed.match(/^https?:\/\/(?:dx\.)?doi\.org\/(10\..+)$/i)
  if (doiUrl) return { kind: "doi", value: decodeURIComponent(doiUrl[1]) }
  if (/^10\.\d{4,9}\/\S+$/.test(trimmed)) return { kind: "doi", value: trimmed }

  const openalexUrl = trimmed.match(/^https?:\/\/openalex\.org\/(W\d+)$/i)
  if (openalexUrl) return { kind: "openalex", value: openalexUrl[1].toUpperCase() }
  if (/^W\d+$/i.test(trimmed)) return { kind: "openalex", value: trimmed.toUpperCase() }

  if (/^https?:\/\//i.test(trimmed)) return { kind: "url", value: trimmed }
  return null
}

/** arXiv serves the PDF for any id at a stable URL - no API call needed. */
export function arxivPdfUrl(bareId: string): string {
  return `${ARXIV_PDF_BASE}/${bareId}`
}

/** Extracts the best open-access PDF URL from an OpenAlex work record.
 * Preference order: best_oa_location.pdf_url (OpenAlex's own "best" pick),
 * then primary_location.pdf_url, then any other location's pdf_url. A location
 * whose pdf_url is null but oa_url is set is NOT used - oa_url is frequently a
 * landing page, not a PDF, and the magic-byte check would reject it after a
 * wasted download. Returns null (not a guess) when no location has a pdf_url. */
export function extractOaPdfUrl(work: unknown): string | null {
  if (typeof work !== "object" || work === null) return null
  const w = work as Record<string, unknown>

  const pdfUrlOf = (loc: unknown): string | null => {
    if (typeof loc !== "object" || loc === null) return null
    const url = (loc as Record<string, unknown>).pdf_url
    return typeof url === "string" && url.length > 0 ? url : null
  }

  const best = pdfUrlOf(w.best_oa_location)
  if (best) return best
  const primary = pdfUrlOf(w.primary_location)
  if (primary) return primary
  if (Array.isArray(w.locations)) {
    for (const loc of w.locations) {
      const url = pdfUrlOf(loc)
      if (url) return url
    }
  }
  return null
}

/** For works OpenAlex flags open-access but records no direct pdf_url (observed
 * in the wild for a genuinely-OA PLOS ONE paper: is_oa true, landing_page_url
 * set, pdf_url null), returns the OA location's URL as a *candidate* to attempt.
 * The download's magic-byte check is the arbiter: some "landing" URLs serve the
 * PDF directly, and HTML ones fail cleanly without poisoning the cache. Returns
 * null when the work isn't flagged OA at all (genuinely paywalled). */
export function extractOaLandingUrl(work: unknown): string | null {
  if (typeof work !== "object" || work === null) return null
  const w = work as Record<string, unknown>

  const oa = w.open_access
  const isOa = typeof oa === "object" && oa !== null && (oa as Record<string, unknown>).is_oa === true
  if (!isOa) return null

  const urlOf = (loc: unknown): string | null => {
    if (typeof loc !== "object" || loc === null) return null
    const l = loc as Record<string, unknown>
    const oaUrl = l.oa_url
    if (typeof oaUrl === "string" && oaUrl.length > 0) return oaUrl
    const landing = l.landing_page_url
    return typeof landing === "string" && landing.length > 0 ? landing : null
  }

  return urlOf(w.best_oa_location) ?? urlOf(w.primary_location)
}

/** Builds the OpenAlex single-work lookup URL for a DOI or W-id. Single-item
 * lookups are free regardless of API key per OpenAlex's documented per-operation
 * costs, but pass the key/mailto through when set anyway. */
export function openalexWorkUrl(id: ClassifiedId): string {
  const params = new URLSearchParams()
  const apiKey = process.env.OPENALEX_API_KEY
  const mailto = process.env.OPENALEX_MAILTO
  if (apiKey) params.set("api_key", apiKey)
  if (mailto) params.set("mailto", mailto)
  const qs = params.toString()
  const path = id.kind === "doi" ? `https://doi.org/${id.value}` : id.value
  return `${OPENALEX_WORKS_URL}/${path}${qs ? `?${qs}` : ""}`
}

/** Turns an identifier into a filesystem-safe cache filename (without dir). */
export function cacheFilename(id: ClassifiedId): string {
  const sanitize = (s: string): string => s.replace(/[^a-zA-Z0-9.-]+/g, "-").replace(/^-+|-+$/g, "")
  if (id.kind === "arxiv") return `arxiv-${sanitize(id.value)}.pdf`
  if (id.kind === "doi") return `doi-${sanitize(id.value)}.pdf`
  if (id.kind === "openalex") return `openalex-${sanitize(id.value)}.pdf`
  // Direct URL: use the last meaningful path segment, or a hash when the path
  // has nothing usable (e.g. ends in /download or a bare query string).
  try {
    const url = new URL(id.value)
    const segments = url.pathname.split("/").filter((s) => s.length > 0)
    const last = segments[segments.length - 1]
    if (last && last.length > 4) {
      const base = last.toLowerCase().endsWith(".pdf") ? last.slice(0, -4) : last
      return `url-${sanitize(base)}.pdf`
    }
  } catch {
    // fall through to hash
  }
  const hash = Bun.hash(id.value).toString(16).slice(0, 12)
  return `url-${hash}.pdf`
}

/** True if the buffer starts with the %PDF- magic bytes. */
export function looksLikePdf(bytes: Uint8Array): boolean {
  if (bytes.length < 5) return false
  return bytes[0] === 0x25 && bytes[1] === 0x50 && bytes[2] === 0x44 && bytes[3] === 0x46 && bytes[4] === 0x2d
}

/** Fetch JSON with exponential backoff on 429/5xx - same shape as the search
 * connectors' jsonFetch. Returns null on 404. */
export async function jsonFetch(url: string): Promise<unknown> {
  const maxRetries = 4
  let delay = 1500
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    const response = await fetch(url, { headers: { Accept: "application/json" } })
    if (response.status === 429) {
      if (attempt === maxRetries) {
        throw new RateLimitError(
          "OpenAlex's rate limit is exhausted. Do not retry - if this id is an arXiv paper, " +
            "pass the arXiv id directly (no OpenAlex lookup needed); otherwise wait for the " +
            "daily allowance to reset or set OPENALEX_API_KEY.",
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

/** Downloads a URL, following redirects, retrying 429/5xx with backoff, and
 * verifying the payload is actually a PDF before returning it. */
export async function downloadPdf(url: string): Promise<Uint8Array> {
  const maxRetries = 3
  let delay = 2000
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    const response = await fetch(url, {
      headers: { Accept: "application/pdf,*/*" },
      redirect: "follow",
    })
    if (response.status === 429) {
      if (attempt === maxRetries) {
        throw new RateLimitError(
          `Rate-limited downloading ${url}. Do not hand-retry - the built-in backoff is exhausted.`,
        )
      }
      const jitter = Math.floor(Math.random() * 1000)
      await new Promise((r) => setTimeout(r, delay + jitter))
      delay = Math.min(delay * 2, 16000)
      continue
    }
    if (response.status >= 500) {
      if (attempt === maxRetries) {
        throw new Error(`Download failed: ${response.status} ${response.statusText}`)
      }
      const jitter = Math.floor(Math.random() * 1000)
      await new Promise((r) => setTimeout(r, delay + jitter))
      delay = Math.min(delay * 2, 16000)
      continue
    }
    if (!response.ok) {
      throw new Error(`Download failed: ${response.status} ${response.statusText}`)
    }
    const bytes = new Uint8Array(await response.arrayBuffer())
    if (!looksLikePdf(bytes)) {
      throw new NotPdfError(
        `The response from ${url} is not a PDF (missing %PDF magic bytes - likely an HTML ` +
          "landing page or an error page). Nothing was written to the cache.",
      )
    }
    return bytes
  }
  throw new Error("Download failed after max retries")
}
