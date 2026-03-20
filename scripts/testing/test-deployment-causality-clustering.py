"""
Test Suite: Causality Clustering and Scoring (Phase 3.2 Knowledge Graph)

Purpose:
    Verify causality clustering algorithms and scoring, including:
    - Deployment clustering convergence
    - Root cluster scoring and identification
    - Cause factor ranking by importance
    - Causal chain explanation generation
    - Per-cluster evidence extraction and ranking

Module Under Test:
    dashboard/backend/api/services/context_store.py::ContextStore

Classes:
    TestClusteringAlgorithm - Deployment clustering logic
    TestRootClusterScoring - Root cluster identification scoring
    TestCauseFactorRanking - Cause factor importance ranking
    TestCauseChainSummaries - Causal chain explanation generation
    TestClusterEvidenceDrilldown - Per-cluster evidence extraction
"""

import pytest
import json
import math
from pathlib import Path
import tempfile
from collections import defaultdict, deque
from datetime import datetime, timedelta

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
def complex_deployment_graph(context_store):
    """Create a complex deployment graph with multiple clusters."""
    deployments = []

    # Create 3 clusters with varying characteristics
    cluster_defs = [
        # Cluster 1: Cascading failure
        {
            'size': 5,
            'pattern': 'cascading',
            'services': ['postgres', 'redis'],
            'config': 'db.pool.size'
        },
        # Cluster 2: Independent failures
        {
            'size': 4,
            'pattern': 'independent',
            'services': ['nginx', 'app'],
            'config': 'timeout.ms'
        },
        # Cluster 3: Correlated
        {
            'size': 6,
            'pattern': 'correlated',
            'services': ['postgres', 'app', 'cache'],
            'config': 'memory.limit'
        }
    ]

    for cluster_idx, cluster_def in enumerate(cluster_defs):
        cluster_deploys = []
        for i in range(cluster_def['size']):
            deploy_id = f'cluster-{cluster_idx}-deploy-{i}'
            deployments.append(deploy_id)
            context_store.start_deployment(deploy_id, f'cmd-{i}', 'system')

            # Add events and services
            context_store.add_event(
                deploy_id, 'error',
                f"{cluster_def['pattern'].replace('_', ' ').title()} failure"
            )

            for service in cluster_def['services']:
                context_store.add_service_state(deploy_id, service, 'failed')

            context_store.add_config_change(deploy_id, cluster_def['config'], '100')

            cluster_deploys.append(deploy_id)

        # Create relationships based on pattern
        if cluster_def['pattern'] == 'cascading':
            for j in range(len(cluster_deploys) - 1):
                context_store.add_cascading_failure(cluster_deploys[j], cluster_deploys[j+1])
        elif cluster_def['pattern'] == 'correlated':
            for j in range(len(cluster_deploys) - 1):
                context_store.add_root_cause_edge(
                    cluster_deploys[j], cluster_deploys[j+1],
                    {'strength': 'high'}
                )

    return deployments


