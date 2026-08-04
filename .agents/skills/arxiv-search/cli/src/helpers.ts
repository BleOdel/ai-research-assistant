// Data source: arXiv's public Export API (Atom XML). No authentication required.
// https://info.arxiv.org/help/api/user-manual.html
//
// The feed structure is simple and stable, so we parse it with regex rather than
// pulling in an XML parsing dependency - same rationale as linkedin-search's HTML
// parsing: the markup shape is well documented and shallow enough that a full parser
// is unnecessary overhead.

export const BASE_URL = "http://export.arxiv.org/api/query"

export function writeError(error: string, code: string): void {
  process.stderr.write(JSON.stringify({ error, code }) + "\n")
}

/** Thrown when 429s persist through every retry - callers should treat this as "back
 * off and try another source," not as a bug to retry harder on. */
export class RateLimitError extends Error {}

/** Fetch with exponential backoff on 429/5xx. arXiv's own guidance asks for no more
 * than one request every ~3 seconds and no concurrent connections - firing several
 * differently-worded queries back to back is the most common way to trip this. */
export async function atomFetch(url: string): Promise<string> {
  const maxRetries = 5
  let delay = 1000
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    const response = await fetch(url, {
      headers: { Accept: "application/atom+xml" },
    })
    if (response.status === 429) {
      if (attempt === maxRetries) {
        throw new RateLimitError(
          "arXiv is rate-limiting this client (it asks for roughly one request per 3 seconds, " +
            "no concurrent connections). Space out queries rather than firing several phrasings " +
            "back to back, or fall back to semantic-scholar-search / WebSearch for this query.",
        )
      }
      const jitter = Math.floor(Math.random() * 500)
      await new Promise((r) => setTimeout(r, delay + jitter))
      delay = Math.min(delay * 2, 8000)
      continue
    }
    if (response.status >= 500) {
      if (attempt === maxRetries) {
        throw new Error(`Request failed: ${response.status} ${response.statusText}`)
      }
      const jitter = Math.floor(Math.random() * 500)
      await new Promise((r) => setTimeout(r, delay + jitter))
      delay = Math.min(delay * 2, 8000)
      continue
    }
    if (!response.ok) {
      throw new Error(`Request failed: ${response.status} ${response.statusText}`)
    }
    return response.text()
  }
  throw new Error("Request failed after max retries")
}

function decodeXmlEntities(text: string): string {
  return text
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&apos;/g, "'")
}

function clean(text: string): string {
  return decodeXmlEntities(text).replace(/\s+/g, " ").trim()
}

export interface ArxivPaper {
  id: string // short form, e.g. "2301.12345v2"
  title: string
  summary: string
  authors: string[]
  published: string | null // ISO date
  updated: string | null
  primaryCategory: string | null
  categories: string[]
  comment: string | null
  journalRef: string | null
  doi: string | null
  absUrl: string
  pdfUrl: string | null
}

/** Extract the short arXiv id (e.g. "2301.12345v2") from a full /abs/ URL. */
function shortId(absUrl: string): string {
  const m = absUrl.match(/arxiv\.org\/abs\/(.+)$/)
  return m ? m[1] : absUrl
}

function matchAll(re: RegExp, text: string): string[] {
  const out: string[] = []
  let m: RegExpExecArray | null
  const global = new RegExp(re, re.flags.includes("g") ? re.flags : re.flags + "g")
  while ((m = global.exec(text)) !== null) {
    out.push(m[1])
  }
  return out
}

