use anyhow::Result;
use clap::Subcommand;

use crate::commands::common::{map_api_error, require_confirmation};
use crate::config::ResolvedConnection;
use crate::output::OutputFormat;
use crate::ui;
use hindclaw_client::Client;

#[derive(Subcommand)]
pub enum MySaCommands {
    /// List your service accounts
    #[command(visible_alias = "ls")]
    List,
    /// Create a service account
    Add {
        /// Service account ID
        id: String,
        /// Display name
        #[arg(long, value_name = "NAME")]
        display_name: String,
        /// Scoping policy ID (optional)
        #[arg(long, value_name = "POLICY_ID")]
        scoping_policy: Option<String>,
    },
    /// Show service account details
    #[command(visible_alias = "show")]
    Info {
        /// Service account ID
        id: String,
    },
    /// Update service account display name
    Update {
        /// Service account ID
        id: String,
        /// New display name
        #[arg(long, value_name = "NAME")]
        display_name: String,
    },
    /// Remove a service account
    #[command(visible_alias = "rm")]
    Remove {
        /// Service account ID
        id: String,
    },
    /// Manage SA API keys
    #[command(subcommand)]
    Key(MySaKeyCommands),
}

#[derive(Subcommand)]
pub enum MySaKeyCommands {
    /// Create an API key for a service account
    Add {
        /// Service account ID
        sa_id: String,
        /// Key description
        #[arg(long, value_name = "TEXT")]
        description: Option<String>,
    },
    /// List API keys for a service account
    #[command(visible_alias = "list")]
    Ls {
        /// Service account ID
        sa_id: String,
    },
    /// Remove an API key
    #[command(visible_alias = "remove")]
    Rm {
        /// Service account ID
        sa_id: String,
        /// Key ID
        key_id: String,
    },
}

pub async fn run(cmd: MySaCommands, conn: ResolvedConnection, format: OutputFormat, yes: bool) -> Result<()> {
    let client = crate::api::build_client(&conn)?;

    match cmd {
        MySaCommands::List => sa_list(&client, format).await,
        MySaCommands::Add { id, display_name, scoping_policy } => {
            sa_add(&client, &id, &display_name, scoping_policy.as_deref()).await
        }
        MySaCommands::Info { id } => sa_info(&client, &id, format).await,
        MySaCommands::Update { id, display_name } => {
            sa_update(&client, &id, &display_name).await
        }
        MySaCommands::Remove { id } => sa_remove(&client, &id, yes).await,
        MySaCommands::Key(key_cmd) => match key_cmd {
            MySaKeyCommands::Add { sa_id, description } => {
                key_add(&client, &sa_id, description.as_deref()).await
            }
            MySaKeyCommands::Ls { sa_id } => key_ls(&client, &sa_id, format).await,
            MySaKeyCommands::Rm { sa_id, key_id } => key_rm(&client, &sa_id, &key_id, yes).await,
        },
    }
}

async fn sa_list(client: &Client, format: OutputFormat) -> Result<()> {
    let sas = client.list_my_service_accounts()
        .await
        .map_err(|e| map_api_error(e, "list service accounts"))?
        .into_inner();

    match format {
        OutputFormat::Pretty => {
            let headers = &["ID", "DISPLAY NAME", "SCOPING POLICY", "STATUS"];
            let rows: Vec<Vec<String>> = sas.iter().map(|sa| {
                vec![
                    sa.id.clone(),
                    sa.display_name.clone(),
                    sa.scoping_policy_id.clone().unwrap_or_default(),
                    if sa.is_active { "active".to_string() } else { "disabled".to_string() },
                ]
            }).collect();
            ui::print_table(headers, &rows);
        }
        _ => crate::output::print_output(&sas, format)?,
    }
    Ok(())
}

