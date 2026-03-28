#![allow(dead_code)]

use std::io::Write;
use std::process::{Command, Stdio};
use std::time::{SystemTime, UNIX_EPOCH};

/// Generate a unique ID with a prefix (for test isolation)
pub fn unique_id(prefix: &str) -> String {
    let ts = SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_millis();
    format!("{}-{}", prefix, ts)
}

/// Create a hindclaw command with a config directory (no server connection)
pub fn hindclaw_config(config_dir: &str) -> Command {
    let mut cmd = Command::new(env!("CARGO_BIN_EXE_hindclaw"));
    cmd.env("HINDCLAW_CONFIG_DIR", config_dir);
    cmd
}

/// Create a hindclaw command connected to the test server.
/// Returns None if HINDCLAW_API_URL / HINDCLAW_API_KEY are not set.
pub fn hindclaw_server() -> Option<Command> {
    let url = std::env::var("HINDCLAW_API_URL").ok()?;
    let key = std::env::var("HINDCLAW_API_KEY").ok()?;
    let mut cmd = Command::new(env!("CARGO_BIN_EXE_hindclaw"));
    cmd.env("HINDCLAW_API_URL", url);
    cmd.env("HINDCLAW_API_KEY", key);
    Some(cmd)
}

/// Set a dummy alias so commands can get past config resolution
pub fn setup_alias(dir: &str) {
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
