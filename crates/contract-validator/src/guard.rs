//! CLI glue for the `contracts`, `boundaries` and `decisions` subcommands.

use crate::boundaries::{self, context_of};
use crate::contracts::{self, Base, Inputs};
use crate::decisions;
use crate::registry::{self, Registry, LOCK_PATH, REGISTRY_PATH};
use std::fs;
use std::path::Path;
use std::process::Command;

pub const SUBCOMMANDS: &[&str] = &["contracts", "boundaries", "decisions"];

#[derive(Default)]
struct Opts {
    staged: bool,
    maintenance: bool,
    write_lock: bool,
    emit_baseline: bool,
    count: bool,
    base_ref: Option<String>,
    base_registry: Option<String>,
    base_lock: Option<String>,
    expiry: Option<String>,
    today: Option<String>,
}

fn parse_opts(args: &[String]) -> Result<Opts, Vec<String>> {
    let mut o = Opts::default();
    let mut i = 0;
    while i < args.len() {
        let arg = args[i].clone();
        let mut value = |name: &str| -> Result<String, Vec<String>> {
            i += 1;
            args.get(i)
                .cloned()
                .ok_or_else(|| vec![format!("{name} requires a value")])
        };
        match arg.as_str() {
            "--staged" => o.staged = true,
            "--all" => o.staged = false,
            "--maintenance" => o.maintenance = true,
            "--write-lock" => o.write_lock = true,
            "--emit-baseline" => o.emit_baseline = true,
            "--count" => o.count = true,
            "--base-ref" => o.base_ref = Some(value("--base-ref")?),
            "--base-registry" => o.base_registry = Some(value("--base-registry")?),
            "--base-lock" => o.base_lock = Some(value("--base-lock")?),
            "--expiry" => o.expiry = Some(value("--expiry")?),
            "--today" => o.today = Some(value("--today")?),
            other => return Err(vec![format!("unknown option '{other}'")]),
        }
        i += 1;
    }
    Ok(o)
}

fn git(root: &Path, args: &[&str]) -> Result<Vec<u8>, String> {
    let out = Command::new("git")
        .arg("-C")
        .arg(root)
        .args(args)
        .output()
        .map_err(|e| format!("git {args:?}: {e}"))?;
    if out.status.success() {
        Ok(out.stdout)
    } else {
        Err(format!(
            "git {args:?} failed: {}",
            String::from_utf8_lossy(&out.stderr).trim()
        ))
    }
}

fn read_working(root: &Path, rel: &str) -> Option<Vec<u8>> {
    fs::read(root.join(rel)).ok()
}

fn read_index(root: &Path, rel: &str) -> Option<Vec<u8>> {
    git(root, &["show", &format!(":{rel}")]).ok()
}

fn load_registry(read: &dyn Fn(&str) -> Option<Vec<u8>>) -> Result<Registry, Vec<String>> {
    let bytes = read(REGISTRY_PATH).ok_or_else(|| vec![format!("{REGISTRY_PATH} is missing")])?;
    let text =
        String::from_utf8(bytes).map_err(|_| vec![format!("{REGISTRY_PATH} is not UTF-8")])?;
    registry::parse(&text).map_err(|e| vec![format!("{REGISTRY_PATH}: {e}")])
}

fn lines(bytes: Vec<u8>) -> Vec<String> {
    String::from_utf8_lossy(&bytes)
        .lines()
        .filter(|l| !l.is_empty())
        .map(str::to_string)
        .collect()
}

pub fn run(root: &Path, sub: &str, args: &[String]) -> Result<String, Vec<String>> {
    let o = parse_opts(args)?;
    let today = o.today.clone().unwrap_or_else(registry::today);
    let read = |rel: &str| {
        if o.staged {
            read_index(root, rel)
        } else {
            read_working(root, rel)
        }
    };
    let reg = load_registry(&read)?;
    match sub {
        "decisions" => {
            if !o.count {
                return Err(vec!["decisions requires --count".into()]);
            }
            if !reg.has_contract_sections() {
                return Err(vec![format!("{REGISTRY_PATH} has no decisions[] section")]);
            }
            Ok(decisions::render(&decisions::count(&reg)))
        }
        "contracts" => run_contracts(root, &o, &reg, &read, &today),
        _ => run_boundaries(root, &o, &reg, &today),
    }
}

