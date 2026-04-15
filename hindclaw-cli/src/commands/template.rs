use anyhow::{bail, Result};
use clap::Subcommand;

use crate::commands::common::{map_api_error, require_confirmation};
use crate::config::ResolvedConnection;
use crate::output::OutputFormat;
use crate::template_ref::TemplateRef;
use crate::ui;
use hindclaw_client::Client;
use hindclaw_client::types::{
    CreateTemplateRequest, InstallTemplateRequest, PatchTemplateRequest, TemplateResponse,
    TemplateScope,
};

#[derive(Subcommand)]
pub enum TemplateCommands {
    /// List installed templates
    #[command(visible_alias = "ls")]
    List {
        /// Filter by scope (server or personal, default: personal)
        #[arg(long, default_value = "personal")]
        scope: String,
    },
    /// Show template details
    #[command(visible_alias = "show")]
    Info {
        /// Template reference (scope/name)
        template: String,
    },
    /// Install a template from a template source
    Install {
        /// Source and template id (source_name/template_id)
        template: String,
        /// Destination scope (server requires admin, default: personal)
        #[arg(long, default_value = "personal")]
        scope: String,
        /// Optional alias to install the template under
        #[arg(long)]
        alias: Option<String>,
    },
    /// Update an installed template from its source
    Upgrade {
        /// Template reference (scope/name)
        template: String,
        /// Force update even if already at latest revision
        #[arg(long)]
        force: bool,
    },
    /// Create a hand-authored template from a JSON file
    Create {
        /// Path to template JSON file (CreateTemplateRequest shape)
        file: String,
        /// Destination scope (server requires admin, default: personal)
        #[arg(long, default_value = "personal")]
        scope: String,
    },
    /// Patch fields on an existing template from a JSON file
    ///
    /// Partial update: only fields present in the JSON body are applied. id,
    /// scope, and owner stay pinned to the existing row.
    Update {
        /// Template reference (scope/name)
        template: String,
        /// Path to JSON file with PatchTemplateRequest fields
        file: String,
    },
    /// Remove a template
    #[command(visible_alias = "rm")]
    Remove {
        /// Template reference (scope/name)
        template: String,
    },
    /// Export a template as JSON to stdout
    Export {
        /// Template reference (scope/name)
        template: String,
    },
    /// Import a template from a JSON file (alias for create, supports stdin as `-`)
    Import {
        /// Path to template JSON file, or `-` for stdin
        file: String,
        /// Destination scope (server requires admin, default: personal)
        #[arg(long, default_value = "personal")]
        scope: String,
    },
    /// Create a memory bank from a template
    Apply {
        /// Template reference (scope/name)
        template: String,
        /// Bank ID for the new bank
        #[arg(long)]
        bank_id: String,
        /// Display name for the new bank
        #[arg(long)]
        bank_name: Option<String>,
    },
}

pub async fn run(
    cmd: TemplateCommands,
    conn: ResolvedConnection,
    format: OutputFormat,
    yes: bool,
) -> Result<()> {
    let client = crate::api::build_client(&conn)?;

    match cmd {
        TemplateCommands::List { scope } => template_list(&client, &scope, format).await,
        TemplateCommands::Info { template } => template_info(&client, &template, format).await,
        TemplateCommands::Install { template, scope, alias } => {
            template_install(&client, &template, &scope, alias.as_deref(), format).await
        }
        TemplateCommands::Upgrade { template, force } => {
            template_upgrade(&client, &template, force, format).await
        }
        TemplateCommands::Create { file, scope } => {
            template_create(&client, &file, &scope, format).await
        }
        TemplateCommands::Update { template, file } => {
            template_update(&client, &template, &file, format).await
        }
        TemplateCommands::Remove { template } => template_remove(&client, &template, yes).await,
        TemplateCommands::Export { template } => template_export(&client, &template).await,
        TemplateCommands::Import { file, scope } => {
            template_import(&client, &file, &scope, format).await
        }
        TemplateCommands::Apply { template, bank_id, bank_name } => {
            template_apply(&client, &template, &bank_id, bank_name.as_deref(), format).await
        }
    }
}

// --- scope helpers ----------------------------------------------------- //

/// Parse a CLI --scope flag into the TemplateScope enum the API uses to
/// populate response fields. The string also chooses which endpoint family
/// (admin vs my) every call dispatches to.
fn parse_scope(scope: &str) -> Result<TemplateScope> {
    match scope {
        "server" => Ok(TemplateScope::Server),
        "personal" => Ok(TemplateScope::Personal),
        other => bail!("invalid --scope '{}', must be 'server' or 'personal'", other),
    }
}

