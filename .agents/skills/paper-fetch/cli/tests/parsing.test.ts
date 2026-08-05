import { describe, expect, test } from "bun:test"
import {
  classifyId,
  arxivPdfUrl,
  extractOaPdfUrl,
  extractOaLandingUrl,
  cacheFilename,
  looksLikePdf,
} from "../src/helpers.js"

describe("classifyId", () => {
  test("new-style arXiv ids, with and without version", () => {
    expect(classifyId("2401.08998")).toEqual({ kind: "arxiv", value: "2401.08998" })
    expect(classifyId("2401.08998v2")).toEqual({ kind: "arxiv", value: "2401.08998v2" })
    expect(classifyId("1706.03762")).toEqual({ kind: "arxiv", value: "1706.03762" })
  })

  test("old-style arXiv ids", () => {
    expect(classifyId("cs/0601001")).toEqual({ kind: "arxiv", value: "cs/0601001" })
    expect(classifyId("cs/0601001v1")).toEqual({ kind: "arxiv", value: "cs/0601001v1" })
  })

  test("arXiv abs/pdf URLs normalize to the bare id", () => {
    expect(classifyId("https://arxiv.org/abs/2401.08998")).toEqual({ kind: "arxiv", value: "2401.08998" })
    expect(classifyId("https://arxiv.org/pdf/2401.08998")).toEqual({ kind: "arxiv", value: "2401.08998" })
    expect(classifyId("https://arxiv.org/pdf/2401.08998v3.pdf")).toEqual({ kind: "arxiv", value: "2401.08998v3" })
    expect(classifyId("http://www.arxiv.org/abs/1706.03762")).toEqual({ kind: "arxiv", value: "1706.03762" })
  })

  test("bare DOIs and doi.org URLs", () => {
    expect(classifyId("10.14722/ndss.2024.24100")).toEqual({ kind: "doi", value: "10.14722/ndss.2024.24100" })
    expect(classifyId("https://doi.org/10.1371/journal.pone.0266462")).toEqual({
      kind: "doi",
      value: "10.1371/journal.pone.0266462",
    })
    expect(classifyId("https://dx.doi.org/10.1016/j.cose.2023.103058")).toEqual({
      kind: "doi",
      value: "10.1016/j.cose.2023.103058",
    })
  })

  test("OpenAlex work ids and URLs", () => {
    expect(classifyId("W2741809807")).toEqual({ kind: "openalex", value: "W2741809807" })
    expect(classifyId("w2741809807")).toEqual({ kind: "openalex", value: "W2741809807" })
    expect(classifyId("https://openalex.org/W2741809807")).toEqual({ kind: "openalex", value: "W2741809807" })
  })

  test("other URLs pass through as direct URLs", () => {
    expect(classifyId("https://www.ndss-symposium.org/wp-content/uploads/2024-100-paper.pdf")).toEqual({
      kind: "url",
      value: "https://www.ndss-symposium.org/wp-content/uploads/2024-100-paper.pdf",
    })
  })

  test("empty and unrecognized inputs return null, not a guess", () => {
    expect(classifyId("")).toBeNull()
    expect(classifyId("   ")).toBeNull()
    expect(classifyId("not-a-paper-id")).toBeNull()
    // A DOI prefix with no suffix is not a valid DOI
    expect(classifyId("10.1371/")).toBeNull()
  })
})

describe("arxivPdfUrl", () => {
  test("builds the stable arXiv PDF URL", () => {
    expect(arxivPdfUrl("2401.08998")).toBe("https://arxiv.org/pdf/2401.08998")
    expect(arxivPdfUrl("2401.08998v2")).toBe("https://arxiv.org/pdf/2401.08998v2")
  })
})

