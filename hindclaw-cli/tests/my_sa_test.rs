use std::io::Write;
use std::process::{Command, Stdio};
use std::time::{SystemTime, UNIX_EPOCH};
use tempfile::TempDir;

fn unique_id(prefix: &str) -> String {
    let ts = SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_millis();
    format!("{}-{}", prefix, ts)
}

fn hindclaw_config(config_dir: &str) -> Command {
    let mut cmd = Command::new(env!("CARGO_BIN_EXE_hindclaw"));
    cmd.env("HINDCLAW_CONFIG_DIR", config_dir);
    cmd
}

fn hindclaw_server() -> Option<Command> {
    let url = std::env::var("HINDCLAW_API_URL").ok()?;
    let key = std::env::var("HINDCLAW_API_KEY").ok()?;
    let mut cmd = Command::new(env!("CARGO_BIN_EXE_hindclaw"));
    cmd.env("HINDCLAW_API_URL", url);
    cmd.env("HINDCLAW_API_KEY", key);
    Some(cmd)
}

/// Set a dummy alias so commands can get past config resolution
fn setup_alias(dir: &str) {
    let mut child = Command::new(env!("CARGO_BIN_EXE_hindclaw"))
        .env("HINDCLAW_CONFIG_DIR", dir)
        .args(["alias", "set", "test", "http://localhost:9999", "--stdin-key"])
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .unwrap();
    child.stdin.as_mut().unwrap().write_all(b"dummy-key\n").unwrap();
    child.wait_with_output().unwrap();
}

// --- Help text tests (no server needed) ---

#[test]
fn test_my_sa_help() {
    let tmp = TempDir::new().unwrap();
    let output = hindclaw_config(tmp.path().to_str().unwrap())
        .args(["sa", "--help"])
        .output()
        .unwrap();
    assert!(output.status.success());
    let stdout = String::from_utf8(output.stdout).unwrap();
    assert!(stdout.contains("list"));
    assert!(stdout.contains("add"));
    assert!(stdout.contains("key"));
    assert!(stdout.contains("update"));
    assert!(stdout.contains("remove"));
}

#[test]
fn test_my_sa_key_help() {
    let tmp = TempDir::new().unwrap();
    let output = hindclaw_config(tmp.path().to_str().unwrap())
        .args(["sa", "key", "--help"])
        .output()
        .unwrap();
    assert!(output.status.success());
    let stdout = String::from_utf8(output.stdout).unwrap();
    assert!(stdout.contains("add"));
    assert!(stdout.contains("ls"));
    assert!(stdout.contains("rm"));
}

// --- Confirmation guard tests ---

#[test]
fn test_my_sa_remove_refuses_without_y_on_non_tty() {
    let tmp = TempDir::new().unwrap();
    let dir = tmp.path().to_str().unwrap();
    setup_alias(dir);

    let output = Command::new(env!("CARGO_BIN_EXE_hindclaw"))
        .env("HINDCLAW_CONFIG_DIR", dir)
        .args(["-a", "test", "sa", "remove", "some-sa"])
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .output()
        .unwrap();
    assert!(!output.status.success());
    let stderr = String::from_utf8(output.stderr).unwrap();
    assert!(stderr.contains("stdin is not a terminal"));
}

#[test]
fn test_my_sa_key_rm_refuses_without_y_on_non_tty() {
    let tmp = TempDir::new().unwrap();
    let dir = tmp.path().to_str().unwrap();
    setup_alias(dir);

    let output = Command::new(env!("CARGO_BIN_EXE_hindclaw"))
        .env("HINDCLAW_CONFIG_DIR", dir)
        .args(["-a", "test", "sa", "key", "rm", "my-sa", "key-123"])
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .output()
        .unwrap();
    assert!(!output.status.success());
    let stderr = String::from_utf8(output.stderr).unwrap();
    assert!(stderr.contains("stdin is not a terminal"));
}

// --- Server tests ---

#[test]
fn test_my_sa_list_json() {
    let Some(mut cmd) = hindclaw_server() else { return };
    let output = cmd.args(["sa", "list", "-o", "json"]).output().unwrap();
    assert!(output.status.success(), "sa list failed: {}", String::from_utf8_lossy(&output.stderr));
    let parsed: serde_json::Value = serde_json::from_slice(&output.stdout).unwrap();
    assert!(parsed.is_array());
}

#[test]
fn test_my_sa_list_alias_ls() {
    let Some(mut cmd) = hindclaw_server() else { return };
    let output = cmd.args(["sa", "ls", "-o", "json"]).output().unwrap();
    assert!(output.status.success(), "sa ls failed: {}", String::from_utf8_lossy(&output.stderr));
}

#[test]
fn test_my_sa_lifecycle() {
    let Some(_) = hindclaw_server() else { return };
    let sa_id = unique_id("test-sa");

    // add
    let output = hindclaw_server().unwrap()
        .args(["sa", "add", &sa_id, "--display-name", "Test SA"])
        .output().unwrap();
    assert!(output.status.success(), "sa add failed: {}", String::from_utf8_lossy(&output.stderr));

    // info
    let output = hindclaw_server().unwrap()
        .args(["sa", "info", &sa_id, "-o", "json"])
        .output().unwrap();
    assert!(output.status.success(), "sa info failed: {}", String::from_utf8_lossy(&output.stderr));
    let parsed: serde_json::Value = serde_json::from_slice(&output.stdout).unwrap();
    assert_eq!(parsed["id"], sa_id);

    // show alias
    let output = hindclaw_server().unwrap()
        .args(["sa", "show", &sa_id, "-o", "json"])
        .output().unwrap();
    assert!(output.status.success(), "sa show failed: {}", String::from_utf8_lossy(&output.stderr));

    // update
    let output = hindclaw_server().unwrap()
        .args(["sa", "update", &sa_id, "--display-name", "Updated SA"])
        .output().unwrap();
    assert!(output.status.success(), "sa update failed: {}", String::from_utf8_lossy(&output.stderr));

    // key add
    let output = hindclaw_server().unwrap()
        .args(["sa", "key", "add", &sa_id, "--description", "test key"])
        .output().unwrap();
    assert!(output.status.success(), "sa key add failed: {}", String::from_utf8_lossy(&output.stderr));

    // key list
    let output = hindclaw_server().unwrap()
        .args(["sa", "key", "ls", &sa_id, "-o", "json"])
        .output().unwrap();
    assert!(output.status.success(), "sa key ls failed: {}", String::from_utf8_lossy(&output.stderr));

    // remove
    let output = hindclaw_server().unwrap()
        .args(["sa", "remove", &sa_id, "-y"])
        .output().unwrap();
    assert!(output.status.success(), "sa remove failed: {}", String::from_utf8_lossy(&output.stderr));
}
