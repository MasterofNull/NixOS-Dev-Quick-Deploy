use std::path::Path;
use std::process::Command;

#[derive(Debug, PartialEq, Eq)]
pub struct ScopeViolation {
    pub file: String,
    pub reason: String,
}

#[allow(dead_code)]
pub struct ScopeGateResult {
    pub violations: Vec<ScopeViolation>,
    pub changed_files: Vec<String>,
    pub uncommitted_files: Vec<String>,
}

pub fn check_slice_scope(
    root: &Path,
    owned_paths: &[String],
    base_ref: Option<&str>,
    check_uncommitted: bool,
) -> Result<ScopeGateResult, String> {
    let base = base_ref.unwrap_or("HEAD~1");

    // 1. Get changed files against base ref
    let diff_output = Command::new("git")
        .current_dir(root)
        .args(["diff", "--name-only", base])
        .output()
        .map_err(|e| format!("failed to run git diff: {e}"))?;

    if !diff_output.status.success() {
        return Err(format!(
            "git diff failed: {}",
            String::from_utf8_lossy(&diff_output.stderr)
        ));
    }

    let diff_text = String::from_utf8_lossy(&diff_output.stdout);
    let changed_files: Vec<String> = diff_text
        .lines()
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
        .collect();

    // 2. Check uncommitted changes (status --porcelain)
    let status_output = Command::new("git")
        .current_dir(root)
        .args(["status", "--porcelain"])
        .output()
        .map_err(|e| format!("failed to run git status: {e}"))?;

    if !status_output.status.success() {
        return Err(format!(
            "git status failed: {}",
            String::from_utf8_lossy(&status_output.stderr)
        ));
    }

    let status_text = String::from_utf8_lossy(&status_output.stdout);
    let uncommitted_files: Vec<String> = status_text
        .lines()
        .map(|s| {
            if s.len() > 3 {
                s[3..].trim().to_string()
            } else {
                s.trim().to_string()
            }
        })
        .filter(|s| !s.is_empty())
        .collect();

    let mut violations = Vec::new();

    if check_uncommitted && !uncommitted_files.is_empty() {
        for uncommitted in &uncommitted_files {
            violations.push(ScopeViolation {
                file: uncommitted.clone(),
                reason: "uncommitted changes detected in working tree; slice must be committed"
                    .to_string(),
            });
        }
    }

    // 3. Match changed files against owned_paths patterns
    for file in &changed_files {
        let is_owned = owned_paths.iter().any(|pattern| path_matches(pattern, file));
        if !is_owned {
            violations.push(ScopeViolation {
                file: file.clone(),
                reason: format!("modified file is outside declared owned paths: {owned_paths:?}"),
            });
        }
    }

    Ok(ScopeGateResult {
        violations,
        changed_files,
        uncommitted_files,
    })
}

fn path_matches(pattern: &str, path: &str) -> bool {
    let norm_pattern = pattern.trim_start_matches("./");
    let norm_path = path.trim_start_matches("./");

    if norm_pattern == norm_path {
        return true;
    }

    if norm_pattern.ends_with("/**") {
        let prefix = &norm_pattern[..norm_pattern.len() - 3];
        return norm_path.starts_with(prefix);
    }

    if norm_pattern.ends_with("/*") {
        let prefix = &norm_pattern[..norm_pattern.len() - 1]; // keep trailing slash
        if norm_path.starts_with(prefix) {
            let remainder = &norm_path[prefix.len()..];
            return !remainder.is_empty() && !remainder.contains('/');
        }
        return false;
    }

    if norm_pattern.starts_with("*.") {
        return norm_path.ends_with(&norm_pattern[1..]);
    }

    // Direct directory prefix
    if norm_pattern.ends_with('/') && norm_path.starts_with(norm_pattern) {
        return true;
    }

    false
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_scope_gate_violations() {
        let root = Path::new(env!("CARGO_MANIFEST_DIR"))
            .ancestors()
            .nth(2)
            .unwrap();

        // 1. In-scope matching
        let res = check_slice_scope(
            root,
            &["crates/contract-validator/**".to_string()],
            Some("HEAD"),
            false,
        );
        assert!(res.is_ok());

        // 2. Out-of-scope violation
        let res_out = check_slice_scope(
            root,
            &["docs/**".to_string()],
            Some("HEAD"),
            false,
        );
        assert!(res_out.is_ok());
        let result = res_out.unwrap();
        if !result.changed_files.is_empty() {
            assert!(!result.violations.is_empty());
        }
    }
    #[test]
    fn test_path_matches_exact_and_patterns() {
        assert!(path_matches("crates/foo/src/main.rs", "crates/foo/src/main.rs"));
        assert!(path_matches("crates/foo/**", "crates/foo/src/main.rs"));
        assert!(path_matches("crates/foo/**", "crates/foo/deep/nested/file.rs"));
        assert!(path_matches("crates/foo/*", "crates/foo/Cargo.toml"));
        assert!(!path_matches("crates/foo/*", "crates/foo/src/main.rs"));
        assert!(path_matches("*.rs", "crates/contract-validator/src/main.rs"));
        assert!(!path_matches("crates/foo/**", "crates/bar/src/main.rs"));
    }
}
