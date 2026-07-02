use std::collections::HashSet;
use std::env;
use std::fs;
use std::path::{Path, PathBuf};
use std::process::{Command, ExitCode};

const CANONICAL_HOT_MEMORY_PATH: &str = "ai-stack/agent-memory/MEMORY.md";

const ACTIVE_MEMORY_REFERENCE_PATHS: &[&str] = &[
    "AGENTS.md",
    "README.md",
    ".agent/SKILL_INDEX.md",
    ".agent/WORKFLOW-CANON.md",
    ".agent/GEMINI.md",
    ".agent/skills/context-efficiency/SKILL.md",
    ".agent/skills/provider-request-error-recovery/SKILL.md",
    ".agent/skills/strict-json-output-contract/SKILL.md",
    ".agent/skills/system-dev/SKILL.md",
];

const REQUIRED_MEMORY_CATEGORIES: &[&str] = &[
    "local_live_state",
    "portable_coordination_templates",
    "durable_collective_memory",
    "curated_prd_plan_prompt",
    "rag_database_facts",
    "raw_learning_feedback",
    "reference_only_archives",
];

const REQUIRED_MEMORY_DOC_PHRASES: &[&str] = &[
    "Local live state",
    "Durable collective memory",
    "RAG And Database Facts",
    "Reference-Only Surfaces",
    "Promotion Rule",
    "Agents must not write directly to AIDB or Qdrant",
    ".agents/planning/**",
    ".agents/summary/**",
    "Raw telemetry is not a fact",
];

const REQUIRED_TRACKED_MEMORY_PATHS: &[&str] = &[
    "config/agent-memory-surface-registry.json",
    "docs/operations/agent-memory-state-standard.md",
    CANONICAL_HOT_MEMORY_PATH,
    ".agent/memory/issues-backlog.md",
    ".agent/collaboration/README.md",
    ".agent/collaboration/HANDOFF.template.md",
    ".agent/collaboration/PENDING.template.json",
    ".agent/collaboration/RESUME.template.json",
    "docs/operations/agent-artifact-distribution-policy.md",
];

#[derive(Clone, Copy)]
enum Check {
    All,
    WritableState,
    MemorySurface,
}

impl Check {
    fn parse(value: &str) -> Option<Self> {
        match value {
            "all" => Some(Self::All),
            "writable-state" => Some(Self::WritableState),
            "memory-surface" => Some(Self::MemorySurface),
            _ => None,
        }
    }
}

fn main() -> ExitCode {
    match run_cli(env::args().skip(1).collect()) {
        Ok(message) => {
            println!("{message}");
            ExitCode::SUCCESS
        }
        Err(failures) => {
            for failure in failures {
                eprintln!("FAIL: {failure}");
            }
            ExitCode::from(1)
        }
    }
}

fn run_cli(args: Vec<String>) -> Result<String, Vec<String>> {
    let mut check = Check::All;
    let mut root = env::current_dir().map_err(|err| vec![format!("cannot resolve cwd: {err}")])?;
    let mut index = 0;

    while index < args.len() {
        match args[index].as_str() {
            "--root" => {
                index += 1;
                let Some(value) = args.get(index) else {
                    return Err(vec!["--root requires a path".to_string()]);
                };
                root = PathBuf::from(value);
            }
            value => {
                let Some(parsed) = Check::parse(value) else {
                    return Err(vec![format!(
                        "unknown check '{value}' (expected all, writable-state, or memory-surface)"
                    )]);
                };
                check = parsed;
            }
        }
        index += 1;
    }

    let failures = run_check(check, &root);
    if failures.is_empty() {
        Ok(match check {
            Check::All => "PASS: harness contract validators passed".to_string(),
            Check::WritableState => {
                "PASS: writable-state policy and service defaults remain declarative-safe"
                    .to_string()
            }
            Check::MemorySurface => "PASS: agent memory surface registry is enforced".to_string(),
        })
    } else {
        Err(failures)
    }
}

fn run_check(check: Check, root: &Path) -> Vec<String> {
    let mut failures = Vec::new();
    match check {
        Check::All => {
            validate_writable_state(root, &mut failures);
            validate_memory_surface(root, &mut failures);
        }
        Check::WritableState => validate_writable_state(root, &mut failures),
        Check::MemorySurface => validate_memory_surface(root, &mut failures),
    }
    failures
}

