mod common;

use tempfile::TempDir;
use common::{hindclaw_config, hindclaw_server};

// --- Help text tests (no server needed) ---

#[test]
fn test_template_help() {
    let tmp = TempDir::new().unwrap();
    let output = hindclaw_config(tmp.path().to_str().unwrap())
        .args(["template", "--help"])
        .output()
        .unwrap();
    assert!(output.status.success());
    let stdout = String::from_utf8(output.stdout).unwrap();
    assert!(stdout.contains("list"));
    assert!(stdout.contains("search"));
    assert!(stdout.contains("install"));
    assert!(stdout.contains("apply"));
    assert!(stdout.contains("export"));
    assert!(stdout.contains("import"));
}

#[test]
fn test_admin_source_help() {
    let tmp = TempDir::new().unwrap();
    let output = hindclaw_config(tmp.path().to_str().unwrap())
        .args(["admin", "source", "--help"])
        .output()
        .unwrap();
    assert!(output.status.success());
    let stdout = String::from_utf8(output.stdout).unwrap();
    assert!(stdout.contains("list"));
    assert!(stdout.contains("add"));
    assert!(stdout.contains("rm"));
}

// --- Server integration tests (skip when env vars absent) ---

#[test]
fn test_template_list_json() {
    let Some(mut cmd) = hindclaw_server() else { return };
    let output = cmd
        .args(["template", "list", "-o", "json"])
        .output()
        .unwrap();
    assert!(output.status.success(), "stderr: {}", String::from_utf8_lossy(&output.stderr));
    let stdout = String::from_utf8(output.stdout).unwrap();
    let _: serde_json::Value = serde_json::from_str(&stdout).unwrap();
}

#[test]
fn test_marketplace_search() {
    let Some(mut cmd) = hindclaw_server() else { return };
    let output = cmd
        .args(["template", "search", "-o", "json"])
        .output()
        .unwrap();
    assert!(output.status.success(), "stderr: {}", String::from_utf8_lossy(&output.stderr));
    let stdout = String::from_utf8(output.stdout).unwrap();
    let parsed: serde_json::Value = serde_json::from_str(&stdout).unwrap();
    assert!(parsed.get("results").is_some());
    assert!(parsed.get("total").is_some());
}

#[test]
fn test_source_list() {
    let Some(mut cmd) = hindclaw_server() else { return };
    let output = cmd
        .args(["admin", "source", "list", "-o", "json"])
        .output()
        .unwrap();
    assert!(output.status.success(), "stderr: {}", String::from_utf8_lossy(&output.stderr));
    let stdout = String::from_utf8(output.stdout).unwrap();
    let _: serde_json::Value = serde_json::from_str(&stdout).unwrap();
}
