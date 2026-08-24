# Why the docs site looks like a Frankenstein

Working notes. Delete once the work below is done.

Everything here was read out of this repository, out of
`.upstream/assistant-ui/repo`, out of `.upstream/shadcn-ui`, and out of
`node_modules/fumadocs-ui`. Line references are real. Where a claim comes from a
research pass rather than a file I opened myself, it says so.

The problem is not taste and not a set of wrong numbers. It is that the project
never declared a style layer, so every component reaches into whichever of four
systems is nearest. Three root causes, each independently fixable.

---

## Root cause 1 — there is no type system at all

`apps/docs/src/pages/docs/[...slug].astro:74` renders the article as:

```html
<div class="prose prose-gray dark:prose-invert mt-8">
```

**`.prose` is not defined anywhere in this project.**

- `@tailwindcss/typography` is not in `apps/docs/package.json`
- fumadocs defines only `@utility prose-no-margin`
  (`fumadocs-ui/css/lib/base.css:144`), never `.prose`
- `shadcn/tailwind.css` does not define it
- the only `.prose` in `fumadocs-ui` is in `css/vitepress.css`, a theme we do
  not import

So the documentation article has **no typographic system applied**. No base
size, no line height, no rhythm between blocks, no list or table styling. What
renders is Tailwind Preflight plus browser defaults — which is why body text
sits at 16px and reads oversized next to assistant-ui's 14px.

Meanwhile `apps/docs/src/styles/typeset.css` is 490 lines of **shadcn/typeset**,
copied verbatim with its header comment intact. It is **not imported anywhere** —
not from `global.css`, not from a layout, not from `astro.config` — and
`class="typeset"` appears nowhere in `apps/docs/src`. The file does not reach the
browser at all.

### What typeset actually is

I had this wrong at first, and it matters. It is not "a style someone picked".
From shadcn's own documentation
(`.upstream/shadcn-ui/apps/v4/content/docs/(root)/typeset.mdx`):

> A typeset is just a small preset class. You can have multiple typesets in your
> app, for different contexts.
>
> **It uses your theme.** Colors, fonts, and radius come from your app.
>
> **It fits its container.** Put it in a chat bubble and it follows the smaller
> type around it. Put it in an article and it scales up with the page.
>
> **It works well with streaming.** When a new block arrives, Typeset doesn't
> make earlier blocks switch margins, borders, or styles.

It is exactly the "declare a library, then apply it" mechanism. Three controls —
`--typeset-size`, `--typeset-leading`, `--typeset-flow` — and everything else
(heading sizes, indents, gaps, rules) derives from them. shadcn also ships a
builder that generates the file and a preset class.

So matching assistant-ui does not mean finding a different typeset. It means
**writing presets with their numbers**:

| preset | assistant-ui equivalent | values |
| --- | --- | --- |
| `.typeset-docs` | `.prose` (`fumadocs.css:166`) | `--typeset-size: 0.875rem`, `--typeset-leading: 1.7` |
| `.typeset-blog` | `.prose-blog` (`fumadocs.css:352`) | `0.9375rem`, `1.75` |
| `.typeset-chat` | the Ask AI thread | smaller; typeset scales to its container |

Their two prose variants map one-to-one onto two typeset presets.

---

## Root cause 2 — no shared token layer, though fumadocs ships one free

Four vocabularies coexist and nothing maps between them:

| System | Comes from | Paints |
| --- | --- | --- |
| fumadocs `--fd-*` | `fumadocs-ui/css/neutral.css` + `preset.css` | body, header, sidebar, cards, callouts |
| shadcn `--background` etc. | our `global.css:102+` | Ask AI widget, everything in `components/ui/` |
| shadcn typeset | our `typeset.css` | **nothing — not even loaded** |
| `.prose` | **nowhere** | **nothing — the class does not exist** |

`bg-background` and `bg-fd-background` are therefore simply different colours,
and the Ask AI widget is a different white from the page it sits on.

### The one-line fix

We import the wrong fumadocs theme. `fumadocs-ui/css/shadcn.css` exists in
`node_modules` today and does precisely the aliasing I was about to write by
hand:

