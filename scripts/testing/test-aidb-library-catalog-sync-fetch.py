#!/usr/bin/env python3
"""Regression coverage for bounded, truthful catalog fetch failures."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import time


ROOT = Path(__file__).resolve().parents[2]
SYNC = ROOT / "scripts" / "data" / "sync-aidb-library-catalog.sh"


def write_executable(path: Path, content: str) -> None:
    path.write_text(content)
    path.chmod(0o755)


def make_fixture(temp_dir: Path) -> tuple[dict[str, str], Path, Path]:
    fake_bin = temp_dir / "bin"
    fake_bin.mkdir()
    curl_log = temp_dir / "curl.log"
    mcp_state = temp_dir / "mcp-attempts"
    skill_state = temp_dir / "skill-attempts"
    timeout_state = temp_dir / "timeout-attempts"
    skill_lister = temp_dir / "list-skills.py"
    key_file = temp_dir / "aidb-api-key"
    key_file.write_text("test-key\n")

    write_executable(
        fake_bin / "curl",
        """#!/bin/sh
printf '%s\\n' \"$*\" >> \"$FAKE_CURL_LOG\"
case \"$*\" in
  *'/health'*) exit 0 ;;
  *'registry.test/catalog'*)
    count=0
    [ -f \"$FAKE_MCP_STATE\" ] && count=$(cat \"$FAKE_MCP_STATE\")
    count=$((count + 1))
    printf '%s' \"$count\" > \"$FAKE_MCP_STATE\"
    if [ \"$FAKE_MCP_MODE\" = permanent ] || [ \"$count\" -lt 2 ]; then
      exit 6
    fi
    printf '{\"servers\": []}\\n'
    exit 0 ;;
esac
exit 0
""",
    )
    write_executable(fake_bin / "jq", "#!/bin/sh\nexit 0\n")
    write_executable(fake_bin / "sleep", "#!/bin/sh\nexit 0\n")
    write_executable(
        fake_bin / "timeout",
        """#!/bin/sh
count=0
[ -f "$FAKE_TIMEOUT_STATE" ] && count=$(cat "$FAKE_TIMEOUT_STATE")
count=$((count + 1))
printf '%s' "$count" > "$FAKE_TIMEOUT_STATE"
printf '%s\\n' "$*" >> "$FAKE_TIMEOUT_LOG"
[ "$FAKE_SKILL_MODE" = timeout ] && exit 124
[ "$1" = --foreground ] && shift
case "$1" in *s) shift ;; esac
exec "$@"
""",
    )
    skill_lister.write_text(
        """import os
from pathlib import Path
import sys

state = Path(os.environ[\"FAKE_SKILL_STATE\"])
count = int(state.read_text()) if state.exists() else 0
state.write_text(str(count + 1))
if os.environ[\"FAKE_SKILL_MODE\"] == \"permanent\" or count == 0:
    sys.exit(1)
print(\"[]\")
"""
    )

    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{fake_bin}:{env['PATH']}",
            "AIDB_API_KEY_FILE": str(key_file),
            "MCP_REGISTRY_URL": "https://registry.test/catalog",
            "SKILL_LISTER": str(skill_lister),
            "FAKE_CURL_LOG": str(curl_log),
            "FAKE_MCP_STATE": str(mcp_state),
            "FAKE_SKILL_STATE": str(skill_state),
            "FAKE_TIMEOUT_STATE": str(timeout_state),
            "FAKE_TIMEOUT_LOG": str(temp_dir / "timeout.log"),
        }
    )
    return env, curl_log, mcp_state


def run_sync(env: dict[str, str], option: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(SYNC), option],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=5,
    )


def assert_no_import(curl_log: Path) -> None:
    calls = curl_log.read_text() if curl_log.exists() else ""
    assert "-X POST" not in calls, f"fetch failure reached import: {calls}"


def test_mcp_transient_retry_succeeds() -> None:
    with tempfile.TemporaryDirectory() as raw_temp:
        env, curl_log, mcp_state = make_fixture(Path(raw_temp))
        env["FAKE_MCP_MODE"] = "transient"
        result = run_sync(env, "--sync-mcp-only")
        assert result.returncode == 0, result.stderr
        assert mcp_state.read_text() == "2"
        assert "-fsS --connect-timeout 5 --max-time 30 https://registry.test/catalog" in curl_log.read_text()


def test_mcp_permanent_failure_is_nonzero_and_not_imported() -> None:
    with tempfile.TemporaryDirectory() as raw_temp:
        env, curl_log, mcp_state = make_fixture(Path(raw_temp))
        env["FAKE_MCP_MODE"] = "permanent"
        result = run_sync(env, "--sync-mcp-only")
        assert result.returncode != 0
        assert mcp_state.read_text() == "3"
        assert "refusing catalog import" in result.stderr
        assert_no_import(curl_log)


def test_skills_transient_retry_succeeds() -> None:
    with tempfile.TemporaryDirectory() as raw_temp:
        env, _, _ = make_fixture(Path(raw_temp))
        env["FAKE_SKILL_MODE"] = "transient"
        result = run_sync(env, "--sync-skills-only")
        assert result.returncode == 0, result.stderr
        assert Path(env["FAKE_SKILL_STATE"]).read_text() == "2"
        timeout_calls = Path(env["FAKE_TIMEOUT_LOG"]).read_text().splitlines()
        assert timeout_calls == [
            f"--foreground 30s python {env['SKILL_LISTER']} --format json",
            f"--foreground 30s python {env['SKILL_LISTER']} --format json",
        ]


def test_skills_permanent_failure_is_nonzero_and_not_imported() -> None:
    with tempfile.TemporaryDirectory() as raw_temp:
        env, curl_log, _ = make_fixture(Path(raw_temp))
        env["FAKE_SKILL_MODE"] = "permanent"
        result = run_sync(env, "--sync-skills-only")
        assert result.returncode != 0
        assert Path(env["FAKE_SKILL_STATE"]).read_text() == "3"
        assert "refusing catalog import" in result.stderr
        assert_no_import(curl_log)


def test_skills_timeout_is_nonzero_and_not_imported_before_deadline() -> None:
    with tempfile.TemporaryDirectory() as raw_temp:
        env, curl_log, _ = make_fixture(Path(raw_temp))
        env["FAKE_SKILL_MODE"] = "timeout"
        started = time.monotonic()
        result = run_sync(env, "--sync-skills-only")
        elapsed = time.monotonic() - started
        assert result.returncode != 0
        assert Path(env["FAKE_TIMEOUT_STATE"]).read_text() == "3"
        assert "refusing catalog import" in result.stderr
        assert elapsed < 5, f"timeout retry subprocess exceeded test deadline: {elapsed:.2f}s"
        assert_no_import(curl_log)


def main() -> None:
    test_mcp_transient_retry_succeeds()
    test_mcp_permanent_failure_is_nonzero_and_not_imported()
    test_skills_transient_retry_succeeds()
    test_skills_permanent_failure_is_nonzero_and_not_imported()
    test_skills_timeout_is_nonzero_and_not_imported_before_deadline()
    print("aidb library catalog fetch regression tests passed")


if __name__ == "__main__":
    main()
