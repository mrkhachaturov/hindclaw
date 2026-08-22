use anyhow::{Context, Result};
use clap::Subcommand;
use std::fs;

use crate::commands::common::{map_api_error, require_confirmation};
use crate::config::ResolvedConnection;
use crate::output::OutputFormat;
use crate::ui;
use hindclaw_client::Client;

#[derive(Subcommand)]
pub enum BankPolicyCommands {
    /// Create or update a bank policy (upsert)
    Set {
        /// Bank ID
        bank_id: String,
        /// Path to JSON file containing the bank policy document
        policy_file: std::path::PathBuf,
    },
    /// Show the bank policy for a bank
    #[command(visible_alias = "show")]
    Info {
        /// Bank ID
        bank_id: String,
    },
    /// Remove the bank policy for a bank
    #[command(visible_alias = "remove")]
    Rm {
        /// Bank ID
        bank_id: String,
    },
}

pub async fn run(cmd: BankPolicyCommands, conn: ResolvedConnection, format: OutputFormat, yes: bool) -> Result<()> {
    let client = crate::api::build_client(&conn)?;

    match cmd {
        BankPolicyCommands::Set { bank_id, policy_file } => {
            bp_set(&client, &bank_id, &policy_file, format).await
        }
        BankPolicyCommands::Info { bank_id } => bp_info(&client, &bank_id, format).await,
        BankPolicyCommands::Rm { bank_id } => bp_rm(&client, &bank_id, yes).await,
    }
}

async fn bp_set(client: &Client, bank_id: &str, policy_file: &std::path::Path, format: OutputFormat) -> Result<()> {
    let raw = fs::read_to_string(policy_file)
        .with_context(|| format!("Failed to read '{}'", policy_file.display()))?;
    let value: serde_json::Value = serde_json::from_str(&raw)
        .with_context(|| format!("Invalid JSON in '{}'", policy_file.display()))?;
    let document = match value {
        serde_json::Value::Object(map) => map,
        _ => anyhow::bail!("Bank policy document must be a JSON object: {}", policy_file.display()),
    };

    let body = hindclaw_client::types::UpsertBankPolicyRequest { document };
    let policy = client.upsert_bank_policy(bank_id, &body)
        .await
        .map_err(|e| map_api_error(e, "upsert bank policy"))?
        .into_inner();

    match format {
        OutputFormat::Pretty => {
            print_bank_policy_info(&policy);
            ui::print_success(&format!("Bank policy for '{}' saved", bank_id));
        }
        _ => crate::output::print_output(&policy, format)?,
    }
    Ok(())
}

async fn bp_info(client: &Client, bank_id: &str, format: OutputFormat) -> Result<()> {
    let policy = client.get_bank_policy(bank_id)
        .await
        .map_err(|e| map_api_error(e, "get bank policy"))?
        .into_inner();

    match format {
        OutputFormat::Pretty => print_bank_policy_info(&policy),
        _ => crate::output::print_output(&policy, format)?,
    }
    Ok(())
}

async fn bp_rm(client: &Client, bank_id: &str, yes: bool) -> Result<()> {
    if !require_confirmation(&format!("Remove bank policy for '{}'", bank_id), yes)? {
        println!("  Cancelled.");
        return Ok(());
    }
    client.delete_bank_policy(bank_id)
        .await
        .map_err(|e| map_api_error(e, "delete bank policy"))?;
    ui::print_success(&format!("Bank policy for '{}' removed", bank_id));
    Ok(())
}

fn print_bank_policy_info(policy: &hindclaw_client::types::BankPolicyResponse) {
    ui::print_kv("Bank", &policy.bank_id);
    println!();
    println!("  Document:");
    let doc = serde_json::to_string_pretty(&policy.document).unwrap_or_default();
    for line in doc.lines() {
        println!("    {}", line);
    }
}
