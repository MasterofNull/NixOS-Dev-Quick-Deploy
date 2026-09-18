#!/usr/bin/env python3
"""Focused FT-4 proof for confirm-gated, non-destructive retrofit."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AQD = ROOT / "scripts/ai/aqd"
BUNDLE = ROOT / "templates/factory-gate-bundle"


def run(*command: str, cwd: Path, expected: int = 0, input_text: str | None = None,
        path_prefix: Path | None = None, path_override: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = {key: value for key, value in os.environ.items()
           if key not in {"GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES"}}
    if path_prefix:
        env["PATH"] = str(path_prefix) + os.pathsep + env.get("PATH", "")
    if path_override:
        env["PATH"] = str(path_override)
    result = subprocess.run(command, cwd=cwd, env=env, input=input_text, text=True, capture_output=True, check=False)
    if (result.returncode == 0) != (expected == 0):
        raise AssertionError(f"unexpected exit {result.returncode}: {' '.join(command)}\n{result.stdout}\n{result.stderr}")
    return result


def preview(target: Path, name: str = "existing fixture", path_override: Path | None = None) -> dict[str, object]:
    result = run(str(AQD), "workflows", "retrofit", "--target", str(target), "--name", name, "--stack", "generic", cwd=ROOT,
                 path_override=path_override)
    return json.loads(result.stdout)


def tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if ".git" in path.parts or not path.is_file():
            continue
        digest.update(str(path.relative_to(root)).encode() + b"\0" + path.read_bytes())
    return digest.hexdigest()


def main() -> int:
    evidence = {"preview_read_only": False, "confirmation_enforced": False,
                "originals_preserved": False, "hooks_composed": False,
                "layout_preserved": False, "collaboration_preserved": False,
                "unsafe_state_refused": False, "layout_confirmation_bound": False,
                "unsafe_receipt_refused": False, "existing_receipt_preserved": False}
    with tempfile.TemporaryDirectory(prefix="factory retrofit fixture ") as temporary:
        work = Path(temporary)
        target = work / "existing repo"
        target.mkdir()
        run("git", "init", cwd=target)
        run("git", "config", "user.name", "Fixture Author", cwd=target)
        run("git", "config", "user.email", "fixture@example.invalid", cwd=target)
        (target / "README.md").write_text("existing readme\n", encoding="utf-8")
        (target / "part-a.bin").write_bytes(b"\x00A")
        (target / "part-b.bin").write_bytes(b"B\xff")
        (target / "AGENTS.md").write_text("existing instructions\n", encoding="utf-8")
        (target / ".github/workflows").mkdir(parents=True)
        (target / ".github/workflows/ci.yml").write_text("name: existing-ci\n", encoding="utf-8")
        existing_pulse = target / ".agent/collaboration/PULSE.log"
        existing_pulse.parent.mkdir(parents=True)
        existing_pulse.write_text("existing collaboration state\n", encoding="utf-8")
        log = target / "hook.log"
        pre_commit = target / ".git/hooks/pre-commit"
        pre_commit.write_text(f"#!/usr/bin/env sh\nprintf 'old-pre-commit:%s:%s\\n' \"$PWD\" \"$#\" >> \"{log}\"\n", encoding="utf-8")
        pre_commit.chmod(0o755)
        pre_push = target / ".git/hooks/pre-push"
        pre_push.write_text(f"#!/usr/bin/env sh\nline=$(cat)\nprintf 'old-pre-push:%s:%s:%s:%s\\n' \"$PWD\" \"$1\" \"$2\" \"$line\" >> \"{log}\"\n", encoding="utf-8")
        pre_push.chmod(0o755)
        original_config = (target / ".git/config").read_bytes()
        original_pre_commit = pre_commit.read_bytes()
        original_pre_push = pre_push.read_bytes()
        before = tree_digest(target)

        first = preview(target)
        assert first["safe_to_install"] and tree_digest(target) == before
        assert first["hooks"]["existing"] and first["backup_paths"]
        evidence["preview_read_only"] = True

        wrong = run(str(AQD), "workflows", "retrofit", "--target", str(target), "--name", "existing fixture",
                    "--stack", "generic", "--confirm-retrofit", "0" * 64, cwd=ROOT, expected=1)
        assert json.loads(wrong.stdout)["installation"]["state"] == "CONFIRMATION_REQUIRED"
        assert tree_digest(target) == before

        stale = first["preview_digest"]
        # These two existing binary files retain the old raw concatenation
        # (`\0AB\xff`) while changing their boundaries.  Framed records bind
        # each path/content digest separately, so confirmation must stale.
        (target / "part-a.bin").write_bytes(b"\x00")
        (target / "part-b.bin").write_bytes(b"AB\xff")
        stale_result = run(str(AQD), "workflows", "retrofit", "--target", str(target), "--name", "existing fixture",
                           "--stack", "generic", "--confirm-retrofit", stale, cwd=ROOT, expected=1)
        assert json.loads(stale_result.stdout)["installation"]["state"] == "CONFIRMATION_REQUIRED"
        assert not (target / ".factory").exists()
        evidence["confirmation_enforced"] = True

        approved = preview(target)
        (target / "layout captured after preview").mkdir()
        layout_stale = run(str(AQD), "workflows", "retrofit", "--target", str(target), "--name", "existing fixture",
                           "--stack", "generic", "--confirm-retrofit", approved["preview_digest"], cwd=ROOT, expected=1)
        assert json.loads(layout_stale.stdout)["installation"]["state"] == "CONFIRMATION_REQUIRED"
        assert not (target / ".factory").exists()
        evidence["layout_confirmation_bound"] = True
        approved = preview(target)
        installed = run(str(AQD), "workflows", "retrofit", "--target", str(target), "--name", "existing fixture",
                        "--stack", "generic", "--confirm-retrofit", approved["preview_digest"], cwd=ROOT)
        receipt = json.loads(installed.stdout)
        assert receipt["installation"]["state"] == "INSTALLED"
        backup = target / receipt["backup_paths"][0]
        assert backup.read_bytes() == original_config
        assert (target / "AGENTS.md").read_text(encoding="utf-8") == "existing instructions\n"
        assert (target / ".github/workflows/ci.yml").read_text(encoding="utf-8") == "name: existing-ci\n"
        assert pre_commit.read_bytes() == original_pre_commit and pre_push.read_bytes() == original_pre_push
        assert existing_pulse.read_text(encoding="utf-8") == "existing collaboration state\n"
        assert json.loads((target / ".agent/collaboration/RESUME.json").read_text(encoding="utf-8"))["phase"] == "ORIENT"
        assert (target / ".agent/memory/issues-backlog.md").is_file()
        assert (target / ".agent/archive/.gitkeep").is_file()
        run(str(target / "scripts/governance/repo-structure-lint"), cwd=target)
        evidence["originals_preserved"] = True
        evidence["collaboration_preserved"] = True

        # Existing pre-commit runs before the factory gate and the factory
        # still blocks because generic checks remain explicitly unconfigured.
        (target / "src").mkdir()
        (target / "tests").mkdir()
        (target / "src/change.txt").write_text("fixture\n", encoding="utf-8")
        run("git", "add", "src/change.txt", cwd=target)
        blocked = run("git", "commit", "-m", "test: retrofit", cwd=target, expected=1)
        assert "UNCONFIGURED:" in blocked.stdout + blocked.stderr
        run(str(target / ".githooks/pre-push"), "origin", "unused", cwd=target / ".git", input_text="refs/heads/main abc refs/heads/main def\n")
        hooks = log.read_text(encoding="utf-8")
        assert f"old-pre-commit:{target}:0" in hooks
        assert f"old-pre-push:{target / '.git'}:origin:unused:refs/heads/main abc refs/heads/main def" in hooks
        # A non-factory hook remains authoritative: its failure reaches Git's
        # composed routing unchanged instead of being hidden by the factory.
        pre_push.write_text(f"#!/usr/bin/env sh\nline=$(cat)\nprintf 'old-pre-push-fail:%s:%s:%s:%s\\n' \"$PWD\" \"$1\" \"$2\" \"$line\" >> \"{log}\"\nexit 7\n", encoding="utf-8")
        pre_push.chmod(0o755)
        failed_old = run(str(target / ".githooks/pre-push"), "origin", "unused", cwd=target / ".git",
                         input_text="post-update\n", expected=1)
        assert failed_old.returncode == 7
        assert f"old-pre-push-fail:{target / '.git'}:origin:unused:post-update" in log.read_text(encoding="utf-8")
        evidence["hooks_composed"] = True

        (target / "undeclared-after-preview").mkdir()
        layout_failure = run(str(target / "scripts/governance/repo-structure-lint"), cwd=target, expected=1)
        assert "undeclared top-level path: undeclared-after-preview" in layout_failure.stdout + layout_failure.stderr
        evidence["layout_preserved"] = True

        # The retained bundle, not a private source copy, remains executable.
        run(str(target / ".factory/gate-bundle/self-test.sh"), cwd=target)

        external = work / "external hook path"
        external.mkdir()
        run("git", "init", cwd=external)
        run("git", "config", "core.hooksPath", "/tmp/external-hooks", cwd=external)
        denied = run(str(AQD), "workflows", "retrofit", "--target", str(external), "--name", "external", "--stack", "generic", cwd=ROOT, expected=1)
        assert json.loads(denied.stdout)["safe_to_install"] is False

        no_op = work / "no-op enforcement"
        no_op.mkdir()
        run("git", "init", cwd=no_op)
        (no_op / "scripts/governance").mkdir(parents=True)
        (no_op / "scripts/governance/gate-runner").write_text("#!/usr/bin/env sh\nexit 0\n", encoding="utf-8")
        no_op_denied = run(str(AQD), "workflows", "retrofit", "--target", str(no_op), "--name", "no-op", "--stack", "generic", cwd=ROOT, expected=1)
        assert "enforcement component collision" in json.loads(no_op_denied.stdout)["blocker"]
        assert not (no_op / ".factory").exists()

        backup_escape = work / "backup escape"
        outside_backup = work / "outside backup"
        backup_escape.mkdir()
        outside_backup.mkdir()
        run("git", "init", cwd=backup_escape)
        (backup_escape / ".factory").mkdir()
        (backup_escape / ".factory/gate-backups").symlink_to(outside_backup, target_is_directory=True)
        backup_denied = run(str(AQD), "workflows", "retrofit", "--target", str(backup_escape), "--name", "backup", "--stack", "generic", cwd=ROOT, expected=1)
        assert json.loads(backup_denied.stdout)["safe_to_install"] is False
        assert not any(outside_backup.iterdir())

        unsafe_state = work / "unsafe state"
        outside_state = work / "outside state"
        unsafe_state.mkdir()
        outside_state.mkdir()
        run("git", "init", cwd=unsafe_state)
        (unsafe_state / ".agent").mkdir()
        (unsafe_state / ".agent/collaboration").symlink_to(outside_state, target_is_directory=True)
        unsafe_state_denied = run(str(AQD), "workflows", "retrofit", "--target", str(unsafe_state),
                                  "--name", "unsafe state", "--stack", "generic", cwd=ROOT, expected=1)
        assert json.loads(unsafe_state_denied.stdout)["safe_to_install"] is False
        assert not any(outside_state.iterdir())
        evidence["unsafe_state_refused"] = True

        receipt_redirect = work / "receipt redirect"
        external_receipt = work / "external receipt"
        receipt_redirect.mkdir()
        run("git", "init", cwd=receipt_redirect)
        (receipt_redirect / ".factory").mkdir()
        external_receipt.write_text("external receipt sentinel\n", encoding="utf-8")
        (receipt_redirect / ".factory/gate-install.json").symlink_to(external_receipt)
        receipt_config = (receipt_redirect / ".git/config").read_bytes()
        receipt_denied = run(str(AQD), "workflows", "retrofit", "--target", str(receipt_redirect),
                             "--name", "receipt redirect", "--stack", "generic", cwd=ROOT, expected=1)
        assert json.loads(receipt_denied.stdout)["safe_to_install"] is False
        assert external_receipt.read_text(encoding="utf-8") == "external receipt sentinel\n"
        assert (receipt_redirect / ".git/config").read_bytes() == receipt_config
        assert not (receipt_redirect / ".factory/gate-bundle").exists()
        assert not (receipt_redirect / ".factory/gate-retrofit-hooks").exists()
        assert not (receipt_redirect / ".githooks").exists()
        evidence["unsafe_receipt_refused"] = True

        existing_receipt = work / "existing receipt"
        existing_receipt.mkdir()
        run("git", "init", cwd=existing_receipt)
        receipt_path = existing_receipt / ".factory/gate-install.json"
        receipt_path.parent.mkdir()
        receipt_path.write_text("ordinary receipt sentinel\n", encoding="utf-8")
        ordinary_config = (existing_receipt / ".git/config").read_bytes()
        ordinary_denied = run(str(AQD), "workflows", "retrofit", "--target", str(existing_receipt),
                              "--name", "existing receipt", "--stack", "generic", cwd=ROOT, expected=1)
        assert json.loads(ordinary_denied.stdout)["safe_to_install"] is False
        assert receipt_path.read_text(encoding="utf-8") == "ordinary receipt sentinel\n"
        assert (existing_receipt / ".git/config").read_bytes() == ordinary_config
        assert not (existing_receipt / ".factory/gate-bundle").exists()
        assert not (existing_receipt / ".factory/gate-retrofit-hooks").exists()
        assert not (existing_receipt / ".githooks").exists()
        evidence["existing_receipt_preserved"] = True

        tool_change = work / "tool availability"
        tool_change.mkdir()
        run("git", "init", cwd=tool_change)
        runtime = work / "runtime only"
        runtime.mkdir()
        for name in ("bash", "python3", "git", "dirname"):
            binary = shutil.which(name)
            assert binary, name
            (runtime / name).symlink_to(binary)
        tool_preview = preview(tool_change, "tool", path_override=runtime)
        assert "secret_scan" not in tool_preview["checks"]["commands"]
        assert any(item.startswith("secret_scan:") for item in tool_preview["checks"]["required_unconfigured"])
        fake_bin = work / "fake scanner"
        fake_bin.mkdir()
        fake = fake_bin / "gitleaks"
        fake.write_text("#!/usr/bin/env sh\nexit 0\n", encoding="utf-8")
        fake.chmod(0o755)
        (runtime / "gitleaks").symlink_to(fake)
        tool_available = preview(tool_change, "tool", path_override=runtime)
        assert tool_available["preview_digest"] != tool_preview["preview_digest"]
        assert tool_available["checks"]["commands"]["secret_scan"] == "gitleaks detect --no-git --redact"
        assert not any(item.startswith("secret_scan:") for item in tool_available["checks"]["required_unconfigured"])
        tool_stale = run(str(AQD), "workflows", "retrofit", "--target", str(tool_change), "--name", "tool", "--stack", "generic",
                         "--confirm-retrofit", tool_preview["preview_digest"], cwd=ROOT, expected=1, path_override=runtime)
        assert json.loads(tool_stale.stdout)["installation"]["state"] == "CONFIRMATION_REQUIRED"
        assert not (tool_change / ".factory").exists()

        redirected = work / "redirected git"
        outside = work / "outside git"
        redirected.mkdir()
        outside.mkdir()
        (redirected / ".git").symlink_to(outside, target_is_directory=True)
        redirect = run(str(AQD), "workflows", "retrofit", "--target", str(redirected), "--name", "redirected", "--stack", "generic", cwd=ROOT, expected=1)
        assert json.loads(redirect.stdout)["safe_to_install"] is False
        assert not any(outside.iterdir())

    assert all(evidence.values()), evidence
    print("AQ_QA_FACTORY_RETROFIT_FIXTURE=" + json.dumps(evidence, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
