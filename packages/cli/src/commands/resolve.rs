use anyhow::Result;
use clap::Args;

use crate::commands::common::map_api_error;
use crate::config::ResolvedConnection;
use crate::output::OutputFormat;
use crate::ui;

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

pub async fn run(args: ResolveArgs, conn: ResolvedConnection, format: OutputFormat) -> Result<()> {
    let client = crate::api::build_client(&conn)?;

    // Validate --sender format before calling API
    let sender_str = if let Some(sender) = &args.principal.sender {
        if !sender.contains(':') {
            anyhow::bail!("--sender must be in format 'provider:id', e.g. 'telegram:276243527'");
        }
        Some(sender.as_str())
    } else {
        None
    };

    // Single debug_resolve endpoint with optional query params
    let result = client.debug_resolve(
        Some(&args.action),              // action
        &args.bank,                       // bank (required)
        args.principal.sa.as_deref(),     // sa_id
        sender_str,                       // sender
        args.principal.user.as_deref(),   // user_id
    )
        .await
        .map_err(|e| map_api_error(e, "debug resolve"))?
        .into_inner();

    match format {
        OutputFormat::Pretty => print_resolve_result(&args.bank, &args.action, &result),
        _ => crate::output::print_output(&result, format)?,
    }
    Ok(())
}

fn print_resolve_result(bank_id: &str, action: &str, result: &serde_json::Value) {
    ui::print_section_header("Access Resolution");

    ui::print_kv("Bank", bank_id);
    ui::print_kv("Action", action);

    // debug_resolve returns untyped JSON — extract fields defensively
    if let Some(tenant) = result.get("tenant_id").and_then(|v| v.as_str()) {
        ui::print_kv("Tenant", tenant);
    }
    if let Some(principal) = result.get("principal_type").and_then(|v| v.as_str()) {
        ui::print_kv("Principal", principal);
    }

    if let Some(access) = result.get("access") {
        println!();
        println!("  Access Result:");
        let access_json = serde_json::to_string_pretty(access).unwrap_or_default();
        for line in access_json.lines() {
            println!("    {}", line);
        }
    }

    if let Some(bp) = result.get("bank_policy") {
        if !bp.is_null() {
            println!();
            println!("  Bank Policy:");
            let bp_json = serde_json::to_string_pretty(bp).unwrap_or_default();
            for line in bp_json.lines() {
                println!("    {}", line);
            }
        } else {
            println!();
            ui::print_kv("Bank Policy", "(none)");
        }
    }
}
