use anyhow::Result;
use clap::Subcommand;

use crate::commands::common::{map_api_error, require_confirmation};
use crate::config::ResolvedConnection;
use crate::output::OutputFormat;
use crate::template_ref::TemplateRef;
use crate::ui;
use hindclaw_client::Client;

#[derive(Subcommand)]
pub enum TemplateCommands {
    /// List installed templates
    #[command(visible_alias = "ls")]
    List {
        /// Filter by scope (server or personal)
        #[arg(long)]
        scope: Option<String>,
    },
    /// Show template details
    #[command(visible_alias = "show")]
    Info {
        /// Template reference (scope/name) — custom templates only
        template: String,
    },
    /// Search marketplace for templates
    Search {
        /// Search query
        query: Option<String>,
        /// Filter by marketplace source
        #[arg(long)]
        source: Option<String>,
        /// Filter by tag
        #[arg(long)]
        tag: Option<String>,
    },
    /// Install a template from a marketplace source
    Install {
        /// Source and template name (source/name)
        template: String,
        /// Install scope (server or personal, default: personal)
        #[arg(long, default_value = "personal")]
        scope: String,
    },
    /// Update an installed marketplace template
    Upgrade {
        /// Template reference (scope/source/name)
        template: String,
    },
    /// Create a custom template from a JSON file
    Create {
        /// Path to template JSON file
        file: String,
        /// Template scope (server or personal, default: personal)
        #[arg(long, default_value = "personal")]
        scope: String,
    },
    /// Update a custom template from a JSON file
    Update {
        /// Template reference (scope/name) — custom templates only
        template: String,
        /// Path to template JSON file with updated fields
        file: String,
    },
    /// Remove a template
    #[command(visible_alias = "rm")]
    Remove {
        /// Template reference (scope/name) — custom templates only
        template: String,
    },
    /// Export a template as JSON to stdout
    Export {
        /// Template reference (scope/name) — custom templates only
        template: String,
    },
    /// Import a template from a JSON file
    Import {
        /// Path to template JSON file (or - for stdin)
        file: String,
        /// Install scope (server or personal, default: personal)
        #[arg(long, default_value = "personal")]
        scope: String,
    },
    /// Create a memory bank from a template
    Apply {
        /// Template reference (scope/name or scope/source/name)
        template: String,
        /// Bank ID for the new bank
        #[arg(long)]
        bank_id: String,
        /// Display name for the new bank
        #[arg(long)]
        bank_name: Option<String>,
    },
}

pub async fn run(cmd: TemplateCommands, conn: ResolvedConnection, format: OutputFormat, yes: bool) -> Result<()> {
    let client = crate::api::build_client(&conn)?;

    match cmd {
        TemplateCommands::List { scope } => template_list(&client, scope.as_deref(), format).await,
        TemplateCommands::Info { template } => template_info(&client, &template, format).await,
        TemplateCommands::Search { query, source, tag } => {
            template_search(&client, query.as_deref(), source.as_deref(), tag.as_deref(), format).await
        }
        TemplateCommands::Install { template, scope } => template_install(&client, &template, &scope, format).await,
        TemplateCommands::Upgrade { template } => template_upgrade(&client, &template, format).await,
        TemplateCommands::Create { file, scope } => template_create(&client, &file, &scope, format).await,
        TemplateCommands::Update { template, file } => template_update(&client, &template, &file, format).await,
        TemplateCommands::Remove { template } => template_remove(&client, &template, yes).await,
        TemplateCommands::Export { template } => template_export(&client, &template).await,
        TemplateCommands::Import { file, scope } => template_import(&client, &file, &scope, format).await,
        TemplateCommands::Apply { template, bank_id, bank_name } => {
            template_apply(&client, &template, &bank_id, bank_name.as_deref(), format).await
        }
    }
}

// --- list ---