// --- list -------------------------------------------------------------- //

async fn template_list(client: &Client, scope: &str, format: OutputFormat) -> Result<()> {
    let scope_enum = parse_scope(scope)?;
    let response = match scope_enum {
        TemplateScope::Server => client.list_admin_templates(None, None).await,
        TemplateScope::Personal => client.list_my_templates(None, None).await,
    }
    .map_err(|e| map_api_error(e, "list templates"))?
    .into_inner();

    let templates = response.templates;

    match format {
        OutputFormat::Pretty => {
            if templates.is_empty() {
                println!("  No templates found.");
                return Ok(());
            }
            let headers = &["NAME", "SCOPE", "SOURCE", "REVISION", "DESCRIPTION"];
            let rows: Vec<Vec<String>> = templates
                .iter()
                .map(|t| {
                    vec![
                        t.id.clone(),
                        t.scope.to_string(),
                        t.source_name.clone().unwrap_or_else(|| "(custom)".into()),
                        t.source_revision.clone().unwrap_or_else(|| "-".into()),
                        truncate(t.description.as_deref().unwrap_or(""), 40),
                    ]
                })
                .collect();
            ui::print_table(headers, &rows);
        }
        _ => crate::output::print_output(&templates, format)?,
    }
    Ok(())
}

// --- info -------------------------------------------------------------- //

async fn template_info(client: &Client, template: &str, format: OutputFormat) -> Result<()> {
    let tref = TemplateRef::parse(template)?;
    let resp = fetch_template(client, &tref).await?;

    match format {
        OutputFormat::Pretty => {
            ui::print_section_header(&format!("Template: {}", resp.id));
            ui::print_kv("Name", &resp.name);
            ui::print_kv("Scope", &resp.scope.to_string());
            if let Some(cat) = &resp.category {
                ui::print_kv("Category", cat);
            }
            if let Some(desc) = &resp.description {
                ui::print_kv("Description", desc);
            }
            if !resp.tags.is_empty() {
                ui::print_kv("Tags", &resp.tags.join(", "));
            }
            if !resp.integrations.is_empty() {
                ui::print_kv("Integrations", &resp.integrations.join(", "));
            }
            if let Some(src) = &resp.source_name {
                ui::print_kv("Source", src);
                ui::print_kv("Source Scope", &resp.source_scope.to_string());
                if let Some(rev) = &resp.source_revision {
                    ui::print_kv("Source Revision", rev);
                }
            } else {
                ui::print_kv("Source", "(hand-authored)");
            }
            ui::print_kv("Installed At", &resp.installed_at.to_rfc3339());
            ui::print_kv("Updated At", &resp.updated_at.to_rfc3339());
            println!();
            println!("  Manifest:");
            // Manifest is typed as serde_json::Map<String, Value> on the wire
            // (the server stores it as opaque JSONB). Pretty-print the raw
            // object rather than hand-picking fields so new BankTemplateConfig
            // fields from upstream flow through without CLI changes.
            let manifest_value = serde_json::Value::Object(resp.manifest.clone());
            let rendered = serde_json::to_string_pretty(&manifest_value)?;
            for line in rendered.lines() {
                println!("    {}", line);
            }
        }
        _ => crate::output::print_output(&resp, format)?,
    }
    Ok(())
}

// --- install ----------------------------------------------------------- //

async fn template_install(
    client: &Client,
    template: &str,
    scope: &str,
    alias: Option<&str>,
    format: OutputFormat,
) -> Result<()> {
    let scope_enum = parse_scope(scope)?;

    let parts: Vec<&str> = template.splitn(2, '/').collect();
    if parts.len() != 2 {
        bail!("Expected 'source_name/template_id' (e.g., 'hindclaw/backend-python')");
    }
    let (source_name, template_id) = (parts[0], parts[1]);

    // Sources default to server scope. A --source-scope flag can be added
    // later when we wire per-user sources into the CLI.
    let body = InstallTemplateRequest {
        source_name: source_name
            .try_into()
            .map_err(|e| anyhow::anyhow!("invalid source_name '{}': {}", source_name, e))?,
        source_scope: Some(TemplateScope::Server),
        alias_id: alias.map(|s| s.to_string()),
    };

    let resp = match scope_enum {
        TemplateScope::Server => client.install_admin_template(template_id, &body).await,
        TemplateScope::Personal => client.install_my_template(template_id, &body).await,
    }
    .map_err(|e| map_api_error(e, "install template"))?
    .into_inner();

    match format {
        OutputFormat::Pretty => {
            ui::print_success(&format!(
                "Installed '{}/{}' as {}/{}",
                source_name, template_id, resp.scope, resp.id
            ));
            if let Some(rev) = &resp.source_revision {
                println!("  Revision: {}", rev);
            }
        }
        _ => crate::output::print_output(&resp, format)?,
    }
    Ok(())
}

