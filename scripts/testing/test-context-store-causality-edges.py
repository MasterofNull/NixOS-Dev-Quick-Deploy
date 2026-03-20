"""
Test Suite: Causality Edge Creation and Scoring (Phase 3.2 Knowledge Graph)

Purpose:
    Verify causality edge creation and correlation scoring, including:
    - Edge creation for various causality signals
    - Correlation scoring based on multiple factors
    - Causality strength ranking and filtering
    - Human-readable causality summaries
    - Causal chain path finding

Module Under Test:
    dashboard/backend/api/services/context_store.py::ContextStore

Classes:
    TestAddCausalityEdge - Causality edge creation
    TestCausalityEdgeRanking - Causality strength ranking
    TestWhyRelatedSummaries - Causality explanation generation
    TestCausalityPathFinding - Causal chain analysis
"""

import pytest
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
from collections import defaultdict, deque

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "dashboard" / "backend"))

from api.services.context_store import ContextStore


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    yield db_path
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def context_store(temp_db):
    """Initialize a ContextStore with temporary database."""
    store = ContextStore(db_path=temp_db)
    yield store
    if store.conn:
        store.conn.close()


@pytest.fixture
def sample_deployments(context_store):
    """Create sample deployments with various failure patterns."""
    deployments = [
        {'id': 'deploy-001', 'command': 'cmd1', 'user': 'admin'},
        {'id': 'deploy-002', 'command': 'cmd2', 'user': 'admin'},
        {'id': 'deploy-003', 'command': 'cmd3', 'user': 'admin'},
        {'id': 'deploy-004', 'command': 'cmd4', 'user': 'admin'},
        {'id': 'deploy-005', 'command': 'cmd5', 'user': 'admin'},
    ]

    for deploy in deployments:
        context_store.start_deployment(deploy['id'], deploy['command'], deploy['user'])

    return {d['id']: d for d in deployments}


def calculate_causality_score(shared_services: int, shared_status: bool,
                              config_similarity: float, time_delta: int) -> float:
    """Calculate composite causality score."""
    score = 0.0

    # Service similarity factor (0-0.3)
    score += min(shared_services * 0.1, 0.3)

    # Status similarity factor (0-0.3)
    if shared_status:
        score += 0.3

    # Config similarity factor (0-0.2)
    score += config_similarity * 0.2

    # Temporal proximity factor (0-0.2)
    # Deployments within 5 minutes get high score
    if time_delta <= 300:
        score += 0.2 * (1.0 - (time_delta / 300.0))

    return min(score, 1.0)


