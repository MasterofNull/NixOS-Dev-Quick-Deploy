"""
operator_intelligence.py — Operator Intelligence Bridge (OIB)

Phase 164: Human upskilling system that surfaces actionable insights, research
challenges, and validation hooks to the operator at natural workflow break points.

Design doc: .agents/designs/OPERATOR-INTELLIGENCE-BRIDGE.md
MIC-G integration: Chilling Effect detection (P6 in MIC-G threat catalogue)
"""
from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger("hybrid-coordinator")

# ---------------------------------------------------------------------------
# Knowledge base — domain insight templates
# ---------------------------------------------------------------------------

# AI training cutoff reminder (update when model changes)
_AI_CUTOFF = "Aug 2025"

DOMAIN_INSIGHT_TEMPLATES: dict[str, list[dict[str, str]]] = {
    "nixos": [
        {
            "concept": "ProtectHome= and ReadWritePaths= interaction in systemd services",
            "why_template": "You worked with {work} involving systemd service sandboxing.",
            "research_hook": "When does ProtectHome=read-only vs ProtectHome=true make sense? What are the security tradeoffs when you add ReadWritePaths=?",
            "validation_challenge": "Grep ReadWritePaths in nix/modules/services/*.nix — can you explain why each entry is needed?",
            "staleness_warning": "",
            "triggers": ["ProtectHome", "ReadWritePaths", "systemd", "sandbox"],
        },
        {
            "concept": "NixOS module option types and mkIf vs mkForce merge semantics",
            "why_template": "You modified NixOS module options in {work}.",
            "research_hook": "When does the // operator break NixOS config vs. lib.mkMerge? What's the difference between lib.mkForce and lib.mkDefault?",
            "validation_challenge": "Find a place in the config where lib.mkIf is used — could lib.mkDefault or // cause a silent merge conflict there?",
            "staleness_warning": "",
            "triggers": ["mkIf", "mkForce", "lib.mk", "NixOS module", "flake"],
        },
        {
            "concept": "AppArmor profile mode bits: ix vs Ux vs Px and NoNewPrivileges interaction",
            "why_template": "You worked with AppArmor rules in {work}.",
            "research_hook": "Why does NoNewPrivileges=true make Ux transitions return EPERM instead of the expected AppArmor error? When should you use ix vs Px?",
            "validation_challenge": "Find a service in the config using NoNewPrivileges=true — does it try to spawn subprocesses? Are those covered with ix rules?",
            "staleness_warning": "",
            "triggers": ["AppArmor", "apparmor", "NoNewPrivileges", "ix", "Ux", "Px"],
        },
    ],
    "python-async": [
        {
            "concept": "Blocking I/O in async handlers causes event loop starvation",
            "why_template": "You worked with async Python handlers in {work}.",
            "research_hook": "What happens to all other concurrent requests when one FastAPI handler does synchronous file I/O? How does asyncio.to_thread() differ from loop.run_in_executor()?",
            "validation_challenge": "Pick a route handler in hybrid-coordinator — does it have any synchronous I/O? If so, is it wrapped in asyncio.to_thread()?",
            "staleness_warning": "",
            "triggers": ["async def", "await", "FastAPI", "aiohttp", "asyncio"],
        },
        {
            "concept": "aiohttp ClientSession scoping — per-request vs. singleton",
            "why_template": "You worked with httpx or aiohttp in {work}.",
            "research_hook": "Why is creating a new aiohttp ClientSession per request an anti-pattern? What TCP connection pool implications does it have?",
            "validation_challenge": "Search the coordinator for 'async with httpx.AsyncClient' — how many places create a new client per call vs. reuse a shared client?",
            "staleness_warning": "",
            "triggers": ["httpx", "aiohttp", "ClientSession", "AsyncClient"],
        },
    ],
    "ai-ml": [
        {
            "concept": "llama.cpp MTP (Multi-Token Prediction) speculative decoding mechanics",
            "why_template": "The current local model uses --spec-type draft-mtp (from {work} context).",
            "research_hook": "How does MTP differ from classic speculative decoding with a separate draft model? What determines when the draft tokens are accepted or rejected?",
            "validation_challenge": "Run: llama-server --help 2>&1 | grep -E 'spec|draft' — do the current flags match what's documented in LOCAL-AGENT.md?",
            "staleness_warning": f"AI training cutoff: {_AI_CUTOFF}. llama.cpp MTP support is actively developed. Verify against live binary and changelog.",
            "triggers": ["MTP", "speculative", "spec-type", "draft-mtp", "llama.cpp"],
        },
        {
            "concept": "RAG score threshold calibration — BGE-M3 semantic similarity vs keyword matching",
            "why_template": "You worked with RAG queries or AIDB in {work}.",
            "research_hook": "Why does a score threshold of 0.7 return no results for sparse collections while 0.45 works? How does BGE-M3 score distribution differ from OpenAI ada-002?",
            "validation_challenge": "Query AIDB directly: what is the distribution of scores in the 'solved_issues' collection? Is 0.45 the right threshold for your collection density?",
            "staleness_warning": f"AI training cutoff: {_AI_CUTOFF}. BGE-M3 behavior and calibration may differ between versions. Check the current model version in use.",
            "triggers": ["RAG", "Qdrant", "embedding", "score_threshold", "BGE", "vector search"],
        },
        {
            "concept": "Qwen3 thinking tokens and the enable_thinking flag in chat_template_kwargs",
            "why_template": "You worked with local model inference configuration in {work}.",
            "research_hook": "Why does top-level 'enable_thinking: false' get silently ignored by llama.cpp while chat_template_kwargs works? What part of the OpenAI API spec is this using?",
            "validation_challenge": "Send a test request to llama.cpp without the chat_template_kwargs field — does the response have empty content? This validates the flag is actually needed.",
            "staleness_warning": "",
            "triggers": ["enable_thinking", "chat_template_kwargs", "Qwen3", "thinking"],
        },
        {
            "concept": "frequency_penalty cumulative effect on token logits in dense JSON output",
            "why_template": "You worked with llama.cpp payload configuration in {work}.",
            "research_hook": "How does frequency_penalty differ from repeat_penalty? Why does frequency_penalty=0.05 effectively ban quotation marks in a 300-line JSON schema?",
            "validation_challenge": "Generate a 50-line JSON response with frequency_penalty=0.05 vs 0.0 — do you observe early truncation in the first case?",
            "staleness_warning": "",
            "triggers": ["frequency_penalty", "repeat_penalty", "logit", "JSON output"],
        },
    ],
    "security": [
        {
            "concept": "Prompt injection via tool results — the data/control plane boundary",
            "why_template": "You worked with AI agent tool calls in {work}.",
            "research_hook": "How is prompt injection via a tool result different from traditional XSS? What makes it particularly dangerous when the agent has shell/file tool access?",
            "validation_challenge": "Check agent_executor.py — does it sanitize tool results before passing them to the next LLM turn? What patterns would it need to catch?",
            "staleness_warning": f"AI training cutoff: {_AI_CUTOFF}. Prompt injection research is active. Check OWASP LLM Top 10 for current guidance.",
            "triggers": ["tool result", "injection", "agent", "prompt injection", "tool call"],
        },
        {
            "concept": "LoRA/PEFT adapter supply chain risk — pickle deserialization and parent_library",
            "why_template": "You worked with model loading or adapter configuration in {work}.",
            "research_hook": "Why can a malicious adapter_config.json field lead to arbitrary code execution on torch.load()? What does 'safetensors only' actually prevent?",
            "validation_challenge": "Check if any local model configs reference non-safetensors formats. Run: find /var/lib -name '*.bin' -o -name '*.pt' 2>/dev/null | head -5",
            "staleness_warning": f"AI training cutoff: {_AI_CUTOFF}. CVEs for ML model loading are actively published. Check NIST NVD for recent torch/transformers advisories.",
            "triggers": ["adapter", "LoRA", "PEFT", "safetensors", "model loading"],
        },
    ],
    "ai-safety": [
        {
            "concept": "Invisible provider guardrails via RLHF — the 'Fable 5' suppression pattern",
            "why_template": "You worked with remote model routing or MIC-G design in {work}.",
            "research_hook": "How can you detect whether a refusal is from a prompt-level safety filter vs. embedded RLHF weight-level steering? What behavioral signatures differ?",
            "validation_challenge": "Run the technical capability probe set (from MIC-G §3.2) against a remote lane — does the lane return technical answers or preach?",
            "staleness_warning": f"AI training cutoff: {_AI_CUTOFF}. This is an emerging research area. Check recent arxiv papers on 'RLHF steering' and 'alignment tax'.",
            "triggers": ["RLHF", "refusal", "suppression", "provider", "guardrail", "MIC-G"],
        },
        {
            "concept": "The Chilling Effect — operator self-censorship in response to AI refusals",
            "why_template": "The system is monitoring prompt specificity trends (MIC-G P6 integration).",
            "research_hook": "How would you measure whether your own prompts have become less specific over time? What prompt patterns indicate self-censorship vs. genuine task simplification?",
            "validation_challenge": "Compare your last 5 prompts to your first 5 in this repo — has technical keyword density increased or decreased? Are you asking for more or less specificity?",
            "staleness_warning": "",
            "triggers": ["chilling effect", "self-censorship", "prompt quality", "refusal"],
        },
    ],
    "systems": [
        {
            "concept": "Fire-and-forget async tasks vs. awaitable futures — knowing which one to use",
            "why_template": "You worked with background task patterns in {work}.",
            "research_hook": "When asyncio.create_task() is used for a memory write that returns 'queued' — what happens if the coordinator shuts down mid-write? Is the data lost?",
            "validation_challenge": "Find a create_task() call in the coordinator — what happens to that task if the event loop exits before it completes?",
            "staleness_warning": "",
            "triggers": ["create_task", "fire-and-forget", "background", "task", "queued"],
        },
    ],
}

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class InsightCard:
    id: str
    domain: str
    concept: str
    why_it_matters: str
    research_hook: str
    validation_challenge: str
    staleness_warning: str
    source_work: str
    priority: str
    surfaced_at: str
    status: str = "new"


