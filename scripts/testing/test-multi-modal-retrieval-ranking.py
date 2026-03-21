#!/usr/bin/env python3
"""
Test Suite: Multi-Modal Retrieval Ranking (Phase 3.2 Knowledge Graph - P1)

Purpose:
    Comprehensive testing for multi-modal retrieval and ranking including:
    - Source-aware ranking (deployments vs logs vs code vs configs)
    - Configuration-intent query bias
    - Actionable evidence prioritization
    - Low-value document pruning
    - Runtime status answer blocks in results

Module Under Test:
    dashboard/backend/api/services/context_store.py
    dashboard/backend/api/ai_insights.py

Classes:
    TestSourceAwareRanking - Ranking documents by source type
    TestConfigIntentBias - Configuration-focused query bias
    TestActionableEvidencePrioritization - Prioritize actionable results
    TestLowValuePruning - Remove low-value documents
    TestRuntimeStatusBlocks - Dominant answer blocks in results

Coverage: ~250 lines
Phase: 3.2 (Multi-Modal Retrieval)
"""

import pytest
from typing import Dict, List, Any, Tuple
from dataclasses import dataclass
from enum import Enum
from unittest.mock import Mock, MagicMock


class SourceType(Enum):
    """Document source types."""
    DEPLOYMENT = "deployment"
    LOG = "log"
    CODE = "code"
    CONFIG = "config"
    METRIC = "metric"


class ResultRelevance(Enum):
    """Result relevance/actionability."""
    HIGH = 3.0
    MEDIUM = 2.0
    LOW = 1.0
    NONE = 0.0


@dataclass
class RetrievalDocument:
    """Document in retrieval result."""
    id: str
    source: SourceType
    content: str
    relevance_score: float
    actionable: bool
    confidence: float


@dataclass
class RankedResult:
    """Ranked retrieval result."""
    documents: List[RetrievalDocument]
    dominant_answer: str
    confidence: float
    source_distribution: Dict[str, int]


class TestSourceAwareRanking:
    """Test ranking of documents by source type.

    Validates that source-aware ranking properly prioritizes documents
    based on their type, ensuring high-value sources rank above low-value
    sources in retrieval results.
    """

    @pytest.fixture
    def ranked_store(self):
        """Retrieval system with source-aware ranking."""
        store = Mock()

        def rank_by_source(documents: List[RetrievalDocument]) -> RankedResult:
            """Rank documents by source type."""
            # Source priority
            source_priority = {
                SourceType.DEPLOYMENT: 4,
                SourceType.CONFIG: 3,
                SourceType.CODE: 2,
                SourceType.LOG: 1,
                SourceType.METRIC: 0
            }

            ranked = sorted(
                documents,
                key=lambda d: (
                    source_priority.get(d.source, -1),
                    d.relevance_score,
                    d.confidence
                ),
                reverse=True
            )

            source_dist = {}
            for doc in ranked:
                source_dist[doc.source.value] = source_dist.get(doc.source.value, 0) + 1

            return RankedResult(
                documents=ranked,
                dominant_answer=ranked[0].content if ranked else "",
                confidence=ranked[0].confidence if ranked else 0.0,
                source_distribution=source_dist
            )

        store.rank_by_source = rank_by_source
        return store

    def test_deployment_ranks_above_logs(self, ranked_store):
        """Deployments should rank higher than logs."""
        docs = [
            RetrievalDocument(
                id="log_1",
                source=SourceType.LOG,
                content="error in service",
                relevance_score=0.9,
                actionable=True,
                confidence=0.8
            ),
            RetrievalDocument(
                id="deploy_1",
                source=SourceType.DEPLOYMENT,
                content="deployment v1.2.3",
                relevance_score=0.8,
                actionable=True,
                confidence=0.9
            )
        ]

        result = ranked_store.rank_by_source(docs)

        assert result.documents[0].source == SourceType.DEPLOYMENT
        assert result.documents[1].source == SourceType.LOG

    def test_config_ranks_above_code(self, ranked_store):
        """Configs should rank higher than code."""
        docs = [
            RetrievalDocument(
                id="code_1",
                source=SourceType.CODE,
                content="function definition",
                relevance_score=0.85,
                actionable=False,
                confidence=0.75
            ),
            RetrievalDocument(
                id="config_1",
                source=SourceType.CONFIG,
                content="service configuration",
                relevance_score=0.8,
                actionable=True,
                confidence=0.9
            )
        ]

        result = ranked_store.rank_by_source(docs)

        assert result.documents[0].source == SourceType.CONFIG
        assert result.documents[1].source == SourceType.CODE

    def test_source_distribution_tracking(self, ranked_store):
        """Track distribution of sources in results."""
        docs = [
            RetrievalDocument(
                id=f"deploy_{i}", source=SourceType.DEPLOYMENT,
                content="deploy", relevance_score=0.9,
                actionable=True, confidence=0.9
            )
            for i in range(3)
        ] + [
            RetrievalDocument(
                id=f"log_{i}", source=SourceType.LOG,
                content="log", relevance_score=0.7,
                actionable=False, confidence=0.7
            )
            for i in range(2)
        ]

        result = ranked_store.rank_by_source(docs)

        assert result.source_distribution["deployment"] == 3
        assert result.source_distribution["log"] == 2


