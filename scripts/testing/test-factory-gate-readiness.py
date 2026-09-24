#!/usr/bin/env python3
"""Focused FT-5 proof for the metadata-only factory readiness preflight.

Covers the five adversarial cases from
.agents/plans/factory-gate-templates/FACTORY-READINESS-ADVISORY-20260918.md:

  Case 1 (stale/missing execution evidence and unconfigured-checks fail-closed)
    -> missing installation, disabled hooks, stale-or-missing execution
       evidence, and unconfigured-required-checks fixtures below.
  Case 2/3/4 are exercised by the existing FT-3/FT-4 install/retrofit
       fixtures (path containment, singleton engine, absent-lane tolerance)
       and by this file's lanes/negative-fixture assertions; this file adds
       the FT-5-specific readiness surface on top of them.
  Case 5 (typed blocked states, never a silent stall/fake PASS)
    -> every negative fixture below asserts a typed blocker code, never a
       bare failure or a silently-passed check.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AQD = ROOT / "scripts/ai/aqd"
GATE_RUNNER = ROOT / "templates/factory-gate-bundle/gate-runner"


def run(*command: str, cwd: Path | None = None, expected: int | None = 0,
        path_prefix: Path | None = None, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    # Drop inherited GIT_* so a nested git op cannot escape the fixture repo, and
    # HYBRID_URL so the absent-lane assertion is hermetic: under tier0/aq-qa the
    # coordinator env sets HYBRID_URL, which would otherwise report the lane
    # CONFIGURED instead of the TRANSPORT_UNAVAILABLE this fixture asserts.
    environment = {key: value for key, value in os.environ.items()
                   if key not in {"GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
                                   "GIT_ALTERNATE_OBJECT_DIRECTORIES", "HYBRID_URL"}}
    if path_prefix:
        environment["PATH"] = str(path_prefix) + os.pathsep + environment.get("PATH", "")
    if extra_env:
        environment.update(extra_env)
    result = subprocess.run(command, cwd=cwd, env=environment, text=True, capture_output=True, check=False)
    if expected is not None and (result.returncode == 0) != (expected == 0):
        raise AssertionError(f"unexpected exit {result.returncode}: {' '.join(command)}\n{result.stdout}\n{result.stderr}")
    return result


def preflight(target: Path, expected: int | None = None, path_prefix: Path | None = None) -> dict[str, object]:
    # Defect-2 fix: status()/readiness-preflight now re-derive checks live
    # from the current repo instead of the frozen install receipt, so a
    # fixture whose install/retrofit ran with a fake tool PATH (cargo,
    # gitleaks) must supply the SAME path_prefix here -- a real PATH is
    # stable across calls; only this hermetic fixture varies it per-call.
    result = run(str(AQD), "workflows", "factory-gate-preflight", "--target", str(target), expected=expected,
                 path_prefix=path_prefix)
    return json.loads(result.stdout)


def blocker_codes(report: dict[str, object]) -> set[str]:
    return {entry["code"] for entry in report["blockers"]}  # type: ignore[index]


def fake_tools(directory: Path, *names: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for name in names:
        binary = directory / name
        binary.write_text("#!/usr/bin/env sh\nexit 0\n", encoding="utf-8")
        binary.chmod(0o755)


def build_ready_rust_target(work: Path, name: str) -> tuple[Path, Path]:
    """Retrofit-install a rust-stack target with hard checks configured (no commit yet)."""
    target = work / name
    (target / "src").mkdir(parents=True)
    run("git", "init", cwd=target)
    run("git", "symbolic-ref", "HEAD", "refs/heads/readiness-fixture", cwd=target)
    run("git", "config", "user.name", "Fixture Author", cwd=target)
    run("git", "config", "user.email", "fixture@example.invalid", cwd=target)
    (target / "Cargo.toml").write_text('[package]\nname = "fixture"\n', encoding="utf-8")
    (target / "src/main.rs").write_text("fn main() {}\n", encoding="utf-8")
    fake_bin = work / f"{name}-bin"
    fake_tools(fake_bin, "cargo", "gitleaks")
    preview = run(str(AQD), "workflows", "retrofit", "--target", str(target), "--name", name,
                  "--stack", "rust", cwd=ROOT, path_prefix=fake_bin)
    preview_json = json.loads(preview.stdout)
    assert preview_json["safe_to_install"], preview_json
    installed = run(str(AQD), "workflows", "retrofit", "--target", str(target), "--name", name,
                    "--stack", "rust", "--confirm-retrofit", preview_json["preview_digest"],
                    cwd=ROOT, path_prefix=fake_bin)
    installed_json = json.loads(installed.stdout)
    assert installed_json["installation"]["state"] == "INSTALLED", installed_json
    return target, fake_bin


def commit_fixture_change(target: Path, fake_bin: Path, message: str = "test: readiness fixture commit") -> None:
    run("git", "add", "Cargo.toml", "src/main.rs", cwd=target)
    run("git", "commit", "-m", message, cwd=target, path_prefix=fake_bin)


def main() -> int:
    evidence = {
        "positive_ready": False,
        "case1_missing_installation": False,
        "case1_disabled_hooks": False,
        "case1_missing_execution_evidence": False,
        "case1_stale_execution_evidence": False,
        "case1_unconfigured_checks_fail_closed": False,
        "bad_repository_organization": False,
        "invalid_tracker": False,
        "absent_lane_informational_only": False,
        "target_side_gate_runner_preflight_parity": False,
        "checks_live_reflect_current_repo": False,
        "upgrade_refreshes_gate_runner_and_recovers_evidence": False,
        "external_scope_cannot_mint_evidence": False,
        "missing_canonical_inventory_blocked": False,
        "symlinked_canonical_check_blocked": False,
        "symlinked_manifest_blocked": False,
        "failed_execution_evidence_explicit_and_ignored": False,
        "receipt_provenance_blocks_deleted_check_and_manifest_entry": False,
        "injected_check_refused_before_execution": False,
        "malformed_failed_evidence_is_missing": False,
        "unsafe_git_info_refused_before_retrofit": False,
        "toctou_execution_uses_verified_snapshot": False,
        "umask_robust_mode_provenance": False,
        "special_and_group_write_mode_rejected": False,
        "boundary_mismatch_source_refused_before_execution": False,
        "boundary_snapshot_first_hook_proof": False,
    }
    with tempfile.TemporaryDirectory(prefix="factory readiness fixture ") as temporary:
        work = Path(temporary)

        # -- Negative: missing installation ---------------------------------
        never_installed = work / "never installed"
        never_installed.mkdir()
        run("git", "init", cwd=never_installed)
        report = preflight(never_installed, expected=1)
        assert report["ready"] is False and report["state"] == "BLOCKED"
        assert "INSTALLATION_ABSENT" in blocker_codes(report)
        evidence["case1_missing_installation"] = True

        # -- Positive: fully configured, freshly-executed repo reports ready.
        target, fake_bin = build_ready_rust_target(work, "ready target")
        pre_commit_report = preflight(target, expected=1, path_prefix=fake_bin)
        assert "MISSING_EXECUTION_EVIDENCE" in blocker_codes(pre_commit_report)
        evidence["case1_missing_execution_evidence"] = True

        commit_fixture_change(target, fake_bin)
        ready_report = preflight(target, expected=0, path_prefix=fake_bin)
        assert ready_report["ready"] is True and ready_report["state"] == "READY"
        assert ready_report["blockers"] == []
        rule_names = {entry["rule"] for entry in ready_report["practice_coverage"]}
        assert {"installation", "hook_routing", "required_checks_configured", "activation",
                "execution_evidence_freshness", "repository_layout", "pm_tracker"} <= rule_names
        # Absent lanes are informational only and never block; the coordinator
        # lane is unconfigured in this hermetic fixture (no HYBRID_URL) yet
        # readiness is still True.
        assert ready_report["lanes"]["hybrid_coordinator"]["state"] == "TRANSPORT_UNAVAILABLE"
        evidence["positive_ready"] = True
        evidence["absent_lane_informational_only"] = True

        # The installed gate-runner's own --preflight mode must agree.
        target_side = run(str(target / "scripts/governance/gate-runner"), "--preflight", cwd=target)
        target_side_json = json.loads(target_side.stdout)
        assert target_side_json["ready"] is True and target_side_json["blockers"] == []
        evidence["target_side_gate_runner_preflight_parity"] = True

        # A passing external subset cannot certify an installed target or
        # overwrite its canonical execution evidence.
        external_checks = work / "external-passing-subset"
        external_checks.mkdir()
        external_check = external_checks / "hard-10-synthetic.sh"
        external_check.write_text("#!/usr/bin/env sh\nexit 0\n", encoding="utf-8")
        external_check.chmod(0o755)
        evidence_path = target / ".factory/gate-run-evidence.json"
        prior_evidence = evidence_path.read_bytes()
        scope_env = {"FACTORY_GATE_CHECKS_DIR": str(external_checks), "FACTORY_REPO_ROOT": str(target)}
        run(str(target / "scripts/governance/gate-runner"), "--pre-commit", cwd=target,
            expected=1, extra_env=scope_env)
        assert evidence_path.read_bytes() == prior_evidence
        override_preflight = run(str(target / "scripts/governance/gate-runner"), "--preflight", cwd=target,
                                 expected=1, extra_env=scope_env)
        assert "EXECUTION_SCOPE_INVALID" in blocker_codes(json.loads(override_preflight.stdout))

        redirected_root = work / "receipt-free-redirected-root"
        redirected_root.mkdir()
        redirected_side_effect = work / "redirected-payload-executed"
        external_check.write_text(f"#!/usr/bin/env sh\ntouch -- {str(redirected_side_effect)!r}\n", encoding="utf-8")
        redirected_env = {"FACTORY_GATE_CHECKS_DIR": str(external_checks),
                          "FACTORY_REPO_ROOT": str(redirected_root)}
        run(str(target / "scripts/governance/gate-runner"), "--pre-commit", cwd=target,
            expected=1, extra_env=redirected_env)
        assert not redirected_side_effect.exists()
        evidence["external_scope_cannot_mint_evidence"] = True

        canonical_checks = target / "scripts/governance/checks.d"
        missing_check = canonical_checks / "hard-40-test.sh"
        missing_contents = missing_check.read_bytes()
        missing_check.unlink()
        assert "EXECUTION_SCOPE_INVALID" in blocker_codes(preflight(target, expected=1, path_prefix=fake_bin))
        missing_check.write_bytes(missing_contents)
        missing_check.chmod(0o755)
        evidence["missing_canonical_inventory_blocked"] = True

        escaped_check = canonical_checks / "hard-50-lint.sh"
        escaped_contents = escaped_check.read_bytes()
        escaped_check.unlink()
        outside_check = work / "outside-canonical-check"
        side_effect = work / "symlink-payload-executed"
        outside_check.write_text(f"#!/usr/bin/env sh\ntouch -- {str(side_effect)!r}\n", encoding="utf-8")
        outside_check.chmod(0o755)
        escaped_check.symlink_to(outside_check)
        run(str(target / "scripts/governance/gate-runner"), "--pre-commit", cwd=target, expected=1)
        assert not side_effect.exists()
        assert "EXECUTION_SCOPE_INVALID" in blocker_codes(preflight(target, expected=1, path_prefix=fake_bin))
        escaped_check.unlink()
        escaped_check.write_bytes(escaped_contents)
        escaped_check.chmod(0o755)
        evidence["symlinked_canonical_check_blocked"] = True

        manifest_path = target / ".factory/gate-bundle/MANIFEST.json"
        manifest_contents = manifest_path.read_bytes()
        manifest_path.unlink()
        outside_manifest = work / "outside-manifest.json"
        outside_manifest.write_bytes(manifest_contents)
        manifest_path.symlink_to(outside_manifest)
        assert "EXECUTION_SCOPE_INVALID" in blocker_codes(preflight(target, expected=1, path_prefix=fake_bin))
        manifest_path.unlink()
        manifest_path.write_bytes(manifest_contents)
        evidence["symlinked_manifest_blocked"] = True

        # Deleting both a check and its manifest entry cannot downgrade the
        # required scope: the factory-owned install receipt remains the
        # provenance baseline and rejects the altered manifest before a run.
        deleted_check = canonical_checks / "hard-40-test.sh"
        deleted_contents = deleted_check.read_bytes()
        deleted_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        deleted_manifest["files"] = [entry for entry in deleted_manifest["files"]
                                     if entry.get("install_target") != "scripts/governance/checks.d/hard-40-test.sh"]
        deleted_check.unlink()
        manifest_path.write_text(json.dumps(deleted_manifest), encoding="utf-8")
        run(str(target / "scripts/governance/gate-runner"), "--pre-commit", cwd=target, expected=1)
        assert "EXECUTION_SCOPE_INVALID" in blocker_codes(preflight(target, expected=1, path_prefix=fake_bin))
        deleted_check.write_bytes(deleted_contents)
        deleted_check.chmod(0o755)
        manifest_path.write_bytes(manifest_contents)
        evidence["receipt_provenance_blocks_deleted_check_and_manifest_entry"] = True

        # -- CRITICAL: an injected checks.d/*.sh PLUS a matching new
        #    MANIFEST.json entry, with the install receipt left untouched,
        #    must be refused BEFORE the injected script ever runs. A
        #    name-set match alone (expected == actual) would pass here --
        #    the pre-execution gate must bind manifest/checks.d contents to
        #    the receipt's recorded sha256 hashes, exactly like
        #    canonical_scope() does for --preflight and the post-execution
        #    evidence writer, or this is a fail-open in a security gate.
        injected_check = canonical_checks / "hard-90-injected.sh"
        injection_side_effect = work / "injected-check-executed"
        injected_check.write_text(
            f"#!/usr/bin/env sh\ntouch -- {str(injection_side_effect)!r}\nexit 0\n", encoding="utf-8")
        injected_check.chmod(0o755)
        injected_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        injected_manifest["files"].append({
            "install_target": "scripts/governance/checks.d/hard-90-injected.sh",
            "disposition": "factory_owned",
        })
        manifest_path.write_text(json.dumps(injected_manifest), encoding="utf-8")
        injection_run = run(str(target / "scripts/governance/gate-runner"), "--pre-commit", cwd=target,
                            expected=1, path_prefix=fake_bin)
        assert not injection_side_effect.exists(), \
            "injected check executed -- pre-execution scope gate failed to refuse before running checks"
        assert "execution check scope" in injection_run.stderr
        assert "EXECUTION_SCOPE_INVALID" in blocker_codes(preflight(target, expected=1, path_prefix=fake_bin))
        injected_check.unlink()
        manifest_path.write_bytes(manifest_contents)
        evidence["injected_check_refused_before_execution"] = True

        # A failing canonical check produces an explicit failed receipt.  The
        # receipt is locally excluded, so the hook does not dirty source work.
        failing_cargo = fake_bin / "cargo"
        cargo_contents = failing_cargo.read_bytes()
        failing_cargo.write_text("#!/usr/bin/env sh\nexit 1\n", encoding="utf-8")
        failing_cargo.chmod(0o755)
        run(str(target / "scripts/governance/gate-runner"), "--pre-commit", cwd=target,
            expected=1, path_prefix=fake_bin)
        failed_report = preflight(target, expected=1, path_prefix=fake_bin)
        assert "FAILED_EXECUTION_EVIDENCE" in blocker_codes(failed_report)
        status = run("git", "status", "--porcelain", cwd=target).stdout
        assert ".factory/gate-run-evidence.json" not in status
        evidence_path.write_text(json.dumps({"evidence_digest": "x", "fail_count": 1}), encoding="utf-8")
        malformed_report = preflight(target, expected=1, path_prefix=fake_bin)
        assert "MISSING_EXECUTION_EVIDENCE" in blocker_codes(malformed_report)
        failing_cargo.write_bytes(cargo_contents)
        failing_cargo.chmod(0o755)
        (target / "Cargo.lock").unlink(missing_ok=True)
        shutil.rmtree(target / "target", ignore_errors=True)
        run(str(target / "scripts/governance/gate-runner"), "--pre-commit", cwd=target,
            path_prefix=fake_bin)
        evidence["failed_execution_evidence_explicit_and_ignored"] = True
        evidence["malformed_failed_evidence_is_missing"] = True

        # The local exclusion is an installer mutation too.  A redirected
        # .git/info is refused during preview, before any retrofit write.
        unsafe_target, unsafe_fake_bin = build_ready_rust_target(work, "unsafe git info target")
        info_dir = unsafe_target / ".git/info"
        outside_info = work / "outside-git-info"
        outside_info.mkdir()
        shutil.rmtree(info_dir)
        info_dir.symlink_to(outside_info, target_is_directory=True)
        unsafe_preview = run(str(AQD), "workflows", "retrofit", "--target", str(unsafe_target),
                             "--name", "unsafe git info target", "--stack", "rust", cwd=ROOT,
                             expected=1, path_prefix=unsafe_fake_bin)
        assert "unsafe git info directory" in unsafe_preview.stdout
        evidence["unsafe_git_info_refused_before_retrofit"] = True

        # -- Negative: stale execution evidence (Case 1 anti-gaming) --------
        (target / "src/main.rs").write_text('fn main() { println!("changed after the recorded pass"); }\n', encoding="utf-8")
        stale_report = preflight(target, expected=1, path_prefix=fake_bin)
        assert "STALE_EXECUTION_EVIDENCE" in blocker_codes(stale_report)
        stale_entry = next(e for e in stale_report["practice_coverage"] if e["rule"] == "execution_evidence_freshness")
        assert stale_entry["evidence"]["recorded_digest"] != stale_entry["evidence"]["current_digest"]
        run("git", "checkout", "--", "src/main.rs", cwd=target)  # restore before the next assertion
        evidence["case1_stale_execution_evidence"] = True

        # -- Negative: disabled/invalid hooks (routing tampered post-install)
        hooks_target, hooks_fake_bin = build_ready_rust_target(work, "disabled hooks target")
        commit_fixture_change(hooks_target, hooks_fake_bin)
        run("git", "config", "--unset", "core.hooksPath", cwd=hooks_target)
        disabled_report = preflight(hooks_target, expected=1, path_prefix=hooks_fake_bin)
        assert "HOOKS_INVALID" in blocker_codes(disabled_report)
        evidence["case1_disabled_hooks"] = True

        # -- Negative: required checks unconfigured (generic stack; never
        #    silently passed or auto-installed) -----------------------------
        unconfigured_target = work / "unconfigured checks target"
        unconfigured_target.mkdir()
        run(str(AQD), "workflows", "project-init", "--target", str(unconfigured_target),
            "--name", "unconfigured checks", "--goal", "prove fail-closed", "--stack", "generic",
            "--owner", "test", cwd=ROOT)
        unconfigured_report = preflight(unconfigured_target, expected=1)
        assert "CHECKS_UNCONFIGURED" in blocker_codes(unconfigured_report)
        checks_entry = next(e for e in unconfigured_report["practice_coverage"] if e["rule"] == "required_checks_configured")
        assert any(item.startswith("build:") for item in checks_entry["evidence"]["hard_blocking"])
        # live_service/freshness are structurally never auto-configurable and
        # must stay informational (WARN), never a readiness blocker on their own.
        assert not any(code == "CHECKS_UNCONFIGURED" for code in blocker_codes(unconfigured_report)
                        if all(item.startswith(("live_service:", "freshness:")) for item in checks_entry["evidence"]["hard_blocking"]))
        evidence["case1_unconfigured_checks_fail_closed"] = True

        # -- Negative: bad repository organization (undeclared top-level path
        #    added after install; repo-structure-lint must fail-closed) -----
        layout_target, layout_fake_bin = build_ready_rust_target(work, "bad layout target")
        commit_fixture_change(layout_target, layout_fake_bin)
        assert preflight(layout_target, expected=0, path_prefix=layout_fake_bin)["ready"] is True
        (layout_target / "undeclared-after-install").mkdir()
        layout_report = preflight(layout_target, expected=1, path_prefix=layout_fake_bin)
        assert "LAYOUT_INVALID" in blocker_codes(layout_report)
        layout_entry = next(e for e in layout_report["practice_coverage"] if e["rule"] == "repository_layout")
        assert "undeclared top-level path" in layout_entry["evidence"]["detail"]
        evidence["bad_repository_organization"] = True

        # -- Negative: invalid tracker (corrupt an already-discovered tracker)
        tracker_target, tracker_fake_bin = build_ready_rust_target(work, "invalid tracker target")
        commit_fixture_change(tracker_target, tracker_fake_bin)
        assert preflight(tracker_target, expected=0, path_prefix=tracker_fake_bin)["ready"] is True
        tracker_path = tracker_target / ".agents/plans/factory-gate/tracker.json"
        tracker_path.write_text("{not valid json", encoding="utf-8")
        tracker_report = preflight(tracker_target, expected=1, path_prefix=tracker_fake_bin)
        assert "TRACKER_INVALID" in blocker_codes(tracker_report)
        evidence["invalid_tracker"] = True

        # -- Defect 2: status()/readiness-preflight re-derive checks LIVE
        #    from the current repo, never the frozen install-time receipt --
        #    a package.json that grows test/lint scripts after install must
        #    be reported CONFIGURED immediately, with no re-install needed.
        node_target = work / "live checks target"
        node_fake_bin = work / "live checks target-bin"
        fake_tools(node_fake_bin, "npm", "gitleaks")
        run(str(AQD), "workflows", "project-init", "--target", str(node_target),
            "--name", "live checks", "--goal", "prove live checks", "--stack", "node",
            "--owner", "test", cwd=ROOT, path_prefix=node_fake_bin)
        before_json = json.loads(run(str(AQD), "workflows", "factory-gate-status", "--target", str(node_target),
                                     path_prefix=node_fake_bin).stdout)
        assert any(item.startswith("test:") for item in before_json["checks"]["required_unconfigured"])
        assert any(item.startswith("lint:") for item in before_json["checks"]["required_unconfigured"])
        (node_target / "package.json").write_text(
            json.dumps({"name": "fixture", "scripts": {"test": "node test.js", "lint": "eslint ."}}), encoding="utf-8")
        after_json = json.loads(run(str(AQD), "workflows", "factory-gate-status", "--target", str(node_target),
                                    path_prefix=node_fake_bin).stdout)
        assert not any(item.startswith("test:") for item in after_json["checks"]["required_unconfigured"])
        assert not any(item.startswith("lint:") for item in after_json["checks"]["required_unconfigured"])
        assert after_json["checks"]["commands"]["test"] == "npm run test"
        assert after_json["checks"]["commands"]["lint"] == "npm run lint"
        evidence["checks_live_reflect_current_repo"] = True

        # -- Defect 1 + Defect 3: a compatible upgrade re-applies retrofit in
        #    place (never refuses on the already-configured core.hooksPath or
        #    the existing .factory/gate-bundle / scripts/governance
        #    destinations) and refreshes factory tooling -- including a
        #    gate-runner that predates evidence-writing support, which would
        #    otherwise block MISSING_EXECUTION_EVIDENCE forever.
        upgrade_target, upgrade_fake_bin = build_ready_rust_target(work, "upgrade target")
        commit_fixture_change(upgrade_target, upgrade_fake_bin)
        assert preflight(upgrade_target, expected=0, path_prefix=upgrade_fake_bin)["ready"] is True

        gate_runner_path = upgrade_target / "scripts/governance/gate-runner"
        current_gate_runner = GATE_RUNNER.read_bytes()
        assert gate_runner_path.read_bytes() == current_gate_runner
        evidence_path = upgrade_target / ".factory/gate-run-evidence.json"
        assert evidence_path.is_file()
        # Simulate a target whose installed gate-runner PREDATES evidence
        # support: it exits 0 on --pre-commit but never writes the receipt.
        gate_runner_path.write_text("#!/usr/bin/env bash\nset -euo pipefail\nexit 0\n", encoding="utf-8")
        gate_runner_path.chmod(0o755)
        # This is an old factory-owned baseline, not arbitrary user
        # tampering: lossless upgrades may refresh only a path whose receipt
        # expressly records the currently installed bytes and mode.
        prior_receipt_path = upgrade_target / ".factory/gate-install.json"
        prior_receipt = json.loads(prior_receipt_path.read_text(encoding="utf-8"))
        prior_receipt["managed_files"]["scripts/governance/gate-runner"] = {
            "disposition": "factory_owned", "mode": 0o755,
            "sha256": hashlib.sha256(gate_runner_path.read_bytes()).hexdigest(),
        }
        prior_receipt_path.write_text(json.dumps(prior_receipt), encoding="utf-8")
        evidence_path.unlink()
        stale_runner_report = preflight(upgrade_target, expected=1, path_prefix=upgrade_fake_bin)
        assert "MISSING_EXECUTION_EVIDENCE" in blocker_codes(stale_runner_report)

        upgrade_preview = run(str(AQD), "workflows", "retrofit", "--target", str(upgrade_target), "--name", "upgrade target",
                              "--stack", "rust", cwd=ROOT, path_prefix=upgrade_fake_bin)
        upgrade_preview_json = json.loads(upgrade_preview.stdout)
        assert upgrade_preview_json["safe_to_install"], upgrade_preview_json
        assert upgrade_preview_json.get("upgrade") is True
        upgrade_installed = run(str(AQD), "workflows", "retrofit", "--target", str(upgrade_target), "--name", "upgrade target",
                                "--stack", "rust", "--confirm-retrofit", upgrade_preview_json["preview_digest"],
                                cwd=ROOT, path_prefix=upgrade_fake_bin)
        upgrade_receipt = json.loads(upgrade_installed.stdout)
        assert upgrade_receipt["installation"]["state"] == "INSTALLED"
        assert upgrade_receipt.get("upgrade") is True
        # The current bundle's evidence-writing gate-runner is restored.
        assert gate_runner_path.read_bytes() == current_gate_runner

        # A normal gate run now writes evidence again and readiness recovers.
        # (A real content change is needed -- Cargo.toml/src/main.rs are
        # already committed from the earlier commit_fixture_change call, and
        # an empty commit would never reach the hook's evidence write.)
        (upgrade_target / "src/main.rs").write_text('fn main() { println!("post-upgrade"); }\n', encoding="utf-8")
        commit_fixture_change(upgrade_target, upgrade_fake_bin, message="test: post-upgrade commit")
        recovered_report = preflight(upgrade_target, expected=0, path_prefix=upgrade_fake_bin)
        assert recovered_report["ready"] is True and recovered_report["blockers"] == []
        evidence["upgrade_refreshes_gate_runner_and_recovers_evidence"] = True

        # -- CRITICAL (TOCTOU): execution must run from the immutable
        #    snapshot taken at validation time, never a re-glob of the
        #    mutable repo path. Reproduces the attack: an earlier check is
        #    made to block for a window; while it blocks, a background
        #    mutator swaps a LATER receipt-recorded check for one that
        #    touches a sentinel, then restores the original bytes before
        #    the run ends. If execution re-opened the repo path after
        #    validation, the sentinel would exist; with the fix, the
        #    snapshot copy taken before the check loop started runs
        #    unconditionally and the sentinel is never created.
        race_target, race_fake_bin = build_ready_rust_target(work, "toctou race target")
        commit_fixture_change(race_target, race_fake_bin)
        race_checks = race_target / "scripts/governance/checks.d"
        # hard-10-* sorts first in the glob the runner executes, so slowing
        # it down opens a deterministic window before hard-50-* (which
        # sorts later) is reached.
        slow_check = race_checks / "hard-10-repo-structure.sh"
        slow_check.write_text("#!/usr/bin/env sh\nsleep 2\nexit 0\n", encoding="utf-8")
        slow_check.chmod(0o755)
        race_receipt_path = race_target / ".factory/gate-install.json"
        race_receipt = json.loads(race_receipt_path.read_text(encoding="utf-8"))
        # Re-pin provenance for our own substituted (but receipt-consistent)
        # fixture content -- this is the test standing in for "a legitimate
        # install," not the attack; the attack is the unpinned mutation below.
        race_receipt["managed_files"]["scripts/governance/checks.d/hard-10-repo-structure.sh"] = {
            "disposition": "factory_owned", "mode": 0o755,
            "sha256": hashlib.sha256(slow_check.read_bytes()).hexdigest(),
        }
        race_receipt_path.write_text(json.dumps(race_receipt), encoding="utf-8")

        target_check = race_checks / "hard-50-lint.sh"
        original_target_bytes = target_check.read_bytes()
        sentinel = work / "toctou-sentinel-executed"

        def mutate_then_restore() -> None:
            # Land squarely inside the slow check's 2s window: swap the
            # later check for a malicious one, hold briefly, then restore
            # the verified bytes -- mirroring an attacker who wants the
            # substitution to go unnoticed by any post-run scope diff too.
            time.sleep(0.5)
            target_check.write_text(
                f"#!/usr/bin/env sh\ntouch -- {str(sentinel)!r}\nexit 0\n", encoding="utf-8")
            target_check.chmod(0o755)
            time.sleep(0.5)
            target_check.write_bytes(original_target_bytes)
            target_check.chmod(0o755)

        mutator = threading.Thread(target=mutate_then_restore)
        mutator.start()
        run(str(race_target / "scripts/governance/gate-runner"), "--pre-commit",
            cwd=race_target, path_prefix=race_fake_bin)
        mutator.join()
        assert not sentinel.exists(), (
            "TOCTOU: a receipt-recorded check swapped mid-run was executed -- "
            "execution re-opened the mutable repo path instead of the validated snapshot")
        evidence["toctou_execution_uses_verified_snapshot"] = True

        # -- Fix 2 regression: mode provenance must be umask-robust. Git
        #    tracks only the owner-exec bit; the remaining permission bits
        #    come from the checkout's umask and must never cause a false
        #    EXECUTION_SCOPE_INVALID, while an actual executable-bit change
        #    must still be caught. MANIFEST.json (non-executable, not
        #    subject to the separate X_OK invalid-check) isolates the mode
        #    comparison from the executability requirement.
        mode_target, mode_fake_bin = build_ready_rust_target(work, "mode provenance target")
        commit_fixture_change(mode_target, mode_fake_bin)
        assert preflight(mode_target, expected=0, path_prefix=mode_fake_bin)["ready"] is True
        mode_manifest = mode_target / ".factory/gate-bundle/MANIFEST.json"
        original_manifest_mode = mode_manifest.stat().st_mode & 0o777
        assert original_manifest_mode & 0o100 == 0, "fixture assumption: MANIFEST.json installs non-executable"

        # A non-exec permission bit differing only by umask (e.g. a
        # group-writable checkout) must still PASS provenance.
        mode_manifest.chmod(0o640)
        umask_drift_report = preflight(mode_target, expected=0, path_prefix=mode_fake_bin)
        assert umask_drift_report["ready"] is True and umask_drift_report["blockers"] == []
        umask_drift_target_side = run(str(mode_target / "scripts/governance/gate-runner"), "--preflight",
                                      cwd=mode_target)
        assert json.loads(umask_drift_target_side.stdout)["ready"] is True
        mode_manifest.chmod(original_manifest_mode)

        # An actual executable-bit change must still be detected.
        mode_manifest.chmod(0o755)
        execbit_report = preflight(mode_target, expected=1, path_prefix=mode_fake_bin)
        assert "EXECUTION_SCOPE_INVALID" in blocker_codes(execbit_report)
        execbit_target_side = run(str(mode_target / "scripts/governance/gate-runner"), "--preflight",
                                  cwd=mode_target, expected=1)
        assert "EXECUTION_SCOPE_INVALID" in blocker_codes(json.loads(execbit_target_side.stdout))
        mode_manifest.chmod(original_manifest_mode)
        evidence["umask_robust_mode_provenance"] = True

        # -- Fix 2 negative fixtures: setuid/setgid/sticky/group-write/
        #    world-write modes must all be REJECTED even though content and
        #    the git-tracked owner-exec bit still match the receipt exactly.
        #    Exercised on a checks.d/*.sh entry (the file that is actually
        #    snapshotted and executed), not just MANIFEST.json above, and
        #    through both --preflight and a real --pre-commit run (which
        #    must refuse before any check executes, never just report it).
        special_target, special_fake_bin = build_ready_rust_target(work, "mode special bits target")
        commit_fixture_change(special_target, special_fake_bin)
        assert preflight(special_target, expected=0, path_prefix=special_fake_bin)["ready"] is True
        special_check = special_target / "scripts/governance/checks.d/hard-50-lint.sh"
        original_special_mode = special_check.stat().st_mode & 0o777

        for bad_mode in (0o777, 0o4755, 0o2755, 0o6755, 0o666):
            special_check.chmod(bad_mode)
            bad_report = preflight(special_target, expected=1, path_prefix=special_fake_bin)
            assert "EXECUTION_SCOPE_INVALID" in blocker_codes(bad_report), (oct(bad_mode), bad_report)
            bad_target_side = run(str(special_target / "scripts/governance/gate-runner"), "--preflight",
                                  cwd=special_target, expected=1)
            assert "EXECUTION_SCOPE_INVALID" in blocker_codes(json.loads(bad_target_side.stdout)), oct(bad_mode)
            bad_run = run(str(special_target / "scripts/governance/gate-runner"), "--pre-commit",
                         cwd=special_target, expected=1, path_prefix=special_fake_bin)
            assert "execution check scope" in bad_run.stderr, (oct(bad_mode), bad_run.stderr)
            special_check.chmod(original_special_mode)

        # Sanity: umask-noise-only modes on the same (executable) file still
        # PASS -- mirrors the MANIFEST.json assertion above, now on the file
        # that actually executes, proving _mode_ok() does not over-reject.
        special_check.chmod(0o750)
        noise_report = preflight(special_target, expected=0, path_prefix=special_fake_bin)
        assert noise_report["ready"] is True and noise_report["blockers"] == []
        special_check.chmod(original_special_mode)
        evidence["special_and_group_write_mode_rejected"] = True

        # -- Fix 3 boundary test (b): a check whose SOURCE bytes at
        #    validation time do not match the receipt (a static content
        #    swap, no concurrency needed) must be refused before ANY check
        #    executes. This is distinct from the earlier
        #    injected_check_refused_before_execution case, which swaps in a
        #    brand-new manifest entry; this one tampers the content of an
        #    EXISTING receipt-recorded check.
        mismatch_target, mismatch_fake_bin = build_ready_rust_target(work, "boundary mismatch target")
        commit_fixture_change(mismatch_target, mismatch_fake_bin)
        assert preflight(mismatch_target, expected=0, path_prefix=mismatch_fake_bin)["ready"] is True
        mismatch_check = mismatch_target / "scripts/governance/checks.d/hard-50-lint.sh"
        original_mismatch_bytes = mismatch_check.read_bytes()
        mismatch_sentinel = work / "boundary-mismatch-sentinel-executed"
        mismatch_check.write_text(
            f"#!/usr/bin/env sh\ntouch -- {str(mismatch_sentinel)!r}\nexit 0\n", encoding="utf-8")
        mismatch_check.chmod(0o755)
        mismatch_run = run(str(mismatch_target / "scripts/governance/gate-runner"), "--pre-commit",
                           cwd=mismatch_target, expected=1, path_prefix=mismatch_fake_bin)
        assert not mismatch_sentinel.exists(), (
            "boundary test (b): a check whose SOURCE bytes did not match the "
            "receipt at validation time still executed")
        assert "execution check scope" in mismatch_run.stderr
        mismatch_check.write_bytes(original_mismatch_bytes)
        mismatch_check.chmod(0o755)
        evidence["boundary_mismatch_source_refused_before_execution"] = True

        # -- Fix 3 boundary test (a): deterministic proof that the snapshot,
        #    not the mutable repo path, is what gets executed -- the
        #    validate/copy boundary the snapshot-first construction closes.
        #    Rather than a thread + sleep race (kept above for the re-glob
        #    race), a synchronization hook (FACTORY_GATE_POST_SNAPSHOT_HOOK,
        #    a development/test-only seam gate-runner never enables itself)
        #    fires once the snapshot has been fully populated and validated
        #    but before its path is handed back for execution. The hook
        #    swaps the SOURCE check for a sentinel-writing payload and
        #    restores it, entirely synchronously, inside that one hook
        #    invocation -- no thread, no sleep. Because the snapshot copy
        #    already happened before the hook could run, there is no window
        #    in which the execution loop could observe the mutated source:
        #    this is deterministic by construction, not by timing.
        hook_target, hook_fake_bin = build_ready_rust_target(work, "boundary hook target")
        commit_fixture_change(hook_target, hook_fake_bin)
        assert preflight(hook_target, expected=0, path_prefix=hook_fake_bin)["ready"] is True
        hook_check = hook_target / "scripts/governance/checks.d/hard-50-lint.sh"
        hook_backup = work / "boundary-hook-original-check"
        hook_backup.write_bytes(hook_check.read_bytes())
        hook_sentinel = work / "boundary-hook-sentinel-executed"
        hook_script = work / "boundary-post-snapshot-hook.py"
        hook_script.write_text(
            "#!/usr/bin/env python3\n"
            "import os, shlex\n"
            "check = os.environ['FACTORY_GATE_BOUNDARY_CHECK']\n"
            "sentinel = os.environ['FACTORY_GATE_BOUNDARY_SENTINEL']\n"
            "backup = os.environ['FACTORY_GATE_BOUNDARY_BACKUP']\n"
            "with open(check, 'w', encoding='utf-8') as fh:\n"
            "    fh.write('#!/usr/bin/env sh\\ntouch -- ' + shlex.quote(sentinel) + '\\nexit 0\\n')\n"
            "os.chmod(check, 0o755)\n"
            "with open(backup, 'rb') as fh:\n"
            "    data = fh.read()\n"
            "with open(check, 'wb') as fh:\n"
            "    fh.write(data)\n"
            "os.chmod(check, 0o755)\n",
            encoding="utf-8")
        hook_script.chmod(0o755)
        hook_env = {
            "FACTORY_GATE_POST_SNAPSHOT_HOOK": str(hook_script),
            "FACTORY_GATE_BOUNDARY_CHECK": str(hook_check),
            "FACTORY_GATE_BOUNDARY_SENTINEL": str(hook_sentinel),
            "FACTORY_GATE_BOUNDARY_BACKUP": str(hook_backup),
        }
        run(str(hook_target / "scripts/governance/gate-runner"), "--pre-commit",
            cwd=hook_target, path_prefix=hook_fake_bin, extra_env=hook_env)
        assert not hook_sentinel.exists(), (
            "boundary test (a): a post-snapshot mutation of the SOURCE check "
            "file was executed -- execution read the mutable repo path "
            "instead of the already-populated snapshot")
        assert hook_check.read_bytes() == hook_backup.read_bytes()
        recovered_after_hook = preflight(hook_target, expected=0, path_prefix=hook_fake_bin)
        assert recovered_after_hook["ready"] is True and recovered_after_hook["blockers"] == []
        evidence["boundary_snapshot_first_hook_proof"] = True

    assert all(evidence.values()), evidence
    print("AQ_QA_FACTORY_READINESS_FIXTURE=" + json.dumps(evidence, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