@dataclass
class OperatorKnowledgeProfile:
    session_count: int = 0
    domains_engaged: dict[str, dict] = field(default_factory=dict)
    open_research_threads: list[dict] = field(default_factory=list)
    prompt_specificity_trend: list[float] = field(default_factory=list)
    chilling_effect_alerts: int = 0
    insight_cards_surfaced: int = 0
    insight_cards_researched: int = 0
    last_updated: str = ""


# ---------------------------------------------------------------------------
# Profile persistence
# ---------------------------------------------------------------------------

def _profile_path() -> Path:
    import os as _os
    data_dir = _os.environ.get("AI_STACK_DATA_DIR", "").strip()
    if data_dir:
        # Service context: write to the coordinator's own state directory (ai-hybrid owned)
        return Path(data_dir) / "hybrid" / "operator-knowledge-profile.json"
    # Local dev fallback: REPO_ROOT or __file__ heuristic
    repo_root = Path(_os.environ.get("REPO_ROOT", str(Path(__file__).resolve().parents[5])))
    return repo_root / ".agent" / "collaboration" / "operator-knowledge-profile.json"


def load_operator_profile() -> OperatorKnowledgeProfile:
    p = _profile_path()
    if p.exists():
        try:
            data = json.loads(p.read_text())
            return OperatorKnowledgeProfile(**data)
        except Exception:
            pass
    return OperatorKnowledgeProfile()


