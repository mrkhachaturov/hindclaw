---
sidebar_position: 1
title: Plugin Configuration
---

# Plugin Configuration Reference

HindClaw uses a two-level config system. Plugin-level defaults are set in `openclaw.json` (or its modular `$include` files). Per-agent behavioral overrides are set in the `agents` map within the plugin config.

**Resolution order:** plugin defaults -> per-agent overrides (shallow merge, agent entry wins).

Server-side bank configuration (retain missions, entity labels, dispositions, directives, strategies) is managed via the [Terraform provider](../guides/terraform). User/group management is also done via Terraform, not config files.

## Config Architecture

```
openclaw.json (plugin config)          Terraform (server-side)
  Infrastructure                         Bank config (per-agent)
    hindsightApiUrl, jwtSecret             retain_mission, entity_labels
                                           dispositions, directives
  Daemon (global only)                     retain_strategies
    apiPort, embedVersion
    embedPackagePath, daemonIdleTimeout  Access control
                                           users, groups, permissions
  Defaults (overridable per-agent)         strategy scopes
    llmProvider, llmModel
    autoRecall, autoRetain, ...
    recallBudget, retainEveryNTurns

  Per-agent behavioral overrides
    agents: { id: { recallBudget,
      recallMaxTokens, recallFrom,
      sessionStartModels, reflectOnRecall,
      hindsightApiUrl, ... } }

  bootstrap: true|false
```

## Plugin Config Options

Set these in the `config` block of the HindClaw plugin entry inside `openclaw.json`.

### Infrastructure

| Option | Type | Default | Per-agent | Description |
|--------|------|---------|-----------|-------------|
| `hindsightApiUrl` | `string` | -- | yes | Hindsight API base URL. When set, connects to a remote server instead of the local daemon. |
| `hindsightApiToken` | `string` | -- | yes | Bearer token for API authentication. Used for single-user setups without hindclaw-extension. Mutually exclusive with `jwtSecret`. |
| `jwtSecret` | `string` | -- | no | Shared secret (HMAC-SHA256) for signing JWTs sent to a server running hindclaw-extension. The same secret must be configured on the server via `HINDSIGHT_API_TENANT_JWT_SECRET`. When set, the plugin generates short-lived JWTs containing the sender, agent, channel, and topic for each request instead of using a static API token. |

### Daemon (Global Only)

These options control the embedded `hindsight-embed` daemon. They cannot be overridden per-agent.

| Option | Type | Default | Per-agent | Description |
|--------|------|---------|-----------|-------------|
| `apiPort` | `number` | `9077` | no | Port the local daemon listens on. |
| `embedVersion` | `string` | `"latest"` | no | Version of `hindsight-embed` to use. |
| `embedPackagePath` | `string` | -- | no | Path to a local `hindsight-embed` installation. For development only. |
| `daemonIdleTimeout` | `number` | `0` | no | Seconds of inactivity before the daemon shuts down. `0` means never. |

### Bank ID Routing

| Option | Type | Default | Per-agent | Description |
|--------|------|---------|-----------|-------------|
| `dynamicBankId` | `boolean` | `true` | yes | Derive the bank ID dynamically from context fields instead of using a static ID. |
| `dynamicBankGranularity` | `string[]` | `["agent","channel","user"]` | yes | Which context fields to include in the derived bank ID. Valid values: `agent`, `provider`, `channel`, `user`. |
| `bankIdPrefix` | `string` | -- | yes | Static prefix prepended to derived bank IDs. |

### Behavioral Defaults

These set the plugin-wide defaults. Any of them can be overridden in a per-agent entry.

| Option | Type | Default | Per-agent | Description |
|--------|------|---------|-----------|-------------|
| `autoRecall` | `boolean` | `true` | yes | Inject recalled memories into the prompt before each turn. |
| `autoRetain` | `boolean` | `true` | yes | Retain conversations after each agent turn. |
| `recallBudget` | `string` | `"mid"` | yes | Recall effort level. Values: `low`, `mid`, `high`. Higher values use more compute for better results. |
| `recallMaxTokens` | `number` | `1024` | yes | Maximum tokens injected into the prompt per recall. |
| `recallTypes` | `string[]` | `["world","experience"]` | yes | Memory types to recall. Values: `world`, `experience`, `observation`. |
| `recallRoles` | `string[]` | -- | yes | Roles to include in the recall query context. Values: `user`, `assistant`, `system`, `tool`. |
| `recallTopK` | `number` | -- | yes | Maximum number of memory results to return from recall. |
| `recallContextTurns` | `number` | -- | yes | Number of recent conversation turns to include as context in the recall query. |
| `recallMaxQueryChars` | `number` | -- | yes | Maximum character length of the recall query. |
| `recallPromptPreamble` | `string` | -- | yes | Text prepended to the recalled memories block before injection. |
| `retainRoles` | `string[]` | `["user","assistant"]` | yes | Message roles captured during retention. Values: `user`, `assistant`, `system`, `tool`. |
| `retainEveryNTurns` | `number` | `1` | yes | Retain every Nth turn. Set to `2` to retain every other turn, `3` for every third, etc. |
| `retainOverlapTurns` | `number` | -- | yes | Number of turns to overlap between consecutive retain windows. Prevents context loss at boundaries. |
| `excludeProviders` | `string[]` | `[]` | yes | Skip memory operations for these message providers (e.g., `["slack"]`). |
| `llmProvider` | `string` | auto | yes | LLM provider for memory extraction. Auto-detected from the gateway config if not set. |
| `llmModel` | `string` | provider default | yes | LLM model name for extraction. |
| `llmApiKeyEnv` | `string` | -- | yes | Environment variable name containing the LLM API key. |
| `debug` | `boolean` | `false` | yes | Enable debug logging for memory operations. |