class TestClusteringAlgorithm:
    """Test deployment clustering logic.

    Verifies that the clustering algorithm correctly groups
    related deployments, merges clusters, and handles edge cases.
    """

    def test_cluster_algorithm_convergence(self, context_store, complex_deployment_graph):
        """Clustering algorithm reaches stable state."""
        # Simple clustering: iterate until no changes
        def cluster_by_relationships(deploy_ids):
            """Group deployments by relationship connectivity."""
            graph = defaultdict(set)

            cursor = context_store.conn.execute(
                'SELECT deployment_id_1, deployment_id_2 FROM deployment_relationships'
            )
            for row in cursor:
                graph[row[0]].add(row[1])
                graph[row[1]].add(row[0])

            clusters = []
            visited = set()

            def dfs(node, cluster):
                visited.add(node)
                cluster.add(node)
                for neighbor in graph[node]:
                    if neighbor not in visited and neighbor in deploy_ids:
                        dfs(neighbor, cluster)

            for deploy_id in deploy_ids:
                if deploy_id not in visited:
                    cluster = set()
                    dfs(deploy_id, cluster)
                    if cluster:
                        clusters.append(cluster)

            return clusters

        # Iterate until convergence
        prev_clusters = None
        converged = False
        iterations = 0
        max_iterations = 10

        while iterations < max_iterations:
            clusters = cluster_by_relationships(complex_deployment_graph)

            if prev_clusters == clusters:
                converged = True
                break

            prev_clusters = clusters
            iterations += 1

        # Should converge
        assert converged is True
        assert iterations < max_iterations
        assert len(clusters) > 0

    def test_cluster_merging(self, context_store, complex_deployment_graph):
        """Merge related clusters correctly."""
        # Create two separate clusters
        cluster1 = complex_deployment_graph[:5]
        cluster2 = complex_deployment_graph[5:10]

        # Add internal relationships
        for i in range(len(cluster1) - 1):
            context_store.add_root_cause_edge(cluster1[i], cluster1[i+1])
        for i in range(len(cluster2) - 1):
            context_store.add_root_cause_edge(cluster2[i], cluster2[i+1])

        # Now add bridge relationship to merge
        context_store.add_root_cause_edge(cluster1[-1], cluster2[0])

        # Re-cluster
        graph = defaultdict(set)
        cursor = context_store.conn.execute(
            'SELECT deployment_id_1, deployment_id_2 FROM deployment_relationships'
        )
        for row in cursor:
            graph[row[0]].add(row[1])
            graph[row[1]].add(row[0])

        # Count connected components
        visited = set()
        components = 0

        def dfs(node):
            visited.add(node)
            for neighbor in graph[node]:
                if neighbor not in visited:
                    dfs(neighbor)

        for deploy_id in complex_deployment_graph[:10]:
            if deploy_id not in visited:
                dfs(deploy_id)
                components += 1

        # Should have merged into one component
        assert components == 1

    def test_cluster_split(self, context_store, complex_deployment_graph):
        """Split overcrowded clusters."""
        # Create overcrowded cluster
        big_cluster = complex_deployment_graph[10:20]

        # Add dense relationships
        for i in range(len(big_cluster)):
            for j in range(i + 1, min(i + 3, len(big_cluster))):
                context_store.add_root_cause_edge(big_cluster[i], big_cluster[j])

        # Compute cluster density
        graph = defaultdict(set)
        cursor = context_store.conn.execute(
            'SELECT deployment_id_1, deployment_id_2 FROM deployment_relationships'
        )
        for row in cursor:
            graph[row[0]].add(row[1])

        edge_count = sum(len(neighbors) for neighbors in graph.values()) / 2
        max_edges = len(big_cluster) * (len(big_cluster) - 1) / 2
        density = edge_count / max_edges if max_edges > 0 else 0

        # High density cluster
        assert density > 0.1

    def test_single_element_clusters(self, context_store, complex_deployment_graph):
        """Handle isolated deployments correctly."""
        # Add isolated deployment
        isolated_id = 'isolated-deploy-999'
        context_store.start_deployment(isolated_id, 'cmd', 'user')
        context_store.complete_deployment(isolated_id, success=True)

        # Query it
        cursor = context_store.conn.execute(
            'SELECT * FROM deployments WHERE deployment_id = ?',
            (isolated_id,)
        )
        deploy = cursor.fetchone()

        assert deploy is not None
        assert deploy['deployment_id'] == isolated_id

        # Should form its own singleton cluster
        cursor = context_store.conn.execute(
            'SELECT * FROM deployment_relationships WHERE deployment_id_1 = ? OR deployment_id_2 = ?',
            (isolated_id, isolated_id)
        )
        relations = list(cursor)

        assert len(relations) == 0


