import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

# Domains → team routing mapping per Phase 26 spec
DOMAIN_TEAM_ROUTES = {
    "nixos": ["architect:remote-reasoning", "implementer:local-agent"],
    "python": ["implementer:codex-cli|qwen-local", "reviewer:self"],
    "security": ["architect:remote-reasoning", "auditor:local-agent"],
    "trading": ["tradingagents:team_via_/trading/*"],
    "design": ["impeccable:team_via_/agent/intake?domain=design"],
    "infra": ["implementer:local-agent", "reviewer:self"],
    "general": ["default:local-agent"]
}

def classify_domain(task_description: str, hint: str = "general") -> str:
    """Classify the domain based on the task description and hints."""
    if hint != "general" and hint in DOMAIN_TEAM_ROUTES:
        return hint

    desc_lower = task_description.lower()
    if "nixos" in desc_lower or "flake" in desc_lower:
        return "nixos"
    if "python" in desc_lower or ".py" in desc_lower or "fastapi" in desc_lower:
        return "python"
    if "security" in desc_lower or "vulnerability" in desc_lower or "audit" in desc_lower:
        return "security"
    if "trade" in desc_lower or "market" in desc_lower:
        return "trading"
    if "design" in desc_lower or "css" in desc_lower or "ui" in desc_lower:
        return "design"
    if "infra" in desc_lower or "deploy" in desc_lower or "systemd" in desc_lower:
        return "infra"

    return "general"

def route_to_team(domain: str) -> List[str]:
    """Return the team of agents assigned to the specific domain."""
    routes = DOMAIN_TEAM_ROUTES.get(domain, DOMAIN_TEAM_ROUTES["general"])
    logger.info(f"Routed domain '{domain}' to team: {routes}")
    return routes
