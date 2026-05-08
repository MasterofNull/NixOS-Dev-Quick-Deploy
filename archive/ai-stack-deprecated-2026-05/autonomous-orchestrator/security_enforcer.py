#!/usr/bin/env python3
"""
Security Policy Enforcer for Autonomous Agent

Enforces restrictions defined in security_policy.json to prevent
risky operations in autonomous mode while allowing safe workflow ops.

Part of Phase 12: Autonomous Orchestration with Security Restrictions
"""

import json
import logging
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class OperationMode(Enum):
    """Agent operation mode"""
    AUTONOMOUS = "autonomous"  # Long-running, restricted
    INTERACTIVE = "interactive"  # Human-supervised, full access


class SecurityViolation(Exception):
    """Raised when an operation violates security policy"""
    pass


class SecurityEnforcer:
    """Enforces security policy restrictions"""

    def __init__(
        self,
        mode: OperationMode = OperationMode.AUTONOMOUS,
        policy_path: Optional[Path] = None,
    ):
        self.mode = mode

        # Load policy
        if policy_path is None:
            policy_path = Path(__file__).parent / "security_policy.json"

        with open(policy_path) as f:
            self.policy = json.load(f)

        # Get mode-specific restrictions
        self.restrictions = self.policy["modes"][mode.value]["restrictions"]
        self.approval_requirements = self.policy["modes"][mode.value]["approval_requirements"]

        # Build tool lists
        if mode == OperationMode.AUTONOMOUS:
            self.blocked_tools = set(
                self.policy["tool_policies"]["blocklist_in_autonomous_mode"]
            )
            self.allowed_tools = set(
                self.policy["tool_policies"]["allowlist_in_autonomous_mode"]
            )
        else:
            self.blocked_tools = set()
            self.allowed_tools = set(["*"])  # All tools allowed in interactive

        self.requires_confirmation = set(
            self.policy["tool_policies"]["always_require_confirmation"]
        )

        # Circuit breakers
        self.circuit_breakers = self.policy["circuit_breakers"]

        # Audit
        self.audit_config = self.policy["audit"]

        logger.info(
            f"Security enforcer initialized in {mode.value} mode "
            f"(blocked: {len(self.blocked_tools)} tools)"
        )

    def check_tool_allowed(self, tool_name: str) -> bool:
        """Check if a tool is allowed in current mode"""

        # Check blocklist first
        if tool_name in self.blocked_tools:
            return False

        # Check allowlist
        if "*" in self.allowed_tools:
            return True

        return tool_name in self.allowed_tools

    def validate_tool_call(
        self,
        tool_name: str,
        arguments: Dict,
    ) -> None:
        """
        Validate a tool call against security policy.

        Raises:
            SecurityViolation: If the tool call violates policy
        """

        # Check if tool is allowed
        if not self.check_tool_allowed(tool_name):
            raise SecurityViolation(
                f"Tool '{tool_name}' is blocked in {self.mode.value} mode. "
                f"Reason: Potential security risk (e.g., mouse/keyboard control)."
            )

        # Special validations by tool category
        if tool_name in ["mouse_move", "mouse_click", "keyboard_type", "keyboard_press"]:
            # Computer use tools
            if not self.restrictions["computer_use"]["enabled"]:
                raise SecurityViolation(
                    f"Computer use tools disabled in {self.mode.value} mode"
                )

        elif tool_name in ["run_python", "run_bash", "run_javascript", "run_command"]:
            # Code execution tools
            if not self.restrictions["code_execution"]["enabled"]:
                raise SecurityViolation(
                    f"Code execution disabled in {self.mode.value} mode"
                )

            # Check for blocked commands
            if "command" in arguments or "code" in arguments:
                code = arguments.get("command") or arguments.get("code", "")
                self._validate_command(code)

        elif tool_name in ["read_file", "write_file", "search_files", "list_directory"]:
            # File operations
            if not self.restrictions["file_operations"]["enabled"]:
                raise SecurityViolation(
                    f"File operations disabled in {self.mode.value} mode"
                )

            # Check path restrictions
            if "path" in arguments or "file_path" in arguments:
                path = arguments.get("path") or arguments.get("file_path")
                self._validate_file_path(path)

        logger.debug(f"Tool call validated: {tool_name}")

    def _validate_command(self, command: str) -> None:
        """Validate shell command against policy"""

        cmd_lower = command.lower().strip()

        # Check blocklist
        blocklist = self.restrictions["shell_commands"]["blocklist"]
        for blocked in blocklist:
            if blocked.lower() in cmd_lower:
                raise SecurityViolation(
                    f"Command contains blocked pattern: '{blocked}'"
                )

        # Check allowlist (if not "*")
        allowlist = self.restrictions["shell_commands"]["allowlist"]
        if "*" not in allowlist:
            # Extract base command
            base_cmd = cmd_lower.split()[0] if cmd_lower else ""

            # Check if base command or full pattern is allowed
            allowed = False
            for pattern in allowlist:
                if pattern == base_cmd or cmd_lower.startswith(pattern.lower()):
                    allowed = True
                    break

            if not allowed:
                raise SecurityViolation(
                    f"Command '{base_cmd}' not in allowlist. "
                    f"Allowed: {', '.join(allowlist)}"
                )

    def _validate_file_path(self, path: str) -> None:
        """Validate file path against policy"""

        path_obj = Path(path).resolve()
        path_str = str(path_obj)

        # Check blocked paths
        blocked = self.restrictions["file_operations"]["blocked_paths"]
        for blocked_path in blocked:
            blocked_expanded = Path(blocked_path).expanduser().resolve()

            try:
                # Check if path is under blocked directory
                path_obj.relative_to(blocked_expanded)
                raise SecurityViolation(
                    f"Path '{path}' is under blocked location: {blocked_path}"
                )
            except ValueError:
                # Not under blocked path, continue
                pass

        # Check allowed paths (if not "*")
        allowed = self.restrictions["file_operations"]["allowed_paths"]
        if "*" not in allowed:
            # Path must be under one of the allowed directories
            is_allowed = False

            for allowed_path in allowed:
                # Resolve relative to repo root
                # (Assuming we're in a git repo)
                try:
                    repo_root = Path.cwd()
                    allowed_full = (repo_root / allowed_path).resolve()

                    # Check if path is under allowed directory
                    path_obj.relative_to(allowed_full)
                    is_allowed = True
                    break
                except (ValueError, Exception):
                    continue

            if not is_allowed:
                raise SecurityViolation(
                    f"Path '{path}' not under allowed directories: {', '.join(allowed)}"
                )

    def requires_human_approval(self, operation_type: str) -> bool:
        """Check if operation requires human approval"""

        approval = self.approval_requirements.get(operation_type, "auto")
        return approval == "human_required"

    def get_approval_tier(self, operation_type: str) -> str:
        """Get required approval tier for operation type"""

        return self.approval_requirements.get(operation_type, "auto")

    def check_circuit_breaker(
        self,
        failures: int = 0,
        tool_calls: int = 0,
        api_cost: float = 0.0,
        file_changes: int = 0,
    ) -> Optional[str]:
        """
        Check circuit breaker limits.

        Returns:
            None if OK, or error message if limit exceeded
        """

        if failures >= self.circuit_breakers["max_consecutive_failures"]:
            return (
                f"Circuit breaker: {failures} consecutive failures "
                f"(max: {self.circuit_breakers['max_consecutive_failures']})"
            )

        if tool_calls >= self.circuit_breakers["max_tool_calls_per_hour"]:
            return (
                f"Circuit breaker: {tool_calls} tool calls in 1 hour "
                f"(max: {self.circuit_breakers['max_tool_calls_per_hour']})"
            )

        if api_cost >= self.circuit_breakers["max_api_cost_per_hour_usd"]:
            return (
                f"Circuit breaker: ${api_cost:.2f} API cost in 1 hour "
                f"(max: ${self.circuit_breakers['max_api_cost_per_hour_usd']:.2f})"
            )

        if file_changes >= self.circuit_breakers["max_file_changes_per_batch"]:
            return (
                f"Circuit breaker: {file_changes} file changes in batch "
                f"(max: {self.circuit_breakers['max_file_changes_per_batch']})"
            )

        return None

    def audit_log(self, event: str, details: Dict) -> None:
        """Log audit event if enabled"""

        if not self.audit_config["log_all_tool_calls"]:
            return

        # TODO: Implement proper audit logging to file
        logger.info(f"AUDIT: {event} - {json.dumps(details)}")


