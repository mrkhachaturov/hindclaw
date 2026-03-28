# hindclaw

CLI for managing [HindClaw](https://github.com/mrkhachaturov/hindclaw) access control on [Hindsight](https://hindsight.vectorize.io) servers.

## Install

```bash
cargo install hindclaw-cli
```

## Quick start

```bash
# Configure a server alias
hindclaw alias set prod https://hindsight.office:8888

# List users
hindclaw admin user list

# Create a user
hindclaw admin user add alice --display-name "Alice"

# Attach a policy
hindclaw admin policy attach allow-recall --user alice --priority 5

# Search marketplace templates
hindclaw template search --tag python

# Install and apply a template
hindclaw template install hindclaw/backend-python --scope server
hindclaw template apply server/hindclaw/backend-python --bank-id my-project --bank-name "My Project"
```

## Commands

```
hindclaw alias set/ls/rm             Server alias management
hindclaw template list/info/search   Discover templates
hindclaw template install/upgrade    Acquire from marketplace
hindclaw template create/update/rm   Manage custom templates
hindclaw template export/import      Portability (JSON files)
hindclaw template apply              Create bank from template
hindclaw admin user ...              User CRUD + channels + keys
hindclaw admin group ...             Group CRUD + members
hindclaw admin policy ...            Policy CRUD + attach/detach
hindclaw admin sa ...                Service account CRUD + keys
hindclaw admin bank-policy ...       Bank policy set/info/rm
hindclaw admin resolve ...           Debug access resolution
hindclaw admin source ...            Marketplace source management
```

## Configuration

Config is stored in `~/.hindclaw/config.json` with 0600 permissions. API keys are never shown in `alias ls` output.

Resolution chain for server connection: `--alias` flag > `HINDCLAW_API_URL` + `HINDCLAW_API_KEY` env vars > default alias.

## Output formats

All commands support `-o pretty` (default on TTY), `-o json`, and `-o yaml`. When piped, output defaults to JSON.

## License

MIT
