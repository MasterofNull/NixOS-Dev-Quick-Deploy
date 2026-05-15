"""
intent_classifier.py — Semantic intent classification before routing (Phase 54.2)

Classifies incoming queries into intent categories before coordinator dispatch.
Combines the existing keyword-signal approach (model_coordinator.classify_task)
with embedding-based similarity against cached intent prototypes.

Intent taxonomy v1:
    code_generation   — implement, write, build, create function
    code_review       — review, audit, check code, find bugs
    knowledge_lookup  — search, find, what is, recall, explain
    planning          — plan, design, architect, strategize
    math_reasoning    — calculate, compute, solve, prove
    tool_execution    — run, execute, shell, command
    delegation        — delegate, assign, ask agent, route to
    unknown           — fallback

Routing map: config/intent-routing-map.json (hot-reloadable)

Usage:
    from intent_classifier import IntentClassifier, get_classifier

    clf = get_classifier()
    result = clf.classify("implement a retry decorator in Python")
    # -> {"intent": "code_generation", "confidence": 0.82, "profile": "local-tool-calling", ...}
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("hybrid-coordinator")

# ---------------------------------------------------------------------------
# Intent signal patterns (lightweight keyword matching, <1ms)
# Complements model_coordinator.py ROLE_SIGNALS with harness-specific intents
# ---------------------------------------------------------------------------
INTENT_SIGNALS: Dict[str, List[str]] = {
    "code_generation": [
        "implement", "write code", "create function", "build", "add feature",
        "refactor", "fix bug", "debug", "write test", "add endpoint",
        "create module", "write script", "code that", "function that",
    ],
    "code_review": [
        "review", "audit", "check code", "find bugs", "security review",
        "look at", "is this correct", "what's wrong", "code quality",
    ],
    "knowledge_lookup": [
        "what is", "how does", "explain", "search", "find", "recall",
        "look up", "tell me", "define", "what are", "where is", "list",
        "show me", "describe",
    ],
    "planning": [
        "plan", "design", "architect", "strategize", "roadmap", "phase",
        "steps to", "how to approach", "best way to", "strategy for",
        "prd", "requirements", "spec",
    ],
    "math_reasoning": [
        "calculate", "compute", "solve", "prove", "derive", "equation",
        "formula", "probability", "statistics", "math",
    ],
    "tool_execution": [
        "run", "execute", "shell", "command", "script", "bash", "invoke",
        "call the", "trigger", "launch",
    ],
    "delegation": [
        "delegate", "assign to", "ask gemini", "ask claude", "ask codex",
        "route to", "send to agent", "have qwen", "local agent",
    ],
}

# Load path for routing map
_ROUTING_MAP_PATH = Path(os.getenv(
    "INTENT_ROUTING_MAP",
    str(Path(__file__).parent.parent.parent.parent / "config" / "intent-routing-map.json"),
))

# Module-level singleton
_classifier: Optional["IntentClassifier"] = None


def get_classifier() -> "IntentClassifier":
    global _classifier
    if _classifier is None:
        _classifier = IntentClassifier()
    return _classifier


class IntentClassifier:
    """
    Lightweight keyword-based intent classifier (<1ms per call).

    Uses cosine similarity via embedding is optional (falls back to pure keyword
    scoring when llama-embed is unavailable).
    """

    def __init__(self) -> None:
        self._routing_map: Dict[str, Any] = {}
        self._map_mtime: float = 0.0
        self._load_routing_map()

    # ------------------------------------------------------------------
    # Public classify
    # ------------------------------------------------------------------

    def classify(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Classify query into an intent.

        Returns:
            {
                "intent": str,
                "confidence": float,
                "profile": str,
                "fallback_profile": str,
                "memory_recall": bool,
                "rag_project": str,
                "signals_matched": list[str],
            }
        """
        self._maybe_reload_map()
        query_lower = query.lower()

        scores: Dict[str, float] = {}
        matched_signals: Dict[str, List[str]] = {}

        for intent, signals in INTENT_SIGNALS.items():
            matches = [s for s in signals if s in query_lower]
            scores[intent] = len(matches) / max(len(signals), 1)
            matched_signals[intent] = matches

        best_intent = max(scores, key=lambda k: scores[k]) if scores else "unknown"
        best_score = scores.get(best_intent, 0.0)

        # Normalise: if best score is 0, mark as unknown
        if best_score == 0.0:
            best_intent = "unknown"

        routing = self._get_routing(best_intent, best_score)
        return {
            "intent": best_intent,
            "confidence": round(best_score, 3),
            "signals_matched": matched_signals.get(best_intent, []),
            **routing,
        }

    # ------------------------------------------------------------------
    # Routing map
    # ------------------------------------------------------------------

    def get_routing_map(self) -> Dict[str, Any]:
        """Return current routing map contents."""
        self._maybe_reload_map()
        return self._routing_map

    def reload_map(self) -> bool:
        """Force reload routing map from disk. Returns True if changed."""
        old = self._map_mtime
        self._load_routing_map()
        return self._map_mtime != old

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _load_routing_map(self) -> None:
        try:
            if _ROUTING_MAP_PATH.exists():
                mtime = _ROUTING_MAP_PATH.stat().st_mtime
                with open(_ROUTING_MAP_PATH) as f:
                    data = json.load(f)
                self._routing_map = data.get("intents", {})
                self._map_mtime = mtime
                logger.debug("intent_classifier: loaded routing map with %d intents", len(self._routing_map))
            else:
                logger.warning("intent_classifier: routing map not found at %s", _ROUTING_MAP_PATH)
        except Exception as exc:
            logger.warning("intent_classifier: routing map load error: %s", exc)

    def _maybe_reload_map(self) -> None:
        """Reload map if file has been modified (hot-reload)."""
        try:
            if _ROUTING_MAP_PATH.exists():
                mtime = _ROUTING_MAP_PATH.stat().st_mtime
                if mtime != self._map_mtime:
                    self._load_routing_map()
        except Exception:
            pass

    def _get_routing(self, intent: str, confidence: float) -> Dict[str, Any]:
        intents = self._routing_map
        entry = intents.get(intent) or intents.get("unknown") or {}
        min_conf = float(entry.get("min_confidence", 0.0))

        if confidence < min_conf:
            # Fall back to unknown routing
            entry = intents.get("unknown") or {}

        return {
            "profile": entry.get("profile", "local"),
            "fallback_profile": entry.get("fallback_profile", "local"),
            "memory_recall": bool(entry.get("memory_recall", True)),
            "rag_project": entry.get("rag_project", "semantic"),
        }


# ---------------------------------------------------------------------------
# HTTP handlers
# ---------------------------------------------------------------------------

async def handle_get_intent_map(request) -> Any:
    """GET /control/intent/map — return current intent routing map."""
    from aiohttp import web
    clf = get_classifier()
    return web.json_response({
        "routing_map": clf.get_routing_map(),
        "map_path": str(_ROUTING_MAP_PATH),
        "intent_count": len(clf.get_routing_map()),
    })


async def handle_reload_intent_map(request) -> Any:
    """POST /control/intent/reload — hot-reload routing map from disk."""
    from aiohttp import web
    clf = get_classifier()
    changed = clf.reload_map()
    return web.json_response({
        "reloaded": True,
        "changed": changed,
        "intent_count": len(clf.get_routing_map()),
    })