### Bootstrap and Agent Map

| Option | Type | Default | Per-agent | Description |
|--------|------|---------|-----------|-------------|
| `bootstrap` | `boolean` | `false` | no | Automatically apply bank configuration on first run when the bank is empty on the server. After the initial bootstrap, use Terraform to manage server state. |
| `agents` | `Record<string, AgentEntry>` | `{}` | no | Per-agent behavioral overrides. Maps agent IDs to their config overrides. |
| `bankMission` | `string` | -- | no | Default bank mission applied automatically to unconfigured banks. |

The `agents` map uses this structure:

```json5
{
  "agents": {
    "my-agent":  { "recallBudget": "high", "recallMaxTokens": 2048 },
    "agent-2":   { "autoRetain": false },
    "ops-agent": { "hindsightApiUrl": "https://hindsight.office.local" }
  }
}
```

## Remote Server Setup

There are two modes for connecting to a remote Hindsight server:

### Single-user mode (no hindclaw-extension)

For setups where access control is not needed, use a static API token:

```json5
{
  "hindsightApiUrl": "https://hindsight.home.local",
  "hindsightApiToken": "your-api-token"
}
```

### Multi-user mode (with hindclaw-extension)

For setups with multiple users, install the hindclaw-extension on the server (see [Installation](../getting-started/installation)) and use JWT authentication:

```json5
{
  "hindsightApiUrl": "https://hindsight.office.local",
  "jwtSecret": "shared-secret-between-plugin-and-server"
}
```

The plugin generates short-lived JWTs (5 min TTL) for each request, embedding the sender identity, agent, channel, and topic. The server extension decodes the JWT, resolves the user, and enforces permissions.

Users, groups, and permissions are managed via the [Terraform provider](../guides/terraform), not in config files.

### Per-agent server routing

Different agents can connect to different servers. Set `hindsightApiUrl` in the per-agent entry:

```json5
// In openclaw.json plugin config, agents section
{
  "agents": {
    "agent-3": {
      "hindsightApiUrl": "https://hindsight.office.local"
    }
  }
}
```

The `jwtSecret` is set at the plugin level (not per-agent) since all agents on the same server share the same secret.

Multi-server topology example:

```
Gateway (jwtSecret configured at plugin level)
  my-agent   (private)  -> hindsightApiUrl: "https://hindsight.home.local"
  agent-2    (private)  -> hindsightApiUrl: "https://hindsight.home.local"
  ops-agent  (company)  -> hindsightApiUrl: "https://hindsight.office.local"
  agent-4    (company)  -> hindsightApiUrl: "https://hindsight.office.local"
  agent-5    (local)    -> no hindsightApiUrl (uses local daemon)
```

## Cross-Agent Recall

An agent can recall memories from other agents' banks by setting `recallFrom` in its per-agent config entry:

```json5
// In openclaw.json plugin config, agents section
{
  "recallFrom": [
    { "bankId": "agent-1" },
    { "bankId": "agent-2", "budget": "high", "maxTokens": 2048 },
    { "bankId": "agent-3", "types": ["world"] }
  ]
}
```

Each entry in `recallFrom` supports:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `bankId` | `string` | required | Target bank ID to recall from. |
| `budget` | `string` | inherits | Recall effort for this bank. Values: `low`, `mid`, `high`. |
| `maxTokens` | `number` | inherits | Max tokens from this bank. |
| `types` | `string[]` | inherits | Memory types to recall from this bank. |
| `tagGroups` | `TagGroup[]` | -- | Tag-based filtering for this bank's recall. |

When access control is active, permissions are checked independently for each target bank. If the requesting user has `recall: false` on a target bank, that bank is silently skipped.

## Client-Enforced vs Server-Enforced Fields

With the hindclaw-extension, most permission fields are enforced server-side via `accept_with()` enrichment (tags, tag_groups, strategy). However, some fields cannot be enforced server-side because the Hindsight `ValidationResult` does not support them. These remain **client-enforced** -- the plugin reads them from its own config or from the resolved permissions returned by the debug endpoint:

| Field | Reason for client enforcement |
|-------|-------------------------------|
| `recallBudget` | No budget field in `ValidationResult` |
| `recallMaxTokens` | No max_tokens field in `ValidationResult` |
| `retainEveryNTurns` | Requires turn count state tracked by the plugin |
| `excludeProviders` | Provider filtering happens before the request reaches the server |
| `llmModel`, `llmProvider` | Extraction model selection is server config, not a per-request override |

These fields can still be set in the plugin config as behavioral overrides.

## User and Group Management

When running with the hindclaw-extension, users, groups, permissions, and strategy scopes are managed via the [Terraform provider](../guides/terraform) -- not via config files. The plugin does not store or resolve any user/group/permission data.

See the [Access Control guide](../guides/access-control) for setup instructions and the [Terraform guide](../guides/terraform) for resource definitions.
