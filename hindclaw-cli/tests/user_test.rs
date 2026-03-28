use std::process::Command;
use std::time::{SystemTime, UNIX_EPOCH};

fn unique_id(prefix: &str) -> String {
    let ts = SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_millis();
    format!("{}-{}", prefix, ts)
}

fn hindclaw() -> Option<Command> {
    let url = std::env::var("HINDCLAW_API_URL").ok()?;
    let key = std::env::var("HINDCLAW_API_KEY").ok()?;
    let mut cmd = Command::new(env!("CARGO_BIN_EXE_hindclaw"));
    cmd.env("HINDCLAW_API_URL", url);
    cmd.env("HINDCLAW_API_KEY", key);
    Some(cmd)
}

#[test]
fn test_user_list() {
    let Some(mut cmd) = hindclaw() else { return; };
    let output = cmd.args(["admin", "user", "list"]).output().unwrap();
    assert!(output.status.success(), "stderr: {}", String::from_utf8_lossy(&output.stderr));
}

#[test]
fn test_user_list_json() {
    let Some(mut cmd) = hindclaw() else { return; };
    let output = cmd.args(["admin", "user", "list", "-o", "json"]).output().unwrap();
    assert!(output.status.success());
    let stdout = String::from_utf8(output.stdout).unwrap();
    let _: serde_json::Value = serde_json::from_str(&stdout).expect("expected valid JSON");
}

#[test]
fn test_user_add_and_remove() {
    let Some(mut cmd) = hindclaw() else { return; };
    let test_id = unique_id("cli-test-user");

    // Add
    let output = cmd.args([
        "admin", "user", "add", &test_id,
        "--display-name", "CLI Test User",
    ]).output().unwrap();
    assert!(output.status.success(), "stderr: {}", String::from_utf8_lossy(&output.stderr));

    // Info
    let mut cmd = hindclaw().unwrap();
    let output = cmd.args(["admin", "user", "info", &test_id]).output().unwrap();
    assert!(output.status.success());
    let stdout = String::from_utf8(output.stdout).unwrap();
    assert!(stdout.contains("CLI Test User"));

    // Remove with -y
    let mut cmd = hindclaw().unwrap();
    let output = cmd.args(["admin", "user", "remove", &test_id, "-y"]).output().unwrap();
    assert!(output.status.success());
}

#[test]
fn test_user_info_not_found() {
    let Some(mut cmd) = hindclaw() else { return; };
    let output = cmd.args(["admin", "user", "info", "no-such-user@hindclaw.test"]).output().unwrap();
    assert!(!output.status.success());
    let stderr = String::from_utf8(output.stderr).unwrap();
    assert!(stderr.contains("Not found") || stderr.contains("not found"));
}

#[test]
fn test_user_remove_requires_yes_on_non_tty() {
    let Some(mut cmd) = hindclaw() else { return; };
    let output = cmd
        .args(["admin", "user", "remove", "nobody@hindclaw.test"])
        .stdin(std::process::Stdio::piped())
        .output()
        .unwrap();
    assert!(!output.status.success());
    let stderr = String::from_utf8(output.stderr).unwrap();
    assert!(stderr.contains("stdin is not a terminal"));
}
