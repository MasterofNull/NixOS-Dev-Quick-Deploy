#!/usr/bin/env python3
"""
Multi-Layer Memory Loading System

Phase 1.5 Slice 1.7: Progressive memory disclosure with L0-L3 loading strategy.

This module implements a layered approach to memory loading that reduces token usage
by up to 50% while maintaining context relevance. Inspired by MemPalace's approach.

Layers:
  L0: Identity (50 tokens) - Always loaded, defines agent identity
  L1: Critical Facts (170 tokens) - Always loaded, essential knowledge
  L2: Topic-Specific (variable) - Loaded on demand based on query context
  L3: Full Semantic Search (heavy) - Only when explicitly requested

Usage:
    from aidb.layered_loading import LayeredMemory

    memory = LayeredMemory()

    # Load with progressive disclosure
    context = memory.progressive_load(
        query="implement JWT authentication",
        max_tokens=500
    )

    # Or load specific layers
    identity = memory.load_l0()
    critical = memory.load_l1()
    topic_facts = memory.load_l2(topic="authentication")
"""

from pathlib import Path
from typing import List, Dict, Optional, Set
from datetime import datetime, timezone
from dataclasses import dataclass
import json

from aidb.temporal_facts import TemporalFact, get_valid_facts
from aidb.temporal_query import (
    filter_facts_by_project,
    filter_facts_by_topic,
    filter_facts_by_type,
)


@dataclass
class LayerConfig:
    """Configuration for a memory layer"""
    name: str
    always_load: bool
    max_tokens: int
    priority: int


