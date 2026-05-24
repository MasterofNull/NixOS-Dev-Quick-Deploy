#!/usr/bin/env python3
"""Contract tests for bounded aq-integrity-scan behavior."""

import importlib.util
import json
import subprocess
import tempfile
from importlib.machinery import SourceFileLoader
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCANNER_PATH = REPO_ROOT / "scripts" / "ai" / "aq-integrity-scan"


def load_scanner():
    loader = SourceFileLoader("aq_integrity_scan_under_test", str(SCANNER_PATH))
    spec = importlib.util.spec_from_loader("aq_integrity_scan_under_test", loader)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    module = load_scanner()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / ".agent").mkdir()
        (root / "scripts" / "ai").mkdir(parents=True)
        (root / "ai-stack" / "mcp-servers" / "hybrid-coordinator" / "feature").mkdir(parents=True)
        (root / "ai-stack" / "tests").mkdir(parents=True)

        (root / ".agent" / "README.md").write_text("Use `aq-existing` and `aq-missing`.", encoding="utf-8")
        (root / "scripts" / "ai" / "aq-existing").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
        handler = root / "ai-stack" / "mcp-servers" / "hybrid-coordinator" / "feature" / "example_handlers.py"
        handler.write_text("def register_routes(app):\n    return app\n", encoding="utf-8")
        wired = root / "ai-stack" / "mcp-servers" / "hybrid-coordinator" / "http_server_impl.py"
        wired.write_text("# intentionally empty wiring surface\n", encoding="utf-8")
        for name in ("router.py", "server.py"):
            (root / "ai-stack" / "mcp-servers" / "hybrid-coordinator" / name).write_text("", encoding="utf-8")
        ext = root / "ai-stack" / "mcp-servers" / "hybrid-coordinator" / "extensions"
        ext.mkdir()
        (ext / "mcp_handlers.py").write_text("", encoding="utf-8")
        (root / "ai-stack" / "tests" / "test_not_dead_code.py").write_text("def test_example():\n    pass\n", encoding="utf-8")
        (root / "ai-stack" / "production_orphan.py").write_text("VALUE = 1\n", encoding="utf-8")
        (root / "ai-stack" / "known_orphan.py").write_text("VALUE = 2\n", encoding="utf-8")
        baseline = root / "config" / "aq-integrity-logical-orphans.json"
        baseline.parent.mkdir()
        baseline.write_text(
            json.dumps(
                {
                    "version": 1,
                    "entries": [
                        {
                            "path": "ai-stack/known_orphan.py",
                            "module": "known_orphan",
                            "classification": "library_candidate",
                            "owner": "test",
                            "action": "classify",
                            "rationale": "fixture baseline",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        module.REPO_ROOT = root
        module.AI_STACK = root / "ai-stack"
        module.SCRIPTS_AI = root / "scripts" / "ai"
        module.DOCS_DIR = root / ".agent"
        module.DEFAULT_LOGICAL_BASELINE = baseline

        scanner = module.IntegrityScanner(timeout_seconds=2, max_files=100, include_logical=True, logical_baseline=baseline)
        result = scanner.run()
        assert_true(result["meta"]["bounded"] is True, "scanner should report bounded mode")
        assert_true(result["meta"]["finding_counts"]["doc_orphans"] == 1, "expected one missing documented command")
        assert_true(result["findings"]["doc_orphans"][0]["command"] == "aq-missing", "wrong doc orphan")
        assert_true(result["meta"]["finding_counts"]["registration_gaps"] == 1, "expected one unwired handler module")
        logical_modules = [item["module"] for item in result["findings"]["logical_orphans"]]
        assert_true("production_orphan" in logical_modules, "logical scan should keep production candidates")
        assert_true("test_not_dead_code" not in logical_modules, "logical orphan scan should ignore tests")
        first_logical = result["findings"]["logical_orphans"][0]
        assert_true("path" in first_logical and "classification" in first_logical, "logical findings need path and classification")
        new_paths = [item["path"] for item in result["findings"]["new_logical_orphans"]]
        assert_true("ai-stack/production_orphan.py" in new_paths, "unbaselined logical orphan should be new")
        assert_true("ai-stack/known_orphan.py" not in new_paths, "baselined logical orphan should not be new")
        assert_true(result["meta"]["logical_baseline_entries"] == 1, "expected baseline entry accounting")
        assert_true(result["meta"]["logical_files_ignored"] >= 1, "expected ignored logical file accounting")
        assert_true("elapsed_seconds" in result["meta"], "scanner should report elapsed time")

    proc = subprocess.run(
        [str(SCANNER_PATH), "--json", "--skip-logical", "--timeout-seconds", "5", "--max-files", "4000"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
    )
    payload = json.loads(proc.stdout)
    assert_true("meta" in payload and "findings" in payload, "json output missing required keys")
    assert_true(payload["meta"]["bounded"] is True, "json output should identify bounded scanner")
    assert_true(payload["meta"]["elapsed_seconds"] <= 10, "scanner contract should complete promptly")

    print("PASS: aq-integrity-scan bounded JSON contract validated")


if __name__ == "__main__":
    main()
