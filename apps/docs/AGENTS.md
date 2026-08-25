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

### Every `transition:persist` carries a name

A bare `transition:persist` gets the name Astro generates, and that name ends in a counter
incremented once per transition directive in the page render — `astro-<file hash>-1` on a
page that renders one, `-2` on a page that renders two. `AskAi` sits in `SiteHeader.astro`
on every page, but on a docs page `DocsSidebar` takes the first number, so the same island
was `astro-typyj2n2-2` under `/docs` and `astro-typyj2n2-1` on the home page. The names do
not match, nothing is carried over, and the swap leaves the old React tree alive with its
DOM detached: the docked panel is replaced by the server's closed markup, while the
detached tree keeps its `astro:after-swap` listener and re-applies
`--ask-ai-panel-width`, so the body stays pushed aside with no panel beside it.

So name them — `transition:persist="ask-ai"`, `transition:persist="docs-sidebar"`. The name
is what makes the island the same island on both sides of a navigation.

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

## `fumadocs-ui` is Base UI, not Radix

The import name lies. `fumadocs-ui` resolves to `@fumadocs/base-ui`, and fumadocs ships a
second implementation of the same components as `@fumadocs/radix-ui`. They differ where it
matters: the Radix drawer wraps its `<aside>` in `@radix-ui/react-presence`, the Base UI one
keeps a local `hidden` flag and clears it from its own `onAnimationEnd`.

So **read `apps/docs/node_modules/fumadocs-ui/dist/` or
`.upstream/fumadocs/packages/base-ui/`, never `.upstream/fumadocs/packages/radix-ui/`.** An
afternoon was lost debugging a Presence state machine that is not in the bundle.

Two consequences of the Base UI drawer, both load-bearing:

- It hides itself only when the exit animation ends. If that animation does not run, the
  drawer stays on screen with `data-state="closed"` — open to the eye, closed to the DOM.
- `SidebarDrawerOverlay` and `SidebarDrawerContent` spread `{...props}` **after** their own
  `onAnimationEnd`. Passing that prop from our vendored slot silently replaces theirs and
  the drawer never hides again.

## Where state lives

> State we own that crosses a component boundary lives in a nanostores atom.
> State fumadocs owns stays in their context.

| state | owner | mechanism |
|---|---|---|
| Ask AI open, mode, pending message | ours | atoms in `lib/ask-ai/store.ts` |
| active theme | ours | atom in `lib/theme/store.ts` |
| search dialog open | fumadocs | their `SearchProvider`, reached by a command atom |
| sidebar `collapsed`, drawer `open` | fumadocs | their `SidebarContext` |
| whether the drawer was open before a navigation | ours | atoms in `lib/sidebar/store.ts` |

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

### The drawer outlives the island that renders it

A section link is meant to leave the drawer standing, so the reader can pick a page in the
new tree without opening it twice — fumadocs clears `closeOnRedirect` for exactly that. In
Next their layout is never rebuilt and the ref survives. Here every navigation destroys the
mobile island together with `useState(false)` and that ref, so the drawer always came back
closed.

`lib/sidebar/store.ts` closes the gap without becoming the mirror this section warns about.
While a page lives, fumadocs' context stays the only truth — it opens on the trigger, closes
on the overlay, on the trigger again and on a path change, and the atom renders nothing.
`DrawerStateSync` writes `open` to the atom when it changes and reads it exactly once, when
a fresh island mounts, as the value the previous page left behind. One way out, one read in.
`keepDrawerOpen` carries `closeOnRedirect` across the same gap: the section link sets it,
the `astro:before-preparation` handler consumes it, and every other navigation clears
`drawerOpen`.

The one divergence from fumadocs is in `SidebarDrawer`: the entry animation class is applied
only from the first open the reader performs. A drawer that arrives already open is not
opening, and would otherwise slide in on every section switch. The exit class stays exactly
as upstream writes it, because Base UI needs that animation to fire in order to hide.

**Do not add `transition:persist` to the mobile island.** Then its element is carried into
the new document, the browser re-applies its styles, and the entry animation replays about
40ms after `astro:page-load` — measured with the same node, same attributes, no DOM
mutation. It also delays the close on a page link until after the swap, because `pathname`
reaches the island as a prop. `slots.sidebar` must stay a module-scope object for the same
family of reasons: an arrow in JSX is a new component type on every render, React remounts
on a type change, and the rebuilt drawer re-reads the atom and forces itself back open.

### The theme is split in two

`ThemeScript.astro` keeps an `is:inline` block that reads `localStorage` and applies the
class **before the first paint**. That part cannot become an atom: module scripts run after
hydration, which is a flash of the wrong theme on every load.

Everything after that is the atom in `lib/theme/store.ts`. Astro toggles are bound by
`[data-theme-toggle]` on `astro:page-load`; React toggles call `toggleTheme()` directly,
which matters because an island hydrates long after that event has fired.

## Ask AI is one surface in three shells

`AskAiSurface` is the whole product — header, thread, welcome, suggestions, composer, thread
list. It never knows where it is. Around it sit three shells that do nothing but place it:

| shell | file | viewport |
|---|---|---|
| docked panel | `ask-ai/panel.tsx` | `md` and up, `askAiMode === 'docked'` |
| floating window | `ask-ai/floating.tsx` | `md` and up, `askAiMode === 'floating'` |
| full-screen sheet | `ask-ai/mobile.tsx` | below `md` |

A new viewport gets a new shell, never a second copy of the surface. The sheet passes
`layout="sheet"`, which is the only thing the header branches on: bigger hit targets and no
dock toggle, because there is nothing to dock to on a phone.

The shell is chosen in the island by `useMediaQuery`, not by CSS. CSS can hide a panel; it
cannot make one modal. The sheet is `ui/sheet.tsx` — shadcn's Base UI Sheet, added with the
CLI and left untouched — so it carries the focus trap, the scroll lock, `aria-modal` and Esc
that a `fixed inset-0` div would have to reinvent one bug at a time. `useMediaQuery` returns
`false` from `getServerSnapshot`, so the desktop shell is what hydrates and the swap happens
on the first client render.

Overriding a `side` variant on `SheetContent` needs the same variant prefix —
`data-[side=right]:w-full`, not `w-full`. The registry's own `data-[side=right]:w-3/4`
carries a class-plus-attribute selector, so a bare utility loses on specificity and
tailwind-merge never sees the two as a conflict. A sheet that opens at three quarters width,
or at `h-auto` when you asked for `h-dvh`, is this and nothing else.

`--ask-ai-panel-width` pushes the body aside only inside a `min-width: 48rem` media query.
Below that the sheet covers the page and there is nothing to push.

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
