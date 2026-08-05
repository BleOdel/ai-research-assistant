# openalex-cli

CLI for searching [OpenAlex](https://openalex.org) via its public REST API. No
account required to start (small free daily allowance); an optional free API key
raises the limit substantially. Zero runtime dependencies.

See [`../SKILL.md`](../SKILL.md) for the full command reference, usage examples, and
the rate-limit/auth notes (including a real, documented data-quality quirk in
OpenAlex's abstract reconstruction).

## Development

```bash
bun install   # dev-only: pulls TypeScript types, no runtime deps
bun run typecheck
bun test      # flag-validation and fixture-based parsing tests only - no live
              # network calls
```