fn run_contracts(
    root: &Path,
    o: &Opts,
    reg: &Registry,
    read: &dyn Fn(&str) -> Option<Vec<u8>>,
    today: &str,
) -> Result<String, Vec<String>> {
    if o.write_lock {
        let text = contracts::render_lock(reg, read).map_err(|e| vec![e])?;
        fs::write(root.join(LOCK_PATH), &text)
            .map_err(|e| vec![format!("cannot write {LOCK_PATH}: {e}")])?;
        return Ok(format!(
            "WROTE: {LOCK_PATH} ({} entries)",
            text.lines().count() - 1
        ));
    }
    let contract_files = git(root, &["ls-files", "--", "contracts"])
        .map(lines)
        .map_err(|e| vec![e])?
        .into_iter()
        .filter(|p| p.ends_with(".schema.json"))
        .collect::<Vec<_>>();
    let lock = read(LOCK_PATH).map(|b| String::from_utf8_lossy(&b).to_string());

    let mut base_registry: Option<Registry> = None;
    let mut base_lock: Option<String> = None;
    if let Some(path) = &o.base_registry {
        let text =
            fs::read_to_string(path).map_err(|e| vec![format!("--base-registry {path}: {e}")])?;
        base_registry =
            Some(registry::parse(&text).map_err(|e| vec![format!("base registry: {e}")])?);
        base_lock = o
            .base_lock
            .as_ref()
            .and_then(|p| fs::read_to_string(p).ok());
    } else if let Some(rev) = &o.base_ref {
        // A base without the registry (pre-S1) is a bootstrap, not a failure.
        if let Ok(bytes) = git(root, &["show", &format!("{rev}:{REGISTRY_PATH}")]) {
            let text = String::from_utf8_lossy(&bytes).to_string();
            base_registry = Some(
                registry::parse(&text).map_err(|e| vec![format!("base registry at {rev}: {e}")])?,
            );
            base_lock = git(root, &["show", &format!("{rev}:{LOCK_PATH}")])
                .ok()
                .map(|b| String::from_utf8_lossy(&b).to_string());
        }
    }
    let base_note = match &base_registry {
        Some(b) if b.has_contract_sections() => "base ratchet applied",
        Some(_) => "base predates the contract sections (bootstrap): base ratchet NOT applied",
        None => "no base supplied: base ratchet NOT applied",
    };
    let out = contracts::check(&Inputs {
        registry: reg,
        read,
        contract_files: &contract_files,
        lock: lock.as_deref(),
        base: base_registry.as_ref().map(|r| Base {
            registry: r,
            lock: base_lock.as_deref(),
        }),
        today,
        maintenance: o.maintenance,
    });
    for w in &out.warnings {
        eprintln!("WARN: {w}");
    }
    if out.failures.is_empty() {
        Ok(format!(
            "PASS: contracts ({} decisions, {} endpoints, {} tools, {} exceptions; {base_note})",
            reg.decisions.len(),
            reg.endpoints.len(),
            reg.tools.len(),
            reg.exceptions.len()
        ))
    } else {
        Err(out.failures)
    }
}

fn run_boundaries(
    root: &Path,
    o: &Opts,
    reg: &Registry,
    today: &str,
) -> Result<String, Vec<String>> {
    if !reg.has_contract_sections() || reg.scan_scope.include.is_empty() {
        return Err(vec![format!(
            "{REGISTRY_PATH} declares no scan_scope.include (nothing would be scanned)"
        )]);
    }
    let names: Vec<String> = if o.staged {
        git(
            root,
            &["diff", "--cached", "--name-only", "--diff-filter=ACMR"],
        )
        .map(lines)
        .map_err(|e| vec![e])?
    } else {
        git(root, &["ls-files"]).map(lines).map_err(|e| vec![e])?
    };
    let mut files = Vec::new();
    let mut failures = Vec::new();
    for name in names.into_iter().filter(|n| boundaries::in_scope(reg, n)) {
        let bytes = if o.staged {
            read_index(root, &name)
        } else {
            read_working(root, &name)
        };
        match bytes {
            Some(b) => files.push((name, b)),
            None if !o.staged && !root.join(&name).exists() => {}
            None => failures.push(format!(
                "boundaries: {name}: unreadable; declared scope not scanned"
            )),
        }
    }
    let report = boundaries::evaluate(reg, &files, today, o.maintenance, !o.staged);
    if o.emit_baseline {
        let expiry = o.expiry.clone().unwrap_or_else(|| "2027-03-31".to_string());
        let mut out = String::new();
        for ((path, kind), (count, owner_sha)) in &report.open {
            let sha = owner_sha.rsplit(':').next().unwrap_or("");
            let owner = context_of(reg, path)
                .map(|c| c.id.as_str())
                .unwrap_or("UNASSIGNED");
            out.push_str(&format!(
                "  - {{path: \"{path}\", kind: {kind}, count: {count}, owner: {owner}, reason: \"S1 baseline of a pre-existing call; shrinks by slice\", expiry: \"{expiry}\", source_sha256: \"{sha}\"}}\n"
            ));
        }
        return Ok(out.trim_end().to_string());
    }
    for w in &report.warnings {
        eprintln!("WARN: {w}");
    }
    failures.extend(report.failures);
    if failures.is_empty() {
        Ok(format!(
            "PASS: boundaries ({} files scanned, {} calls within the dated baseline, 0 new violations)",
            report.scanned, report.baselined
        ))
    } else {
        Err(failures)
    }
}
