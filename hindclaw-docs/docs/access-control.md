# Access Control

Layered permission model: users belong to groups, groups define defaults, banks override per-group or per-user. All access control data lives in the Hindsight PostgreSQL database and is managed through the [Terraform provider](https://registry.terraform.io/providers/mrkhachaturov/hindclaw).

There are no config files for access control. See the [Access Control Guide](./guides/access-control) for a full walkthrough.

## Permission Model

```
Users
  └── belong to Groups (via memberships)
        └── Groups define permission defaults
              └── Banks override per-group or per-user
```

Resolution order (most specific wins):

1. **Merge global groups** -- collect all user's groups, merge with rules below
2. **Bank `_default` baseline** -- if bank has a `_default` permission entry, start there
3. **Bank group overlay** -- merge bank-level group entries for this user's groups
4. **Bank user override** -- apply per-user override if defined

Banks without permission overrides fall through to global group defaults.

## Managing with Terraform

The `mrkhachaturov/hindclaw` provider manages users, groups, memberships, and permissions as standard Terraform resources.

### Provider configuration

```hcl
terraform {
  required_providers {
    hindclaw = {
      source = "hindclaw.pro/mrkhachaturov/hindclaw"
    }
  }
}

provider "hindclaw" {
  api_url = "https://hindsight.home.local"   # or HINDCLAW_API_URL
  api_key = var.hindclaw_api_key             # or HINDCLAW_API_KEY
}
```

### Users and channel mappings

```hcl
resource "hindclaw_user" "alice" {
  id           = "alice"
  display_name = "Alice"
  email        = "alice@example.com"
}

resource "hindclaw_user_channel" "alice_telegram" {
  user_id          = hindclaw_user.alice.id
  channel_provider = "telegram"
  sender_id        = "123456"
}

resource "hindclaw_user_channel" "alice_slack" {
  user_id          = hindclaw_user.alice.id
  channel_provider = "slack"
  sender_id        = "U123456"
}
```

### Groups

```hcl
resource "hindclaw_group" "executives" {
  id               = "executives"
  display_name     = "Executive"
  recall           = true
  retain           = true
  retain_roles     = ["user", "assistant", "tool"]
  retain_tags      = ["role:executive"]
  recall_budget    = "high"
  recall_max_tokens = 2048
  recall_tag_groups = null   # no filter -- sees everything
}

resource "hindclaw_group" "staff" {
  id                   = "staff"
  display_name         = "Staff"
  recall               = true
  retain               = true
  retain_roles         = ["assistant"]
  retain_tags          = ["role:staff"]
  retain_every_n_turns = 2
  recall_budget        = "low"
  recall_max_tokens    = 512
  recall_tag_groups    = jsonencode([
    { not = { tags = ["sensitivity:restricted"], match = "any_strict" } }
  ])
  llm_provider = "openai"
  llm_model    = "gpt-4o-mini"
}

resource "hindclaw_group" "sales_team" {
  id           = "sales-team"
  display_name = "Sales Team"
  recall_tag_groups = jsonencode([
    { tags = ["department:sales"], match = "any" }
  ])
  retain_tags = ["department:sales"]
}
```

### Memberships

```hcl
resource "hindclaw_group_membership" "alice_executives" {
  group_id = hindclaw_group.executives.id
  user_id  = hindclaw_user.alice.id
}

resource "hindclaw_group_membership" "bob_staff" {
  group_id = hindclaw_group.staff.id
  user_id  = hindclaw_user.bob.id
}

resource "hindclaw_group_membership" "bob_sales" {
  group_id = hindclaw_group.sales_team.id
  user_id  = hindclaw_user.bob.id
}
```

### Bank-level permission overrides

```hcl
# On advisor bank: staff can recall but not retain
resource "hindclaw_bank_permission" "advisor_staff" {
  bank_id    = "advisor"
  scope_type = "group"
  scope_id   = hindclaw_group.staff.id
  recall     = true
  retain     = false
}

# On ops-agent bank: Bob gets elevated recall
resource "hindclaw_bank_permission" "ops_bob" {
  bank_id           = "ops-agent"
  scope_type        = "user"
  scope_id          = hindclaw_user.bob.id
  recall_budget     = "high"
  recall_max_tokens = 2048
}
```

## Group Fields

Every field below can be set at the group level, and overridden at the bank level per-group or per-user.

| Field | Type | Description |
|-------|------|-------------|
| `display_name` | string | Human-readable name |
| `recall` | boolean | Can read from memory |
| `retain` | boolean | Can write to memory |
| `retain_roles` | string[] | Message roles retained: `user`, `assistant`, `system`, `tool` |
| `retain_tags` | string[] | Tags added to all retained facts |
| `retain_every_n_turns` | number | Retain every Nth turn |
| `retain_strategy` | string | Named retain strategy (from cascade) |
| `recall_budget` | string | Recall effort: `low`, `mid`, `high` |
| `recall_max_tokens` | number | Max tokens injected per turn |
| `recall_tag_groups` | TagGroup[] or null | Tag filter for recall. `null` = no filter. |
| `llm_model` | string | LLM model for extraction |
| `llm_provider` | string | LLM provider for extraction |
| `exclude_providers` | string[] | Skip these message providers |

## Merge Rules (multiple groups)

When a user belongs to multiple groups:

| Field | Rule |
|-------|------|
| `recall`, `retain` | Most permissive wins (`true > false`) |
| `retain_roles`, `retain_tags` | Unioned |
| `recall_budget` | Most permissive (`high > mid > low`) |
| `recall_max_tokens` | Highest value wins |
| `recall_tag_groups` | AND-ed together |
| `llm_model`, `llm_provider` | Alphabetically first group that defines it wins |
| `retain_every_n_turns` | Lowest value wins (most frequent) |
| `exclude_providers` | Unioned (most restrictive) |
| `retain_strategy` | From strategy cascade (separate resolution) |

## Tag-Based Filtering

`recall_tag_groups` uses Hindsight's `tag_groups` API for boolean filtering:

```json5
// See everything (no filter)
"recall_tag_groups": null

// Exclude restricted content
"recall_tag_groups": [
  {"not": {"tags": ["sensitivity:restricted"], "match": "any_strict"}}
]

// Include only department content (plus untagged)
"recall_tag_groups": [
  {"tags": ["department:sales"], "match": "any"}
]
```

Tags come from two sources:
1. **Extension-injected** -- `retain_tags` from groups plus automatic `user:<id>` tags, injected via `accept_with()` during retain
2. **LLM-extracted** -- entity labels with `tag: true` in bank config

Both merge into a single `tags` array on each fact.
