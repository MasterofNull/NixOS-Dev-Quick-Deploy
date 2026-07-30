#!/usr/bin/env python3
"""Validate the project-scoped native Codex sub-agent configuration."""

import copy
from pathlib import Path
import tomllib


ROOT = Path(__file__).resolve().parents[2]
PROJECT_CONFIG = ROOT / ".codex" / "config.toml"
AGENT_DIR = ROOT / ".codex" / "agents"
EXPECTED_AGENTS = {
    "aq-implementer.toml": {
        "name": "aq_implementer",
        "description": "Economical implementation worker for an exact, monitored AQ-OS slice.",
        "model": "gpt-5.6-terra",
        "effort": "medium",
        "sandbox": "workspace-write",
    },
    "aq-reviewer.toml": {
        "name": "aq_reviewer",
        "description": "Independent flagship reviewer for exact-subject AQ-OS acceptance.",
        "model": "gpt-5.6-sol",
        "effort": "high",
        "sandbox": "read-only",
    },
    "aq-explorer.toml": {
        "name": "aq_explorer",
        "description": "Read-only economical explorer for bounded evidence gathering.",
        "model": "gpt-5.6-terra",
        "effort": "low",
        "sandbox": "read-only",
    },
}
EXPECTED_ROLE_DECLARATIONS = {
    contract["name"]: {
        "description": contract["description"],
        "config_file": f"agents/{filename}",
    }
    for filename, contract in EXPECTED_AGENTS.items()
}


def load_toml(path: Path) -> dict:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def validate_project(project: dict) -> None:
    agents = project.get("agents")
    assert isinstance(agents, dict), "project config must define [agents]"
    assert agents.get("enabled") is True
    assert agents.get("max_concurrent_threads_per_session") == 3
    assert agents.get("default_subagent_model") == "gpt-5.6-terra"
    assert agents.get("default_subagent_reasoning_effort") == "medium"
    assert agents.get("interrupt_message") is True
    scalar_keys = {
        "enabled",
        "max_concurrent_threads_per_session",
        "default_subagent_model",
        "default_subagent_reasoning_effort",
        "interrupt_message",
    }
    assert set(agents) == scalar_keys | set(EXPECTED_ROLE_DECLARATIONS)
    for role_name, expected in EXPECTED_ROLE_DECLARATIONS.items():
        assert agents.get(role_name) == expected
    assert "features" not in project, "project layer must not duplicate global features"
    assert "projects" not in project, "project layer must not declare its own trust"


def validate_agent(filename: str, data: dict) -> None:
    contract = EXPECTED_AGENTS[filename]
    assert data.get("name") == contract["name"]
    assert isinstance(data.get("description"), str) and data["description"].strip()
    instructions = data.get("developer_instructions")
    assert isinstance(instructions, str) and instructions.strip()
    assert data.get("model") == contract["model"]
    assert data.get("model_reasoning_effort") == contract["effort"]
    assert data.get("sandbox_mode") == contract["sandbox"]
    child_agents = data.get("agents")
    assert isinstance(child_agents, dict), f"{filename} must define child-local [agents]"
    assert child_agents.get("enabled") is False, f"{filename} must not spawn sub-agents"
    assert set(child_agents) == {"enabled"}, f"{filename} child-agent policy must stay minimal"
    lowered = instructions.lower()
    assert "commit" in lowered and "scope" in lowered
    assert "route agents" in lowered


def assert_rejected(mutator, project: dict, agents: dict[str, dict], label: str) -> None:
    mutated_project = copy.deepcopy(project)
    mutated_agents = copy.deepcopy(agents)
    mutator(mutated_project, mutated_agents)
    try:
        validate_project(mutated_project)
        for filename, data in mutated_agents.items():
            validate_agent(filename, data)
    except AssertionError:
        return
    raise AssertionError(f"adversarial configuration was accepted: {label}")


def main() -> int:
    project = load_toml(PROJECT_CONFIG)
    validate_project(project)
    actual_files = {path.name for path in AGENT_DIR.glob("*.toml")}
    assert actual_files == set(EXPECTED_AGENTS), f"unexpected custom agent inventory: {actual_files}"
    agent_data = {filename: load_toml(AGENT_DIR / filename) for filename in EXPECTED_AGENTS}
    for filename, data in agent_data.items():
        validate_agent(filename, data)

    assert_rejected(
        lambda cfg, _: cfg["agents"].pop("interrupt_message"),
        project,
        agent_data,
        "missing project field",
    )
    assert_rejected(
        lambda cfg, _: cfg["agents"].pop("aq_reviewer"),
        project,
        agent_data,
        "missing custom role declaration",
    )
    assert_rejected(
        lambda cfg, _: cfg["agents"]["aq_implementer"].update(
            config_file="/tmp/untrusted-agent.toml"
        ),
        project,
        agent_data,
        "role config escapes project declaration",
    )
    assert_rejected(
        lambda cfg, _: cfg["agents"]["aq_explorer"].update(
            description="generic helper"
        ),
        project,
        agent_data,
        "role declaration description drift",
    )
    assert_rejected(
        lambda _, children: children["aq-reviewer.toml"].pop("sandbox_mode"),
        project,
        agent_data,
        "missing custom-agent field",
    )
    assert_rejected(
        lambda _, children: children["aq-explorer.toml"].pop("agents"),
        project,
        agent_data,
        "missing child-agent policy",
    )
    assert_rejected(
        lambda _, children: children["aq-reviewer.toml"].update(sandbox_mode="workspace-write"),
        project,
        agent_data,
        "writable reviewer",
    )
    assert_rejected(
        lambda _, children: children["aq-explorer.toml"].update(sandbox_mode="workspace-write"),
        project,
        agent_data,
        "writable explorer",
    )
    assert_rejected(
        lambda cfg, _: cfg["agents"].update(max_concurrent_threads_per_session=4),
        project,
        agent_data,
        "excess concurrency",
    )
    assert_rejected(
        lambda cfg, _: cfg["agents"].update(default_subagent_model="gpt-5.6-sol"),
        project,
        agent_data,
        "non-economical default",
    )
    assert_rejected(
        lambda _, children: children["aq-implementer.toml"]["agents"].update(enabled=True),
        project,
        agent_data,
        "child agents enabled",
    )
    assert_rejected(
        lambda cfg, _: cfg.update(features={"codex_hooks": True}),
        project,
        agent_data,
        "deprecated feature key",
    )
    assert_rejected(
        lambda cfg, _: cfg.update(projects={"/": {"trust_level": "trusted"}}),
        project,
        agent_data,
        "root trust",
    )

    print("PASS: native Codex sub-agent configuration is scoped and role-correct")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
