#!/usr/bin/env python3
"""Focused FT-3 proof for the greenfield factory gate installer."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/ai/lib"))
import factory_gate_install  # noqa: E402
AQD = ROOT / "scripts/ai/aqd"
INSTALLER = ROOT / "scripts/ai/lib/factory_gate_install.py"
BUNDLE = ROOT / "templates/factory-gate-bundle"


def run(*command: str, cwd: Path | None = None, expected: int | None = 0,
        path_prefix: Path | None = None) -> subprocess.CompletedProcess[str]:
    environment = {key: value for key, value in os.environ.items()
                   if key not in {"GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES"}}
    if path_prefix:
        environment["PATH"] = str(path_prefix) + os.pathsep + environment.get("PATH", "")
    result = subprocess.run(command, cwd=cwd, env=environment, text=True, capture_output=True, check=False)
    if expected is not None and (result.returncode == 0) != (expected == 0):
        raise AssertionError(f"unexpected exit {result.returncode}: {' '.join(command)}\n{result.stdout}\n{result.stderr}")
    return result


def status(target: Path) -> dict[str, object]:
    result = run(str(AQD), "workflows", "factory-gate-status", "--target", str(target))
    return json.loads(result.stdout)


def main() -> int:
    evidence = {"hooks_block_bad_commit": False, "tracker_discovered": False,
                "collision_preserved": False, "unconfigured_blocked": False,
                "collaboration_seeded": False, "layout_enforced": False,
                "agent_notice_safe": False}
    with tempfile.TemporaryDirectory(prefix="factory gate fixture ") as temporary:
        work = Path(temporary)
        target = work / "green field"
        created = run(str(AQD), "workflows", "project-init", "--target", str(target),
                      "--name", "safe fixture", "--goal", "prove installed hook", "--stack", "generic", "--owner", "test")
        assert '"safe_to_install": true' in created.stdout
        receipt = json.loads((target / ".factory/gate-install.json").read_text(encoding="utf-8"))
        assert receipt["activation"] == "ACTIVATION_BLOCKED"
        assert receipt["checks"]["state"] == "CONFIGURATION_BLOCKED"
        assert receipt["hooks"]["state"] == "ACTIVE"
        evidence["unconfigured_blocked"] = True
        assert (target / ".agent/collaboration/PULSE.log").is_file()
        assert json.loads((target / ".agent/collaboration/RESUME.json").read_text(encoding="utf-8"))["phase"] == "ORIENT"
        assert (target / ".agent/memory/issues-backlog.md").is_file()
        assert (target / ".agent/archive/.gitkeep").is_file()
        evidence["collaboration_seeded"] = True
        agent_notice = (target / "AGENTS.md").read_text(encoding="utf-8")
        workflow_notice = (target / ".agent/WORKFLOW-CANON.md").read_text(encoding="utf-8")
        for token in ("{{BUILD_CMD}}", "{{TEST_CMD}}", "{{LINT_CMD}}", "{{SECRET_SCAN_CMD}}"):
            assert token not in agent_notice and token not in workflow_notice
        assert "fail-closed until explicitly configured" in agent_notice
        assert "not an executable command" in workflow_notice
        evidence["agent_notice_safe"] = True

        # The standalone bundle is a recovery/reference artifact, so every
        # preserved source byte and its own self-test must remain runnable.
        for source in BUNDLE.rglob("*"):
            if source.is_file() and "__pycache__" not in source.parts and source.suffix != ".pyc":
                installed = target / ".factory/gate-bundle" / source.relative_to(BUNDLE)
                assert installed.read_bytes() == source.read_bytes(), source
        run(str(target / ".factory/gate-bundle/self-test.sh"), cwd=target)
        policy_lint = target / "scripts/governance/repo-structure-lint"
        run(str(policy_lint), cwd=target)
        (target / "later-added-root").mkdir()
        undeclared = run(str(policy_lint), cwd=target, expected=1)
        assert "undeclared top-level path: later-added-root" in undeclared.stdout + undeclared.stderr
        evidence["layout_enforced"] = True

        # A trusted fixture executable lets the metadata-only detector render
        # its declared scanner command without installing a dependency.
        fake_bin = work / "trusted tools"
        fake_bin.mkdir()
        fake_gitleaks = fake_bin / "gitleaks"
        fake_gitleaks.write_text("#!/usr/bin/env sh\nexit 0\n", encoding="utf-8")
        fake_gitleaks.chmod(0o755)
        redaction_target = work / "redaction target"
        redaction_target.mkdir()
        run("git", "init", cwd=redaction_target)
        run(sys.executable, str(INSTALLER), "install", "--target", str(redaction_target),
            "--bundle-root", str(BUNDLE), "--project-name", "redaction fixture", path_prefix=fake_bin)
        assert "gitleaks detect --no-git --redact" in (redaction_target / "scripts/governance/checks.d/hard-20-secret-scan.sh").read_text(encoding="utf-8")

        run("git", "config", "user.name", "Fixture Author", cwd=target)
        run("git", "config", "user.email", "fixture-author@example.invalid", cwd=target)
        (target / "src").mkdir()
        (target / "tests").mkdir()
        (target / "src/fixture.txt").write_text("trusted fixture\n", encoding="utf-8")
        run("git", "add", "src/fixture.txt", cwd=target)
        blocked = run("git", "commit", "-m", "test: gate fixture", cwd=target, expected=1)
        assert "Factory gate:" in blocked.stdout + blocked.stderr
        assert "UNCONFIGURED:" in blocked.stdout + blocked.stderr
        evidence["hooks_block_bad_commit"] = True

        checked = run(str(target / "scripts/governance/checks.d/hard-80-pm-tracker.sh"), cwd=target)
        assert "pm-tracker: PASS (1 tracker(s))" in checked.stdout
        current = status(target)
        assert current["tracker"]["state"] == "DISCOVERED"
        assert ".agents/plans/factory-gate/tracker.json" in current["tracker"]["paths"]
        evidence["tracker_discovered"] = True

        polyglot = {"profiles": {
            "python": {"checks": {"test": {"state": "UNCONFIGURED", "reason": "runtime module availability is not verified"}}},
            "rust": {"checks": {"test": {"state": "READY", "command": "cargo test"}}},
        }}
        commands, blocked = factory_gate_install.command_values(polyglot)
        assert "test" not in commands
        assert any(item.startswith("test: python:") for item in blocked)
        rendered = factory_gate_install.rendered(BUNDLE / "checks.d/hard-40-test.sh",
                                                 factory_gate_install.render_values("polyglot", commands)).decode()
        assert "UNCONFIGURED: render {{TEST_CMD}}" in rendered

        existing = work / "existing hooks"
        existing.mkdir()
        run("git", "init", cwd=existing)
        run("git", "config", "core.hooksPath", "custom-hooks", cwd=existing)
        before = run(str(AQD), "workflows", "project-init", "--target", str(existing),
                     "--name", "existing", "--goal", "must refuse", "--stack", "generic", "--owner", "test", "--force", expected=1)
        refused = json.loads(before.stdout.splitlines()[-1])
        assert refused["hooks"]["state"] == "CONFLICT" and not refused["safe_to_install"]
        assert run("git", "config", "--get", "core.hooksPath", cwd=existing).stdout.strip() == "custom-hooks"
        assert not (existing / ".factory").exists() and not (existing / ".agent").exists()
        evidence["collision_preserved"] = True

        default_hooks = work / "default hooks"
        default_hooks.mkdir()
        run("git", "init", cwd=default_hooks)
        sentinel = default_hooks / ".git/hooks/pre-commit"
        sentinel.write_text("#!/usr/bin/env sh\necho sentinel\n", encoding="utf-8")
        sentinel.chmod(0o755)
        push_sentinel = default_hooks / ".git/hooks/pre-push"
        push_sentinel.write_text("#!/usr/bin/env sh\necho push-sentinel\n", encoding="utf-8")
        push_sentinel.chmod(0o755)
        default_refusal = run(str(AQD), "workflows", "project-init", "--target", str(default_hooks),
                              "--name", "default hooks", "--goal", "must preserve", "--stack", "generic", "--owner", "test", expected=1)
        assert json.loads(default_refusal.stdout.splitlines()[-1])["hooks"]["state"] == "CONFLICT"
        assert sentinel.read_text(encoding="utf-8") == "#!/usr/bin/env sh\necho sentinel\n"
        assert push_sentinel.read_text(encoding="utf-8") == "#!/usr/bin/env sh\necho push-sentinel\n"
        assert not (default_hooks / ".agent").exists()

        redirected = work / "redirected metadata"
        external_git = work / "outside git metadata"
        redirected.mkdir()
        external_git.mkdir()
        (redirected / ".git").symlink_to(external_git, target_is_directory=True)
        redirect_refusal = run(str(AQD), "workflows", "project-init", "--target", str(redirected),
                               "--name", "redirect", "--goal", "must preserve", "--stack", "generic", "--owner", "test", expected=1)
        assert json.loads(redirect_refusal.stdout.splitlines()[-1])["hooks"]["state"] == "CONFLICT"
        assert not any(external_git.iterdir()) and not (redirected / ".agent").exists()

        redirected_config = work / "redirected config"
        external_config = work / "outside git config"
        redirected_config.mkdir()
        run("git", "init", cwd=redirected_config)
        external_config.write_text("[core]\nrepositoryformatversion = 0\n", encoding="utf-8")
        (redirected_config / ".git/config").unlink()
        (redirected_config / ".git/config").symlink_to(external_config)
        config_refusal = run(str(AQD), "workflows", "project-init", "--target", str(redirected_config),
                             "--name", "config redirect", "--goal", "must preserve", "--stack", "generic", "--owner", "test", expected=1)
        assert json.loads(config_refusal.stdout.splitlines()[-1])["hooks"]["state"] == "CONFLICT"
        assert external_config.read_text(encoding="utf-8") == "[core]\nrepositoryformatversion = 0\n"
        assert not (redirected_config / ".agent").exists()

        shared_metadata = work / "shared metadata"
        outside_common = work / "outside common git"
        shared_metadata.mkdir()
        outside_common.mkdir()
        outside_common_config = outside_common / "config"
        outside_common_config.write_text("[core]\nrepositoryformatversion = 0\n", encoding="utf-8")
        run("git", "init", cwd=shared_metadata)
        (shared_metadata / ".git/commondir").write_text("../outside common git\n", encoding="utf-8")
        common_refusal = run(str(AQD), "workflows", "project-init", "--target", str(shared_metadata),
                             "--name", "shared metadata", "--goal", "must preserve", "--stack", "generic", "--owner", "test", expected=1)
        assert json.loads(common_refusal.stdout.splitlines()[-1])["hooks"]["state"] == "CONFLICT"
        assert outside_common_config.read_text(encoding="utf-8") == "[core]\nrepositoryformatversion = 0\n"
        assert not (shared_metadata / ".agent").exists()

        hostile_bundle = work / "hostile bundle"
        shutil.copytree(BUNDLE, hostile_bundle)
        manifest = json.loads((hostile_bundle / "MANIFEST.json").read_text(encoding="utf-8"))
        manifest["files"][1]["install_target"] = "../escaped"
        (hostile_bundle / "MANIFEST.json").write_text(json.dumps(manifest), encoding="utf-8")
        hostile_target = work / "hostile target"
        hostile_target.mkdir()
        hostile = run(sys.executable, str(INSTALLER), "preview", "--target", str(hostile_target),
                      "--bundle-root", str(hostile_bundle), "--project-name", "$(no-shell-execution)", expected=1)
        assert json.loads(hostile.stdout)["state"] == "ERROR"
        assert not (work / "escaped").exists()

    assert all(evidence.values()), evidence
    print("AQ_QA_FACTORY_GATE_FIXTURE=" + json.dumps(evidence, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
