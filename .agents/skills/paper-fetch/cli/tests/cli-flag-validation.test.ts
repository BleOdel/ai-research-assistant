import { describe, test, expect } from "bun:test";
import { runCLI } from "./helpers";

describe("cli flag validation", () => {
  test("no command prints help and exits 1", async () => {
    const result = await runCLI([]);
    expect(result.exitCode).toBe(1);
    expect(result.stdout).toContain("paper-fetch");
  });

  test("fetch --help prints help and exits 0", async () => {
    const result = await runCLI(["fetch", "--help"]);
    expect(result.exitCode).toBe(0);
    expect(result.stdout).toContain("USAGE");
  });

  test("unknown command exits 1 with a JSON error on stderr", async () => {
    const result = await runCLI(["bogus"]);
    expect(result.exitCode).toBe(1);
    const err = JSON.parse(result.stderr);
    expect(err.code).toBe("BAD_CMD");
  });

  test("fetch with no id exits 1 with NO_ID", async () => {
    const result = await runCLI(["fetch"]);
    expect(result.exitCode).toBe(1);
    const err = JSON.parse(result.stderr);
    expect(err.code).toBe("NO_ID");
  });

  test("resolve with no id exits 1 with NO_ID", async () => {
    const result = await runCLI(["resolve"]);
    expect(result.exitCode).toBe(1);
    const err = JSON.parse(result.stderr);
    expect(err.code).toBe("NO_ID");
  });

  test("fetch with an unclassifiable id exits 1 with BAD_ID, no network call", async () => {
    const result = await runCLI(["fetch", "not-a-paper-id"]);
    expect(result.exitCode).toBe(1);
    const err = JSON.parse(result.stderr);
    expect(err.code).toBe("BAD_ID");
  });
});
