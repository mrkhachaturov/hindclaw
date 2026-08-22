//! Hindclaw API Client
//!
//! A Rust client library for the Hindclaw access control API.
//!
//! # Example
//!
//! ```rust,no_run
//! use hindclaw_client::Client;
//!
//! #[tokio::main]
//! async fn main() -> Result<(), Box<dyn std::error::Error>> {
//!     let client = Client::new("http://localhost:8888");
//!
//!     // List users
//!     let users = client.list_users().await?;
//!     println!("Found {} users", users.into_inner().len());
//!
//!     Ok(())
//! }
//! ```

// Include the generated client code
include!(concat!(env!("OUT_DIR"), "/hindclaw_client_generated.rs"));

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_client_creation() {
        let _client = Client::new("http://localhost:8888");
        assert!(true);
    }

    #[tokio::test]
    #[ignore] // Requires a running Hindclaw server: cargo test -- --ignored
    async fn test_user_lifecycle() {
        let api_url = std::env::var("HINDCLAW_API_URL")
            .unwrap_or_else(|_| "http://localhost:8888".to_string());
        let api_key = std::env::var("HINDCLAW_API_KEY")
            .expect("HINDCLAW_API_KEY must be set for integration tests");

        // Build a reqwest client with Bearer auth and generous timeout
        let http_client = reqwest::Client::builder()
            .timeout(std::time::Duration::from_secs(30))
            .default_headers({
                let mut headers = reqwest::header::HeaderMap::new();
                headers.insert(
                    reqwest::header::AUTHORIZATION,
                    format!("Bearer {}", api_key).parse().unwrap(),
                );
                headers
            })
            .build()
            .expect("Failed to build HTTP client");
        let client = Client::new_with_client(&api_url, http_client);

        let user_id = format!("rust-test-{}", uuid::Uuid::new_v4());

        // Create a user
        let create_request = types::CreateUserRequest {
            id: user_id.clone(),
            display_name: "Rust Test User".to_string(),
            email: None,
            is_active: true,
        };
        let _create_response = client
            .create_user(&create_request)
            .await
            .expect("Failed to create user");

        // List users and verify ours exists
        let users = client
            .list_users()
            .await
            .expect("Failed to list users");
        let user_list = users.into_inner();
        assert!(
            user_list.iter().any(|u| u.id == user_id),
            "Created user should appear in list"
        );

        // Cleanup: delete test user
        let _ = client.delete_user(&user_id).await;
    }
}