function parseEntry(chunk: string): ArxivPaper | null {
  const idMatch = chunk.match(/<id>([\s\S]*?)<\/id>/)
  if (!idMatch) return null
  const absUrl = clean(idMatch[1])

  const titleMatch = chunk.match(/<title>([\s\S]*?)<\/title>/)
  const title = titleMatch ? clean(titleMatch[1]) : "(untitled)"

  const summaryMatch = chunk.match(/<summary>([\s\S]*?)<\/summary>/)
  const summary = summaryMatch ? clean(summaryMatch[1]) : ""

  const authors = matchAll(/<author>\s*<name>([\s\S]*?)<\/name>/g, chunk).map(clean)

  const published = chunk.match(/<published>([\s\S]*?)<\/published>/)?.[1] ?? null
  const updated = chunk.match(/<updated>([\s\S]*?)<\/updated>/)?.[1] ?? null

  const primaryCategory =
    chunk.match(/<arxiv:primary_category[^>]*\bterm="([^"]+)"/)?.[1] ?? null
  const categories = matchAll(/<category[^>]*\bterm="([^"]+)"/g, chunk)

  const comment = chunk.match(/<arxiv:comment>([\s\S]*?)<\/arxiv:comment>/)?.[1]
    ? clean(chunk.match(/<arxiv:comment>([\s\S]*?)<\/arxiv:comment>/)![1])
    : null
  const journalRef = chunk.match(/<arxiv:journal_ref>([\s\S]*?)<\/arxiv:journal_ref>/)?.[1]
    ? clean(chunk.match(/<arxiv:journal_ref>([\s\S]*?)<\/arxiv:journal_ref>/)![1])
    : null
  const doi = chunk.match(/<arxiv:doi>([\s\S]*?)<\/arxiv:doi>/)?.[1]
    ? clean(chunk.match(/<arxiv:doi>([\s\S]*?)<\/arxiv:doi>/)![1])
    : null

  const pdfMatch = chunk.match(/<link[^>]*\btitle="pdf"[^>]*\bhref="([^"]+)"/)
  const pdfUrl = pdfMatch ? clean(pdfMatch[1]) : null

  return {
    id: shortId(absUrl),
    title,
    summary,
    authors,
    published,
    updated,
    primaryCategory,
    categories,
    comment,
    journalRef,
    doi,
    absUrl,
    pdfUrl,
  }
}

export interface ParsedFeed {
  totalResults: number
  papers: ArxivPaper[]
}

/** Parse an arXiv Atom feed into structured papers. One malformed entry cannot break the rest. */
export function parseFeed(xml: string): ParsedFeed {
  const totalMatch = xml.match(/<opensearch:totalResults[^>]*>(\d+)<\/opensearch:totalResults>/)
  const totalResults = totalMatch ? parseInt(totalMatch[1], 10) : 0

  const entries = xml.split(/<entry>/).slice(1).map((e) => e.split("</entry>")[0])
  const papers: ArxivPaper[] = []
  for (const chunk of entries) {
    const paper = parseEntry(chunk)
    if (paper) papers.push(paper)
  }
  return { totalResults, papers }
}

/** Escape a raw term for embedding inside an arXiv search_query field. */
function escapeTerm(term: string): string {
  return `"${term.replace(/"/g, '\\"')}"`
}

export interface QueryOpts {
  query?: string
  category?: string
  since?: string // YYYY-MM-DD
}

/** Build the search_query string arXiv's API expects, ANDing the given fields. */
export function buildSearchQuery(opts: QueryOpts): string {
  const clauses: string[] = []
  if (opts.query) clauses.push(`all:${escapeTerm(opts.query)}`)
  if (opts.category) clauses.push(`cat:${opts.category}`)
  if (opts.since) {
    const from = opts.since.replace(/-/g, "") + "0000"
    const to = "99991231" + "2359"
    clauses.push(`submittedDate:[${from}+TO+${to}]`)
  }
  if (clauses.length === 0) {
    throw new Error("At least one of --query, --category, or --since is required")
  }
  return clauses.join("+AND+")
}

/** Normalize a user-supplied id (bare id, versioned id, or /abs/ URL) to arXiv's id_list form. */
export function normalizeId(input: string): string {
  const abs = input.match(/arxiv\.org\/abs\/(.+?)(?:\?|$)/)
  if (abs) return abs[1]
  return input.trim()
}
