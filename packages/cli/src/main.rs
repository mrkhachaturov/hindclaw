mod api;
mod config;
mod output;
mod template_ref;
mod ui;
mod commands;

use anyhow::Result;
use clap::{Parser, Subcommand, ValueEnum};
use commands::{
    group::GroupCommands, my_sa::MySaCommands, policy::PolicyCommands,
    resolve::ResolveArgs, sa::SaCommands, bank_policy::BankPolicyCommands,
    source::SourceCommands, template::TemplateCommands, user::UserCommands,
};

#[derive(Debug, Clone, Copy, ValueEnum)]
pub enum Format {
    Pretty,
    Json,
    Yaml,
}

#[derive(Parser)]
#[command(name = "hindclaw")]
#[command(about = "HindClaw CLI — access-control admin for Hindsight", long_about = None)]
#[command(version)]
struct Cli {
    /// Output format. When omitted: pretty on TTY, json when piped.
    #[arg(short = 'o', long, global = true)]
    output: Option<Format>,

    /// Show verbose output
    #[arg(short = 'v', long, global = true)]
    verbose: bool,

    /// Server alias (overrides default and env vars)
    #[arg(short = 'a', long = "alias", global = true)]
    alias: Option<String>,

    /// Skip confirmation prompts
    #[arg(short = 'y', long = "yes", global = true)]
    yes: bool,

    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// Manage server aliases
    #[command(subcommand)]
    Alias(commands::alias::AliasCommands),

    /// Manage your service accounts
    #[command(subcommand)]
    Sa(MySaCommands),

    /// Manage templates (list, search, install, apply, ...)
    #[command(subcommand)]
    Template(TemplateCommands),

    /// Admin operations (users, groups, policies, ...)
    #[command(subcommand)]
    Admin(AdminCommands),
}

#[derive(Subcommand)]
enum AdminCommands {
    /// Manage users
    #[command(subcommand)]
    User(UserCommands),

    /// Manage groups
    #[command(subcommand)]
    Group(GroupCommands),

    /// Manage policies
    #[command(subcommand)]
    Policy(PolicyCommands),

    /// Manage service accounts
    #[command(subcommand)]
    Sa(SaCommands),

    /// Manage bank policies
    #[command(subcommand)]
    BankPolicy(BankPolicyCommands),

    /// Debug access resolution
    Resolve(ResolveArgs),

    /// Manage marketplace sources
    #[command(subcommand)]
    Source(SourceCommands),
}

#[tokio::main]
async fn main() -> Result<()> {
    let cli = Cli::parse();
    let format = output::OutputFormat::from(cli.output);

    match cli.command {
        Commands::Alias(cmd) => commands::alias::run(cmd, format, cli.yes).await,
        Commands::Sa(cmd) => {
            let conn = config::resolve_connection(cli.alias.as_deref())?;
            commands::my_sa::run(cmd, conn, format, cli.yes).await
        }
        Commands::Template(cmd) => {
            let conn = config::resolve_connection(cli.alias.as_deref())?;
            commands::template::run(cmd, conn, format, cli.yes).await
        }
        Commands::Admin(admin_cmd) => {
            let conn = config::resolve_connection(cli.alias.as_deref())?;
            match admin_cmd {
                AdminCommands::User(cmd) => commands::user::run(cmd, conn, format, cli.yes).await,
                AdminCommands::Group(cmd) => commands::group::run(cmd, conn, format, cli.yes).await,
                AdminCommands::Policy(cmd) => commands::policy::run(cmd, conn, format, cli.yes).await,
                AdminCommands::Sa(cmd) => commands::sa::run(cmd, conn, format, cli.yes).await,
                AdminCommands::BankPolicy(cmd) => commands::bank_policy::run(cmd, conn, format, cli.yes).await,
                AdminCommands::Resolve(args) => commands::resolve::run(args, conn, format).await,
                AdminCommands::Source(cmd) => commands::source::run(cmd, conn, format, cli.yes).await,
            }
        }
    }
}
