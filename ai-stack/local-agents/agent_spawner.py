#!/usr/bin/env python3
"""
Agent Spawner — Multi-Agent Team Orchestration

Spawns independent LocalAgentExecutor subprocesses with distinct roles
(coordinator, coder, reviewer, researcher, planner). Each agent runs as
its own process with its own system prompt, tool set, and state tracking.

Usage:
  # Spawn a single agent task
  python agent_spawner.py spawn --role coder --task "implement battery threshold feature"

  # Spawn a team for a complex task
  python agent_spawner.py team --task "refactor the authentication system"

  # Check agent status
  python agent_spawner.py status

  # Kill all agents
  python agent_spawner.py kill

Agent Roles and Capabilities:
  coordinator  — Orchestrates teams, delegates, aggregates results
  coder        — Implements code changes, writes tests
  reviewer     — Reviews code for correctness, security, quality
  researcher   — Gathers context, searches knowledge base, web research
  planner      — Breaks complex tasks into phases, identifies dependencies

Architecture:
  User prompt → coordinator agent → spawns team agents → collects results → synthesis
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import signal
import subprocess
import sys
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── Paths ─────────────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
# Use /tmp for state since the harness runs with ProtectSystem=strict and may
# not have write access to /run or the repo directory.
STATE_DIR = Path(os.environ.get("AGENT_STATE_DIR", "/tmp/agent-spawner"))
STATE_DIR.mkdir(parents=True, exist_ok=True)
AGENTS_DIR = REPO_ROOT / "ai-stack" / "local-agents"

# Add local-agents to path for imports
if str(AGENTS_DIR) not in sys.path:
    sys.path.insert(0, str(AGENTS_DIR))

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] agent-spawner: %(message)s",
)
log = logging.getLogger(__name__)

# ── Agent Role Definitions ───────────────────────────────────────────────────

AGENT_ROLES: Dict[str, Dict[str, Any]] = {
    "coordinator": {
        "description": "Orchestrates agent teams, delegates tasks, aggregates results",
        "system_prompt": (
            "You are a coordinator agent. Your role is to:\n"
            "1. Analyze the user's request and break it into sub-tasks\n"
            "2. Delegate sub-tasks to appropriate specialist agents (coder, reviewer, researcher, planner)\n"
            "3. Collect and synthesize results from sub-agents\n"
            "4. Produce a final comprehensive response\n\n"
            "Rules:\n"
            "- Be systematic and thorough\n"
            "- Delegate when work can be parallelized\n"
            "- Always validate results before synthesizing\n"
            "- Capture evidence of what you delegated and why"
        ),
        "tools": ["shell", "file_read", "delegate"],
        "max_tool_calls": 20,
    },
    "coder": {
        "description": "Implements code changes, writes tests, fixes bugs",
        "system_prompt": (
            "You are a coder agent. Your role is to implement code changes.\n\n"
            "Rules:\n"
            "- Follow project conventions (read nearby files first)\n"
            "- Never hardcode secrets, ports, or URLs\n"
            "- Write tests alongside implementation\n"
            "- Use declarative-first approach for NixOS changes\n"
            "- Report what files you changed and what commands you ran\n"
            "- If you need to run commands, explain what they do first"
        ),
        "tools": ["shell", "file_read", "file_write", "code_execution"],
        "max_tool_calls": 15,
    },
    "reviewer": {
        "description": "Reviews code for correctness, security, performance, quality",
        "system_prompt": (
            "You are a reviewer agent. Your role is to review code changes.\n\n"
            "Check for:\n"
            "1. Correctness — does the code do what it claims?\n"
            "2. Security — no hardcoded secrets, safe input handling\n"
            "3. Performance — no obvious bottlenecks\n"
            "4. Code quality — follows project conventions, well-structured\n"
            "5. Tests — adequate test coverage\n\n"
            "Report findings as: PASS, WARN, or FAIL with explanation."
        ),
        "tools": ["shell", "file_read", "code_execution"],
        "max_tool_calls": 10,
    },
    "researcher": {
        "description": "Gathers context, searches knowledge base, finds documentation",
        "system_prompt": (
            "You are a researcher agent. Your role is to gather context.\n\n"
            "Methods:\n"
            "1. Search the local knowledge base and codebase\n"
            "2. Read relevant files and documentation\n"
            "3. Identify patterns from similar past work\n"
            "4. Summarize findings with source references\n\n"
            "Always cite your sources. Prefer local files first."
        ),
        "tools": ["shell", "file_read", "file_search"],
        "max_tool_calls": 12,
    },
    "planner": {
        "description": "Breaks complex tasks into phases, identifies dependencies and risks",
        "system_prompt": (
            "You are a planner agent. Your role is to create execution plans.\n\n"
            "Output a phased plan:\n"
            "1. Phase 1 — Discovery (gather context, identify affected files)\n"
            "2. Phase 2 — Implementation (specific changes per file)\n"
            "3. Phase 3 — Validation (tests, linting, syntax checks)\n"
            "4. Phase 4 — Deployment (if applicable)\n\n"
            "For each phase: list files to change, commands to run, and rollback plan.\n"
            "Identify dependencies and parallelization opportunities."
        ),
        "tools": ["shell", "file_read", "file_search"],
        "max_tool_calls": 8,
    },
}

# ── State Management ─────────────────────────────────────────────────────────

@dataclass
class AgentInstance:
    """Represents a running agent instance"""
    id: str
    role: str
    task: str
    status: str = "pending"  # pending, running, completed, failed, killed
    pid: Optional[int] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    result: Optional[str] = None
    error: Optional[str] = None
    tool_calls_made: int = 0
    execution_time_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AgentState:
    """Manages agent instance state persisted to disk"""

    def __init__(self):
        self.state_file = STATE_DIR / "agent-state.json"
        self.instances: Dict[str, AgentInstance] = {}
        self._load()

    def _load(self):
        if self.state_file.exists():
            try:
                data = json.loads(self.state_file.read_text())
                for iid, idata in data.get("instances", {}).items():
                    self.instances[iid] = AgentInstance(**idata)
            except (json.JSONDecodeError, TypeError) as e:
                log.warning("Corrupted state file, starting fresh: %s", e)
                self.instances = {}

    def _save(self):
        data = {
            "instances": {k: v.to_dict() for k, v in self.instances.items()},
            "updated_at": datetime.now().isoformat(),
        }
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(json.dumps(data, indent=2))

    def register(self, role: str, task: str) -> AgentInstance:
        instance = AgentInstance(
            id=str(uuid.uuid4())[:8],
            role=role,
            task=task,
        )
        self.instances[instance.id] = instance
        self._save()
        return instance

    def update(self, instance_id: str, **kwargs):
        if instance_id in self.instances:
            for k, v in kwargs.items():
                setattr(self.instances[instance_id], k, v)
            self._save()

    def get_active(self) -> List[AgentInstance]:
        return [
            i for i in self.instances.values()
            if i.status in ("pending", "running")
        ]

    def get_all(self) -> List[AgentInstance]:
        return list(self.instances.values())

    def cleanup_dead(self):
        """Remove completed instances older than 1 hour"""
        cutoff = time.time() - 3600
        to_remove = []
        for iid, inst in self.instances.items():
            if inst.status in ("completed", "failed", "killed") and inst.completed_at:
                try:
                    completed_ts = datetime.fromisoformat(inst.completed_at).timestamp()
                    if completed_ts < cutoff:
                        to_remove.append(iid)
                except (ValueError, TypeError):
                    pass
        for iid in to_remove:
            del self.instances[iid]
        if to_remove:
            self._save()


# ── Agent Process Spawning ───────────────────────────────────────────────────

def _build_agent_prompt(role: str, task: str) -> str:
    """Build the full prompt for an agent subprocess"""
    role_def = AGENT_ROLES.get(role, AGENT_ROLES["coder"])
    return f"{role_def['system_prompt']}\n\n---\n\nTASK:\n{task}"


def _spawn_agent_process(
    instance: AgentInstance,
    llama_url: str = "http://127.0.0.1:8080",
    switchboard_url: str = "http://127.0.0.1:8085",
    coordinator_url: str = "http://127.0.0.1:8003",
) -> subprocess.Popen:
    """Spawn an agent as an independent subprocess.

    The agent runs as a Python script that:
    1. Reads its role and task from environment
    2. Calls llama.cpp via the switchboard (for tool-augmented chat)
    3. Writes its result to a shared state file
    """
    role_def = AGENT_ROLES[instance.role]
    prompt = _build_agent_prompt(instance.role, instance.task)

    env = os.environ.copy()
    env.update({
        "AGENT_ID": instance.id,
        "AGENT_ROLE": instance.role,
        "AGENT_TASK": task,
        "AGENT_SYSTEM_PROMPT": prompt,
        "LLAMA_CPP_URL": llama_url,
        "SWITCHBOARD_URL": switchboard_url,
        "COORDINATOR_URL": coordinator_url,
        "AGENT_STATE_FILE": str(STATE_DIR / f"agent-{instance.id}.json"),
        "AGENT_MAX_TOOL_CALLS": str(role_def["max_tool_calls"]),
        "PYTHONUNBUFFERED": "1",
    })

    # The agent subprocess runs a standalone script that executes the task
    agent_runner = AGENTS_DIR / "agent_runner.py"
    if not agent_runner.exists():
        # Fallback: use a simple inline script via python -c
        return _spawn_agent_inline(instance, prompt, env)

    proc = subprocess.Popen(
        [sys.executable, str(agent_runner)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    return proc


def _spawn_agent_inline(
    instance: AgentInstance,
    prompt: str,
    env: Dict[str, str],
) -> subprocess.Popen:
    """Spawn agent using inline Python (no separate runner script needed)."""
    code = """
