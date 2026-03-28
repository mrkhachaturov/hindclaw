use anyhow::Result;
use clap::Subcommand;
use crate::output::OutputFormat;

#[derive(Subcommand)]
pub enum AliasCommands {
    /// Set a server alias
    Set {
        /// Alias name
        name: String,
        /// Server URL
        url: String,
        /// Read API key from stdin instead of interactive prompt
        #[arg(long)]
        stdin_key: bool,
        /// Set as default alias
        #[arg(long)]
        default: bool,
    },
    /// List aliases
    Ls,
    /// Remove an alias
    Rm {
        /// Alias name to remove
        name: String,
    },
}

pub async fn run(cmd: AliasCommands, _format: OutputFormat) -> Result<()> {
    match cmd {
        AliasCommands::Set { .. } => todo!("alias set"),
        AliasCommands::Ls => todo!("alias ls"),
        AliasCommands::Rm { .. } => todo!("alias rm"),
    }
}