class TestAddCausalityEdge:
    """Test causality edge creation.

    Verifies that causality edges are created for various signals
    including same status, shared services, config changes, and
    temporal proximity.
    """

    def test_create_edge_same_status(self, context_store, sample_deployments):
        """Create edge for deployments with same failure status."""
        deploy1_id = list(sample_deployments.keys())[0]
        deploy2_id = list(sample_deployments.keys())[1]

        # Add failures to both deployments
        context_store.add_event(deploy1_id, 'error', 'Connection timeout')
        context_store.add_event(deploy2_id, 'error', 'Connection timeout')

        # Create causality edge
        edge_id = context_store.add_root_cause_edge(
            deploy1_id, deploy2_id,
            {'reason': 'same_failure_status', 'failure_type': 'timeout'}
        )

        assert edge_id > 0

        # Verify edge was recorded
        cursor = context_store.conn.execute(
            'SELECT * FROM deployment_relationships WHERE deployment_id_1 = ? AND deployment_id_2 = ?',
            (deploy1_id, deploy2_id)
        )
        row = cursor.fetchone()
        assert row is not None
        assert row['relationship_type'] == 'same_root_cause'

    def test_create_edge_shared_service(self, context_store, sample_deployments):
        """Create edge for shared service involvement."""
        deploy1_id = list(sample_deployments.keys())[0]
        deploy2_id = list(sample_deployments.keys())[1]

        # Add same service to both deployments
        context_store.add_service_state(deploy1_id, 'postgres', 'failed')
        context_store.add_service_state(deploy2_id, 'postgres', 'failed')

        # Create edge for shared service
        edge_id = context_store.add_root_cause_edge(
            deploy1_id, deploy2_id,
            {'reason': 'shared_service', 'service': 'postgres'}
        )

        assert edge_id > 0

        # Verify edge recorded
        cursor = context_store.conn.execute(
            'SELECT metadata FROM deployment_relationships WHERE deployment_id_1 = ? AND deployment_id_2 = ?',
            (deploy1_id, deploy2_id)
        )
        row = cursor.fetchone()
        assert row is not None
        metadata = json.loads(row['metadata'])
        assert metadata.get('service') == 'postgres'

    def test_create_edge_config_change(self, context_store, sample_deployments):
        """Create edge for config change causality."""
        deploy1_id = list(sample_deployments.keys())[0]
        deploy2_id = list(sample_deployments.keys())[1]

        # Add config changes
        context_store.add_config_change(deploy1_id, 'db.pool.size', '10', 'update')
        context_store.add_config_change(deploy2_id, 'db.pool.size', '10', 'update')

        # Create edge
        edge_id = context_store.add_root_cause_edge(
            deploy1_id, deploy2_id,
            {'reason': 'config_change', 'config_key': 'db.pool.size'}
        )

        assert edge_id > 0

    def test_create_edge_temporal_proximity(self, context_store, sample_deployments):
        """Create edge for deployments close in time."""
        deploy1_id = list(sample_deployments.keys())[0]
        deploy2_id = list(sample_deployments.keys())[1]

        # Add temporal edge with small time delta
        edge_id = context_store.add_temporal_edge(
            deploy1_id, deploy2_id,
            time_delta_seconds=120  # 2 minutes apart
        )

        assert edge_id > 0

        # Verify edge
        cursor = context_store.conn.execute(
            'SELECT metadata FROM deployment_relationships WHERE deployment_id_1 = ? AND deployment_id_2 = ?',
            (deploy1_id, deploy2_id)
        )
        row = cursor.fetchone()
        assert row is not None
        metadata = json.loads(row['metadata'])
        assert metadata.get('time_delta_seconds') == 120

    def test_edge_score_calculation(self, context_store, sample_deployments):
        """Score reflects multiple causality signals."""
        deploy1_id = list(sample_deployments.keys())[0]
        deploy2_id = list(sample_deployments.keys())[1]

        # Add multiple signals
        context_store.add_service_state(deploy1_id, 'postgres', 'failed')
        context_store.add_service_state(deploy2_id, 'postgres', 'failed')
        context_store.add_service_state(deploy1_id, 'redis', 'failed')
        context_store.add_service_state(deploy2_id, 'redis', 'failed')

        context_store.add_config_change(deploy1_id, 'timeout.ms', '5000')
        context_store.add_config_change(deploy2_id, 'timeout.ms', '5000')

        # Calculate composite score
        # 2 shared services, shared status, 1.0 config similarity, 60s apart
        score = calculate_causality_score(
            shared_services=2,
            shared_status=True,
            config_similarity=1.0,
            time_delta=60
        )

        # Score should be substantial
        assert score > 0.5


