import { mkdirSync, existsSync } from "node:fs"
import { join, resolve } from "node:path"
import {
  classifyId,
  arxivPdfUrl,
  openalexWorkUrl,
  extractOaPdfUrl,
  extractOaLandingUrl,
  cacheFilename,
  jsonFetch,
  downloadPdf,
  writeError,
  RateLimitError,
  NotPdfError,
  type ClassifiedId,
} from "../helpers.js"

export interface FetchOpts {
  id: string
  out: string
  force: boolean
  format: "json" | "plain"
}

interface Resolution {
  pdfUrl: string
  resolvedVia: "arxiv" | "openalex" | "oa-landing-attempt" | "direct"
  /** Set when resolvedVia is "oa-landing-attempt": the URL may serve HTML, and
   * the download's magic-byte check is the arbiter. Carried into the NOT_PDF
   * error message so the caller knows where the open copy lives. */
  landingUrl?: string
}

export async function resolvePdfUrl(classified: ClassifiedId): Promise<Resolution> {
  if (classified.kind === "arxiv") {
    return { pdfUrl: arxivPdfUrl(classified.value), resolvedVia: "arxiv" }
  }
  if (classified.kind === "url") {
    return { pdfUrl: classified.value, resolvedVia: "direct" }
  }
  // DOI or OpenAlex id: look the work up on OpenAlex (single-item lookups are
  // free regardless of API key) and take its best open-access PDF location.
  const work = await jsonFetch(openalexWorkUrl(classified))
  if (work === null) {
    throw new Error(`OpenAlex has no record for "${classified.value}" (404).`)
  }
  const pdfUrl = extractOaPdfUrl(work)
  if (pdfUrl) return { pdfUrl, resolvedVia: "openalex" }

  // Observed in the wild: genuinely open-access works (e.g. a PLOS ONE paper,
  // is_oa true) where OpenAlex records only a landing_page_url and no pdf_url.
  // Attempt the OA location anyway - some such URLs serve the PDF directly, and
  // the magic-byte check rejects HTML cleanly.
  const landingUrl = extractOaLandingUrl(work)
  if (landingUrl) {
    return { pdfUrl: landingUrl, resolvedVia: "oa-landing-attempt", landingUrl }
  }

  const err = new Error(
    `No open-access copy is known for "${classified.value}". The work exists on OpenAlex ` +
      "but is not flagged open access - it is likely paywalled. This tool never scrapes " +
      "paywalled publisher sites; score/fact-check this source from its abstract and say " +
      "so in the evidence basis.",
  )
  err.name = "NoOpenAccessPdf"
  throw err
}

export async function runFetch(opts: FetchOpts): Promise<number> {
  const classified = classifyId(opts.id)
  if (!classified) {
    writeError(
      `Could not classify "${opts.id}" as an arXiv id, DOI, OpenAlex work id, or URL.`,
      "BAD_ID",
    )
    return 1
  }

  const outDir = resolve(opts.out)
  const filePath = join(outDir, cacheFilename(classified))

  if (!opts.force && existsSync(filePath)) {
    const size = Bun.file(filePath).size
    emit(opts.format, { path: filePath, bytes: size, cached: true, resolved_via: null, source_url: null })
    return 0
  }

  let landingUrl: string | undefined
  try {
    const resolution = await resolvePdfUrl(classified)
    landingUrl = resolution.landingUrl
    const { pdfUrl, resolvedVia } = resolution
    const bytes = await downloadPdf(pdfUrl)
    mkdirSync(outDir, { recursive: true })
    await Bun.write(filePath, bytes)
    emit(opts.format, {
      path: filePath,
      bytes: bytes.length,
      cached: false,
      resolved_via: resolvedVia,
      source_url: pdfUrl,
    })
    return 0
  } catch (err) {
    if (err instanceof RateLimitError) {
      writeError(err.message, "RATE_LIMITED")
    } else if (err instanceof NotPdfError) {
      if (landingUrl) {
        // The work IS open access, but its recorded OA location serves HTML
        // rather than a direct PDF - a different situation from paywalled, and
        // one the caller can act on (visit the landing page, find the direct
        // PDF link, and pass it to `fetch` as a URL).
        writeError(
          `"${opts.id}" is open access, but OpenAlex records no direct PDF link and its OA ` +
            `landing page (${landingUrl}) serves HTML, not a PDF. Open that page, find the ` +
            "direct PDF link, and pass it to fetch as a URL. Nothing was written to the cache.",
          "NO_OA_PDF",
        )
      } else {
        writeError(err.message, "NOT_PDF")
      }
    } else if (err instanceof Error && err.name === "NoOpenAccessPdf") {
      writeError(err.message, "NO_OA_PDF")
    } else {
      writeError(err instanceof Error ? err.message : String(err), "FETCH_FAILED")
    }
    return 1
  }
}

interface FetchResult {
  path: string
  bytes: number
  cached: boolean
  resolved_via: string | null
  source_url: string | null
}

function emit(format: "json" | "plain", result: FetchResult): void {
  if (format === "plain") {
    const suffix = result.cached ? " (cached)" : ` (${result.bytes} bytes, via ${result.resolved_via})`
    process.stdout.write(`${result.path}${suffix}\n`)
    return
  }
  process.stdout.write(JSON.stringify(result) + "\n")
}
