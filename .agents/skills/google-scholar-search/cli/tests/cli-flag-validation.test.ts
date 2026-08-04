import { describe, test, expect } from "bun:test";
import { runCLI } from "./helpers";

// SERPAPI_API_KEY is explicitly cleared (empty string, which requireApiKey()
// treats as unset) for every test here so results are deterministic regardless
// of what's in the host/CI environment. None of these paths should ever reach
// the network - they all fail during flag validation or the API-key check.
const NO_KEY = { SERPAPI_API_KEY: "" };

describe("cli flag validation", () => {
  test("no command prints help and exits 1", async () => {
    const result = await runCLI([], NO_KEY);
    expect(result.exitCode).toBe(1);
    expect(result.stdout).toContain("google-scholar-cli");
  });

  test("search --help prints help and exits 0", async () => {
    const result = await runCLI(["search", "--help"], NO_KEY);
    expect(result.exitCode).toBe(0);
    expect(result.stdout).toContain("USAGE");
  });

  test("unknown command exits 1 with a JSON error on stderr", async () => {
    const result = await runCLI(["bogus"], NO_KEY);
    expect(result.exitCode).toBe(1);
    const err = JSON.parse(result.stderr);
    expect(err.code).toBe("BAD_CMD");
  });

  test("search with no --query exits 1 with NO_QUERY", async () => {
    const result = await runCLI(["search"], NO_KEY);
    expect(result.exitCode).toBe(1);
    const err = JSON.parse(result.stderr);
    expect(err.code).toBe("NO_QUERY");
  });

  test("search with a non-numeric --limit exits 1 with BAD_ARG", async () => {
    const result = await runCLI(["search", "-q", "test", "--limit", "not-a-number"], NO_KEY);
    expect(result.exitCode).toBe(1);
    const err = JSON.parse(result.stderr);
    expect(err.code).toBe("BAD_ARG");
  });

  test("search with a non-numeric --year-from exits 1 with BAD_ARG", async () => {
    const result = await runCLI(["search", "-q", "test", "--year-from", "not-a-year"], NO_KEY);
    expect(result.exitCode).toBe(1);
    const err = JSON.parse(result.stderr);
    expect(err.code).toBe("BAD_ARG");
  });

  test("cited-by with no id exits 1 with NO_ID", async () => {
    const result = await runCLI(["cited-by"], NO_KEY);
    expect(result.exitCode).toBe(1);
    const err = JSON.parse(result.stderr);
    expect(err.code).toBe("NO_ID");
  });

  test("search without SERPAPI_API_KEY exits 1 with NO_API_KEY", async () => {
    const result = await runCLI(["search", "-q", "test"], NO_KEY);
    expect(result.exitCode).toBe(1);
    const err = JSON.parse(result.stderr);
    expect(err.code).toBe("NO_API_KEY");
    expect(err.error).toContain("SERPAPI_API_KEY");
  });

  test("cited-by without SERPAPI_API_KEY exits 1 with NO_API_KEY", async () => {
    const result = await runCLI(["cited-by", "cites123"], NO_KEY);
    expect(result.exitCode).toBe(1);
    const err = JSON.parse(result.stderr);
    expect(err.code).toBe("NO_API_KEY");
  });
});