fn validate_writable_state(root: &Path, failures: &mut Vec<String>) {
    let policy_text = read_required(
        root,
        "docs/development/NIXOS-WRITABLE-STATE-REQUIREMENTS.md",
        failures,
    );
    let options_text = read_required(root, "nix/modules/core/options.nix", failures);
    let runtime_profiles_text =
        read_required(root, "config/runtime-isolation-profiles.json", failures);
    let mcp_text = read_required(root, "nix/modules/services/mcp-servers.nix", failures);
    let http_text = read_required(
        root,
        "ai-stack/mcp-servers/hybrid-coordinator/http_server_impl.py",
        failures,
    );
    let disclosure_text = read_required(
        root,
        "ai-stack/mcp-servers/hybrid-coordinator/knowledge/progressive_disclosure.py",
        failures,
    );
    let learning_text = read_required(
        root,
        "ai-stack/mcp-servers/hybrid-coordinator/extensions/real_time_learning_engine.py",
        failures,
    );

    check_contains(
        &options_text,
        "mutableSpaces = {",
        "options should expose declarative mutable spaces",
        failures,
    );
    check_contains(
        &options_text,
        "programWritablePaths",
        "options should expose program writable paths",
        failures,
    );

    let nix_roots = collect_assignment_values(&options_text, "workspace_root = ");
    let json_roots = collect_json_string_values(&runtime_profiles_text, "workspace_root");
    for root_path in &json_roots {
        if !nix_roots.contains(root_path) {
            failures.push(format!(
                "runtime profile registry workspace root missing from Nix defaults: {root_path}"
            ));
        }
    }
    for required in [
        "/var/lib/nixos-ai-stack/mutable/program/agent-runs",
        "/var/lib/nixos-ai-stack/mutable/program/agent-worktrees",
    ] {
        if !nix_roots.contains(required) {
            failures.push(format!(
                "Nix runtime isolation defaults missing workspace root: {required}"
            ));
        }
        if !json_roots.contains(required) {
            failures.push(format!(
                "runtime isolation profile registry missing workspace root: {required}"
            ));
        }
    }

    check_contains(
        &policy_text,
        "Treat `repoPath` as read-only for system services.",
        "policy doc should declare repoPath read-only for hardened services",
        failures,
    );
    check_contains(
        &policy_text,
        "runtime mutable state",
        "policy doc should classify runtime mutable state",
        failures,
    );
    check_contains(
        &policy_text,
        "repo-grounded artifact",
        "policy doc should classify repo-grounded artifacts",
        failures,
    );
    check_contains(
        &policy_text,
        "`deployment.mutableSpaces.enable`",
        "policy doc should name the declarative mutable-spaces switch",
        failures,
    );
    check_contains(
        &mcp_text,
        "ReadOnlyPaths = [repoSource];",
        "MCP services should keep the repo path mounted read-only",
        failures,
    );
    check_contains(
        &mcp_text,
        "create_path 0770 ${lib.escapeShellArg path}",
        "mutable path bootstrap should create runtime roots group-writable",
        failures,
    );
    check_contains(
        &mcp_text,
        "map (root: \"d ${root} 0770 ${svcUser} ${aiGroup} -\") runtimeWorkspaceRoots",
        "tmpfiles d-rule should create runtime workspace roots group-writable",
        failures,
    );
    check_contains(
        &mcp_text,
        "map (root: \"z ${root} 0770 ${svcUser} ${aiGroup} -\") runtimeWorkspaceRoots",
        "tmpfiles z-rule should enforce runtime workspace root group writability",
        failures,
    );
    check_contains(
        &http_text,
        "os.getenv(\"DISCLOSURE_CONTEXT_DIR\", \"/var/lib/ai-stack/hybrid/context-tiers\")",
        "hybrid coordinator should keep disclosure runtime state in writable service storage",
        failures,
    );
    check_contains(
        &learning_text,
        "os.getenv(\"REMEDIATION_PLAYBOOKS_DIR\", \"/var/lib/ai-stack/hybrid/playbooks\")",
        "hybrid coordinator should keep remediation playbooks in writable service storage",
        failures,
    );
    check_contains(
        &disclosure_text,
        "os.getenv(\"AI_STACK_REPO_PATH\", str(Path(__file__).resolve().parents[4]))",
        "progressive disclosure config should resolve repo root through env or relative path",
        failures,
    );
    check_absent(
        &disclosure_text,
        "/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/config/progressive-disclosure-domains.json",
        "progressive disclosure config should not hardcode a developer checkout path",
        failures,
    );
}

