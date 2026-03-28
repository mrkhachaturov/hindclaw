use std::process::{Command, Stdio};
use std::time::{SystemTime, UNIX_EPOCH};
use tempfile::TempDir;

fn unique_id(prefix: &str) -> String {
    let ts = SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_millis();
    format!("{}-{}", prefix, ts)
}

fn test_env() -> Option<(String, String)> {
    let url = std::env::var("HINDCLAW_API_URL").ok()?;
    let key = std::env::var("HINDCLAW_API_KEY").ok()?;
    Some((url, key))
}

fn hindclaw(config_dir: &str, url: &str, key: &str) -> Command {
    let mut cmd = Command::new(env!("CARGO_BIN_EXE_hindclaw"));
    cmd.env("HINDCLAW_CONFIG_DIR", config_dir);
    cmd.env("HINDCLAW_API_URL", url);
    cmd.env("HINDCLAW_API_KEY", key);
    cmd
}

fn policy_document() -> serde_json::Value {
    serde_json::json!({
        "version": "2026-03-24",
        "statements": [
            {
                "effect": "allow",
                "actions": ["bank:recall"],
                "banks": ["*"]
            }
        ]
    })
}

fn write_policy_file(dir: &std::path::Path) -> std::path::PathBuf {
    let path = dir.join("policy.json");
    std::fs::write(&path, serde_json::to_string_pretty(&policy_document()).unwrap()).unwrap();
    path
}

// --- Help text tests (no server needed) ---

#[test]
fn test_policy_help() {
    let tmp = TempDir::new().unwrap();
    let output = Command::new(env!("CARGO_BIN_EXE_hindclaw"))
        .env("HINDCLAW_CONFIG_DIR", tmp.path().to_str().unwrap())
        .args(["admin", "policy", "--help"])
        .output()
        .unwrap();
    assert!(output.status.success());
    let stdout = String::from_utf8(output.stdout).unwrap();
    assert!(stdout.contains("list"));
    assert!(stdout.contains("create"));
    assert!(stdout.contains("attach"));
    assert!(stdout.contains("detach"));
    assert!(stdout.contains("entities"));
}

#[test]
fn test_attach_requires_user_or_group() {
    let Some((url, key)) = test_env() else { return };
    let tmp = TempDir::new().unwrap();
    let dir = tmp.path().to_str().unwrap();

    // attach with neither --user nor --group should fail (runtime bail, not clap)
    let output = hindclaw(dir, &url, &key)
        .args(["admin", "policy", "attach", "some-policy"])
        .output()
        .unwrap();
    assert!(!output.status.success());
}

// --- Server integration tests (skip when env vars absent) ---

#[test]
fn test_policy_list() {
    let Some((url, key)) = test_env() else { return };
    let tmp = TempDir::new().unwrap();
    let dir = tmp.path().to_str().unwrap();

    let output = hindclaw(dir, &url, &key)
        .args(["admin", "policy", "list", "-o", "json"])
        .output()
        .unwrap();
    assert!(output.status.success(), "stderr: {}", String::from_utf8_lossy(&output.stderr));
    let stdout = String::from_utf8(output.stdout).unwrap();
    let parsed: serde_json::Value = serde_json::from_str(&stdout).unwrap();
    assert!(parsed.is_array(), "Expected JSON array response");
}

#[test]
fn test_policy_create_and_info() {
    let Some((url, key)) = test_env() else { return };
    let tmp = TempDir::new().unwrap();
    let dir = tmp.path().to_str().unwrap();
    let policy_file = write_policy_file(tmp.path());
    let pid = unique_id("pol-create");

    // Create
    let output = hindclaw(dir, &url, &key)
        .args([
            "admin", "policy", "create", &pid,
            policy_file.to_str().unwrap(),
            "--display-name", "Test Policy",
        ])
        .output()
        .unwrap();
    assert!(output.status.success(), "stderr: {}", String::from_utf8_lossy(&output.stderr));

    // Info
    let output = hindclaw(dir, &url, &key)
        .args(["admin", "policy", "info", &pid, "-o", "json"])
        .output()
        .unwrap();
    assert!(output.status.success(), "stderr: {}", String::from_utf8_lossy(&output.stderr));
    let stdout = String::from_utf8(output.stdout).unwrap();
    let parsed: serde_json::Value = serde_json::from_str(&stdout).unwrap();
    assert_eq!(parsed["id"].as_str().unwrap(), pid);
    assert_eq!(parsed["display_name"], "Test Policy");

    // Cleanup
    hindclaw(dir, &url, &key)
        .args(["admin", "policy", "remove", &pid, "-y"])
        .output()
        .unwrap();
}

