import { BASE_URL, atomFetch, parseFeed, buildSearchQuery, writeError, type ArxivPaper } from "../helpers.js"

export interface SearchOpts {
  query?: string
  category?: string
  since?: string
  sort: "relevance" | "date"
  limit: number
  start: number
  format: "json" | "table" | "plain"
}

function buildUrl(opts: SearchOpts): string {
  const searchQuery = buildSearchQuery({ query: opts.query, category: opts.category, since: opts.since })
  const params = new URLSearchParams({
    search_query: searchQuery,
    start: String(opts.start),
    max_results: String(opts.limit),
    sortBy: opts.sort === "date" ? "submittedDate" : "relevance",
    sortOrder: "descending",
  })
  return `${BASE_URL}?${params.toString()}`
}

function renderTable(papers: ArxivPaper[]): string {
  if (papers.length === 0) return "No results."
  const rows = papers.map((p) => {
    const id = p.id.padEnd(16)
    const title = p.title.slice(0, 50).padEnd(50)
    const year = (p.published ?? "").slice(0, 4)
    const cat = p.primaryCategory ?? "-"
    return `${id} ${title} ${year}  ${cat}`
  })
  const header = "ID".padEnd(16) + " " + "TITLE".padEnd(50) + " YEAR  CATEGORY"
  return [header, "-".repeat(header.length), ...rows].join("\n")
}

function renderPlain(papers: ArxivPaper[]): string {
  return papers
    .map(
      (p) =>
        `${p.title}\n  ${p.authors.join(", ") || "(no authors listed)"}\n  ${p.primaryCategory ?? "-"} · ${(p.published ?? "-").slice(0, 10)}\n  id: ${p.id}\n  ${p.absUrl}`,
    )
    .join("\n\n")
}

export async function runSearch(opts: SearchOpts): Promise<number> {
  try {
    const xml = await atomFetch(buildUrl(opts))
    const { totalResults, papers } = parseFeed(xml)

    if (opts.format === "table") {
      process.stdout.write(renderTable(papers) + "\n")
    } else if (opts.format === "plain") {
      process.stdout.write((renderPlain(papers) || "No results.") + "\n")
    } else {
      process.stdout.write(
        JSON.stringify(
          { meta: { totalResults, returned: papers.length, start: opts.start }, results: papers },
          null,
          2,
        ) + "\n",
      )
    }
    return 0
  } catch (e) {
    writeError(e instanceof Error ? e.message : String(e), "SEARCH_FAILED")
    return 1
  }
}
