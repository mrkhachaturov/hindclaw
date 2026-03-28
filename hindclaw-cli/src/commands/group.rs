use anyhow::Result;
use clap::Subcommand;

use crate::{config::ResolvedConnection, output::OutputFormat, ui};
use crate::commands::user::{map_api_error, require_confirmation};
use hindclaw_client::Client;

#[derive(Subcommand)]
pub enum GroupCommands {
    /// List all groups
    List,

    /// Create a group
    Add {
        /// Group ID
        id: String,
        /// Display name
        #[arg(long)]
        display_name: String,
    },

    /// Show group details
    Info {
        /// Group ID
        id: String,
    },

    /// Delete a group
    Remove {
        /// Group ID
        id: String,
    },

    /// List members of a group
    Members {
        /// Group ID
        id: String,
    },

    /// Manage group members
    #[command(subcommand)]
    Member(GroupMemberCommands),
}

#[derive(Subcommand)]
pub enum GroupMemberCommands {
    /// Add a user to a group
    Add {
        /// Group ID
        group_id: String,
        /// User ID
        user_id: String,
    },
    /// Remove a user from a group
    Rm {
        /// Group ID
        group_id: String,
        /// User ID
        user_id: String,
    },
}

pub async fn run(cmd: GroupCommands, conn: ResolvedConnection, format: OutputFormat, yes: bool) -> Result<()> {
    let client = crate::api::build_client(&conn)?;

    match cmd {
        GroupCommands::List => group_list(&client, format).await,
        GroupCommands::Add { id, display_name } => group_add(&client, &id, &display_name).await,
        GroupCommands::Info { id } => group_info(&client, &id, format).await,
        GroupCommands::Remove { id } => group_remove(&client, &id, yes).await,
        GroupCommands::Members { id } => group_members(&client, &id, format).await,
        GroupCommands::Member(sub) => match sub {
            GroupMemberCommands::Add { group_id, user_id } =>
                member_add(&client, &group_id, &user_id).await,
            GroupMemberCommands::Rm { group_id, user_id } =>
                member_rm(&client, &group_id, &user_id, yes).await,
        },
    }
}

async fn group_list(client: &Client, format: OutputFormat) -> Result<()> {
    let groups = client.list_groups()
        .await
        .map_err(|e| map_api_error(e, "list groups"))?
        .into_inner();

    match format {
        OutputFormat::Pretty => {
            ui::print_section_header("Groups");
            let headers = &["ID", "DISPLAY NAME"];
            let rows: Vec<Vec<String>> = groups.iter().map(|g| {
                vec![
                    g.id.clone(),
                    g.display_name.clone(),
                ]
            }).collect();
            ui::print_table(headers, &rows);
        }
        _ => crate::output::print_output(&groups, format)?,
    }
    Ok(())
}

async fn group_add(client: &Client, id: &str, display_name: &str) -> Result<()> {
    let body = hindclaw_client::types::CreateGroupRequest {
        id: id.to_string(),
        display_name: display_name.to_string(),
    };
    client.create_group(&body)
        .await
        .map_err(|e| map_api_error(e, "create group"))?;
    ui::print_success(&format!("Group '{}' created", id));
    Ok(())
}

async fn group_info(client: &Client, id: &str, format: OutputFormat) -> Result<()> {
    let group = client.get_group(id)
        .await
        .map_err(|e| map_api_error(e, "get group"))?
        .into_inner();

    match format {
        OutputFormat::Pretty => {
            ui::print_section_header(&format!("Group: {}", group.id));
            ui::print_kv("ID", &group.id);
            ui::print_kv("Display Name", &group.display_name);
        }
        _ => crate::output::print_output(&group, format)?,
    }
    Ok(())
}

async fn group_remove(client: &Client, id: &str, yes: bool) -> Result<()> {
    if !require_confirmation(&format!("Remove group '{}'", id), yes)? {
        println!("  Cancelled.");
        return Ok(());
    }
    client.delete_group(id)
        .await
        .map_err(|e| map_api_error(e, "delete group"))?;
    ui::print_success(&format!("Group '{}' removed", id));
    Ok(())
}

async fn group_members(client: &Client, id: &str, format: OutputFormat) -> Result<()> {
    let members = client.list_group_members(id)
        .await
        .map_err(|e| map_api_error(e, "list group members"))?
        .into_inner();

    match format {
        OutputFormat::Pretty => {
            let headers = &["USER ID"];
            let rows: Vec<Vec<String>> = members.iter().map(|m| {
                vec![m.user_id.clone()]
            }).collect();
            ui::print_table(headers, &rows);
        }
        _ => crate::output::print_output(&members, format)?,
    }
    Ok(())
}

async fn member_add(client: &Client, group_id: &str, user_id: &str) -> Result<()> {
    let body = hindclaw_client::types::AddMemberRequest {
        user_id: user_id.to_string(),
    };
    client.add_group_member(group_id, &body)
        .await
        .map_err(|e| map_api_error(e, "add group member"))?;
    ui::print_success(&format!("User '{}' added to group '{}'", user_id, group_id));
    Ok(())
}

async fn member_rm(client: &Client, group_id: &str, user_id: &str, yes: bool) -> Result<()> {
    if !require_confirmation(&format!("Remove user '{}' from group '{}'", user_id, group_id), yes)? {
        println!("  Cancelled.");
        return Ok(());
    }
    client.remove_group_member(group_id, user_id)
        .await
        .map_err(|e| map_api_error(e, "remove group member"))?;
    ui::print_success(&format!("User '{}' removed from group '{}'", user_id, group_id));
    Ok(())
}
