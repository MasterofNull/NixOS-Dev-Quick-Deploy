#!/usr/bin/env python3
"""Targeted checks for shared skill registry sync helpers."""

import importlib.util
import json
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "ai" / "aq-sync-shared-skills.py"
SPEC = importlib.util.spec_from_file_location("aq_sync_shared_skills", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise SystemExit("ERROR: unable to load aq-sync-shared-skills module")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    report = MODULE.compare_registry(
        [
            {"slug": "alpha", "source_path": ".agent/skills/alpha/SKILL.md", "content": "# Alpha"},
            {"slug": "beta", "source_path": ".agent/skills/beta/SKILL.md", "content": "# Beta"},
            {"slug": "system_bootstrap", "source_path": ".agent/skills/system_bootstrap/SKILL.md", "content": "# System"},
        ],
        [
            {"slug": "alpha", "source_path": ".agent/skills/alpha/SKILL.md"},
            {"slug": "orphan", "source_path": ".agent/skills/orphan/SKILL.md"},
            {"slug": "system-bootstrap", "source_path": ".agent/skills/system_bootstrap/SKILL.md"},
        ],
    )
    assert_true(report["local_skill_count"] == 3, "expected local skill count")
    assert_true(report["approved_skill_count"] == 3, "expected approved skill count")
    assert_true(report["missing_in_aidb"] == ["beta"], "expected missing beta skill")
    assert_true(report["extra_in_aidb"] == ["orphan"], "expected orphan remote skill")
    assert_true(report["healthy"] is False, "expected unhealthy drift report")

    with tempfile.TemporaryDirectory() as tmp_dir:
        manifest_path = Path(tmp_dir) / "approved-skill-sources.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "skills": [
                        {
                            "slug": "learn",
                            "source_url": "https://example.invalid/learn/SKILL.md",
                            "source_path": "external/agentskill.sh/agentskill-sh/learn/SKILL.md",
                            "managed_by": "agentskill-sh",
                            "enabled": True,
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        external = MODULE.load_external_skill_records(manifest_path)
    assert_true(len(external) == 1, "expected one external skill manifest entry")
    assert_true(external[0]["slug"] == "learn", "expected learn external skill slug")
    assert_true(external[0]["managed_by"] == "agentskill-sh", "expected managed_by from manifest")
    print("PASS: shared skill sync detects local/AIDB registry drift")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
