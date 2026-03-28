mod common;

use common::{unique_id, hindclaw_server as hindclaw};

#[test]
fn test_group_list() {
    let Some(mut cmd) = hindclaw() else { return; };
    let output = cmd.args(["admin", "group", "list"]).output().unwrap();
    assert!(output.status.success(), "stderr: {}", String::from_utf8_lossy(&output.stderr));
}

#[test]
fn test_group_list_json() {
    let Some(mut cmd) = hindclaw() else { return; };
    let output = cmd.args(["admin", "group", "list", "-o", "json"]).output().unwrap();
    assert!(output.status.success());
    let stdout = String::from_utf8(output.stdout).unwrap();
    let _: serde_json::Value = serde_json::from_str(&stdout).expect("expected valid JSON");
}

#[test]
fn test_group_add_and_remove() {
    let Some(mut cmd) = hindclaw() else { return; };
    let test_id = unique_id("cli-test-group");

    // Add
    let output = cmd.args([
        "admin", "group", "add", &test_id,
        "--display-name", "CLI Test Group",
    ]).output().unwrap();
    assert!(output.status.success(), "stderr: {}", String::from_utf8_lossy(&output.stderr));

    // Info
    let mut cmd = hindclaw().unwrap();
    let output = cmd.args(["admin", "group", "info", &test_id]).output().unwrap();
    assert!(output.status.success());
    let stdout = String::from_utf8(output.stdout).unwrap();
    assert!(stdout.contains("CLI Test Group"));

    // Remove with -y
    let mut cmd = hindclaw().unwrap();
    let output = cmd.args(["admin", "group", "remove", &test_id, "-y"]).output().unwrap();
    assert!(output.status.success());
}

#[test]
fn test_group_info_not_found() {
    let Some(mut cmd) = hindclaw() else { return; };
    let output = cmd.args(["admin", "group", "info", "no-such-group"]).output().unwrap();
    assert!(!output.status.success());
    let stderr = String::from_utf8(output.stderr).unwrap();
    assert!(stderr.contains("Not found") || stderr.contains("not found"));
}
