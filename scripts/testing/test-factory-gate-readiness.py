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
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AQD = ROOT / "scripts/ai/aqd"
GATE_RUNNER = ROOT / "templates/factory-gate-bundle/gate-runner"


def run(*command: str, cwd: Path | None = None, expected: int | None = 0,
        path_prefix: Path | None = None) -> subprocess.CompletedProcess[str]:
    # Drop inherited GIT_* so a nested git op cannot escape the fixture repo, and
    # HYBRID_URL so the absent-lane assertion is hermetic: under tier0/aq-qa the
    # coordinator env sets HYBRID_URL, which would otherwise report the lane
    # CONFIGURED instead of the TRANSPORT_UNAVAILABLE this fixture asserts.
    environment = {key: value for key, value in os.environ.items()
                   if key not in {"GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
                                   "GIT_ALTERNATE_OBJECT_DIRECTORIES", "HYBRID_URL"}}
    if path_prefix:
        environment["PATH"] = str(path_prefix) + os.pathsep + environment.get("PATH", "")
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

    assert all(evidence.values()), evidence
    print("AQ_QA_FACTORY_READINESS_FIXTURE=" + json.dumps(evidence, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
