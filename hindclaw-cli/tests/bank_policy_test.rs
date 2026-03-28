use std::io::Write;
use std::process::{Command, Stdio};
use tempfile::TempDir;

fn hindclaw_config(config_dir: &str) -> Command {
    let mut cmd = Command::new(env!("CARGO_BIN_EXE_hindclaw"));
    cmd.env("HINDCLAW_CONFIG_DIR", config_dir);
    cmd
}

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

#[test]
fn test_bank_policy_help() {
    let tmp = TempDir::new().unwrap();
    let output = hindclaw_config(tmp.path().to_str().unwrap())
        .args(["admin", "bank-policy", "--help"])
        .output()
        .unwrap();
    assert!(output.status.success());
    let stdout = String::from_utf8(output.stdout).unwrap();
    assert!(stdout.contains("set"));
    assert!(stdout.contains("info"));
    assert!(stdout.contains("rm"));
}

#[test]
fn test_bank_policy_set_rejects_missing_file() {
    let tmp = TempDir::new().unwrap();
    let dir = tmp.path().to_str().unwrap();
    setup_alias(dir);

    let output = Command::new(env!("CARGO_BIN_EXE_hindclaw"))
        .env("HINDCLAW_CONFIG_DIR", dir)
        .args(["-a", "test", "admin", "bank-policy", "set", "my-bank", "/nonexistent/policy.json"])
        .output()
        .unwrap();
    assert!(!output.status.success());
}

#[test]
fn test_bank_policy_set_rejects_invalid_json() {
    let tmp = TempDir::new().unwrap();
    let dir = tmp.path().to_str().unwrap();
    let bad_json = tmp.path().join("bad.json");
    std::fs::write(&bad_json, "not json at all { broken").unwrap();
    setup_alias(dir);

    let output = Command::new(env!("CARGO_BIN_EXE_hindclaw"))
        .env("HINDCLAW_CONFIG_DIR", dir)
        .args(["-a", "test", "admin", "bank-policy", "set", "my-bank", bad_json.to_str().unwrap()])
        .output()
        .unwrap();
    assert!(!output.status.success());
    let stderr = String::from_utf8(output.stderr).unwrap();
    assert!(stderr.contains("Invalid JSON"));
}

#[test]
fn test_bank_policy_set_rejects_json_array() {
    let tmp = TempDir::new().unwrap();
    let dir = tmp.path().to_str().unwrap();
    let array_json = tmp.path().join("array.json");
    std::fs::write(&array_json, "[1, 2, 3]").unwrap();
    setup_alias(dir);

    let output = Command::new(env!("CARGO_BIN_EXE_hindclaw"))
        .env("HINDCLAW_CONFIG_DIR", dir)
        .args(["-a", "test", "admin", "bank-policy", "set", "my-bank", array_json.to_str().unwrap()])
        .output()
        .unwrap();
    assert!(!output.status.success());
    let stderr = String::from_utf8(output.stderr).unwrap();
    assert!(stderr.contains("must be a JSON object"));
}

#[test]
fn test_bank_policy_rm_refuses_without_y_on_non_tty() {
    let tmp = TempDir::new().unwrap();
    let dir = tmp.path().to_str().unwrap();
    setup_alias(dir);

    let output = Command::new(env!("CARGO_BIN_EXE_hindclaw"))
        .env("HINDCLAW_CONFIG_DIR", dir)
        .args(["-a", "test", "admin", "bank-policy", "rm", "my-bank"])
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .output()
        .unwrap();
    assert!(!output.status.success());
    let stderr = String::from_utf8(output.stderr).unwrap();
    assert!(stderr.contains("stdin is not a terminal"));
}
