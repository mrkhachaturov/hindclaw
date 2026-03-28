use anyhow::Result;
use clap::Subcommand;

use crate::{config::ResolvedConnection, output::OutputFormat, ui};
use crate::commands::common::{map_api_error, require_confirmation};
use hindclaw_client::Client;

#[derive(Subcommand)]
pub enum UserCommands {
    /// List all users
    #[command(visible_alias = "ls")]
    List,

    /// Create a user
    Add {
        /// User ID (e.g., email or internal identifier)
        id: String,
        /// Display name
        #[arg(long)]
        display_name: String,
        /// Email address
        #[arg(long)]
        email: Option<String>,
    },

    /// Show user details
    #[command(visible_alias = "show")]
    Info {
        /// User ID
        id: String,
    },

    /// Delete a user
    #[command(visible_alias = "rm")]
    Remove {
        /// User ID
        id: String,
    },

    /// Disable a user (sets is_active = false)
    Disable {
        /// User ID
        id: String,
    },

    /// Enable a user (sets is_active = true)
    Enable {
        /// User ID
        id: String,
    },

    /// List channels for a user
    Channels {
        /// User ID
        id: String,
    },

    /// Manage user channels
    #[command(subcommand)]
    Channel(UserChannelCommands),

    /// Manage user API keys
    #[command(subcommand)]
    Key(UserKeyCommands),
}

#[derive(Subcommand)]
pub enum UserChannelCommands {
    /// Add a channel to a user
    Add {
        /// User ID
        user_id: String,
        /// Provider (e.g., telegram)
        provider: String,
        /// Sender ID on the provider
        sender_id: String,
    },
    /// Remove a channel from a user
    #[command(visible_alias = "remove")]
    Rm {
        /// User ID
        user_id: String,
        /// Provider
        provider: String,
        /// Sender ID
        sender_id: String,
    },
}

#[derive(Subcommand)]
pub enum UserKeyCommands {
    /// Create an API key for a user
    Add {
        /// User ID
        user_id: String,
        /// Key description
        #[arg(long)]
        description: Option<String>,
    },
    /// List API keys for a user
    #[command(visible_alias = "list")]
    Ls {
        /// User ID
        user_id: String,
    },
    /// Delete an API key
    #[command(visible_alias = "remove")]
    Rm {
        /// User ID
        user_id: String,
        /// Key ID
        key_id: String,
    },
}

pub async fn run(cmd: UserCommands, conn: ResolvedConnection, format: OutputFormat, yes: bool) -> Result<()> {
    let client = crate::api::build_client(&conn)?;

    match cmd {
        UserCommands::List => user_list(&client, format).await,
        UserCommands::Add { id, display_name, email } => user_add(&client, &id, &display_name, email.as_deref()).await,
        UserCommands::Info { id } => user_info(&client, &id, format).await,
        UserCommands::Remove { id } => user_remove(&client, &id, yes).await,
        UserCommands::Disable { id } => user_set_active(&client, &id, false).await,
        UserCommands::Enable { id } => user_set_active(&client, &id, true).await,
        UserCommands::Channels { id } => user_channels(&client, &id, format).await,
        UserCommands::Channel(sub) => match sub {
            UserChannelCommands::Add { user_id, provider, sender_id } =>
                channel_add(&client, &user_id, &provider, &sender_id).await,
            UserChannelCommands::Rm { user_id, provider, sender_id } =>
                channel_rm(&client, &user_id, &provider, &sender_id, yes).await,
        },
        UserCommands::Key(sub) => match sub {
            UserKeyCommands::Add { user_id, description } =>
                key_add(&client, &user_id, description.as_deref()).await,
            UserKeyCommands::Ls { user_id } =>
                key_ls(&client, &user_id, format).await,
            UserKeyCommands::Rm { user_id, key_id } =>
                key_rm(&client, &user_id, &key_id, yes).await,
        },
    }
}

async fn user_list(client: &Client, format: OutputFormat) -> Result<()> {
    let users = client.list_users()
        .await
        .map_err(|e| map_api_error(e, "list users"))?
        .into_inner();

    match format {
        OutputFormat::Pretty => {
            ui::print_section_header("Users");
            let headers = &["ID", "DISPLAY NAME", "EMAIL", "STATUS"];
            let rows: Vec<Vec<String>> = users.iter().map(|u| {
                vec![
                    u.id.clone(),
                    u.display_name.clone(),
                    u.email.clone().unwrap_or_default(),
                    if u.is_active { "active".to_string() } else { "disabled".to_string() },
                ]
            }).collect();
            ui::print_table(headers, &rows);
        }
        _ => crate::output::print_output(&users, format)?,
    }
    Ok(())
}

