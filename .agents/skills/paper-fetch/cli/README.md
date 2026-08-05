# paper-fetch CLI

Resolves a paper identifier (arXiv id, DOI, OpenAlex work id, or direct URL) to an
open-access PDF and downloads it into `research/fulltext/` (gitignored) for
full-text reading. Utility skill, not a search connector - see `../SKILL.md` for
full usage, resolution behavior, and error codes.

```bash
bun install        # dev types only - zero runtime dependencies
bun run typecheck
bun test           # offline fixture tests, no network
bun run src/cli.ts fetch 1706.03762
```
