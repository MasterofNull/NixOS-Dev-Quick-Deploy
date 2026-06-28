#!/usr/bin/env python3
"""
Tool Registry and Calling Infrastructure for Local Agents

Provides OpenClaw-like tool calling capabilities for local llama.cpp models:
- Tool definition schema (JSON)
- Tool registry with safety policies
- Function calling protocol for llama.cpp
- Tool call parsing and validation
- Result formatting for model consumption
- Audit logging

Part of Phase 11 Batch 11.1: Tool Calling Infrastructure
"""

import asyncio
import hashlib
import json
import logging
import os
import sqlite3
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

# Add parent directory to path for imports to reach workflow.safety_control_layer
# (Assumes being run from ai-stack/local-agents)
_MODULE_DIR = Path(__file__).parent
_COORDINATOR_DIR = _MODULE_DIR.parent / "mcp-servers" / "hybrid-coordinator"
if str(_COORDINATOR_DIR) not in sys.path:
    sys.path.insert(0, str(_COORDINATOR_DIR))

try:
    from workflow.safety_control_layer import SafetyControlLayer
except ImportError:
    # Fallback/stub if not available
    class SafetyControlLayer: # type: ignore
        def __init__(self, mode="open"): pass
        def intercept_action(self, *args, **kwargs): return None

logger = logging.getLogger(__name__)


def _default_tool_audit_db_path() -> Path:
    """Choose a writable audit DB location for services and interactive shells."""
    for env_name in ("XDG_STATE_HOME", "DATA_DIR"):
        base = os.getenv(env_name)
        if base:
            return Path(base) / "local-agents" / "tool_audit.db"

    data_home = os.getenv("XDG_DATA_HOME")
    if data_home:
        return Path(data_home) / "nixos-ai-stack" / "local-agents" / "tool_audit.db"

    return Path.home() / ".local/share/nixos-ai-stack/local-agents/tool_audit.db"


class SafetyPolicy(Enum):
    """Safety policy levels for tool access"""
    READ_ONLY = "read_only"  # Read files, fetch URLs
    WRITE_SAFE = "write_safe"  # Write to /tmp, logs
    WRITE_DATA = "write_data"  # Write to data dirs
    SYSTEM_MODIFY = "system_modify"  # Service restart, config
    DESTRUCTIVE = "destructive"  # Delete, format, network


class ToolCategory(Enum):
    """Tool categories for organization"""
    FILE_OPS = "file_operations"
    SHELL = "shell_commands"
    WEB = "web_operations"
    VISION = "vision_computer_use"
    MEMORY = "memory_database"
    CODE_EXEC = "code_execution"
    AI_COORD = "ai_coordination"


DEFAULT_SECURITY_METADATA: Dict[str, Any] = {
    "sandbox_profile": "readonly-strict",
    "resource_roots": ["/var/lib/nixos-ai-stack/mutable/program/agent-runs"],
    "timeout_seconds": 30,
    "output_cap_bytes": 65536,
    "artifact_retention": "none",
    "secret_policy": "deny",
    "network_policy": "none",
}

POLICY_SECURITY_DEFAULTS: Dict[SafetyPolicy, Dict[str, Any]] = {
    SafetyPolicy.READ_ONLY: {
        "sandbox_profile": "readonly-strict",
        "network_policy": "none",
    },
    SafetyPolicy.WRITE_SAFE: {
        "sandbox_profile": "execute-guarded",
        "network_policy": "loopback",
    },
    SafetyPolicy.WRITE_DATA: {
        "sandbox_profile": "execute-guarded",
        "network_policy": "loopback",
    },
    SafetyPolicy.SYSTEM_MODIFY: {
        "sandbox_profile": "worktree-guarded",
        "network_policy": "loopback",
        "artifact_retention": "audit",
    },
    SafetyPolicy.DESTRUCTIVE: {
        "sandbox_profile": "worktree-guarded",
        "network_policy": "loopback",
        "artifact_retention": "audit",
        "secret_policy": "deny-and-confirm",
    },
}


