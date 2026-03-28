use anyhow::Result;
use clap::Subcommand;
use crate::{config::ResolvedConnection, output::OutputFormat};

#[derive(Subcommand)]
pub enum UserCommands {
    /// List all users
    List,
}

pub async fn run(cmd: UserCommands, _conn: ResolvedConnection, _format: OutputFormat, _yes: bool) -> Result<()> {
    match cmd {
        UserCommands::List => todo!("user list"),
    }
}
