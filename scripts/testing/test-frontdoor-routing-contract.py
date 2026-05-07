#!/usr/bin/env python3
"""Static routing-contract checks for canonical front-door alias defaults."""

from pathlib import Path
import json


ROOT = Path(__file__).resolve().parents[2]


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    route_aliases = load_json(ROOT / "config" / "route-aliases.json")
    discovery = load_json(ROOT / "config" / "ai-stack-agent-discovery.json")
    local_orch = (ROOT / "scripts" / "ai" / "local-orchestrator").read_text(encoding="utf-8")
    config_route = (ROOT / "dashboard" / "backend" / "api" / "routes" / "config.py").read_text(encoding="utf-8")

    aliases = route_aliases.get("aliases") or {}
    discovery_aliases = ((discovery.get("primary_contact") or {}).get("routing_aliases") or {})

    assert_true(aliases.get("Implementation") == "local-tool-calling", "front-door Implementation should default local-first")
    assert_true(aliases.get("Reasoning") == "local-tool-calling", "front-door Reasoning should default local-first")
    assert_true(aliases.get("RemoteCoding") == "remote-coding", "explicit remote coding alias missing")
    assert_true(aliases.get("RemoteReasoning") == "remote-reasoning", "explicit remote reasoning alias missing")
    assert_true(discovery_aliases.get("Implementation") == "local-tool-calling", "discovery manifest Implementation alias drift")
    assert_true(discovery_aliases.get("Reasoning") == "local-tool-calling", "discovery manifest Reasoning alias drift")
    assert_true('AI_LOCAL_FRONTDOOR_IMPLEMENTATION_PROFILE="${AI_LOCAL_FRONTDOOR_IMPLEMENTATION_PROFILE:-local-tool-calling}"' in local_orch, "local-orchestrator implementation default drift")
    assert_true('AI_LOCAL_FRONTDOOR_REASONING_PROFILE="${AI_LOCAL_FRONTDOOR_REASONING_PROFILE:-local-tool-calling}"' in local_orch, "local-orchestrator reasoning default drift")
    assert_true('"source": str(_route_aliases_path())' in config_route, "dashboard config route should report canonical route-alias source")

    print("PASS: front-door routing contract is aligned")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