@dataclass
class ToolDefinition:
    """
    Tool definition following OpenAI function calling schema.

    Compatible with llama.cpp function calling format.
    """
    name: str
    description: str
    parameters: Dict[str, Any]  # JSON schema for parameters
    category: ToolCategory
    safety_policy: SafetyPolicy

    # Execution
    handler: Callable  # Async function to execute tool
    requires_confirmation: bool = False
    requires_proposal: bool = False # Agentix style staging
    audit: bool = True

    # Rate limiting
    max_calls_per_minute: int = 60
    max_calls_per_hour: int = 1000

    # Metadata
    version: str = "1.0.0"
    enabled: bool = True

    # Security metadata required by the MAEAH Phase 1/62 tool contract.
    # Legacy tool declarations may omit these; __post_init__ assigns conservative
    # effective defaults so registry lint can validate a complete policy view.
    sandbox_profile: str = ""
    resource_roots: List[str] = field(default_factory=list)
    timeout_seconds: int = 0
    output_cap_bytes: int = 0
    artifact_retention: str = ""
    secret_policy: str = ""
    network_policy: str = ""

    def __post_init__(self):
        # Auto-set requires_proposal for risky policies
        if self.safety_policy in (SafetyPolicy.SYSTEM_MODIFY, SafetyPolicy.DESTRUCTIVE):
            self.requires_proposal = True
        self._apply_security_defaults()

    def _apply_security_defaults(self) -> None:
        """Populate effective sandbox/security metadata for registry linting."""
        defaults = {
            **DEFAULT_SECURITY_METADATA,
            **POLICY_SECURITY_DEFAULTS.get(self.safety_policy, {}),
        }
        if not self.sandbox_profile:
            self.sandbox_profile = str(defaults["sandbox_profile"])
        if not self.resource_roots:
            self.resource_roots = list(defaults["resource_roots"])
        if not self.timeout_seconds:
            self.timeout_seconds = int(defaults["timeout_seconds"])
        if not self.output_cap_bytes:
            self.output_cap_bytes = int(defaults["output_cap_bytes"])
        if not self.artifact_retention:
            self.artifact_retention = str(defaults["artifact_retention"])
        if not self.secret_policy:
            self.secret_policy = str(defaults["secret_policy"])
        if not self.network_policy:
            self.network_policy = str(defaults["network_policy"])

    def to_json_schema(self) -> Dict[str, Any]:
        """
        Convert to llama.cpp function calling JSON schema.

        Returns schema in OpenAI-compatible format.
        """
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (without handler)"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
            "category": self.category.value,
            "safety_policy": self.safety_policy.value,
            "requires_confirmation": self.requires_confirmation,
            "audit": self.audit,
            "max_calls_per_minute": self.max_calls_per_minute,
            "max_calls_per_hour": self.max_calls_per_hour,
            "version": self.version,
            "enabled": self.enabled,
            "sandbox_profile": self.sandbox_profile,
            "resource_roots": self.resource_roots,
            "timeout_seconds": self.timeout_seconds,
            "output_cap_bytes": self.output_cap_bytes,
            "artifact_retention": self.artifact_retention,
            "secret_policy": self.secret_policy,
            "network_policy": self.network_policy,
        }


@dataclass
class ToolCall:
    """A tool call request from a model"""
    id: str
    tool_name: str
    arguments: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    model_id: str = ""
    session_id: str = ""

    # Execution state
    status: str = "pending"  # pending, executing, completed, failed
    result: Optional[Any] = None
    error: Optional[str] = None
    execution_time_ms: float = 0.0

    # Safety
    safety_check_passed: bool = False
    user_confirmed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "timestamp": self.timestamp.isoformat(),
            "model_id": self.model_id,
            "session_id": self.session_id,
            "status": self.status,
            "result": self.result,
            "error": self.error,
            "execution_time_ms": self.execution_time_ms,
            "safety_check_passed": self.safety_check_passed,
            "user_confirmed": self.user_confirmed,
        }


