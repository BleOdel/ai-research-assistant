# google-scholar-cli

CLI for searching [Google Scholar](https://scholar.google.com) via
[SerpApi](https://serpapi.com/google-scholar-api). Requires a SerpApi account and API
key for every request (free tier: 250 searches/month) - zero runtime dependencies
beyond that.

See [`../SKILL.md`](../SKILL.md) for the full command reference, usage examples, and
the API-key setup.

## Development

```bash
bun install   # dev-only: pulls TypeScript types, no runtime deps
bun run typecheck
bun test      # flag-validation and fixture-based parsing tests only - no live
              # network calls, since that would require a real API key and would
              # burn against the account's monthly quota on every CI run
```
