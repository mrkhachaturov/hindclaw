---
sidebar_position: 3
title: Terraform Provider
---

# Terraform Provider

The [`mrkhachaturov/hindclaw`](https://registry.terraform.io/providers/mrkhachaturov/hindclaw/latest) Terraform provider manages the full hindclaw stack as code — users, groups, banks, access policies, service accounts, directives, mental models, and bank configs.

## Installation

```hcl
terraform {
  required_providers {
    hindclaw = {
      source = "mrkhachaturov/hindclaw"
    }
  }
}

provider "hindclaw" {
  api_url = "https://hindsight.home.local"
  api_key = var.hindclaw_api_key
}

variable "hindclaw_api_key" {
  type      = string
  sensitive = true
}
```

## Authentication

The provider uses a root API key (`hc_u_root_...`) or a service account key. Both are passed via the `api_key` field or the `HINDCLAW_API_KEY` environment variable.

```bash
export TF_VAR_hindclaw_api_key="hc_u_root_..."
terraform apply
```

The root key is generated on first server start from `HINDCLAW_ROOT_API_KEY`. For CI/CD and automation, create a dedicated service account and use its key instead of the root key. See [Service Accounts](#service-accounts) below.

## File Organization

Split Terraform config by concern for readability:

```
terraform/
├── main.tf               # provider config
├── users.tf              # users + channel mappings
├── groups.tf             # groups (identity-only) + memberships
├── banks.tf              # bank profiles
├── bank_configs.tf       # bank missions + entity labels
├── bank_labels.tf        # locals for shared labels
├── policies.tf           # access policies + attachments
├── service_accounts.tf   # SAs + keys + scoping policies
├── bank_policies.tf      # per-bank strategy config
├── directives.tf         # behavioral rules
├── mental_models.tf      # pre-computed summaries
└── outputs.tf            # SA key outputs (sensitive)
```

---

## Users and Channels

Users are canonical human identities. Channel mappings link platform-specific sender IDs (e.g., `telegram:276243527`) to a user.

```hcl
# users.tf

resource "hindclaw_user" "alice" {
  id           = "alice"
  display_name = "Alice Smith"
  email        = "alice@company.com"
}

resource "hindclaw_user" "bob" {
  id           = "bob"
  display_name = "Bob Jones"
  email        = "bob@company.com"
}

# Channel mappings — one per platform the user communicates from
resource "hindclaw_user_channel" "alice_telegram" {
  user_id          = hindclaw_user.alice.id
  channel_provider = "telegram"
  sender_id        = "111111111"
}

resource "hindclaw_user_channel" "alice_claude_code" {
  user_id          = hindclaw_user.alice.id
  channel_provider = "claude-code"
  sender_id        = "alice@company.com"
}

resource "hindclaw_user_channel" "bob_telegram" {
  user_id          = hindclaw_user.bob.id
  channel_provider = "telegram"
  sender_id        = "222222222"
}
```

When a request arrives with `sender = "telegram:111111111"`, the server resolves it to user `alice` and evaluates her access policies.

### User fields

| Field | Required | Description |
|---|---|---|
| `id` | yes | Canonical user ID used in policies and references |
| `display_name` | yes | Human-readable name |
| `email` | no | Email address (informational) |
| `disable_user` | no | Deactivate without deleting. All SA keys for this user stop working. |
| `force_destroy` | no | Allow destroy even if the user owns service accounts |

---

## Groups

Groups are identity-only collections. They have no permission fields — access is controlled entirely through policies attached to the group.

```hcl
# groups.tf

resource "hindclaw_group" "executives" {
  id           = "executives"
  display_name = "Executive"
}

resource "hindclaw_group" "staff" {
  id           = "staff"
  display_name = "Staff"
}

resource "hindclaw_group" "default" {
  id           = "_default"
  display_name = "Anonymous"
  # No policies attached = no access for unmapped senders by default
}

# Memberships
resource "hindclaw_group_membership" "alice_executives" {
  group_id = hindclaw_group.executives.id
  user_id  = hindclaw_user.alice.id
}

resource "hindclaw_group_membership" "bob_staff" {
  group_id = hindclaw_group.staff.id
  user_id  = hindclaw_user.bob.id
}
```

A user can belong to multiple groups. Policies attached to all their groups are merged when resolving effective permissions.

### Group fields

| Field | Required | Description |
|---|---|---|
| `id` | yes | Group ID. Use `_default` for the fallback group for unmapped senders. |
| `display_name` | yes | Human-readable name |
| `force_destroy` | no | Allow destroy even if the group has members or policy attachments |

---

## Access Policies

Access policies define what actions principals (users, groups, service accounts) can perform on which banks, including behavioral parameters like recall budget and retain roles. Policies are reusable — attach the same policy to multiple groups.

### Policy document data source

Use `data "hindclaw_policy_document"` to build policy JSON from HCL. Each `statement` block maps to one entry in the `statements` array.

```hcl
# policies.tf

# Executive policy — full access, high recall budget
data "hindclaw_policy_document" "executive" {
  statement {
    effect  = "allow"
    actions = ["bank:recall", "bank:reflect", "bank:retain"]
    banks   = ["*"]

    recall_budget     = "high"
    recall_max_tokens = 2048
    retain_roles      = ["user", "assistant"]
  }
}

# Staff policy — read-only, lower budget, filtered recall
data "hindclaw_policy_document" "staff" {
  statement {
    effect  = "allow"
    actions = ["bank:recall", "bank:reflect"]
    banks   = ["*"]

    recall_budget     = "low"
    recall_max_tokens = 512
    retain_roles      = []
  }
}

# Deny staff access to a specific sensitive bank
data "hindclaw_policy_document" "staff_deny_sensitive" {
  statement {
    effect  = "allow"
    actions = ["bank:recall", "bank:reflect"]
    banks   = ["*"]

    recall_budget = "low"
  }

  statement {
    effect  = "deny"
    actions = ["bank:recall", "bank:reflect", "bank:retain"]
    banks   = ["bb9e"]
  }
}

# IAM admin policy — manage users, groups, policies
data "hindclaw_policy_document" "iam_admin" {
  statement {
    effect  = "allow"
    actions = ["iam:*"]
    banks   = ["*"]
  }
}

resource "hindclaw_policy" "executive" {
  id           = "executive"
  display_name = "Executive Access"
  document     = data.hindclaw_policy_document.executive.json
}

resource "hindclaw_policy" "staff" {
  id           = "staff-readonly"
  display_name = "Staff Read-Only"
  document     = data.hindclaw_policy_document.staff.json
}

resource "hindclaw_policy" "iam_admin" {
  id           = "iam-admin"
  display_name = "IAM Administrator"
  document     = data.hindclaw_policy_document.iam_admin.json
}
```

### Policy attachments

Attach policies to users or groups using `hindclaw_policy_attachment`. The `priority` field resolves tie-breaking for single-value behavioral fields when multiple policies apply.

```hcl
# Attach executive policy to the executives group (priority 10 upgrades recall budget)
resource "hindclaw_policy_attachment" "executive_group" {
  policy_id      = hindclaw_policy.executive.id
  principal_type = "group"
  principal_id   = hindclaw_group.executives.id
  priority       = 10
}

# Attach staff policy to the staff group
resource "hindclaw_policy_attachment" "staff_group" {
  policy_id      = hindclaw_policy.staff.id
  principal_type = "group"
  principal_id   = hindclaw_group.staff.id
}

# Attach IAM admin policy directly to alice (user-level)
resource "hindclaw_policy_attachment" "alice_iam_admin" {
  policy_id      = hindclaw_policy.iam_admin.id
  principal_type = "user"
  principal_id   = hindclaw_user.alice.id
}
```

### Policy document fields

**`statement` block:**

| Field | Type | Description |
|---|---|---|
| `effect` | `allow` / `deny` | Grant or explicitly deny the listed actions. Deny overrides allow at any level. |
| `actions` | string[] | Actions to grant or deny. Use `bank:*` for all bank actions, `iam:*` for all control-plane actions. |
| `banks` | string[] | Bank IDs the statement applies to. `"*"` matches all banks. `"yoda::*"` matches all banks prefixed with `yoda::`. |
| `recall_budget` | string | `low`, `mid`, or `high`. Recall cost tier. Most permissive value wins when merging. |
| `recall_max_tokens` | number | Max tokens for recall results. Highest value wins when merging. |
| `recall_tag_groups` | string (JSON) | Tag-based recall filter. Multiple filters are AND-ed together across statements. |
| `retain_roles` | string[] | Message roles to retain: `user`, `assistant`, `system`, `tool`. Unioned across statements. |
| `retain_tags` | string[] | Tags injected on all retained facts. Unioned across statements. |
| `retain_every_n_turns` | number | Retain frequency. Lowest value wins (most frequent). |
| `retain_strategy` | string | Named Hindsight extraction strategy. Most specific principal wins. |
| `llm_model` | string | LLM model override for extraction. Most specific principal wins. |
| `llm_provider` | string | LLM provider override. Most specific principal wins. |
| `exclude_providers` | string[] | Message providers to skip. Unioned across statements. |

### Built-in policies

The server provides built-in policies that cannot be modified:

| Policy ID | Grants |
|---|---|
| `bank:readwrite` | `bank:recall`, `bank:reflect`, `bank:retain` on `*` |
| `bank:readonly` | `bank:recall`, `bank:reflect` on `*` |
| `bank:retain-only` | `bank:retain` on `*` |
| `bank:admin` | All `bank:*` actions on `*` |
| `iam:admin` | All `iam:*` control plane actions |

Attach built-in policies by ID:

```hcl
resource "hindclaw_policy_attachment" "alice_bank_admin" {
  policy_id      = "bank:admin"
  principal_type = "user"
  principal_id   = hindclaw_user.alice.id
}
```

### Actions reference

**Core bank actions:**

| Action | Description |
|---|---|
| `bank:recall` | Retrieve raw memories |
| `bank:reflect` | LLM-synthesized answers (independent of recall) |
| `bank:retain` | Store new memories |

**Extended bank actions:**

| Action | Description |
|---|---|
| `bank:memories:list`, `bank:memories:get`, `bank:memories:delete` | Memory management |
| `bank:mental_models:*` | Mental model CRUD and refresh |
| `bank:directives:*` | Directive management |
| `bank:stats`, `bank:config:update`, `bank:delete` | Bank administration |

**Control-plane actions:**

| Action | Description |
|---|---|
| `iam:users:read`, `iam:users:write` | User management |
| `iam:groups:read`, `iam:groups:write` | Group management |
| `iam:policies:read`, `iam:policies:write` | Policy management |
| `iam:attachments:write` | Attach policies to principals |
| `iam:service_accounts:read`, `iam:service_accounts:write` | Service account management |
| `iam:service_account_keys:write` | API key management |

---

## Service Accounts

Service accounts are machine identities for MCP clients, Claude Code, CI/CD, and Terraform runs. Each SA belongs to exactly one user and inherits that user's effective permissions. An optional scoping policy can narrow (but never broaden) the SA's access below its owner's permissions.

```hcl
# service_accounts.tf

# SA for the Terraform operator (no scoping — full access up to alice's permissions)
resource "hindclaw_service_account" "alice_terraform" {
  id            = "alice-terraform"
  owner_user_id = hindclaw_user.alice.id
  display_name  = "Alice — Terraform"
}

resource "hindclaw_service_account_key" "alice_terraform" {
  service_account_id = hindclaw_service_account.alice_terraform.id
  description        = "Terraform CI key"
}

# SA for Claude Code — scoped to recall + reflect only on two banks
data "hindclaw_policy_document" "alice_claude_scope" {
  statement {
    effect  = "allow"
    actions = ["bank:recall", "bank:reflect"]
    banks   = ["yoda", "r2d2"]

    recall_budget     = "mid"
    recall_max_tokens = 1024
  }
}

resource "hindclaw_policy" "alice_claude_scope" {
  id           = "alice-claude-scope"
  display_name = "Alice Claude Code — Scoped"
  document     = data.hindclaw_policy_document.alice_claude_scope.json
}

resource "hindclaw_service_account" "alice_claude" {
  id                = "alice-claude"
  owner_user_id     = hindclaw_user.alice.id
  display_name      = "Alice — Claude Code"
  scoping_policy_id = hindclaw_policy.alice_claude_scope.id
}

resource "hindclaw_service_account_key" "alice_claude" {
  service_account_id = hindclaw_service_account.alice_claude.id
  description        = "Claude Code dev key"
}
```

The SA's effective access is the intersection of the owner's effective policy and the scoping policy. A scoping policy can only make things more restrictive — it cannot grant permissions the owner doesn't have.

### SA fields

| Field | Required | Description |
|---|---|---|
| `id` | yes | SA identifier |
| `owner_user_id` | yes | User who owns this SA |
| `display_name` | yes | Human-readable label |
| `scoping_policy_id` | no | Optional policy to narrow access. At most one per SA. |

### SA key outputs

SA keys are sensitive. Export them from `outputs.tf` for use in downstream systems:

```hcl
# outputs.tf

output "alice_terraform_key" {
  value     = hindclaw_service_account_key.alice_terraform.api_key
  sensitive = true
}

output "alice_claude_key" {
  value     = hindclaw_service_account_key.alice_claude.api_key
  sensitive = true
}
```

Retrieve after apply:

```bash
terraform output -raw alice_claude_key
```

---

## Banks

Bank resources manage Hindsight bank profiles, missions, and behavioral tuning.

```hcl
# banks.tf

resource "hindclaw_bank" "yoda" {
  bank_id                = "yoda"
  name                   = "Yoda"
  mission                = "Strategic mentor and advisor"
  disposition_skepticism = 3
  disposition_empathy    = 5
}

resource "hindclaw_bank" "r2d2" {
  bank_id  = "r2d2"
  name     = "R2-D2"
  mission  = "Technical operations and infrastructure"
}
```

### Bank configs

Bank configs define the extraction mission, entity labels, and operational modes:

```hcl
# bank_configs.tf

resource "hindclaw_bank_config" "yoda" {
  bank_id = hindclaw_bank.yoda.bank_id
  config = jsonencode({
    retain_mission       = "Extract strategic decisions, leadership patterns, and mentorship moments."
    reflect_mission      = "You are Yoda — a wise strategic mentor with full context of past conversations."
    observations_mission = "Identify recurring themes in decision-making and communication style."
    entity_labels        = local.yoda_labels
  })
}

resource "hindclaw_bank_config" "r2d2" {
  bank_id = hindclaw_bank.r2d2.bank_id
  config = jsonencode({
    retain_mission  = "Extract infrastructure decisions, service configs, and system changes."
    reflect_mission = "You are R2-D2 — a technical operations droid with full system knowledge."
    entity_labels   = local.common_labels
  })
}
```

Bank configs use `jsonencode()` for the config map. Entity labels can be defined as Terraform locals for reuse across banks.

### Entity labels (shared locals)

```hcl
# bank_labels.tf

locals {
  common_person_label = {
    key         = "person"
    description = "Known person. Use only these values."
    type        = "multi-values"
    tag         = true
    values = [
      { value = "alice", description = "Alice Smith — CEO" },
      { value = "bob",   description = "Bob Jones — CTO" },
    ]
  }

  sensitivity_label = {
    key         = "sensitivity"
    description = "Content sensitivity level."
    type        = "single-value"
    tag         = true
    values = [
      { value = "restricted", description = "Confidential — executives only" },
      { value = "internal",   description = "Internal — all staff" },
    ]
  }

  common_labels = [local.common_person_label]
  yoda_labels   = [local.common_person_label, local.sensitivity_label]
}
```

---

## Bank Policies

Bank policies configure context-level strategy routing (per-channel, per-topic overrides) and public access for unmapped senders. This replaces the old `hindclaw_strategy_scope` resource.

```hcl
# bank_policies.tf

resource "hindclaw_bank_policy" "yoda" {
  bank_id  = hindclaw_bank.yoda.bank_id
  document = jsonencode({
    version          = "2026-03-24"
    default_strategy = "yoda-default"
    strategy_overrides = [
      { scope = "channel", value = "telegram",  strategy = "yoda-telegram" },
      { scope = "topic",   value = "12345",      strategy = "yoda-dm-alice" },
    ]
    # No public_access — unknown senders are denied by default
  })
}

resource "hindclaw_bank_policy" "r2d2" {
  bank_id  = hindclaw_bank.r2d2.bank_id
  document = jsonencode({
    version          = "2026-03-24"
    default_strategy = "r2d2-ops"
  })
}
```

To allow public (unmapped) senders — for example, a customer-facing Telegram group — add a `public_access` section:

```hcl
resource "hindclaw_bank_policy" "kb_agent" {
  bank_id  = "kb-agent"
  document = jsonencode({
    version          = "2026-03-24"
    default_strategy = "kb-default"
    public_access = {
      overrides = [
        {
          scope             = "provider"
          value             = "telegram"
          actions           = ["bank:recall", "bank:reflect"]
          recall_budget     = "low"
          recall_max_tokens = 256
        }
      ]
    }
  })
}
```

### Strategy resolution order

When the server needs a retain strategy for a request:

1. Principal's effective access policy — `retain_strategy` on the matching statement (user-attached > group-attached)
2. Bank policy context overrides — most specific match (topic > channel > default)
3. Hindsight built-in default if nothing matches

---

## Directives

Directives are behavioral rules injected into every bank operation:

```hcl
# directives.tf

resource "hindclaw_directive" "no_pii" {
  bank_id  = hindclaw_bank.yoda.bank_id
  name     = "no_pii"
  content  = "Never store personally identifiable information such as passport numbers, payment card details, or home addresses."
}

resource "hindclaw_directive" "strategic_focus" {
  bank_id  = hindclaw_bank.yoda.bank_id
  name     = "strategic_focus"
  content  = "Focus on strategic decisions, priorities, and reasoning. Skip tactical implementation details."
}
```

---

## Mental Models

Mental models run a `reflect` operation on creation and store the result for instant retrieval on future queries:

```hcl
# mental_models.tf

resource "hindclaw_mental_model" "leadership_style" {
  bank_id      = hindclaw_bank.yoda.bank_id
  name         = "Leadership Style"
  source_query = "Summarize this user's leadership approach, decision-making style, and communication preferences."
}

resource "hindclaw_mental_model" "system_overview" {
  bank_id      = hindclaw_bank.r2d2.bank_id
  name         = "System Overview"
  source_query = "Summarize the current infrastructure, key services, and their operational status."
}
```

---

## Data Sources

### Banks list

List all configured banks:

```hcl
data "hindclaw_banks" "all" {}
```

---

## Practical Example

Three users, two agents, role-based access:

| | `yoda` (strategic) | `r2d2` (operations) |
|---|---|---|
| **alice** (executive) | recall + reflect + retain, high budget | recall + reflect + retain, high budget |
| **bob** (staff) | recall + reflect only, low budget | recall + reflect only, low budget |
| **anonymous** | denied | denied |

```hcl
# 1. Users + channels
resource "hindclaw_user" "alice" {
  id           = "alice"
  display_name = "Alice"
}

resource "hindclaw_user" "bob" {
  id           = "bob"
  display_name = "Bob"
}

resource "hindclaw_user_channel" "alice_telegram" {
  user_id          = hindclaw_user.alice.id
  channel_provider = "telegram"
  sender_id        = "111111111"
}

resource "hindclaw_user_channel" "bob_telegram" {
  user_id          = hindclaw_user.bob.id
  channel_provider = "telegram"
  sender_id        = "222222222"
}

# 2. Groups
resource "hindclaw_group" "executives" {
  id           = "executives"
  display_name = "Executive"
}

resource "hindclaw_group" "staff" {
  id           = "staff"
  display_name = "Staff"
}

resource "hindclaw_group_membership" "alice_executives" {
  group_id = hindclaw_group.executives.id
  user_id  = hindclaw_user.alice.id
}

resource "hindclaw_group_membership" "bob_staff" {
  group_id = hindclaw_group.staff.id
  user_id  = hindclaw_user.bob.id
}

# 3. Policies
data "hindclaw_policy_document" "executive" {
  statement {
    effect            = "allow"
    actions           = ["bank:recall", "bank:reflect", "bank:retain"]
    banks             = ["*"]
    recall_budget     = "high"
    recall_max_tokens = 2048
    retain_roles      = ["user", "assistant"]
  }
}

data "hindclaw_policy_document" "staff" {
  statement {
    effect            = "allow"
    actions           = ["bank:recall", "bank:reflect"]
    banks             = ["*"]
    recall_budget     = "low"
    recall_max_tokens = 512
  }
}

resource "hindclaw_policy" "executive" {
  id           = "executive"
  display_name = "Executive Access"
  document     = data.hindclaw_policy_document.executive.json
}

resource "hindclaw_policy" "staff" {
  id           = "staff-readonly"
  display_name = "Staff Read-Only"
  document     = data.hindclaw_policy_document.staff.json
}

# 4. Attach policies to groups
resource "hindclaw_policy_attachment" "executive_group" {
  policy_id      = hindclaw_policy.executive.id
  principal_type = "group"
  principal_id   = hindclaw_group.executives.id
}

resource "hindclaw_policy_attachment" "staff_group" {
  policy_id      = hindclaw_policy.staff.id
  principal_type = "group"
  principal_id   = hindclaw_group.staff.id
}

# 5. Banks + configs
resource "hindclaw_bank" "yoda" {
  bank_id  = "yoda"
  name     = "Yoda"
  mission  = "Strategic mentor and advisor"
}

resource "hindclaw_bank" "r2d2" {
  bank_id  = "r2d2"
  name     = "R2-D2"
  mission  = "Technical operations and infrastructure"
}

resource "hindclaw_bank_config" "yoda" {
  bank_id = hindclaw_bank.yoda.bank_id
  config = jsonencode({
    retain_mission = "Extract strategic decisions and leadership patterns."
    entity_labels  = local.yoda_labels
  })
}

resource "hindclaw_bank_config" "r2d2" {
  bank_id = hindclaw_bank.r2d2.bank_id
  config = jsonencode({
    retain_mission = "Extract infrastructure decisions and system changes."
    entity_labels  = local.common_labels
  })
}

# 6. Service account for Terraform runs
resource "hindclaw_service_account" "terraform" {
  id            = "alice-terraform"
  owner_user_id = hindclaw_user.alice.id
  display_name  = "Terraform"
}

resource "hindclaw_service_account_key" "terraform" {
  service_account_id = hindclaw_service_account.terraform.id
  description        = "Terraform apply key"
}

output "terraform_key" {
  value     = hindclaw_service_account_key.terraform.api_key
  sensitive = true
}
```

## Full Documentation

See the [Terraform Registry docs](https://registry.terraform.io/providers/mrkhachaturov/hindclaw/latest/docs) for the complete resource and data source reference.