#[test]
fn test_policy_update() {
    let Some((url, key)) = test_env() else { return };
    let tmp = TempDir::new().unwrap();
    let dir = tmp.path().to_str().unwrap();
    let policy_file = write_policy_file(tmp.path());
    let pid = unique_id("pol-update");

    // Create
    hindclaw(dir, &url, &key)
        .args([
            "admin", "policy", "create", &pid,
            policy_file.to_str().unwrap(),
            "--display-name", "Original Name",
        ])
        .output()
        .unwrap();

    // Update display_name
    let output = hindclaw(dir, &url, &key)
        .args([
            "admin", "policy", "update", &pid,
            policy_file.to_str().unwrap(),
            "--display-name", "Updated Name",
        ])
        .output()
        .unwrap();
    assert!(output.status.success(), "stderr: {}", String::from_utf8_lossy(&output.stderr));

    // Verify
    let output = hindclaw(dir, &url, &key)
        .args(["admin", "policy", "info", &pid, "-o", "json"])
        .output()
        .unwrap();
    let stdout = String::from_utf8(output.stdout).unwrap();
    let parsed: serde_json::Value = serde_json::from_str(&stdout).unwrap();
    assert_eq!(parsed["display_name"], "Updated Name");

    // Cleanup
    hindclaw(dir, &url, &key)
        .args(["admin", "policy", "remove", &pid, "-y"])
        .output()
        .unwrap();
}

#[test]
fn test_policy_remove_requires_confirmation() {
    let Some((url, key)) = test_env() else { return };
    let tmp = TempDir::new().unwrap();
    let dir = tmp.path().to_str().unwrap();
    let policy_file = write_policy_file(tmp.path());
    let pid = unique_id("pol-rm");

    // Create
    hindclaw(dir, &url, &key)
        .args([
            "admin", "policy", "create", &pid,
            policy_file.to_str().unwrap(),
            "--display-name", "Test RM Policy",
        ])
        .output()
        .unwrap();

    // Remove without -y on non-TTY stdin should fail
    let output = hindclaw(dir, &url, &key)
        .args(["admin", "policy", "remove", &pid])
        .stdin(Stdio::piped())
        .output()
        .unwrap();
    assert!(!output.status.success());
    let stderr = String::from_utf8(output.stderr).unwrap();
    assert!(stderr.contains("stdin is not a terminal"));

    // Remove with -y should succeed
    let output = hindclaw(dir, &url, &key)
        .args(["admin", "policy", "remove", &pid, "-y"])
        .output()
        .unwrap();
    assert!(output.status.success());
}

#[test]
fn test_policy_attach_detach_entities() {
    let Some((url, key)) = test_env() else { return };
    let tmp = TempDir::new().unwrap();
    let dir = tmp.path().to_str().unwrap();
    let policy_file = write_policy_file(tmp.path());
    let pid = unique_id("pol-attach");
    let gid = unique_id("grp-pol");

    // Create policy
    hindclaw(dir, &url, &key)
        .args([
            "admin", "policy", "create", &pid,
            policy_file.to_str().unwrap(),
            "--display-name", "Test Attach Policy",
        ])
        .output()
        .unwrap();

    // Create a group to attach to
    hindclaw(dir, &url, &key)
        .args([
            "admin", "group", "add", &gid,
            "--display-name", "Test Group",
        ])
        .output()
        .unwrap();

    // Attach to group
    let output = hindclaw(dir, &url, &key)
        .args([
            "admin", "policy", "attach", &pid,
            "--group", &gid,
            "--priority", "5",
        ])
        .output()
        .unwrap();
    assert!(output.status.success(), "stderr: {}", String::from_utf8_lossy(&output.stderr));

    // Entities should show the group attachment
    let output = hindclaw(dir, &url, &key)
        .args([
            "admin", "policy", "entities", &pid,
            "-o", "json",
        ])
        .output()
        .unwrap();
    assert!(output.status.success());
    let stdout = String::from_utf8(output.stdout).unwrap();
    let parsed: serde_json::Value = serde_json::from_str(&stdout).unwrap();
    let attachments = parsed.as_array().unwrap();
    assert!(attachments.iter().any(|a| {
        a["principal_type"] == "group" && a["principal_id"].as_str() == Some(gid.as_str())
    }));

    // Detach
    let output = hindclaw(dir, &url, &key)
        .args([
            "admin", "policy", "detach", &pid,
            "--group", &gid,
            "-y",
        ])
        .output()
        .unwrap();
    assert!(output.status.success());

    // Cleanup
    hindclaw(dir, &url, &key)
        .args(["admin", "policy", "remove", &pid, "-y"])
        .output()
        .unwrap();
    hindclaw(dir, &url, &key)
        .args(["admin", "group", "remove", &gid, "-y"])
        .output()
        .unwrap();
}
