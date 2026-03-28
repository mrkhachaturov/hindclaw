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
