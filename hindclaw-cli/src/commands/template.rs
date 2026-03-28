use anyhow::Result;
use clap::Subcommand;
use crate::{config::ResolvedConnection, output::OutputFormat};
#[allow(unused_imports)]
use crate::commands::common::{map_api_error, require_confirmation};

#[derive(Subcommand)]
pub enum TemplateCommands {
    /// List installed templates
    List {
        /// Filter by scope (server or personal)
        #[arg(long)]
        scope: Option<String>,
    },
    /// Show template details
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

pub async fn run(cmd: TemplateCommands, _conn: ResolvedConnection, _format: OutputFormat, _yes: bool) -> Result<()> {
    match cmd {
        TemplateCommands::List { .. } => todo!("template list"),
        TemplateCommands::Info { .. } => todo!("template info"),
        TemplateCommands::Search { .. } => todo!("template search"),
        TemplateCommands::Install { .. } => todo!("template install"),
        TemplateCommands::Upgrade { .. } => todo!("template upgrade"),
        TemplateCommands::Create { .. } => todo!("template create"),
        TemplateCommands::Update { .. } => todo!("template update"),
        TemplateCommands::Remove { .. } => todo!("template remove"),
        TemplateCommands::Export { .. } => todo!("template export"),
        TemplateCommands::Import { .. } => todo!("template import"),
        TemplateCommands::Apply { .. } => todo!("template apply"),
    }
}
