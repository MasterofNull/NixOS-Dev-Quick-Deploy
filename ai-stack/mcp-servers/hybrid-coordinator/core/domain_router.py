"""
Domain classifier and team router for the Unified Agent Orchestration Gateway (Phase 26).

After the PLAN phase, classifies the task domain and selects the appropriate agent
team composition. Domain routing is keyword + context-based — no model-name coupling.

Domains:
  nixos    — NixOS modules, flake config, systemd, options.nix
  python   — ai-stack Python services, FastAPI, aiohttp
  security — auth, secrets, CVE, audit, hardening
  trading  — trading analysis, market data, finance
  design   — UI/UX, frontend, typography, impeccable
  infra    — CI/CD, GitHub, deployment, monitoring
  general  — catch-all for unclassified tasks

Each domain maps to a TeamComposition: ordered list of (role, capability_tag, prefer_local).
The DELEGATE phase iterates the team and calls agent_capability_registry.best_agent_for()
for each role — no hardcoded agent IDs.
"""

import logging
import re
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("hybrid-coordinator")

# ---------------------------------------------------------------------------
# Domain keyword patterns
# ---------------------------------------------------------------------------

_DOMAIN_PATTERNS: List[Tuple[str, List[str]]] = [
    ("nixos", [
        r"\bnix\b", r"nixos", r"flake", r"nix\s+module", r"options\.nix",
        r"home-manager", r"systemd\s+service", r"mkDefault", r"mkForce",
        r"nix/modules", r"nix/hosts", r"nixos-rebuild", r"deploy",
    ]),
    ("security", [
        r"\bsecret", r"\bauth\b", r"token\b", r"\bCVE\b", r"\bauditor\b",
        r"vulnerability", r"hardening", r"permission", r"credential",
        r"exploit", r"injection", r"xss\b", r"csrf\b", r"sql\s+injection",
    ]),
    ("trading", [
        r"trading", r"trade\b", r"market", r"stock\b", r"finance",
        r"portfolio", r"fundamental", r"sentiment", r"bull\b", r"bear\b",
        r"analyst", r"ticker\b", r"price\b.*action",
    ]),
    ("design", [
        r"ui\b", r"ux\b", r"frontend", r"typography", r"color\b",
        r"impeccable", r"animation", r"layout", r"component", r"css\b",
        r"visual", r"poster", r"design\b",
    ]),
    ("python", [
        r"\.py\b", r"python\b", r"fastapi", r"aiohttp", r"async\s+def",
        r"ai-stack", r"hybrid-coordinator", r"handler", r"endpoint",
        r"pytest", r"import\s+\w", r"class\b.*:",
    ]),
    ("infra", [
        r"ci/?cd", r"github\s+action", r"\.yml\b", r"deploy\b", r"pipeline",
        r"prometheus", r"grafana", r"monitoring", r"alert\b", r"terraform",
        r"docker", r"container", r"kubernetes",
    ]),
]

# ---------------------------------------------------------------------------
# Team compositions
# ---------------------------------------------------------------------------

@dataclass
class AgentRole:
    role: str           # architect | implementer | reviewer | specialist
    capability: str     # matches agent_capability_registry capability tag
    prefer_local: bool  # route to local switchboard when possible
    description: str    # human-readable, not shown to agent


@dataclass
class TeamComposition:
    domain: str
    roles: List[AgentRole]
    workflow_hint: str           # e.g., "Use /trading/analyze for financial data"
    tooling_hints: List[str]     # recommended tools for this domain
    delegation_strategy: str     # sequential | parallel | self


