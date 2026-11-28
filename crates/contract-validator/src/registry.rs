//! Typed view of the contract sections of `config/system-state-authorities.yaml`.

use crate::yaml::{parse_sections, Value};

pub const REGISTRY_PATH: &str = "config/system-state-authorities.yaml";
pub const LOCK_PATH: &str = "contracts/.lock";

const SECTIONS: &[&str] = &[
    "contexts",
    "decisions",
    "endpoints",
    "tools",
    "scan_scope",
    "boundary_exceptions",
];

#[derive(Debug, Clone, Default)]
pub struct Context {
    pub id: String,
    pub paths: Vec<String>,
    pub modules: Vec<String>,
    pub allowed_imports: Vec<String>,
    pub contract_package: String,
}

#[derive(Debug, Clone, Default)]
pub struct Decision {
    pub id: String,
    pub decision: String,
    pub context: String,
    pub owner: String,
    pub current_owner: String,
    pub contract: String,
    pub compat: String,
    pub tag: String,
    pub events: Vec<String>,
    pub writers: Vec<String>,
    pub writers_verified: bool,
}

#[derive(Debug, Clone, Default)]
pub struct Endpoint {
    pub id: String,
    pub owner: String,
    pub contract: String,
    pub env_vars: Vec<String>,
    pub literals: Vec<String>,
    pub callers: Vec<String>,
}

#[derive(Debug, Clone, Default)]
pub struct Tool {
    pub id: String,
    pub path: String,
    pub owner: String,
    pub decision: String,
    pub callers: Vec<String>,
}

#[derive(Debug, Clone, Default)]
pub struct ScanScope {
    pub include: Vec<String>,
    pub exclude: Vec<String>,
}

#[derive(Debug, Clone, Default)]
pub struct Exception {
    pub path: String,
    pub kind: String,
    pub count: usize,
    pub owner: String,
    pub reason: String,
    pub expiry: String,
    pub source_sha256: String,
}

#[derive(Debug, Clone, Default)]
pub struct Registry {
    pub contexts: Vec<Context>,
    pub decisions: Vec<Decision>,
    pub endpoints: Vec<Endpoint>,
    pub tools: Vec<Tool>,
    pub scan_scope: ScanScope,
    pub exceptions: Vec<Exception>,
    /// Sections present in the document (used to tell a pre-S1 base from a stripped one).
    pub present: Vec<String>,
}

impl Registry {
    pub fn has_contract_sections(&self) -> bool {
        self.present.iter().any(|s| s == "decisions")
    }
}

pub fn parse(text: &str) -> Result<Registry, String> {
    let sections = parse_sections(text, SECTIONS)?;
    let mut reg = Registry::default();
    for section in sections {
        reg.present.push(section.key.clone());
        let rows: Vec<Value> = match &section.value {
            Value::Seq(items) => items.clone(),
            Value::Map(_) if section.key == "scan_scope" => vec![section.value.clone()],
            _ => {
                return Err(format!(
                    "line {}: section '{}' must be a list",
                    section.line, section.key
                ))
            }
        };
        for row in rows {
            match section.key.as_str() {
                "contexts" => reg.contexts.push(Context {
                    id: row.str_of("id"),
                    paths: row.strs_of("paths"),
                    modules: row.strs_of("modules"),
                    allowed_imports: row.strs_of("allowed_imports"),
                    contract_package: row.str_of("contract_package"),
                }),
                "decisions" => reg.decisions.push(Decision {
                    id: row.str_of("id"),
                    decision: row.str_of("decision"),
                    context: row.str_of("context"),
                    owner: row.str_of("owner"),
                    current_owner: row.str_of("current_owner"),
                    contract: row.str_of("contract"),
                    compat: row.str_of("compat"),
                    tag: row.str_of("tag"),
                    events: row.strs_of("events"),
                    writers: row.strs_of("writers"),
                    writers_verified: row.str_of("writers_verified") == "true",
                }),
                "endpoints" => reg.endpoints.push(Endpoint {
                    id: row.str_of("id"),
                    owner: row.str_of("owner"),
                    contract: row.str_of("contract"),
                    env_vars: row.strs_of("env_vars"),
                    literals: row.strs_of("literals"),
                    callers: row.strs_of("callers"),
                }),
                "tools" => reg.tools.push(Tool {
                    id: row.str_of("id"),
                    path: row.str_of("path"),
                    owner: row.str_of("owner"),
                    decision: row.str_of("decision"),
                    callers: row.strs_of("callers"),
                }),
                "scan_scope" => {
                    reg.scan_scope = ScanScope {
                        include: row.strs_of("include"),
                        exclude: row.strs_of("exclude"),
                    }
                }
                _ => {
                    let count_text = row.str_of("count");
                    let count = count_text.parse::<usize>().map_err(|_| {
                        format!(
                            "exception '{}' has non-numeric count '{count_text}'",
                            row.str_of("path")
                        )
                    })?;
                    reg.exceptions.push(Exception {
                        path: row.str_of("path"),
                        kind: row.str_of("kind"),
                        count,
                        owner: row.str_of("owner"),
                        reason: row.str_of("reason"),
                        expiry: row.str_of("expiry"),
                        source_sha256: row.str_of("source_sha256"),
                    })
                }
            }
        }
    }
    Ok(reg)
}

/// A registry path that could leave the repo root: absolute, or containing a `..` component.
pub fn unsafe_path(p: &str) -> bool {
    p.starts_with('/') || p.split('/').any(|c| c == "..")
}

/// Prefix match used for context paths, scan scope and exclusions.
pub fn path_matches(path: &str, pattern: &str) -> bool {
    path == pattern || path.starts_with(pattern)
}

pub fn today() -> String {
    let secs = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    let days = (secs / 86_400) as i64;
    let z = days + 719_468;
    let era = z.div_euclid(146_097);
    let doe = z.rem_euclid(146_097);
    let yoe = (doe - doe / 1_460 + doe / 36_524 - doe / 146_096) / 365;
    let year = yoe + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let day = doy - (153 * mp + 2) / 5 + 1;
    let month = if mp < 10 { mp + 3 } else { mp - 9 };
    let year = if month <= 2 { year + 1 } else { year };
    format!("{year:04}-{month:02}-{day:02}")
}