```css
:root, .dark {
  --color-fd-background: var(--background);
  --color-fd-foreground: var(--foreground);
  --color-fd-card:       var(--card);
  --color-fd-border:     var(--border);
  --color-fd-muted-foreground: var(--muted-foreground);
  /* …and the rest */
}

#nd-sidebar {
  background-color: var(--sidebar);
  color: var(--sidebar-foreground);
  border-color: var(--sidebar-border);
}
```

Two consequences. Every fumadocs surface starts following the shadcn palette, so
the widget and the page become the same colour system. And the sidebar gets its
**own legitimate token** `--sidebar` instead of borrowing `--fd-card` — which is
the library-declares/component-applies shape we want.

`global.css:2` currently imports `neutral.css`. assistant-ui imports
`shadcn.css`. That is the whole difference.

### Why the surfaces differ today, with numbers

From `fumadocs-ui/css/lib/default-colors.css`:

| | light | dark |
| --- | --- | --- |
| `--fd-background` — body, main | `hsl(0 0% 96%)` | `hsl(0 0% 7.04%)` |
| `--fd-card` — our sidebar | `hsl(0 0% 94.7%)` | `hsl(0 0% 9.8%)` |
| difference | −1.3% | **+2.76%** |

The gap exists in both themes and **reverses direction** — sidebar darker than
the page in light, lighter in dark. Not a one-theme slip.

Contributing sources:

- `components/docs/sidebar.tsx:81` — desktop sidebar is `bg-fd-card` + `border-e`
- `components/docs/sidebar.tsx:134` — the *mobile* sidebar is `bg-fd-background`,
  so desktop and mobile already disagree with each other
- `components/SiteHeader.astro:22` — header is `bg-fd-background/80` with
  `backdrop-blur-sm`; at 80% opacity it matches neither surface and tints with
  whatever scrolls beneath
- `neutral.css` re-tints the sidebar in dark mode only:

```css
.dark #nd-sidebar {
  --color-fd-muted: hsl(0, 0%, 16%);
  --color-fd-secondary: hsl(0, 0%, 18%);
}
```

### Astro is not the obstacle

`global.css` is imported once per layout (`Site.astro:5`, `DocsShell.astro:5`).
Islands render into the same document, so global CSS and custom properties reach
them automatically — there is no Shadow DOM isolation. The mechanism for
"declare once, apply everywhere" already works. What is missing is the
declaration: `global.css` does not define a system, it just pulls in four of
them and lets each component choose.

---

## Root cause 3 — the layout reserves more space for emptiness than for text

`apps/docs/src/layouts/DocsGrid.astro:2` is five columns:

```text
"sidebar sidebar main toc toc" 1fr /
  minmax(min-content, 1fr)                          ← empty gutter
  var(--fd-sidebar-col)                             ← 268px
  minmax(0, calc(97rem - sidebar - toc))            ← main, caps at 1016px
  var(--fd-toc-width)                               ← 268px
  minmax(min-content, 1fr)                          ← empty gutter
```

`--fd-layout-width` is **97rem = 1552px**; sidebar and TOC are 268px each
(`sidebar.tsx:72`, `toc.tsx:52`). So main caps at 1552 − 536 = **1016px**, the
whole block caps at 1552px, and everything wider is split between the two gutters.

A third layer sits inside that: the article is capped again at `max-w-3xl` =
**768px** and centred (`[...slug].astro:54`).

| viewport | gutter | sidebar | slack | **text** | slack | TOC | gutter |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1552px | 0 | 268 | 124 | **768** | 124 | 268 | 0 |
| 1920px | 184 | 268 | 124 | **768** | 124 | 268 | 184 |
| 2560px | 504 | 268 | 124 | **768** | 124 | 268 | 504 |

At 2560px there is 628px of emptiness on each side of 768px of text — more empty
than content — and it grows linearly with the screen, because the 1552px cap is
fixed.

This also explains why the sidebar looks unpinned: the element occupies the grid
area `"sidebar sidebar"`, i.e. **both** the gutter and its own column. Its
background spans both while its contents are pushed right by `items-end` to
268px. The TOC does the same mirrored on the right.

### Compounding: column width against type size

