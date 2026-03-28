use anyhow::Result;
use clap::Subcommand;
use crate::{config::ResolvedConnection, output::OutputFormat};

#[derive(Subcommand)]
pub enum SourceCommands {
    /// List marketplace sources
    List,
    /// Register a marketplace source
    Add {
        /// Source URL (e.g., https://github.com/hindclaw/community-templates)
        url: String,
        /// Override auto-derived source name
        #[arg(long)]
        alias: Option<String>,
        /// Auth token for private repositories
        #[arg(long)]
        auth_token: Option<String>,
    },
    /// Remove a marketplace source
    Rm {
        /// Source name
        name: String,
    },
}

pub async fn run(cmd: SourceCommands, _conn: ResolvedConnection, _format: OutputFormat, _yes: bool) -> Result<()> {
    match cmd {
        SourceCommands::List => todo!("source list"),
        SourceCommands::Add { .. } => todo!("source add"),
        SourceCommands::Rm { .. } => todo!("source rm"),
    }
}
