---
sidebar_position: 1
slug: /intro
---

# What is hindclaw?

hindclaw is a production-grade [Hindsight](https://hindsight.vectorize.io) memory plugin for [OpenClaw](https://github.com/openclaw/openclaw). It gives your AI agent fleet long-term memory with per-agent configuration, multi-bank recall, named retain strategies, and infrastructure-as-code management.

## Features

- **Per-agent bank configs** -- each agent gets its own retain mission, entity labels, dispositions, and directives (JSON5 files)
- **Multi-bank recall** -- agents read from multiple banks in parallel (round-robin interleave)
- **Named retain strategies** -- map conversation topics to extraction profiles (deep analysis, lightweight, review)
- **Session start context** -- inject mental models at session start
- **Reflect-on-recall** -- use reflect instead of recall for richer context injection
- **Infrastructure as Code** -- `hindclaw plan/apply/import` CLI to sync bank configs (like Terraform for memory banks)
- **Stateless client** -- bankId per-call, no instance state, enables multi-bank operations

## Quick Start

### 1. Install and configure hindsight-embed

```bash
uv tool install hindsight-embed
hindsight-embed configure -p openclaw
```

### 2. Install the plugin

```bash
openclaw plugins install hindclaw
```

### 3. Create bank configs

Create JSON5 files in `.openclaw/banks/` for each agent:

```json5
// .openclaw/banks/yoda.json5
{
  "bank_id": "yoda",
  "retain_mission": "Extract strategic decisions, priorities, cross-departmental patterns.",
  "disposition_skepticism": 4,
  "disposition_literalism": 2,
  "disposition_empathy": 3,
  "entity_labels": [
    {
      "key": "department",
      "description": "Which AstraTeam department",
      "type": "multi-values",
      "tag": true,
      "values": [
        {"value": "motors", "description": "AstroMotors"},
        {"value": "detail", "description": "AstroDetail"},
        {"value": "estate", "description": "AstraEstate"}
      ]
    }
  ]
}
```

### 4. Restart the gateway

```bash
just restart
```

The plugin auto-discovers bank configs, bootstraps them to the Hindsight server, and starts memory operations.

## Architecture

```
User (Telegram/Slack) --> OpenClaw Gateway --> hindclaw plugin --> Hindsight API --> PostgreSQL
```

hindclaw sits between OpenClaw and Hindsight. It handles:
- **Recall hook** (before_prompt_build) -- retrieves relevant memories and injects them into the prompt
- **Retain hook** (agent_end) -- extracts facts from conversations and stores them
- **Session start hook** -- loads mental models for context
- **Bank config sync** -- keeps server state in sync with local JSON5 files

## Built on Hindsight

[Hindsight](https://hindsight.vectorize.io) is a biomimetic memory system for AI agents. It provides semantic, BM25, graph, and temporal retrieval strategies. hindclaw is a client that maps OpenClaw concepts (agents, channels, topics) onto Hindsight capabilities (banks, strategies, tags).

## Links

- [GitHub](https://github.com/mrkhachaturov/hindsight-openclaw-pro)
- [npm](https://www.npmjs.com/package/hindclaw)
- [Hindsight](https://hindsight.vectorize.io)
- [OpenClaw](https://github.com/openclaw/openclaw)
