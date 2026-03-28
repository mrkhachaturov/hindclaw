use anyhow::Result;
use clap::Subcommand;
use crate::{config::ResolvedConnection, output::OutputFormat};

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
    Info {
        /// Bank ID
        bank_id: String,
    },
    /// Remove the bank policy for a bank
    Rm {
        /// Bank ID
        bank_id: String,
    },
}

pub async fn run(cmd: BankPolicyCommands, _conn: ResolvedConnection, _format: OutputFormat, _yes: bool) -> Result<()> {
    match cmd {
        BankPolicyCommands::Set { .. } => todo!("bank-policy set"),
        BankPolicyCommands::Info { .. } => todo!("bank-policy info"),
        BankPolicyCommands::Rm { .. } => todo!("bank-policy rm"),
    }
}
