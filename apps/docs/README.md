# hindclaw-docs

The [hindclaw.pro](https://hindclaw.pro) documentation site: Astro with fumadocs, built as
a container. Pages are prerendered at build time; only the routes under `/api/` are served
on demand by the node process.

## Tasks

Tools and tasks come from mise. The repo is a mise monorepo, so tasks are addressed by
path and run from anywhere in the tree.

```bash
mise run //apps/docs:dev        # dev server on :3000
mise run //apps/docs:build      # build into dist/
mise run //apps/docs:preview    # serve the build
mise run //apps/docs:check      # lint, typecheck, test, build
```

From inside `apps/docs/` the `//apps/docs` prefix collapses to `:` — `mise run :dev`.

## Search

`astro build` writes `dist/client/search-index.json` from the fumadocs page structure,
covering docs and API reference pages. `mise run //apps/docs:sync-search` pushes that
index into Typesense, which is how the search box is fed — there is no crawler.

The sync creates `<collection>_<timestamp>`, imports into it, repoints the collection
alias and drops the previous one. It needs `TYPESENSE_ADMIN_API_KEY`.

Queries never leave the server: the browser calls `/api/search`, which runs the Typesense
query with a key the client never sees.

## Environment

Read from the process environment at runtime, not baked into the build.

| Variable | Used by |
|---|---|
| `TYPESENSE_URL` | `/api/search` and the sync |
| `TYPESENSE_COLLECTION` | `/api/search` and the sync |
| `TYPESENSE_API_KEY` | `/api/search` — search-only key |
| `TYPESENSE_ADMIN_API_KEY` | sync only |

Copy `.env.example` to `.env` for local work. `astro dev` reads it; the built server does
not, so pass the values on the command line when running `dist/server/entry.mjs` directly.

A deployment may supply `TYPESENSE_API_KEY` from a secret manager instead of the
environment; see `src/lib/secrets.ts`. When it does, an unreachable secret manager makes
`/api/search` answer 503 rather than falling back to anything.

`.github/workflows/deploy-docs.yml` only calls the app webhook — the build happens on the
builder, not in CI.
