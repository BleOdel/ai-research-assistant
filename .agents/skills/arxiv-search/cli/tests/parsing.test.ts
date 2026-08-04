import { describe, test, expect } from "bun:test";
import { parseFeed, buildSearchQuery, normalizeId } from "../src/helpers";

function feed(entries: string, total = 1): string {
  return `<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <opensearch:totalResults>${total}</opensearch:totalResults>
  ${entries}
</feed>`;
}

function entry(overrides: Partial<Record<string, string>> = {}): string {
  return `<entry>
    <id>http://arxiv.org/abs/${overrides.id ?? "2301.12345v2"}</id>
    <updated>${overrides.updated ?? "2023-01-15T12:00:00Z"}</updated>
    <published>${overrides.published ?? "2023-01-01T12:00:00Z"}</published>
    <title>${overrides.title ?? "A Great Paper"}</title>
    <summary>  ${overrides.summary ?? "This paper studies retrieval augmented generation."}
    </summary>
    <author><name>${overrides.author1 ?? "Ada Lovelace"}</name></author>
    <author><name>${overrides.author2 ?? "Alan Turing"}</name></author>
    <arxiv:doi>${overrides.doi ?? "10.1234/example"}</arxiv:doi>
    <link href="http://arxiv.org/abs/${overrides.id ?? "2301.12345v2"}" rel="alternate" type="text/html"/>
    <link title="pdf" href="http://arxiv.org/pdf/${overrides.id ?? "2301.12345v2"}" rel="related" type="application/pdf"/>
    <arxiv:primary_category term="${overrides.primaryCategory ?? "cs.CL"}" scheme="http://arxiv.org/schemas/atom"/>
    <category term="${overrides.primaryCategory ?? "cs.CL"}" scheme="http://arxiv.org/schemas/atom"/>
    <category term="cs.LG" scheme="http://arxiv.org/schemas/atom"/>
  </entry>`;
}

describe("parseFeed", () => {
  test("parses total results and a single entry", () => {
    const { totalResults, papers } = parseFeed(feed(entry(), 42));
    expect(totalResults).toBe(42);
    expect(papers).toHaveLength(1);
    const p = papers[0];
    expect(p.id).toBe("2301.12345v2");
    expect(p.title).toBe("A Great Paper");
    expect(p.summary).toBe("This paper studies retrieval augmented generation.");
    expect(p.authors).toEqual(["Ada Lovelace", "Alan Turing"]);
    expect(p.primaryCategory).toBe("cs.CL");
    expect(p.categories).toEqual(["cs.CL", "cs.LG"]);
    expect(p.doi).toBe("10.1234/example");
    expect(p.pdfUrl).toBe("http://arxiv.org/pdf/2301.12345v2");
    expect(p.absUrl).toBe("http://arxiv.org/abs/2301.12345v2");
  });

  test("parses multiple entries independently", () => {
    const xml = feed(entry({ id: "2301.00001", title: "First" }) + entry({ id: "2301.00002", title: "Second" }), 2);
    const { papers } = parseFeed(xml);
    expect(papers).toHaveLength(2);
    expect(papers[0].title).toBe("First");
    expect(papers[1].title).toBe("Second");
  });

  test("one malformed entry does not break the rest", () => {
    const malformed = `<entry><title>No id here</title></entry>`;
    const xml = feed(malformed + entry({ id: "2301.00003", title: "Valid" }), 2);
    const { papers } = parseFeed(xml);
    expect(papers).toHaveLength(1);
    expect(papers[0].title).toBe("Valid");
  });

  test("decodes XML entities in title and summary", () => {
    const xml = feed(entry({ title: "A &amp; B &lt;Study&gt;", summary: "Uses &quot;quotes&quot;" }));
    const { papers } = parseFeed(xml);
    expect(papers[0].title).toBe("A & B <Study>");
    expect(papers[0].summary).toBe('Uses "quotes"');
  });

  test("collapses whitespace/newlines in multi-line summary", () => {
    const xml = feed(entry({ summary: "Line one\n    Line two\n    Line three" }));
    const { papers } = parseFeed(xml);
    expect(papers[0].summary).toBe("Line one Line two Line three");
  });

  test("returns empty results when feed has no entries", () => {
    const { totalResults, papers } = parseFeed(feed("", 0));
    expect(totalResults).toBe(0);
    expect(papers).toHaveLength(0);
  });
});

describe("buildSearchQuery", () => {
  test("builds a query clause for --query", () => {
    expect(buildSearchQuery({ query: "graph neural networks" })).toBe('all:"graph neural networks"');
  });

  test("ANDs query and category", () => {
    expect(buildSearchQuery({ query: "rag", category: "cs.CL" })).toBe('all:"rag"+AND+cat:cs.CL');
  });

  test("adds a submittedDate range clause for --since", () => {
    const q = buildSearchQuery({ category: "cs.LG", since: "2024-01-01" });
    expect(q).toContain("cat:cs.LG");
    expect(q).toContain("submittedDate:[202401010000+TO+");
  });

  test("throws when no criteria are given", () => {
    expect(() => buildSearchQuery({})).toThrow();
  });
});

describe("normalizeId", () => {
  test("passes through a bare id unchanged", () => {
    expect(normalizeId("2301.12345")).toBe("2301.12345");
  });

  test("passes through a versioned id unchanged", () => {
    expect(normalizeId("2301.12345v2")).toBe("2301.12345v2");
  });

  test("extracts the id from a full abs URL", () => {
    expect(normalizeId("http://arxiv.org/abs/2301.12345v2")).toBe("2301.12345v2");
  });

  test("extracts the id from an https abs URL with trailing query", () => {
    expect(normalizeId("https://arxiv.org/abs/2301.12345?context=cs")).toBe("2301.12345");
  });
});
