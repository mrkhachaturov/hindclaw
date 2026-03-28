use anyhow::Result;
use clap::Subcommand;
use crate::{config::ResolvedConnection, output::OutputFormat};

#[derive(Subcommand)]
pub enum GroupCommands {
    /// List all groups
    List,
}

pub async fn run(cmd: GroupCommands, _conn: ResolvedConnection, _format: OutputFormat, _yes: bool) -> Result<()> {
    match cmd {
        GroupCommands::List => todo!("group list"),
    }
}
