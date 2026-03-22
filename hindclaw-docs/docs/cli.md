# CLI Reference

Terraform-style management of Hindsight bank configurations. Local bank config files are the source of truth.

## Commands

### `hindclaw plan`

Preview what will change without modifying the server.

```bash
hindclaw plan --all              # all configured agents
hindclaw plan --agent agent-1    # single agent
```

Output:

```
# bank.agent-1 (agent-1)

  + retain_strategies
      + {
      +   "detailed": {
      +     "retain_extraction_mode": "verbose",
      +     "retain_mission": "Extract financial metrics..."
      +   }
      + }

  ~ retain_mission
    "Extract financial data..." -> "Extract financial metrics, P&L, cashflow..."

  - old_directive
    "Deprecated instruction that will be removed"

Plan: 2 to add, 1 to change, 1 to destroy.
```

### `hindclaw apply`

Show plan, ask for confirmation, apply changes.

```bash
hindclaw apply --all
hindclaw apply --agent agent-1
hindclaw apply --agent agent-1 --auto-approve   # skip confirmation (CI)
```

### `hindclaw import`

Pull current server state into a local file.

```bash
hindclaw import --agent agent-1 --output ./banks/agent-1.json5
```

## Options

| Option | Description |
|--------|-------------|
| `--agent <id>` | Target a single agent |
| `--all` | Target all configured agents |
| `--config <path>` | Config file path (default: `OPENCLAW_CONFIG_PATH` or `.openclaw/openclaw.json`) |
| `--api-url <url>` | Override Hindsight API URL |
| `--auto-approve` / `-y` | Skip confirmation prompt |

:::note
The CLI manages **bank configurations** only (missions, dispositions, entity labels, directives, strategies). Users, groups, and permissions are managed via the [Terraform provider](https://registry.terraform.io/providers/mrkhachaturov/hindclaw/latest) or the REST API at `/ext/hindclaw/*`. See [Access Control](./access-control) for details.
:::
