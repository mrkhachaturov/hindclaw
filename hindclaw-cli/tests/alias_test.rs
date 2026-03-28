use std::io::Write;
use std::process::{Command, Stdio};
use tempfile::TempDir;

fn hindclaw(config_dir: &str) -> Command {
    let mut cmd = Command::new(env!("CARGO_BIN_EXE_hindclaw"));
    cmd.env("HINDCLAW_CONFIG_DIR", config_dir);
    cmd
}

/// Helper: run `alias set` with key piped via stdin
fn alias_set(dir: &str, name: &str, url: &str, key: &str, extra_args: &[&str]) -> std::process::Output {
    let mut cmd = hindclaw(dir);
    cmd.args(["alias", "set", name, url, "--stdin-key"]);
    cmd.args(extra_args);
    let mut child = cmd
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .unwrap();
    child.stdin.take().unwrap().write_all(format!("{}\n", key).as_bytes()).unwrap();
    child.wait_with_output().unwrap()
}

#[test]
fn test_alias_ls_empty() {
    let tmp = TempDir::new().unwrap();
    let output = hindclaw(tmp.path().to_str().unwrap())
        .args(["alias", "ls"])
        .output()
        .unwrap();
    assert!(output.status.success());
    let stdout = String::from_utf8(output.stdout).unwrap();
    assert!(stdout.contains("No aliases configured"));
}

#[test]
fn test_alias_set_and_ls() {
    let tmp = TempDir::new().unwrap();
    let dir = tmp.path().to_str().unwrap();

    // Set alias via stdin key
    let output = alias_set(dir, "test", "http://localhost:8888", "test-key", &[]);
    assert!(output.status.success());

    // List should show it
    let output = hindclaw(dir)
        .args(["alias", "ls", "-o", "json"])
        .output()
        .unwrap();
    assert!(output.status.success());
    let stdout = String::from_utf8(output.stdout).unwrap();
    assert!(stdout.contains("http://localhost:8888"));
}

#[test]
fn test_alias_default_flag() {
    let tmp = TempDir::new().unwrap();
    let dir = tmp.path().to_str().unwrap();

    // Set two aliases, second as default
    alias_set(dir, "staging", "http://staging:8888", "key1", &[]);
    alias_set(dir, "prod", "http://prod:8888", "key2", &["--default"]);

    // List as JSON — only prod should be default
    let output = hindclaw(dir)
        .args(["alias", "ls", "-o", "json"])
        .output()
        .unwrap();
    let stdout = String::from_utf8(output.stdout).unwrap();
    let parsed: serde_json::Value = serde_json::from_str(&stdout).unwrap();
    assert_eq!(parsed["prod"]["default"], true);
    assert_eq!(parsed["staging"]["default"], false);

    // Setting staging as default should clear prod's default
    alias_set(dir, "staging", "http://staging:8888", "key1", &["--default"]);
    let output = hindclaw(dir)
        .args(["alias", "ls", "-o", "json"])
        .output()
        .unwrap();
    let stdout = String::from_utf8(output.stdout).unwrap();
    let parsed: serde_json::Value = serde_json::from_str(&stdout).unwrap();
    assert_eq!(parsed["staging"]["default"], true);
    assert_eq!(parsed["prod"]["default"], false);
}

#[test]
fn test_alias_rm_requires_confirmation() {
    let tmp = TempDir::new().unwrap();
    let dir = tmp.path().to_str().unwrap();

    // Set alias
    alias_set(dir, "test", "http://localhost:8888", "key", &[]);

    // Remove without -y on non-TTY should fail
    let output = hindclaw(dir)
        .args(["alias", "rm", "test"])
        .output()
        .unwrap();
    assert!(!output.status.success());
    let stderr = String::from_utf8(output.stderr).unwrap();
    assert!(stderr.contains("stdin is not a terminal"));

    // Remove with -y should succeed
    let output = hindclaw(dir)
        .args(["alias", "rm", "test", "-y"])
        .output()
        .unwrap();
    assert!(output.status.success());
}

#[test]
fn test_alias_rm_nonexistent() {
    let tmp = TempDir::new().unwrap();
    let output = hindclaw(tmp.path().to_str().unwrap())
        .args(["alias", "rm", "nonexistent", "-y"])
        .output()
        .unwrap();
    assert!(!output.status.success());
    let stderr = String::from_utf8(output.stderr).unwrap();
    assert!(stderr.contains("not found"));
}

#[test]
fn test_alias_set_invalid_url() {
    let tmp = TempDir::new().unwrap();
    let dir = tmp.path().to_str().unwrap();

    let output = alias_set(dir, "bad", "not-a-url", "key", &[]);
    assert!(!output.status.success());
    let stderr = String::from_utf8(output.stderr).unwrap();
    assert!(stderr.contains("Invalid URL"));
}

#[test]
fn test_config_file_permissions() {
    let tmp = TempDir::new().unwrap();
    let dir = tmp.path().to_str().unwrap();

    alias_set(dir, "test", "http://localhost:8888", "key", &[]);

    // Check file permissions are 0600
    let config_path = tmp.path().join("config.json");
    let metadata = std::fs::metadata(&config_path).unwrap();
    use std::os::unix::fs::PermissionsExt;
    let mode = metadata.permissions().mode() & 0o777;
    assert_eq!(mode, 0o600, "Config file should have 0600 permissions, got {:o}", mode);
}
