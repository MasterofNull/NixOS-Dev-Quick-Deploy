#!/usr/bin/env python3
"""Regression coverage for locally selected CI contract checks.

Exercises the real focused runner against a disposable repository and uses
synthetic fixtures to keep the three hosted-contract failure modes local.
"""
from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from types import ModuleType
from typing import Protocol, cast

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "config" / "validation-check-registry.json"

EXPECTED_CHECKS = {
    "tier0d-gate-mutation": {
        "command": ["python3", "scripts/testing/test-tier0d-gate-mutation.py"],
        "trigger_paths": ["scripts/governance/tier0.d/", "scripts/testing/test-tier0d-gate-mutation.py"],
    },
    "aq-usage-logging": {
        "command": ["python3", "scripts/testing/test-aq-usage-logging.py"],
        "trigger_paths": ["scripts/ai/", "scripts/testing/test-aq-usage-logging.py"],
    },
    "plans-index": {
        "command": ["python3", "scripts/testing/test-plans-index.py"],
        "trigger_paths": [".agents/plans/", "scripts/ai/aq-plans-index", "scripts/testing/test-plans-index.py"],
    },
}


class Tier0MutationContract(Protocol):
    GATE_DIR: Path
    COVERED_ELSEWHERE: dict[str, str]

    def meta_check(self) -> list[str]: ...


class UsageLoggingContract(Protocol):
    AI: Path

    def main(self) -> int: ...


class PlansIndexContract(Protocol):
    PLANS_DIR: Path

    def _plan_record(self, plan_dir: Path) -> dict[str, object]: ...


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def load_module(name: str, path: Path) -> ModuleType:
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    if spec is None:
        raise AssertionError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def test_registry_contracts() -> None:
    entries = {entry["id"]: entry for entry in json.loads(REGISTRY.read_text())["checks"]}
    for check_id, expected in EXPECTED_CHECKS.items():
        check(check_id in entries, f"missing local registry check: {check_id}")
        for field, value in expected.items():
            check(entries[check_id][field] == value, f"{check_id}: wrong {field}")


def test_unowned_tier0_gate_is_rejected() -> None:
    module = cast(Tier0MutationContract, load_module(
        "tier0_mutation_contract", ROOT / "scripts/testing/test-tier0d-gate-mutation.py"))
    with tempfile.TemporaryDirectory() as tmp:
        fixture_gates = Path(tmp) / "tier0.d"
        shutil.copytree(module.GATE_DIR, fixture_gates)
        (fixture_gates / "check-synthetic-unowned.py").write_text("#!/usr/bin/env python3\n", encoding="utf-8")
        original_dir = module.GATE_DIR
        module.GATE_DIR = fixture_gates
        try:
            errors = module.meta_check()
            check(any("check-synthetic-unowned.py: no mutation test" in error for error in errors),
                  "an unowned synthetic gate was accepted")
            module.COVERED_ELSEWHERE["check-synthetic-unowned.py"] = (
                "scripts/testing/test-local-ci-contract-preflight.py")
            check(module.meta_check() == [], "a covered synthetic gate was rejected")
        finally:
            module.GATE_DIR = original_dir
            module.COVERED_ELSEWHERE.pop("check-synthetic-unowned.py", None)


def test_unhooked_aq_entrypoint_is_rejected() -> None:
    module = cast(UsageLoggingContract, load_module(
        "aq_usage_logging_contract", ROOT / "scripts/testing/test-aq-usage-logging.py"))
    with tempfile.TemporaryDirectory() as tmp:
        ai_dir = Path(tmp) / "scripts" / "ai"
        lib_dir = ai_dir / "lib"
        lib_dir.mkdir(parents=True)
        for name in ("aq-shim.sh", "aq_usage.py"):
            shutil.copy2(ROOT / "scripts" / "ai" / "lib" / name, lib_dir / name)
        shutil.copy2(ROOT / "scripts" / "ai" / "aq-capability-audit", ai_dir / "aq-capability-audit")
        for name, contents in {
            "aq-valid": '#!/usr/bin/env bash\n. "${BASH_SOURCE[0]%/*}/lib/aq-shim.sh" 2>/dev/null || true # aq-usage-hook\n',
            "aq-capability-index": '#!/usr/bin/env bash\n. "${BASH_SOURCE[0]%/*}/lib/aq-shim.sh" 2>/dev/null || true # aq-usage-hook\n',
            "aq-baseline": "#!/usr/bin/env bash\n",
        }.items():
            path = ai_dir / name
            path.write_text(contents, encoding="utf-8")
            path.chmod(0o755)
        original_ai = module.AI
        module.AI = ai_dir
        try:
            try:
                module.main()
            except AssertionError as error:
                check("aq-* entrypoints without the usage hook" in str(error),
                      f"unhooked aq-* fixture failed the wrong contract: {error}")
            else:
                raise AssertionError("an unhooked aq-* fixture was accepted")
            (ai_dir / "aq-baseline").write_text(
                '#!/usr/bin/env bash\n. "${BASH_SOURCE[0]%/*}/lib/aq-shim.sh" 2>/dev/null || true # aq-usage-hook\n',
                encoding="utf-8")
            check(module.main() == 0, "a hooked aq-* fixture was rejected")
        finally:
            module.AI = original_ai


