use anyhow::Result;
use std::io::IsTerminal;

/// Map progenitor API errors to user-friendly messages.
pub fn map_api_error<E: std::fmt::Debug>(err: progenitor_client::Error<E>, context: &str) -> anyhow::Error {
    if let Some(status) = err.status() {
        match status.as_u16() {
            404 => anyhow::anyhow!("Not found ({})", context),
            409 => anyhow::anyhow!("Conflict — resource already exists ({})", context),
            401 => anyhow::anyhow!("Unauthorized — check your API key"),
            403 => anyhow::anyhow!("Forbidden — insufficient permissions"),
            _ => anyhow::anyhow!("API error {} ({}): {}", status, context, err),
        }
    } else {
        anyhow::anyhow!("Request failed ({}): {}", context, err)
    }
}

/// Require interactive confirmation for destructive operations.
/// Returns Ok(true) if confirmed, Ok(false) if cancelled.
/// Bails if stdin is not a terminal and -y was not passed.
pub fn require_confirmation(prompt: &str, yes: bool) -> Result<bool> {
    if yes {
        return Ok(true);
    }
    if !std::io::stdin().is_terminal() {
        anyhow::bail!("stdin is not a terminal. Use -y to confirm destructive operations non-interactively.");
    }
    let confirmed = dialoguer::Confirm::new()
        .with_prompt(format!("  {}?", prompt))
        .default(false)
        .interact()?;
    Ok(confirmed)
}
