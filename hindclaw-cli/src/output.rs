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
            None => OutputFormat::Pretty, // placeholder, will be replaced in Task 2
        }
    }
}
