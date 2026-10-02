#!/usr/bin/env python3
"""Verify Ralph optimizer handlers use configured repository cwd and fail closed."""

import asyncio
import ast
import hashlib
import json
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SERVER_PATH = ROOT / "ai-stack/mcp-servers/ralph-wiggum/server.py"


def load_handlers() -> SimpleNamespace:
    """Compile only the production handlers so tests need no service dependencies."""
    tree = ast.parse(SERVER_PATH.read_text(encoding="utf-8"))
    handlers = []
    for node in tree.body:
        if isinstance(node, ast.AsyncFunctionDef) and node.name in {
            "sync_prsi_queue", "execute_prsi_actions"
        }:
            node.decorator_list = []
            node.args.defaults = [ast.Constant(value=None) for _ in node.args.defaults]
            handlers.append(node)

    actions = []
    namespace = {
        "asyncio": __import__("asyncio"),
        "hashlib": hashlib,
        "json": json,
        "os": os,
        "datetime": datetime,
        "timezone": timezone,
        "PRSI_QUEUE_LOCK": __import__("asyncio").Lock(),
        "logger": SimpleNamespace(error=lambda *_args, **_kwargs: None),
    }

    def load_queue():
        return {"actions": [dict(action) for action in actions], "counts": {}}

    def save_queue(queue):
        actions[:] = queue.get("actions", [])

    def recompute_counts(queue):
        queue["counts"] = {"pending_approval": 0, "approved": 0, "executed": 0, "rejected": 0}
        for action in queue.get("actions", []):
            status = action.get("status", "pending_approval")
            if status in queue["counts"]:
                queue["counts"][status] += 1

    namespace.update({
        "_load_prsi_queue": load_queue,
        "_save_prsi_queue": save_queue,
        "_recompute_counts": recompute_counts,
    })
    module = ast.fix_missing_locations(ast.Module(body=handlers, type_ignores=[]))
    exec(compile(module, str(SERVER_PATH), "exec"), namespace)
    return SimpleNamespace(**namespace, actions=actions)


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def check_service_path() -> None:
    result = subprocess.run(
        [
            "nix", "eval", "--json",
            ".#nixosConfigurations.hyperd-ai-dev.config.systemd.services.ai-ralph-wiggum.path",
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )
    service_path = json.loads(result.stdout)
    check(
        any("python" in entry.lower() for entry in service_path),
        f"Ralph service PATH must include its Python runtime; got {service_path!r}",
    )


def test_atomic_write() -> None:
    """Extract and test _save_prsi_queue with a read-only file."""
    tree = ast.parse(SERVER_PATH.read_text(encoding="utf-8"))
    save_func = None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "_save_prsi_queue":
            save_func = node
            break

    check(save_func is not None, "_save_prsi_queue function not found in server.py")

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir)
        queue_file = temp_root / "prsi-queue.json"

        # Create initial file with read-only mode (simulating hyperd-owned file)
        queue_file.write_text(json.dumps({"actions": []}), encoding="utf-8")
        queue_file.chmod(0o444)

        namespace = {
            "asyncio": __import__("asyncio"),
            "datetime": datetime,
            "json": json,
            "os": os,
            "Path": Path,
            "tempfile": tempfile,
            "timezone": timezone,
            "PRSI_QUEUE_PATH": queue_file,
        }

        module = ast.Module(body=[save_func], type_ignores=[])
        module = ast.fix_missing_locations(module)
        exec(compile(module, str(SERVER_PATH), "exec"), namespace)

        # Call the function with a new action
        namespace["_save_prsi_queue"]({"actions": [{"id": "test"}]})

        # Verify file is writable now and contains valid JSON
        content = json.loads(queue_file.read_text(encoding="utf-8"))
        check("updated_at" in content, f"File should contain updated_at; got {content}")
        check(content["actions"] == [{"id": "test"}], f"File should contain actions; got {content}")

        # Verify file mode is 0o640
        stat_mode = queue_file.stat().st_mode & 0o777
        check(stat_mode == 0o640, f"File mode should be 0o640; got {oct(stat_mode)}")

        # Verify no temp files left behind
        tmp_files = list(temp_root.glob(".prsi-queue.*.tmp"))
        check(len(tmp_files) == 0, f"Temp files should be cleaned up; found {tmp_files}")


async def main() -> None:
    check_service_path()
    test_atomic_write()
    server = load_handlers()
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir)
        with patch.dict(os.environ, {"REPO_ROOT": str(temp_root)}):
            with patch("subprocess.run", return_value=SimpleNamespace(
                returncode=0, stdout=json.dumps({"applied": []}), stderr=""
            )) as run:
                result = await server.sync_prsi_queue(auth="test")
                check(result["status"] == "ok", "sync should succeed with configured REPO_ROOT")
                check(run.call_args.kwargs["cwd"] == str(temp_root), "sync should use configured cwd")

            server.actions[:] = [{"id": "approved-1", "status": "approved"}]
            with patch("subprocess.run", return_value=SimpleNamespace(
                returncode=0, stdout="{}", stderr=""
            )) as run:
                result = await server.execute_prsi_actions(
                    limit=1, dry_run=False, auto_sync=False, auth="test"
                )
                check(result["executed"] == 1, "execute should run the approved action")
                check(run.call_args.kwargs["cwd"] == str(temp_root), "execute should use configured cwd")

        server.actions[:] = [{"id": "approved-2", "status": "approved"}]
        with patch.dict(os.environ, {}, clear=True), patch("subprocess.run") as run:
            result = await server.sync_prsi_queue(auth="test")
            check(result["status"] == "error", "sync should fail without REPO_ROOT")
            check(not run.called, "sync must not launch optimizer without REPO_ROOT")

            result = await server.execute_prsi_actions(
                limit=1, dry_run=False, auto_sync=False, auth="test"
            )
            check(result["executed"] == 0, "execute should not execute without REPO_ROOT")
            check(not run.called, "execute must not launch optimizer without REPO_ROOT")
            check(server.actions[0]["status"] == "failed",
                  "approved action should fail closed without REPO_ROOT")


if __name__ == "__main__":
    asyncio.run(main())
    print("PASS: Ralph PRSI handlers require and honor REPO_ROOT")
