import { DETAIL_URL, DEFAULT_FIELDS, jsonFetch, parsePaperResponse, normalizeId, writeError } from "../helpers.js"

export interface DetailOpts {
  id: string
  format: "json" | "plain"
}

export async function runDetail(opts: DetailOpts): Promise<number> {
  const id = normalizeId(opts.id)
  try {
    const params = new URLSearchParams({ fields: DEFAULT_FIELDS })
    const raw = await jsonFetch(`${DETAIL_URL}/${encodeURIComponent(id)}?${params.toString()}`)
    const paper = parsePaperResponse(raw)

    if (!paper) {
      writeError(`No paper found for id "${id}"`, "NOT_FOUND")
      return 1
    }

    if (opts.format === "plain") {
      const authors = paper.authors.map((a) => a.name).join(", ") || "(no authors listed)"
      const lines = [
        paper.title,
        authors,
        `${paper.venue ?? "(no venue - preprint or unlisted)"} · ${paper.year ?? "-"} · ${paper.citationCount ?? 0} citations (${paper.influentialCitationCount ?? 0} influential)`,
        "",
        paper.abstract || "(no abstract)",
        "",
        paper.externalIds.DOI ? `DOI: ${paper.externalIds.DOI}` : "",
        paper.externalIds.ArXiv ? `arXiv: ${paper.externalIds.ArXiv}` : "",
        `Semantic Scholar id: ${paper.paperId}`,
        paper.url ? `URL: ${paper.url}` : "",
      ].filter((l) => l !== "")
      process.stdout.write(lines.join("\n") + "\n")
    } else {
      process.stdout.write(JSON.stringify(paper, null, 2) + "\n")
    }
    return 0
  } catch (e) {
    writeError(e instanceof Error ? e.message : String(e), "DETAIL_FAILED")
    return 1
  }
}
