use anyhow::Result;
use crate::config::ResolvedConnection;

/// Build an authenticated hindclaw_client::Client from a resolved connection.
pub fn build_client(conn: &ResolvedConnection) -> Result<hindclaw_client::Client> {
    let http_client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(30))
        .default_headers({
            let mut headers = reqwest::header::HeaderMap::new();
            headers.insert(
                reqwest::header::AUTHORIZATION,
                format!("Bearer {}", conn.api_key).parse()
                    .map_err(|_| anyhow::anyhow!("Invalid API key format"))?,
            );
            headers
        })
        .build()?;
    Ok(hindclaw_client::Client::new_with_client(&conn.url, http_client))
}