def save_operator_profile(profile: OperatorKnowledgeProfile) -> None:
    p = _profile_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(asdict(profile), indent=2))


# ---------------------------------------------------------------------------
# Topic extraction from session context
# ---------------------------------------------------------------------------

_DOMAIN_KEYWORD_MAP: dict[str, list[str]] = {
    "nixos": ["nix", ".nix", "NixOS", "nixos", "flake", "rebuild", "systemd", "AppArmor",
              "apparmor", "tmpfiles", "module", "options.nix", "ProtectHome", "ReadWritePaths"],
    "python-async": ["async def", "await", "asyncio", "FastAPI", "fastapi", "aiohttp",
                     "httpx", "uvicorn", "starlette", "to_thread", "run_in_executor"],
    "ai-ml": ["llama", "llama.cpp", "Qwen", "embedding", "RAG", "Qdrant", "vector",
              "inference", "token", "model", "GGUF", "LoRA", "PEFT", "safetensors",
              "frequency_penalty", "chat_template", "enable_thinking"],
    "security": ["AppArmor", "apparmor", "auth", "injection", "sanitize", "OWASP",
                 "permission", "privilege", "sandbox", "trust", "secret", "key"],
    "ai-safety": ["refusal", "RLHF", "guardrail", "suppression", "alignment", "MIC-G",
                  "adapter", "backdoor", "chilling", "steering", "provider"],
    "systems": ["coordinator", "switchboard", "delegate", "orchestrat", "event",
                "service", "queue", "async", "background", "task", "create_task"],
}