async fn sa_add(client: &Client, id: &str, display_name: &str, scoping_policy: Option<&str>) -> Result<()> {
    let body = hindclaw_client::types::CreateSelfServiceAccountRequest {
        id: id.to_string(),
        display_name: display_name.to_string(),
        scoping_policy_id: scoping_policy.map(|s| s.to_string()),
    };
    let sa = client.create_my_service_account(&body)
        .await
        .map_err(|e| map_api_error(e, "create service account"))?
        .into_inner();
    print_sa_info(&sa);
    ui::print_success(&format!("Service account '{}' created", sa.id));
    Ok(())
}

async fn sa_info(client: &Client, id: &str, format: OutputFormat) -> Result<()> {
    let sa = client.get_my_service_account(id)
        .await
        .map_err(|e| map_api_error(e, "get service account"))?
        .into_inner();

    match format {
        OutputFormat::Pretty => print_sa_info(&sa),
        _ => crate::output::print_output(&sa, format)?,
    }
    Ok(())
}

async fn sa_update(client: &Client, id: &str, display_name: &str) -> Result<()> {
    let body = hindclaw_client::types::UpdateSelfServiceAccountRequest {
        display_name: display_name.to_string(),
    };
    let sa = client.update_my_service_account(id, &body)
        .await
        .map_err(|e| map_api_error(e, "update service account"))?
        .into_inner();
    print_sa_info(&sa);
    ui::print_success(&format!("Service account '{}' updated", sa.id));
    Ok(())
}

async fn sa_remove(client: &Client, id: &str, yes: bool) -> Result<()> {
    if !require_confirmation(&format!("Remove service account '{}'", id), yes)? {
        println!("  Cancelled.");
        return Ok(());
    }
    client.delete_my_service_account(id)
        .await
        .map_err(|e| map_api_error(e, "delete service account"))?;
    ui::print_success(&format!("Service account '{}' removed", id));
    Ok(())
}

async fn key_add(client: &Client, sa_id: &str, description: Option<&str>) -> Result<()> {
    let body = hindclaw_client::types::CreateSaKeyRequest {
        description: description.map(|d| d.to_string()),
    };
    let key = client.create_my_sa_key(sa_id, &body)
        .await
        .map_err(|e| map_api_error(e, "create SA key"))?
        .into_inner();

    println!();
    println!("  Access Key: {}", key.api_key);
    println!();
    ui::print_warning("This is the only time the key will be shown. Save it now.");
    Ok(())
}

async fn key_ls(client: &Client, sa_id: &str, format: OutputFormat) -> Result<()> {
    let keys = client.list_my_sa_keys(sa_id)
        .await
        .map_err(|e| map_api_error(e, "list SA keys"))?
        .into_inner();

    match format {
        OutputFormat::Pretty => {
            let headers = &["ID", "PREFIX", "DESCRIPTION"];
            let rows: Vec<Vec<String>> = keys.iter().map(|k| {
                vec![
                    k.id.clone(),
                    k.api_key_prefix.clone(),
                    k.description.clone().unwrap_or_default(),
                ]
            }).collect();
            ui::print_table(headers, &rows);
        }
        _ => crate::output::print_output(&keys, format)?,
    }
    Ok(())
}

async fn key_rm(client: &Client, sa_id: &str, key_id: &str, yes: bool) -> Result<()> {
    if !require_confirmation(&format!("Remove key '{}' from SA '{}'", key_id, sa_id), yes)? {
        println!("  Cancelled.");
        return Ok(());
    }
    client.delete_my_sa_key(sa_id, key_id)
        .await
        .map_err(|e| map_api_error(e, "delete SA key"))?;
    ui::print_success(&format!("Key '{}' removed from service account '{}'", key_id, sa_id));
    Ok(())
}

fn print_sa_info(sa: &hindclaw_client::types::ServiceAccountResponse) {
    ui::print_kv("ID", &sa.id);
    ui::print_kv("Display Name", &sa.display_name);
    ui::print_kv("Status", if sa.is_active { "active" } else { "disabled" });
    ui::print_kv("Scoping Policy", sa.scoping_policy_id.as_deref().unwrap_or("(none)"));
}
