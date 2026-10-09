#!/usr/bin/env python3
# local-harness-proxy — Legacy file-based bridge for constrained AI agents.
#
# Monitors .agent/comms/command.json for shell commands and writes
# output to output.json. Superseded by the native MCP bridge.
import asyncio
import json
import logging
import os
import subprocess
import time
import sys
from pathlib import Path
from typing import Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO, format='[Proxy] %(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class LocalHarnessProxy:
    def __init__(self):
        self.repo_root = Path(__file__).resolve().parent.parent.parent
        self.comms_dir = self.repo_root / ".agent" / "comms"
        self.command_file = self.comms_dir / "command.json"
        self.output_file = self.comms_dir / "output.json"
        self.poll_interval = 1 # seconds

        self._setup_comms_dir()

    def _setup_comms_dir(self):
        self.comms_dir.mkdir(parents=True, exist_ok=True)
        if not self.comms_dir.is_dir():
            logger.error(f"FATAL: Failed to create communications directory at {self.comms_dir}. Please check permissions.")
            sys.exit(1)
        logger.info(f"Comms directory set to: {self.comms_dir}")

    async def _execute_command(self, command_payload: Dict[str, Any]) -> Dict[str, Any]:
        cmd = command_payload.get("command")
        args = command_payload.get("args", [])
        cwd = command_payload.get("cwd", str(self.repo_root))
        timeout = command_payload.get("timeout", 300) # 5 minutes default

        if not cmd:
            return {"status": "error", "error": "No command specified in payload."}

        full_command = [cmd] + args
        logger.info(f"Executing: {' '.join(full_command)} in {cwd}")

        try:
            process = await asyncio.create_subprocess_exec(
                *full_command,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=os.environ # Inherit environment
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)

            return {
                "status": "success" if process.returncode == 0 else "failure",
                "command": ' '.join(full_command),
                "returncode": process.returncode,
                "stdout": stdout.decode(errors='ignore'),
                "stderr": stderr.decode(errors='ignore'),
                "timestamp": time.time()
            }
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            return {
                "status": "timeout",
                "command": ' '.join(full_command),
                "error": f"Command timed out after {timeout} seconds.",
                "stdout": "",
                "stderr": "",
                "timestamp": time.time()
            }
        except FileNotFoundError:
            return {
                "status": "error",
                "command": ' '.join(full_command),
                "error": f"Command not found: {cmd}. Ensure it's in PATH or provide full path.",
                "stdout": "",
                "stderr": "",
                "timestamp": time.time()
            }
        except Exception as e:
            return {
                "status": "error",
                "command": ' '.join(full_command),
                "error": str(e),
                "stdout": "",
                "stderr": "",
                "timestamp": time.time()
            }

    async def run(self):
        logger.info(f"Watching for commands in {self.command_file}...")
        while True:
            if self.command_file.exists():
                try:
                    # Wait until the file is stable to avoid reading partial writes
                    last_size = -1
                    stable_reads = 0
                    max_checks = 10 # Wait for max 1 second
                    check_count = 0
                    while stable_reads < 2 and check_count < max_checks:
                        try:
                            current_size = self.command_file.stat().st_size
                            if current_size == last_size and current_size > 0:
                                stable_reads += 1
                            else:
                                stable_reads = 0
                            last_size = current_size
                        except FileNotFoundError:
                            last_size = -1
                            break
                        await asyncio.sleep(0.1)
                        check_count += 1

                    if last_size <= 0:
                        logger.warning("Command file disappeared or is empty, skipping.")
                        if self.command_file.exists():
                            self.command_file.unlink() # Clean up empty/stale file
                        continue

                    content = self.command_file.read_text(errors='ignore')
                    logger.info("Processing command file...")
                    command_payload = json.loads(content)
                    self.command_file.unlink() # Remove command file immediately
                    result = await self._execute_command(command_payload)
                    self.output_file.write_text(json.dumps(result, indent=2))
                    logger.info("Execution finished. Output written to output.json.")

                    print("\n--- BEGIN PROXY OUTPUT ---")
                    print(json.dumps(result, indent=2))
                    print("--- END PROXY OUTPUT ---\n")

                except json.JSONDecodeError as e:
                    content = self.command_file.read_text(errors='ignore') if self.command_file.exists() else ""
                    error_msg = f"Error decoding command.json: {e}. Content: '{content}'"
                    logger.error(error_msg)
                    result = {"status": "error", "error": error_msg}
                    self.output_file.write_text(json.dumps(result, indent=2))
                    if self.command_file.exists(): self.command_file.unlink() # Delete invalid command file
                    print("\n--- BEGIN PROXY OUTPUT ---")
                    print(json.dumps(result, indent=2))
                    print("--- END PROXY OUTPUT ---\n")
                except Exception as e:
                    error_msg = f"Unexpected error processing command file: {e}"
                    logger.error(error_msg, exc_info=True)
                    result = {"status": "error", "error": error_msg}
                    self.output_file.write_text(json.dumps(result, indent=2))
                    if self.command_file.exists(): self.command_file.unlink() # Try to clean up
                    print("\n--- BEGIN PROXY OUTPUT ---")
                    print(json.dumps(result, indent=2))
                    print("--- END PROXY OUTPUT ---\n")
            await asyncio.sleep(self.poll_interval)

if __name__ == "__main__":
    proxy = LocalHarnessProxy()
    asyncio.run(proxy.run())