def test_missing_plan_classification_is_visible() -> None:
    module = cast(PlansIndexContract, load_module(
        "plans_index_contract", ROOT / "scripts/ai/aq-plans-index"))
    with tempfile.TemporaryDirectory() as tmp:
        plan = Path(tmp) / "experience-capture"
        plan.mkdir()
        plans_dir = module.PLANS_DIR
        module.PLANS_DIR = plan.parent
        try:
            missing = module._plan_record(plan)
            check(missing["classification"] == "unclassified", "missing classification was accepted")
            check(missing["tracking_route"] == "classification_queue", "missing classification was not queued")
            (plan / ".plan-classification.json").write_text(json.dumps({
                "classification": "durable_plan", "tracking_route": "tracker.json",
                "evidence": "Synthetic plan fixture",}), encoding="utf-8")
            (plan / "tracker.json").write_text('{"items": []}', encoding="utf-8")
            valid = module._plan_record(plan)
            check(valid["classification"] == "durable_plan" and valid["classification_issue"] == "",
                  "valid classification fixture was rejected")
        finally:
            module.PLANS_DIR = plans_dir


def test_runner_selects_every_contract_check() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        fixture_env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        fixture_env.update({"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"})
        git = ["git", "-c", "core.hooksPath=/dev/null", "-c", "commit.gpgSign=false"]
        (repo / "scripts/governance/lib").mkdir(parents=True)
        shutil.copy2(ROOT / "scripts/governance/run-focused-ci-checks.sh",
                     repo / "scripts/governance/run-focused-ci-checks.sh")
        shutil.copy2(ROOT / "scripts/governance/lib/clean_git_env.py",
                     repo / "scripts/governance/lib/clean_git_env.py")
        checks = [{"id": check_id, "description": check_id,
                   "trigger_paths": value["trigger_paths"],
                   "command": [sys.executable, "-c", "pass"], "enabled": True}
                  for check_id, value in EXPECTED_CHECKS.items()]
        registry = repo / "registry.json"
        registry.write_text(json.dumps({"checks": checks}), encoding="utf-8")
        for path in ("scripts/governance/tier0.d/check-synthetic.py", "scripts/ai/aq-baseline",
                     ".agents/plans/experience-capture/.plan-classification.json"):
            target = repo / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("fixture\n", encoding="utf-8")
        subprocess.run([*git, "init", "-q", str(repo)], check=True, env=fixture_env)
        subprocess.run([*git, "-C", str(repo), "add", "."], check=True, env=fixture_env)
        subprocess.run([*git, "-C", str(repo), "-c", "user.email=test@example.invalid",
                        "-c", "user.name=Test", "commit", "-qm", "fixture"], check=True,
                       env=fixture_env)
        for path in ("scripts/governance/tier0.d/check-synthetic.py", "scripts/ai/aq-baseline",
                     ".agents/plans/experience-capture/.plan-classification.json"):
            (repo / path).write_text("changed fixture\n", encoding="utf-8")
        subprocess.run([*git, "-C", str(repo), "add", "."], check=True, env=fixture_env)
        report = repo / "report.json"
        env = fixture_env | {"REGISTRY": str(registry), "FOCUSED_CI_JSON": str(report)}
        result = subprocess.run(["bash", "scripts/governance/run-focused-ci-checks.sh", "--pre-commit"],
                                cwd=repo, env=env, text=True, capture_output=True)
        check(result.returncode == 0, result.stdout + result.stderr)
        selected = {entry["check_id"] for entry in json.loads(report.read_text())["checks"]}
        check(selected == set(EXPECTED_CHECKS), f"runner selected {sorted(selected)}")


def main() -> int:
    for test in (test_registry_contracts, test_unowned_tier0_gate_is_rejected,
                 test_unhooked_aq_entrypoint_is_rejected, test_missing_plan_classification_is_visible,
                 test_runner_selects_every_contract_check):
        test()
    print("PASS: local CI contract preflight regression")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
