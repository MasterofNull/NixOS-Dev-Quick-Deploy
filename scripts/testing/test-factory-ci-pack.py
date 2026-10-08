#!/usr/bin/env python3
"""Focused P0-E proof: portable GitHub CI pack (greenfield, brownfield, collision, untrusted PR)."""
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

spec = importlib.util.spec_from_file_location("ci_policy", BUNDLE / "ci/ci_policy.py")
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)

ENV = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
WORKFLOW = Path(".github/workflows/factory-gate.yml")
FOREIGN = "name: existing-ci\non: [push]\njobs:\n  t:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/cache@v3\n"


def git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, env=ENV, check=True, capture_output=True, text=True)


def rules(text: str) -> set[str]:
    return {f["rule"] for f in policy.audit_text(text) if f["severity"] == "violation"}


def main() -> int:
    ev: dict[str, bool] = {}
    template = (BUNDLE / "ci/factory-gate.yml.tmpl").read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory(prefix="factory ci fixture ") as tmp:
        work = Path(tmp)

        # Greenfield: installed workflow is rendered, pinned by immutable SHA, least privilege.
        green = work / "green"
        green.mkdir()
        git(green, "init", "-q")
        done = fgi.install(green, BUNDLE, "generic", "ci fixture")
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
        report = policy.check(green)
        assert report["verdict"] == "LOCAL_READY" and report["remote"] == "UNVERIFIED_REMOTE", report
        ev["greenfield_local_ready"] = True
        # Self-test and gate paths referenced by the workflow must exist after install.
        assert (green / ".factory/gate-bundle/ci/ci_policy.py").is_file() and (green / ".factory/gate-bundle/self-test.sh").is_file()
        assert (green / "scripts/governance/gate-runner").is_file()
        ev["workflow_references_installed_files"] = True
        # CLI exit semantics.
        cli = subprocess.run([sys.executable, str(green / ".factory/gate-bundle/ci/ci_policy.py"), "check", str(green)],
                             capture_output=True, text=True, env=ENV)
        assert cli.returncode == 0 and "LOCAL_READY / UNVERIFIED_REMOTE" in cli.stdout, cli.stdout

        # Remote claims never promote the remote axis (no network, no PASS).
        (green / ".factory").mkdir(exist_ok=True)
        (green / ".factory/ci-remote-evidence.json").write_text(json.dumps({"status": "PASS"}), encoding="utf-8")
        again = policy.check(green)
        assert again["remote"] == "UNVERIFIED_REMOTE" and "PASS" not in again["display"], again
        ev["verdict_unverified_remote_without_evidence"] = True

        # Tampering with the installed workflow is detected.
        tampered = text.replace("fbc6f3992d24b796d5a048ff273f7fcc4a7b6c09", "v5", 1)
        (green / WORKFLOW).write_text(tampered, encoding="utf-8")
        assert policy.check(green)["verdict"] == "LOCAL_BLOCKED"
        ev["tag_pin_blocks_local_verdict"] = True

        # Untrusted PR / missing secret: template never uses pull_request_target or non-default secrets.
        assert "pull_request_target" not in template and not re.findall(r"secrets\.(?!GITHUB_TOKEN)", template)
        assert "persist-credentials: false" in template
        assert rules("on: pull_request_target\npermissions:\n  contents: read\n") == {"pull-request-target"}
        assert rules("on: push\n") == {"missing-permissions"}
        assert rules("on: push\npermissions: write-all\n") >= {"permissions-write-all"}
        assert rules("on: push\npermissions:\n  contents: write\njobs:\n  a:\n    steps:\n      - uses: x/y@v1\n") >= {"top-level-write", "unpinned-action"}
        assert rules("on: push\npermissions:\n  contents: read\njobs:\n  a:\n    steps:\n      - uses: docker://img:1\n") == {"unpinned-action"}
        review = [f for f in policy.audit_text("on: push\npermissions:\n  contents: read\nenv:\n  A: ${{ secrets.TOKEN_X }}\n")
                  if f["rule"] == "secret-reference"]
        assert review and review[0]["severity"] == "review"
        ev["untrusted_pr_and_secret_cases"] = True

        # Greenfield collision: existing workflow at the pack path is never overwritten.
        collide = work / "collide"
        (collide / ".github/workflows").mkdir(parents=True)
        git(collide, "init", "-q")
        (collide / WORKFLOW).write_text(FOREIGN, encoding="utf-8")
        blocked = fgi.preview(collide, BUNDLE, "generic", "ci fixture")
        assert not blocked["safe_to_install"] and str(WORKFLOW) in blocked["collisions"], blocked["collisions"]
        assert (collide / WORKFLOW).read_text(encoding="utf-8") == FOREIGN
        ev["greenfield_collision_refused"] = True

        # Brownfield: existing workflows are preserved byte-for-byte (merge, not clobber).
        brown = work / "brown"
        (brown / ".github/workflows").mkdir(parents=True)
        git(brown, "init", "-q")
        git(brown, "config", "user.name", "Fixture")
        git(brown, "config", "user.email", "fixture@example.invalid")
        (brown / ".github/workflows/ci.yml").write_text(FOREIGN, encoding="utf-8")
        (brown / "README.md").write_text("existing\n", encoding="utf-8")
        pre = fgi.retrofit_preview(brown, BUNDLE, "generic", "ci fixture")
        assert pre["safe_to_install"], pre["blocker"]
        assert str(WORKFLOW) in pre["writes"] and not (brown / WORKFLOW).exists()
        installed = fgi.retrofit_install(brown, BUNDLE, "generic", "ci fixture", pre["preview_digest"])
        assert installed["installation"]["state"] == "INSTALLED", installed
        assert (brown / ".github/workflows/ci.yml").read_text(encoding="utf-8") == FOREIGN
        assert policy.check(brown)["verdict"] == "LOCAL_READY"
        b = policy.check(brown)
        assert b["foreign_workflows"] == 1 and b["foreign_violations"] >= 1 and b["foreign_preserved"]
        ev["brownfield_preserved_and_pack_added"] = True

        # Brownfield with a project-owned file at the pack path: preserved, not evaluated as the pack.
        own = work / "own"
        (own / ".github/workflows").mkdir(parents=True)
        git(own, "init", "-q")
        git(own, "config", "user.name", "Fixture")
        git(own, "config", "user.email", "fixture@example.invalid")
        (own / WORKFLOW).write_text(FOREIGN, encoding="utf-8")
        pre2 = fgi.retrofit_preview(own, BUNDLE, "generic", "ci fixture")
        assert pre2["safe_to_install"] and any(p["path"] == str(WORKFLOW) for p in pre2["preserved"]), pre2
        fgi.retrofit_install(own, BUNDLE, "generic", "ci fixture", pre2["preview_digest"])
        assert (own / WORKFLOW).read_text(encoding="utf-8") == FOREIGN
        assert policy.check(own)["verdict"] == "NOT_INSTALLED"
        ev["brownfield_collision_preserved"] = True

        # Empty repo with nothing installed.
        empty = work / "empty"
        empty.mkdir()
        assert policy.check(empty)["verdict"] == "NOT_INSTALLED"

    summary = policy.health_summary(ROOT)
    assert summary["available"] and summary["verdict"] == "LOCAL_READY" and summary["remote"] == "UNVERIFIED_REMOTE", summary
    ev["health_summary_projection"] = True
    assert all(ev.values()), ev
    print("AQ_QA_FACTORY_CI_PACK_FIXTURE=" + json.dumps(ev, sort_keys=True, separators=(",", ":")))
    print("PASS: factory CI pack")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