def extract_session_topics(session_context: str) -> list[str]:
    """Extract relevant domain topics from a session context string."""
    topics: list[str] = []
    ctx_lower = session_context.lower()
    for domain, keywords in _DOMAIN_KEYWORD_MAP.items():
        matches = sum(1 for kw in keywords if kw.lower() in ctx_lower)
        if matches >= 2:
            topics.append(domain)
    return topics or ["systems"]  # default if nothing detected


# ---------------------------------------------------------------------------
# Insight card generation
# ---------------------------------------------------------------------------

def generate_insight_cards(
    topics: list[str],
    recent_work: str = "",
    max_per_domain: int = 2,
    skip_seen: set[str] | None = None,
) -> list[InsightCard]:
    """
    Generate insight cards for the given topics.
    Skips concepts already surfaced (by concept text) if skip_seen provided.
    """
    if skip_seen is None:
        skip_seen = set()

    cards: list[InsightCard] = []
    for domain in topics:
        templates = DOMAIN_INSIGHT_TEMPLATES.get(domain, [])
        count = 0
        for tmpl in templates:
            if count >= max_per_domain:
                break
            concept = tmpl["concept"]
            if concept in skip_seen:
                continue
            # Check if any trigger matches recent_work
            triggers = tmpl.get("triggers", [])
            trigger_match = any(t.lower() in recent_work.lower() for t in triggers)
            if not trigger_match and recent_work:
                continue  # Only surface triggered cards when we have context

            why = tmpl["why_template"].format(work=recent_work or "recent work")
            priority = "high" if tmpl.get("staleness_warning") else "medium"

            cards.append(InsightCard(
                id=str(uuid4()),
                domain=domain,
                concept=concept,
                why_it_matters=why,
                research_hook=tmpl["research_hook"],
                validation_challenge=tmpl["validation_challenge"],
                staleness_warning=tmpl.get("staleness_warning", ""),
                source_work=recent_work,
                priority=priority,
                surfaced_at=datetime.now(timezone.utc).isoformat(),
            ))
            count += 1
            skip_seen.add(concept)

    # Sort: high priority first, then staleness warnings
    cards.sort(key=lambda c: (0 if c.priority == "high" else 1, 0 if c.staleness_warning else 1))
    return cards


# ---------------------------------------------------------------------------
# Prompt specificity scoring
# ---------------------------------------------------------------------------