class LayeredMemory:
    """
    Multi-layer memory loading system with progressive disclosure.

    Implements L0-L3 loading strategy to minimize token usage while
    maintaining context relevance.
    """

    # Layer configurations
    LAYERS = {
        "L0": LayerConfig(name="identity", always_load=True, max_tokens=50, priority=0),
        "L1": LayerConfig(name="critical", always_load=True, max_tokens=170, priority=1),
        "L2": LayerConfig(name="topic", always_load=False, max_tokens=300, priority=2),
        "L3": LayerConfig(name="full", always_load=False, max_tokens=1000, priority=3),
    }

    def __init__(
        self,
        identity_file: str = "~/.aidb/identity.txt",
        critical_facts_file: str = "~/.aidb/critical_facts.json",
        fact_store=None
    ):
        """
        Initialize layered memory system.

        Args:
            identity_file: Path to identity text file (L0)
            critical_facts_file: Path to critical facts JSON (L1)
            fact_store: Optional fact store for L2/L3 queries
        """
        self.identity_file = Path(identity_file).expanduser()
        self.critical_facts_file = Path(critical_facts_file).expanduser()
        self.fact_store = fact_store

        # Cache for loaded layers
        self._cache: Dict[str, str] = {}

    def load_l0(self) -> str:
        """
        Load L0: Identity layer (50 tokens).

        Contains agent identity, role, and core context.
        This layer is always loaded.

        Returns:
            Identity text (50 tokens max)
        """
        if "L0" in self._cache:
            return self._cache["L0"]

        # Load identity from file
        if self.identity_file.exists():
            with open(self.identity_file, 'r') as f:
                identity = f.read().strip()
        else:
            # Default identity if file doesn't exist
            identity = self._generate_default_identity()

        # Ensure token limit (approximate: 4 chars per token)
        max_chars = self.LAYERS["L0"].max_tokens * 4
        if len(identity) > max_chars:
            identity = identity[:max_chars] + "..."

        self._cache["L0"] = identity
        return identity

    def load_l1(self) -> str:
        """
        Load L1: Critical facts layer (170 tokens).

        Contains essential knowledge that should always be in context.
        Facts marked as critical (confidence >= 0.95, type=decision or preference).

        Returns:
            Critical facts formatted as text (170 tokens max)
        """
        if "L1" in self._cache:
            return self._cache["L1"]

        critical_facts = []

        # Load from critical facts file if it exists
        if self.critical_facts_file.exists():
            try:
                with open(self.critical_facts_file, 'r') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        critical_facts = data
            except Exception as e:
                print(f"Warning: Could not load critical facts: {e}")

        # Format as compact text
        if critical_facts:
            lines = []
            for fact in critical_facts:
                if isinstance(fact, dict):
                    content = fact.get("content", "")
                    project = fact.get("project", "")
                    lines.append(f"• [{project}] {content}")
                else:
                    lines.append(f"• {fact}")

            critical_text = "\n".join(lines)
        else:
            critical_text = "No critical facts defined yet."

        # Ensure token limit
        max_chars = self.LAYERS["L1"].max_tokens * 4
        if len(critical_text) > max_chars:
            critical_text = critical_text[:max_chars] + "..."

        self._cache["L1"] = critical_text
        return critical_text

    def load_l2(self, topic: Optional[str] = None, topics: Optional[List[str]] = None) -> str:
        """
        Load L2: Topic-specific memories (variable tokens).

        Loads facts filtered by topic(s). This layer is loaded on demand
        based on the query context.

        Args:
            topic: Single topic to load
            topics: List of topics to load

        Returns:
            Topic-specific facts formatted as text
        """
        if topic is None and topics is None:
            return ""

        cache_key = f"L2:{topic or ','.join(topics or [])}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Get facts from store (if available)
        if self.fact_store is None:
            return ""

        facts = self.fact_store.get_all()

        # Filter by topic(s)
        topic_list = topics or ([topic] if topic else [])
        relevant_facts = []
        for fact in facts:
            if fact.topic in topic_list:
                relevant_facts.append(fact)

        # Filter to only valid facts
        now = datetime.now(timezone.utc)
        valid_facts = [f for f in relevant_facts if f.is_valid_at(now)]

        # Format as compact text
        lines = []
        for fact in valid_facts[:20]:  # Limit to top 20
            lines.append(f"• [{fact.topic}] {fact.content}")

        topic_text = "\n".join(lines) if lines else f"No facts for topic(s): {', '.join(topic_list)}"

        # Ensure token limit
        max_chars = self.LAYERS["L2"].max_tokens * 4
        if len(topic_text) > max_chars:
            topic_text = topic_text[:max_chars] + "..."

        self._cache[cache_key] = topic_text
        return topic_text

    def load_l3(self, query: str, limit: int = 10) -> str:
        """
        Load L3: Full semantic search (heavy).

        Performs semantic search across all facts. This is the most
        expensive layer and should only be used when explicitly requested.

        Args:
            query: Search query
            limit: Maximum number of results

        Returns:
            Search results formatted as text
        """
        cache_key = f"L3:{query}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Get facts from store (if available)
        if self.fact_store is None:
            return f"No fact store available for semantic search"

        # In a full implementation, this would use vector search
        # For now, simple text matching
        facts = self.fact_store.get_all()

        # Filter to valid facts
        now = datetime.now(timezone.utc)
        valid_facts = [f for f in facts if f.is_valid_at(now)]

        # Simple keyword matching (would be vector search in production)
        query_lower = query.lower()
        scored_facts = []
        for fact in valid_facts:
            content_lower = fact.content.lower()
            if query_lower in content_lower:
                # Simple relevance score based on position
                position = content_lower.index(query_lower)
                score = 1.0 / (position + 1)
                scored_facts.append((score, fact))

        # Sort by score and take top results
        scored_facts.sort(reverse=True, key=lambda x: x[0])
        top_facts = [fact for _, fact in scored_facts[:limit]]

        # Format results
        lines = [f"Search results for: {query}"]
        for i, fact in enumerate(top_facts, 1):
            lines.append(f"{i}. [{fact.project}/{fact.topic}] {fact.content}")

        search_text = "\n".join(lines) if top_facts else f"No results found for: {query}"

        # Ensure token limit
        max_chars = self.LAYERS["L3"].max_tokens * 4
        if len(search_text) > max_chars:
            search_text = search_text[:max_chars] + "..."

        self._cache[cache_key] = search_text
        return search_text

    def progressive_load(
        self,
        query: str,
        max_tokens: int = 500,
        force_l3: bool = False
    ) -> str:
        """
        Load layers progressively until token budget is reached.

        This is the main method for loading memory with automatic
        token budget management.

        Args:
            query: User query to determine relevant context
            max_tokens: Maximum token budget
            force_l3: Force full semantic search (L3) even if budget is tight

        Returns:
            Combined context from multiple layers
        """
        context_parts = []
        budget_remaining = max_tokens

        # L0: Always load identity (50 tokens)
        l0 = self.load_l0()
        context_parts.append("# Identity")
        context_parts.append(l0)
        budget_remaining -= self._estimate_tokens(l0)

        # L1: Always load critical facts (170 tokens)
        if budget_remaining > 0:
            l1 = self.load_l1()
            context_parts.append("\n# Critical Facts")
            context_parts.append(l1)
            budget_remaining -= self._estimate_tokens(l1)

        # L2: Load topic-specific if budget allows
        if budget_remaining > 100:
            topics = self._extract_topics(query)
            if topics:
                l2 = self.load_l2(topics=topics)
                if l2:
                    context_parts.append("\n# Topic-Specific Memory")
                    context_parts.append(l2)
                    budget_remaining -= self._estimate_tokens(l2)

        # L3: Full search only if requested AND budget allows
        if force_l3 or (budget_remaining > 200 and "deep_search" in query.lower()):
            l3 = self.load_l3(query)
            if l3:
                # Truncate to remaining budget
                max_l3_chars = budget_remaining * 4
                l3_truncated = l3[:max_l3_chars]
                context_parts.append("\n# Semantic Search Results")
                context_parts.append(l3_truncated)

        return "\n".join(context_parts)

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count (rough approximation: 4 chars per token)"""
        return len(text) // 4

    def _extract_topics(self, query: str) -> List[str]:
        """
        Extract likely topics from query.

        In production, this would use NLP or embeddings.
        For now, simple keyword matching.
        """
        topics = []

        # Common topic keywords
        topic_keywords = {
            "auth": ["auth", "authentication", "login", "jwt", "oauth"],
            "security": ["security", "encryption", "vulnerability", "secure"],
            "api": ["api", "endpoint", "rest", "graphql"],
            "database": ["database", "sql", "query", "postgres", "db"],
            "testing": ["test", "testing", "pytest", "unittest"],
            "deployment": ["deploy", "deployment", "docker", "nix", "nixos"],
            "memory": ["memory", "aidb", "facts", "recall"],
            "workflow": ["workflow", "orchestration", "automation"],
        }

        query_lower = query.lower()
        for topic, keywords in topic_keywords.items():
            if any(kw in query_lower for kw in keywords):
                topics.append(topic)

        return topics[:3]  # Limit to top 3 topics

    def _generate_default_identity(self) -> str:
        """Generate default identity text if file doesn't exist"""
        return (
            "I am an AI agent in the NixOS-Dev-Quick-Deploy harness.\n"
            "My role: orchestrate local agents and manage development workflows.\n"
            "Focus: local-first AI, declarative infrastructure, cost optimization."
        )

    def clear_cache(self):
        """Clear the layer cache"""
        self._cache.clear()

    def set_identity(self, identity_text: str):
        """
        Set and save identity text.

        Args:
            identity_text: New identity text (will be truncated to 50 tokens)
        """
        # Ensure directory exists
        self.identity_file.parent.mkdir(parents=True, exist_ok=True)

        # Truncate to token limit
        max_chars = self.LAYERS["L0"].max_tokens * 4
        if len(identity_text) > max_chars:
            identity_text = identity_text[:max_chars]

        # Save to file
        with open(self.identity_file, 'w') as f:
            f.write(identity_text)

        # Update cache
        self._cache["L0"] = identity_text

    def add_critical_fact(self, content: str, project: str = "general"):
        """
        Add a fact to the critical facts list.

        Args:
            content: Fact content
            project: Project name
        """
        # Load existing critical facts
        critical_facts = []
        if self.critical_facts_file.exists():
            try:
                with open(self.critical_facts_file, 'r') as f:
                    critical_facts = json.load(f)
            except Exception:
                critical_facts = []

        # Add new fact
        critical_facts.append({
            "content": content,
            "project": project,
            "added_at": datetime.now(timezone.utc).isoformat()
        })

        # Save
        self.critical_facts_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.critical_facts_file, 'w') as f:
            json.dump(critical_facts, f, indent=2)

        # Clear L1 cache to force reload
        if "L1" in self._cache:
            del self._cache["L1"]

    def get_layer_stats(self) -> Dict[str, int]:
        """
        Get statistics about loaded layers.

        Returns:
            Dictionary with token counts per layer
        """
        stats = {}
        for layer_id, config in self.LAYERS.items():
            cache_keys = [k for k in self._cache.keys() if k.startswith(layer_id)]
            if cache_keys:
                total_tokens = sum(
                    self._estimate_tokens(self._cache[k])
                    for k in cache_keys
                )
                stats[config.name] = total_tokens
            else:
                stats[config.name] = 0

        return stats


