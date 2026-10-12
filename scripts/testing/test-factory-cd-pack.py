#!/usr/bin/env python3
"""Focused ECC P2 proof: separately approval-gated CD pack on factory gate bundle.

Verifies:
- Greenfield: workflow rendered with 40-hex pinned action SHAs, environment binding,
  concurrency serialization (cancel-in-progress: false), contents: read least-privilege,
  artifact digest verification, pre-deploy gate runner, and on-failure rollback plan.
- Two-axis verdict: LOCAL_READY / UNVERIFIED_REMOTE. Remote claims never promote.
- Violation blocking: unpinned actions, pull_request triggers, write-all permissions,
  cancel-in-progress: true, missing environment, and missing rollback steps block local verdict.
- Collision & Brownfield: existing foreign workflows preserved byte-for-byte;
  foreign violations preserved without clobbering; project-owned workflows respected.
- Health summary: bounded projection for dashboard / QA.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUNDLE = ROOT / "templates/factory-gate-bundle"
sys.path.insert(0, str(ROOT / "scripts/ai/lib"))
import factory_gate_install as fgi  # noqa: E402

spec = importlib.util.spec_from_file_location("cd_policy", BUNDLE / "ci/cd_policy.py")
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)

ENV = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
WORKFLOW = Path(".github/workflows/factory-cd.yml")
FOREIGN_CD = "name: existing-deploy\non: [workflow_dispatch]\njobs:\n  d:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v3\n"


def git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, env=ENV, check=True, capture_output=True, text=True)


def rules(text: str) -> set[str]:
    return {f["rule"] for f in policy.audit_text(text) if f["severity"] == "violation"}


def main() -> int:
    ev: dict[str, bool] = {}
    template = (BUNDLE / "ci/factory-cd.yml.tmpl").read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory(prefix="factory cd fixture ") as tmp:
        work = Path(tmp)

        # 1. Greenfield: installed workflow is rendered, pinned by immutable SHA, least privilege,
        # has environment approval binding, serialized concurrency, artifact verification, and rollback.
        green = work / "green"
        green.mkdir()
        git(green, "init", "-q")
        done = fgi.install(green, BUNDLE, "generic", "cd fixture")
        assert done["installation"]["state"] == "INSTALLED", done
        text = (green / WORKFLOW).read_text(encoding="utf-8")

        assert "{{" not in re.sub(r"\$\{\{.*?\}\}", "", text), "unrendered placeholder"
        assert "scripts/governance/gate-runner --pre-commit" in text
        uses = re.findall(r"uses:\s*(\S+)", text)
        assert uses and all(re.fullmatch(r"[\w./-]+@[0-9a-f]{40}", u) for u in uses), uses
        ev["greenfield_pins_immutable_sha"] = True

        assert re.search(r"^permissions:\n  contents: read\n", text, re.M)
        assert not re.search(r":\s*write\b|write-all", text)
        ev["permissions_least_privilege"] = True

        assert "environment:" in text and "name:" in text
        ev["environment_protection_binding"] = True

        assert "cancel-in-progress: false" in text
        ev["concurrency_serialization"] = True

        assert "inputs.artifact_digest" in text or "ci-evidence/SHA256SUMS" in text
        ev["artifact_digest_verification"] = True

        assert "failure()" in text and "rollback" in text.lower()
        ev["rollback_step_configured"] = True

        report = policy.check(green)
        assert report["verdict"] == "LOCAL_READY" and report["remote"] == "UNVERIFIED_REMOTE", report
        ev["greenfield_local_ready"] = True

        assert (green / ".factory/gate-bundle/ci/cd_policy.py").is_file()
        ev["workflow_references_installed_files"] = True

        # CLI exit semantics.
        cli = subprocess.run(
            [sys.executable, str(green / ".factory/gate-bundle/ci/cd_policy.py"), "check", str(green)],
            capture_output=True,
            text=True,
            env=ENV,
        )
        assert cli.returncode == 0 and "LOCAL_READY / UNVERIFIED_REMOTE" in cli.stdout, cli.stdout
        ev["cli_exit_clean"] = True

        # 2. Remote claims never promote remote axis without evidence.
        (green / ".factory").mkdir(exist_ok=True)
        (green / ".factory/cd-remote-evidence.json").write_text(json.dumps({"status": "PASS"}), encoding="utf-8")
        again = policy.check(green)
        assert again["remote"] == "UNVERIFIED_REMOTE" and "PASS" not in again["display"], again
        ev["verdict_unverified_remote_without_evidence"] = True

        # 3. Tampering with action pin is detected.
        tampered = text.replace("fbc6f3992d24b796d5a048ff273f7fcc4a7b6c09", "v5", 1)
        (green / WORKFLOW).write_text(tampered, encoding="utf-8")
        assert policy.check(green)["verdict"] == "LOCAL_BLOCKED"
        ev["tag_pin_blocks_local_verdict"] = True

        # Restore green workflow for further tests.
        (green / WORKFLOW).write_text(text, encoding="utf-8")

        # 4. Violation rule coverage.
        assert "pull_request" not in template
        assert "pull_request_target" not in template
        assert "persist-credentials: false" in template

        pr_violations = rules("on: pull_request\npermissions:\n  contents: read\nenvironment: prod\nconcurrency:\n  group: cd\n  cancel-in-progress: false\njobs:\n  d:\n    steps:\n      - run: rollback\n      - run: sha256sum\n")
        assert "untrusted-pr-trigger" in pr_violations, pr_violations

        pr_target_violations = rules("on: pull_request_target\npermissions:\n  contents: read\nenvironment: prod\nconcurrency:\n  group: cd\n  cancel-in-progress: false\njobs:\n  d:\n    steps:\n      - run: rollback\n      - run: sha256sum\n")
        assert "pull-request-target" in pr_target_violations, pr_target_violations

        cancel_true_violations = rules("on: workflow_dispatch\npermissions:\n  contents: read\nenvironment: prod\nconcurrency:\n  group: cd\n  cancel-in-progress: true\njobs:\n  d:\n    steps:\n      - run: rollback\n      - run: sha256sum\n")
        assert "cancel-in-progress-true" in cancel_true_violations, cancel_true_violations

        no_env_violations = rules("on: workflow_dispatch\npermissions:\n  contents: read\nconcurrency:\n  group: cd\n  cancel-in-progress: false\njobs:\n  d:\n    steps:\n      - run: rollback\n      - run: sha256sum\n")
        assert "missing-environment" in no_env_violations, no_env_violations

        no_rollback_violations = rules("on: workflow_dispatch\npermissions:\n  contents: read\nenvironment: prod\nconcurrency:\n  group: cd\n  cancel-in-progress: false\njobs:\n  d:\n    steps:\n      - run: sha256sum\n")
        assert "missing-rollback" in no_rollback_violations, no_rollback_violations

        no_artifact_violations = rules("on: workflow_dispatch\npermissions:\n  contents: read\nenvironment: prod\nconcurrency:\n  group: cd\n  cancel-in-progress: false\njobs:\n  d:\n    steps:\n      - run: rollback\n")
        assert "missing-artifact-verification" in no_artifact_violations, no_artifact_violations

        ev["violation_rules_covered"] = True

        # 5. Greenfield collision: existing workflow at the CD path is never overwritten.
        collide = work / "collide"
        (collide / ".github/workflows").mkdir(parents=True)
        git(collide, "init", "-q")
        (collide / WORKFLOW).write_text(FOREIGN_CD, encoding="utf-8")
        blocked = fgi.preview(collide, BUNDLE, "generic", "cd fixture")
        assert not blocked["safe_to_install"] and str(WORKFLOW) in blocked["collisions"], blocked["collisions"]
        assert (collide / WORKFLOW).read_text(encoding="utf-8") == FOREIGN_CD
        ev["greenfield_collision_refused"] = True

        # 6. Brownfield: existing foreign workflows preserved byte-for-byte.
        brown = work / "brown"
        (brown / ".github/workflows").mkdir(parents=True)
        git(brown, "init", "-q")
        git(brown, "config", "user.name", "Fixture")
        git(brown, "config", "user.email", "fixture@example.invalid")
        (brown / ".github/workflows/custom-cd.yml").write_text(FOREIGN_CD, encoding="utf-8")
        (brown / "README.md").write_text("existing\n", encoding="utf-8")
        pre = fgi.retrofit_preview(brown, BUNDLE, "generic", "cd fixture")
        assert pre["safe_to_install"], pre["blocker"]
        assert str(WORKFLOW) in pre["writes"] and not (brown / WORKFLOW).exists()
        installed = fgi.retrofit_install(brown, BUNDLE, "generic", "cd fixture", pre["preview_digest"])
        assert installed["installation"]["state"] == "INSTALLED", installed
        assert (brown / ".github/workflows/custom-cd.yml").read_text(encoding="utf-8") == FOREIGN_CD
        assert policy.check(brown)["verdict"] == "LOCAL_READY"
        b = policy.check(brown)
        assert b["foreign_preserved"]
        ev["brownfield_preserved_and_pack_added"] = True

        # 7. Project-owned file at the pack path: preserved, not evaluated as the pack.
        own = work / "own"
        (own / ".github/workflows").mkdir(parents=True)
        git(own, "init", "-q")
        git(own, "config", "user.name", "Fixture")
        git(own, "config", "user.email", "fixture@example.invalid")
        (own / WORKFLOW).write_text(FOREIGN_CD, encoding="utf-8")
        pre2 = fgi.retrofit_preview(own, BUNDLE, "generic", "cd fixture")
        assert pre2["safe_to_install"] and any(p["path"] == str(WORKFLOW) for p in pre2["preserved"]), pre2
        fgi.retrofit_install(own, BUNDLE, "generic", "cd fixture", pre2["preview_digest"])
        assert (own / WORKFLOW).read_text(encoding="utf-8") == FOREIGN_CD
        assert policy.check(own)["verdict"] == "NOT_INSTALLED"
        ev["brownfield_collision_preserved"] = True

        # 8. Empty repo with nothing installed.
        empty = work / "empty"
        empty.mkdir()
        assert policy.check(empty)["verdict"] == "NOT_INSTALLED"

    # 9. Health summary projection.
    summary = policy.health_summary(ROOT)
    assert summary["available"] and summary["verdict"] == "LOCAL_READY" and summary["remote"] == "UNVERIFIED_REMOTE", summary
    assert summary["environment_configured"] and summary["rollback_configured"]
    ev["health_summary_projection"] = True

    assert all(ev.values()), ev
    print("AQ_QA_FACTORY_CD_PACK_FIXTURE=" + json.dumps(ev, sort_keys=True, separators=(",", ":")))
    print("PASS: factory CD pack")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
