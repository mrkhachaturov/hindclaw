use anyhow::Result;
use clap::Subcommand;
use dialoguer::{Confirm, Password};
use std::io::{self, BufRead, IsTerminal};
use url::Url;

use crate::config::{Alias, ConfigFile};
use crate::output::OutputFormat;
use crate::ui;

#[derive(Subcommand)]
pub enum AliasCommands {
    /// Set a server alias
    Set {
        /// Alias name
        name: String,
        /// Server URL (e.g., http://localhost:8888)
        url: String,
        /// Read API key from stdin instead of interactive prompt
        #[arg(long)]
        stdin_key: bool,
        /// Set as default alias
        #[arg(long)]
        default: bool,
    },
    /// List aliases
    #[command(visible_alias = "list")]
    Ls,
    /// Remove an alias
    #[command(visible_alias = "remove")]
    Rm {
        /// Alias name to remove
        name: String,
    },
}

pub async fn run(cmd: AliasCommands, format: OutputFormat, yes: bool) -> Result<()> {
    match cmd {
        AliasCommands::Set { name, url, stdin_key, default } => {
            set_alias(&name, &url, stdin_key, default)?;
        }
        AliasCommands::Ls => {
            list_aliases(format)?;
        }
        AliasCommands::Rm { name } => {
            remove_alias(&name, yes)?;
        }
    }
    Ok(())
}

fn set_alias(name: &str, url_str: &str, stdin_key: bool, default: bool) -> Result<()> {
    // Validate URL
    let _parsed = Url::parse(url_str)
        .map_err(|e| anyhow::anyhow!("Invalid URL '{}': {}", url_str, e))?;
    if !url_str.starts_with("http://") && !url_str.starts_with("https://") {
        anyhow::bail!("URL must start with http:// or https://");
    }

    // Get API key
    let api_key = if stdin_key {
        let stdin = io::stdin();
        let line = stdin.lock().lines().next()
            .ok_or_else(|| anyhow::anyhow!("No input on stdin"))??;
        line.trim().to_string()
    } else {
        Password::new()
            .with_prompt("  Enter API key")
            .interact()?
    };

    if api_key.is_empty() {
        anyhow::bail!("API key cannot be empty");
    }

    let mut config = ConfigFile::load()?;

    // If setting as default, clear other defaults
    if default {
        for alias in config.aliases.values_mut() {
            alias.default = false;
        }
    }

    config.aliases.insert(name.to_string(), Alias {
        url: url_str.to_string(),
        api_key,
        default,
    });

    config.save()?;

    let suffix = if default { " (default)" } else { "" };
    ui::print_success(&format!("Alias '{}' saved{}", name, suffix));

    Ok(())
}

fn list_aliases(format: OutputFormat) -> Result<()> {
    let config = ConfigFile::load()?;

    match format {
        OutputFormat::Pretty => {
            if config.aliases.is_empty() {
                println!("  No aliases configured. Run `hindclaw alias set <name> <url>` to add one.");
                return Ok(());
            }
            let headers = &["NAME", "URL", "DEFAULT"];
            let rows: Vec<Vec<String>> = config.aliases.iter().map(|(name, alias)| {
                vec![
                    name.clone(),
                    alias.url.clone(),
                    if alias.default { "✓".to_string() } else { String::new() },
                ]
            }).collect();
            ui::print_table(headers, &rows);
        }
        _ => {
            // Always output valid structure, even when empty — scripts depend on parseable json/yaml
            use serde::Serialize;
            #[derive(Serialize)]
            struct AliasInfo { url: String, default: bool }

            let output: std::collections::BTreeMap<String, AliasInfo> = config.aliases.iter()
                .map(|(name, a)| (name.clone(), AliasInfo { url: a.url.clone(), default: a.default }))
                .collect();
            crate::output::print_output(&output, format)?;
        }
    }

    Ok(())
}

fn remove_alias(name: &str, yes: bool) -> Result<()> {
    let mut config = ConfigFile::load()?;

    if !config.aliases.contains_key(name) {
        anyhow::bail!("Alias '{}' not found", name);
    }

    if !yes {
        if !std::io::stdin().is_terminal() {
            anyhow::bail!("stdin is not a terminal. Use -y to confirm destructive operations non-interactively.");
        }
        let confirmed = Confirm::new()
            .with_prompt(format!("  Remove alias '{}'?", name))
            .default(false)
            .interact()?;
        if !confirmed {
            println!("  Cancelled.");
            return Ok(());
        }
    }

    config.aliases.remove(name);
    config.save()?;
    ui::print_success(&format!("Alias '{}' removed", name));

    Ok(())
}