async fn template_list(client: &Client, scope: Option<&str>, format: OutputFormat) -> Result<()> {
    let templates = client.list_templates(scope)
        .await
        .map_err(|e| map_api_error(e, "list templates"))?
        .into_inner();

    match format {
        OutputFormat::Pretty => {
            if templates.is_empty() {
                println!("  No templates found.");
                return Ok(());
            }
            let headers = &["NAME", "SCOPE", "SOURCE", "VERSION", "DESCRIPTION"];
            let rows: Vec<Vec<String>> = templates.iter().map(|t| {
                vec![
                    t.id.clone(),
                    t.scope.clone(),
                    t.source_name.clone().unwrap_or_else(|| "(custom)".into()),
                    t.version.clone().unwrap_or_else(|| "-".into()),
                    truncate(&t.description, 40),
                ]
            }).collect();
            ui::print_table(headers, &rows);
        }
        _ => crate::output::print_output(&templates, format)?,
    }
    Ok(())
}

// --- info ---

async fn template_info(client: &Client, template: &str, format: OutputFormat) -> Result<()> {
    let tref = TemplateRef::parse(template)?;
    if tref.source.is_some() {
        anyhow::bail!("'info' only supports custom templates (scope/name). For marketplace templates, use 'template list'.");
    }

    let resp = client.get_template(&tref.scope, &tref.name)
        .await
        .map_err(|e| map_api_error(e, "get template"))?
        .into_inner();

    match format {
        OutputFormat::Pretty => {
            ui::print_section_header(&format!("Template: {}", resp.id));
            ui::print_kv("Scope", &resp.scope);
            ui::print_kv("Source", resp.source_name.as_deref().unwrap_or("(custom)"));
            if let Some(v) = &resp.version {
                ui::print_kv("Version", v);
            }
            ui::print_kv("Author", &resp.author);
            ui::print_kv("Description", &resp.description);
            if !resp.tags.is_empty() {
                ui::print_kv("Tags", &resp.tags.join(", "));
            }
            println!();
            ui::print_kv("Retain Mode", &resp.retain_extraction_mode);
            ui::print_kv("Skepticism", &resp.disposition_skepticism.to_string());
            ui::print_kv("Literalism", &resp.disposition_literalism.to_string());
            ui::print_kv("Empathy", &resp.disposition_empathy.to_string());
            println!();
            ui::print_kv("Retain Mission", &resp.retain_mission);
            ui::print_kv("Reflect Mission", &resp.reflect_mission);
            if let Some(obs) = &resp.observations_mission {
                ui::print_kv("Observations", obs);
            }
            if !resp.directive_seeds.is_empty() {
                println!();
                println!("  {} directive seed(s)", resp.directive_seeds.len());
            }
            if !resp.mental_model_seeds.is_empty() {
                println!("  {} mental model seed(s)", resp.mental_model_seeds.len());
            }
        }
        _ => crate::output::print_output(&resp, format)?,
    }
    Ok(())
}

// --- search ---

async fn template_search(
    client: &Client,
    query: Option<&str>,
    source: Option<&str>,
    tag: Option<&str>,
    format: OutputFormat,
) -> Result<()> {
    let resp = client.marketplace_search(query, source, tag)
        .await
        .map_err(|e| map_api_error(e, "marketplace search"))?
        .into_inner();

    match format {
        OutputFormat::Pretty => {
            if resp.results.is_empty() {
                println!("  No templates found.");
                return Ok(());
            }
            println!("  {} result(s)\n", resp.total);
            let headers = &["SOURCE", "NAME", "VERSION", "INSTALLED", "DESCRIPTION"];
            let rows: Vec<Vec<String>> = resp.results.iter().map(|r| {
                let installed = if r.installed {
                    match &r.installed_version {
                        Some(v) => format!("✓ ({})", v),
                        None => "✓".into(),
                    }
                } else {
                    String::new()
                };
                vec![
                    r.source.clone(),
                    r.name.clone(),
                    r.version.clone(),
                    installed,
                    truncate(&r.description, 35),
                ]
            }).collect();
            ui::print_table(headers, &rows);
        }
        _ => crate::output::print_output(&resp, format)?,
    }
    Ok(())
}

// --- install ---

