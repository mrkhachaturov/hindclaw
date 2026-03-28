use anyhow::{bail, Result};

/// Parsed template reference from CLI argument.
///
/// Formats:
///   `scope/name`                — custom template (no source)
///   `scope/source/name`         — marketplace template
#[derive(Debug, Clone)]
pub struct TemplateRef {
    pub scope: String,
    pub source: Option<String>,
    pub name: String,
}

impl TemplateRef {
    /// Parse a template reference string.
    ///
    /// Two-part: `server/my-template` → scope=server, source=None, name=my-template
    /// Three-part: `server/hindclaw/backend-python` → scope=server, source=hindclaw, name=backend-python
    pub fn parse(s: &str) -> Result<Self> {
        let parts: Vec<&str> = s.split('/').collect();
        match parts.len() {
            2 => {
                validate_scope(parts[0])?;
                if parts[1].is_empty() {
                    bail!("Invalid template reference '{}': name cannot be empty.", s);
                }
                Ok(TemplateRef {
                    scope: parts[0].to_string(),
                    source: None,
                    name: parts[1].to_string(),
                })
            }
            3 => {
                validate_scope(parts[0])?;
                if parts[1].is_empty() {
                    bail!("Invalid template reference '{}': source cannot be empty.", s);
                }
                if parts[2].is_empty() {
                    bail!("Invalid template reference '{}': name cannot be empty.", s);
                }
                Ok(TemplateRef {
                    scope: parts[0].to_string(),
                    source: Some(parts[1].to_string()),
                    name: parts[2].to_string(),
                })
            }
            _ => bail!(
                "Invalid template reference '{}'. Expected 'scope/name' or 'scope/source/name'.",
                s
            ),
        }
    }
}

fn validate_scope(scope: &str) -> Result<()> {
    match scope {
        "server" | "personal" => Ok(()),
        _ => bail!("Invalid scope '{}'. Must be 'server' or 'personal'.", scope),
    }
}

impl std::fmt::Display for TemplateRef {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match &self.source {
            Some(src) => write!(f, "{}/{}/{}", self.scope, src, self.name),
            None => write!(f, "{}/{}", self.scope, self.name),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_two_part() {
        let r = TemplateRef::parse("server/my-template").unwrap();
        assert_eq!(r.scope, "server");
        assert!(r.source.is_none());
        assert_eq!(r.name, "my-template");
    }

    #[test]
    fn test_parse_three_part() {
        let r = TemplateRef::parse("personal/hindclaw/backend-python").unwrap();
        assert_eq!(r.scope, "personal");
        assert_eq!(r.source.as_deref(), Some("hindclaw"));
        assert_eq!(r.name, "backend-python");
    }

    #[test]
    fn test_invalid_scope() {
        assert!(TemplateRef::parse("global/my-template").is_err());
    }

    #[test]
    fn test_single_part_fails() {
        assert!(TemplateRef::parse("my-template").is_err());
    }

    #[test]
    fn test_display_two_part() {
        let r = TemplateRef { scope: "server".into(), source: None, name: "test".into() };
        assert_eq!(r.to_string(), "server/test");
    }

    #[test]
    fn test_display_three_part() {
        let r = TemplateRef { scope: "server".into(), source: Some("hindclaw".into()), name: "test".into() };
        assert_eq!(r.to_string(), "server/hindclaw/test");
    }

    #[test]
    fn test_too_many_segments() {
        assert!(TemplateRef::parse("server/source/name/extra").is_err());
    }

    #[test]
    fn test_empty_source() {
        assert!(TemplateRef::parse("server//name").is_err());
    }

    #[test]
    fn test_empty_name() {
        assert!(TemplateRef::parse("server/").is_err());
        assert!(TemplateRef::parse("server/source/").is_err());
    }
}
