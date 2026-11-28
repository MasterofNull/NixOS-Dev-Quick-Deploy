#!/usr/bin/env python3
"""CLI-level negative tests for the contract guard (S1 review fixes). Each case fails on the pre-fix binary.

Builds throwaway git repos with a small registry and drives `harness-contracts` and
`tier0.d/check-contracts.sh` exactly as tier0 and CI do.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
YAML = """contexts:
  - {id: K1, paths: [scripts/a/], modules: [task_registry], contract_package: contracts/k1}
  - {id: K3, paths: [scripts/b/], allowed_imports: []}
decisions:
  - {id: D01, decision: route, context: K1, owner: c, contract: contracts/k1/route/v1.schema.json, tag: OK}
scan_scope:
  include: [scripts/]
  exclude: []
"""
SCHEMA = '{"$id": "https://x/k1/route/v1.schema.json", "properties": {"schema_version": {"const": 1}}}\n'


def binary() -> str:
    env = os.environ.get("HARNESS_CONTRACTS_BIN")
    if env:
        return env
    out = ROOT / "target/release/harness-contracts"
    subprocess.run(["cargo", "build", "--release", "-p", "harness-contracts"], cwd=ROOT, check=True, capture_output=True)
    return str(out)


FAILED: list[str] = []
BIN = binary()
GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]


def sh(repo: Path, *a: str, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(list(a), cwd=repo, capture_output=True, text=True, env={**os.environ, **(env or {})})


def make_repo(yaml: str = YAML, schema: str = SCHEMA, lock: bool = True) -> Path:
    repo = Path(tempfile.mkdtemp())
    sh(repo, "git", "init", "-q", "-b", "main")
    (repo / "config").mkdir()
    (repo / "config/system-state-authorities.yaml").write_text(yaml)
    (repo / "contracts/k1/route").mkdir(parents=True)
    (repo / "contracts/k1/route/v1.schema.json").write_text(schema)
    (repo / "scripts/a").mkdir(parents=True)
    (repo / "scripts/b").mkdir(parents=True)
    (repo / "scripts/a/task_registry.py").write_text("X = 1\n")
    (repo / "scripts/b/x.py").write_text("import os\n")
    if lock:
        sh(repo, BIN, "--root", ".", "contracts", "--write-lock")
    sh(repo, "git", "add", "-A")
    sh(repo, *GIT, "commit", "-qm", "base")
    return repo


def run(repo: Path, *args: str) -> tuple[int, str]:
    p = sh(repo, BIN, "--root", str(repo), *args)
    return p.returncode, p.stdout + p.stderr


def expect(name: str, ok: bool, detail: str) -> None:
    if not ok:
        print(f"FAIL {name}: {detail.strip()[:160]}", file=sys.stderr)
        if os.environ.get("GUARD_CLI_KEEP_GOING"):  # used to show every case fails on a pre-fix binary
            FAILED.append(name)
            return
        sys.exit(1)
    print(f"PASS {name}")


def main() -> int:
    repo = make_repo()
    rc, out = run(repo, "contracts", "--base-ref", "HEAD")
    expect("clean repo passes", rc == 0, out)

    # HIGH main.rs: an option VALUE equal to a guard subcommand name must not hijack dispatch.
    rc, out = run(repo, "scope-gate", "--owned", "contracts", "--base", "HEAD")
    expect("scope-gate --owned contracts dispatches to scope-gate", rc == 0 and "strictly within owned scope" in out, out)
    rc, out = sh(repo, BIN, "--root", "contracts", "scope-gate").returncode, ""
    expect("--root contracts is a path, not the subcommand", rc != 0, "expected a failure to read the root, not a guard run")

    # HIGH guard.rs: an unresolvable --base-ref fails closed; a valid base without the registry bootstraps.
    rc, out = run(repo, "contracts", "--base-ref", "deadbeefdeadbeefdeadbeef")
    expect("unresolvable --base-ref fails closed", rc != 0 and "does not resolve" in out, out)
    boot = Path(tempfile.mkdtemp())
    sh(boot, "git", "init", "-q", "-b", "main")
    (boot / "README").write_text("x\n")
    sh(boot, "git", "add", "-A")
    sh(boot, *GIT, "commit", "-qm", "pre-registry")
    for rel in ("config", "contracts", "scripts"):
        shutil.copytree(repo / rel, boot / rel)
    sh(boot, "git", "add", "-A")
    sh(boot, *GIT, "commit", "-qm", "add registry")
    rc, out = run(boot, "contracts", "--base-ref", "HEAD~1")
    expect("valid base without the registry is a bootstrap", rc == 0 and "base ratchet NOT applied" in out, out)

    # MEDIUM guard.rs: registry paths may not escape the repo root.
    abs_repo = make_repo(YAML.replace("contracts/k1/route/v1.schema.json", "/etc/hosts"), lock=False)
    rc, out = run(abs_repo, "contracts")
    expect("absolute registry path rejected", rc != 0 and "absolute or contains" in out, out)
    up_repo = make_repo(YAML.replace("contracts/k1/route/v1.schema.json", "contracts/../contracts/k1/route/v1.schema.json"), lock=False)
    rc, out = run(up_repo, "contracts")
    expect("parent-dir registry path rejected", rc != 0 and "absolute or contains" in out, out)

    # MEDIUM boundaries.rs: a relative import across contexts is a boundary call.
    rel = make_repo()
    (rel / "scripts/b/x.py").write_text("from . import task_registry\n")
    sh(rel, "git", "add", "-A")
    rc, out = run(rel, "boundaries", "--staged")
    expect("cross-context relative import flagged", rc != 0 and "crosses K3 -> K1" in out, out)

    # MEDIUM contracts.rs: a versioned schema must declare properties.schema_version.const.
    nover = make_repo(schema='{"$id": "https://x/k1/route/v1.schema.json", "required": ["schema_version"]}\n')
    rc, out = run(nover, "contracts")
    expect("versioned schema without schema_version const fails", rc != 0 and "declares no properties.schema_version.const" in out, out)

    # HIGH contracts.rs: a candidate cannot widen allowed_imports against the base.
    wide = make_repo()
    (wide / "config/system-state-authorities.yaml").write_text(YAML.replace("allowed_imports: []", "allowed_imports: [task_registry]"))
    rc, out = run(wide, "contracts", "--base-ref", "HEAD")
    expect("widened allowed_imports fails the base ratchet", rc != 0 and "widened allowed_imports" in out, out)

    # HIGH contracts.rs: exceptions may not appear against a base that has no boundary_exceptions section.
    exc = make_repo()
    row = "  - {path: scripts/b/x.py, kind: dynamic, count: 1, owner: K3, reason: r, expiry: 2099-01-01, source_sha256: " + "0" * 64 + "}\n"
    (exc / "config/system-state-authorities.yaml").write_text(YAML + "boundary_exceptions:\n" + row)
    rc, out = run(exc, "contracts", "--base-ref", "HEAD")
    expect("exceptions against a base without any are rejected", rc != 0 and "exceptions appeared against a base" in out, out)

    # LOW check-contracts.sh: a broken registry is reported as a registry error, not as a missing binary.
    gate = make_repo()
    (gate / "scripts/governance/tier0.d").mkdir(parents=True)
    shutil.copy(ROOT / "scripts/governance/tier0.d/check-contracts.sh", gate / "scripts/governance/tier0.d/")
    (gate / "config/system-state-authorities.yaml").write_text("decisions: [this is: not valid\n")
    sh(gate, "git", "add", "-A")
    p = sh(gate, "bash", "scripts/governance/tier0.d/check-contracts.sh", "--pre-commit",
           env={"HARNESS_CONTRACTS_BIN": BIN})
    text = p.stdout + p.stderr
    expect("broken registry is reported as a registry error", p.returncode != 0 and "is unavailable" not in text and "system-state-authorities.yaml" in text, text)
    if FAILED:
        print(f"test-contracts-guard-cli: {len(FAILED)} case(s) failed")
        return 1
    print("test-contracts-guard-cli: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