async fn template_install(client: &Client, template: &str, scope: &str, format: OutputFormat) -> Result<()> {
    let parts: Vec<&str> = template.splitn(2, '/').collect();
    if parts.len() != 2 {
        anyhow::bail!("Expected 'source/name' format (e.g., 'hindclaw/backend-python')");
    }
    let (source_name, template_name) = (parts[0], parts[1]);

    let body = hindclaw_client::types::InstallTemplateRequest {
        source: source_name.try_into().map_err(|e| anyhow::anyhow!("Invalid source: {}", e))?,
        name: template_name.try_into().map_err(|e| anyhow::anyhow!("Invalid name: {}", e))?,
        scope: scope.try_into().map_err(|e| anyhow::anyhow!("Invalid scope: {}", e))?,
    };
    let resp = client.install_template(&body)
        .await
        .map_err(|e| map_api_error(e, "install template"))?
        .into_inner();

    match format {
        OutputFormat::Pretty => {
            ui::print_success(&format!(
                "Installed '{}/{}' as {}/{}",
                source_name, template_name, resp.scope, resp.id
            ));
            if let Some(v) = &resp.version {
                println!("  Version: {}", v);
            }
        }
        _ => crate::output::print_output(&resp, format)?,
    }
    Ok(())
}

// --- upgrade ---

async fn template_upgrade(client: &Client, template: &str, format: OutputFormat) -> Result<()> {
    let tref = TemplateRef::parse(template)?;
    let source = tref.source.as_deref()
        .ok_or_else(|| anyhow::anyhow!(
            "Upgrade requires a marketplace template reference: scope/source/name"
        ))?;

    let resp = client.update_template_from_marketplace(&tref.scope, source, &tref.name)
        .await
        .map_err(|e| map_api_error(e, "upgrade template"))?
        .into_inner();

    match format {
        OutputFormat::Pretty => {
            if resp.updated {
                ui::print_success(&format!(
                    "Upgraded '{}' from {} to {}",
                    template,
                    resp.previous_version.as_deref().unwrap_or("?"),
                    resp.new_version.as_deref().unwrap_or("?"),
                ));
            } else {
                println!("  Already up to date.");
            }
        }
        _ => crate::output::print_output(&resp, format)?,
    }
    Ok(())
}

// --- create ---

