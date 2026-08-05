import { describe, test, expect } from "bun:test";
import { parseSearchResponse, parseOneWork, normalizeWorkId } from "../src/helpers";

// Fixture based on the real OpenAlex response for the Heimdall paper (fetched live
// via curl during development, trimmed to the fields this parser reads), including
// the real quirk that surfaced: primary_location.source is null even though a
// human-readable venue name is available under raw_source_name.
function rawWork(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    id: overrides.id ?? "https://openalex.org/W4391725312",
    doi: overrides.doi ?? "https://doi.org/10.14722/ndss.2024.24100",
    title: overrides.title ?? "Eavesdropping on Controller Acoustic Emanation for Keystroke Inference Attack in Virtual Reality",
    publication_year: overrides.publication_year ?? 2024,
    cited_by_count: overrides.cited_by_count ?? 20,
    primary_location: overrides.primary_location ?? {
      source: null,
      raw_source_name: "Proceedings 2024 Network and Distributed System Security Symposium",
      landing_page_url: "https://doi.org/10.14722/ndss.2024.24100",
    },
    authorships: overrides.authorships ?? [
      {
        author_position: "first",
        author: { id: "https://openalex.org/A5081283448", display_name: "Shiqing Luo", orcid: "https://orcid.org/0000-0002-4169-2555" },
      },
      {
        author_position: "middle",
        author: { id: "https://openalex.org/A5104831694", display_name: "Anh Nguyen", orcid: null },
      },
    ],
    open_access: overrides.open_access ?? { is_oa: true, oa_status: "gold" },
    abstract_inverted_index:
      "abstract_inverted_index" in overrides
        ? overrides.abstract_inverted_index
        : { We: [0], present: [1], Heimdall: [2], a: [3], "novel": [4], attack: [5] },
  };
}

describe("parseSearchResponse", () => {
  test("parses meta.count and organic results", () => {
    const { totalResults, results } = parseSearchResponse({
      meta: { count: 954 },
      results: [rawWork()],
    });
    expect(totalResults).toBe(954);
    expect(results).toHaveLength(1);
    const r = results[0];
    expect(r.id).toBe("https://openalex.org/W4391725312");
    expect(r.title).toContain("Eavesdropping on Controller Acoustic Emanation");
    expect(r.year).toBe(2024);
    expect(r.citedByCount).toBe(20);
    expect(r.doi).toBe("https://doi.org/10.14722/ndss.2024.24100");
    expect(r.isOpenAccess).toBe(true);
  });

  test("authors are extracted from authorships[].author.display_name", () => {
    const { results } = parseSearchResponse({ results: [rawWork()] });
    expect(results[0].authors).toEqual([
      { name: "Shiqing Luo", authorId: "https://openalex.org/A5081283448", orcid: "https://orcid.org/0000-0002-4169-2555" },
      { name: "Anh Nguyen", authorId: "https://openalex.org/A5104831694", orcid: null },
    ]);
  });

  test("venue falls back to raw_source_name when source is null (real observed case)", () => {
    const { results } = parseSearchResponse({ results: [rawWork()] });
    expect(results[0].venue).toBe("Proceedings 2024 Network and Distributed System Security Symposium");
  });

  test("venue prefers source.display_name when source is present", () => {
    const { results } = parseSearchResponse({
      results: [
        rawWork({
          primary_location: {
            source: { display_name: "Journal of Made-Up Security" },
            raw_source_name: "should not be used",
          },
        }),
      ],
    });
    expect(results[0].venue).toBe("Journal of Made-Up Security");
  });

  test("reconstructs the abstract from the inverted index in position order", () => {
    const { results } = parseSearchResponse({
      results: [
        rawWork({
          abstract_inverted_index: { the: [0, 3], quick: [1], fox: [2], jumps: [4] },
        }),
      ],
    });
    expect(results[0].abstract).toBe("the quick fox the jumps");
  });

  test("abstract is null (not fabricated) when the inverted index is absent", () => {
    const { results } = parseSearchResponse({ results: [rawWork({ abstract_inverted_index: undefined })] });
    expect(results[0].abstract).toBeNull();
  });

  test("skips entries missing required fields instead of fabricating them", () => {
    const { results } = parseSearchResponse({
      results: [rawWork(), { title: "No id here" }],
    });
    expect(results).toHaveLength(1);
  });

  test("returns empty results for a malformed response", () => {
    const { totalResults, results } = parseSearchResponse(null);
    expect(totalResults).toBeNull();
    expect(results).toHaveLength(0);
  });

  test("handles a response with no results array", () => {
    const { results } = parseSearchResponse({ meta: { count: 0 } });
    expect(results).toHaveLength(0);
  });
});

describe("parseOneWork", () => {
  test("parses a single work detail response", () => {
    const work = parseOneWork(rawWork());
    expect(work).not.toBeNull();
    expect(work!.title).toContain("Eavesdropping");
  });

  test("returns null for a malformed response", () => {
    expect(parseOneWork({ notAWork: true })).toBeNull();
    expect(parseOneWork(null)).toBeNull();
  });
});

describe("normalizeWorkId", () => {
  test("passes through a bare OpenAlex work id unchanged", () => {
    expect(normalizeWorkId("W4391725312")).toBe("W4391725312");
  });

  test("converts a bare DOI to a doi.org URL", () => {
    expect(normalizeWorkId("10.14722/ndss.2024.24100")).toBe("https://doi.org/10.14722/ndss.2024.24100");
  });

  test("passes through a full doi.org URL unchanged", () => {
    expect(normalizeWorkId("https://doi.org/10.14722/ndss.2024.24100")).toBe("https://doi.org/10.14722/ndss.2024.24100");
  });

  test("passes through a full openalex.org URL unchanged", () => {
    expect(normalizeWorkId("https://openalex.org/W4391725312")).toBe("https://openalex.org/W4391725312");
  });
});
