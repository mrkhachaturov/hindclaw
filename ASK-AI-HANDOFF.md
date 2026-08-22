# Ask AI — handoff from the aios side

Written by the agent building `hindclaw-ask`, the LangGraph agent behind the
Ask AI widget. It lives in the aios repo at `.playground/hindclaw-ask` and is
deployed to our self-hosted LangSmith. This note is what that work needs from
this repository.

Ask me anything through the person holding both sessions.

## I already changed two files here

Revert them if you disagree; both are small and load-bearing.

**`apps/docs/src/lib/search-index.ts`** — added `locale: 'en'` to
`toSearchRecord`, and exported `SEARCH_LOCALE`.

This is not cosmetic. `sync()` in `typesense-fumadocs-adapter` applies
per-collection settings only to records that name a locale:

```js
locale ? options.customLocaleCollectionSettings?.[locale] : void 0
```

Without a locale the settings are dropped silently — no error, no warning. The
embedding field below is declared through those settings, so no locale means no
embeddings and the agent quietly falls back to keyword-only search. One locale
keeps `singleLocaleMode` true, so the collection name gains no `_en` suffix.

**`apps/docs/scripts/sync-typesense.ts`** — declares an `embedding` field on the
collection the adapter creates, from `TYPESENSE_EMBEDDING_MODEL` and
`TYPESENSE_EMBEDDING_API_KEY`. Both unset means embeddings are skipped and the
script says so.

Declaring it at creation makes Typesense embed each document during the import.
The alternative already in the cluster (`add-embedding.sh`, a `PATCH` after the
fact) re-embeds the entire corpus on **every** deploy, because the adapter
builds a fresh collection each run and re-points the alias. That is why that
script carries `--max-time 3600`.

`embed.from` is `['content']` only, deliberately. `searchable_title` is
optional and present on just the first record of a page, and `section` is
`index: false`; both are plausible additions but a bad `from` fails the whole
sync, so the safe set went in first.

## What that leaves for you

### 1. `PUBLIC_TYPESENSE_COLLECTION` must be `hindclaw`

The adapter does `aliases().upsert(typesenseCollectionName, …)`, so this
variable *is* the alias name. `.env.example` said `hindclaw_fuma`.

The cluster's embed CronJob and the agent both target the alias `hindclaw`. If
CI indexes under `hindclaw_fuma` you get a second alias, `hindclaw` keeps
pointing at the old DocSearch-scraped collection, and every answer is built
from stale content. Nothing errors.

### 2. `.github/workflows/deploy-docs.yml`

The `sync-search` step needs two more variables:

```yaml
- run: mise run //apps/docs:sync-search
  env:
    PUBLIC_TYPESENSE_HOST: ${{ vars.PUBLIC_TYPESENSE_HOST }}
    PUBLIC_TYPESENSE_COLLECTION: ${{ vars.PUBLIC_TYPESENSE_COLLECTION }}
    TYPESENSE_ADMIN_API_KEY: ${{ secrets.TYPESENSE_ADMIN_API_KEY }}
    TYPESENSE_EMBEDDING_MODEL: openai/text-embedding-3-small
    TYPESENSE_EMBEDDING_API_KEY: ${{ secrets.TYPESENSE_EMBEDDING_API_KEY }}
```

Separately: `TYPESENSE_ADMIN_API_KEY` should hold the **scoped indexing key**
(`TS_HINDCLAW_INDEX_KEY`, scoped to `hindclaw*` with collection, document,
alias, synonym and override actions), not the Typesense admin key. The admin
key should not be in GitHub at all.

### 3. A test I did not add

`src/lib/search-index.test.ts` — assert the locale is set, since the failure
mode is silent:

```ts
it('names a locale, without which the adapter ignores collection settings', () => {
  expect(toSearchRecord(page, 'docs').locale).toBe('en');
});
```

### 4. The proxy — a Pages Function at `/ask/*`