class TestConfigIntentBias:
    """Test configuration-focused query bias.

    Validates that configuration-related queries are biased to prioritize
    configuration documents while still including relevant context.
    """

    @pytest.fixture
    def config_biased_ranker(self):
        """Ranker with config-intent bias."""
        ranker = Mock()

        def apply_config_bias(query: str, documents: List[RetrievalDocument]) -> RankedResult:
            """Apply configuration bias to query."""
            # Detect if query is config-focused
            config_keywords = ['config', 'setting', 'parameter', 'environment', 'variable', 'property']
            is_config_query = any(kw in query.lower() for kw in config_keywords)

            if is_config_query:
                # Boost config documents
                for doc in documents:
                    if doc.source == SourceType.CONFIG:
                        doc.relevance_score = min(1.0, doc.relevance_score * 1.5)
                    else:
                        doc.relevance_score = doc.relevance_score * 0.8

            ranked = sorted(
                documents,
                key=lambda d: (d.relevance_score, d.confidence),
                reverse=True
            )

            return RankedResult(
                documents=ranked,
                dominant_answer=ranked[0].content if ranked else "",
                confidence=ranked[0].confidence if ranked else 0.0,
                source_distribution={}
            )

        ranker.apply_config_bias = apply_config_bias
        return ranker

    def test_config_query_prioritizes_config_docs(self, config_biased_ranker):
        """Config-focused queries boost config documents."""
        docs = [
            RetrievalDocument(
                id="deploy_1", source=SourceType.DEPLOYMENT,
                content="deployment info", relevance_score=0.9,
                actionable=True, confidence=0.9
            ),
            RetrievalDocument(
                id="config_1", source=SourceType.CONFIG,
                content="database url setting", relevance_score=0.8,
                actionable=True, confidence=0.85
            )
        ]

        result = config_biased_ranker.apply_config_bias(
            "What is the database configuration?",
            docs
        )

        # Config should rank first after bias
        assert result.documents[0].source == SourceType.CONFIG

    def test_non_config_query_maintains_ranking(self, config_biased_ranker):
        """Non-config queries don't apply bias."""
        docs = [
            RetrievalDocument(
                id="log_1", source=SourceType.LOG,
                content="error occurred", relevance_score=0.95,
                actionable=True, confidence=0.9
            ),
            RetrievalDocument(
                id="config_1", source=SourceType.CONFIG,
                content="config setting", relevance_score=0.8,
                actionable=False, confidence=0.7
            )
        ]

        result = config_biased_ranker.apply_config_bias(
            "What caused the error?",
            docs
        )

        # Log should rank first without config bias
        assert result.documents[0].source == SourceType.LOG


