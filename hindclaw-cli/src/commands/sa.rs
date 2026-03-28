use anyhow::Result;
use clap::Subcommand;

use crate::commands::common::{map_api_error, require_confirmation};
use crate::config::ResolvedConnection;
use crate::output::OutputFormat;
use crate::ui;
use hindclaw_client::Client;

#[derive(Subcommand)]
pub enum SaCommands {
    /// List service accounts
    #[command(visible_alias = "ls")]
    List,
    /// Create a service account
    Add {
        /// Service account ID
        id: String,
        /// Owner user ID
        #[arg(long)]
        owner: String,
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
    /// Update a service account
    Update {
        /// Service account ID
        id: String,
        /// New display name
        #[arg(long, value_name = "NAME")]
        display_name: Option<String>,
        /// New scoping policy ID
        #[arg(long, value_name = "POLICY_ID")]
        scoping_policy: Option<String>,
        /// Remove scoping policy (sets to null)
        #[arg(long, conflicts_with = "scoping_policy")]
        clear_scoping_policy: bool,
    },
    /// Remove a service account
    #[command(visible_alias = "rm")]
    Remove {
        /// Service account ID
        id: String,
    },
    /// Disable a service account
    Disable {
        /// Service account ID
        id: String,
    },
    /// Enable a service account
    Enable {
        /// Service account ID
        id: String,
    },
    /// Manage SA API keys
    #[command(subcommand)]
    Key(SaKeyCommands),
}

#[derive(Subcommand)]
pub enum SaKeyCommands {
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

pub async fn run(cmd: SaCommands, conn: ResolvedConnection, format: OutputFormat, yes: bool) -> Result<()> {
    let client = crate::api::build_client(&conn)?;

    match cmd {
        SaCommands::List => sa_list(&client, format).await,
        SaCommands::Add { id, owner, display_name, scoping_policy } => {
            sa_add(&client, &id, &owner, &display_name, scoping_policy.as_deref()).await
        }
        SaCommands::Info { id } => sa_info(&client, &id, format).await,
        SaCommands::Update { id, display_name, scoping_policy, clear_scoping_policy } => {
            sa_update(&conn, &id, display_name.as_deref(), scoping_policy.as_deref(), clear_scoping_policy).await
        }
        SaCommands::Remove { id } => sa_remove(&client, &id, yes).await,
        SaCommands::Disable { id } => sa_toggle(&client, &id, false).await,
        SaCommands::Enable { id } => sa_toggle(&client, &id, true).await,
        SaCommands::Key(key_cmd) => match key_cmd {
            SaKeyCommands::Add { sa_id, description } => {
                key_add(&client, &sa_id, description.as_deref()).await
            }
            SaKeyCommands::Ls { sa_id } => key_ls(&client, &sa_id, format).await,
            SaKeyCommands::Rm { sa_id, key_id } => key_rm(&client, &sa_id, &key_id, yes).await,
        },
    }
}

async fn sa_list(client: &Client, format: OutputFormat) -> Result<()> {
    let sas = client.list_service_accounts()
        .await
        .map_err(|e| map_api_error(e, "list service accounts"))?
        .into_inner();

    match format {
        OutputFormat::Pretty => {
            let headers = &["ID", "OWNER", "DISPLAY NAME", "SCOPING POLICY", "STATUS"];
            let rows: Vec<Vec<String>> = sas.iter().map(|sa| {
                vec![
                    sa.id.clone(),
                    sa.owner_user_id.clone(),
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

async fn sa_add(client: &Client, id: &str, owner: &str, display_name: &str, scoping_policy: Option<&str>) -> Result<()> {
    let body = hindclaw_client::types::CreateServiceAccountRequest {
        id: id.to_string(),
        owner_user_id: owner.to_string(),
        display_name: display_name.to_string(),
        scoping_policy_id: scoping_policy.map(|s| s.to_string()),
    };
    let sa = client.create_service_account(&body)
        .await
        .map_err(|e| map_api_error(e, "create service account"))?
        .into_inner();
    print_sa_info(&sa);
    ui::print_success(&format!("Service account '{}' created", sa.id));
    Ok(())
}

async fn sa_info(client: &Client, id: &str, format: OutputFormat) -> Result<()> {
    let sa = client.get_service_account(id)
        .await
        .map_err(|e| map_api_error(e, "get service account"))?
        .into_inner();

    match format {
        OutputFormat::Pretty => print_sa_info(&sa),
        _ => crate::output::print_output(&sa, format)?,
    }
    Ok(())
}

async fn sa_update(conn: &crate::config::ResolvedConnection, id: &str, display_name: Option<&str>, scoping_policy: Option<&str>, clear_scoping_policy: bool) -> Result<()> {
    // Build raw JSON with only the fields the user provided.
    // The generated client's skip_serializing_if omits None fields, which is correct
    // for "don't change" but can't express "set to null". Raw JSON lets us send
    // explicit null for --clear-scoping-policy while omitting unchanged fields.
    let mut body = serde_json::Map::new();
    if let Some(dn) = display_name {
        body.insert("display_name".into(), serde_json::Value::String(dn.to_string()));
    }
    if clear_scoping_policy {
        body.insert("scoping_policy_id".into(), serde_json::Value::Null);
    } else if let Some(sp) = scoping_policy {
        body.insert("scoping_policy_id".into(), serde_json::Value::String(sp.to_string()));
    }

    let http_client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(30))
        .default_headers({
            let mut h = reqwest::header::HeaderMap::new();
            h.insert(
                reqwest::header::AUTHORIZATION,
                format!("Bearer {}", conn.api_key).parse()
                    .map_err(|_| anyhow::anyhow!("Invalid API key format"))?,
            );
            h
        })
        .build()?;

    let resp = http_client
        .put(format!("{}/ext/hindclaw/service-accounts/{}", conn.url, id))
        .json(&body)
        .send()
        .await
        .map_err(|e| anyhow::anyhow!("Request failed (update service account): {}", e))?;

    if !resp.status().is_success() {
        let status = resp.status();
        anyhow::bail!("API error {} (update service account)", status);
    }

    let sa: hindclaw_client::types::ServiceAccountResponse = resp.json().await
        .map_err(|e| anyhow::anyhow!("Failed to parse response: {}", e))?;
    print_sa_info(&sa);
    ui::print_success(&format!("Service account '{}' updated", sa.id));
    Ok(())
}

async fn sa_remove(client: &Client, id: &str, yes: bool) -> Result<()> {
    if !require_confirmation(&format!("Remove service account '{}'", id), yes)? {
        println!("  Cancelled.");
        return Ok(());
    }
    client.delete_service_account(id)
        .await
        .map_err(|e| map_api_error(e, "delete service account"))?;
    ui::print_success(&format!("Service account '{}' removed", id));
    Ok(())
}

async fn sa_toggle(client: &Client, id: &str, is_active: bool) -> Result<()> {
    let body = hindclaw_client::types::UpdateServiceAccountRequest {
        display_name: None,
        scoping_policy_id: None,
        is_active: Some(is_active),
    };
    client.update_service_account(id, &body)
        .await
        .map_err(|e| map_api_error(e, "update service account"))?;
    let state = if is_active { "enabled" } else { "disabled" };
    ui::print_success(&format!("Service account '{}' {}", id, state));
    Ok(())
}

async fn key_add(client: &Client, sa_id: &str, description: Option<&str>) -> Result<()> {
    let body = hindclaw_client::types::CreateSaKeyRequest {
        description: description.map(|d| d.to_string()),
    };
    let key = client.create_sa_key(sa_id, &body)
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
    let keys = client.list_sa_keys(sa_id)
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
    client.delete_sa_key(sa_id, key_id)
        .await
        .map_err(|e| map_api_error(e, "delete SA key"))?;
    ui::print_success(&format!("Key '{}' removed from service account '{}'", key_id, sa_id));
    Ok(())
}

fn print_sa_info(sa: &hindclaw_client::types::ServiceAccountResponse) {
    ui::print_kv("ID", &sa.id);
    ui::print_kv("Owner", &sa.owner_user_id);
    ui::print_kv("Display Name", &sa.display_name);
    ui::print_kv("Status", if sa.is_active { "active" } else { "disabled" });
    ui::print_kv("Scoping Policy", sa.scoping_policy_id.as_deref().unwrap_or("(none)"));
}