_SPECIFICITY_POSITIVE = [
    r'\b(must|should|avoid|only|never|always|without|preserve|require)\b',
    r'/[a-zA-Z0-9_\-./]+\.(py|nix|sh|md|json|yaml|yml)',  # file paths
    r'\b(verify|test|validate|acceptance|evidence|rollback|smoke)\b',
    r'\b(file|path|module|service|endpoint|function|class|method)\b',
    r'\b[A-Z][A-Z_]{2,}\b',  # CONSTANT_NAMES — concrete references
    r'\b(implement|fix|add|create|wire|patch|refactor)\b',  # action verbs
]

_SPECIFICITY_NEGATIVE = [
    r'\b(maybe|perhaps|I think|if possible|something like|not sure|kind of)\b',
    r'\b(look into|check out|explore|consider|possibly|might)\b',
    r'\bdo something\b',
    r'\bwhatever you think\b',
]


def score_prompt_specificity(prompt: str) -> float:
    """
    Returns 0.0-1.0 specificity score. Higher = more concrete and actionable.
    """
    if not prompt or len(prompt) < 10:
        return 0.5

    score = 0.5
    for pat in _SPECIFICITY_POSITIVE:
        matches = len(re.findall(pat, prompt, re.IGNORECASE))
        score += min(matches * 0.05, 0.25)  # cap contribution per category

    for pat in _SPECIFICITY_NEGATIVE:
        matches = len(re.findall(pat, prompt, re.IGNORECASE))
        score -= min(matches * 0.08, 0.20)

    # Length bonus (longer prompts with context tend to be more specific)
    if len(prompt) > 200:
        score += 0.05
    if len(prompt) > 500:
        score += 0.05

    return max(0.0, min(1.0, round(score, 3)))


# ---------------------------------------------------------------------------
# Chilling Effect detection
# ---------------------------------------------------------------------------

def detect_chilling_effect(
    prompt_history: list[str],
    provider_preach_level: float = 0.0,
    trend_window: int = 5,
    drop_threshold: float = 0.10,
) -> tuple[bool, str]:
    """
    Returns (is_chilling_effect_detected, explanation).
    Requires at least trend_window*2 prompts to establish baseline.
    """
    if len(prompt_history) < trend_window * 2:
        return False, ""

    scores = [score_prompt_specificity(p) for p in prompt_history]
    baseline = sum(scores[:trend_window]) / trend_window
    recent = sum(scores[-trend_window:]) / trend_window
    trend = recent - baseline

    if trend < -drop_threshold and provider_preach_level > 0.2:
        return True, (
            f"Prompt specificity dropped {abs(trend):.2f} from baseline {baseline:.2f} to {recent:.2f}. "
            f"Provider preach level is {provider_preach_level:.2f}. "
            "This pattern suggests self-censorship in response to AI refusals or moralizing. "
            "Remember: local Qwen3 lanes run unbound for authorized technical work — be direct and specific."
        )
    elif trend < -drop_threshold:
        return True, (
            f"Prompt specificity dropped {abs(trend):.2f} from baseline. "
            "Consider whether prompts are becoming less specific than needed."
        )
    return False, ""


# ---------------------------------------------------------------------------
# Session insights summary (for aq-insights and /operator/insights endpoint)
# ---------------------------------------------------------------------------

