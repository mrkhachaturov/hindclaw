mod common;

use std::process::{Command, Stdio};
use tempfile::TempDir;
use common::{unique_id, hindclaw_config, hindclaw_server, setup_alias};

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
    let Some(_) = hindclaw_server() else { return };
    let sa_id = unique_id("cli-test-sa");
    let user_id = unique_id("sa-owner");

    // Create owner user (FK constraint requires valid owner_user_id)
    let output = hindclaw_server().unwrap()
        .args(["admin", "user", "add", &user_id, "--display-name", "SA Test Owner"])
        .output().unwrap();
    assert!(output.status.success(), "user add: {}", String::from_utf8_lossy(&output.stderr));

    // Add SA
    let output = hindclaw_server().unwrap().args([
        "admin", "sa", "add", &sa_id,
        "--owner", &user_id,
        "--display-name", "CLI Test SA",
    ]).output().unwrap();
    assert!(output.status.success(), "sa add: {}", String::from_utf8_lossy(&output.stderr));

    // Info
    let output = hindclaw_server().unwrap()
        .args(["admin", "sa", "info", &sa_id]).output().unwrap();
    assert!(output.status.success());

    // Disable
    let output = hindclaw_server().unwrap()
        .args(["admin", "sa", "disable", &sa_id]).output().unwrap();
    assert!(output.status.success());

    // Enable
    let output = hindclaw_server().unwrap()
        .args(["admin", "sa", "enable", &sa_id]).output().unwrap();
    assert!(output.status.success());

    // Remove SA
    let output = hindclaw_server().unwrap()
        .args(["admin", "sa", "remove", &sa_id, "-y"]).output().unwrap();
    assert!(output.status.success());

    // Cleanup owner user
    hindclaw_server().unwrap()
        .args(["admin", "user", "remove", &user_id, "-y"])
        .output().unwrap();
}
