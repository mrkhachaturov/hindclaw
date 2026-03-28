# Hindclaw Rust Client

Rust client for the Hindclaw access control API. Uses [progenitor](https://github.com/oxidecomputer/progenitor) for compile-time code generation from the OpenAPI spec.

## Usage

```toml
[dependencies]
hindclaw-client = "0.1"
```

```rust
use hindclaw_client::Client;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Create client with Bearer auth
    let http_client = reqwest::Client::builder()
        .default_headers({
            let mut headers = reqwest::header::HeaderMap::new();
            headers.insert(
                reqwest::header::AUTHORIZATION,
                "Bearer hc_admin_xxxxx".parse().unwrap(),
            );
            headers
        })
        .build()?;
    let client = Client::new_with_client("https://hindsight.home.local", http_client);

    // List users
    let users = client.list_users().await?;
    println!("Found {} users", users.into_inner().len());

    Ok(())
}
```

## Regenerating

The client regenerates automatically on `cargo build` when `openapi.json` changes. To force:

```bash
python scripts/extract-openapi.py > hindclaw-clients/openapi.json
cd hindclaw-clients/rust && cargo check
```
