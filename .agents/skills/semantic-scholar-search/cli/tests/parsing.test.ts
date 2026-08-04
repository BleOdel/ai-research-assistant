import { describe, test, expect } from "bun:test";
import { parseSearchResponse, parsePaperResponse, normalizeId, buildYearParam } from "../src/helpers";

function rawPaper(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    paperId: overrides.paperId ?? "abc123",
    title: overrides.title ?? "A Great Paper",
    abstract: overrides.abstract ?? "This paper studies retrieval augmented generation.",
    year: overrides.year ?? 2023,
    venue: overrides.venue ?? "NeurIPS",
    citationCount: overrides.citationCount ?? 42,
    influentialCitationCount: overrides.influentialCitationCount ?? 5,
    authors: overrides.authors ?? [
      { authorId: "1", name: "Ada Lovelace" },
      { authorId: "2", name: "Alan Turing" },
    ],
    externalIds: overrides.externalIds ?? { DOI: "10.1234/example", ArXiv: "2301.12345" },
    url: overrides.url ?? "https://www.semanticscholar.org/paper/abc123",
  };
}

describe("parseSearchResponse", () => {
  test("parses total, offset, and papers", () => {
    const { total, offset, papers } = parseSearchResponse({
      total: 100,
      offset: 0,
      data: [rawPaper()],
    });
    expect(total).toBe(100);
    expect(offset).toBe(0);
    expect(papers).toHaveLength(1);
    const p = papers[0];
    expect(p.paperId).toBe("abc123");
    expect(p.title).toBe("A Great Paper");
    expect(p.year).toBe(2023);
    expect(p.venue).toBe("NeurIPS");
    expect(p.citationCount).toBe(42);
    expect(p.influentialCitationCount).toBe(5);
    expect(p.authors).toEqual([
      { authorId: "1", name: "Ada Lovelace" },
      { authorId: "2", name: "Alan Turing" },
    ]);
    expect(p.externalIds.DOI).toBe("10.1234/example");
  });

  test("skips entries missing required fields instead of fabricating them", () => {
    const { papers } = parseSearchResponse({
      total: 2,
      offset: 0,
      data: [rawPaper(), { title: "No paperId here" }],
    });
    expect(papers).toHaveLength(1);
  });

  test("normalizes a missing/empty venue to null (preprint signal)", () => {
    const { papers } = parseSearchResponse({ total: 1, offset: 0, data: [rawPaper({ venue: "" })] });
    expect(papers[0].venue).toBeNull();
  });

  test("returns empty results for a malformed response", () => {
    const { total, papers } = parseSearchResponse(null);
    expect(total).toBe(0);
    expect(papers).toHaveLength(0);
  });

  test("handles a response with no data array", () => {
    const { papers } = parseSearchResponse({ total: 0, offset: 0 });
    expect(papers).toHaveLength(0);
  });
});

describe("parsePaperResponse", () => {
  test("parses a single paper detail response", () => {
    const paper = parsePaperResponse(rawPaper({ paperId: "xyz789", title: "Detail Paper" }));
    expect(paper).not.toBeNull();
    expect(paper!.paperId).toBe("xyz789");
    expect(paper!.title).toBe("Detail Paper");
  });

  test("returns null for a malformed response", () => {
    expect(parsePaperResponse({ notAPaper: true })).toBeNull();
    expect(parsePaperResponse(null)).toBeNull();
  });
});

describe("normalizeId", () => {
  test("passes through a bare S2 paper id unchanged", () => {
    expect(normalizeId("abc123")).toBe("abc123");
  });

  test("uppercases a prefixed arxiv id", () => {
    expect(normalizeId("arxiv:2301.12345")).toBe("ARXIV:2301.12345");
  });

  test("uppercases a prefixed doi id and preserves the doi's own casing/slashes", () => {
    expect(normalizeId("doi:10.1234/Some.Example")).toBe("DOI:10.1234/Some.Example");
  });

  test("handles whitespace around the prefix and value", () => {
    expect(normalizeId(" arxiv : 2301.12345 ")).toBe("ARXIV:2301.12345");
  });
});

describe("buildYearParam", () => {
  test("returns null when neither bound is given", () => {
    expect(buildYearParam({})).toBeNull();
  });

  test("builds a from-to range", () => {
    expect(buildYearParam({ from: 2020, to: 2024 })).toBe("2020-2024");
  });

  test("builds an open-ended from range", () => {
    expect(buildYearParam({ from: 2020 })).toBe("2020-");
  });

  test("builds an open-ended to range", () => {
    expect(buildYearParam({ to: 2020 })).toBe("-2020");
  });
});
