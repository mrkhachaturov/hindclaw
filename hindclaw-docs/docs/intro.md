---
sidebar_position: 1
slug: /intro
title: What is hindclaw?
---

# What is hindclaw?

hindclaw is a production-grade [Hindsight](https://hindsight.vectorize.io) memory system for [OpenClaw](https://github.com/openclaw/openclaw). It consists of two components: a **thin plugin** that generates JWTs and sends standard Hindsight API calls, and a **server extension** (`hindclaw-extension`) that enforces access control, resolves permissions, and enriches requests with tags and strategies. Together they give your AI agent fleet long-term memory with per-agent configuration, multi-bank recall, named retain strategies, and infrastructure-as-code management.

## Two Dimensions

Every message resolves along two orthogonal axes:

**WHO** -- permissions enforced server-side by the hindclaw-extension. Users, groups, and bank-level overrides are managed via the [Terraform provider](https://registry.terraform.io/providers/mrkhachaturov/hindclaw/latest). Resolution follows 4 layers (global group defaults -> bank `_default` baseline -> bank group overlay -> bank user override) with 11 configurable fields at every layer: LLM model, token budget, extraction depth, tag visibility, retention frequency.

**HOW** -- strategy resolved per scope via a 5-level cascade (agent -> channel -> topic -> group -> user). Each scope routes to a named strategy with its own extraction mission, mode, and entity labels. Strategy resolution and tag enrichment happen server-side.

```mermaid
graph TD
    MSG["Message: user + bank + topic"] --> PLUGIN["Plugin generates JWT\n(sender, agent, channel, topic)"]
    PLUGIN --> SERVER["Hindsight API Server"]
    SERVER --> TENANT["HindclawTenant\nJWT -> user identity"]
    TENANT --> VALIDATOR["HindclawValidator\nresolve permissions + strategy"]
    VALIDATOR --> R{"recall?"}
    VALIDATOR --> W{"retain?"}
    R -->|true| RECALL["accept_with(tag_groups)\nserver-side filtering"]
    R -->|false| NO_R["reject"]
    W -->|true| RETAIN["accept_with(tags, strategy)\nserver-side enrichment"]
    W -->|false| NO_W["reject"]
```

Permission resolution, tag injection, and strategy selection all happen server-side in the hindclaw-extension. The plugin is a thin adapter that generates a JWT and sends standard Hindsight API calls. Every combination of **(user x bank x topic)** can produce different behavior.

## Core Features

**Per-agent bank configs** -- each agent gets its own retain mission, entity labels, dispositions, and directives. Bank configs, users, groups, permissions, directives, and mental models are managed via the [Terraform provider](https://registry.terraform.io/providers/mrkhachaturov/hindclaw/latest).

**Multi-bank recall** -- agents read from multiple banks in parallel. A strategic advisor recalls from finance, marketing, and ops banks simultaneously.

**Named retain strategies** -- map conversation topics to extraction profiles. Strategic conversations get deep analysis, daily chats get lightweight extraction. Strategies can also be assigned per user group.

**Access control** -- server-side via hindclaw-extension. Users belong to groups. Groups define defaults. Banks override per-group or per-user. Anonymous users blocked by default. JWT authentication for plugins acting on behalf of users. Users and groups are managed via the [Terraform provider](https://registry.terraform.io/providers/mrkhachaturov/hindclaw/latest).

**Infrastructure as Code** -- the **[terraform-provider-hindclaw](https://registry.terraform.io/providers/mrkhachaturov/hindclaw/latest)** manages the full stack -- users, groups, permissions, directives, mental models, and bank configs -- as standard Terraform resources. All Hindsight infrastructure is declared in `.tf` files and applied with `terraform apply`.

**Session start context** -- mental models loaded before the first message. No cold start.

**Reflect-on-recall** -- use Hindsight's reflect API instead of raw recall for richer, reasoned responses.

**Multi-server** -- per-agent infrastructure routing. One gateway, multiple Hindsight servers (home, office, local daemon).

## Built on Hindsight

[Hindsight](https://hindsight.vectorize.io) is a biomimetic memory system for AI agents with semantic, BM25, graph, and temporal retrieval. hindclaw is a client that maps OpenClaw concepts (agents, channels, topics, users) onto Hindsight capabilities (banks, strategies, tags, tag_groups).

:::tip Looking for a managed solution?
Skip the self-hosting and use [Hindsight Cloud](https://ui.hindsight.vectorize.io/signup) — managed memory infrastructure by [Vectorize](https://vectorize.io), the team behind Hindsight.
:::

## Next Steps

- [Installation](./getting-started/installation) -- set up the plugin and (optionally) the server extension
- [Terraform Provider](./guides/terraform) -- manage bank configs, users, groups, and permissions as code
- [Access Control](./guides/access-control) -- set up multi-user permissions via hindclaw-extension
- [Configuration Reference](./reference/configuration) -- plugin and JWT configuration
