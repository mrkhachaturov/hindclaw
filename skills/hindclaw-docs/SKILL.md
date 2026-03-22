---
name: hindclaw-docs
description: HindClaw documentation for AI agents. Use this to learn about access control, Terraform provider, multi-bank recall, session context, and configuration for Hindsight memory infrastructure.
---

# HindClaw Documentation Skill

Production memory infrastructure for AI agents. Server-side access control, Terraform-managed banks, and multi-agent memory with per-user permissions. Built on Hindsight by Vectorize.

## When to Use This Skill

Use this skill when you need to:
- Set up HindClaw (server extension + OpenClaw plugin)
- Configure access control (JWT auth, users, groups, permissions)
- Use the Terraform provider for infrastructure as code
- Set up multi-bank recall for agents
- Configure session context and reflect
- Understand retain strategies and entity labels
- Run multi-server configurations
- Debug permission resolution

## Documentation Structure

All documentation is in `references/` organized by category:

```
references/
├── intro.md                        # START HERE — what is HindClaw
├── getting-started/
│   ├── installation.md             # Install extension + plugin
│   └── verify.md                   # Verify the setup works
├── guides/
│   ├── access-control.md           # JWT auth, users, groups, permissions
│   ├── terraform.md                # Terraform provider for IaC
│   ├── multi-bank-recall.md        # Cross-bank recall for agents
│   ├── session-context.md          # Mental models on session start
│   ├── reflect.md                  # Reflect-on-recall
│   └── multi-server.md             # Multiple Hindsight servers
├── reference/
│   └── configuration.md            # Plugin + extension config reference
└── development.md                  # Development setup
```

## How to Find Documentation

### 1. Find Files by Pattern (use Glob tool)

```bash
# All guides
references/guides/*.md

# Getting started
references/getting-started/*.md

# Configuration reference
references/reference/*.md
```

### 2. Search Content (use Grep tool)

```bash
# Search for concepts
pattern: "JWT"                # Authentication
pattern: "permission"         # Access control
pattern: "terraform"          # Infrastructure as code
pattern: "bank"               # Memory banks
pattern: "strategy"           # Retain strategies
pattern: "entity_label"       # Entity labels
pattern: "recall"             # Multi-bank recall
```

### 3. Read Full Documentation (use Read tool)

```
references/intro.md
references/guides/access-control.md
references/reference/configuration.md
```

## Start Here

Read the intro to understand the two components (plugin + server extension), then the access control guide for the permission model:

```
references/intro.md
references/guides/access-control.md
```

## Key Concepts

- **HindClaw Extension**: Server-side Hindsight extensions (JWT auth, permission enforcement, tag injection, REST API)
- **HindClaw Plugin**: OpenClaw gateway plugin (signs JWTs, auto-starts embed daemon)
- **Terraform Provider**: Manage users, groups, banks, permissions, directives, mental models as code
- **Permission Cascade**: 4-layer resolution (global defaults -> bank baseline -> bank group -> bank user)
- **Retain Strategies**: Named extraction profiles per scope (agent -> channel -> topic -> group -> user)
- **Entity Labels**: Controlled vocabulary for consistent fact classification with multilingual aliases
- **Multi-Bank Recall**: Agents read from multiple banks in parallel with per-bank permission checks

## Packages

- `hindclaw-extension` (PyPI): Server-side extensions for Hindsight API
- `terraform-provider-hindclaw` (Terraform Registry): Infrastructure as code
- `hindclaw-openclaw` (npm): OpenClaw gateway plugin

## Notes

- Built on Hindsight by Vectorize — the memory engine
- Server extension enforces all access control — plugin is a thin adapter
- All permissions resolved server-side, never client-side
- Terraform is the recommended way to manage infrastructure