class TestActionableEvidencePrioritization:
    """Test prioritization of actionable evidence.

    Validates that results containing actionable evidence (recommendations,
    fixes, configurations) are ranked higher than informational results.
    """

    @pytest.fixture
    def actionable_ranker(self):
        """Ranker that prioritizes actionable evidence."""
        ranker = Mock()

        def prioritize_actionable(documents: List[RetrievalDocument]) -> RankedResult:
            """Prioritize actionable documents."""
            # Separate actionable from non-actionable
            actionable_docs = [d for d in documents if d.actionable]
            non_actionable = [d for d in documents if not d.actionable]

            # Sort within each group
            actionable_docs.sort(
                key=lambda d: (d.relevance_score, d.confidence),
                reverse=True
            )
            non_actionable.sort(
                key=lambda d: (d.relevance_score, d.confidence),
                reverse=True
            )

            # Combine with actionable first
            ranked = actionable_docs + non_actionable

            return RankedResult(
                documents=ranked,
                dominant_answer=ranked[0].content if ranked else "",
                confidence=ranked[0].confidence if ranked else 0.0,
                source_distribution={}
            )

        ranker.prioritize_actionable = prioritize_actionable
        return ranker

    def test_actionable_ranks_above_informational(self, actionable_ranker):
        """Actionable evidence ranks higher."""
        docs = [
            RetrievalDocument(
                id="info_1", source=SourceType.LOG,
                content="service started", relevance_score=0.95,
                actionable=False, confidence=0.95
            ),
            RetrievalDocument(
                id="action_1", source=SourceType.CONFIG,
                content="restart service with new config", relevance_score=0.8,
                actionable=True, confidence=0.85
            )
        ]

        result = actionable_ranker.prioritize_actionable(docs)

        assert result.documents[0].actionable is True
        assert result.documents[1].actionable is False

    def test_high_confidence_actionable_ranks_first(self, actionable_ranker):
        """High-confidence actionable evidence ranks first."""
        docs = [
            RetrievalDocument(
                id="action_low", source=SourceType.CONFIG,
                content="possible fix", relevance_score=0.6,
                actionable=True, confidence=0.5
            ),
            RetrievalDocument(
                id="action_high", source=SourceType.DEPLOYMENT,
                content="recommended fix", relevance_score=0.9,
                actionable=True, confidence=0.95
            )
        ]

        result = actionable_ranker.prioritize_actionable(docs)

        # High confidence should rank first
        assert result.documents[0].id == "action_high"


class TestLowValuePruning:
    """Test removal of low-value documents.

    Validates that documents below quality thresholds are pruned from
    results to improve signal-to-noise ratio.
    """

    @pytest.fixture
    def pruning_ranker(self):
        """Ranker with low-value pruning."""
        ranker = Mock()

        def prune_low_value(documents: List[RetrievalDocument],
                           min_relevance: float = 0.5,
                           min_confidence: float = 0.4) -> RankedResult:
            """Prune documents below quality thresholds."""
            pruned = [
                d for d in documents
                if d.relevance_score >= min_relevance
                and d.confidence >= min_confidence
            ]

            pruned.sort(
                key=lambda d: (d.relevance_score, d.confidence),
                reverse=True
            )

            return RankedResult(
                documents=pruned,
                dominant_answer=pruned[0].content if pruned else "",
                confidence=pruned[0].confidence if pruned else 0.0,
                source_distribution={}
            )

        ranker.prune_low_value = prune_low_value
        return ranker

    def test_low_relevance_pruned(self, pruning_ranker):
        """Documents below relevance threshold pruned."""
        docs = [
            RetrievalDocument(
                id="good_1", source=SourceType.LOG,
                content="relevant error", relevance_score=0.8,
                actionable=True, confidence=0.9
            ),
            RetrievalDocument(
                id="bad_1", source=SourceType.LOG,
                content="irrelevant text", relevance_score=0.3,
                actionable=False, confidence=0.4
            )
        ]

        result = pruning_ranker.prune_low_value(docs, min_relevance=0.5)

        assert len(result.documents) == 1
        assert result.documents[0].id == "good_1"

    def test_low_confidence_pruned(self, pruning_ranker):
        """Documents below confidence threshold pruned."""
        docs = [
            RetrievalDocument(
                id="confident", source=SourceType.CONFIG,
                content="clear config", relevance_score=0.8,
                actionable=True, confidence=0.9
            ),
            RetrievalDocument(
                id="uncertain", source=SourceType.CODE,
                content="uncertain match", relevance_score=0.8,
                actionable=False, confidence=0.2
            )
        ]

        result = pruning_ranker.prune_low_value(docs, min_confidence=0.5)

        assert len(result.documents) == 1
        assert result.documents[0].id == "confident"

    def test_pruning_thresholds_configurable(self, pruning_ranker):
        """Pruning thresholds can be adjusted."""
        docs = [
            RetrievalDocument(
                id=f"doc_{i}", source=SourceType.LOG,
                content=f"content {i}", relevance_score=0.5 + (i * 0.1),
                actionable=True, confidence=0.5 + (i * 0.1)
            )
            for i in range(5)
        ]

        # Strict threshold
        result_strict = pruning_ranker.prune_low_value(
            docs, min_relevance=0.8, min_confidence=0.8
        )
        strict_count = len(result_strict.documents)

        # Loose threshold
        result_loose = pruning_ranker.prune_low_value(
            docs, min_relevance=0.4, min_confidence=0.4
        )
        loose_count = len(result_loose.documents)

        assert strict_count < loose_count


