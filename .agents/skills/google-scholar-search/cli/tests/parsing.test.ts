import { describe, test, expect } from "bun:test";
import { parseSearchResponse } from "../src/helpers";

function rawResult(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    position: overrides.position ?? 0,
    title: overrides.title ?? "A Great Paper on Keystroke Inference",
    result_id: overrides.result_id ?? "abc123def456",
    link: overrides.link ?? "https://example.com/paper.pdf",
    snippet: overrides.snippet ?? "This paper studies keystroke inference in VR.",
    publication_info: overrides.publication_info ?? {
      summary: "A Author, B Author - Proceedings of USENIX Security, 2024 - usenix.org",
      authors: [
        { name: "A Author", author_id: "auth1" },
        { name: "B Author", author_id: "auth2" },
      ],
    },
    resources: overrides.resources ?? [{ title: "usenix.org", file_format: "PDF", link: "https://usenix.org/paper.pdf" }],
    inline_links: overrides.inline_links ?? {
      cited_by: { total: 42, link: "https://scholar.google.com/...", cites_id: "cites123" },
    },
  };
}

describe("parseSearchResponse", () => {
  test("parses total results and organic_results", () => {
    const { totalResults, results } = parseSearchResponse({
      search_information: { total_results: 1234 },
      organic_results: [rawResult()],
    });
    expect(totalResults).toBe(1234);
    expect(results).toHaveLength(1);
    const r = results[0];
    expect(r.resultId).toBe("abc123def456");
    expect(r.title).toBe("A Great Paper on Keystroke Inference");
    expect(r.authors).toEqual([
      { name: "A Author", authorId: "auth1" },
      { name: "B Author", authorId: "auth2" },
    ]);
    expect(r.citedByCount).toBe(42);
    expect(r.citedById).toBe("cites123");
    expect(r.pdfUrl).toBe("https://usenix.org/paper.pdf");
  });

  test("extracts year from the publication summary string", () => {
    const { results } = parseSearchResponse({
      organic_results: [
        rawResult({
          publication_info: {
            summary: "C Author, D Author - Nature, 2021 - nature.com",
            authors: [],
          },
        }),
      ],
    });
    expect(results[0].year).toBe(2021);
    expect(results[0].venue).toBe("Nature");
  });

  test("handles a summary with no venue, just author(s) and year", () => {
    const { results } = parseSearchResponse({
      organic_results: [rawResult({ publication_info: { summary: "E Author - 2019 - arxiv.org", authors: [] } })],
    });
    expect(results[0].year).toBe(2019);
  });

  test("returns null year/venue when the summary has no recognizable year", () => {
    const { results } = parseSearchResponse({
      organic_results: [rawResult({ publication_info: { summary: "F Author - some venue with no year", authors: [] } })],
    });
    expect(results[0].year).toBeNull();
  });

  test("skips entries missing required fields instead of fabricating them", () => {
    const { results } = parseSearchResponse({
      organic_results: [rawResult(), { title: "No result_id here" }],
    });
    expect(results).toHaveLength(1);
  });

  test("citedByCount is null when inline_links.cited_by is absent (not defaulted to 0)", () => {
    const { results } = parseSearchResponse({
      organic_results: [rawResult({ inline_links: {} })],
    });
    expect(results[0].citedByCount).toBeNull();
    expect(results[0].citedById).toBeNull();
  });

  test("returns empty results for a malformed response", () => {
    const { totalResults, results } = parseSearchResponse(null);
    expect(totalResults).toBeNull();
    expect(results).toHaveLength(0);
  });

  test("handles a response with no organic_results array", () => {
    const { results } = parseSearchResponse({ search_information: { total_results: 0 } });
    expect(results).toHaveLength(0);
  });
});