class ToolRegistry:
    """
    Central registry for tools available to local agents.

    Features:
    - Tool registration and discovery
    - Safety policy enforcement
    - Rate limiting
    - Audit logging
    - Tool call execution
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.tools: Dict[str, ToolDefinition] = {}
        self.call_history: List[ToolCall] = []

        # Rate limiting tracking
        self.call_counts: Dict[str, List[float]] = {}  # tool_name → timestamps

        # Safety Control Layer (Phase 13.1)
        safety_mode = os.getenv("AI_SAFETY_MODE", "review").lower()
        self.safety_layer = SafetyControlLayer(mode=safety_mode)

        # Database for audit trail
        self.db_path = db_path or _default_tool_audit_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()

        logger.info(f"Tool registry initialized: {self.db_path}")

    def _init_database(self):
        """Initialize SQLite database for audit trail"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tool_calls (
                id TEXT PRIMARY KEY,
                timestamp TIMESTAMP NOT NULL,
                tool_name TEXT NOT NULL,
                arguments TEXT,
                model_id TEXT,
                session_id TEXT,
                status TEXT,
                result TEXT,
                error TEXT,
                execution_time_ms REAL,
                safety_check_passed BOOLEAN,
                user_confirmed BOOLEAN
            )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tool_timestamp ON tool_calls(timestamp DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tool_name ON tool_calls(tool_name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tool_session ON tool_calls(session_id)")

        conn.commit()
        conn.close()

        logger.info("Tool call audit database initialized")

    def register(self, tool: ToolDefinition):
        """
        Register a tool in the registry.

        Args:
            tool: Tool definition with handler
        """
        if tool.name in self.tools:
            logger.warning(f"Tool {tool.name} already registered, replacing")

        self.tools[tool.name] = tool
        logger.info(
            f"Registered tool: {tool.name} "
            f"(category={tool.category.value}, policy={tool.safety_policy.value})"
        )

    def unregister(self, tool_name: str):
        """Unregister a tool"""
        if tool_name in self.tools:
            del self.tools[tool_name]
            logger.info(f"Unregistered tool: {tool_name}")

    def get_tool(self, tool_name: str) -> Optional[ToolDefinition]:
        """Get tool definition by name"""
        return self.tools.get(tool_name)

    def list_tools(
        self,
        category: Optional[ToolCategory] = None,
        safety_policy: Optional[SafetyPolicy] = None,
        enabled_only: bool = True,
    ) -> List[ToolDefinition]:
        """
        List registered tools with optional filtering.

        Args:
            category: Filter by category
            safety_policy: Filter by safety policy
            enabled_only: Only return enabled tools

        Returns:
            List of matching tool definitions
        """
        tools = list(self.tools.values())

        if category:
            tools = [t for t in tools if t.category == category]

        if safety_policy:
            tools = [t for t in tools if t.safety_policy == safety_policy]

        if enabled_only:
            tools = [t for t in tools if t.enabled]

        return tools

    def get_tools_for_model(self) -> List[Dict[str, Any]]:
        """
        Get tools in llama.cpp function calling format.

        Returns list of tool schemas for model prompt.
        """
        enabled_tools = [t for t in self.tools.values() if t.enabled]
        return [tool.to_json_schema() for tool in enabled_tools]

    def _check_rate_limit(self, tool_name: str) -> Tuple[bool, str]:
        """
        Check if tool call would exceed rate limits.

        Returns:
            (allowed, reason)
        """
        tool = self.tools.get(tool_name)
        if not tool:
            return False, f"Tool {tool_name} not found"

        now = time.time()
        tool_calls = self.call_counts.get(tool_name, [])

        # Clean old timestamps
        minute_ago = now - 60
        hour_ago = now - 3600
        tool_calls = [ts for ts in tool_calls if ts > hour_ago]

        # Check per-minute limit
        recent_calls = [ts for ts in tool_calls if ts > minute_ago]
        if len(recent_calls) >= tool.max_calls_per_minute:
            return False, f"Rate limit exceeded: {len(recent_calls)}/{tool.max_calls_per_minute} calls/min"

        # Check per-hour limit
        if len(tool_calls) >= tool.max_calls_per_hour:
            return False, f"Rate limit exceeded: {len(tool_calls)}/{tool.max_calls_per_hour} calls/hour"

        return True, "OK"

    def _record_call_timestamp(self, tool_name: str):
        """Record timestamp for rate limiting"""
        if tool_name not in self.call_counts:
            self.call_counts[tool_name] = []
        self.call_counts[tool_name].append(time.time())

    async def execute_tool_call(
        self,
        tool_call: ToolCall,
        request_confirmation: Optional[Callable[[ToolCall], bool]] = None,
    ) -> ToolCall:
        """
        Execute a tool call with safety checks and audit logging.

        Args:
            tool_call: Tool call to execute
            request_confirmation: Optional callback to request user confirmation

        Returns:
            Updated tool call with result or error
        """
        tool = self.tools.get(tool_call.tool_name)

        if not tool:
            tool_call.status = "failed"
            tool_call.error = f"Tool {tool_call.tool_name} not found"
            await self._audit_tool_call(tool_call)
            return tool_call

        if not tool.enabled:
            tool_call.status = "failed"
            tool_call.error = f"Tool {tool_call.tool_name} is disabled"
            await self._audit_tool_call(tool_call)
            return tool_call

        # Rate limiting
        allowed, reason = self._check_rate_limit(tool_call.tool_name)
        if not allowed:
            tool_call.status = "failed"
            tool_call.error = reason
            await self._audit_tool_call(tool_call)
            return tool_call

        # --- Phase 13.1: Safety Control Layer (Agentix style) ---
        if tool.requires_proposal:
            intercept_result = self.safety_layer.intercept_action(
                action_type=tool_call.tool_name,
                params=tool_call.arguments,
                agent_id=tool_call.model_id or "unknown"
            )
            if intercept_result:
                tool_call.status = "intercepted"
                tool_call.result = intercept_result
                tool_call.safety_check_passed = False
                await self._audit_tool_call(tool_call)
                return tool_call

        # Safety check (placeholder - can be extended)
        tool_call.safety_check_passed = True

        # User confirmation for sensitive operations
        if tool.requires_confirmation:
            if request_confirmation:
                tool_call.user_confirmed = request_confirmation(tool_call)
            else:
                tool_call.user_confirmed = False

            if not tool_call.user_confirmed:
                tool_call.status = "failed"
                tool_call.error = "User confirmation required but not granted"
                await self._audit_tool_call(tool_call)
                return tool_call

        # Execute tool
        tool_call.status = "executing"
        start_time = time.time()

        try:
            # Call tool handler
            result = await tool.handler(**tool_call.arguments)

            tool_call.result = result
            tool_call.status = "completed"
            tool_call.execution_time_ms = (time.time() - start_time) * 1000

            # Record timestamp for rate limiting
            self._record_call_timestamp(tool_call.tool_name)

            logger.info(
                f"Tool call completed: {tool_call.tool_name} "
                f"(time={tool_call.execution_time_ms:.1f}ms)"
            )

        except Exception as e:
            tool_call.status = "failed"
            tool_call.error = str(e)
            tool_call.execution_time_ms = (time.time() - start_time) * 1000

            logger.error(
                f"Tool call failed: {tool_call.tool_name} "
                f"(error={tool_call.error}, time={tool_call.execution_time_ms:.1f}ms)"
            )

        # Audit log
        if tool.audit:
            await self._audit_tool_call(tool_call)

        self.call_history.append(tool_call)

        return tool_call

    async def _audit_tool_call(self, tool_call: ToolCall):
        """Store tool call in audit database"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO tool_calls
            (id, timestamp, tool_name, arguments, model_id, session_id,
             status, result, error, execution_time_ms, safety_check_passed, user_confirmed)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                tool_call.id,
                tool_call.timestamp,
                tool_call.tool_name,
                json.dumps(tool_call.arguments),
                tool_call.model_id,
                tool_call.session_id,
                tool_call.status,
                json.dumps(tool_call.result) if tool_call.result else None,
                tool_call.error,
                tool_call.execution_time_ms,
                tool_call.safety_check_passed,
                tool_call.user_confirmed,
            ),
        )

        conn.commit()
        conn.close()

    def parse_tool_call_from_llama(self, model_output: str) -> Optional[ToolCall]:
        """
        Parse tool call from llama.cpp function calling output.

        llama.cpp outputs function calls in JSON format:
        {
          "function": "tool_name",
          "arguments": {...}
        }

        Args:
            model_output: Raw model output

        Returns:
            Parsed ToolCall or None if not a function call
        """
        try:
            # Try to extract JSON from output.
            # llama.cpp may wrap in markdown code blocks or prepend prose.
            output = model_output.strip()

            if output.startswith("```json"):
                output = output[7:]  # Remove ```json
            if output.endswith("```"):
                output = output[:-3]  # Remove ```

            output = output.strip()

            def _sanitize_json(raw: str) -> str:
                """Escape bare control chars inside JSON string values.

                The model sometimes emits literal newlines/tabs inside JSON string
                values (e.g. when old_string/new_string spans multiple source lines).
                json.loads() rejects unescaped control chars, so we replace them
                inside string-value regions only.
                """
                import re as _re
                result, in_str, i = [], False, 0
                while i < len(raw):
                    ch = raw[i]
                    if in_str:
                        if ch == "\\" and i + 1 < len(raw):
                            result.append(ch)
                            result.append(raw[i + 1])
                            i += 2
                            continue
                        if ch == '"':
                            in_str = False
                        elif ch == "\n":
                            result.append("\\n")
                            i += 1
                            continue
                        elif ch == "\r":
                            result.append("\\r")
                            i += 1
                            continue
                        elif ch == "\t":
                            result.append("\\t")
                            i += 1
                            continue
                        elif ord(ch) < 0x20:
                            result.append(f"\\u{ord(ch):04x}")
                            i += 1
                            continue
                    else:
                        if ch == '"':
                            in_str = True
                    result.append(ch)
                    i += 1
                return "".join(result)

            # Fast path: entire output is JSON.
            try:
                data = json.loads(output)
            except json.JSONDecodeError:
                # Retry after sanitizing bare control chars in string values.
                try:
                    data = json.loads(_sanitize_json(output))
                except json.JSONDecodeError:
                    # Fallback: model prepended prose before the JSON object.
                    # Find the last '{' that opens a valid JSON object so we skip
                    # any leading natural-language text.
                    brace = output.rfind('{"function"')
                    if brace == -1:
                        brace = output.rfind("{")
                    if brace == -1:
                        return None
                    try:
                        data = json.loads(output[brace:])
                    except json.JSONDecodeError:
                        data = json.loads(_sanitize_json(output[brace:]))

            # Check if it's a function call
            if not isinstance(data, dict) or "function" not in data:
                return None

            tool_call = ToolCall(
                id=hashlib.md5(f"{data['function']}{time.time()}".encode()).hexdigest()[:16],
                tool_name=data["function"],
                arguments=data.get("arguments") or {},
            )

            return tool_call

        except (json.JSONDecodeError, KeyError) as e:
            logger.debug(f"Failed to parse tool call: {e}")
            return None

    # Per-tool-result char cap: 3000 chars (~750 tokens).
    # At 5 tool calls × 750 tok = 3750 tok, system prompt ~500 tok → stays well under n_ctx=8192.
    _RESULT_CHAR_CAP = 3000

    def format_tool_result(self, tool_call: ToolCall) -> str:
        """Format tool call result for model consumption with size cap."""
        if tool_call.status == "completed":
            raw = json.dumps(tool_call.result, ensure_ascii=False) if not isinstance(tool_call.result, str) else tool_call.result
            if len(raw) > self._RESULT_CHAR_CAP:
                raw = raw[:self._RESULT_CHAR_CAP] + f"\n... [truncated: {len(raw) - self._RESULT_CHAR_CAP} chars omitted]"
            return json.dumps({
                "tool": tool_call.tool_name,
                "status": "success",
                "result": raw,
            })
        else:
            return json.dumps({
                "tool": tool_call.tool_name,
                "status": "error",
                "error": tool_call.error,
            })

    def get_statistics(self) -> Dict[str, Any]:
        """Get tool registry statistics"""
        total_tools = len(self.tools)
        enabled_tools = len([t for t in self.tools.values() if t.enabled])

        tools_by_category = {}
        for category in ToolCategory:
            tools_by_category[category.value] = len([
                t for t in self.tools.values() if t.category == category
            ])

        tools_by_policy = {}
        for policy in SafetyPolicy:
            tools_by_policy[policy.value] = len([
                t for t in self.tools.values() if t.safety_policy == policy
            ])

        return {
            "total_tools": total_tools,
            "enabled_tools": enabled_tools,
            "tools_by_category": tools_by_category,
            "tools_by_policy": tools_by_policy,
            "security_metadata": self.get_security_metadata_summary(),
            "total_calls": len(self.call_history),
            "successful_calls": len([c for c in self.call_history if c.status == "completed"]),
            "failed_calls": len([c for c in self.call_history if c.status == "failed"]),
        }

    def get_security_metadata_summary(self) -> Dict[str, Any]:
        """Summarize effective sandbox/security metadata for dashboard use."""
        enabled_tools = [t for t in self.tools.values() if t.enabled]
        missing = [
            t.name
            for t in enabled_tools
            if not all([
                t.sandbox_profile,
                t.resource_roots,
                t.timeout_seconds,
                t.output_cap_bytes,
                t.artifact_retention,
                t.secret_policy,
                t.network_policy,
            ])
        ]
        profiles: Dict[str, int] = {}
        network_policies: Dict[str, int] = {}
        for tool in enabled_tools:
            profiles[tool.sandbox_profile] = profiles.get(tool.sandbox_profile, 0) + 1
            network_policies[tool.network_policy] = network_policies.get(tool.network_policy, 0) + 1
        return {
            "complete": not missing,
            "missing_count": len(missing),
            "missing_tools": missing[:20],
            "sandbox_profiles": profiles,
            "network_policies": network_policies,
        }


# Global registry instance
_REGISTRY: Optional[ToolRegistry] = None


def get_registry() -> ToolRegistry:
    """Get global tool registry instance"""
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = ToolRegistry()
    return _REGISTRY


if __name__ == "__main__":
    # Test tool registry
    logging.basicConfig(level=logging.INFO)

    async def test():
        registry = ToolRegistry()

        # Register a test tool
        async def read_file_handler(file_path: str) -> str:
            """Test file read handler"""
            await asyncio.sleep(0.1)  # Simulate IO
            return f"Contents of {file_path}"

        tool = ToolDefinition(
            name="read_file",
            description="Read contents of a file",
            parameters={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Absolute path to file",
                    }
                },
                "required": ["file_path"],
            },
            category=ToolCategory.FILE_OPS,
            safety_policy=SafetyPolicy.READ_ONLY,
            handler=read_file_handler,
        )

        registry.register(tool)

        # Test tool execution
        tool_call = ToolCall(
            id="test-123",
            tool_name="read_file",
            arguments={"file_path": "/tmp/test.txt"},
            model_id="test-model",
            session_id="test-session",
        )

        result = await registry.execute_tool_call(tool_call)

        print(f"\nTool call result:")
        print(f"  Status: {result.status}")
        print(f"  Result: {result.result}")
        print(f"  Time: {result.execution_time_ms:.1f}ms")

        # Test formatting
        formatted = registry.format_tool_result(result)
        print(f"\nFormatted result:")
        print(formatted)

        # Get statistics
        stats = registry.get_statistics()
        print(f"\nRegistry statistics:")
        print(json.dumps(stats, indent=2))

    asyncio.run(test())
