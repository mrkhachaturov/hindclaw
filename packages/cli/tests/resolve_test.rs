mod common;

use std::process::Command;
use tempfile::TempDir;
use common::{hindclaw_config, setup_alias};

#[test]
fn test_resolve_help() {
    let tmp = TempDir::new().unwrap();
    let output = hindclaw_config(tmp.path().to_str().unwrap())
        .args(["admin", "resolve", "--help"])
        .output()
        .unwrap();
    assert!(output.status.success());
    let stdout = String::from_utf8(output.stdout).unwrap();
    assert!(stdout.contains("--bank"));
    assert!(stdout.contains("--user"));
    assert!(stdout.contains("--sa"));
    assert!(stdout.contains("--sender"));
    assert!(stdout.contains("--action"));
}

#[test]
fn test_resolve_requires_bank() {
    let tmp = TempDir::new().unwrap();
    let output = hindclaw_config(tmp.path().to_str().unwrap())
        .args(["admin", "resolve", "--user", "alice"])
        .output()
        .unwrap();
    assert!(!output.status.success());
    let stderr = String::from_utf8(output.stderr).unwrap();
    assert!(stderr.contains("--bank"));
}

#[test]
fn test_resolve_requires_one_of_user_sa_sender() {
    let tmp = TempDir::new().unwrap();
    let output = hindclaw_config(tmp.path().to_str().unwrap())
        .args(["admin", "resolve", "--bank", "my-bank"])
        .output()
        .unwrap();
    assert!(!output.status.success());
}

#[test]
fn test_resolve_user_and_sa_are_mutually_exclusive() {
    let tmp = TempDir::new().unwrap();
    let output = hindclaw_config(tmp.path().to_str().unwrap())
        .args(["admin", "resolve", "--bank", "my-bank", "--user", "alice", "--sa", "bot"])
        .output()
        .unwrap();
    assert!(!output.status.success());
}

#[test]
fn test_resolve_sender_invalid_format() {
    let tmp = TempDir::new().unwrap();
    let dir = tmp.path().to_str().unwrap();
    setup_alias(dir);

    // "telegramonly" has no colon — should fail with format error
    let output = Command::new(env!("CARGO_BIN_EXE_hindclaw"))
        .env("HINDCLAW_CONFIG_DIR", dir)
        .args(["-a", "test", "admin", "resolve", "--bank", "my-bank", "--sender", "telegramonly"])
        .output()
        .unwrap();
    assert!(!output.status.success());
    let stderr = String::from_utf8(output.stderr).unwrap();
    assert!(stderr.contains("provider:id"));
}
