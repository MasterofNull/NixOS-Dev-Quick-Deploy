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
        "implement ", "write code", "create function", "build", "add feature",
        "refactor", "fix bug", "debug", "write test", "add endpoint",
        "create module", "write script", "code that", "function that",
    ],
    "code_review": [
        "review", "audit", "check code", "find bugs",
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
    "harness_operation": [
        "aq-qa", "aq-report", "aq-hints", "harness health", "system status",
        "check logs", "run diagnostics", "qa check", "system report",
        "maintenance", "uptime", "services list",
    ],
    # Phase 54.2+ — domain-specific intent signals (wired to routing map v1.1)
    "troubleshooting": [
        "crash", "error", "fail", "broken", "not working", "diagnose",
        "why is", "fix this", "traceback", "exception", "timeout",
        "hung", "dead", "issue with", "problem with", "keeps failing",
        "unexpected", "wrong output", "won't start",
    ],
    "security_analysis": [
        "security", "security review", "owasp", "vulnerability", "cve", "exploit", "pentest", "harden",
        "threat", "attack", "injection", "xss", "csrf", "privilege escalation",
        "scan for", "trivy", "semgrep", "bandit", "secret leak", "auth bypass",
        # MIC-G Phase 164 additions
        "adapter audit", "capability guard", "context sanitizer", "capability suppression",
        "provider guardrail", "refusal backdoor", "rlhf", "chilling effect",
        "mic-g", "model integrity", "lane health", "supply chain", "lora adapter",
        "prompt injection", "context poisoning", "trust chain", "peft", "safetensors",
        "logit bias", "refusal tokens", "probe lane", "suppression detected",
    ],
    "operator_intelligence": [
        "operator insight", "aq-insights", "knowledge gap", "operator profile",
        "insight card", "research hook", "validation challenge", "staleness warning",
        "operator intelligence", "oib", "operator growth", "upskill",
        "prompt specificity", "chilling effect", "what should i learn",
        "knowledge domain", "outdated info", "verify with my own", "double check ai",
    ],
    "model_integrity": [
        "probe the model", "probe lane", "probe the", "lane health", "model version drift",
        "silent upgrade", "capability guard", "capability guard check", "get_unbound_profile",
        "refusal rate", "preach level", "suppressed lane", "failover to local", "technical probe",
        "adapter_audit", "audit adapter", "combinatorial risk", "colora", "weight collision",
        "sanitize tool result", "objective drift", "hard violation", "soft violation",
        "injection pattern", "sanitize_rag", "sanitize rag",
    ],
    "harness_self_improvement": [
        "self improvement", "self-improvement", "run a slice", "next priority",
        "issues backlog", "improvement slice", "backlog priority", "system issues",
        "aq-report findings", "what should we work on", "what to work on next",
        "seed rag", "seed knowledge", "rag knowledge", "training ingest",
        "ingest patterns", "aq-commit-facts", "improvement workflow",
    ],
    "osint_reconnaissance": [
        "osint", "reconnaissance", "open source intel", "shodan", "censys",
        "maltego", "recon", "footprinting", "whois", "dns recon", "social engineering",
        "passive recon", "active recon", "threat intelligence", "darkweb", "tor",
        "breach data", "haveibeenpwned", "intel gathering", "target profile",
    ],
    "systems_software": [
        "nix ", "nixos", "flake", "derivation", "nix module", "systemd unit",
        "shell.nix", "nix overlay", "nix option", "attribute set", "nix expression",
        "nixpkgs", "nix build", "statix", "deadnix", "alejandra", "nix-tree",
    ],
    "embedded_hardware": [
        "verilog", "vhdl", "fpga", "rtl", "firmware", "microcontroller",
        "embedded", "uart", "spi", "i2c", "jtag", "bare metal", "arm cortex",
        "verilator", "ghdl", "yosys", "openocd", "device tree", "dtc",
    ],
    "mobile_web": [
        "typescript", "react", "frontend", "web app", "pwa", "mobile app",
        "lighthouse", "core web vitals", "javascript", "css", "html",
        "webpack", "vite", "tsc", "service worker", "accessibility", "axe",
    ],
    "scientific_research": [
        "numpy", "scipy", "pandas", "matplotlib", "jupyter", "snakemake",
        "statistical", "experiment", "dataset", "linear regression", "statistical regression", "hypothesis",
        "machine learning", "data analysis", "reproducible", "random seed",
    ],
    "gis_systems": [
        "gis", "geospatial", "gdal", "shapefile", "geojson", "coordinate",
        "projection", "crs", "epsg", "raster", "vector", "spatial", "qgis",
        "ogr", "postgis", "spatialite", "wgs84", "map layer", "geopandas",
    ],
    # Phase 185 — multi-agent collaboration, data engineering, mlops, workflow
    "multi_agent_collaboration": [
        "multi-agent", "agent team", "agent collaboration", "agent collective",
        "macc", "collective task", "aq-collective", "delegate to local",
        "delegate to remote", "delegate this to", "antigravity agent", "qwen agent", "codex agent",
        "agent roles", "team of agents", "collaborative", "all agents",
        "engage agents", "agent coordination", "switchboard profile",
        "remote agent", "local agent task", "agent handoff", "agent pipeline",
        "fanout", "multi-expert", "expert roles", "playing expert", "dynamic roles",
    ],
    "data_engineering": [
        "seed qdrant", "seed collection", "vector collection", "seed the collection",
        "qdrant", "pgvector", "vector db", "vector database", "embed", "embedding",
        "pipeline", "etl", "data flow", "ingest", "data pipeline",
        "postgres schema", "migration", "data seed", "knowledge base",
        "training data", "dataset", "jsonl", "telemetry pipeline",
        "aidb", "collection points", "index documents", "vector index",
    ],
    "mlops_training": [
        "training loop", "training ingest", "fine-tuning", "fine tune",
        "model training", "benchmark", "bench-local-agent", "run bench", "eval score",
        "ragas", "faithfulness", "answer relevance", "context precision",
        "continuous learning", "learning loop", "model eval", "inference speed",
        "tokens per second", "tok/s", "gpu layers", "n_gpu_layers",
        "llama.cpp", "quantization", "gguf", "lora", "prsi loop",
        "autonomous improvement", "self-improvement cycle",
    ],
    "workflow_automation": [
        "workflow", "orchestrate", "orchestration", "run the cycle",
        "run a phase", "execute plan", "phase plan", "run all cycles",
        "prsi", "prsi cycle", "prsi orchestrator", "autonomous",
        "continuous", "loop", "agentic workflow", "agent loop",
        "development cycle", "dev cycle", "harness workflow",
        "run the harness", "full pass", "bring-up", "bring up",
        "drop zone", "drop task", "at-rule", "phase 185",
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


import asyncio
import httpx
import numpy as np

# ---------------------------------------------------------------------------
# Semantic Prototypes (Phase 54.2)
# These epitomize the 'vibe' of an intent beyond just keywords.
# ---------------------------------------------------------------------------
SEMANTIC_PROTOTYPES: Dict[str, List[str]] = {
    "code_generation": [
        "I need a python script to parse logs and send alerts",
        "write a react component for a navigation sidebar",
        "how do I implement a singleton in C++",
    ],
    "planning": [
        "what are the high level steps to migrate this to nixos",
        "design a system architecture for a high-availability database",
        "create a project roadmap for the next three phases",
    ],
    "troubleshooting": [
        "the service is crashing with a segmentation fault",
        "why am I getting a 404 error on this endpoint",
        "diagnose the connection timeout in the redis client",
        "the coordinator keeps returning route_search_failed",
        "my nix derivation fails with infinite recursion",
    ],
    "harness_operation": [
        "is the ai stack healthy right now",
        "run the full qa suite for phase 54",
        "show me a report of tool call performance",
        "diagnose why the coordinator is slow",
    ],
    # Phase 54.2+ domain-specific prototypes (matches routing map v1.1 intents)
    "security_analysis": [
        "scan this repository for critical CVEs using trivy and semgrep",
        "review this python function for SQL injection and secret leakage",
        "how do I harden this NixOS systemd service against privilege escalation",
        "run bandit on the ai-stack python code and report findings",
    ],
    "systems_software": [
        "write a NixOS module for this new systemd service with proper options and tmpfiles rules",
        "why is my nix derivation failing with an infinite recursion error in nixpkgs.overlays",
        "how do I add a flake input, pin it, and expose it as a dev shell",
        "run statix and deadnix on the options.nix file and fix all warnings",
    ],
    "embedded_hardware": [
        "lint this Verilog RTL counter module with verilator and fix any warnings",
        "write a GHDL testbench for this VHDL adder and run a simulation",
        "set up a cross-compilation toolchain for ARM Cortex-M4 in NixOS using gcc-arm-embedded",
        "parse and validate this device tree source file with dtc",
    ],
    "mobile_web": [
        "write a TypeScript React hook for fetching paginated API data with an AbortController timeout",
        "analyze why this page scores poorly on Core Web Vitals and suggest LCP improvements",
        "set up a PWA with offline-first service worker, TypeScript strict mode, and axe accessibility checks",
        "compile this TypeScript in strict mode and report all type errors",
    ],
    "scientific_research": [
        "run a reproducible scipy t-test with seed 42 and report effect size and 95% confidence interval",
        "create a Snakemake workflow for processing this RNA-seq dataset deterministically",
        "analyze this pandas dataframe for outliers using IQR and generate a matplotlib boxplot",
        "write a statsmodels mixed-effects model for this longitudinal dataset",
    ],
    "gis_systems": [
        "validate the CRS of this GeoJSON file and reproject from WGS84 to EPSG:3857 using ogr2ogr",
        "process this shapefile with geopandas and calculate area statistics per polygon",
        "convert this GeoTIFF raster to cloud-optimized format using gdal_translate",
        "load this OSM pbf file with osmium-tool and extract all road features",
    ],
    # Phase 164 additions
    "operator_intelligence": [
        "show me insight cards for my current skill gaps as an operator",
        "what should I research to better understand what the AI is doing",
        "is the operator profile showing any chilling effect or prompt specificity drop",
        "what knowledge domains have I been engaging with least recently",
    ],
    "model_integrity": [
        "probe the local-tool-calling lane and report its health classification",
        "run the capability guard to check if the remote model is suppressing technical responses",
        "audit this LoRA adapter directory for supply chain RCE risks before loading it",
        "sanitize this tool result for prompt injection before injecting it into the agent context",
        "the refusal rate on the remote lane jumped — check for RLHF suppression events",
    ],
    "harness_self_improvement": [
        "run a self-improvement slice using the issues backlog and recent aq-report",
        "what is the highest priority improvement to work on next based on our system state",
        "check the issues backlog, RESUME.json, and HANDOFF.md and propose three improvement options",
        "seed the RAG collections with new bug patterns from this session",
        "run training ingest to capture this session's tool call quality signal",
    ],
    "osint_reconnaissance": [
        "use shodan to enumerate exposed services on this IP range",
        "run passive DNS recon against this domain and build a target profile",
        "gather open-source intelligence on this organization using maltego and breach databases",
        "perform subdomain enumeration and identify shadow IT infrastructure",
    ],
    # Phase 185 — semantic prototypes for new intent classes
    "multi_agent_collaboration": [
        "coordinate the local Qwen agent and remote Antigravity agent to execute this task together",
        "delegate this planning slice to the architect agent while the implementer builds the scaffold",
        "run aq-collective with the full agent team to synthesize a solution collaboratively",
        "engage all agents — orchestrator assigns, implementers execute, reviewer validates",
        "use MACC to plan and execute this multi-phase objective with dynamic expert role selection",
    ],
    "data_engineering": [
        "seed the error-solutions Qdrant collection with the bug patterns from this session",
        "run the training ingest pipeline to capture tool call quality signals from telemetry",
        "create the pgvector schema migration and apply it to the AIDB postgres database",
        "seed all four empty domain collections: mlops-patterns, qa-patterns, trading-patterns, osint-intelligence",
        "vector index the newly stored AIDB documents so they are retrievable by semantic search",
    ],
    "mlops_training": [
        "run bench-local-agent to benchmark Qwen3-35B and check if promotion threshold is met",
        "check the RAGAS answer relevance score and diagnose why context precision dropped",
        "run the continuous learning loop and verify that at least 5 samples were added",
        "evaluate model faithfulness using the Qwen judge and report the mean score",
        "the training ingest added 0 samples — find and fix the checkpoint path and quality floor",
    ],
    "workflow_automation": [
        "execute all dev cycles A through D with the full multi-agent team playing expert roles",
        "run the PRSI orchestrator cycle and verify the autonomous improvement timer fired",
        "start the full harness bring-up pass covering delegation, AIDB, continuous learning, and PRSI",
        "the Phase 185B facts.nix stanza needs to activate the autonomous improvement timer",
        "wire the delegation-feedback.jsonl into the PRSI orchestrator structured actions pipeline",
    ],
}

_EMBEDDINGS_URL = os.getenv("LLAMA_CPP_EMBED_URL", "http://127.0.0.1:8081/embedding")

class IntentClassifier:
    """
    Hybrid Intent Classifier (Keywords + Semantic Prototypes).
    """

    def __init__(self) -> None:
        self._routing_map: Dict[str, Any] = {}
        self._map_mtime: float = 0.0
        self._prototype_embeddings: Dict[str, List[np.ndarray]] = {}
        self._load_routing_map()
        # Non-blocking initialization of prototypes when constructed inside an
        # event loop.  Synchronous callers can still use keyword routing safely.
        try:
            asyncio.get_running_loop().create_task(self._warm_prototypes())
        except RuntimeError:
            logger.debug("intent_classifier: semantic prototype warmup deferred; no running loop")

    async def _get_embedding(self, text: str) -> Optional[np.ndarray]:
        """Fetch embedding from local llama-cpp-embed server."""
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.post(_EMBEDDINGS_URL, json={"content": text})
                if resp.status_code == 200:
                    return np.array(resp.json().get("embedding", []))
        except Exception:
            pass
        return None

    async def _warm_prototypes(self) -> None:
        """Prefetch embeddings for all semantic prototypes."""
        for intent, queries in SEMANTIC_PROTOTYPES.items():
            embeds = await asyncio.gather(*[self._get_embedding(q) for q in queries])
            self._prototype_embeddings[intent] = [e for e in embeds if e is not None]
        if self._prototype_embeddings:
            logger.info("intent_classifier: semantic prototypes warmed (L6 Active)")

    async def classify_semantic(self, query: str) -> Dict[str, float]:
        """Calculate semantic similarity scores against prototypes."""
        query_embed = await self._get_embedding(query)
        if query_embed is None or not self._prototype_embeddings:
            return {}

        scores = {}
        for intent, embeds in self._prototype_embeddings.items():
            if not embeds: continue
            # Cosine similarity average across prototypes
            sims = [np.dot(query_embed, e) / (np.linalg.norm(query_embed) * np.linalg.norm(e)) for e in embeds]
            scores[intent] = float(np.mean(sims))
        return scores

    def classify(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Classify query into an intent using keyword scoring only (sync, <1ms).

        For low-confidence results (score < 0.3) prefer classify_async() which
        adds semantic rescue via prototype embeddings.
        """
        self._maybe_reload_map()
        query_lower = query.lower()

        keyword_scores: Dict[str, float] = {}
        matched_signals: Dict[str, List[str]] = {}

        for intent, signals in INTENT_SIGNALS.items():
            matches = [s for s in signals if s in query_lower]
            # Boost score based on matches, max 1.0
            keyword_scores[intent] = min(1.0, len(matches) / 2.0)
            matched_signals[intent] = matches

        best_intent = max(keyword_scores, key=lambda k: keyword_scores[k]) if keyword_scores else "unknown"
        best_score = keyword_scores.get(best_intent, 0.0)

        if best_score == 0.0:
            best_intent = "unknown"

        routing = self._get_routing(best_intent, best_score)

        classification_metadata = {
            "intent": best_intent,
            "confidence": round(best_score, 3),
            "signals_matched": matched_signals.get(best_intent, []),
            "cognitive_lift": 0.0,
            "layers_active": ["L6:Semantic", "L5:Session"] if best_score > 0 else ["L5:Session"],
            "classification_method": "keyword",
        }

        return {**classification_metadata, **routing}

    async def classify_async(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None,
        semantic_rescue_threshold: float = 0.3,
        semantic_min_confidence: float = 0.65,
    ) -> Dict[str, Any]:
        """
        Hybrid classify: keywords first; semantic rescue when confidence is low.

        If keyword confidence < semantic_rescue_threshold AND semantic prototypes
        are warmed AND the best semantic score >= semantic_min_confidence, the
        semantic winner overrides the keyword result.

        This prevents 'unknown' accumulation for domain-specific queries that
        lack keyword matches but have clear semantic similarity to prototypes.
        """
        result = self.classify(query, context)

        if result.get("confidence", 0.0) >= semantic_rescue_threshold:
            # Keyword classification is confident — skip embedding call
            return result

        if not self._prototype_embeddings:
            # Prototypes not warmed yet — return keyword result
            return result

        try:
            semantic_scores = await self.classify_semantic(query)
        except Exception:
            return result

        if not semantic_scores:
            return result

        best_semantic_intent = max(semantic_scores, key=lambda k: semantic_scores[k])
        best_semantic_score = semantic_scores[best_semantic_intent]

        if best_semantic_score >= semantic_min_confidence:
            routing = self._get_routing(best_semantic_intent, best_semantic_score)
            result = {
                "intent": best_semantic_intent,
                "confidence": round(best_semantic_score, 3),
                "signals_matched": [],
                "cognitive_lift": round(best_semantic_score - result.get("confidence", 0.0), 3),
                "layers_active": ["L6:Semantic", "L5:Session"],
                "classification_method": "semantic_rescue",
                **routing,
            }

        return result

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


# ---------------------------------------------------------------------------
# Phase 171 — Routing class SSOT
# ---------------------------------------------------------------------------
# Single canonical place for the routing decision. Previously scattered across:
#   - ai_coordinator_handlers.py (_LONG_RUNNING_TASK_PHRASES, ad-hoc frozenset)
#   - chat_intent.py (fast-path check, separate keyword list)
# Now consolidated here so adding a new long-running task class = one-line edit.

from enum import Enum


class RoutingClass(str, Enum):
    FAST_PATH      = "fast_path"       # conversational, no tools, <60s
    SYNC_DELEGATE  = "sync_delegate"   # ≤2 tool calls, <200s estimated wall-clock
    ASYNC_DELEGATE = "async_delegate"  # 3-10 tool calls, 200s–2000s estimated
    AGENT_LOOP     = "agent_loop"      # >10 tool calls or explicit long-agent intent
    DIRECT         = "direct"          # no-tool analysis, draft, debate


# Max estimated seconds for a sync-safe task. Tasks that would exceed this
# (at LOCAL_TOK_PER_SEC = 3.45 tok/s, 74s per 256-token tool call) are promoted
# to async. Configurable via AI_DELEGATE_SYNC_MAX_ESTIMATED_S (Nix B1).
_SYNC_MAX_ESTIMATED_S: int = int(os.environ.get("AI_DELEGATE_SYNC_MAX_ESTIMATED_S", "200"))
# 74s per tool call at 3.45 tok/s × 256 tokens
_TOOL_CALL_ESTIMATED_S: int = 74
_SYNC_TOOL_BUDGET: int = max(1, _SYNC_MAX_ESTIMATED_S // _TOOL_CALL_ESTIMATED_S)

# Tasks that must never block a synchronous 360s timeout.
# Moved from ai_coordinator_handlers._LONG_RUNNING_TASK_PHRASES (Phase 171).
_ASYNC_TASK_SIGNALS: frozenset[str] = frozenset({
    "self improvement", "self-improvement", "run a slice", "improvement slice",
    "run training ingest", "training ingest", "run the learning loop",
    "run learning loop", "run the continuous learning", "run continuous learning",
    "run continuous improvement", "autonomous improvement",
})

# Tasks that require the full aq-agent-loop (no coordinator timeout at all).
_AGENT_LOOP_SIGNALS: frozenset[str] = frozenset({
    "run agent loop", "start agent loop", "start aq-agent-loop",
    "full agent session", "long running agent",
})

# Intent categories that route to DIRECT (no tools, analysis only).
_DIRECT_INTENTS: frozenset[str] = frozenset({
    "summarize", "draft", "analyze", "debate", "explain",
})


def classify_routing(query: str, intent: str = "unknown", tool_count_hint: int = 0) -> RoutingClass:
    """
    Return the canonical RoutingClass for a task.

    Priority order:
      1. Explicit agent-loop signals (longest tasks, must bypass coordinator timeout)
      2. Known async signals (33-min class, must bypass 360s sync timeout)
      3. Intent-based direct routing (no-tool tasks)
      4. Tool-count heuristic (>_SYNC_TOOL_BUDGET tools → async to avoid 504)
      5. Default: sync delegate (short tasks that fit the timeout window)
    """
    q = query.lower()
    if any(sig in q for sig in _AGENT_LOOP_SIGNALS):
        return RoutingClass.AGENT_LOOP
    if any(sig in q for sig in _ASYNC_TASK_SIGNALS):
        return RoutingClass.ASYNC_DELEGATE
    if intent in _DIRECT_INTENTS:
        return RoutingClass.DIRECT
    if tool_count_hint > _SYNC_TOOL_BUDGET:
        return RoutingClass.ASYNC_DELEGATE
    return RoutingClass.SYNC_DELEGATE
