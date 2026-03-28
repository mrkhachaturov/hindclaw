use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use std::env;
use std::fs;
use std::os::unix::fs::{OpenOptionsExt, PermissionsExt};
use std::path::PathBuf;

const CONFIG_DIR_NAME: &str = ".hindclaw";
const CONFIG_FILE_NAME: &str = "config.json";

#[derive(Debug, Serialize, Deserialize)]
pub struct ConfigFile {
    #[serde(default)]
    pub aliases: BTreeMap<String, Alias>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Alias {
    pub url: String,
    pub api_key: String,
    #[serde(default)]
    pub default: bool,
}

#[derive(Debug)]
pub struct ResolvedConnection {
    pub url: String,
    pub api_key: String,
    pub source: ConnectionSource,
}

#[derive(Debug)]
pub enum ConnectionSource {
    Alias(String),
    Environment,
    DefaultAlias(String),
}

impl std::fmt::Display for ConnectionSource {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            ConnectionSource::Alias(name) => write!(f, "alias '{}'", name),
            ConnectionSource::Environment => write!(f, "environment variables"),
            ConnectionSource::DefaultAlias(name) => write!(f, "default alias '{}'", name),
        }
    }
}

impl ConfigFile {
    pub fn load() -> Result<Self> {
        let path = config_file_path()?;
        if !path.exists() {
            return Ok(ConfigFile { aliases: BTreeMap::new() });
        }

        // Check permissions
        check_permissions(&path)?;

        let content = fs::read_to_string(&path)
            .with_context(|| format!("Failed to read {}", path.display()))?;
        let config: ConfigFile = serde_json::from_str(&content)
            .with_context(|| format!("Failed to parse {}", path.display()))?;
        Ok(config)
    }

    pub fn save(&self) -> Result<PathBuf> {
        use std::io::Write;

        let dir = config_dir()?;
        if !dir.exists() {
            fs::create_dir_all(&dir)
                .with_context(|| format!("Failed to create {}", dir.display()))?;
            fs::set_permissions(&dir, fs::Permissions::from_mode(0o700))?;
        }

        let path = dir.join(CONFIG_FILE_NAME);
        let content = serde_json::to_string_pretty(self)?;

        // Write atomically: create temp file with 0600 from the start, then rename.
        // This avoids a window where the file exists with umask-default permissions.
        let tmp_path = path.with_extension("tmp");
        {
            let file = fs::OpenOptions::new()
                .write(true)
                .create(true)
                .truncate(true)
                .mode(0o600)
                .open(&tmp_path)
                .with_context(|| format!("Failed to create {}", tmp_path.display()))?;
            let mut writer = std::io::BufWriter::new(file);
            writer.write_all(content.as_bytes())?;
            writer.flush()?;
        }
        fs::rename(&tmp_path, &path)
            .with_context(|| format!("Failed to rename {} to {}", tmp_path.display(), path.display()))?;

        Ok(path)
    }

    pub fn default_alias(&self) -> Option<(&str, &Alias)> {
        self.aliases.iter()
            .find(|(_, a)| a.default)
            .map(|(name, alias)| (name.as_str(), alias))
    }
}

/// Resolve connection using the chain: --alias > env vars > default alias
#[allow(dead_code)]
pub fn resolve_connection(alias_flag: Option<&str>) -> Result<ResolvedConnection> {
    // 1. Explicit --alias flag (highest priority)
    if let Some(name) = alias_flag {
        let config = ConfigFile::load()?;
        let alias = config.aliases.get(name)
            .ok_or_else(|| anyhow::anyhow!("Alias '{}' not found. Run `hindclaw alias ls` to see available aliases.", name))?;
        return Ok(ResolvedConnection {
            url: alias.url.clone(),
            api_key: alias.api_key.clone(),
            source: ConnectionSource::Alias(name.to_string()),
        });
    }

    // 2. Environment variables
    if let (Ok(url), Ok(key)) = (env::var("HINDCLAW_API_URL"), env::var("HINDCLAW_API_KEY")) {
        return Ok(ResolvedConnection {
            url,
            api_key: key,
            source: ConnectionSource::Environment,
        });
    }

    // 3. Default alias
    let config = ConfigFile::load()?;
    if let Some((name, alias)) = config.default_alias() {
        return Ok(ResolvedConnection {
            url: alias.url.clone(),
            api_key: alias.api_key.clone(),
            source: ConnectionSource::DefaultAlias(name.to_string()),
        });
    }

    // 4. Error
    anyhow::bail!("No server configured.\n\n  Set an alias:     hindclaw alias set <name> <url>\n  Or use env vars:  HINDCLAW_API_URL + HINDCLAW_API_KEY")
}

fn config_dir() -> Result<PathBuf> {
    let dir = env::var("HINDCLAW_CONFIG_DIR")
        .map(PathBuf::from)
        .unwrap_or_else(|_| {
            dirs::home_dir()
                .expect("Could not determine home directory")
                .join(CONFIG_DIR_NAME)
        });
    Ok(dir)
}

fn config_file_path() -> Result<PathBuf> {
    Ok(config_dir()?.join(CONFIG_FILE_NAME))
}

fn check_permissions(path: &PathBuf) -> Result<()> {
    let metadata = fs::metadata(path)?;
    let mode = metadata.permissions().mode();
    let file_perms = mode & 0o777;
    if file_perms != 0o600 {
        eprintln!(
            "  {} Config file {} has permissions {:o}, expected 600. Run: chmod 600 {}",
            "⚠",
            path.display(),
            file_perms,
            path.display(),
        );
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_config_file_round_trip() {
        let mut config = ConfigFile { aliases: BTreeMap::new() };
        config.aliases.insert("test".to_string(), Alias {
            url: "http://localhost:8888".to_string(),
            api_key: "hc_u_root_test".to_string(),
            default: true,
        });

        let json = serde_json::to_string_pretty(&config).unwrap();
        let parsed: ConfigFile = serde_json::from_str(&json).unwrap();

        assert_eq!(parsed.aliases.len(), 1);
        assert_eq!(parsed.aliases["test"].url, "http://localhost:8888");
        assert!(parsed.aliases["test"].default);
    }

    #[test]
    fn test_default_alias() {
        let mut config = ConfigFile { aliases: BTreeMap::new() };
        config.aliases.insert("a".to_string(), Alias {
            url: "http://a".to_string(), api_key: "key".to_string(), default: false,
        });
        config.aliases.insert("b".to_string(), Alias {
            url: "http://b".to_string(), api_key: "key".to_string(), default: true,
        });

        let (name, _) = config.default_alias().unwrap();
        assert_eq!(name, "b");
    }

    #[test]
    fn test_no_default_alias() {
        let config = ConfigFile { aliases: BTreeMap::new() };
        assert!(config.default_alias().is_none());
    }
}
