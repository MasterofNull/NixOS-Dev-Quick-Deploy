"""
Dynamic agent capability registry for the Unified Agent Orchestration Gateway (Phase 26).

Discovers available agents at runtime from environment variables and service probes.
No model IDs, no client names, and no subscription names are hardcoded here.

Agent sources:
  1. SWITCHBOARD_REMOTE_ALIAS_* env vars (set by Nix, operator-controlled)
  2. Local switchboard profiles at :8085 (Qwen, continue-local, embedded-assist, etc.)
  3. Direct env overrides via AGENT_CAPABILITY_OVERRIDE_* (optional, advanced)

Capability tags (assigned based on profile name patterns, not model names):
  architect     — architecture, policy, long-form synthesis
  implementer   — code patches, test scaffolding, short execution tasks
  reviewer      — deterministic acceptance gate, diff review
  domain:nixos  — NixOS module / flake expertise
  domain:python — Python implementation slices
  domain:security — security audit, secrets, CVE triage
"""

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Set

import httpx

logger = logging.getLogger("hybrid-coordinator")

# ---------------------------------------------------------------------------
# Agent model
# ---------------------------------------------------------------------------

@dataclass
class AgentCapability:
    agent_id: str             # stable opaque ID (not a model name)
    profile: str              # switchboard profile name or alias key
    capabilities: List[str]   # tags: architect, implementer, reviewer, domain:*
    endpoint: str             # base URL (switchboard, etc.)
    source: str               # "local" | "remote"
    last_health_ms: Optional[float] = None   # None = not yet checked
    available: bool = True

    def has_capability(self, tag: str) -> bool:
        return tag in self.capabilities

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Capability heuristics — no hardcoded model names
# ---------------------------------------------------------------------------

# Profile-name fragment → capability tags
_PROFILE_CAPABILITY_MAP: List[tuple] = [
    ("reasoning",   ["architect"]),
    ("agent",       ["implementer", "architect"]),
    ("coder",       ["implementer"]),
    ("coding",      ["implementer"]),
    ("codex",       ["implementer", "reviewer"]),
    ("claude",      ["architect", "reviewer"]),
    ("local",       ["implementer"]),
    ("embedded",    ["implementer"]),
    ("gemini",      ["architect"]),
    ("remote",      ["architect", "implementer"]),
    ("free",        ["implementer"]),
]

_DOMAIN_PROFILE_MAP: List[tuple] = [
    ("nix",      "domain:nixos"),
    ("python",   "domain:python"),
    ("security", "domain:security"),
    ("trading",  "domain:trading"),
    ("design",   "domain:design"),
]


def _infer_capabilities(profile: str) -> List[str]:
    caps: Set[str] = set()
    lower = profile.lower()
    for fragment, tags in _PROFILE_CAPABILITY_MAP:
        if fragment in lower:
            caps.update(tags)
    for fragment, domain_tag in _DOMAIN_PROFILE_MAP:
        if fragment in lower:
            caps.add(domain_tag)
    if not caps:
        caps.add("implementer")
    return sorted(caps)


# ---------------------------------------------------------------------------
# Registry state
# ---------------------------------------------------------------------------

_agents: Dict[str, AgentCapability] = {}
_last_refresh: float = 0.0
_REFRESH_TTL = 120.0  # re-probe every 2 minutes

_switchboard_url: str = "http://127.0.0.1:8085"


def init(
    switchboard_url: Optional[str] = None,
) -> None:
    global _switchboard_url
    _switchboard_url = switchboard_url or os.environ.get(
        "SWITCHBOARD_URL", "http://127.0.0.1:8085"
    )
    _seed_from_env()


