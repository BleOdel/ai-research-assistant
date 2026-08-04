# semantic-scholar-cli

CLI for searching papers on [Semantic Scholar](https://www.semanticscholar.org) via its
public Graph API. No authentication, zero runtime dependencies — runs with just `bun`.

See [`../SKILL.md`](../SKILL.md) for the full command reference, usage examples, and
the rate-limit note.

## Development

```bash
bun install   # dev-only: pulls TypeScript types, no runtime deps
bun run typecheck
bun test
```