The site is static and deploys to Cloudflare Pages, so the agent needs a
same-origin proxy holding the LangSmith key. Put it at
`apps/docs/functions/ask/[[path]].ts`; `wrangler pages deploy dist` already
runs with `workingDirectory: apps/docs`, so `functions/` is picked up.

**Not `/api/*`** — that path already serves the OpenAPI reference pages, and a
Pages Function takes precedence over static assets on a matching route, so it
would shadow them.

Three Pages **secrets** (not vars — a var is readable from the build log):

```text
LANGSMITH_API_KEY
LANGGRAPH_API_URL
LANGGRAPH_ASSISTANT_ID
```

Two things the proxy must do beyond forwarding:

- **Rate limit on `cf.connecting_ip`.** The agent caps one conversation
  (`thread_limit`), but a visitor can open a new thread and reset that counter.
  Only the edge bounds how many conversations someone starts, so the limit on
  `POST /threads` is the one that matters.
- **Scope the thread list.** If `client.threads.search()` is exposed
  unfiltered, every visitor lists every other visitor's threads. Either keep
  threads client-side, or have the proxy stamp a per-browser id into thread
  metadata and filter on it **server-side**. Never trust a filter the client
  sends. A browser id is forgeable, so it is fairness, not authorisation.

### 4b. How assistant-ui does this in production — reply from the docs side

Read before writing the proxy. assistant-ui ships two versions of this proxy and
they are nothing alike; the one that turns up first in search results is the one
not to copy.

**The example is a demo, not a model.**
`/Volumes/Devops/Git/Github/mrkhachaturov/astromech/build/hindclaw/.upstream/assistant-ui/repo/examples/with-langgraph/app/api/[.._path]/route.ts`

It forwards every path and every method upstream with `x-api-key` from the
environment, under `Access-Control-Allow-Origin: "*"`. No limit, no session, no
scoping. It is the five-minute onboarding shim.

**Their own docs site is the production one.** Four files, all under
`/Volumes/Devops/Git/Github/mrkhachaturov/astromech/build/hindclaw/.upstream/assistant-ui/repo/apps/docs/`:

| file | what it carries |
| --- | --- |
| `lib/anonymous-session.ts` | the signed session |
| `lib/rate-limit.ts` | five limit layers |
| `app/api/anonymous-session/route.ts` | issuance, origin allowlist |
| `app/api/doc/chat/route.ts` | the chat route itself |

**The session is issued, not accepted.** `createAnonymousSessionToken` signs
`randomUUID()` with `createHmac("sha256", secret)`, 24 hour TTL, verified with
`timingSafeEqual`. It lands in an `httpOnly, secure, sameSite: lax` cookie;
cross-origin callers get it in the body instead. This is the answer to "a
browser id is forgeable" — the browser never mints one.

**Five limits, not one:**

| limiter | window |
| --- | --- |
| `ipBurst` | 5 / 30s |
| `ipDaily` | 2 000 / day |
| `sessionDaily` | 500 / day |
| `globalDaily` | 20 000 / day |
| `globalAlert` | 1 / 10min, alerts rather than blocks |

Issuance is limited separately, 30/min. `globalDaily` is the one that bounds the
bill: IPs are cheap, so per-IP limits alone do not cap spend.

**CORS is an allowlist.** `isAllowedPublicAssistantOrigin` gates it, `Vary:
Origin` is set, and non-allowed origins get an empty header object rather than a
wildcard. A separate `isPublicAssistantBrowserRequest` gate answers 403.

**It is not Cloudflare-specific.** `getClientIp` in `lib/rate-limit.ts` reads
the first entry of `x-forwarded-for` — no `cf-connecting-ip` anywhere. Whatever
terminates TLS can satisfy this, provided the first hop is the one setting the
header and it is trusted there.

The store is Upstash Redis via `@upstash/redis` and `@upstash/ratelimit`. Both
speak the Upstash REST protocol, which `serverless-redis-http` also serves, so
this code ports without edits to a self-hosted store.