# Default team compositions per domain — no model IDs, only capability tags
_TEAM_COMPOSITIONS: Dict[str, TeamComposition] = {
    "nixos": TeamComposition(
        domain="nixos",
        roles=[
            AgentRole("architect", "architect", prefer_local=False,
                      description="Design Nix module structure and option contracts"),
            AgentRole("implementer", "implementer", prefer_local=True,
                      description="Write and validate Nix module code"),
            AgentRole("reviewer", "reviewer", prefer_local=True,
                      description="Check for hardcoded ports/URLs, policy compliance"),
        ],
        workflow_hint="Always validate with `nix-instantiate --parse` before commit.",
        tooling_hints=["simulate_nix_change", "validate_service_config", "hybrid_search"],
        delegation_strategy="sequential",
    ),
    "python": TeamComposition(
        domain="python",
        roles=[
            AgentRole("implementer", "implementer", prefer_local=True,
                      description="Write Python implementation slices"),
            AgentRole("reviewer", "reviewer", prefer_local=True,
                      description="py_compile + style + logic review"),
        ],
        workflow_hint="Run `python3 -m py_compile` on every changed file before commit.",
        tooling_hints=["hybrid_search", "workflow_plan", "qa_check"],
        delegation_strategy="sequential",
    ),
    "security": TeamComposition(
        domain="security",
        roles=[
            AgentRole("architect", "architect", prefer_local=False,
                      description="Risk analysis, CVE triage, policy design"),
            AgentRole("implementer", "implementer", prefer_local=True,
                      description="Implement fixes, harden configs"),
            AgentRole("reviewer", "reviewer", prefer_local=False,
                      description="Verify no secrets leaked, no new vulns introduced"),
        ],
        workflow_hint="Never expose /run/secrets/ paths in output. Use safe_command_executor.",
        tooling_hints=["hybrid_search", "qa_check", "workflow_plan"],
        delegation_strategy="sequential",
    ),
    "trading": TeamComposition(
        domain="trading",
        roles=[
            AgentRole("specialist", "domain:trading", prefer_local=True,
                      description="5-team tradingagents pipeline via /trading/*"),
        ],
        workflow_hint="Route to /trading/analyze for market data, /trading/debate for multi-agent.",
        tooling_hints=["trading_analyze", "trading_forecast", "trading_tools"],
        delegation_strategy="parallel",
    ),
    "design": TeamComposition(
        domain="design",
        roles=[
            AgentRole("specialist", "domain:design", prefer_local=False,
                      description="Impeccable design intelligence via /impeccable/*"),
        ],
        workflow_hint="Use impeccable_design tool for OKLCH color, typography, and motion.",
        tooling_hints=["impeccable_design", "hybrid_search"],
        delegation_strategy="self",
    ),
    "infra": TeamComposition(
        domain="infra",
        roles=[
            AgentRole("implementer", "implementer", prefer_local=True,
                      description="CI/CD config, deploy scripts, monitoring setup"),
            AgentRole("reviewer", "reviewer", prefer_local=True,
                      description="Validate pipeline correctness, no credential leaks"),
        ],
        workflow_hint="Test with dry-run flags before applying any pipeline changes.",
        tooling_hints=["hybrid_search", "workflow_plan", "qa_check"],
        delegation_strategy="sequential",
    ),
    "general": TeamComposition(
        domain="general",
        roles=[
            AgentRole("implementer", "implementer", prefer_local=True,
                      description="General-purpose task execution via local-agent profile"),
        ],
        workflow_hint="Use local-agent switchboard profile for general tasks.",
        tooling_hints=["hybrid_search", "workflow_plan"],
        delegation_strategy="self",
    ),
}


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

def classify_domain(prompt: str, context: Optional[Dict[str, Any]] = None) -> str:
    """Classify prompt into a domain using keyword patterns.

    Returns the highest-confidence domain name, or 'general' as fallback.
    Context dict may include 'existing_plans', 'relevant_files', 'domain' hint.
    """
    # Explicit domain override from upstream phases
    if context and context.get("domain"):
        return context["domain"]

    text = prompt.lower()
    if context:
        for key in ("existing_plans", "prd_scope", "intent_summary"):
            extra = context.get(key, "")
            if isinstance(extra, str):
                text += " " + extra.lower()
            elif isinstance(extra, list):
                text += " " + " ".join(str(x) for x in extra).lower()

    scores: Dict[str, int] = {}
    for domain, patterns in _DOMAIN_PATTERNS:
        score = sum(1 for pat in patterns if re.search(pat, text, re.IGNORECASE))
        if score > 0:
            scores[domain] = score

    if not scores:
        return "general"

    # Pick highest score; break ties by order in _DOMAIN_PATTERNS
    best = max(scores, key=lambda d: scores[d])
    logger.debug("domain_router: classified prompt as '%s' (scores=%s)", best, scores)
    return best


def get_team(domain: str) -> TeamComposition:
    """Return the TeamComposition for a domain, falling back to 'general'."""
    return _TEAM_COMPOSITIONS.get(domain, _TEAM_COMPOSITIONS["general"])


def route(
    prompt: str,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Classify domain and return routing decision for the DELEGATE phase.

    Returns a dict with domain, team_composition, and per-role agent recommendations.
    Caller must resolve actual agents via agent_capability_registry.best_agent_for().
    """
    domain = classify_domain(prompt, context)
    team = get_team(domain)
    return {
        "domain": domain,
        "delegation_strategy": team.delegation_strategy,
        "workflow_hint": team.workflow_hint,
        "tooling_hints": team.tooling_hints,
        "roles": [
            {
                "role": r.role,
                "capability": r.capability,
                "prefer_local": r.prefer_local,
                "description": r.description,
            }
            for r in team.roles
        ],
    }


def describe() -> Dict[str, Any]:
    """Summary for API/MCP responses."""
    return {
        "domains": list(_TEAM_COMPOSITIONS.keys()),
        "teams": {d: asdict(t) for d, t in _TEAM_COMPOSITIONS.items()},
    }
