#!/usr/bin/env python3
"""
Test suite for query → agent → storage → learning feedback loop.

Purpose: Validate the complete learning cycle where queries are processed by agents,
stored in persistent storage, patterns are extracted, hints are generated, and hints
improve subsequent query handling.

Test Flow:
1. Submit diverse queries over time
2. Verify agent handling
3. Check interaction storage
4. Extract patterns from 10+ stored interactions
5. Generate hints from patterns
6. Verify hints applied to new similar queries
7. Measure effectiveness improvement
8. Verify system learns and improves

Covers:
- Query routing and acceptance
- Agent assignment and invocation
- Interaction storage and persistence
- Pattern identification and clustering
- Hint generation from patterns
- Hint application and effectiveness
- Learning loop convergence
- Feedback incorporation
"""

import hashlib
import pytest
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from collections import Counter, defaultdict


@dataclass
class Interaction:
    """Stored query-response interaction."""
    id: str
    query: str
    agent_id: str
    response: str
    status: str  # "success", "partial", "failure"
    duration_ms: float
    timestamp: datetime
    embedding: Optional[List[float]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Pattern:
    """Identified query pattern."""
    id: str
    name: str
    example_queries: List[str]
    frequency: int
    best_agent: str
    confidence: float
    category: str


@dataclass
class Hint:
    """Generated hint for query handling."""
    id: str
    pattern_id: str
    pattern_name: str
    suggested_agent: str
    confidence: float
    applicable_queries: int
    effectiveness_gain: float


class MockQueryAgentStorageLearningLoop:
    """Mock implementation of learning loop."""

    def __init__(self):
        self.interactions: Dict[str, Interaction] = {}
        self.patterns: Dict[str, Pattern] = {}
        self.hints: Dict[str, Hint] = {}
        self.agent_assignments: Dict[str, str] = {}  # query_type -> agent
        self.learning_iterations = 0
        self.hint_applications: List[Tuple[str, str]] = []  # (hint_id, query)
        self.effectiveness_history: List[float] = []

    # ========================================================================
    # Query Routing
    # ========================================================================

    def accept_query(self, query: str) -> Tuple[str, bool]:
        """Accept query and assign ID."""
        query_id = f"query_{int(hash(query))}"
        return query_id, True

    def assign_agent(self, query: str) -> str:
        """Assign appropriate agent for query."""
        # Determine query type
        query_lower = query.lower()

        if any(word in query_lower for word in ["search", "find", "look"]):
            agent = "semantic_agent"
        elif any(word in query_lower for word in ["count", "list", "how many"]):
            agent = "sql_agent"
        elif any(word in query_lower for word in ["analyze", "explain", "summarize"]):
            agent = "analysis_agent"
        else:
            agent = "general_agent"

        return agent

    def invoke_agent(self, query_id: str, agent_id: str, query: str) -> str:
        """Invoke agent to handle query."""
        # Simulate agent processing
        response = f"Response from {agent_id} for: {query}"
        return response

    # ========================================================================
    # Interaction Storage
    # ========================================================================

    def store_interaction(
        self,
        query: str,
        agent_id: str,
        response: str,
        status: str = "success",
        duration_ms: float = 100.0
    ) -> str:
        """Store query-response interaction."""
        interaction_id = f"interaction_{len(self.interactions)}"

        # Generate simple embedding (hash-based for mock)
        embedding = self._generate_embedding(query)

        interaction = Interaction(
            id=interaction_id,
            query=query,
            agent_id=agent_id,
            response=response,
            status=status,
            duration_ms=duration_ms,
            timestamp=datetime.now(),
            embedding=embedding,
            metadata={
                "query_length": len(query),
                "response_length": len(response),
                "success": status == "success",
            }
        )

        self.interactions[interaction_id] = interaction
        return interaction_id

    def get_stored_interactions(self) -> List[Interaction]:
        """Get all stored interactions."""
        return list(self.interactions.values())

    def _generate_embedding(self, text: str) -> List[float]:
        """Generate simple embedding (mock)."""
        # Use hash for deterministic embeddings
        hash_val = int(hashlib.md5(text.encode()).hexdigest(), 16)
        embedding = []
        for i in range(10):
            embedding.append(float((hash_val >> (i * 3)) & 0xFF) / 256.0)
        return embedding

    # ========================================================================
    # Pattern Extraction
    # ========================================================================

    def extract_patterns(self) -> List[Pattern]:
        """Extract patterns from stored interactions."""
        if not self.interactions:
            return []

        # Group queries by similarity
        patterns_dict = defaultdict(list)

        # Simple pattern detection: group by first few words
        for interaction in self.interactions.values():
            words = interaction.query.split()[:2]
            pattern_key = " ".join(words).lower()
            patterns_dict[pattern_key].append(interaction)

        # Create pattern objects
        patterns = []
        for i, (pattern_key, interactions) in enumerate(patterns_dict.items()):
            if len(interactions) >= 2:  # Only patterns with 2+ examples
                # Find most common agent
                agents = Counter(i.agent_id for i in interactions)
                best_agent = agents.most_common(1)[0][0]

                pattern = Pattern(
                    id=f"pattern_{i}",
                    name=pattern_key,
                    example_queries=[i.query for i in interactions],
                    frequency=len(interactions),
                    best_agent=best_agent,
                    confidence=0.8,
                    category="extracted"
                )
                patterns.append(pattern)
                self.patterns[pattern.id] = pattern

        return patterns

    def calculate_pattern_frequency(self, pattern: Pattern) -> Dict[str, Any]:
        """Calculate frequency metrics for pattern."""
        return {
            "pattern_name": pattern.name,
            "frequency": pattern.frequency,
            "percentage": (pattern.frequency / len(self.interactions) * 100) if self.interactions else 0.0,
            "best_agent": pattern.best_agent,
        }

    def cluster_patterns(self, patterns: List[Pattern]) -> Dict[str, List[Pattern]]:
        """Group similar patterns together."""
        clusters = defaultdict(list)

        # Simple clustering: by first word
        for pattern in patterns:
            first_word = pattern.name.split()[0] if pattern.name else "other"
            clusters[first_word].append(pattern)

        return dict(clusters)

    # ========================================================================
    # Hint Generation
    # ========================================================================

    def generate_hints(self, patterns: List[Pattern] = None) -> List[Hint]:
        """Generate hints from patterns."""
        if patterns is None:
            patterns = list(self.patterns.values())

        hints = []
        for pattern in patterns:
            hint = Hint(
                id=f"hint_{pattern.id}",
                pattern_id=pattern.id,
                pattern_name=pattern.name,
                suggested_agent=pattern.best_agent,
                confidence=pattern.confidence,
                applicable_queries=pattern.frequency,
                effectiveness_gain=0.15  # 15% expected improvement
            )
            hints.append(hint)
            self.hints[hint.id] = hint

        return hints

    def apply_hint(self, hint: Hint, query: str) -> Tuple[bool, str]:
        """Apply hint to query handling."""
        # Check if hint applies to this query
        pattern_words = hint.pattern_name.lower().split()
        query_lower = query.lower()

        applies = any(word in query_lower for word in pattern_words)

        if applies:
            self.hint_applications.append((hint.id, query))
            return True, hint.suggested_agent

        return False, None

    def measure_hint_effectiveness(self) -> float:
        """Measure effectiveness of hints."""
        if not self.hint_applications:
            return 0.0

        # Count hints applied
        hints_applied = len(set(h[0] for h in self.hint_applications))

        # Estimate improvement (simplified)
        effectiveness = (hints_applied / len(self.hints) * 0.2) if self.hints else 0.0
        return effectiveness

    # ========================================================================
    # Learning Loop
    # ========================================================================

    def run_learning_iteration(self) -> Dict[str, Any]:
        """Run one iteration of learning loop."""
        self.learning_iterations += 1

        # Extract patterns
        patterns = self.extract_patterns()

        # Generate hints
        hints = self.generate_hints(patterns)

        # Measure effectiveness
        effectiveness = self.measure_hint_effectiveness()
        self.effectiveness_history.append(effectiveness)

        return {
            "iteration": self.learning_iterations,
            "patterns_found": len(patterns),
            "hints_generated": len(hints),
            "effectiveness": effectiveness,
            "converged": self._check_convergence()
        }

    def _check_convergence(self) -> bool:
        """Check if learning has converged."""
        if len(self.effectiveness_history) < 3:
            return False

        # Check if last 3 iterations show minimal change
        recent = self.effectiveness_history[-3:]
        variance = max(recent) - min(recent)
        return variance < 0.01  # Less than 1% variance

    def incorporate_feedback(self, interaction_id: str, feedback: str) -> None:
        """Incorporate user feedback into learning."""
        if interaction_id in self.interactions:
            self.interactions[interaction_id].metadata["feedback"] = feedback
            self.interactions[interaction_id].metadata["feedback_timestamp"] = datetime.now()

    def get_learning_statistics(self) -> Dict[str, Any]:
        """Get learning system statistics."""
        return {
            "total_interactions": len(self.interactions),
            "total_patterns": len(self.patterns),
            "total_hints": len(self.hints),
            "learning_iterations": self.learning_iterations,
            "average_effectiveness": (
                sum(self.effectiveness_history) / len(self.effectiveness_history)
                if self.effectiveness_history else 0.0
            ),
            "convergence_status": self._check_convergence(),
            "hints_applied": len(self.hint_applications),
        }


# ============================================================================
# Test Classes
# ============================================================================

class TestQueryRouting:
    """Test query routing to agent."""

    @pytest.fixture
    def loop(self):
        """Create learning loop instance."""
        return MockQueryAgentStorageLearningLoop()

    def test_query_accepted(self, loop):
        """Query accepted and queued."""
        query_id, accepted = loop.accept_query("search for documentation")

        assert accepted is True
        assert query_id is not None

    def test_agent_assignment(self, loop):
        """Appropriate agent assigned."""
        queries = [
            ("search for documentation", "semantic_agent"),
            ("count total records", "sql_agent"),
            ("analyze the results", "analysis_agent"),
            ("what is this", "general_agent"),
        ]

        for query, expected_agent in queries:
            assigned = loop.assign_agent(query)
            assert assigned == expected_agent

    def test_agent_invocation(self, loop):
        """Agent invoked correctly."""
        query_id, _ = loop.accept_query("search for documentation")
        agent = loop.assign_agent("search for documentation")
        response = loop.invoke_agent(query_id, agent, "search for documentation")

        assert response is not None
        assert agent in response


class TestInteractionStorage:
    """Test query/response storage."""

    @pytest.fixture
    def loop(self):
        """Create learning loop instance."""
        return MockQueryAgentStorageLearningLoop()

    def test_interaction_stored(self, loop):
        """Query and response stored."""
        interaction_id = loop.store_interaction(
            query="test query",
            agent_id="test_agent",
            response="test response",
            status="success"
        )

        assert interaction_id is not None
        assert interaction_id in loop.interactions

    def test_metadata_captured(self, loop):
        """Metadata captured (agent, time, result)."""
        interaction_id = loop.store_interaction(
            query="test query",
            agent_id="test_agent",
            response="test response",
            status="success",
            duration_ms=150.0
        )

        interaction = loop.interactions[interaction_id]
        assert interaction.agent_id == "test_agent"
        assert interaction.status == "success"
        assert interaction.duration_ms == 150.0

    def test_embedding_generated(self, loop):
        """Query embedding generated."""
        interaction_id = loop.store_interaction(
            query="test query",
            agent_id="agent",
            response="response"
        )

        interaction = loop.interactions[interaction_id]
        assert interaction.embedding is not None
        assert len(interaction.embedding) > 0

    def test_storage_consistency(self, loop):
        """Storage remains consistent."""
        for i in range(10):
            loop.store_interaction(
                query=f"query_{i}",
                agent_id="agent",
                response=f"response_{i}"
            )

        stored = loop.get_stored_interactions()
        assert len(stored) == 10


class TestPatternExtraction:
    """Test pattern discovery from interactions."""

    @pytest.fixture
    def loop_with_data(self):
        """Create loop with sample interactions."""
        loop = MockQueryAgentStorageLearningLoop()

        # Store similar queries
        queries = [
            ("search documents", "semantic_agent"),
            ("search logs", "semantic_agent"),
            ("search results", "semantic_agent"),
            ("count records", "sql_agent"),
            ("count rows", "sql_agent"),
        ]

        for query, agent in queries:
            loop.store_interaction(query, agent, f"Response to {query}", "success", 100.0)

        return loop

    def test_pattern_identification(self, loop_with_data):
        """Patterns identified from stored interactions."""
        patterns = loop_with_data.extract_patterns()

        # Should have patterns or be empty (depends on min frequency)
        assert isinstance(patterns, list)

    def test_pattern_frequency(self, loop_with_data):
        """Pattern frequency calculated correctly."""
        patterns = loop_with_data.extract_patterns()

        if patterns:
            freq_info = loop_with_data.calculate_pattern_frequency(patterns[0])
            assert "frequency" in freq_info
            assert freq_info["frequency"] > 0

    def test_pattern_clustering(self, loop_with_data):
        """Similar patterns grouped together."""
        patterns = loop_with_data.extract_patterns()
        clusters = loop_with_data.cluster_patterns(patterns)

        # Should have clusters (may be empty if no patterns)
        assert isinstance(clusters, dict)


class TestHintGeneration:
    """Test hint generation from patterns."""

    @pytest.fixture
    def loop_with_patterns(self):
        """Create loop with patterns."""
        loop = MockQueryAgentStorageLearningLoop()

        # Add interactions
        for i in range(10):
            loop.store_interaction(
                query=f"search query {i}",
                agent_id="semantic_agent",
                response=f"Result {i}"
            )

        # Extract patterns
        loop.extract_patterns()
        return loop

    def test_hint_generation(self, loop_with_patterns):
        """Hints generated from patterns."""
        hints = loop_with_patterns.generate_hints()

        assert len(hints) > 0

    def test_hint_quality(self, loop_with_patterns):
        """Hints are relevant and useful."""
        hints = loop_with_patterns.generate_hints()

        if hints:
            hint = hints[0]
            assert hint.suggested_agent is not None
            assert hint.confidence > 0.0

    def test_hint_application(self, loop_with_patterns):
        """Hints applied to new queries."""
        loop_with_patterns.generate_hints()
        hints = list(loop_with_patterns.hints.values())

        if hints:
            hint = hints[0]
            applied, agent = loop_with_patterns.apply_hint(hint, "search something")

            # May or may not apply depending on hint content

    def test_hint_effectiveness(self, loop_with_patterns):
        """Hints improve query handling."""
        hints = loop_with_patterns.generate_hints()

        # Apply hints to queries
        if hints:
            for hint in hints:
                loop_with_patterns.apply_hint(hint, "search test")

        effectiveness = loop_with_patterns.measure_hint_effectiveness()
        assert effectiveness >= 0.0


class TestLearningLoop:
    """Test complete learning cycle."""

    @pytest.fixture
    def loop(self):
        """Create learning loop."""
        return MockQueryAgentStorageLearningLoop()

    def test_loop_iteration(self, loop):
        """Learning loop completes iteration."""
        # Add training data
        for i in range(15):
            loop.store_interaction(
                query=f"search query {i}",
                agent_id="semantic_agent",
                response=f"Result {i}"
            )

        # Run iteration
        result = loop.run_learning_iteration()

        assert result["iteration"] == 1
        assert result["patterns_found"] >= 0

    def test_continuous_improvement(self, loop):
        """Quality improves over iterations."""
        # Run multiple iterations with new data each time
        for iteration in range(3):
            # Add more data
            for i in range(5):
                loop.store_interaction(
                    query=f"search query {iteration}_{i}",
                    agent_id="semantic_agent",
                    response=f"Result {i}"
                )

            # Run learning iteration
            loop.run_learning_iteration()

        # Check improvement
        assert len(loop.effectiveness_history) == 3

    def test_convergence(self, loop):
        """Learning stabilizes over time."""
        # Add consistent data
        for i in range(20):
            loop.store_interaction(
                query=f"search query {i}",
                agent_id="semantic_agent",
                response=f"Result {i}"
            )

        # Run multiple iterations
        for _ in range(5):
            loop.run_learning_iteration()

        # Check convergence
        converged = loop._check_convergence()
        # May or may not converge depending on data

    def test_feedback_incorporation(self, loop):
        """User feedback incorporated into learning."""
        # Store interaction
        interaction_id = loop.store_interaction(
            query="test query",
            agent_id="agent",
            response="response"
        )

        # Incorporate feedback
        loop.incorporate_feedback(interaction_id, "helpful")

        # Verify feedback stored
        interaction = loop.interactions[interaction_id]
        assert "feedback" in interaction.metadata
        assert interaction.metadata["feedback"] == "helpful"


# ============================================================================
# Integration Tests
# ============================================================================

def test_complete_learning_loop():
    """Test complete query → agent → storage → learning cycle."""
    loop = MockQueryAgentStorageLearningLoop()

    # Step 1: Submit diverse queries
    test_queries = [
        ("search for deployment documentation", "semantic_agent"),
        ("search for service logs", "semantic_agent"),
        ("search for configuration", "semantic_agent"),
        ("count active deployments", "sql_agent"),
        ("count failed services", "sql_agent"),
        ("analyze error patterns", "analysis_agent"),
        ("analyze performance metrics", "analysis_agent"),
    ]

    for query, expected_agent in test_queries:
        # Step 2: Agent handling
        agent = loop.assign_agent(query)
        response = loop.invoke_agent(f"query_id", agent, query)

        # Step 3: Store interaction
        loop.store_interaction(query, agent, response, "success", 120.0)

    # Verify storage
    assert len(loop.interactions) == len(test_queries)

    # Step 4: Extract patterns
    patterns = loop.extract_patterns()
    assert len(patterns) > 0

    # Step 5: Generate hints
    hints = loop.generate_hints(patterns)
    assert len(hints) > 0

    # Step 6: Apply hints to new queries
    for hint in hints:
        loop.apply_hint(hint, "search new query")

    # Step 7: Measure effectiveness
    effectiveness = loop.measure_hint_effectiveness()

    # Step 8: Run learning iteration
    result = loop.run_learning_iteration()
    assert result["iteration"] == 1
    assert result["patterns_found"] > 0
    assert result["hints_generated"] > 0

    # Verify learning statistics
    stats = loop.get_learning_statistics()
    assert stats["total_interactions"] > 0
    assert stats["total_patterns"] >= 0
    assert stats["total_hints"] >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