async fn template_create(client: &Client, file: &str, scope: &str, format: OutputFormat) -> Result<()> {
    let content = std::fs::read_to_string(file)
        .map_err(|e| anyhow::anyhow!("Failed to read '{}': {}", file, e))?;
    let mut value: serde_json::Value = serde_json::from_str(&content)
        .map_err(|e| anyhow::anyhow!("Invalid template JSON in '{}': {}", file, e))?;

    // Inject --scope into the JSON body (CreateTemplateRequest requires scope)
    if let Some(obj) = value.as_object_mut() {
        obj.insert("scope".to_string(), serde_json::Value::String(scope.to_string()));
    } else {
        anyhow::bail!("Template JSON must be an object: {}", file);
    }

    let body: hindclaw_client::types::CreateTemplateRequest = serde_json::from_value(value)
        .map_err(|e| anyhow::anyhow!("Invalid template structure in '{}': {}", file, e))?;

    let resp = client.create_template(&body)
        .await
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

// --- update ---

async fn template_update(client: &Client, template: &str, file: &str, format: OutputFormat) -> Result<()> {
    let tref = TemplateRef::parse(template)?;
    if tref.source.is_some() {
        anyhow::bail!("'update' only supports custom templates (scope/name). For marketplace templates, use 'template upgrade'.");
    }

    let content = std::fs::read_to_string(file)
        .map_err(|e| anyhow::anyhow!("Failed to read '{}': {}", file, e))?;
    let body: hindclaw_client::types::UpdateTemplateRequest = serde_json::from_str(&content)
        .map_err(|e| anyhow::anyhow!("Invalid template JSON in '{}': {}", file, e))?;

    let resp = client.update_template(&tref.scope, &tref.name, &body)
        .await
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

// --- remove ---

async fn template_remove(client: &Client, template: &str, yes: bool) -> Result<()> {
    let tref = TemplateRef::parse(template)?;
    if tref.source.is_some() {
        anyhow::bail!("'remove' only supports custom templates (scope/name).");
    }

    if !require_confirmation(&format!("Remove template '{}'", template), yes)? {
        println!("  Cancelled.");
        return Ok(());
    }

    client.delete_template(&tref.scope, &tref.name)
        .await
        .map_err(|e| map_api_error(e, "remove template"))?;

    ui::print_success(&format!("Removed template '{}'", template));
    Ok(())
}

// --- export ---

async fn template_export(client: &Client, template: &str) -> Result<()> {
    let tref = TemplateRef::parse(template)?;
    if tref.source.is_some() {
        anyhow::bail!("'export' only supports custom templates (scope/name).");
    }

    let resp = client.get_template(&tref.scope, &tref.name)
        .await
        .map_err(|e| map_api_error(e, "get template"))?
        .into_inner();

    // Always output as JSON regardless of -o flag (export is for piping)
    println!("{}", serde_json::to_string_pretty(&resp)?);
    Ok(())
}

// --- import ---

async fn template_import(client: &Client, file: &str, scope: &str, format: OutputFormat) -> Result<()> {
    let content = if file == "-" {
        use std::io::Read;
        let mut buf = String::new();
        std::io::stdin().read_to_string(&mut buf)?;
        buf
    } else {
        std::fs::read_to_string(file)
            .map_err(|e| anyhow::anyhow!("Failed to read '{}': {}", file, e))?
    };

    let mut value: serde_json::Value = serde_json::from_str(&content)
        .map_err(|e| anyhow::anyhow!("Invalid template JSON: {}", e))?;

    // Inject --scope into the JSON body
    if let Some(obj) = value.as_object_mut() {
        obj.insert("scope".to_string(), serde_json::Value::String(scope.to_string()));
    } else {
        anyhow::bail!("Template JSON must be an object");
    }

    let body: hindclaw_client::types::CreateTemplateRequest = serde_json::from_value(value)
        .map_err(|e| anyhow::anyhow!("Invalid template structure: {}", e))?;

    let resp = client.create_template(&body)
        .await
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

// --- apply ---

async fn template_apply(client: &Client, template: &str, bank_id: &str, bank_name: Option<&str>, format: OutputFormat) -> Result<()> {
    let body = hindclaw_client::types::CreateBankFromTemplateRequest {
        bank_id: bank_id.try_into().map_err(|e| anyhow::anyhow!("Invalid bank ID: {}", e))?,
        template: template.try_into().map_err(|e| anyhow::anyhow!("Invalid template ref: {}", e))?,
        name: bank_name.map(|n| n.to_string()),
    };
    let resp = client.create_bank_from_template(&body)
        .await
        .map_err(|e| map_api_error(e, "create bank from template"))?
        .into_inner();

    match format {
        OutputFormat::Pretty => {
            ui::print_section_header(&format!("Bank: {}", resp.bank_id));
            ui::print_kv("Template", &resp.template.to_string());
            ui::print_kv("Bank Created", &format!("{}", resp.bank_created));
            ui::print_kv("Config Applied", &format!("{}", resp.config_applied));

            if !resp.directives.is_empty() {
                println!();
                println!("  Seeded {} directive(s):", resp.directives.len());
                for d in &resp.directives {
                    let status = if d.created { "✓" } else { "✗" };
                    let id = d.directive_id.as_deref().unwrap_or("-");
                    print!("    {} {} ({})", status, d.name, id);
                    if let Some(err) = &d.error {
                        print!(" — {}", err);
                    }
                    println!();
                }
            }
            if !resp.mental_models.is_empty() {
                println!("  Seeded {} mental model(s):", resp.mental_models.len());
                for m in &resp.mental_models {
                    let status = if m.created { "✓" } else { "✗" };
                    let id = m.mental_model_id.as_deref().unwrap_or("-");
                    print!("    {} {} ({})", status, m.name, id);
                    if let Some(err) = &m.error {
                        print!(" — {}", err);
                    }
                    println!();
                }
            }
            if !resp.errors.is_empty() {
                println!();
                for err in &resp.errors {
                    ui::print_warning(err);
                }
            } else {
                println!();
                ui::print_success("Bank ready");
            }
        }
        _ => crate::output::print_output(&resp, format)?,
    }
    Ok(())
}

fn truncate(s: &str, max_len: usize) -> String {
    if s.len() <= max_len {
        s.to_string()
    } else {
        format!("{}...", &s[..max_len - 3])
    }
}
