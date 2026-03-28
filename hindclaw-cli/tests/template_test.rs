use std::process::Command;
use tempfile::TempDir;

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