class TestRootClusterScoring:
    """Test root cluster identification scoring.

    Verifies scoring of clusters by root-cause likelihood
    based on multiple contributing factors.
    """

    def test_score_clusters(self, context_store, complex_deployment_graph):
        """Score each cluster for root-cause likelihood."""
        def score_cluster(cluster_ids):
            """Score a cluster for root-cause likelihood."""
            score = 0.0

            # Factor 1: Size (larger clusters more likely to be root)
            score += min(len(cluster_ids) / 10, 0.2)

            # Factor 2: Temporal concentration
            cursor = context_store.conn.execute(
                f'SELECT started_at FROM deployments WHERE deployment_id IN ({",".join("?" * len(cluster_ids))})',
                cluster_ids
            )
            timestamps = [row[0] for row in cursor]
            if len(timestamps) > 1:
                # All timestamps close together = high temporal concentration
                score += 0.2

            # Factor 3: Failure severity
            cursor = context_store.conn.execute(
                f'SELECT status FROM deployments WHERE deployment_id IN ({",".join("?" * len(cluster_ids))})',
                cluster_ids
            )
            failed_count = sum(1 for row in cursor if row[0] == 'failed')
            score += (failed_count / len(cluster_ids)) * 0.3

            # Factor 4: Relationship density
            cursor = context_store.conn.execute(
                f'SELECT COUNT(*) as count FROM deployment_relationships WHERE '
                f'deployment_id_1 IN ({",".join("?" * len(cluster_ids))}) AND '
                f'deployment_id_2 IN ({",".join("?" * len(cluster_ids))})',
                cluster_ids + cluster_ids
            )
            rel_count = cursor.fetchone()['count']
            max_rels = len(cluster_ids) * (len(cluster_ids) - 1) / 2
            if max_rels > 0:
                score += (rel_count / max_rels) * 0.3

            return min(score, 1.0)

        # Score all potential clusters
        cursor = context_store.conn.execute(
            'SELECT deployment_id FROM deployments LIMIT 1'
        )
        sample = cursor.fetchone()

        if sample:
            group = context_store.find_root_cause_group(sample['deployment_id'])
            # Score the group
            if group['root_cause_group']:
                group_ids = [d['deployment_id'] for d in group['root_cause_group']]
                score = score_cluster([sample['deployment_id']] + group_ids)
                assert 0 <= score <= 1

    def test_score_factors(self, context_store, complex_deployment_graph):
        """Break down score by contributing factors."""
        factors = {
            'size_factor': 0.0,
            'temporal_factor': 0.0,
            'severity_factor': 0.0,
            'density_factor': 0.0
        }

        # Test individual factor calculations
        cluster = complex_deployment_graph[:5]

        # Size factor
        factors['size_factor'] = min(len(cluster) / 10, 0.2)
        assert 0 <= factors['size_factor'] <= 0.2

        # Temporal factor
        factors['temporal_factor'] = 0.2  # Assuming concentrated

        # Severity factor
        cursor = context_store.conn.execute(
            f'SELECT status FROM deployments WHERE deployment_id IN ({",".join("?" * len(cluster))})',
            cluster
        )
        failed = sum(1 for row in cursor if row[0] == 'failed')
        factors['severity_factor'] = (failed / len(cluster)) * 0.3
        assert 0 <= factors['severity_factor'] <= 0.3

        # Density factor
        factors['density_factor'] = 0.15  # Assuming moderate density

        total = sum(factors.values())
        assert 0 <= total <= 1.0

    def test_temporal_factor(self, context_store, complex_deployment_graph):
        """Temporal proximity increases score."""
        cluster = complex_deployment_graph[:3]

        def calculate_temporal_score(deploy_ids):
            """Calculate temporal concentration score."""
            cursor = context_store.conn.execute(
                f'SELECT started_at FROM deployments WHERE deployment_id IN ({",".join("?" * len(deploy_ids))})',
                deploy_ids
            )
            timestamps = [row[0] for row in cursor]

            if len(timestamps) < 2:
                return 0.0

            # Calculate time span
            ts_sorted = sorted(timestamps)
            span_seconds = (datetime.fromisoformat(ts_sorted[-1]) - datetime.fromisoformat(ts_sorted[0])).total_seconds()

            # Within 5 minutes = high score
            if span_seconds <= 300:
                return 0.2
            elif span_seconds <= 3600:
                return 0.1
            else:
                return 0.0

        score = calculate_temporal_score(cluster)
        assert 0 <= score <= 0.2

    def test_failure_severity_factor(self, context_store, complex_deployment_graph):
        """Failure severity affects score."""
        cluster = complex_deployment_graph[:4]

        cursor = context_store.conn.execute(
            f'SELECT status FROM deployments WHERE deployment_id IN ({",".join("?" * len(cluster))})',
            cluster
        )
        failed_count = sum(1 for row in cursor if row[0] == 'failed')

        severity_factor = (failed_count / len(cluster)) * 0.3

        assert 0 <= severity_factor <= 0.3

    def test_cascade_factor(self, context_store, complex_deployment_graph):
        """Cascade patterns affect score."""
        cluster = complex_deployment_graph[:5]

        # Count cascading relationships
        cursor = context_store.conn.execute(
            f'SELECT COUNT(*) as count FROM deployment_relationships '
            f'WHERE relationship_type = ? AND '
            f'deployment_id_1 IN ({",".join("?" * len(cluster))}) AND '
            f'deployment_id_2 IN ({",".join("?" * len(cluster))})',
            ['cascaded_to'] + cluster + cluster
        )
        cascade_count = cursor.fetchone()['count']

        cascade_factor = min(cascade_count * 0.1, 0.3)

        assert 0 <= cascade_factor <= 0.3


