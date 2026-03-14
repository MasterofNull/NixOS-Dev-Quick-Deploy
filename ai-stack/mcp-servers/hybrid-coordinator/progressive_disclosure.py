#!/usr/bin/env python3
"""
Progressive Disclosure API
Allows remote LLMs to discover system capabilities without information overload
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

logger = logging.getLogger("progressive-disclosure")


class CapabilityLevel(BaseModel):
    """Single capability level description"""
    name: str = Field(..., description="Short capability name")
    description: str = Field(..., description="Brief description")
    example_query: Optional[str] = Field(None, description="Example query that uses this")
    token_estimate: int = Field(..., description="Rough token count for typical response")


class SystemCapabilities(BaseModel):
    """System capabilities organized by category"""
    rag_capabilities: List[CapabilityLevel] = Field(..., description="RAG and knowledge retrieval")
    learning_capabilities: List[CapabilityLevel] = Field(..., description="Continuous learning features")
    multi_turn_capabilities: List[CapabilityLevel] = Field(..., description="Multi-turn conversation features")
    monitoring_capabilities: List[CapabilityLevel] = Field(..., description="Health and monitoring")
    available_collections: List[Dict[str, Any]] = Field(..., description="Qdrant collections info")
    total_knowledge_points: int = Field(..., description="Total points across all collections")


class DiscoveryRequest(BaseModel):
    """Request for capability discovery"""
    level: str = Field(default="overview", description="Detail level: overview, detailed, comprehensive")
    categories: Optional[List[str]] = Field(None, description="Specific categories to explore")
    token_budget: int = Field(default=500, description="Maximum tokens for response")


class DiscoveryResponse(BaseModel):
    """Capability discovery response"""
    level: str = Field(..., description="Disclosure level provided")
    capabilities: SystemCapabilities = Field(..., description="Discovered capabilities")
    next_steps: List[str] = Field(..., description="Suggested next queries")
    estimated_tokens: int = Field(..., description="Estimated token count of response")
    disclosure_id: str = Field(..., description="Unique ID for this disclosure")


class ProgressiveDisclosure:
    """
    Progressive disclosure API for remote LLMs

    Enables remote LLMs to:
    1. Discover system capabilities without overwhelming detail
    2. Request specific information as needed
    3. Learn about available tools and collections progressively

    Three disclosure levels:
    - overview: 100-300 tokens (capability categories only)
    - detailed: 300-800 tokens (capabilities with examples)
    - comprehensive: 800-2000 tokens (full specs with usage patterns)

    Example usage by remote LLM:

    # Level 1: Get overview
    response = await disclosure_api.discover(level="overview")
    # Returns: ["RAG search", "Multi-turn sessions", "Continuous learning", ...]

    # Level 2: Deep dive into specific category
    response = await disclosure_api.discover(
        level="detailed",
        categories=["multi_turn_capabilities"]
    )
    # Returns: Detailed info about session management, context levels, etc.
    """

    def __init__(
        self,
        qdrant_client,
        multi_turn_manager,
        feedback_api
    ):
        self.qdrant = qdrant_client
        self.multi_turn_manager = multi_turn_manager
        self.feedback_api = feedback_api

        # Define capability structure (static for now, could be dynamic later)
        self.capability_definitions = {
            "rag_capabilities": [
                CapabilityLevel(
                    name="Context Search",
                    description="Search knowledge base with semantic similarity",
                    example_query="Find solutions for NixOS GNOME keyring errors",
                    token_estimate=300
                ),
                CapabilityLevel(
                    name="Multi-Collection Search",
                    description="Query across error-solutions, best-practices, codebase-context",
                    example_query="Search best-practices and error-solutions for Podman issues",
                    token_estimate=500
                ),
                CapabilityLevel(
                    name="Filtered Retrieval",
                    description="Filter by metadata (category, file_type, language, etc.)",
                    example_query="Get Python-specific error solutions",
                    token_estimate=250
                ),
            ],

            "learning_capabilities": [
                CapabilityLevel(
                    name="Interaction Tracking",
                    description="Record interactions with outcomes for continuous learning",
                    example_query="Track that solution X worked for error Y",
                    token_estimate=100
                ),
                CapabilityLevel(
                    name="Outcome Updates",
                    description="Update previous interactions with success/failure feedback",
                    example_query="Mark interaction abc123 as successful",
                    token_estimate=50
                ),
                CapabilityLevel(
                    name="Training Data Export",
                    description="Generate fine-tuning datasets from successful interactions",
                    example_query="Export last 100 interactions as training data",
                    token_estimate=200
                ),
            ],

            "multi_turn_capabilities": [
                CapabilityLevel(
                    name="Session Management",
                    description="Persistent sessions with context tracking across turns",
                    example_query="Create session and query multiple times with context building",
                    token_estimate=400
                ),
                CapabilityLevel(
                    name="Context Deduplication",
                    description="Avoid re-sending same context across turns",
                    example_query="Track context_ids from previous turn to avoid duplicates",
                    token_estimate=300
                ),
                CapabilityLevel(
                    name="Progressive Context Levels",
                    description="3 levels: standard (concise), detailed (full), comprehensive (verbose)",
                    example_query="Start with standard, escalate to detailed if needed",
                    token_estimate=350
                ),
                CapabilityLevel(
                    name="Confidence-Based Refinement",
                    description="Report low confidence, receive suggestions for improvement",
                    example_query="Report confidence 0.65 with gaps, get follow-up query suggestions",
                    token_estimate=250
                ),
            ],

            "monitoring_capabilities": [
                CapabilityLevel(
                    name="Health Checks",
                    description="Check status of AI stack services",
                    example_query="Get health status of all services",
                    token_estimate=200
                ),
                CapabilityLevel(
                    name="Service Logs",
                    description="Retrieve logs from specific services",
                    example_query="Get last 50 lines from qdrant service",
                    token_estimate=300
                ),
                CapabilityLevel(
                    name="Telemetry Tracking",
                    description="Performance metrics and usage statistics",
                    example_query="Get query latency statistics for last hour",
                    token_estimate=150
                ),
            ],
        }

    async def discover(
        self,
        level: str = "overview",
        categories: Optional[List[str]] = None,
        token_budget: int = 500
    ) -> DiscoveryResponse:
        """
        Discover system capabilities with progressive disclosure

        Args:
            level: Disclosure level (overview/detailed/comprehensive)
            categories: Specific categories to explore (or None for all)
            token_budget: Maximum tokens for response

        Returns:
            DiscoveryResponse with capabilities and next steps
        """
        start_time = datetime.now(timezone.utc)
        disclosure_id = str(uuid4())

        logger.info(f"Discovery request: level={level}, categories={categories}, budget={token_budget}")

        # Get collection info
        available_collections = await self.get_collection_info()
        total_knowledge_points = sum(c.get("points_count", 0) for c in available_collections)

        # Filter capabilities by requested categories
        if categories:
            filtered_caps = {
                cat: self.capability_definitions.get(cat, [])
                for cat in categories
                if cat in self.capability_definitions
            }
        else:
            filtered_caps = self.capability_definitions

        # Format capabilities based on disclosure level
        if level == "overview":
            capabilities = self.format_overview(filtered_caps, available_collections, total_knowledge_points)
            next_steps = [
                "Request 'detailed' level for specific category",
                "Try example queries to test capabilities",
                "Check available_collections for knowledge coverage"
            ]
            estimated_tokens = 200

        elif level == "detailed":
            capabilities = self.format_detailed(filtered_caps, available_collections, total_knowledge_points)
            next_steps = [
                "Request 'comprehensive' level for full specifications",
                "Start multi-turn session to test progressive context",
                "Query specific collections for actual knowledge"
            ]
            estimated_tokens = 600

        else:  # comprehensive
            capabilities = self.format_comprehensive(filtered_caps, available_collections, total_knowledge_points)
            next_steps = [
                "Begin actual queries against knowledge base",
                "Set up multi-turn session for complex tasks",
                "Use feedback API to report confidence and refine"
            ]
            estimated_tokens = 1500

        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        logger.info(f"Discovery completed in {duration:.2f}s, estimated {estimated_tokens} tokens")

        return DiscoveryResponse(
            level=level,
            capabilities=capabilities,
            next_steps=next_steps,
            estimated_tokens=estimated_tokens,
            disclosure_id=disclosure_id
        )

    async def get_collection_info(self) -> List[Dict[str, Any]]:
        """Get information about available Qdrant collections.

        Optimized to fetch collection info in parallel for faster response.
        """
        import asyncio
        import concurrent.futures

        collection_names = [
            "error-solutions",
            "best-practices",
            "codebase-context",
            "skills-patterns",
            "interaction-history"
        ]

        def _fetch_single_collection(name: str) -> Dict[str, Any]:
            """Sync wrapper for fetching single collection info."""
            try:
                info = self.qdrant.get_collection(name)
                return {
                    "name": name,
                    "points_count": info.points_count,
                    "vector_size": info.config.params.vectors.size,
                    "status": "active"
                }
            except Exception as e:
                logger.debug(f"Collection {name} not accessible: {e}")
                return {
                    "name": name,
                    "points_count": 0,
                    "vector_size": 384,
                    "status": "unavailable"
                }

        # Run collection fetches in parallel using thread pool
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                loop.run_in_executor(executor, _fetch_single_collection, name)
                for name in collection_names
            ]
            collections = await asyncio.gather(*futures)

        return list(collections)

    def format_overview(
        self,
        capabilities: Dict[str, List[CapabilityLevel]],
        collections: List[Dict[str, Any]],
        total_points: int
    ) -> SystemCapabilities:
        """Format capabilities at overview level (minimal detail)"""

        # Just return capability names, no descriptions
        formatted = {}
        for category, caps in capabilities.items():
            formatted[category] = [
                CapabilityLevel(
                    name=cap.name,
                    description=f"{cap.description[:50]}...",  # Truncate
                    token_estimate=cap.token_estimate
                )
                for cap in caps
            ]

        return SystemCapabilities(
            rag_capabilities=formatted.get("rag_capabilities", []),
            learning_capabilities=formatted.get("learning_capabilities", []),
            multi_turn_capabilities=formatted.get("multi_turn_capabilities", []),
            monitoring_capabilities=formatted.get("monitoring_capabilities", []),
            available_collections=[
                {"name": c["name"], "points": c["points_count"]}
                for c in collections
            ],
            total_knowledge_points=total_points
        )

    def format_detailed(
        self,
        capabilities: Dict[str, List[CapabilityLevel]],
        collections: List[Dict[str, Any]],
        total_points: int
    ) -> SystemCapabilities:
        """Format capabilities at detailed level (with examples)"""

        # Include full descriptions and examples
        formatted = {}
        for category, caps in capabilities.items():
            formatted[category] = caps  # Full CapabilityLevel objects

        return SystemCapabilities(
            rag_capabilities=formatted.get("rag_capabilities", []),
            learning_capabilities=formatted.get("learning_capabilities", []),
            multi_turn_capabilities=formatted.get("multi_turn_capabilities", []),
            monitoring_capabilities=formatted.get("monitoring_capabilities", []),
            available_collections=collections,
            total_knowledge_points=total_points
        )

    def format_comprehensive(
        self,
        capabilities: Dict[str, List[CapabilityLevel]],
        collections: List[Dict[str, Any]],
        total_points: int
    ) -> SystemCapabilities:
        """Format capabilities at comprehensive level (everything)"""

        # Same as detailed but with additional metadata
        formatted = {}
        for category, caps in capabilities.items():
            formatted[category] = caps

        return SystemCapabilities(
            rag_capabilities=formatted.get("rag_capabilities", []),
            learning_capabilities=formatted.get("learning_capabilities", []),
            multi_turn_capabilities=formatted.get("multi_turn_capabilities", []),
            monitoring_capabilities=formatted.get("monitoring_capabilities", []),
            available_collections=collections,
            total_knowledge_points=total_points
        )

    async def get_token_budget_recommendations(
        self,
        query_type: str,
        context_level: str = "standard"
    ) -> Dict[str, Any]:
        """
        Get recommended token budgets for different query types

        Helps remote LLMs understand how much context to request
        """

        recommendations = {
            "quick_lookup": {
                "standard": 500,
                "detailed": 1000,
                "comprehensive": 2000,
                "description": "Single fact or error solution lookup"
            },
            "troubleshooting": {
                "standard": 1000,
                "detailed": 2000,
                "comprehensive": 4000,
                "description": "Debug and fix complex issues"
            },
            "learning": {
                "standard": 800,
                "detailed": 1500,
                "comprehensive": 3000,
                "description": "Learn about patterns and best practices"
            },
            "implementation": {
                "standard": 1500,
                "detailed": 3000,
                "comprehensive": 6000,
                "description": "Implement features with code examples"
            }
        }

        return recommendations.get(query_type, recommendations["quick_lookup"])


# ---------------------------------------------------------------------------
# Domain-Based Progressive Disclosure (Phase 12.3 Extension)
# ---------------------------------------------------------------------------

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

DOMAIN_CONFIG_PATH = Path(os.getenv(
    "PROGRESSIVE_DISCLOSURE_CONFIG",
    "/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/config/progressive-disclosure-domains.json"
))


@dataclass
class DomainContext:
    """Context loaded for a specific domain at a disclosure level."""
    domain_id: str
    domain_name: str
    level: str
    context_text: str
    tools: List[str] = field(default_factory=list)
    hints: List[str] = field(default_factory=list)
    mcp_endpoints: List[str] = field(default_factory=list)
    skills: List[str] = field(default_factory=list)
    docs: List[str] = field(default_factory=list)
    research_packs: List[str] = field(default_factory=list)
    memory_recall: List[str] = field(default_factory=list)
    token_estimate: int = 0

    def to_compact_string(self) -> str:
        """Generate compact context string for injection (minimal tokens)."""
        parts = [f"[{self.domain_name}]", self.context_text]
        if self.tools:
            parts.append(f"Tools: {', '.join(self.tools[:5])}")
        if self.hints:
            parts.append(f"Tips: {'; '.join(self.hints[:2])}")
        if self.skills:
            parts.append(f"Skills: {', '.join(self.skills[:3])}")
        return " | ".join(parts)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "domain_id": self.domain_id,
            "domain_name": self.domain_name,
            "level": self.level,
            "context_text": self.context_text,
            "tools": self.tools,
            "hints": self.hints,
            "mcp_endpoints": self.mcp_endpoints,
            "skills": self.skills,
            "docs": self.docs,
            "research_packs": self.research_packs,
            "memory_recall": self.memory_recall,
            "token_estimate": self.token_estimate,
        }


@dataclass
class DomainMatch:
    """Result of domain detection."""
    domain_id: str
    confidence: float
    matched_triggers: List[str]


class DomainLoader:
    """
    Loads domain-specific context using progressive disclosure.

    Domains: nixos-dev, web-dev, ai-harness, data-engineering, devops, security, documentation
    Levels: minimal (500 tokens), standard (1500 tokens), full (4000 tokens)
    """

    def __init__(self, config_path: Optional[Path] = None):
        self._config_path = config_path or DOMAIN_CONFIG_PATH
        self._config: Optional[Dict[str, Any]] = None
        self._load_config()

    def _load_config(self) -> None:
        """Load configuration from JSON file."""
        try:
            if self._config_path.exists():
                self._config = json.loads(self._config_path.read_text(encoding="utf-8"))
                logger.debug("Loaded domain config from %s", self._config_path)
            else:
                logger.warning("Domain config not found, using defaults")
                self._config = {"domains": {}, "domain_detection": {"fallback_domain": "ai-harness"}}
        except Exception as e:
            logger.error("Failed to load domain config: %s", e)
            self._config = {"domains": {}}

    def detect_domains(self, query: str) -> List[DomainMatch]:
        """Detect which domains match the query based on trigger keywords."""
        if not self._config:
            return []

        query_lower = query.lower()
        query_tokens = set(re.findall(r'\b\w+\b', query_lower))
        matches: List[DomainMatch] = []

        for domain_id, domain_data in self._config.get("domains", {}).items():
            triggers = domain_data.get("triggers", [])
            matched = [t for t in triggers if t in query_lower or t in query_tokens]
            if matched:
                confidence = min(len(matched) / max(len(triggers), 1) + 0.1 * len(matched), 1.0)
                matches.append(DomainMatch(domain_id=domain_id, confidence=confidence, matched_triggers=matched))

        matches.sort(key=lambda m: m.confidence, reverse=True)
        threshold = self._config.get("domain_detection", {}).get("confidence_threshold", 0.2)
        return [m for m in matches if m.confidence >= threshold]

    def get_context(self, query: str, level: Optional[str] = None, max_domains: int = 2) -> List[DomainContext]:
        """Get domain-specific context for a query."""
        matches = self.detect_domains(query)
        if not matches:
            fallback = self._config.get("domain_detection", {}).get("fallback_domain", "ai-harness")
            matches = [DomainMatch(domain_id=fallback, confidence=0.5, matched_triggers=[])]

        if level is None:
            level = self._detect_level(query)

        return [ctx for m in matches[:max_domains] if (ctx := self._load_domain_context(m.domain_id, level))]

    def _detect_level(self, query: str) -> str:
        """Auto-detect disclosure level based on query complexity."""
        query_lower = query.lower()
        escalation = self._config.get("loading_rules", {}).get("escalation_triggers", [])
        if any(t in query_lower for t in escalation):
            return "full"
        if any(t in query_lower for t in ["implement", "create", "build", "configure", "setup"]):
            return "standard"
        return "minimal"

    def _load_domain_context(self, domain_id: str, level: str) -> Optional[DomainContext]:
        """Load context for a specific domain at a given level."""
        domain = self._config.get("domains", {}).get(domain_id)
        if not domain:
            return None

        merged = self._merge_levels(domain.get("disclosure", {}), level)
        context_text = merged.get("context", "")
        token_estimate = len(context_text) // 4 + len(merged.get("tools", [])) * 3

        return DomainContext(
            domain_id=domain_id,
            domain_name=domain.get("name", domain_id),
            level=level,
            context_text=context_text,
            tools=merged.get("tools", []),
            hints=merged.get("hints", []),
            mcp_endpoints=merged.get("mcp_endpoints", []),
            skills=merged.get("skills", []),
            docs=merged.get("docs", []),
            research_packs=merged.get("research_packs", []),
            memory_recall=merged.get("memory_recall", []),
            token_estimate=token_estimate,
        )

    def _merge_levels(self, disclosure: Dict[str, Any], target_level: str) -> Dict[str, Any]:
        """Merge disclosure levels following inheritance chain."""
        level_order = ["minimal", "standard", "full"]
        try:
            target_idx = level_order.index(target_level)
        except ValueError:
            target_idx = 0

        merged: Dict[str, Any] = {}
        list_keys = ["tools", "hints", "mcp_endpoints", "skills", "docs", "research_packs", "memory_recall"]

        for level in level_order[:target_idx + 1]:
            level_data = disclosure.get(level, {})
            if "context" in level_data:
                merged["context"] = level_data["context"]
            for key in list_keys:
                if key in level_data:
                    merged.setdefault(key, []).extend(
                        item for item in level_data[key] if item not in merged.get(key, [])
                    )
        return merged

    def list_domains(self) -> List[Dict[str, str]]:
        """List all available domains."""
        return [
            {"id": did, "name": d.get("name", did), "description": d.get("description", "")}
            for did, d in self._config.get("domains", {}).items()
        ]


# Singleton instance
_domain_loader: Optional[DomainLoader] = None


def get_domain_loader() -> DomainLoader:
    """Get or create the singleton DomainLoader instance."""
    global _domain_loader
    if _domain_loader is None:
        _domain_loader = DomainLoader()
    return _domain_loader


def get_domain_context(query: str, level: Optional[str] = None) -> List[DomainContext]:
    """Convenience function to get domain context for a query."""
    return get_domain_loader().get_context(query, level)
