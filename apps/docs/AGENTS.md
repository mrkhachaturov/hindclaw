# hindclaw-docs

Rules that are not visible from the code alone. Each one exists because the obvious
alternative was tried, or because it breaks something that only shows up later.

Read `README.md` first for tasks, search and environment.

## Desktop and mobile are separate islands

A docs page mounts two sets of islands and gates each by viewport:

| island | directive | renders |
|---|---|---|
| `DocsSidebar`, `DocsToc` | `client:media="(min-width: 768px)"` | the sidebar column and the right-hand TOC |
| `DocsMobile` | `client:media="(max-width: 767px)"` | fumadocs' `#nd-subnav`, the TOC popover and the drawer |

`client:media` gates hydration, not server rendering, so the other side's HTML is still in
the page. That is fine — it is hidden by the same CSS fumadocs already ships
(`max-md:hidden` on the sidebar column, `md:hidden` on the subnav) — but it is why
`DocsMobile` must not render fumadocs' own `Sidebar`: its desktop half would be visible on
wide screens with no JS to remove it. `slots.sidebar.root` is substituted with
`MobileSidebar`, which renders only the drawer.

**Never merge the desktop islands into one that also holds the article.** `DocsSidebar`
carries `transition:persist` so its collapsed state survives client-side navigation; an
island that contains page content cannot be persisted, because Astro would keep the
previous page's text with it. This was the reason the page was split up in the first place.

Passing content into an island is otherwise free: Astro's React integration turns a slot
into `memo(StaticHtml, () => true)` with `dangerouslySetInnerHTML` and
`suppressHydrationWarning`, so React never re-renders or diffs it, and the HTML is read
from the DOM already on the page. The reason not to do it here is `transition:persist`.

### Why the mobile island contains a whole `DocsLayout`

`#nd-subnav`, the TOC popover and the drawer chrome all call `useDocsLayout()`, whose
`LayoutContext` is declared without `export` in `fumadocs-ui/layouts/docs`. They cannot be
mounted one by one. `DocsMobile` therefore renders `DocsLayout` with
`slots.container` replaced by a pass-through fragment — the grid is ours, in
`DocsGrid.astro`, and `astro-island` is `display: contents`, so the layout's children land
as direct grid items.

That also means fumadocs' `layout:` variant works: it compiles to
`#nd-docs-layout:has(&) { … }`, so `#nd-subnav` raises `--fd-header-height` on our grid by
existing inside it.

## Where state lives

> State we own that crosses a component boundary lives in a nanostores atom.
> State fumadocs owns stays in their context.

| state | owner | mechanism |
|---|---|---|
| Ask AI open, mode, pending message | ours | atoms in `lib/ask-ai/store.ts` |
| active theme | ours | atom in `lib/theme/store.ts` |
| search dialog open | fumadocs | their `SearchProvider`, reached by a command atom |
| sidebar `collapsed`, drawer `open` | fumadocs | their `SidebarContext` |

`SidebarContext` is private, so the atom cannot own the sidebar. Mirroring it would create
a second copy of the truth that fumadocs mutates behind our back — the overlay closes the
drawer, and so does a navigation. The rule that follows: **a control that drives sidebar
state must be rendered by the island that renders the sidebar.** `SidebarTrigger` exists
for that. A button in `SiteHeader.astro` cannot reach the context, and neither can an
island nested in a slot — slotted content arrives as inert HTML, and a nested island
hydrates under its own root.

Search is the case where the atom is a channel rather than a store: the header island owns
the dialog, so `DocsMobile` calls `openSearch()` from `lib/search/store.ts` and a bridge
inside the search island turns it into `setOpenSearch(true)`. Use `atom.listen`, not
`subscribe`, for a command channel — `subscribe` fires immediately on mount and would
replay the last command.

### The theme is split in two

`ThemeScript.astro` keeps an `is:inline` block that reads `localStorage` and applies the
class **before the first paint**. That part cannot become an atom: module scripts run after
hydration, which is a flash of the wrong theme on every load.

Everything after that is the atom in `lib/theme/store.ts`. Astro toggles are bound by
`[data-theme-toggle]` on `astro:page-load`; React toggles call `toggleTheme()` directly,
which matters because an island hydrates long after that event has fired.

## Search sits in the header, not the sidebar

fumadocs puts the search trigger in the sidebar and in its mobile bar. We moved it into
`SiteHeader`, matching assistant-ui.

That is why the header's `RootProvider` is the one carrying `SearchDialog`, and why every
other `RootProvider` passes `search={{ enabled: false }}`. Three search providers would
register ⌘K three times and nest one dialog inside another. They all pass
`theme={{ enabled: false }}` for the same reason — the inline script owns the theme.

## The grid

`DocsGrid.astro` carries fumadocs' layout variables as utility classes on the element,
never as Astro scoped styles. Scoped styles come last in the cascade and add specificity,
so they silently beat rules like `md:layout:[--fd-sidebar-width:260px]` and collapse the
sidebar column.

It declares three rows — `header`, `toc-popover`, `main`. On desktop the first two are
empty and collapse to zero, so the result is the single row it used to be.

Below `md` it also pins `--fd-banner-height: 0`, because `SiteHeader` is hidden there on
docs pages. Without it the subnav's `sticky top-(--fd-docs-row-1)` pushes itself down by
the height of a header that is not on the screen.

## Pages are prerendered

Only the routes under `src/pages/api/` set `prerender = false`. Every page is rendered at
build time, so the server never sees the request that produced a page. Anything that
adapts to the reader — viewport, pointer, theme — has to be decided in the browser by CSS
or by an island, never by inspecting a request on the server.
