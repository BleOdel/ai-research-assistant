import { WORKS_URL, jsonFetch, parseOneWork, normalizeWorkId, authParams, writeError, RateLimitError } from "../helpers.js"

export interface DetailOpts {
  id: string
  format: "json" | "plain"
}

/** Fetching a single work by id/DOI is free on OpenAlex regardless of API key
 * (per its documented per-operation costs) - prefer this over repeated `search`
 * calls where possible. */
export async function runDetail(opts: DetailOpts): Promise<number> {
  try {
    const id = normalizeWorkId(opts.id)
    const params = new URLSearchParams(authParams())
    const qs = params.toString()
    const url = `${WORKS_URL}/${encodeURIComponent(id).replace(/%2F/g, "/")}${qs ? `?${qs}` : ""}`
    const raw = await jsonFetch(url)
    const work = parseOneWork(raw)

    if (!work) {
      writeError(`No work found for id "${opts.id}"`, "NOT_FOUND")
      return 1
    }

    if (opts.format === "plain") {
      const authors = work.authors.map((a) => a.name).join(", ") || "(no authors listed)"
      const lines = [
        work.title,
        authors,
        `${work.venue ?? "(no venue indexed)"} · ${work.year ?? "-"} · ${work.citedByCount ?? 0} citations`,
        "",
        work.abstract || "(no abstract available)",
        "",
        work.doi ? `DOI: ${work.doi}` : "",
        `OpenAlex id: ${work.id}`,
        work.isOpenAccess ? "Open access: yes" : "",
        work.url ? `URL: ${work.url}` : "",
      ].filter((l) => l !== "")
      process.stdout.write(lines.join("\n") + "\n")
    } else {
      process.stdout.write(JSON.stringify(work, null, 2) + "\n")
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