def _seed_from_env() -> None:
    """Seed agents from SWITCHBOARD_REMOTE_ALIAS_* and known local profiles."""
    # Local switchboard profiles (always present)
    local_profiles = [
        ("local-agent",       "http://127.0.0.1:8085", "local"),
        ("continue-local",    "http://127.0.0.1:8085", "local"),
        ("embedded-assist",   "http://127.0.0.1:8085", "local"),
        ("local-tool-calling","http://127.0.0.1:8085", "local"),
        ("remote-reasoning",  "http://127.0.0.1:8085", "remote"),
        ("remote-coding",     "http://127.0.0.1:8085", "remote"),
        ("remote-gemini",     "http://127.0.0.1:8085", "remote"),
        ("remote-default",    "http://127.0.0.1:8085", "remote"),
    ]
    for profile, endpoint, source in local_profiles:
        agent_id = f"{source}:{profile}"
        _agents[agent_id] = AgentCapability(
            agent_id=agent_id,
            profile=profile,
            capabilities=_infer_capabilities(profile),
            endpoint=endpoint,
            source=source,
        )

    # Remote aliases from env (operator-controlled, set by Nix)
    for key, value in os.environ.items():
        if key.startswith("SWITCHBOARD_REMOTE_ALIAS_"):
            alias_name = key[len("SWITCHBOARD_REMOTE_ALIAS_"):].lower().replace("_", "-")
            agent_id = f"remote-alias:{alias_name}"
            _agents[agent_id] = AgentCapability(
                agent_id=agent_id,
                profile=alias_name,
                capabilities=_infer_capabilities(alias_name),
                endpoint=_switchboard_url,
            source="remote",
        )

    # 4. Global NPM/system CLIs (gemini, pi)
    import shutil
    for cli_bin in ("gemini", "pi"):
        if shutil.which(cli_bin):
            agent_id = f"system:{cli_bin}"
            _agents[agent_id] = AgentCapability(
                agent_id=agent_id,
                profile=cli_bin,
                capabilities=_infer_capabilities(cli_bin),
                endpoint="stdio", # Placeholder
                source="system-cli",
            )

    logger.info("agent_capability_registry: seeded %d agents from env", len(_agents))


async def _probe_agent_health(agent: AgentCapability) -> bool:
    """Quick health check — marks agent unavailable if unreachable."""
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            t0 = time.monotonic()
            if "8085" in agent.endpoint:
                resp = await client.get(f"{agent.endpoint}/v1/models")
            else:
                resp = await client.get(f"{agent.endpoint}/health")
            agent.last_health_ms = (time.monotonic() - t0) * 1000
            agent.available = resp.status_code < 500
    except Exception:
        agent.available = False
        agent.last_health_ms = None
    return agent.available


async def refresh(force: bool = False) -> None:
    """Re-seed from env and probe agent health. Throttled by TTL."""
    global _last_refresh
    now = time.time()
    if not force and (now - _last_refresh) < _REFRESH_TTL:
        return
    _seed_from_env()
    tasks = [_probe_agent_health(a) for a in _agents.values()]
    await asyncio.gather(*tasks, return_exceptions=True)
    _last_refresh = now
    available = sum(1 for a in _agents.values() if a.available)
    logger.info("agent_capability_registry: refreshed — %d/%d available", available, len(_agents))


# ---------------------------------------------------------------------------
# Query interface
# ---------------------------------------------------------------------------

def get_all() -> List[AgentCapability]:
    return list(_agents.values())


def get_available() -> List[AgentCapability]:
    return [a for a in _agents.values() if a.available]


def find_by_capability(cap: str, prefer_local: bool = True) -> List[AgentCapability]:
    """Return available agents with the given capability, local-first by default."""
    matches = [a for a in _agents.values() if a.available and a.has_capability(cap)]
    if prefer_local:
        matches.sort(key=lambda a: (0 if a.source == "local" else 1))
    return matches


def best_agent_for(
    capability: str,
    domain: Optional[str] = None,
    prefer_local: bool = True,
) -> Optional[AgentCapability]:
    """Return the highest-priority available agent for a capability + optional domain."""
    if domain:
        domain_tag = f"domain:{domain}"
        domain_matches = [
            a for a in _agents.values()
            if a.available and a.has_capability(capability) and a.has_capability(domain_tag)
        ]
        if domain_matches:
            domain_matches.sort(key=lambda a: (0 if a.source == "local" else 1))
            return domain_matches[0]
    candidates = find_by_capability(capability, prefer_local=prefer_local)
    return candidates[0] if candidates else None


def describe() -> Dict[str, Any]:
    """Summary for API/MCP responses."""
    total = len(_agents)
    available = sum(1 for a in _agents.values() if a.available)
    return {
        "total_agents": total,
        "available_agents": available,
        "agents": [a.to_dict() for a in _agents.values()],
        "last_refresh": _last_refresh,
    }