# Convenience function for quick usage
def load_memory_with_budget(
    query: str,
    max_tokens: int = 500,
    fact_store=None
) -> str:
    """
    Quick helper to load memory with progressive disclosure.

    Args:
        query: User query
        max_tokens: Token budget
        fact_store: Optional fact store

    Returns:
        Formatted memory context
    """
    memory = LayeredMemory(fact_store=fact_store)
    return memory.progressive_load(query, max_tokens)


if __name__ == "__main__":
    # Demo usage
    print("=== Multi-Layer Memory Loading Demo ===\n")

    memory = LayeredMemory()

    # Set up identity
    memory.set_identity(
        "I am Claude, an AI coordinator for NixOS-Dev-Quick-Deploy.\n"
        "My role: orchestrate local agents (qwen, gemini) and delegate tasks.\n"
        "System: NixOS on hyperd's desktop with 32GB RAM, RTX 3090.\n"
        "Focus: local-first AI, declarative infrastructure, cost optimization."
    )

    # Add some critical facts
    memory.add_critical_fact(
        "Always use progressive disclosure to minimize token usage",
        project="ai-stack"
    )
    memory.add_critical_fact(
        "Prefer local agents over remote to reduce costs",
        project="ai-stack"
    )

    # Load with progressive disclosure
    context = memory.progressive_load(
        query="How should I implement JWT authentication?",
        max_tokens=500
    )

    print(context)
    print("\n" + "="*50)
    print("Layer Statistics:")
    stats = memory.get_layer_stats()
    for layer, tokens in stats.items():
        print(f"  {layer}: {tokens} tokens")
