# hindclaw-docs

The [hindclaw.pro](https://hindclaw.pro) documentation site: Astro with fumadocs, built
to static HTML and published to Cloudflare Pages.

## Tasks

Tools and tasks come from mise. The repo is a mise monorepo, so tasks are addressed by
path and run from anywhere in the tree.

```bash
mise run //apps/docs:dev        # dev server on :4321
mise run //apps/docs:build      # static build into dist/
mise run //apps/docs:preview    # serve the built dist/
mise run //apps/docs:check      # lint, typecheck, test, build
```

From inside `apps/docs/` the `//hindclaw-docs` prefix collapses to `:` —
`mise run :dev`.

## Search

`astro build` writes `dist/search-index.json` from the fumadocs page structure, covering
docs and API reference pages. `mise run //apps/docs:sync-search` pushes that index
into Typesense, which is how the search box is fed — there is no crawler.

The sync creates `<collection>_<timestamp>`, imports into it, repoints the collection
alias and drops the previous one. It needs `TYPESENSE_ADMIN_API_KEY`; the deploy workflow
runs it after a successful publish.

## Environment

`astro.config.mjs` declares these through `envField`, so a build without them fails
rather than shipping a dead search box.

| Variable | Where |
|---|---|
| `PUBLIC_TYPESENSE_HOST` | build and sync |
| `PUBLIC_TYPESENSE_COLLECTION` | build and sync |
| `PUBLIC_TYPESENSE_SEARCH_API_KEY` | build only — compiled into the client bundle |
| `TYPESENSE_ADMIN_API_KEY` | sync only — never reaches the build |

Copy `.env.example` to `.env` for local work.
