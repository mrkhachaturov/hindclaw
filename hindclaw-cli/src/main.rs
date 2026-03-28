mod api;
mod config;
mod output;
mod ui;
mod commands;

use anyhow::Result;
use clap::{Parser, Subcommand, ValueEnum};

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
}

#[tokio::main]
async fn main() -> Result<()> {
    let cli = Cli::parse();
    let format = output::OutputFormat::from(cli.output);

    match cli.command {
        Commands::Alias(cmd) => commands::alias::run(cmd, format, cli.yes).await,
    }
}
