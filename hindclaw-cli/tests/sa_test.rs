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
fn test_sa_help() {
    let tmp = TempDir::new().unwrap();
    let output = hindclaw_config(tmp.path().to_str().unwrap())
        .args(["admin", "sa", "--help"])
        .output()
        .unwrap();
    assert!(output.status.success());
    let stdout = String::from_utf8(output.stdout).unwrap();
    assert!(stdout.contains("list"));
    assert!(stdout.contains("add"));
    assert!(stdout.contains("key"));
}

#[test]
fn test_sa_key_help() {
    let tmp = TempDir::new().unwrap();
    let output = hindclaw_config(tmp.path().to_str().unwrap())
        .args(["admin", "sa", "key", "--help"])
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
fn test_sa_remove_refuses_without_y_on_non_tty() {
    let tmp = TempDir::new().unwrap();
    let dir = tmp.path().to_str().unwrap();
    setup_alias(dir);

    let output = Command::new(env!("CARGO_BIN_EXE_hindclaw"))
        .env("HINDCLAW_CONFIG_DIR", dir)
        .args(["-a", "test", "admin", "sa", "remove", "some-sa"])
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
fn test_sa_key_rm_refuses_without_y_on_non_tty() {
    let tmp = TempDir::new().unwrap();
    let dir = tmp.path().to_str().unwrap();
    setup_alias(dir);

    let output = Command::new(env!("CARGO_BIN_EXE_hindclaw"))
        .env("HINDCLAW_CONFIG_DIR", dir)
        .args(["-a", "test", "admin", "sa", "key", "rm", "my-sa", "key-123"])
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
fn test_sa_list() {
    let Some(mut cmd) = hindclaw_server() else { return };
    let output = cmd.args(["admin", "sa", "list", "-o", "json"]).output().unwrap();
    assert!(output.status.success(), "stderr: {}", String::from_utf8_lossy(&output.stderr));
    let stdout = String::from_utf8(output.stdout).unwrap();
    let _: serde_json::Value = serde_json::from_str(&stdout).expect("valid JSON");
}

#[test]
fn test_sa_lifecycle() {
    let Some(mut cmd) = hindclaw_server() else { return };
    let sa_id = unique_id("cli-test-sa");

    // Add
    let output = cmd.args([
        "admin", "sa", "add", &sa_id,
        "--owner", "root",
        "--display-name", "CLI Test SA",
    ]).output().unwrap();
    assert!(output.status.success(), "stderr: {}", String::from_utf8_lossy(&output.stderr));

    // Info
    let mut cmd = hindclaw_server().unwrap();
    let output = cmd.args(["admin", "sa", "info", &sa_id]).output().unwrap();
    assert!(output.status.success());

    // Disable
    let mut cmd = hindclaw_server().unwrap();
    let output = cmd.args(["admin", "sa", "disable", &sa_id]).output().unwrap();
    assert!(output.status.success());

    // Enable
    let mut cmd = hindclaw_server().unwrap();
    let output = cmd.args(["admin", "sa", "enable", &sa_id]).output().unwrap();
    assert!(output.status.success());

    // Remove
    let mut cmd = hindclaw_server().unwrap();
    let output = cmd.args(["admin", "sa", "remove", &sa_id, "-y"]).output().unwrap();
    assert!(output.status.success());
}