async fn user_add(client: &Client, id: &str, display_name: &str, email: Option<&str>) -> Result<()> {
    let body = hindclaw_client::types::CreateUserRequest {
        id: id.to_string(),
        display_name: display_name.to_string(),
        email: email.map(|e| e.to_string()),
        is_active: true,
    };
    client.create_user(&body)
        .await
        .map_err(|e| map_api_error(e, "create user"))?;
    ui::print_success(&format!("User '{}' created", id));
    Ok(())
}

async fn user_info(client: &Client, id: &str, format: OutputFormat) -> Result<()> {
    let user = client.get_user(id)
        .await
        .map_err(|e| map_api_error(e, "get user"))?
        .into_inner();

    match format {
        OutputFormat::Pretty => {
            ui::print_section_header(&format!("User: {}", user.id));
            ui::print_kv("ID", &user.id);
            ui::print_kv("Display Name", &user.display_name);
            ui::print_kv("Email", user.email.as_deref().unwrap_or("(none)"));
            ui::print_kv("Status", if user.is_active { "active" } else { "disabled" });
        }
        _ => crate::output::print_output(&user, format)?,
    }
    Ok(())
}

async fn user_remove(client: &Client, id: &str, yes: bool) -> Result<()> {
    if !require_confirmation(&format!("Remove user '{}'", id), yes)? {
        println!("  Cancelled.");
        return Ok(());
    }
    client.delete_user(id)
        .await
        .map_err(|e| map_api_error(e, "delete user"))?;
    ui::print_success(&format!("User '{}' removed", id));
    Ok(())
}

async fn user_set_active(client: &Client, id: &str, active: bool) -> Result<()> {
    let body = hindclaw_client::types::UpdateUserRequest {
        display_name: None,
        email: None,
        is_active: Some(active),
    };
    client.update_user(id, &body)
        .await
        .map_err(|e| map_api_error(e, "update user"))?;
    let action = if active { "enabled" } else { "disabled" };
    ui::print_success(&format!("User '{}' {}", id, action));
    Ok(())
}

async fn user_channels(client: &Client, id: &str, format: OutputFormat) -> Result<()> {
    let channels = client.list_user_channels(id)
        .await
        .map_err(|e| map_api_error(e, "list user channels"))?
        .into_inner();

    match format {
        OutputFormat::Pretty => {
            let headers = &["PROVIDER", "SENDER ID"];
            let rows: Vec<Vec<String>> = channels.iter().map(|c| {
                vec![c.provider.clone(), c.sender_id.clone()]
            }).collect();
            ui::print_table(headers, &rows);
        }
        _ => crate::output::print_output(&channels, format)?,
    }
    Ok(())
}

async fn channel_add(client: &Client, user_id: &str, provider: &str, sender_id: &str) -> Result<()> {
    let body = hindclaw_client::types::AddChannelRequest {
        provider: provider.to_string(),
        sender_id: sender_id.to_string(),
    };
    client.add_user_channel(user_id, &body)
        .await
        .map_err(|e| map_api_error(e, "add channel"))?;
    ui::print_success(&format!("Channel {}:{} added to user '{}'", provider, sender_id, user_id));
    Ok(())
}

async fn channel_rm(client: &Client, user_id: &str, provider: &str, sender_id: &str, yes: bool) -> Result<()> {
    if !require_confirmation(&format!("Remove channel {}:{} from user '{}'", provider, sender_id, user_id), yes)? {
        println!("  Cancelled.");
        return Ok(());
    }
    client.remove_user_channel(user_id, provider, sender_id)
        .await
        .map_err(|e| map_api_error(e, "remove channel"))?;
    ui::print_success(&format!("Channel {}:{} removed", provider, sender_id));
    Ok(())
}

async fn key_add(client: &Client, user_id: &str, description: Option<&str>) -> Result<()> {
    let body = hindclaw_client::types::CreateApiKeyRequest {
        description: description.map(|d| d.to_string()),
    };
    let resp = client.create_api_key(user_id, &body)
        .await
        .map_err(|e| map_api_error(e, "create API key"))?
        .into_inner();

    println!();
    println!("  Access Key: {}", resp.api_key);
    println!();
    ui::print_warning("This is the only time the key will be shown. Save it now.");
    Ok(())
}

async fn key_ls(client: &Client, user_id: &str, format: OutputFormat) -> Result<()> {
    let keys = client.list_api_keys(user_id)
        .await
        .map_err(|e| map_api_error(e, "list API keys"))?
        .into_inner();

    match format {
        OutputFormat::Pretty => {
            let headers = &["KEY ID", "PREFIX", "DESCRIPTION"];
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

async fn key_rm(client: &Client, user_id: &str, key_id: &str, yes: bool) -> Result<()> {
    if !require_confirmation(&format!("Remove key '{}'", key_id), yes)? {
        println!("  Cancelled.");
        return Ok(());
    }
    client.delete_api_key(user_id, key_id)
        .await
        .map_err(|e| map_api_error(e, "delete API key"))?;
    ui::print_success(&format!("Key '{}' removed", key_id));
    Ok(())
}

