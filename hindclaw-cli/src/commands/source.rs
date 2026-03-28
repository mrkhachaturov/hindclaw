use anyhow::Result;
use clap::Subcommand;

use crate::commands::common::{map_api_error, require_confirmation};
use crate::config::ResolvedConnection;
use crate::output::OutputFormat;
use crate::ui;
use hindclaw_client::Client;

#[derive(Subcommand)]
pub enum SourceCommands {
    /// List marketplace sources
    #[command(visible_alias = "ls")]
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
    #[command(visible_alias = "remove")]
    Rm {
        /// Source name
        name: String,
    },
}

pub async fn run(cmd: SourceCommands, conn: ResolvedConnection, format: OutputFormat, yes: bool) -> Result<()> {
    let client = crate::api::build_client(&conn)?;

    match cmd {
        SourceCommands::List => source_list(&client, format).await,
        SourceCommands::Add { url, alias, auth_token } => {
            source_add(&client, &url, alias.as_deref(), auth_token.as_deref(), format).await
        }
        SourceCommands::Rm { name } => source_rm(&client, &name, yes).await,
    }
}

async fn source_list(client: &Client, format: OutputFormat) -> Result<()> {
    let sources = client.list_template_sources()
        .await
        .map_err(|e| map_api_error(e, "list template sources"))?
        .into_inner();

    match format {
        OutputFormat::Pretty => {
            if sources.is_empty() {
                println!("  No marketplace sources configured.");
                println!("  Run `hindclaw admin source add <url>` to register one.");
                return Ok(());
            }
            let headers = &["NAME", "URL", "AUTH", "CREATED"];
            let rows: Vec<Vec<String>> = sources.iter().map(|s| {
                vec![
                    s.name.clone(),
                    s.url.clone(),
                    if s.has_auth { "✓".into() } else { String::new() },
                    s.created_at.clone(),
                ]
            }).collect();
            ui::print_table(headers, &rows);
        }
        _ => crate::output::print_output(&sources, format)?,
    }
    Ok(())
}

async fn source_add(client: &Client, url: &str, alias: Option<&str>, auth_token: Option<&str>, format: OutputFormat) -> Result<()> {
    let body = hindclaw_client::types::CreateSourceRequest {
        url: url.try_into().map_err(|e| anyhow::anyhow!("Invalid URL: {}", e))?,
        alias: alias.map(|a| a.try_into()).transpose().map_err(|e| anyhow::anyhow!("Invalid alias: {}", e))?,
        auth_token: auth_token.map(|t| t.try_into()).transpose().map_err(|e| anyhow::anyhow!("Invalid token: {}", e))?,
    };
    let resp = client.create_template_source(&body)
        .await
        .map_err(|e| map_api_error(e, "create template source"))?
        .into_inner();

    match format {
        OutputFormat::Pretty => {
            ui::print_success(&format!("Source '{}' registered", resp.name));
            ui::print_kv("URL", &resp.url);
        }
        _ => crate::output::print_output(&resp, format)?,
    }
    Ok(())
}

async fn source_rm(client: &Client, name: &str, yes: bool) -> Result<()> {
    if !require_confirmation(&format!("Remove source '{}'", name), yes)? {
        println!("  Cancelled.");
        return Ok(());
    }

    client.delete_template_source(name)
        .await
        .map_err(|e| map_api_error(e, "remove template source"))?;

    ui::print_success(&format!("Source '{}' removed", name));
    Ok(())
}