fn validate_memory_surface(root: &Path, failures: &mut Vec<String>) {
    let registry_text = read_required(root, "config/agent-memory-surface-registry.json", failures);
    let standard_doc = read_required(
        root,
        "docs/operations/agent-memory-state-standard.md",
        failures,
    );
    let gitignore = read_required(root, ".gitignore", failures);
    let tracked = tracked_files(root, failures);

    for category in REQUIRED_MEMORY_CATEGORIES {
        check_contains(
            &registry_text,
            &format!("\"{category}\""),
            &format!("registry missing category: {category}"),
            failures,
        );
    }

    for path in REQUIRED_TRACKED_MEMORY_PATHS {
        if !tracked.contains(*path) && !root.join(path).exists() {
            failures.push(format!("required tracked/added file missing: {path}"));
        }
    }

    for phrase in REQUIRED_MEMORY_DOC_PHRASES {
        check_contains(
            &standard_doc,
            phrase,
            &format!("standard doc missing phrase: {phrase}"),
            failures,
        );
    }

    for pattern in [
        ".agents/scratchpad/",
        ".agents/telemetry/*.jsonl",
        ".agent/collaboration/RESUME.json",
    ] {
        check_contains(
            &gitignore,
            pattern,
            &format!(".gitignore missing memory/state local pattern: {pattern}"),
            failures,
        );
    }

    check_contains(
        &registry_text,
        "\"path\": \"ai-stack/agent-memory/MEMORY.md\"",
        "hot_memory_limits must point to canonical hot memory path",
        failures,
    );
    let hot_file = root.join(CANONICAL_HOT_MEMORY_PATH);
    match fs::read_to_string(&hot_file) {
        Ok(text) => {
            if text.lines().count() > 200 {
                failures.push(format!("{CANONICAL_HOT_MEMORY_PATH} exceeds 200 lines"));
            }
        }
        Err(err) => failures.push(format!(
            "hot memory file missing or unreadable: {CANONICAL_HOT_MEMORY_PATH}: {err}"
        )),
    }

    let forbidden_patterns =
        collect_json_string_arrays(&registry_text, "forbidden_tracked_patterns");
    if forbidden_patterns.is_empty() {
        failures.push("registry must define forbidden_tracked_patterns".to_string());
    }
    for pattern in forbidden_patterns {
        for path in &tracked {
            if glob_match(&pattern, path) {
                failures.push(format!(
                    "forbidden local/raw state path is tracked: {path} (pattern {pattern})"
                ));
            }
        }
    }

    for path in ACTIVE_MEMORY_REFERENCE_PATHS {
        let text = read_required(root, path, failures);
        if text.contains("MEMORY.md") && !text.contains(CANONICAL_HOT_MEMORY_PATH) {
            failures.push(format!(
                "{path} references MEMORY.md without canonical path {CANONICAL_HOT_MEMORY_PATH}"
            ));
        }
        if text.contains("`memory/MEMORY.md`") || text.contains(".agent/memory/MEMORY.md") {
            failures.push(format!("{path} references a stale hot-memory path"));
        }
    }
}

fn read_required(root: &Path, relative: &str, failures: &mut Vec<String>) -> String {
    match fs::read_to_string(root.join(relative)) {
        Ok(text) => text,
        Err(err) => {
            failures.push(format!("missing or unreadable {relative}: {err}"));
            String::new()
        }
    }
}

fn check_contains(haystack: &str, needle: &str, message: &str, failures: &mut Vec<String>) {
    if !haystack.contains(needle) {
        failures.push(message.to_string());
    }
}

fn check_absent(haystack: &str, needle: &str, message: &str, failures: &mut Vec<String>) {
    if haystack.contains(needle) {
        failures.push(message.to_string());
    }
}

fn tracked_files(root: &Path, failures: &mut Vec<String>) -> HashSet<String> {
    let output = Command::new("git")
        .arg("-C")
        .arg(root)
        .arg("ls-files")
        .output();
    match output {
        Ok(output) if output.status.success() => String::from_utf8_lossy(&output.stdout)
            .lines()
            .map(ToOwned::to_owned)
            .collect(),
        Ok(output) => {
            failures.push(format!(
                "git ls-files failed: {}",
                String::from_utf8_lossy(&output.stderr).trim()
            ));
            HashSet::new()
        }
        Err(err) => {
            failures.push(format!("failed to run git ls-files: {err}"));
            HashSet::new()
        }
    }
}

