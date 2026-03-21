# Hindclaw Go Client

Generated Go client for the Hindclaw access control API.

## Installation

```bash
go get github.com/mrkhachaturov/hindclaw/hindclaw-clients/go
```

## Usage

```go
import hindclaw "github.com/mrkhachaturov/hindclaw/hindclaw-clients/go"

client := hindclaw.NewAPIClientWithToken("https://hindsight.home.local", "hc_admin_xxxxx")

// List users
users, _, err := client.ExtensionAPI.ListUsers(ctx).Execute()

// Create a group
_, _, err = client.ExtensionAPI.CreateGroup(ctx).CreateGroupRequest(hindclaw.CreateGroupRequest{
    Id: "engineering",
    DisplayName: "Engineering",
}).Execute()
```

## Regenerating

```bash
cd build/hindclaw
python scripts/extract-openapi.py > hindclaw-clients/openapi.json
bash scripts/generate-clients.sh
```