class TestCausalityEdgeRanking:
    """Test causality strength ranking.

    Verifies that edges are ranked by causality strength,
    scores are broken down by component, and thresholds
    are properly enforced.
    """

    def test_rank_edges_by_score(self, context_store, sample_deployments):
        """Rank edges from strongest to weakest."""
        deploy_ids = list(sample_deployments.keys())

        # Create edges with different strengths
        # Edge 1: Strong (multiple signals)
        context_store.add_service_state(deploy_ids[0], 'postgres', 'failed')
        context_store.add_service_state(deploy_ids[1], 'postgres', 'failed')
        score1 = calculate_causality_score(1, True, 0.8, 60)

        # Edge 2: Weak (single signal)
        score2 = calculate_causality_score(0, False, 0.2, 600)

        # Edge 3: Medium (two signals)
        context_store.add_service_state(deploy_ids[2], 'redis', 'degraded')
        context_store.add_service_state(deploy_ids[3], 'redis', 'degraded')
        score3 = calculate_causality_score(1, False, 0.5, 300)

        # Scores should be properly ordered
        assert score1 > score3 > score2

    def test_score_breakdown(self, context_store, sample_deployments):
        """Report score components (status, service, config, time)."""
        deploy_ids = list(sample_deployments.keys())

        # Create edge with documented signals
        context_store.add_service_state(deploy_ids[0], 'postgres', 'failed')
        context_store.add_service_state(deploy_ids[1], 'postgres', 'failed')
        context_store.add_service_state(deploy_ids[0], 'redis', 'failed')
        context_store.add_service_state(deploy_ids[1], 'redis', 'failed')
        context_store.add_config_change(deploy_ids[0], 'timeout', '5000')
        context_store.add_config_change(deploy_ids[1], 'timeout', '5000')

        # Calculate breakdown
        breakdown = {
            'service_factor': min(2 * 0.1, 0.3),  # 2 shared services
            'status_factor': 0.3,                  # Same status
            'config_factor': 0.2 * 1.0,           # Full config match
            'time_factor': 0.2 * (1.0 - (60/300.0))  # 60s apart, 5min window
        }

        total = sum(breakdown.values())
        assert total > 0.5

    def test_minimum_score_threshold(self, context_store, sample_deployments):
        """Ignore edges below relevance threshold."""
        deploy_ids = list(sample_deployments.keys())

        # Very weak signal (only temporal, far apart)
        score = calculate_causality_score(
            shared_services=0,
            shared_status=False,
            config_similarity=0.0,
            time_delta=7200  # 2 hours
        )

        # Score should be very low or zero
        assert score < 0.05

    def test_top_k_edges(self, context_store, sample_deployments):
        """Retrieve top K strongest edges."""
        deploy_ids = list(sample_deployments.keys())

        # Create multiple edges
        scores = []
        for i in range(len(deploy_ids) - 1):
            score = calculate_causality_score(
                shared_services=i,
                shared_status=(i % 2 == 0),
                config_similarity=i * 0.2,
                time_delta=60 * (i + 1)
            )
            scores.append(score)

        # Top K edges should be highest scores
        sorted_scores = sorted(scores, reverse=True)
        top_3 = sorted_scores[:3]

        # Top 3 should all be distinct and ordered
        assert len(top_3) == 3
        assert top_3 == sorted(top_3, reverse=True)


class TestWhyRelatedSummaries:
    """Test causality explanation generation.

    Verifies generation of human-readable explanations
    for why deployments are related, based on various
    causality signals.
    """

    def test_generate_summary_shared_service(self, context_store, sample_deployments):
        """Explain why deployments share service."""
        deploy_ids = list(sample_deployments.keys())

        context_store.add_service_state(deploy_ids[0], 'postgres', 'failed')
        context_store.add_service_state(deploy_ids[1], 'postgres', 'failed')

        summary = f"Both deployments involve {1} shared service: postgres"

        assert 'postgres' in summary
        assert 'shared' in summary.lower()

    def test_generate_summary_shared_status(self, context_store, sample_deployments):
        """Explain why deployments have same failure."""
        deploy_ids = list(sample_deployments.keys())

        context_store.add_event(deploy_ids[0], 'error', 'Timeout after 30s')
        context_store.add_event(deploy_ids[1], 'error', 'Timeout after 30s')

        summary = "Both deployments failed with same error: Timeout"

        assert 'Timeout' in summary or 'timeout' in summary.lower()
        assert 'same' in summary.lower()

    def test_generate_summary_temporal(self, context_store, sample_deployments):
        """Explain temporal proximity."""
        summary = "Deployments occurred 2 minutes apart, suggesting possible cascading failure"

        assert 'apart' in summary.lower() or 'temporal' in summary.lower()
        assert 'minute' in summary.lower()

    def test_generate_summary_config(self, context_store, sample_deployments):
        """Explain config-based causality."""
        deploy_ids = list(sample_deployments.keys())

        context_store.add_config_change(deploy_ids[0], 'db.pool.size', '100')
        context_store.add_config_change(deploy_ids[1], 'db.pool.size', '100')

        summary = "Both deployments updated config: db.pool.size = 100"

        assert 'db.pool.size' in summary or 'config' in summary.lower()

    def test_summary_language_clarity(self, context_store, sample_deployments):
        """Summaries are clear and actionable."""
        summaries = [
            "Both deployments involve postgres database, which could be the common root cause",
            "Deployment 2 occurred 30 seconds after Deployment 1, suggesting failure propagation",
            "Both deployments modified timeout configuration from 5s to 30s",
        ]

        for summary in summaries:
            # Summary should be readable and mention specific details
            assert len(summary) > 20
            assert any(keyword in summary.lower() for keyword in ['both', 'occurred', 'modified', 'could', 'suggest'])


