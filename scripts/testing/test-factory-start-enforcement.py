#!/usr/bin/env python3
"""Focused FT-5 proof that enabled factory starts fail closed before dispatch."""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AQD = ROOT / "scripts/ai/aqd"
START_TEMPLATE = ROOT / "templates/agentic-workflow/.agent/commands/start-workflow.sh.tmpl"


def run(*command: str, cwd: Path | None = None, expected: int = 0,
        environment: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = {key: value for key, value in os.environ.items()
           if key not in {"GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
                          "GIT_ALTERNATE_OBJECT_DIRECTORIES"}}
    if environment:
        env.update(environment)
    result = subprocess.run(command, cwd=cwd, env=env, text=True, capture_output=True, check=False)
    if result.returncode != expected:
        raise AssertionError(f"unexpected exit {result.returncode}: {' '.join(command)}\n{result.stdout}\n{result.stderr}")
    return result


def fake_tools(directory: Path, *names: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for name in names:
        tool = directory / name
        tool.write_text("#!/usr/bin/env sh\nexit 0\n", encoding="utf-8")
        tool.chmod(0o755)


def ready_target(work: Path) -> tuple[Path, Path]:
    target = work / "ready start"
    (target / "src").mkdir(parents=True)
    run("git", "init", cwd=target)
    run("git", "symbolic-ref", "HEAD", "refs/heads/factory-ready", cwd=target)
    run("git", "config", "user.name", "Fixture Author", cwd=target)
    run("git", "config", "user.email", "fixture@example.invalid", cwd=target)
    (target / "Cargo.toml").write_text('[package]\nname = "fixture"\n', encoding="utf-8")
    (target / "src/main.rs").write_text("fn main() {}\n", encoding="utf-8")
    tools = work / "ready tools"
    fake_tools(tools, "cargo", "gitleaks")
    env = {"PATH": str(tools) + os.pathsep + os.environ.get("PATH", "")}
    preview = run(str(AQD), "workflows", "retrofit", "--target", str(target), "--name", "ready start",
                  "--stack", "rust", cwd=ROOT, environment=env)
    digest = __import__("json").loads(preview.stdout)["preview_digest"]
    run(str(AQD), "workflows", "retrofit", "--target", str(target), "--name", "ready start",
        "--stack", "rust", "--confirm-retrofit", digest, cwd=ROOT, environment=env)
    run("git", "add", "Cargo.toml", "src/main.rs", cwd=target, environment=env)
    run("git", "commit", "-m", "test: ready start", cwd=target, environment=env)
    return target, tools


def write_start_fixture(target: Path, runner: str | None) -> Path:
    command = target / ".agent/commands/start-workflow.sh"
    command.parent.mkdir(parents=True)
    shutil.copy2(START_TEMPLATE, command)
    command.chmod(0o755)
    contract = target / ".agent/workflows/intent-contract.json"
    contract.parent.mkdir(parents=True, exist_ok=True)
    contract.write_text('{"user_intent":"fixture"}\n', encoding="utf-8")
    if runner is not None:
        gate = target / "scripts/governance/gate-runner"
        gate.parent.mkdir(parents=True, exist_ok=True)
        gate.write_text(runner, encoding="utf-8")
        gate.chmod(0o755)
    return command


def main() -> int:
    evidence = {"brownfield_blocked_before_write": False, "force_does_not_bypass": False,
                "ready_brownfield_progresses": False, "missing_runner_blocks_dispatch": False,
                "blocked_runner_blocks_dispatch": False, "ready_runner_dispatches": False}
    with tempfile.TemporaryDirectory(prefix="factory start fixture ") as temporary:
        work = Path(temporary)
        blocked = work / "blocked start"
        blocked.mkdir()
        run("git", "init", cwd=blocked)
        blocked_result = run(str(AQD), "workflows", "brownfield", "--target", str(blocked),
                             "--objective", "prove block", "--constraints", "none",
                             "--out-of-scope", "none", "--acceptance", "none", cwd=ROOT, expected=1)
        assert '"state": "BLOCKED"' in blocked_result.stdout
        assert not (blocked / ".agent").exists()
        evidence["brownfield_blocked_before_write"] = True

        forced_result = run(str(AQD), "workflows", "brownfield", "--target", str(blocked), "--force",
                            "--objective", "prove force block", "--constraints", "none",
                            "--out-of-scope", "none", "--acceptance", "none", cwd=ROOT, expected=1)
        assert '"state": "BLOCKED"' in forced_result.stdout
        assert not (blocked / ".agent").exists()
        evidence["force_does_not_bypass"] = True

        ready, tools = ready_target(work)
        ready_env = {"PATH": str(tools) + os.pathsep + os.environ.get("PATH", "")}
        run(str(AQD), "workflows", "brownfield", "--target", str(ready),
            "--objective", "ready progression", "--constraints", "none",
            "--out-of-scope", "none", "--acceptance", "none", cwd=ROOT, environment=ready_env)
        assert list((ready / ".agent/workflows").glob("brownfield-PDR-*.md"))
        evidence["ready_brownfield_progresses"] = True

        curl_bin = work / "transport tools"
        curl_bin.mkdir()
        log = work / "transport.log"
        curl = curl_bin / "curl"
        curl.write_text("#!/usr/bin/env sh\nprintf '%s\\n' \"$*\" >> \"$FACTORY_START_LOG\"\nprintf '{}\\n'\n", encoding="utf-8")
        curl.chmod(0o755)
        start_env = {"PATH": str(curl_bin) + os.pathsep + os.environ.get("PATH", ""),
                     "HYBRID_URL": "http://transport.invalid", "FACTORY_START_LOG": str(log)}

        missing = work / "missing runner"
        missing.mkdir()
        missing_start = write_start_fixture(missing, None)
        missing_result = run(str(missing_start), cwd=missing, expected=1, environment=start_env)
        assert "FACTORY_READINESS_RUNNER_MISSING" in missing_result.stderr
        assert not log.exists()
        evidence["missing_runner_blocks_dispatch"] = True

        blocked_runner = work / "blocked runner"
        blocked_runner.mkdir()
        blocked_start = write_start_fixture(
            blocked_runner, "#!/usr/bin/env sh\nprintf '%s\\n' '{\"state\":\"BLOCKED\"}'\nexit 1\n")
        blocked_start_result = run(str(blocked_start), cwd=blocked_runner, expected=1, environment=start_env)
        assert "FACTORY_READINESS_BLOCKED" in blocked_start_result.stderr
        assert not log.exists()
        evidence["blocked_runner_blocks_dispatch"] = True

        ready_runner = work / "ready runner"
        ready_runner.mkdir()
        ready_start = write_start_fixture(
            ready_runner, "#!/usr/bin/env sh\nprintf '%s\\n' '{\"state\":\"READY\"}'\nexit 0\n")
        run(str(ready_start), cwd=ready_runner, environment=start_env)
        calls = log.read_text(encoding="utf-8")
        assert "/workflow/plan" in calls and "/workflow/run/start" in calls and "/hints?" in calls
        evidence["ready_runner_dispatches"] = True

    assert all(evidence.values()), evidence
    print("AQ_QA_FACTORY_START_ENFORCEMENT=" + __import__("json").dumps(evidence, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