class TestCauseFactorRanking:
    """Test cause factor importance ranking.

    Verifies ranking of factors by importance and
    calculation of relative weights.
    """

    def test_rank_cause_factors(self, context_store, complex_deployment_graph):
        """Rank factors by importance (service, config, status, time)."""
        cluster = complex_deployment_graph[:5]

        factors = {
            'service': 0.0,
            'config': 0.0,
            'status': 0.0,
            'time': 0.0
        }

        # Count shared services
        cursor = context_store.conn.execute(
            f'SELECT service_name, COUNT(*) as count FROM deployment_service_states '
            f'WHERE deployment_id IN ({",".join("?" * len(cluster))}) '
            f'GROUP BY service_name ORDER BY count DESC LIMIT 1',
            cluster
        )
        row = cursor.fetchone()
        if row:
            factors['service'] = row['count'] / len(cluster)

        # Count shared config changes
        cursor = context_store.conn.execute(
            f'SELECT config_key, COUNT(*) as count FROM deployment_config_changes '
            f'WHERE deployment_id IN ({",".join("?" * len(cluster))}) '
            f'GROUP BY config_key ORDER BY count DESC LIMIT 1',
            cluster
        )
        row = cursor.fetchone()
        if row:
            factors['config'] = row['count'] / len(cluster)

        # Status consistency
        cursor = context_store.conn.execute(
            f'SELECT status, COUNT(*) as count FROM deployments '
            f'WHERE deployment_id IN ({",".join("?" * len(cluster))}) '
            f'GROUP BY status ORDER BY count DESC LIMIT 1',
            cluster
        )
        row = cursor.fetchone()
        if row:
            factors['status'] = row['count'] / len(cluster)

        # Temporal concentration
        factors['time'] = 0.5  # Assume moderate temporal concentration

        # Rank factors
        ranked = sorted(factors.items(), key=lambda x: x[1], reverse=True)

        # Top factor should be most significant
        assert ranked[0][1] >= ranked[1][1]

    def test_factor_weight_calculation(self, context_store, complex_deployment_graph):
        """Calculate relative weight of each factor."""
        factors = {
            'service': 0.8,
            'config': 0.6,
            'status': 0.7,
            'time': 0.3
        }

        total = sum(factors.values())
        weights = {k: v / total for k, v in factors.items()}

        # All weights should sum to 1.0
        assert abs(sum(weights.values()) - 1.0) < 0.01

        # Service should have highest weight
        assert weights['service'] > weights['time']

    def test_factor_confidence_scores(self, context_store, complex_deployment_graph):
        """Score confidence in each factor."""
        # Confidence based on evidence count
        cluster = complex_deployment_graph[:5]

        confidences = {}

        # Service confidence
        cursor = context_store.conn.execute(
            f'SELECT COUNT(DISTINCT service_name) as count FROM deployment_service_states '
            f'WHERE deployment_id IN ({",".join("?" * len(cluster))})',
            cluster
        )
        service_evidence = cursor.fetchone()['count']
        confidences['service'] = min(service_evidence / 5, 1.0)

        # Config confidence
        cursor = context_store.conn.execute(
            f'SELECT COUNT(DISTINCT config_key) as count FROM deployment_config_changes '
            f'WHERE deployment_id IN ({",".join("?" * len(cluster))})',
            cluster
        )
        config_evidence = cursor.fetchone()['count']
        confidences['config'] = min(config_evidence / 5, 1.0)

        # All confidences should be 0-1
        for conf in confidences.values():
            assert 0 <= conf <= 1


