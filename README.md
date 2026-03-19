<p align="center">
  <img src=".github/assets/hindclaw.png" alt="HindClaw">
</p>

<p align="center">
  Production memory for OpenClaw agent fleets — per-user access control, cross-agent recall, and infrastructure-as-code bank management. Powered by Hindsight.
</p>

<p align="center">
  <a href="https://www.npmjs.com/package/hindclaw"><img src="https://img.shields.io/npm/v/hindclaw?style=flat-square&color=0f766e" alt="npm"></a>
  <img src="https://img.shields.io/badge/license-MIT-10b981?style=flat-square" alt="License">
  <img src="https://img.shields.io/badge/node-%3E%3D22-c2410c?style=flat-square" alt="Node">
</p>

<p align="center">
  <a href="docs/">Documentation</a> &middot;
  <a href="https://hindsight.vectorize.io">Hindsight</a> &middot;
  <a href="https://openclaw.ai">OpenClaw</a>
</p>

---

## Why HindClaw?

Built on [Hindsight](https://hindsight.vectorize.io) — the highest-scoring agent memory system on the [LongMemEval benchmark](https://vectorize.io/#:~:text=The%20New%20Leader%20in%20Agent%20Memory).

The official Hindsight plugin gives you auto-capture and auto-recall. HindClaw adds what you need to run it in production:

### Per-User Access Control

RBAC for agent memory. Users inherit permissions from groups, banks override per-role.

```mermaid
graph LR
    MSG[Message from user-1] --> RESOLVE[Resolve identity]
    RESOLVE --> GROUPS[Groups: group-1, group-2]
    GROUPS --> MERGE[Merge permissions]
    MERGE --> BANK{Bank override?}
    BANK -->|yes| OVERRIDE[Apply bank permissions]
    BANK -->|no| GLOBAL[Use global defaults]
    OVERRIDE --> RESULT[recall: true, budget: high]
    GLOBAL --> RESULT
```

### Cross-Agent Recall

One agent queries multiple banks in parallel. Permissions checked per-bank.

```mermaid
graph LR
    Q[agent-1 recall query] --> B1[bank: agent-1]
    Q --> B2[bank: agent-2]
    Q --> B3[bank: agent-3]
    B1 -->|recall: true| R1[results]
    B2 -->|recall: true| R2[results]
    B3 -->|recall: false| SKIP[skipped]
    R1 --> MERGE[Merge + interleave]
    R2 --> MERGE
    MERGE --> INJECT[Inject into prompt]
```

### Named Retain Strategies

Different conversation topics routed to different extraction strategies.

```mermaid
graph LR
    MSG[Incoming message] --> TOPIC{Topic ID?}
    TOPIC -->|280304| DEEP[deep-analysis strategy]
    TOPIC -->|280418| LIGHT[lightweight strategy]
    TOPIC -->|other| DEFAULT[bank default strategy]
    DEEP --> RETAIN1[Verbose extraction]
    LIGHT --> RETAIN2[Concise extraction]
    DEFAULT --> RETAIN3[Standard extraction]
```

### Infrastructure as Code

`hindclaw plan` shows what will change. `hindclaw apply` syncs it. Like Terraform for memory banks.

```mermaid
graph LR
    FILE[Bank config files] --> PLAN[hindclaw plan]
    PLAN --> DIFF{Changes?}
    DIFF -->|none| OK[Up to date]
    DIFF -->|yes| SHOW[Show diff]
    SHOW --> APPLY[hindclaw apply]
    APPLY --> CONFIRM{Confirm?}
    CONFIRM -->|yes| SYNC[Sync to Hindsight]
    CONFIRM -->|no| CANCEL[Cancelled]
```

### Session Start Context

Mental models loaded before the first message — no cold start.

```mermaid
graph LR
    START[Session starts] --> LOAD[Load mental models]
    LOAD --> M1[Project context]
    LOAD --> M2[User preferences]
    M1 --> INJECT[Inject into system prompt]
    M2 --> INJECT
    INJECT --> READY[Agent ready with full context]
    READY --> MSG1[First user message]
```

### Reflect on Recall

Instead of raw memory retrieval, the agent reasons over its memories.

```mermaid
graph LR
    Q[User question] --> MODE{Reflect enabled?}
    MODE -->|yes| REFLECT[Hindsight reflect API]
    MODE -->|no| RECALL[Hindsight recall API]
    REFLECT --> REASON[LLM reasons over memories]
    REASON --> ANSWER[Grounded response]
    RECALL --> RAW[Raw memory list]
    RAW --> ANSWER
```

### Multi-Server Support

Per-agent infrastructure routing — one gateway, multiple Hindsight servers.

```mermaid
graph LR
    GW[Gateway] --> A1[agent-1]
    GW --> A2[agent-2]
    GW --> A3[agent-3]
    GW --> A4[agent-4]
    A1 --> HOME[Home server]
    A2 --> HOME
    A3 --> OFFICE[Office server]
    A4 --> LOCAL[Local daemon]
```

### Zero-Config Bootstrap

Set `bootstrap: true` and start the gateway. Bank configs applied automatically on first run.

```mermaid
graph LR
    START[Gateway starts] --> CHECK{Bank empty?}
    CHECK -->|yes| APPLY[Auto-apply config]
    CHECK -->|no| SKIP[Already configured]
    APPLY --> READY[Bank ready]
    SKIP --> READY
```

---

## Quick Start

### 1. Install

```bash
openclaw plugins install hindclaw
```

### 2. Configure

Add to your `openclaw.json` (or a `$include`'d config file):

```json5
{
  "plugins": {
    "entries": {
      "hindclaw": {
        "enabled": true,
        "config": {
          "dynamicBankGranularity": ["agent"],
          "bootstrap": true
        }
      }
    }
  }
}
```

### 3. Start

```bash
openclaw gateway
```

That's it — memories are captured and recalled automatically.
The plugin starts a local Hindsight daemon on first run (requires Python 3.11+ and `uv`).

> For bank configs, access control, strategies, and multi-server setups, see the [full documentation](docs/).

---

## Features

### Bank Management

Define agent memory banks as JSON5 files — missions, entity labels, directives, dispositions. All version-controlled.

```bash
hindclaw plan --all     # preview changes
hindclaw apply --all    # sync to Hindsight
hindclaw import --agent agent-1 --output ./banks/agent-1.json5
```

See [CLI Reference](docs/cli.md).

### Access Control

Users, groups, and bank-level permission overrides. Tag-based recall filtering with Hindsight's `tag_groups` API (AND/OR/NOT boolean logic).

```json5
// groups/group-1.json5
{
  "displayName": "Executive",
  "members": ["user-1"],
  "recall": true,
  "retain": true,
  "recallBudget": "high",
  "recallTagGroups": null  // no filter — sees everything
}
```

See [Access Control](docs/access-control.md).

### Named Strategies

Route different conversation topics to different extraction strategies:

```json5
// In bank config
{
  "retain": {
    "strategies": {
      "deep-analysis": { "topics": ["280304"] },
      "lightweight":   { "topics": ["280418"] }
    }
  }
}
```

See [Bank Configuration](docs/bank-config.md).

### Cross-Agent Recall

An agent can recall from multiple banks. Permissions are checked per-bank — no unauthorized cross-reads.

```json5
{
  "recallFrom": ["agent-1", "agent-2", "agent-3"],
  "recallBudget": "high"
}
```

See [Configuration](docs/configuration.md).

---

## Documentation

| Guide | Description |
|-------|-------------|
| [Configuration](docs/configuration.md) | Plugin config, behavioral defaults, per-agent overrides |
| [Bank Configuration](docs/bank-config.md) | Missions, entity labels, strategies, `$include` directives |
| [Access Control](docs/access-control.md) | Users, groups, permissions, resolution algorithm |
| [CLI Reference](docs/cli.md) | `hindclaw plan`, `apply`, `import`, `init` |
| [Development](docs/development.md) | Building, testing, contributing |

---

## Migration from @vectorize-io/hindsight-openclaw

```bash
openclaw plugins remove @vectorize-io/hindsight-openclaw
openclaw plugins install hindclaw
```

Bank ID scheme is compatible — existing memories are preserved.
All plugin-level options use the same names, including `bankMission`.
Per-agent bank config files use `retain_mission` for the same purpose (server-side field name).

---

## Links

- [Hindsight](https://hindsight.vectorize.io) — the memory engine
- [OpenClaw](https://openclaw.ai) — the agent framework
- [GitHub](https://github.com/mrkhachaturov/hindsight-openclaw-pro)

## License

MIT — see [LICENSE](LICENSE)

Based on [`@vectorize-io/hindsight-openclaw`](https://github.com/vectorize-io/hindsight/tree/main/hindsight-integrations/openclaw) (MIT, Copyright (c) 2025 Vectorize AI, Inc.)
