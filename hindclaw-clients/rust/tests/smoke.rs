//! HTTP smoke test for the progenitor-generated Hindclaw client.
//!
//! Uses mockito to stand up an in-process stub server, points a
//! Client at it, and verifies that `list_users()` roundtrips through
//! the real progenitor codepath — URL construction, header handling,
//! JSON deserialisation — without needing an upstream Hindsight
//! server running.

use hindclaw_client::Client;

#[tokio::test]
async fn list_users_smoke() {
    let mut server = mockito::Server::new_async().await;
    let mock = server
        .mock("GET", "/ext/hindclaw/users")
        .with_status(200)
        .with_header("content-type", "application/json")
        .with_body("[]")
        .create_async()
        .await;

    let client = Client::new(&server.url());
    let response = client.list_users().await.expect("list_users");
    assert!(response.into_inner().is_empty());

    mock.assert_async().await;
}