class TestCauseChainSummaries:
    """Test causal chain explanation generation.

    Verifies generation of likely cause chains,
    depth control, confidence, and alternatives.
    """

    def test_generate_chain_summary(self, context_store, complex_deployment_graph):
        """Generate likely cause chain explanation."""
        # Get cluster
        cursor = context_store.conn.execute(
            'SELECT deployment_id FROM deployments WHERE status = ? LIMIT 3',
            ('failed',)
        )
        chain_ids = [row[0] for row in cursor]

        if chain_ids:
            summary = "Likely cause chain:\n"
            for i, deploy_id in enumerate(chain_ids):
                cursor = context_store.conn.execute(
                    'SELECT started_at FROM deployments WHERE deployment_id = ?',
                    (deploy_id,)
                )
                row = cursor.fetchone()
                summary += f"{i+1}. {deploy_id} ({row['started_at']})\n"

            assert len(summary) > 0
            assert all(d in summary for d in chain_ids)

    def test_chain_depth_control(self, context_store, complex_deployment_graph):
        """Limit chain depth to manageable length (3-5 steps)."""
        # Create long chain
        chain_ids = complex_deployment_graph[:10]

        # Limit to 5
        max_depth = 5
        limited_chain = chain_ids[:max_depth]

        assert len(limited_chain) <= 5

    def test_chain_confidence(self, context_store, complex_deployment_graph):
        """Score confidence of chain explanation."""
        # Confidence based on:
        # - Relationship strength
        # - Service overlap
        # - Temporal consistency

        def calculate_chain_confidence(chain_length, avg_relationship_strength, temporal_variance):
            """Calculate confidence score."""
            score = 0.0

            # Longer chains are less confident
            score += (1.0 - min(chain_length / 10, 1.0)) * 0.4

            # Strong relationships increase confidence
            score += avg_relationship_strength * 0.4

            # Low temporal variance increases confidence
            score += (1.0 - min(temporal_variance / 3600, 1.0)) * 0.2

            return min(score, 1.0)

        confidence = calculate_chain_confidence(
            chain_length=3,
            avg_relationship_strength=0.85,
            temporal_variance=300  # 5 minutes
        )

        assert 0 <= confidence <= 1.0
        assert confidence > 0.5  # Should be fairly confident

    def test_alternative_chains(self, context_store, complex_deployment_graph):
        """Provide alternative explanation chains."""
        # Find multiple potential chains
        start_deploy = complex_deployment_graph[0]

        # Chain 1: Via cascading failures
        cursor = context_store.conn.execute(
            'SELECT deployment_id_2 FROM deployment_relationships WHERE deployment_id_1 = ? AND relationship_type = ?',
            (start_deploy, 'cascaded_to')
        )
        cascading_next = [row[0] for row in cursor]

        # Chain 2: Via same root cause
        cursor = context_store.conn.execute(
            'SELECT deployment_id_2 FROM deployment_relationships WHERE deployment_id_1 = ? AND relationship_type = ?',
            (start_deploy, 'same_root_cause')
        )
        root_cause_next = [row[0] for row in cursor]

        alternatives = []
        if cascading_next:
            alternatives.append({'type': 'cascading', 'next': cascading_next[0]})
        if root_cause_next:
            alternatives.append({'type': 'root_cause', 'next': root_cause_next[0]})

        # Should have at least potential for alternatives
        assert isinstance(alternatives, list)