fn collect_assignment_values(text: &str, prefix: &str) -> HashSet<String> {
    text.lines()
        .filter_map(|line| {
            let start = line.find(prefix)? + prefix.len();
            let rest = line[start..].trim_start();
            quoted_value(rest)
        })
        .collect()
}

fn collect_json_string_values(text: &str, key: &str) -> HashSet<String> {
    let mut values = HashSet::new();
    let needle = format!("\"{key}\"");
    let mut offset = 0;
    while let Some(index) = text[offset..].find(&needle) {
        let after_key = offset + index + needle.len();
        if let Some(colon) = text[after_key..].find(':') {
            let value_start = after_key + colon + 1;
            if let Some(value) = quoted_value(text[value_start..].trim_start()) {
                values.insert(value);
            }
            offset = value_start;
        } else {
            break;
        }
    }
    values
}

fn collect_json_string_arrays(text: &str, key: &str) -> Vec<String> {
    let mut values = Vec::new();
    let needle = format!("\"{key}\"");
    let mut offset = 0;
    while let Some(index) = text[offset..].find(&needle) {
        let after_key = offset + index + needle.len();
        let Some(open_rel) = text[after_key..].find('[') else {
            break;
        };
        let open = after_key + open_rel;
        let Some(close_rel) = text[open..].find(']') else {
            break;
        };
        let close = open + close_rel;
        values.extend(collect_quoted_values(&text[open + 1..close]));
        offset = close + 1;
    }
    values
}

fn collect_quoted_values(text: &str) -> Vec<String> {
    let mut values = Vec::new();
    let mut remaining = text;
    while let Some(start) = remaining.find('"') {
        let after_start = &remaining[start + 1..];
        let Some(end) = after_start.find('"') else {
            break;
        };
        values.push(after_start[..end].to_string());
        remaining = &after_start[end + 1..];
    }
    values
}

fn quoted_value(text: &str) -> Option<String> {
    let text = text.trim_start();
    let rest = text.strip_prefix('"')?;
    let end = rest.find('"')?;
    Some(rest[..end].to_string())
}

fn glob_match(pattern: &str, value: &str) -> bool {
    glob_match_bytes(pattern.as_bytes(), value.as_bytes())
}

fn glob_match_bytes(pattern: &[u8], value: &[u8]) -> bool {
    if pattern.is_empty() {
        return value.is_empty();
    }
    match pattern[0] {
        b'*' => {
            glob_match_bytes(&pattern[1..], value)
                || (!value.is_empty() && glob_match_bytes(pattern, &value[1..]))
        }
        b'?' => !value.is_empty() && glob_match_bytes(&pattern[1..], &value[1..]),
        byte => {
            !value.is_empty() && byte == value[0] && glob_match_bytes(&pattern[1..], &value[1..])
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn repo_root() -> PathBuf {
        Path::new(env!("CARGO_MANIFEST_DIR"))
            .ancestors()
            .nth(2)
            .expect("crate should live under crates/contract-validator")
            .to_path_buf()
    }

    #[test]
    fn fixture_paths_exist() {
        let root = repo_root();
        for path in [
            "docs/development/NIXOS-WRITABLE-STATE-REQUIREMENTS.md",
            "nix/modules/core/options.nix",
            "config/runtime-isolation-profiles.json",
            "nix/modules/services/mcp-servers.nix",
            "ai-stack/mcp-servers/hybrid-coordinator/http_server_impl.py",
            "ai-stack/mcp-servers/hybrid-coordinator/knowledge/progressive_disclosure.py",
            "ai-stack/mcp-servers/hybrid-coordinator/extensions/real_time_learning_engine.py",
            "config/agent-memory-surface-registry.json",
            "docs/operations/agent-memory-state-standard.md",
            CANONICAL_HOT_MEMORY_PATH,
        ] {
            assert!(root.join(path).exists(), "missing fixture path: {path}");
        }
    }

    #[test]
    fn validators_pass_on_current_repo() {
        let root = repo_root();
        let failures = run_check(Check::All, &root);
        assert!(
            failures.is_empty(),
            "contract validator failures:\n{}",
            failures.join("\n")
        );
    }

    #[test]
    fn glob_matching_handles_repo_patterns() {
        assert!(glob_match(
            ".agents/telemetry/*.jsonl",
            ".agents/telemetry/a.jsonl"
        ));
        assert!(glob_match(
            ".agents/delegation/**",
            ".agents/delegation/outputs/a.log"
        ));
        assert!(!glob_match(
            ".agents/telemetry/*.jsonl",
            ".agents/attention/a.jsonl"
        ));
    }
}