// --- upgrade ----------------------------------------------------------- //

async fn template_upgrade(
    client: &Client,
    template: &str,
    force: bool,
    format: OutputFormat,
) -> Result<()> {
    let tref = TemplateRef::parse(template)?;
    let scope_enum = scope_from_ref(&tref)?;

    let resp = match scope_enum {
        TemplateScope::Server => {
            client
                .update_admin_template_from_source(&tref.name, Some(force))
                .await
        }
        TemplateScope::Personal => {
            client
                .update_my_template_from_source(&tref.name, Some(force))
                .await
        }
    }
    .map_err(|e| map_api_error(e, "upgrade template"))?
    .into_inner();

    match format {
        OutputFormat::Pretty => {
            if resp.updated {
                ui::print_success(&format!(
                    "Upgraded '{}' from {} to {}",
                    tref,
                    resp.previous_revision.as_deref().unwrap_or("?"),
                    resp.new_revision.as_deref().unwrap_or("?"),
                ));
            } else {
                println!("  Already up to date.");
            }
        }
        _ => crate::output::print_output(&resp, format)?,
    }
    Ok(())
}

// --- create ------------------------------------------------------------ //

async fn template_create(
    client: &Client,
    file: &str,
    scope: &str,
    format: OutputFormat,
) -> Result<()> {
    let scope_enum = parse_scope(scope)?;
    let body = read_create_request(file)?;

    let resp = match scope_enum {
        TemplateScope::Server => client.create_admin_template(&body).await,
        TemplateScope::Personal => client.create_my_template(&body).await,
    }
    .map_err(|e| map_api_error(e, "create template"))?
    .into_inner();

    match format {
        OutputFormat::Pretty => {
            ui::print_success(&format!("Created template '{}'", resp.id));
        }
        _ => crate::output::print_output(&resp, format)?,
    }
    Ok(())
}

// --- update (PATCH) ---------------------------------------------------- //

async fn template_update(
    client: &Client,
    template: &str,
    file: &str,
    format: OutputFormat,
) -> Result<()> {
    let tref = TemplateRef::parse(template)?;
    let scope_enum = scope_from_ref(&tref)?;

    let content = std::fs::read_to_string(file)
        .map_err(|e| anyhow::anyhow!("Failed to read '{}': {}", file, e))?;
    let body: PatchTemplateRequest = serde_json::from_str(&content)
        .map_err(|e| anyhow::anyhow!("Invalid patch JSON in '{}': {}", file, e))?;

    let resp = match scope_enum {
        TemplateScope::Server => client.patch_admin_template(&tref.name, &body).await,
        TemplateScope::Personal => client.patch_my_template(&tref.name, &body).await,
    }
    .map_err(|e| map_api_error(e, "update template"))?
    .into_inner();

    match format {
        OutputFormat::Pretty => {
            ui::print_success(&format!("Updated template '{}'", template));
        }
        _ => crate::output::print_output(&resp, format)?,
    }
    Ok(())
}

// --- remove ------------------------------------------------------------ //

async fn template_remove(client: &Client, template: &str, yes: bool) -> Result<()> {
    let tref = TemplateRef::parse(template)?;
    let scope_enum = scope_from_ref(&tref)?;

    if !require_confirmation(&format!("Remove template '{}'", template), yes)? {
        println!("  Cancelled.");
        return Ok(());
    }

    match scope_enum {
        TemplateScope::Server => client.delete_admin_template(&tref.name).await,
        TemplateScope::Personal => client.delete_my_template(&tref.name).await,
    }
    .map_err(|e| map_api_error(e, "remove template"))?;

    ui::print_success(&format!("Removed template '{}'", template));
    Ok(())
}

// --- export ------------------------------------------------------------ //

async fn template_export(client: &Client, template: &str) -> Result<()> {
    let tref = TemplateRef::parse(template)?;
    let resp = fetch_template(client, &tref).await?;
    println!("{}", serde_json::to_string_pretty(&resp)?);
    Ok(())
}

// --- import ------------------------------------------------------------ //

