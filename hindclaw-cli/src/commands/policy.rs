use anyhow::{Context, Result};
use clap::Subcommand;
use colored::*;
use std::path::PathBuf;

use crate::commands::common::{map_api_error, require_confirmation};
use crate::config::ResolvedConnection;
use crate::output::OutputFormat;
use crate::ui;
use hindclaw_client::Client;

#[derive(Subcommand)]
pub enum PolicyCommands {
    /// List all policies
    List,

    /// Create a policy from a JSON document file
    Create {
        /// Policy ID
        id: String,
        /// Path to policy document JSON file
        file: PathBuf,
        /// Human-readable display name (required)
        #[arg(long)]
        display_name: String,
    },

    /// Show policy details
    Info {
        /// Policy ID
        id: String,
    },

    /// Update a policy from a JSON document file
    Update {
        /// Policy ID
        id: String,
        /// Path to updated policy document JSON file
        file: PathBuf,
        /// Human-readable display name
        #[arg(long)]
        display_name: Option<String>,
    },

    /// Remove a policy (requires confirmation)
    Remove {
        /// Policy ID
        id: String,
    },

    /// Attach a policy to a user or group
    Attach {
        /// Policy ID
        policy_id: String,
        /// Attach to a user with this ID
        #[arg(long, conflicts_with = "group")]
        user: Option<String>,
        /// Attach to a group with this ID
        #[arg(long, conflicts_with = "user")]
        group: Option<String>,
        /// Attachment priority (default: 0, higher = evaluated first)
        #[arg(long, default_value = "0")]
        priority: i64,
    },

    /// Detach a policy from a user or group (requires confirmation)
    Detach {
        /// Policy ID
        policy_id: String,
        /// Detach from a user with this ID
        #[arg(long, conflicts_with = "group")]
        user: Option<String>,
        /// Detach from a group with this ID
        #[arg(long, conflicts_with = "user")]
        group: Option<String>,
    },

    /// List all users and groups this policy is attached to
    Entities {
        /// Policy ID
        policy_id: String,
    },
}

pub async fn run(cmd: PolicyCommands, conn: ResolvedConnection, format: OutputFormat, yes: bool) -> Result<()> {
    let client = crate::api::build_client(&conn)?;

    match cmd {
        PolicyCommands::List => list_policies(&client, format).await,
        PolicyCommands::Create { id, file, display_name } => {
            create_policy(&client, &id, &file, &display_name, format).await
        }
        PolicyCommands::Info { id } => info_policy(&client, &id, format).await,
        PolicyCommands::Update { id, file, display_name } => {
            update_policy(&client, &id, &file, display_name.as_deref(), format).await
        }
        PolicyCommands::Remove { id } => remove_policy(&client, &id, yes).await,
        PolicyCommands::Attach { .. } => todo!("policy attach"),
        PolicyCommands::Detach { .. } => todo!("policy detach"),
        PolicyCommands::Entities { .. } => todo!("policy entities"),
    }
}

async fn list_policies(client: &Client, format: OutputFormat) -> Result<()> {
    let policies = client.list_policies()
        .await
        .map_err(|e| map_api_error(e, "list policies"))?
        .into_inner();

    match format {
        OutputFormat::Pretty => {
            let headers = &["ID", "DISPLAY NAME", "BUILTIN"];
            let rows: Vec<Vec<String>> = policies.iter().map(|p| {
                vec![
                    p.id.clone(),
                    p.display_name.clone(),
                    if p.is_builtin { "yes".to_string() } else { String::new() },
                ]
            }).collect();
            ui::print_table(headers, &rows);
        }
        _ => crate::output::print_output(&policies, format)?,
    }
    Ok(())
}

async fn create_policy(
    client: &Client,
    id: &str,
    file: &std::path::Path,
    display_name: &str,
    format: OutputFormat,
) -> Result<()> {
    let document = read_policy_document(file)?;

    let body = hindclaw_client::types::CreatePolicyRequest {
        id: id.to_string(),
        display_name: display_name.to_string(),
        document,
    };

    let response = client.create_policy(&body)
        .await
        .map_err(|e| map_api_error(e, "create policy"))?
        .into_inner();

    match format {
        OutputFormat::Pretty => {
            ui::print_success(&format!("Policy '{}' created.", response.id));
        }
        _ => crate::output::print_output(&response, format)?,
    }
    Ok(())
}

async fn info_policy(client: &Client, id: &str, format: OutputFormat) -> Result<()> {
    let policy = client.get_policy(id)
        .await
        .map_err(|e| map_api_error(e, "get policy"))?
        .into_inner();

    match format {
        OutputFormat::Pretty => {
            ui::print_kv("ID", &policy.id);
            ui::print_kv("Display Name", &policy.display_name);
            ui::print_kv("Builtin", if policy.is_builtin { "yes" } else { "no" });
            println!();
            println!("  {}:", "Document".bold());
            let doc_json = serde_json::to_string_pretty(&policy.document)?;
            for line in doc_json.lines() {
                println!("    {}", line);
            }
        }
        _ => crate::output::print_output(&policy, format)?,
    }
    Ok(())
}

async fn update_policy(
    client: &Client,
    id: &str,
    file: &std::path::Path,
    display_name: Option<&str>,
    format: OutputFormat,
) -> Result<()> {
    let document = read_policy_document(file)?;

    let body = hindclaw_client::types::UpdatePolicyRequest {
        display_name: display_name.map(str::to_string),
        document: Some(document),
    };

    let response = client.update_policy(id, &body)
        .await
        .map_err(|e| map_api_error(e, "update policy"))?
        .into_inner();

    match format {
        OutputFormat::Pretty => {
            ui::print_success(&format!("Policy '{}' updated.", response.id));
        }
        _ => crate::output::print_output(&response, format)?,
    }
    Ok(())
}

async fn remove_policy(client: &Client, id: &str, yes: bool) -> Result<()> {
    if !require_confirmation(&format!("Remove policy '{}'", id), yes)? {
        println!("  Cancelled.");
        return Ok(());
    }

    client.delete_policy(id)
        .await
        .map_err(|e| map_api_error(e, "remove policy"))?;

    ui::print_success(&format!("Policy '{}' removed.", id));
    Ok(())
}

fn read_policy_document(file: &std::path::Path) -> Result<serde_json::Map<String, serde_json::Value>> {
    let content = std::fs::read_to_string(file)
        .with_context(|| format!("Failed to read policy document: {}", file.display()))?;
    let value: serde_json::Value = serde_json::from_str(&content)
        .with_context(|| format!("Invalid JSON in {}", file.display()))?;
    match value {
        serde_json::Value::Object(map) => Ok(map),
        _ => anyhow::bail!("Policy document must be a JSON object: {}", file.display()),
    }
}
