import { BASE_URL, atomFetch, parseFeed, normalizeId, writeError, RateLimitError } from "../helpers.js"

export interface DetailOpts {
  id: string
  format: "json" | "plain"
}

export async function runDetail(opts: DetailOpts): Promise<number> {
  const id = normalizeId(opts.id)
  try {
    const params = new URLSearchParams({ id_list: id, max_results: "1" })
    const xml = await atomFetch(`${BASE_URL}?${params.toString()}`)
    const { papers } = parseFeed(xml)
    const paper = papers[0]

    if (!paper) {
      writeError(`No paper found for id "${id}"`, "NOT_FOUND")
      return 1
    }

    if (opts.format === "plain") {
      const lines = [
        paper.title,
        paper.authors.join(", ") || "(no authors listed)",
        `${paper.primaryCategory ?? "-"} · published ${(paper.published ?? "-").slice(0, 10)} · updated ${(paper.updated ?? "-").slice(0, 10)}`,
        "",
        paper.summary || "(no abstract)",
        "",
        paper.comment ? `Comment: ${paper.comment}` : "",
        paper.journalRef ? `Journal ref: ${paper.journalRef}` : "",
        paper.doi ? `DOI: ${paper.doi}` : "",
        `Categories: ${paper.categories.join(", ")}`,
        `Abstract page: ${paper.absUrl}`,
        paper.pdfUrl ? `PDF: ${paper.pdfUrl}` : "",
      ].filter((l) => l !== "")
      process.stdout.write(lines.join("\n") + "\n")
    } else {
      process.stdout.write(JSON.stringify(paper, null, 2) + "\n")
    }
    return 0
  } catch (e) {
    if (e instanceof RateLimitError) {
      writeError(e.message, "RATE_LIMITED")
      return 1
    }
    writeError(e instanceof Error ? e.message : String(e), "DETAIL_FAILED")
    return 1
  }
}
