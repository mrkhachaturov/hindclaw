# HindClaw TODOs

## CLI: Command naming inconsistency

The CLI uses different verbs for the same operations across subcommands. Standard CLIs (git, docker, kubectl) pick one style and stick with it.

**Current state:**

| Subcommand | List | Create | Delete |
|------------|------|--------|--------|
| `alias` | `ls` | `set` | `rm` |
| `admin sa` | `list` | `add` | `remove` |
| `admin sa key` | `ls` | `add` | `rm` |
| `admin user` | `list` | `add` | `remove` |
| `admin user key` | ? | ? | ? |
| `admin group` | `list` | `add` | `remove` |
| `admin policy` | `list` | `create` | `remove` |
| `template` | `list` | `create` | `remove` |

Three different create verbs (`set`, `add`, `create`), two different list verbs (`ls`, `list`), two different delete verbs (`rm`, `remove`).

**Proposal:** Support both short and long forms everywhere as aliases:
- `ls` / `list` — both work everywhere
- `rm` / `remove` — both work everywhere
- `add` / `create` — both work everywhere

Or pick one convention and alias the other. Most CLIs support `ls` as an alias for `list`.

---

## CLI: Self-service SA commands (`hindclaw sa`)

**Server-side done (v0.3.0):** `/me/service-accounts` endpoints exist with full ownership enforcement. Clients regenerated with `list_my_service_accounts`, `create_my_service_account`, etc.

**CLI not done:** The Rust CLI needs `hindclaw sa` subcommands targeting the `/me/` endpoints. Mapping is defined in the spec (`docs/rkstack/specs/hindclaw/2026-03-28-sa-self-service-design.md` Section 4):
- `hindclaw sa list` → `GET /me/service-accounts`
- `hindclaw sa add <id>` → `POST /me/service-accounts`
- `hindclaw sa info <id>` → `GET /me/service-accounts/{id}`
- `hindclaw sa key add <sa-id>` → `POST /me/service-accounts/{id}/keys`
- etc.

This is v2 scope per the CLI spec.

---

## CLI: Missing `hindclaw bank` commands

There's no way to list or inspect banks from the CLI. The `template apply` command creates banks, but there's no:
- `hindclaw bank list` — see what banks exist
- `hindclaw bank info <id>` — inspect a bank's config
- `hindclaw bank stats <id>` — fact count, last retain, etc.

These are useful for debugging plugin issues ("is my bank there? does it have facts?").

---

## CLI: `hindclaw claude` subcommand (future)

From the multi-bank design spec — the interactive setup wizard:
- `hindclaw claude init` — create project config, pick bank + template + domain banks
- `hindclaw claude configure` — change settings
- `hindclaw claude status` — show bank stats, config, domain connections

Not started. Separate spec needed.

---

## Plugin: Server-side budget enforcement not yet implemented

The plugin handles `warnings` in recall responses (cap-and-warn), but the server (`HindclawValidator.validate_recall()`) doesn't actually enforce `recall_budget` and `recall_max_tokens` from policies yet. The infrastructure is in `AccessResult` and `intersect_sa_policy`, but the validator passes client values through unchecked.

Spec: `docs/rkstack/specs/hindclaw/2026-03-28-claude-hindclaw-plugin-v2-design.md` section 6.

---

## Upstream Hindsight v0.4.21 / v0.4.22 — features relevant to HindClaw

Tracked after bumping from v0.4.20 to v0.4.22 (2026-04-03).

### High priority

- [ ] **Audit log integration** (#717, #758) — every retain/recall/reflect is now logged with bank ID, operation metadata, and `duration_ms`. HindClaw should expose tenant-scoped audit queries via `/ext/hindclaw/` HTTP extension. Enables per-tenant usage dashboards and billing.

- [ ] **`tags_match` / `tag_groups` in mental model triggers** (#804) — mental models can now trigger based on tag patterns. HindClaw injects tags per tenant via `HindclawValidator` — test that mental models can be scoped per-tenant using these tag-based triggers. Could allow tenant-specific consolidation and mental model behavior.

- [ ] **`max_observations_per_scope` bank config** (#729) — per-bank limit on stored observations. HindClaw should expose this as a tenant quota setting in bank management / templates. Prevents runaway memory growth per tenant.

### Medium priority

- [ ] **Client-side `strategy` on MCP retain** (#684) — clients can now pass `verbose`/`fast` per retain call. `HindclawValidator.validate_retain()` already injects strategy server-side — verify interaction when both client and server set strategy (server should win for policy enforcement).

- [ ] **Recall metadata fix** (#680, #803) — recall responses now correctly include metadata in both engine and HTTP layers. If HindClaw stores access control metadata on memories/documents, it's now queryable in recall results. Verify `HindclawValidator.validate_recall()` passes metadata through.

- [ ] **`document_metadata` in API** (#798) — document metadata exposed in API and control plane. If HindClaw stores ACL or tenant info in document metadata, it's now surfaced. Consider using this for document-level access control.

### Low priority / watch

- [ ] **`HINDSIGHT_API_LLM_EXTRA_BODY`** (#781) — custom model params per deployment. Useful if tenant-specific LLM configs are needed (e.g., different temperature per bank).

- [ ] **`X-Ignored-Params` warning header** (#802) — API warns on unknown request params. Helpful for debugging HindClaw client/extension calls.

- [ ] **Delta retain** (#701) — skip LLM processing for unchanged chunks on document upsert. Relevant for bulk ingestion pipelines. No HindClaw action needed, but good to know it exists.

- [ ] **`none` LLM provider** (#691) — chunk-only storage without LLM extraction. Could be useful for raw document ingestion tenants that only need retrieval, not memory extraction.
