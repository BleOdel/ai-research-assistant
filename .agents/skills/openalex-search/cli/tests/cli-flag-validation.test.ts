import { describe, test, expect } from "bun:test";
import { runCLI } from "./helpers";

describe("cli flag validation", () => {
  test("no command prints help and exits 1", async () => {
    const result = await runCLI([]);
    expect(result.exitCode).toBe(1);
    expect(result.stdout).toContain("openalex-cli");
  });

  test("search --help prints help and exits 0", async () => {
    const result = await runCLI(["search", "--help"]);
    expect(result.exitCode).toBe(0);
    expect(result.stdout).toContain("USAGE");
  });

  test("unknown command exits 1 with a JSON error on stderr", async () => {
    const result = await runCLI(["bogus"]);
    expect(result.exitCode).toBe(1);
    const err = JSON.parse(result.stderr);
    expect(err.code).toBe("BAD_CMD");
  });

  test("search with no --query exits 1 with NO_QUERY", async () => {
    const result = await runCLI(["search"]);
    expect(result.exitCode).toBe(1);
    const err = JSON.parse(result.stderr);
    expect(err.code).toBe("NO_QUERY");
  });

  test("search with a non-numeric --limit exits 1 with BAD_ARG", async () => {
    const result = await runCLI(["search", "-q", "test", "--limit", "not-a-number"]);
    expect(result.exitCode).toBe(1);
    const err = JSON.parse(result.stderr);
    expect(err.code).toBe("BAD_ARG");
  });

  test("search with a non-numeric --year-from exits 1 with BAD_ARG", async () => {
    const result = await runCLI(["search", "-q", "test", "--year-from", "not-a-year"]);
    expect(result.exitCode).toBe(1);
    const err = JSON.parse(result.stderr);
    expect(err.code).toBe("BAD_ARG");
  });

  test("detail with no id exits 1 with NO_ID", async () => {
    const result = await runCLI(["detail"]);
    expect(result.exitCode).toBe(1);
    const err = JSON.parse(result.stderr);
    expect(err.code).toBe("NO_ID");
  });
});