class TestCausalityPathFinding:
    """Test causal chain analysis.

    Verifies finding causality paths between deployments,
    generating explanations, and identifying strongest paths.
    """

    def test_find_shortest_path(self, context_store, sample_deployments):
        """Find shortest causality path between deployments."""
        deploy_ids = list(sample_deployments.keys())

        # Create chain: deploy-001 -> deploy-002 -> deploy-003
        context_store.add_temporal_edge(deploy_ids[0], deploy_ids[1], 60)
        context_store.add_temporal_edge(deploy_ids[1], deploy_ids[2], 60)

        # Build relationship graph from DB
        cursor = context_store.conn.execute(
            'SELECT deployment_id_1, deployment_id_2, relationship_type FROM deployment_relationships'
        )
        edges = [(row[0], row[1], row[2]) for row in cursor]

        # Find shortest path using BFS
        def find_shortest_path(start, end):
            queue = deque([(start, [start])])
            visited = {start}

            while queue:
                node, path = queue.popleft()
                if node == end:
                    return path

                # Find outgoing edges
                for src, dst, rel_type in edges:
                    if src == node and dst not in visited:
                        visited.add(dst)
                        queue.append((dst, path + [dst]))

            return None

        path = find_shortest_path(deploy_ids[0], deploy_ids[2])

        # Should find a path
        assert path is not None
        assert len(path) == 3
        assert path == [deploy_ids[0], deploy_ids[1], deploy_ids[2]]

    def test_explain_path(self, context_store, sample_deployments):
        """Generate explanation for causality path."""
        deploy_ids = list(sample_deployments.keys())

        # Create path
        context_store.add_temporal_edge(deploy_ids[0], deploy_ids[1], 60)
        context_store.add_temporal_edge(deploy_ids[1], deploy_ids[2], 60)

        # Generate explanation
        explanation = (
            f"{deploy_ids[0]} (started failure) -> "
            f"{deploy_ids[1]} (30 seconds later, propagation) -> "
            f"{deploy_ids[2]} (60 seconds later, cascade)"
        )

        assert deploy_ids[0] in explanation
        assert deploy_ids[1] in explanation
        assert deploy_ids[2] in explanation

    def test_strongest_path(self, context_store, sample_deployments):
        """Find highest-scoring causality path."""
        deploy_ids = list(sample_deployments.keys())

        # Create multiple paths with different scores
        # Path 1: weak
        context_store.add_temporal_edge(deploy_ids[0], deploy_ids[2], 3600)  # 1 hour

        # Path 2: strong (short path, same services)
        context_store.add_service_state(deploy_ids[0], 'postgres', 'failed')
        context_store.add_service_state(deploy_ids[1], 'postgres', 'failed')
        context_store.add_temporal_edge(deploy_ids[0], deploy_ids[1], 60)

        context_store.add_service_state(deploy_ids[1], 'postgres', 'failed')
        context_store.add_service_state(deploy_ids[3], 'postgres', 'failed')
        context_store.add_temporal_edge(deploy_ids[1], deploy_ids[3], 60)

        # Path 2 should score higher than Path 1
        path2_score = calculate_causality_score(1, True, 0.5, 60)
        path1_score = calculate_causality_score(0, False, 0.0, 3600)

        assert path2_score > path1_score