def get_enforcer(
    mode: OperationMode = OperationMode.AUTONOMOUS
) -> SecurityEnforcer:
    """Get security enforcer instance for mode"""
    return SecurityEnforcer(mode=mode)


if __name__ == "__main__":
    # Test security enforcer
    logging.basicConfig(level=logging.INFO)

    # Test autonomous mode
    enforcer = SecurityEnforcer(mode=OperationMode.AUTONOMOUS)

    # These should pass
    try:
        enforcer.validate_tool_call("read_file", {"path": ".agents/plans/test.md"})
        print("✓ read_file allowed")
    except SecurityViolation as e:
        print(f"✗ read_file blocked: {e}")

    try:
        enforcer.validate_tool_call("git_status", {})
        print("✓ git_status allowed")
    except SecurityViolation as e:
        print(f"✗ git_status blocked: {e}")

    # These should fail
    try:
        enforcer.validate_tool_call("mouse_click", {"x": 100, "y": 100})
        print("✗ mouse_click allowed (SHOULD BE BLOCKED)")
    except SecurityViolation as e:
        print(f"✓ mouse_click blocked: {e}")

    try:
        enforcer.validate_tool_call("run_bash", {"command": "rm -rf /"})
        print("✗ rm -rf allowed (SHOULD BE BLOCKED)")
    except SecurityViolation as e:
        print(f"✓ rm -rf blocked: {e}")

    try:
        enforcer.validate_tool_call("write_file", {"path": "/etc/passwd", "content": "hack"})
        print("✗ /etc/passwd write allowed (SHOULD BE BLOCKED)")
    except SecurityViolation as e:
        print(f"✓ /etc/passwd write blocked: {e}")

    # Test circuit breakers
    result = enforcer.check_circuit_breaker(failures=5)
    if result:
        print(f"✓ Circuit breaker triggered: {result}")
    else:
        print("✗ Circuit breaker should have triggered")
