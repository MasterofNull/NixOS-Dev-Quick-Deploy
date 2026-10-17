#!/usr/bin/env python3
"""K3 regression proof: aq-factory init & doctor via existing installer (simplified, no maintainer-signed tags)."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AQ_FACTORY = ROOT / "scripts/ai/aq-factory"
KIT = ROOT / "templates/factory-kit"


def sh(*cmd: str, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=check)


def new_repo(base: Path, name: str, with_identity: bool = True) -> Path:
    repo = base / name
    repo.mkdir(parents=True, exist_ok=True)
    sh("git", "init", "-q", "-b", "main", cwd=repo)
    if with_identity:
        sh("git", "config", "user.name", "Test User", cwd=repo)
        sh("git", "config", "user.email", "test@example.test", cwd=repo)
    return repo


def test_skill_subcommand_preserved(base: Path) -> None:
    target = base / "skills"
    res = subprocess.run([sys.executable, str(AQ_FACTORY), "skill", "sample-skill", "Sample purpose", "--root", str(target)],
                         capture_output=True, text=True)
    assert res.returncode == 0, f"skill subcommand failed: {res.stderr}"
    assert (target / "sample-skill/SKILL.md").is_file()


def test_init_identity_enforcement(base: Path) -> None:
    repo = new_repo(base, "no-identity", with_identity=False)
    res = subprocess.run([sys.executable, str(AQ_FACTORY), "init", "--repo", str(repo), "--owner-handle", "@alice"], env={k: v for k, v in os.environ.items() if not k.startswith("GIT_")} | {"GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null"},
                         capture_output=True, text=True)
    assert res.returncode == 4, f"expected rc=4 for missing git identity, got {res.returncode}"
    assert "user.name and user.email must be configured" in res.stderr


def test_init_and_doctor_lifecycle(base: Path) -> None:
    repo = new_repo(base, "lifecycle")

    # 1. Preview (dry-run)
    res_dry = subprocess.run([sys.executable, str(AQ_FACTORY), "init", "--repo", str(repo), "--owner-handle", "@testuser", "--dry-run"],
                             capture_output=True, text=True)
    assert res_dry.returncode == 0, f"dry-run failed: {res_dry.stderr}"
    assert not (repo / ".factory/kit.lock").exists()

    # 2. Init
    res_init = subprocess.run([sys.executable, str(AQ_FACTORY), "init", "--repo", str(repo), "--owner-handle", "@testuser"],
                              capture_output=True, text=True)
    assert res_init.returncode == 0, f"init failed: {res_init.stderr}\n{res_init.stdout}"
    assert (repo / ".factory/kit.lock").is_file()
    assert (repo / "kit.toml").is_file()
    assert (repo / ".githooks/pre-commit").is_file()
    assert (repo / ".githooks/commit-msg").is_file()
    assert os.access(repo / ".githooks/pre-commit", os.X_OK)
    assert os.access(repo / ".githooks/commit-msg", os.X_OK)

    # Verify CODEOWNERS has handle
    codeowners = (repo / ".github/CODEOWNERS").read_text(encoding="utf-8")
    assert "@testuser" in codeowners

    # 3. Doctor read-only pass
    res_doc = subprocess.run([sys.executable, str(AQ_FACTORY), "doctor", "--repo", str(repo)],
                             capture_output=True, text=True)
    assert res_doc.returncode == 0, f"doctor failed:\n{res_doc.stdout}\n{res_doc.stderr}"

    # 4. Idempotent init
    res_idem = subprocess.run([sys.executable, str(AQ_FACTORY), "init", "--repo", str(repo), "--owner-handle", "@testuser"],
                              capture_output=True, text=True)
    assert res_idem.returncode == 0, f"idempotent init failed: {res_idem.stderr}"


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="factory-k3-") as tmp:
        base = Path(tmp)
        test_skill_subcommand_preserved(base)
        test_init_identity_enforcement(base)
        test_init_and_doctor_lifecycle(base)
    print("PASS: factory kit K3 (aq-factory init + doctor lifecycle, identity enforcement, skill preservation)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