| | ours | assistant-ui |
| --- | --- | --- |
| article width | `max-w-3xl` = **768px** | `--docs-article-width: 56rem` = **896px** |
| body text | 16px (no system applied) | 14px (`.prose`) |
| lead paragraph | 18px | 15px |
| sidebar links | inherited `text-sm` | `13px` |
| TOC | inherited | `12px` |

Roughly 65–70 characters per line for us against 95–100 for them on the same
screen. That is what "they give more room to what matters" actually is: a wider
column carrying smaller type.

Font family is not the issue — we use Geist Variable (`global.css:44`), they use
Inter with `font-optical-sizing: auto`. Both fine. The scale is the issue.

---

## How assistant-ui is actually built

From a dedicated research pass over their `apps/docs`. Their stack is four
layers, and the ordering is the load-bearing decision:

```css
/* styles/globals.css */
@import "tailwindcss";
@import "fumadocs-ui/css/shadcn.css";   /* fd-* aliased onto shadcn */
@import "fumadocs-ui/css/preset.css";
@import "./fumadocs.css";                /* their own layer, last word */
```

1. **Tokens** — stock shadcn zinc in `globals.css`, plus an `@theme inline` block
   binding raw variables to utility names. Two non-stock additions worth noting:
   `--page-width: 80rem`, and a self-inverting surface that needs no `.dark`
   override:

   ```css
   --code-surface: color-mix(in oklab, var(--foreground) 4%, var(--background));
   ```

   They also null every `--shadow-*` to `0 0 #0000` — a deliberate flat system.

2. **Aliasing** — `fumadocs-ui/css/shadcn.css`, as above.

3. **App layout scale** — a small `--docs-*` set on `:root`:
   `--docs-header-height: 48px`, `--docs-article-width: 56rem`,
   `--docs-page-inline: 1rem` (1.5rem ≥768px). That is the entire list.

4. **Components** — semantic Tailwind (`bg-muted`, `text-muted-foreground`) in
   app chrome, `fd-*` classes only inside `components/docs/fumadocs/**`, and a
   shared `components/ui` primitive layer built on `cva`. The split is by
   directory and it is consistent.

**Layout.** Their sidebar is not in the grid at all — a `fixed` 260px rail, with
the content wrapper offset by `md:ml-(--sidebar-width)`. The grid holds only main
and TOC, and gains the TOC column at ≥1280px through `:has(#nd-toc)`, so a page
without headings gets one column automatically:

```css
#nd-docs-layout { --fd-layout-width: 9999px;
                  grid-template: "main" 1fr / minmax(0, 1fr) !important; }
#nd-page { max-width: var(--docs-article-width) !important;
           margin-inline: auto !important; }
```

**The sidebar switcher** — the control that swaps the whole sidebar tree. Worth
copying wholesale for content-heavy projects:

- pages declare eligibility in frontmatter: `platforms: [react, rn, ink]`;
  missing field means universal
- a pure function re-shapes the single page tree per selection; empty separators
  are pruned
- the choice persists three-tier: URL `?platform=` → `localStorage` → default,
  behind `useSyncExternalStore` for SSR safety, with cross-tab sync
- switching routes you to the *equivalent* page in the new tree if one exists,
  else the tree root

**Collapsible sections** are a plain `<button aria-expanded>` plus
`motion/react`, single-open accordion, with the open section derived from the
URL and an auto-scroll-to-active that fires just after the animation ends.

**One sidebar DOM** serves mobile and desktop, switched by responsive classes, so
open/closed state cannot desync between the two.

---

## What must not be lost

The risk in "make it look like assistant-ui" is trading behaviour for
appearance. The two are separable, and the line is: **fumadocs stays the engine,
we change only the style layer.** Search, page tree, TOC, MDX and OpenAPI are
components with behaviour; none care what colour or size they render at.

Checklist to re-verify after each step:

