#!/usr/bin/env python3
"""Targeted checks for aq-report editor-state budget reporting."""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
from importlib.machinery import SourceFileLoader
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AQ_REPORT_PATH = ROOT / "scripts" / "ai" / "aq-report"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _write_vscodium_state(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    try:
        connection.execute("CREATE TABLE ItemTable (key TEXT PRIMARY KEY, value TEXT)")
        gemini_payload = {
            "workspaceChange": "x" * 120,
            "ideContext": "y" * 80,
        }
        qwen_payload = {
            "conversations": [
                {},
                {"messages": ["hello"], "title": "active"},
            ]
        }
        connection.execute(
            "INSERT INTO ItemTable(key, value) VALUES (?, ?)",
            ("google.geminicodeassist", json.dumps(gemini_payload)),
        )
        connection.execute(
            "INSERT INTO ItemTable(key, value) VALUES (?, ?)",
            ("qwenlm.qwen-code-vscode-ide-companion", json.dumps(qwen_payload)),
        )
        connection.commit()
    finally:
        connection.close()


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="aq-report-editor-state-") as tmpdir:
        root = Path(tmpdir)
        continue_dir = root / ".continue" / "sessions"
        continue_dir.mkdir(parents=True)
        (continue_dir / "small.json").write_text("{}", encoding="utf-8")
        (continue_dir / "large.json").write_text("z" * 300, encoding="utf-8")
        archive_dir = root / ".continue" / "sessions-backup-20260508-000000"
        archive_dir.mkdir(parents=True)
        (archive_dir / "archived.json").write_text("{}", encoding="utf-8")

        obsolete_path = root / ".vscode-oss" / "extensions" / ".obsolete"
        obsolete_path.parent.mkdir(parents=True, exist_ok=True)
        obsolete_path.write_text(json.dumps({"openai.chatgpt-0.5.80": True}), encoding="utf-8")

        vscodium_db = root / ".config" / "VSCodium" / "User" / "globalStorage" / "state.vscdb"
        _write_vscodium_state(vscodium_db)

        codex_dir = root / ".codex"
        codex_dir.mkdir(parents=True)
        (codex_dir / "state_5.sqlite.pre-vscodium-repair-20260508-000000").write_text("backup", encoding="utf-8")

        os.environ["AI_STRICT_ENV"] = "false"
        os.environ["AQ_PRIMARY_HOME"] = str(root)
        os.environ["AQ_CONTINUE_SESSIONS_DIR"] = str(continue_dir)
        os.environ["AQ_CONTINUE_ARCHIVE_ROOT"] = str(root / ".continue")
        os.environ["AQ_VSCODIUM_GLOBAL_STATE_DB"] = str(vscodium_db)
        os.environ["AQ_VSCODIUM_OBSOLETE_PATH"] = str(obsolete_path)
        os.environ["AQ_CODEX_STATE_DB"] = str(codex_dir / "state_5.sqlite")
        os.environ["AQ_EDITOR_CONTINUE_ACTIVE_BYTES_BUDGET"] = "128"
        os.environ["AQ_EDITOR_CONTINUE_SESSION_FILE_BYTES_BUDGET"] = "128"
        os.environ["AQ_EDITOR_GEMINI_STATE_BYTES_BUDGET"] = "512"
        os.environ["AQ_EDITOR_QWEN_STATE_BYTES_BUDGET"] = "512"
        aq_report = SourceFileLoader("aq_report_editor_state_budgets", str(AQ_REPORT_PATH)).load_module()

        budget = aq_report.editor_state_budget_health()
        assert_true(not budget.get("healthy"), "expected oversized editor state to fail the budget gate")
        failing_ids = {item.get("id") for item in budget.get("checks") or [] if item.get("status") == "FAIL"}
        assert_true("continue_hot_corpus" in failing_ids, "expected Continue hot corpus failure")
        assert_true("obsolete_ai_markers" in failing_ids, "expected stale obsolete marker failure")

        payload = json.loads(
            aq_report.format_json(
                "7d",
                {},
                {},
                {},
                {},
                {},
                {},
                {},
                [],
                [],
                [],
                {},
                {},
                {"available": True, "healthy": True, "total_checks": 6, "passed_n": 6, "failed_n": 0, "skipped_n": 0, "checks": [], "failure_categories": [], "state_budget": budget},
                {"available": False, "windows": {}},
                {"available": False, "windows": {}},
                {},
                {},
                {},
                {},
                {},
                {},
                {},
                {},
                {},
                {},
                [],
            )
        )
        state_budget = ((payload.get("continue_editor") or {}).get("state_budget") or {})
        assert_true(state_budget.get("failed_n") == budget.get("failed_n"), "expected state budget in aq-report JSON payload")

    print("PASS: aq-report surfaces editor-state budgets and failures")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
