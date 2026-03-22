---
sidebar_position: 3
title: Terraform Provider
---

# Terraform Provider

The [`mrkhachaturov/hindclaw`](https://registry.terraform.io/providers/mrkhachaturov/hindclaw/latest) Terraform provider manages the full hindclaw stack as code — users, groups, banks, permissions, directives, mental models, and bank configs.

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
  api_url = "http://localhost:9077"
  api_key = var.hindclaw_api_key
}

variable "hindclaw_api_key" {
  type      = string
  sensitive = true
}
```

## Authentication

The provider authenticates with a JWT or API key via the `api_key` field. For embedded setups with `jwtSecret`, generate a long-lived admin JWT:

```python
import jwt, time
print(jwt.encode({
    "sub": "admin",
    "client_id": "openclaw",
    "sender": "admin:terraform",
    "iat": int(time.time()),
    "exp": int(time.time()) + 365 * 86400
}, "your-jwt-secret", algorithm="HS256"))
```

Set via environment variable:

```bash
export TF_VAR_hindclaw_api_key="eyJ..."
terraform apply
```

## Resources

### Users and Channels

```hcl
resource "hindclaw_user" "alice" {
  id           = "alice@company.com"
  display_name = "Alice Smith"
  email        = "alice@company.com"
}

resource "hindclaw_user_channel" "alice_telegram" {
  user_id          = hindclaw_user.alice.id
  channel_provider = "telegram"
  sender_id        = "123456789"
}
```

Channel mappings connect external sender IDs to hindclaw users. When a message arrives from `telegram:123456789`, the server resolves it to `alice@company.com`.

### Groups and Memberships

```hcl
resource "hindclaw_group" "staff" {
  id            = "staff"
  display_name  = "Staff"
  recall        = true
  retain        = true
  recall_budget = "mid"
}

resource "hindclaw_group_membership" "alice_staff" {
  group_id = hindclaw_group.staff.id
  user_id  = hindclaw_user.alice.id
}
```

### Banks and Configs

```hcl
resource "hindclaw_bank" "assistant" {
  bank_id                = "assistant"
  name                   = "Assistant"
  mission                = "General purpose assistant"
  disposition_skepticism = 3
  disposition_empathy    = 4
}

resource "hindclaw_bank_config" "assistant" {
  bank_id = hindclaw_bank.assistant.bank_id
  config = jsonencode({
    retain_mission       = "Extract important facts, decisions, and preferences."
    reflect_mission      = "You are a helpful assistant with full context."
    observations_mission = "Identify recurring patterns and preferences."
    entity_labels        = local.assistant_labels
  })
}
```

Bank configs use `jsonencode()` for the config map. Entity labels can be defined as Terraform locals for reuse across banks.

### Permissions

```hcl
# Group-level: staff can recall+retain on assistant bank
resource "hindclaw_bank_permission" "staff_assistant" {
  bank_id    = hindclaw_bank.assistant.bank_id
  scope_type = "group"
  scope_id   = hindclaw_group.staff.id
  recall     = true
  retain     = true
}

# User-level override: alice gets high budget
resource "hindclaw_bank_permission" "alice_assistant" {
  bank_id      = hindclaw_bank.assistant.bank_id
  scope_type   = "user"
  scope_id     = hindclaw_user.alice.id
  recall       = true
  retain       = true
  recall_budget = "high"
}
```

User permissions override group permissions. Use this for per-user access restrictions or elevated privileges.

### Directives

```hcl
resource "hindclaw_directive" "no_pii" {
  bank_id   = hindclaw_bank.assistant.bank_id
  name      = "no_pii"
  content   = "Never store personally identifiable information."
  is_active = true
}
```

### Mental Models

```hcl
resource "hindclaw_mental_model" "user_profile" {
  bank_id      = hindclaw_bank.assistant.bank_id
  name         = "User Profile"
  source_query = "Summarize the user's background, preferences, and current projects."
  max_tokens   = 500
}
```

Mental models run a `reflect` operation on creation and store the result for instant retrieval on future queries.

### Entity Labels (via locals)

```hcl
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

  assistant_labels = [local.common_person_label]
}
```

Define labels as locals for reuse across multiple bank configs.

## Data Sources

### Resolved Permissions

Verify the permission cascade for a specific sender:

```hcl
data "hindclaw_resolved_permissions" "check" {
  bank   = hindclaw_bank.assistant.bank_id
  sender = "telegram:123456789"
  agent  = "assistant"
}

output "alice_can_recall" {
  value = data.hindclaw_resolved_permissions.check.recall
}
```

### Banks List

```hcl
data "hindclaw_banks" "all" {}
```

## File Organization

Split Terraform config by concern for readability:

```
terraform/
├── main.tf           # provider config
├── users.tf          # users + channel mappings
├── groups.tf         # groups + memberships
├── banks.tf          # bank profiles + dispositions
├── bank_configs.tf   # missions + entity labels
├── bank_labels.tf    # locals for shared labels
├── permissions.tf    # group + user permissions
├── directives.tf     # per-bank behavioral rules
├── mental_models.tf  # pre-computed reflect summaries
└── outputs.tf        # verification data sources
```

## Full Documentation

See the [Terraform Registry docs](https://registry.terraform.io/providers/mrkhachaturov/hindclaw/latest/docs) for complete resource and data source reference.
