use anyhow::Result;
use clap::Subcommand;
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
        PolicyCommands::List => todo!("policy list"),
        PolicyCommands::Create { .. } => todo!("policy create"),
        PolicyCommands::Info { .. } => todo!("policy info"),
        PolicyCommands::Update { .. } => todo!("policy update"),
        PolicyCommands::Remove { .. } => todo!("policy remove"),
        PolicyCommands::Attach { .. } => todo!("policy attach"),
        PolicyCommands::Detach { .. } => todo!("policy detach"),
        PolicyCommands::Entities { .. } => todo!("policy entities"),
    }
}