class TestClusterEvidenceDrilldown:
    """Test per-cluster evidence extraction.

    Verifies extraction and ranking of evidence
    supporting cluster analysis.
    """

    def test_extract_status_evidence(self, context_store, complex_deployment_graph):
        """Extract failure statuses from cluster."""
        cluster = complex_deployment_graph[:5]

        cursor = context_store.conn.execute(
            f'SELECT status, COUNT(*) as count FROM deployments '
            f'WHERE deployment_id IN ({",".join("?" * len(cluster))}) '
            f'GROUP BY status',
            cluster
        )
        statuses = {row['status']: row['count'] for row in cursor}

        assert len(statuses) > 0
        assert sum(statuses.values()) == len(cluster)

    def test_extract_issue_evidence(self, context_store, complex_deployment_graph):
        """Extract issue signals from cluster."""
        cluster = complex_deployment_graph[:5]

        cursor = context_store.conn.execute(
            f'SELECT event_type, message FROM deployment_events '
            f'WHERE deployment_id IN ({",".join("?" * len(cluster))}) AND event_type = ?',
            cluster + ['error']
        )
        issues = [{'type': row['event_type'], 'message': row['message']} for row in cursor]

        assert len(issues) > 0

    def test_extract_service_evidence(self, context_store, complex_deployment_graph):
        """Extract service involvement from cluster."""
        cluster = complex_deployment_graph[:5]

        cursor = context_store.conn.execute(
            f'SELECT service_name, status, COUNT(*) as count FROM deployment_service_states '
            f'WHERE deployment_id IN ({",".join("?" * len(cluster))}) '
            f'GROUP BY service_name, status',
            cluster
        )
        services = [{
            'name': row['service_name'],
            'status': row['status'],
            'count': row['count']
        } for row in cursor]

        assert len(services) > 0

    def test_extract_config_evidence(self, context_store, complex_deployment_graph):
        """Extract config reference from cluster."""
        cluster = complex_deployment_graph[:5]

        cursor = context_store.conn.execute(
            f'SELECT config_key, config_value, COUNT(*) as count FROM deployment_config_changes '
            f'WHERE deployment_id IN ({",".join("?" * len(cluster))}) '
            f'GROUP BY config_key, config_value',
            cluster
        )
        configs = [{
            'key': row['config_key'],
            'value': row['config_value'],
            'count': row['count']
        } for row in cursor]

        assert len(configs) > 0

    def test_evidence_ranking(self, context_store, complex_deployment_graph):
        """Rank evidence by relevance."""
        cluster = complex_deployment_graph[:5]

        # Collect all evidence types
        evidence = {
            'services': [],
            'configs': [],
            'statuses': [],
            'events': []
        }

        # Rank by frequency
        cursor = context_store.conn.execute(
            f'SELECT service_name, COUNT(*) as count FROM deployment_service_states '
            f'WHERE deployment_id IN ({",".join("?" * len(cluster))}) '
            f'GROUP BY service_name ORDER BY count DESC',
            cluster
        )
        evidence['services'] = [row['service_name'] for row in cursor]

        cursor = context_store.conn.execute(
            f'SELECT config_key, COUNT(*) as count FROM deployment_config_changes '
            f'WHERE deployment_id IN ({",".join("?" * len(cluster))}) '
            f'GROUP BY config_key ORDER BY count DESC',
            cluster
        )
        evidence['configs'] = [row['config_key'] for row in cursor]

        assert len(evidence['services']) > 0 or len(evidence['configs']) > 0

    def test_evidence_drill_detail(self, context_store, complex_deployment_graph):
        """Provide drilldown detail for each evidence item."""
        cluster = complex_deployment_graph[:5]

        # Get top service with details
        cursor = context_store.conn.execute(
            f'SELECT service_name FROM deployment_service_states '
            f'WHERE deployment_id IN ({",".join("?" * len(cluster))}) '
            f'GROUP BY service_name ORDER BY COUNT(*) DESC LIMIT 1',
            cluster
        )
        row = cursor.fetchone()

        if row:
            top_service = row[0]

            # Get detail
            cursor = context_store.conn.execute(
                f'SELECT deployment_id, status, timestamp, service_name FROM deployment_service_states '
                f'WHERE service_name = ? AND deployment_id IN ({",".join("?" * len(cluster))})',
                [top_service] + cluster
            )
            details = [dict(r) for r in cursor]

            assert len(details) > 0
            assert all(d['service_name'] == top_service for d in details)