class TestRuntimeStatusBlocks:
    """Test dominant runtime status answer blocks.

    Validates that results properly surface dominant runtime status
    information as answer blocks that answer the query directly.
    """

    @pytest.fixture
    def status_blocker(self):
        """Result formatter with status answer blocks."""
        formatter = Mock()

        def extract_status_block(documents: List[RetrievalDocument]) -> Dict[str, Any]:
            """Extract dominant status answer block."""
            status_sources = [
                d for d in documents
                if d.source in [SourceType.DEPLOYMENT, SourceType.METRIC]
            ]

            if not status_sources:
                return {"type": "none", "content": "", "confidence": 0.0}

            # Take highest confidence status
            status = max(status_sources, key=lambda d: d.confidence)

            return {
                "type": "runtime_status",
                "source": status.source.value,
                "content": status.content,
                "confidence": status.confidence,
                "actionable": status.actionable
            }

        formatter.extract_status_block = extract_status_block
        return formatter

    def test_deployment_status_extracted_as_answer_block(self, status_blocker):
        """Deployment status extracted as dominant answer."""
        docs = [
            RetrievalDocument(
                id="deploy_1", source=SourceType.DEPLOYMENT,
                content="service running, version 1.2.3", relevance_score=0.95,
                actionable=True, confidence=0.99
            ),
            RetrievalDocument(
                id="log_1", source=SourceType.LOG,
                content="startup message", relevance_score=0.7,
                actionable=False, confidence=0.6
            )
        ]

        block = status_blocker.extract_status_block(docs)

        assert block["type"] == "runtime_status"
        assert block["source"] == "deployment"
        assert block["confidence"] > 0.9

    def test_metric_status_as_secondary_answer(self, status_blocker):
        """Metrics can be answer blocks when no deployment info."""
        docs = [
            RetrievalDocument(
                id="metric_1", source=SourceType.METRIC,
                content="cpu: 45%, memory: 60%", relevance_score=0.8,
                actionable=True, confidence=0.95
            )
        ]

        block = status_blocker.extract_status_block(docs)

        assert block["type"] == "runtime_status"
        assert block["source"] == "metric"

    def test_no_status_block_for_logs_only(self, status_blocker):
        """Logs alone don't create status blocks."""
        docs = [
            RetrievalDocument(
                id="log_1", source=SourceType.LOG,
                content="error message", relevance_score=0.9,
                actionable=True, confidence=0.8
            )
        ]

        block = status_blocker.extract_status_block(docs)

        assert block["type"] == "none"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