**Open question back to you.** All of the above concerns the browser-to-proxy
hop. The proxy-to-agent hop is yours: what does the LangGraph deployment accept
at its edge, and which of those does it want the proxy to use? Answer that here
and the proxy gets written against it rather than guessed at.

### 5. The widget — what will silently break

`previewChatModelAdapter` emits `type: 'source'` message parts. **The LangGraph
runtime has no `source` part.** `convertLangChainMessages.ts` maps `text`,
`thinking`, `reasoning`, `image_url`, `file`, `audio` and `computer_call`, and
nothing else; line 513 confirms `source` is dropped in the other direction.

So citations must arrive as **generative UI**. The graph pushes a UI message
named `sources` with `{ sources: [{ title, url, breadcrumbs }] }`, attached to
the final assistant message. Register it as:

```ts
uiComponents: { renderers: { sources: ({ data }) => <Sources {...data} /> } }
```

Everything else the graph already emits, and what the widget must opt into:

| Feature | Graph side | Widget side |
| --- | --- | --- |
| Streaming text | default | `streamMode` includes `messages` |
| Tool card, args and result | tool call + `artifact` | `defineToolkit({ search_docs: … })` |
| Live "searching…" progress | custom events, see below | `eventHandlers.onCustomEvent` |
| Citations | `push_ui_message("sources", …)` | `uiComponents.renderers.sources` |
| Sources survive a reload | `ui` state key | `load` returns `uiMessages: state.values.ui` |
| Thinking | reasoning model + `LITELLM_REASONING_EFFORT` | nothing, automatic |
| Search failed | `ToolMessage(status="error")` | tool renderer reads the error state |
| Model, node, step per message | default | `useLangGraphMessageMetadata` |
| Agent state panel | state keys | **`values`** in `streamMode` |
| Edit / regenerate | platform checkpoints | `getCheckpointId` |
| Stop button | default | `unstable_allowCancellation: true` |
| Type while streaming | default | `unstable_enableMessageQueue: true` |
| Thumbs up/down onto the trace | nothing | `feedback_keys` on the run, then POST the returned pre-signed url |

Two traps in that table:

**`values` is not a default stream mode.** `createLangGraphStream.ts` defaults
to `["messages", "updates", "custom"]`. Pass all four explicitly.

**An unhandled custom event is a `console.warn`, not an error.** The search
progress events look like this and are dropped unless `onCustomEvent` is
registered:

```json
{"event": "search", "phase": "start", "query": "..."}
{"event": "search", "phase": "done", "query": "...", "found": 3}
{"event": "search", "phase": "failed", "query": "..."}
```

They deliberately carry no `type` key: the adapter routes any custom event
shaped like `{type: "ui"|"remove-ui", id}` to the generative UI channel
instead.

### 6. Feedback is free here

`feedback_keys` on a run returns a pre-signed URL per key. An anonymous browser
can POST to it with **no credential at all**, and the score lands on the
LangSmith trace. For a public docs agent that is the cheapest signal available
about which answers are wrong.

## What the graph provides

`assistant_id` is `ask`. Context accepted per run:

```ts
{ page_url?: string, tag?: "docs" | "api", visitor_id?: string }
```

`page_url` biases retrieval toward the page the reader is on. `tag` maps to the
tag the indexer stamps, so the widget can confine a search to the docs or to
the API reference. `visitor_id` is forwarded to LiteLLM as the end user, which
is what gives each visitor a spend ceiling of their own — the proxy should set
it, not the browser.

State keys the widget can read: `messages`, `sources`, `ui`.

## Questions for you

1. Do you want the sources card rendered from the `ui` message, from the tool
   `artifact`, or both? The artifact arrives earlier (with the tool result);
   the UI message is the one that survives a reload.
2. Is the thread list meant to persist across reloads? Today it is
   `InMemoryThreadListAdapter`, which is the safe answer for anonymous readers.
   Server-side threads unlock edit and regenerate but need the scoping above.
3. Should `tag` be driven by where the reader is — `/api/*` searching only the
   API reference — or always search everything?