describe("extractOaPdfUrl", () => {
  // Shaped exactly like a real OpenAlex work record's location fields.
  const workWith = (fields: Record<string, unknown>) => ({
    id: "https://openalex.org/W123",
    display_name: "Test work",
    ...fields,
  })

  test("prefers best_oa_location.pdf_url", () => {
    const work = workWith({
      best_oa_location: { pdf_url: "https://arxiv.org/pdf/2401.08998", oa_url: "https://arxiv.org/abs/2401.08998" },
      primary_location: { pdf_url: "https://other.example/paper.pdf" },
    })
    expect(extractOaPdfUrl(work)).toBe("https://arxiv.org/pdf/2401.08998")
  })

  test("falls back to primary_location.pdf_url", () => {
    const work = workWith({
      best_oa_location: null,
      primary_location: { pdf_url: "https://publisher.example/oa/paper.pdf" },
    })
    expect(extractOaPdfUrl(work)).toBe("https://publisher.example/oa/paper.pdf")
  })

  test("falls back to any locations[] entry with a pdf_url", () => {
    const work = workWith({
      best_oa_location: null,
      primary_location: { pdf_url: null, landing_page_url: "https://publisher.example/paper" },
      locations: [
        { pdf_url: null, landing_page_url: "https://publisher.example/paper" },
        { pdf_url: "https://repository.example/bitstream/paper.pdf" },
      ],
    })
    expect(extractOaPdfUrl(work)).toBe("https://repository.example/bitstream/paper.pdf")
  })

  test("a location with only oa_url (no pdf_url) is NOT used - oa_url is often a landing page", () => {
    const work = workWith({
      best_oa_location: { pdf_url: null, oa_url: "https://publisher.example/article/view/123" },
      primary_location: { pdf_url: null },
      locations: [{ pdf_url: null, oa_url: "https://publisher.example/article/view/123" }],
    })
    expect(extractOaPdfUrl(work)).toBeNull()
  })

  test("returns null for paywalled works and malformed input", () => {
    expect(extractOaPdfUrl(workWith({ best_oa_location: null, primary_location: null }))).toBeNull()
    expect(extractOaPdfUrl(null)).toBeNull()
    expect(extractOaPdfUrl("not an object")).toBeNull()
    expect(extractOaPdfUrl({})).toBeNull()
  })
})

describe("extractOaLandingUrl", () => {
  // Shaped from the real OpenAlex record that surfaced this case: a PLOS ONE
  // paper (10.1371/journal.pone.0266462) with is_oa true, landing_page_url set,
  // and pdf_url null.
  test("returns the OA landing URL for an OA-flagged work with no pdf_url", () => {
    const work = {
      id: "https://openalex.org/W4224009465",
      open_access: { is_oa: true },
      best_oa_location: {
        is_oa: true,
        landing_page_url: "https://doi.org/10.1371/journal.pone.0266462",
        pdf_url: null,
      },
    }
    expect(extractOaLandingUrl(work)).toBe("https://doi.org/10.1371/journal.pone.0266462")
  })

  test("prefers oa_url over landing_page_url when both exist", () => {
    const work = {
      open_access: { is_oa: true },
      best_oa_location: {
        oa_url: "https://repository.example/oa/paper",
        landing_page_url: "https://publisher.example/article",
        pdf_url: null,
      },
    }
    expect(extractOaLandingUrl(work)).toBe("https://repository.example/oa/paper")
  })

  test("returns null when the work is not flagged open access - paywalled is a hard stop", () => {
    const work = {
      open_access: { is_oa: false },
      best_oa_location: null,
      primary_location: { landing_page_url: "https://publisher.example/paywalled" },
    }
    expect(extractOaLandingUrl(work)).toBeNull()
  })

  test("returns null on malformed input", () => {
    expect(extractOaLandingUrl(null)).toBeNull()
    expect(extractOaLandingUrl({})).toBeNull()
    expect(extractOaLandingUrl({ open_access: { is_oa: true } })).toBeNull()
  })
})

describe("cacheFilename", () => {
  test("arXiv, DOI, and OpenAlex ids produce readable, safe filenames", () => {
    expect(cacheFilename({ kind: "arxiv", value: "2401.08998v2" })).toBe("arxiv-2401.08998v2.pdf")
    expect(cacheFilename({ kind: "doi", value: "10.14722/ndss.2024.24100" })).toBe("doi-10.14722-ndss.2024.24100.pdf")
    expect(cacheFilename({ kind: "openalex", value: "W2741809807" })).toBe("openalex-W2741809807.pdf")
  })

  test("direct URLs use the last path segment, deduplicating a .pdf suffix", () => {
    expect(cacheFilename({ kind: "url", value: "https://x.example/papers/heimdall-ndss24.pdf" })).toBe(
      "url-heimdall-ndss24.pdf",
    )
  })

  test("URLs with no usable path segment fall back to a hash, deterministically", () => {
    const a = cacheFilename({ kind: "url", value: "https://x.example/?id=1" })
    const b = cacheFilename({ kind: "url", value: "https://x.example/?id=1" })
    expect(a).toBe(b)
    expect(a).toMatch(/^url-[0-9a-f]+\.pdf$/)
  })
})

describe("looksLikePdf", () => {
  test("accepts %PDF- prefixed buffers", () => {
    expect(looksLikePdf(new TextEncoder().encode("%PDF-1.7\n..."))).toBe(true)
  })

  test("rejects HTML error pages and short buffers", () => {
    expect(looksLikePdf(new TextEncoder().encode("<!DOCTYPE html><html>..."))).toBe(false)
    expect(looksLikePdf(new TextEncoder().encode("%PDF"))).toBe(false)
    expect(looksLikePdf(new Uint8Array(0))).toBe(false)
  })
})
