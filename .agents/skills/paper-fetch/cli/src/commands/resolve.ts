import { classifyId, writeError, RateLimitError } from "../helpers.js"
import { resolvePdfUrl } from "./fetch.js"

export interface ResolveOpts {
  id: string
  format: "json" | "plain"
}

/** Resolves the identifier to its PDF URL without downloading anything - useful
 * for checking whether a source has an open-access PDF at all before committing
 * to a download, and for debugging resolution behavior. */
export async function runResolve(opts: ResolveOpts): Promise<number> {
  const classified = classifyId(opts.id)
  if (!classified) {
    writeError(
      `Could not classify "${opts.id}" as an arXiv id, DOI, OpenAlex work id, or URL.`,
      "BAD_ID",
    )
    return 1
  }

  try {
    const { pdfUrl, resolvedVia } = await resolvePdfUrl(classified)
    if (opts.format === "plain") {
      process.stdout.write(`${pdfUrl} (via ${resolvedVia})\n`)
    } else {
      process.stdout.write(JSON.stringify({ pdf_url: pdfUrl, resolved_via: resolvedVia, id_kind: classified.kind }) + "\n")
    }
    return 0
  } catch (err) {
    if (err instanceof RateLimitError) {
      writeError(err.message, "RATE_LIMITED")
    } else if (err instanceof Error && err.name === "NoOpenAccessPdf") {
      writeError(err.message, "NO_OA_PDF")
    } else {
      writeError(err instanceof Error ? err.message : String(err), "RESOLVE_FAILED")
    }
    return 1
  }
}