async fn template_import(
    client: &Client,
    file: &str,
    scope: &str,
    format: OutputFormat,
) -> Result<()> {
    let scope_enum = parse_scope(scope)?;
    let content = if file == "-" {
        use std::io::Read;
        let mut buf = String::new();
        std::io::stdin().read_to_string(&mut buf)?;
        buf
    } else {
        std::fs::read_to_string(file)
            .map_err(|e| anyhow::anyhow!("Failed to read '{}': {}", file, e))?
    };

    let body: CreateTemplateRequest = serde_json::from_str(&content)
        .map_err(|e| anyhow::anyhow!("Invalid template JSON: {}", e))?;

    let resp = match scope_enum {
        TemplateScope::Server => client.create_admin_template(&body).await,
        TemplateScope::Personal => client.create_my_template(&body).await,
    }
    .map_err(|e| map_api_error(e, "import template"))?
    .into_inner();

    match format {
        OutputFormat::Pretty => {
            ui::print_success(&format!("Imported template '{}'", resp.id));
        }
        _ => crate::output::print_output(&resp, format)?,
    }
    Ok(())
}

// --- apply ------------------------------------------------------------- //

async fn template_apply(
    client: &Client,
    template: &str,
    bank_id: &str,
    bank_name: Option<&str>,
    format: OutputFormat,
) -> Result<()> {
    let body = hindclaw_client::types::CreateBankFromTemplateRequest {
        bank_id: bank_id
            .try_into()
            .map_err(|e| anyhow::anyhow!("invalid bank_id: {}", e))?,
        template: template
            .try_into()
            .map_err(|e| anyhow::anyhow!("invalid template ref: {}", e))?,
        name: bank_name.map(|s| s.to_string()),
    };
    let resp = client
        .create_bank_from_template(&body)
        .await
        .map_err(|e| map_api_error(e, "create bank from template"))?
        .into_inner();

    match format {
        OutputFormat::Pretty => {
            ui::print_section_header(&format!("Bank: {}", resp.bank_id));
            ui::print_kv("Template", &resp.template);
            ui::print_kv("Bank Created", &format!("{}", resp.bank_created));
            ui::print_kv("Config Applied", &format!("{}", resp.import_result.config_applied));

            let import = &resp.import_result;
            let total_directives = import.directives_created.len() + import.directives_updated.len();
            if total_directives > 0 {
                println!();
                println!(
                    "  Seeded {} directive(s): {} created, {} updated",
                    total_directives,
                    import.directives_created.len(),
                    import.directives_updated.len()
                );
            }
            let total_models = import.mental_models_created.len() + import.mental_models_updated.len();
            if total_models > 0 {
                println!(
                    "  Seeded {} mental model(s): {} created, {} updated",
                    total_models,
                    import.mental_models_created.len(),
                    import.mental_models_updated.len()
                );
            }
            if import.dry_run {
                println!();
                ui::print_warning("Dry run — no changes were persisted.");
            } else {
                println!();
                ui::print_success("Bank ready");
            }
        }
        _ => crate::output::print_output(&resp, format)?,
    }
    Ok(())
}

// --- helpers ----------------------------------------------------------- //

/// Fetch a template by scope-prefixed reference, dispatching to the
/// appropriate admin/my endpoint family.
async fn fetch_template(client: &Client, tref: &TemplateRef) -> Result<TemplateResponse> {
    let scope_enum = scope_from_ref(tref)?;
    let resp = match scope_enum {
        TemplateScope::Server => client.get_admin_template(&tref.name).await,
        TemplateScope::Personal => client.get_my_template(&tref.name).await,
    }
    .map_err(|e| map_api_error(e, "get template"))?
    .into_inner();
    Ok(resp)
}

/// Extract the TemplateScope from a TemplateRef's scope component.
fn scope_from_ref(tref: &TemplateRef) -> Result<TemplateScope> {
    parse_scope(&tref.scope)
}

/// Read a CreateTemplateRequest from a JSON file.
fn read_create_request(file: &str) -> Result<CreateTemplateRequest> {
    let content = std::fs::read_to_string(file)
        .map_err(|e| anyhow::anyhow!("Failed to read '{}': {}", file, e))?;
    serde_json::from_str(&content)
        .map_err(|e| anyhow::anyhow!("Invalid template JSON in '{}': {}", file, e))
}

fn truncate(s: &str, max_len: usize) -> String {
    if s.len() <= max_len {
        s.to_string()
    } else {
        format!("{}...", &s[..max_len - 3])
    }
}
