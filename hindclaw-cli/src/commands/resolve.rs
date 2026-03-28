use anyhow::Result;
use clap::Args;
use crate::{config::ResolvedConnection, output::OutputFormat};

#[derive(Args)]
#[group(required = true, multiple = false)]
pub struct PrincipalArgs {
    /// Resolve for a user
    #[arg(long, value_name = "USER_ID")]
    user: Option<String>,

    /// Resolve for a service account
    #[arg(long, value_name = "SA_ID")]
    sa: Option<String>,

    /// Resolve for a sender (format: provider:id, e.g. telegram:276243527)
    #[arg(long, value_name = "PROVIDER:ID")]
    sender: Option<String>,
}

#[derive(Args)]
pub struct ResolveArgs {
    /// Bank ID to resolve access for
    #[arg(long, value_name = "BANK_ID")]
    bank: String,

    #[command(flatten)]
    principal: PrincipalArgs,

    /// Action to resolve (defaults to bank:recall)
    #[arg(long, default_value = "bank:recall", value_name = "ACTION")]
    action: String,
}

pub async fn run(_args: ResolveArgs, _conn: ResolvedConnection, _format: OutputFormat) -> Result<()> {
    todo!("resolve")
}