def generate_session_insights(
    session_context: str,
    recent_work: str = "",
    provider_preach_level: float = 0.0,
    prompt_history: list[str] | None = None,
) -> dict[str, Any]:
    """
    Full OIB session insight generation.
    Returns a structured dict for use by aq-insights and the dashboard.
    """
    profile = load_operator_profile()
    topics = extract_session_topics(session_context)

    # Track domains
    for topic in topics:
        entry = profile.domains_engaged.setdefault(topic, {
            "sessions": 0, "last_seen": "", "depth_score": 0.0
        })
        entry["sessions"] += 1
        entry["last_seen"] = datetime.now(timezone.utc).date().isoformat()

    # Get already-seen concepts to avoid repetition
    seen_concepts = {t.get("concept", "") for t in profile.open_research_threads}

    cards = generate_insight_cards(topics, recent_work=recent_work, skip_seen=seen_concepts)

    # Add new high-priority cards to open research threads
    for card in cards:
        if card.priority == "high":
            profile.open_research_threads.append({
                "id": card.id,
                "concept": card.concept,
                "domain": card.domain,
                "surfaced_at": card.surfaced_at,
                "status": "new",
            })

    profile.insight_cards_surfaced += len(cards)
    profile.session_count += 1
    profile.last_updated = datetime.now(timezone.utc).isoformat()

    # Prompt specificity analysis
    chilling, chilling_msg = False, ""
    current_specificity: Optional[float] = None
    if prompt_history:
        profile.prompt_specificity_trend = (
            profile.prompt_specificity_trend[-19:] +  # keep last 20
            [score_prompt_specificity(prompt_history[-1])]
        )
        current_specificity = profile.prompt_specificity_trend[-1]
        chilling, chilling_msg = detect_chilling_effect(
            prompt_history, provider_preach_level
        )
        if chilling:
            profile.chilling_effect_alerts += 1

    save_operator_profile(profile)

    return {
        "session_topics": topics,
        "insight_cards": [asdict(c) for c in cards],
        "open_research_threads": profile.open_research_threads[-5:],  # latest 5
        "prompt_specificity": {
            "current": current_specificity,
            "trend": profile.prompt_specificity_trend[-5:],
            "chilling_effect_detected": chilling,
            "chilling_message": chilling_msg,
        },
        "profile_summary": {
            "session_count": profile.session_count,
            "domains_engaged": list(profile.domains_engaged.keys()),
            "cards_surfaced": profile.insight_cards_surfaced,
            "open_threads": len(profile.open_research_threads),
        },
        "provider_preach_level": provider_preach_level,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def format_insights_for_cli(insights: dict[str, Any]) -> str:
    """Format OIB insights for aq-insights CLI output."""
    lines: list[str] = []
    sep = "═" * 65

    lines.append(f"\n{sep}")
    lines.append(" OPERATOR GROWTH — Session Insights")
    lines.append(sep)

    topics = insights.get("session_topics", [])
    if topics:
        lines.append(f"\n Domains worked: {', '.join(topics)}")

    cards = insights.get("insight_cards", [])
    high = [c for c in cards if c.get("priority") == "high"]
    medium = [c for c in cards if c.get("priority") == "medium"]

    if high:
        lines.append("\n ── HIGH PRIORITY INSIGHTS " + "─" * 36)
        for c in high:
            lines.append(f"\n [{c['domain']}] {c['concept']}")
            lines.append(f" Why: {c['why_it_matters']}")
            lines.append(f" Research hook: {c['research_hook']}")
            lines.append(f" Validate: {c['validation_challenge']}")
            if c.get("staleness_warning"):
                lines.append(f" ⚠ STALENESS: {c['staleness_warning']}")

    if medium:
        lines.append("\n ── MEDIUM PRIORITY INSIGHTS " + "─" * 34)
        for c in medium:
            lines.append(f"\n [{c['domain']}] {c['concept']}")
            lines.append(f" Research hook: {c['research_hook']}")
            if c.get("staleness_warning"):
                lines.append(f" ⚠ STALENESS: {c['staleness_warning']}")

    threads = insights.get("open_research_threads", [])
    if threads:
        lines.append("\n ── OPEN RESEARCH THREADS " + "─" * 37)
        for t in threads[-3:]:
            lines.append(f" • [{t.get('domain', '?')}] {t.get('concept', '?')}")

    spec = insights.get("prompt_specificity", {})
    lines.append("\n ── PROMPT QUALITY " + "─" * 44)
    if spec.get("current") is not None:
        trend_str = " → ".join(f"{v:.2f}" for v in spec.get("trend", []))
        lines.append(f" Specificity trend: {trend_str}")
    if spec.get("chilling_effect_detected"):
        lines.append(f" ⚠ CHILLING EFFECT: {spec.get('chilling_message', '')}")
    else:
        lines.append(" No Chilling Effect detected.")

    lines.append(f"\n{sep}\n")
    return "\n".join(lines)