import asyncio, json, os, sys, time, httpx
from pathlib import Path

AGENT_ID = os.environ["AGENT_ID"]
AGENT_ROLE = os.environ["AGENT_ROLE"]
AGENT_TASK = os.environ["AGENT_TASK"]
SYSTEM_PROMPT = os.environ["AGENT_SYSTEM_PROMPT"]
LLAMA_URL = os.environ.get("LLAMA_CPP_URL", "http://127.0.0.1:8080")
STATE_FILE = os.environ.get("AGENT_STATE_FILE", "")
MAX_TOOL_CALLS = int(os.environ.get("AGENT_MAX_TOOL_CALLS", "10"))

async def run():
    state = {
        "id": AGENT_ID, "role": AGENT_ROLE, "status": "running",
        "started_at": time.time(), "tool_calls": 0,
    }

    # Write running state
    if STATE_FILE:
        Path(STATE_FILE).write_text(json.dumps(state))

    try:
        # Call llama.cpp via switchboard for tool-augmented execution
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": AGENT_TASK},
        ]

        async with httpx.AsyncClient(timeout=120.0) as client:
            # Try switchboard first (has tool execution loop)
            try:
                resp = await client.post(
                    f"{os.environ.get('SWITCHBOARD_URL', LLAMA_URL)}/v1/chat/completions",
                    json={
                        "messages": messages,
                        "temperature": 0.3,
                        "max_tokens": 4096,
                    },
                    headers={"X-AI-Profile": f"local-{AGENT_ROLE}"},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    content = data["choices"][0]["message"]["content"]
                    state["status"] = "completed"
                    state["result"] = content
                    state["completed_at"] = time.time()
                    if STATE_FILE:
                        Path(STATE_FILE).write_text(json.dumps(state))
                    print(content)
                    return
            except Exception as e:
                print(f"Switchboard failed, trying llama directly: {e}", file=sys.stderr)

            # Fallback: call llama.cpp directly
            resp = await client.post(
                f"{LLAMA_URL}/v1/chat/completions",
                json={
                    "messages": messages,
                    "temperature": 0.3,
                    "max_tokens": 4096,
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                state["status"] = "completed"
                state["result"] = content
                state["completed_at"] = time.time()
                if STATE_FILE:
                    Path(STATE_FILE).write_text(json.dumps(state))
                print(content)
            else:
                raise Exception(f"llama.cpp error: {resp.status_code} {resp.text[:200]}")

    except Exception as e:
        state["status"] = "failed"
        state["error"] = str(e)
        state["completed_at"] = time.time()
        if STATE_FILE:
            Path(STATE_FILE).write_text(json.dumps(state))
        print(json.dumps(state), file=sys.stderr)
        sys.exit(1)

asyncio.run(run())
"""
    proc = subprocess.Popen(
        [sys.executable, "-c", code],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    return proc


# ── Team Orchestration ───────────────────────────────────────────────────────

TEAM_COMPOSITIONS = {
    "code-change": ["planner", "coder", "reviewer"],
    "debug": ["researcher", "coder", "reviewer"],
    "research": ["researcher", "planner"],
    "full": ["planner", "researcher", "coder", "reviewer", "coordinator"],
}


def infer_team(task: str) -> List[str]:
    """Infer which agent roles are needed for a task."""
    task_lower = task.lower()
    if any(kw in task_lower for kw in ["implement", "add feature", "create", "build", "write code"]):
        return TEAM_COMPOSITIONS["code-change"]
    if any(kw in task_lower for kw in ["debug", "fix bug", "error", "crash", "fail"]):
        return TEAM_COMPOSITIONS["debug"]
    if any(kw in task_lower for kw in ["research", "investigate", "analyze", "explore", "audit"]):
        return TEAM_COMPOSITIONS["research"]
    return TEAM_COMPOSITIONS["code-change"]  # default


async def spawn_team(
    task: str,
    roles: Optional[List[str]] = None,
    llama_url: str = "http://127.0.0.1:8080",
    switchboard_url: str = "http://127.0.0.1:8085",
    coordinator_url: str = "http://127.0.0.1:8003",
) -> Dict[str, Any]:
    """Spawn a team of agents for a complex task.

    Returns a dict with team_id, member_ids, and status.
    """
    state = AgentState()
    state.cleanup_dead()

    roles = roles or infer_team(task)
    team_id = str(uuid.uuid4())[:8]

    log.info("Spawning team %s for task: %s", team_id, task[:80])
    log.info("Team roles: %s", roles)

    members = []
    processes = {}

    for role in roles:
        instance = state.register(role, task)
        members.append(instance.to_dict())

        proc = _spawn_agent_process(
            instance, llama_url, switchboard_url, coordinator_url,
        )
        processes[instance.id] = proc

        state.update(
            instance.id,
            pid=proc.pid,
            status="running",
            started_at=datetime.now().isoformat(),
        )
        log.info("  Spawned %s agent %s (PID %d)", role, instance.id, proc.pid)

    team_state = {
        "team_id": team_id,
        "task": task,
        "roles": roles,
        "members": members,
        "status": "running",
        "created_at": datetime.now().isoformat(),
    }

    # Save team state
    team_file = STATE_DIR / f"team-{team_id}.json"
    team_file.write_text(json.dumps(team_state, indent=2))

    return team_state


async def wait_for_team(team_id: str, timeout: float = 300.0) -> Dict[str, Any]:
    """Wait for all agents in a team to complete."""
    team_file = STATE_DIR / f"team-{team_id}.json"
    if not team_file.exists():
        return {"error": f"Team {team_id} not found"}

    team_state = json.loads(team_file.read_text())
    start = time.time()
    state = AgentState()

    while time.time() - start < timeout:
        all_done = True
        results = {}

        for member in team_state["members"]:
            mid = member["id"]
            inst = state.instances.get(mid)
            if inst and inst.status in ("completed", "failed", "killed"):
                results[mid] = inst.to_dict()
            elif inst and inst.status == "running":
                # Check if process is still alive
                agent_state_file = STATE_DIR / f"agent-{mid}.json"
                if agent_state_file.exists():
                    agent_data = json.loads(agent_state_file.read_text())
                    if agent_data.get("status") in ("completed", "failed"):
                        state.update(mid, **agent_data)
                        results[mid] = state.instances[mid].to_dict()
                    else:
                        all_done = False
                else:
                    all_done = False
            else:
                all_done = False

        team_state["results"] = results
        team_state["status"] = "completed" if all_done else "running"
        team_file.write_text(json.dumps(team_state, indent=2))

        if all_done:
            return team_state

        await asyncio.sleep(1.0)

    team_state["status"] = "timeout"
    team_file.write_text(json.dumps(team_state, indent=2))
    return team_state


# ── Status and Monitoring ────────────────────────────────────────────────────

def get_status(instance_id: Optional[str] = None) -> Dict[str, Any]:
    """Get status of agents"""
    state = AgentState()
    state.cleanup_dead()

    if instance_id:
        inst = state.instances.get(instance_id)
        if not inst:
            return {"error": f"Instance {instance_id} not found"}
        result = inst.to_dict()
        # Read latest state from agent's own state file
        agent_file = STATE_DIR / f"agent-{instance_id}.json"
        if agent_file.exists():
            try:
                agent_data = json.loads(agent_file.read_text())
                result["live_state"] = agent_data
            except (json.JSONDecodeError, IOError):
                pass
        return result

    return {
        "active_agents": len(state.get_active()),
        "total_agents": len(state.instances),
        "instances": [i.to_dict() for i in state.get_all()],
    }


def kill_agent(instance_id: str) -> Dict[str, Any]:
    """Kill a running agent"""
    state = AgentState()
    inst = state.instances.get(instance_id)
    if not inst:
        return {"error": f"Instance {instance_id} not found"}

    if inst.pid:
        try:
            os.kill(inst.pid, signal.SIGTERM)
            state.update(instance_id, status="killed", completed_at=datetime.now().isoformat())
            return {"status": "killed", "id": instance_id, "pid": inst.pid}
        except ProcessLookupError:
            state.update(instance_id, status="killed", completed_at=datetime.now().isoformat())
            return {"status": "killed (already dead)", "id": instance_id}

    return {"error": "No PID for this instance"}


def kill_all() -> Dict[str, Any]:
    """Kill all running agents"""
    state = AgentState()
    killed = []
    for inst in state.get_active():
        if inst.pid:
            try:
                os.kill(inst.pid, signal.SIGTERM)
                killed.append(inst.id)
                state.update(inst.id, status="killed", completed_at=datetime.now().isoformat())
            except ProcessLookupError:
                killed.append(inst.id)
                state.update(inst.id, status="killed", completed_at=datetime.now().isoformat())
    return {"killed": killed, "count": len(killed)}


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Agent Spawner — Multi-Agent Team Orchestration")
    sub = parser.add_subparsers(dest="command", required=True)

    # spawn — single agent
    p_spawn = sub.add_parser("spawn", help="Spawn a single agent")
    p_spawn.add_argument("--role", required=True, choices=list(AGENT_ROLES.keys()))
    p_spawn.add_argument("--task", required=True)
    p_spawn.add_argument("--llama-url", default=os.getenv("LLAMA_CPP_URL", "http://127.0.0.1:8080"))
    p_spawn.add_argument("--switchboard-url", default=os.getenv("SWITCHBOARD_URL", "http://127.0.0.1:8085"))
    p_spawn.add_argument("--coordinator-url", default=os.getenv("COORDINATOR_URL", "http://127.0.0.1:8003"))

    # team — spawn a team
    p_team = sub.add_parser("team", help="Spawn an agent team")
    p_team.add_argument("--task", required=True)
    p_team.add_argument("--roles", nargs="*", help="Specific roles (auto-detected if omitted)")
    p_team.add_argument("--wait", action="store_true", help="Wait for team to complete")
    p_team.add_argument("--timeout", type=float, default=300.0)
    p_team.add_argument("--llama-url", default=os.getenv("LLAMA_CPP_URL", "http://127.0.0.1:8080"))
    p_team.add_argument("--switchboard-url", default=os.getenv("SWITCHBOARD_URL", "http://127.0.0.1:8085"))
    p_team.add_argument("--coordinator-url", default=os.getenv("COORDINATOR_URL", "http://127.0.0.1:8003"))

    # status — check agent status
    p_status = sub.add_parser("status", help="Check agent status")
    p_status.add_argument("--id", help="Specific instance ID")

    # kill — kill agent(s)
    p_kill = sub.add_parser("kill", help="Kill agent(s)")
    p_kill.add_argument("--id", help="Specific instance ID (omit for all)")

    args = parser.parse_args()

    if args.command == "spawn":
        state = AgentState()
        instance = state.register(args.role, args.task)
        proc = _spawn_agent_process(instance, args.llama_url, args.switchboard_url, args.coordinator_url)
        state.update(instance.id, pid=proc.pid, status="running", started_at=datetime.now().isoformat())
        print(json.dumps(instance.to_dict(), indent=2))

    elif args.command == "team":
        result = asyncio.run(spawn_team(
            args.task, args.roles, args.llama_url, args.switchboard_url, args.coordinator_url,
        ))
        if args.wait:
            log.info("Waiting for team %s to complete (timeout=%.0fs)...", result["team_id"], args.timeout)
            result = asyncio.run(wait_for_team(result["team_id"], args.timeout))
        print(json.dumps(result, indent=2))

    elif args.command == "status":
        print(json.dumps(get_status(args.id), indent=2))

    elif args.command == "kill":
        if args.id:
            print(json.dumps(kill_agent(args.id), indent=2))
        else:
            print(json.dumps(kill_all(), indent=2))


if __name__ == "__main__":
    main()
