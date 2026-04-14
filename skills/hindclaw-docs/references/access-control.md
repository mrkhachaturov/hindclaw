# Access Control

Policy-based model: policies are attached to users, groups, and service accounts. Deny takes precedence over allow. All access control data lives in the Hindsight PostgreSQL database and is managed through the [Terraform provider](https://registry.terraform.io/providers/mrkhachaturov/hindclaw).

There are no config files for access control. See the [Access Control Guide](./guides/access-control) for a full walkthrough.

## Permission Model

```
Policies
  └── attached to Users, Groups, or Service Accounts
        └── evaluated per endpoint (IAM actions)
              └── deny takes precedence over allow
```

Each policy contains one or more statements. Each statement targets specific IAM actions (e.g., `bank:retain`, `bank:recall`, `iam:admin`) with an effect of `allow` or `deny`.

When a user makes a request, all policies attached to that user (directly and via group memberships) are collected and evaluated. If any policy denies the action, access is denied regardless of other allows.

## Managing with Terraform

The `mrkhachaturov/hindclaw` provider manages users, groups, memberships, policies, policy attachments, and service accounts as standard Terraform resources.

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

### Groups (identity only)

Groups are identity constructs. They have no permission fields. Permissions are granted by attaching policies to the group.

```hcl
resource "hindclaw_group" "executives" {
  id           = "executives"
  display_name = "Executive"
}

resource "hindclaw_group" "staff" {
  id           = "staff"
  display_name = "Staff"
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
```

### Policies and attachments

```hcl
# Policy granting full recall and retain on all banks
resource "hindclaw_policy" "exec_memory" {
  id          = "exec-memory"
  display_name = "Executive Memory Access"

  statement {
    effect  = "allow"
    actions = ["bank:recall", "bank:retain"]
    resources = ["*"]
  }
}

# Policy granting recall-only on all banks, deny retain
resource "hindclaw_policy" "staff_readonly" {
  id           = "staff-readonly"
  display_name = "Staff Read-Only Memory"

  statement {
    effect  = "allow"
    actions = ["bank:recall"]
    resources = ["*"]
  }

  statement {
    effect  = "deny"
    actions = ["bank:retain"]
    resources = ["*"]
  }
}

# Attach exec policy to executives group
resource "hindclaw_policy_attachment" "exec_memory_attach" {
  policy_id   = hindclaw_policy.exec_memory.id
  target_type = "group"
  target_id   = hindclaw_group.executives.id
}

# Attach staff policy to staff group
resource "hindclaw_policy_attachment" "staff_readonly_attach" {
  policy_id   = hindclaw_policy.staff_readonly.id
  target_type = "group"
  target_id   = hindclaw_group.staff.id
}
```

### Service accounts

Service accounts are non-human principals used by automation, Terraform itself, or other systems. They authenticate via API key and have policies attached the same way as users.

```hcl
resource "hindclaw_service_account" "terraform_admin" {
  id           = "terraform-admin"
  display_name = "Terraform Admin"
}

resource "hindclaw_policy_attachment" "terraform_admin_iam" {
  policy_id   = hindclaw_policy.iam_admin.id
  target_type = "service_account"
  target_id   = hindclaw_service_account.terraform_admin.id
}
```

## Tag-Based Filtering

`recall_tag_groups` on bank policies uses Hindsight's `tag_groups` API for boolean filtering:

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
1. **Extension-injected** -- `retain_tags` from bank policies plus automatic `user:<id>` tags, injected via `accept_with()` during retain
2. **LLM-extracted** -- entity labels with `tag: true` in bank config

Both merge into a single `tags` array on each fact.
