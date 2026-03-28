use anyhow::Result;
use serde::Serialize;
use std::io::IsTerminal;

#[derive(Debug, Clone, Copy, PartialEq)]
pub enum OutputFormat {
    Pretty,
    Json,
    Yaml,
}

impl From<Option<crate::Format>> for OutputFormat {
    fn from(f: Option<crate::Format>) -> Self {
        match f {
            Some(crate::Format::Pretty) => OutputFormat::Pretty,
            Some(crate::Format::Json) => OutputFormat::Json,
            Some(crate::Format::Yaml) => OutputFormat::Yaml,
            None => {
                if std::io::stdout().is_terminal() {
                    OutputFormat::Pretty
                } else {
                    OutputFormat::Json
                }
            }
        }
    }
}

pub fn to_json<T: Serialize>(data: &T) -> Result<String> {
    Ok(serde_json::to_string_pretty(data)?)
}

pub fn to_yaml<T: Serialize>(data: &T) -> Result<String> {
    Ok(serde_yml::to_string(data)?)
}

pub fn print_output<T: Serialize>(data: &T, format: OutputFormat) -> Result<()> {
    match format {
        OutputFormat::Json => println!("{}", to_json(data)?),
        OutputFormat::Yaml => println!("{}", to_yaml(data)?),
        OutputFormat::Pretty => unreachable!("Pretty format handled by ui.rs"),
    }
    Ok(())
}