| Feature | Where it comes from | At risk from |
| --- | --- | --- |
| TOC scroll indicator, active tracking | `fumadocs-ui/components/toc` via `components/docs/toc.tsx:3-5` | nothing — behaviour, not CSS |
| Typesense search, ⌘K | `lib/typesense.ts`, `pages/api/search.ts` | nothing |
| Sidebar collapse and hover-peek | `components/docs/sidebar.tsx` | step 4 edits this file |
| Ask AI: docked/floating, resize, threads | `components/ask-ai/*` | step 2 recolours it |
| Copy Markdown, View as Markdown, Edit on GitHub | `components/page-controls.tsx` | uses `not-prose` |
| Client-side nav, widget persistence | `ClientRouter` + `transition:persist` | nothing |
| Mermaid, Shiki, Tabs, Accordions, Cards | `components/astro/*` | step 1: they use `not-prose` / `prose-no-margin` |
| OpenAPI reference pages | `fumadocs-openapi` | step 1: may carry its own scale |
| Blog, `llms.txt` | `lib/blog.ts`, `lib/llms.ts` | nothing |

Two need care rather than a glance. `not-prose` and `prose-no-margin` **are**
real fumadocs utilities (unlike `.prose`), and `Card.astro:34,40` and
`page-controls.tsx:23` depend on them. And the OpenAPI preset may bring a type
scale that fights `.typeset` on `/docs/api/*`.

---

## What not to copy from them

- **Their `fumadocs.css` as a file.** 588 lines, `!important` on nearly every
  rule, because they import fumadocs' preset and then fight it on specificity.
  We already split the way shadcn did — `DocsGrid.astro`, `sidebar.tsx`,
  `toc.tsx` are ours — so we change values at source with no `!important`.
- **Their `#nd-sidebar` block.** They disable fumadocs' sidebar entirely
  (`sidebar: { enabled: false }`) and hand-build one, which makes ~80 lines of
  their sidebar CSS dead fossil. Copying it would import rubbish and fight our
  sidebar, which is live.
- **`48px` written in three places.** Their header height is duplicated across
  two CSS files and a Tailwind class. Ours should be one token.
- **Repeated class strings as local `const`s** where `cva` is already a
  dependency.

For contrast: shadcn's own docs (`.upstream/shadcn-ui/apps/v4`) depend on
`fumadocs-core`, `fumadocs-mdx` and `fumadocs-ui`, yet never reference
`--fd-background`, `--fd-card` or `--fd-layout-width` at all. They use fumadocs
for content and build the layout on shadcn tokens. That is structurally where we
already are — we just have not finished the job.

---

## Plan

Each step is independently visible on `localhost:4321` and reversible.

1. **Turn the type system on.** Import `typeset.css` from `global.css`, define
   `.typeset-docs` / `.typeset-blog` presets with assistant-ui's numbers, and
   replace `class="prose prose-gray dark:prose-invert"` with
   `class="typeset typeset-docs"` on the docs, blog and API article pages.
   Biggest single win; fixes "fonts are huge" and gives the article a rhythm.

2. **Swap the fumadocs theme.** `global.css:2` — `neutral.css` → `shadcn.css`.
   One line; unifies the whole palette and gives the sidebar `--sidebar`.
   Re-check the Ask AI widget, which is what this is meant to reconcile.

3. **Remove the gutters.** `DocsGrid.astro` → three columns:
   `"sidebar main toc" 1fr / var(--fd-sidebar-col) minmax(0,1fr) var(--fd-toc-width)`.
   Sidebar pins left, TOC pins right, article stays centred by its own max-width.

4. **Widen the column and settle the surfaces.** `max-w-3xl` → `max-w-4xl`
   (768 → 896px, exactly their 56rem). Decide whether the header keeps its `/80`
   translucency deliberately or goes flat.

5. **Optional, separate: the sidebar switcher.** Frontmatter-driven tree
   switching, for the content-heavy projects this site is a template for. This is
   a feature, not styling, and should be its own piece of work.

Steps 1–4 are small and reversible. Step 2 recolours the entire site at once and
should be looked at on its own even though it is one line.

---

## Open questions

- Does the OpenAPI preset carry a type scale that will fight `.typeset` on
  `/docs/api/*`?
- Is `typeset.css` a vendor copy we want to keep overwritable? It carries no
  local edits today, so presets belong in `global.css`, not inside that file.
- Do we want `--docs-*` layout tokens of our own (header height, article width)
  so those values stop being written in several places?
- Header height, sidebar width (268px) and TOC width (268px) are currently
  Tailwind arbitrary values inside components. Should they become tokens before
  step 3, so the grid and the components cannot drift?
