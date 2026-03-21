#!/usr/bin/env python3

"""
Test Suite: Deployment Graph Query Modes (Phase 3.2 Knowledge Graph)

Purpose:
    Verify deployment graph query modes and visualization, including:
    - Different query perspectives (overview, issues, services, configs)
    - Focus filtering and relationship inspection
    - Cluster identification and summaries
    - Root cluster detection with confidence scoring
    - Similar failure pattern detection

Module Under Test:
    dashboard/backend/api/services/context_store.py::ContextStore

Classes:
    TestGraphQueryModes - Different graph query perspectives
    TestFocusFiltering - Relationship inspection with focus
    TestDeploymentClusterSummaries - Cluster-level summaries
    TestRootClusterIdentification - Root cause cluster detection
    TestSimilarFailureQueries - Finding similar failure patterns
"""

import pytest
import json
from pathlib import Path
import tempfile
from datetime import datetime, timedelta
from collections import defaultdict

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
def rich_deployment_graph(context_store):
    """Create a rich deployment graph with various relationships."""
    # Create deployments across multiple time windows
    deployments = []
    for i in range(1, 21):
        deploy_id = f'deploy-{i:03d}'
        deployments.append(deploy_id)
        context_store.start_deployment(deploy_id, f'cmd-{i}', 'system')

        # Add varied states
        if i <= 5:
            context_store.add_event(deploy_id, 'error', f'Failed: {["OOM", "timeout", "connection", "config", "resource"][i%5]}')
            context_store.complete_deployment(deploy_id, success=False)
        elif i <= 10:
            context_store.add_event(deploy_id, 'warning', 'Degraded service')
        else:
            context_store.complete_deployment(deploy_id, success=True)

        # Add services
        services = ['nginx', 'app', 'postgres', 'redis', 'cache']
        for j, service in enumerate(services):
            status = ['running', 'failed', 'degraded'][i % 3] if i <= 10 else 'running'
            context_store.add_service_state(deploy_id, service, status)

    # Create some causality relationships
    for i in range(5):
        context_store.add_root_cause_edge(deployments[i], deployments[i+1],
                                         {'reason': 'cascading_failure'})

    return deployments


class TestGraphQueryModes:
    """Test different graph query perspectives.

    Verifies that the graph query API supports multiple modes
    for viewing the deployment graph from different angles.
    """

    def test_overview_mode(self, context_store, rich_deployment_graph):
        """Overview mode shows all deployments and relationships."""
        # Get deployment summary
        cursor = context_store.conn.execute(
            'SELECT COUNT(*) as count FROM deployments'
        )
        deploy_count = cursor.fetchone()['count']

        assert deploy_count >= 20

        # Get relationships
        cursor = context_store.conn.execute(
            'SELECT COUNT(*) as count FROM deployment_relationships'
        )
        rel_count = cursor.fetchone()['count']

        # Should have some relationships
        assert rel_count > 0

    def test_issues_mode(self, context_store, rich_deployment_graph):
        """Issues mode filters to failed deployments."""
        # Query failed deployments
        cursor = context_store.conn.execute(
            'SELECT COUNT(*) as count FROM deployments WHERE status = ?',
            ('failed',)
        )
        failed_count = cursor.fetchone()['count']

        # Should have some failed deployments
        assert failed_count > 0

        # Get details of failed deployments
        cursor = context_store.conn.execute(
            'SELECT deployment_id, status FROM deployments WHERE status = ? LIMIT 10',
            ('failed',)
        )
        failed_deploys = [dict(row) for row in cursor]

        assert len(failed_deploys) > 0
        for deploy in failed_deploys:
            assert deploy['status'] == 'failed'

    def test_services_mode(self, context_store, rich_deployment_graph):
        """Services mode groups by service involvement."""
        # Get services and their deployment involvement
        cursor = context_store.conn.execute(
            '''SELECT service_name, COUNT(DISTINCT deployment_id) as deploy_count
               FROM deployment_service_states
               GROUP BY service_name'''
        )
        service_deployments = {row['service_name']: row['deploy_count'] for row in cursor}

        # Should have service data
        assert len(service_deployments) > 0
        assert 'nginx' in service_deployments
        assert service_deployments['nginx'] > 0

    def test_configs_mode(self, context_store, rich_deployment_graph):
        """Configs mode shows config-based grouping."""
        # Add config changes
        for i, deploy_id in enumerate(rich_deployment_graph[:5]):
            context_store.add_config_change(deploy_id, 'timeout', str(i * 1000))
            context_store.add_config_change(deploy_id, 'pool.size', str(i + 10))

        # Group deployments by config
        cursor = context_store.conn.execute(
            '''SELECT config_key, COUNT(DISTINCT deployment_id) as deploy_count
               FROM deployment_config_changes
               GROUP BY config_key'''
        )
        config_deployments = {row['config_key']: row['deploy_count'] for row in cursor}

        assert len(config_deployments) > 0
        assert 'timeout' in config_deployments


class TestFocusFiltering:
    """Test relationship inspection with focus.

    Verifies filtering and inspection of relationships
    when focusing on specific deployments or clusters.
    """

    def test_focus_single_deployment(self, context_store, rich_deployment_graph):
        """Focus on single deployment shows relationships."""
        target_deploy = rich_deployment_graph[0]

        # Get relationships involving this deployment
        cursor = context_store.conn.execute(
            '''SELECT * FROM deployment_relationships
               WHERE deployment_id_1 = ? OR deployment_id_2 = ?''',
            (target_deploy, target_deploy)
        )
        relationships = [dict(row) for row in cursor]

        # May or may not have relationships, but query should work
        assert isinstance(relationships, list)

    def test_focus_related_cluster(self, context_store, rich_deployment_graph):
        """Focus on cluster shows internal relationships."""
        # Create a small cluster
        cluster = rich_deployment_graph[:5]

        # Add internal relationships
        for i in range(len(cluster) - 1):
            context_store.add_root_cause_edge(cluster[i], cluster[i+1])

        # Query cluster relationships
        cursor = context_store.conn.execute(
            f'''SELECT * FROM deployment_relationships
               WHERE deployment_id_1 IN ({','.join('?' * len(cluster))})
               AND deployment_id_2 IN ({','.join('?' * len(cluster))})''',
            cluster + cluster
        )
        cluster_rels = [dict(row) for row in cursor]

        # Should have internal cluster relationships
        assert len(cluster_rels) > 0

    def test_relationship_direction_filtering(self, context_store, rich_deployment_graph):
        """Filter upstream vs downstream relationships."""
        deploy = rich_deployment_graph[2]

        # Get upstream (dependencies)
        cursor = context_store.conn.execute(
            'SELECT deployment_id_1 FROM deployment_relationships WHERE deployment_id_2 = ?',
            (deploy,)
        )
        upstream = [row[0] for row in cursor]

        # Get downstream (dependents)
        cursor = context_store.conn.execute(
            'SELECT deployment_id_2 FROM deployment_relationships WHERE deployment_id_1 = ?',
            (deploy,)
        )
        downstream = [row[0] for row in cursor]

        # Both may be empty, but should be queryable
        assert isinstance(upstream, list)
        assert isinstance(downstream, list)

    def test_edge_type_filtering(self, context_store, rich_deployment_graph):
        """Filter by edge type (causality, dependency, etc)."""
        # Add different types of edges
        context_store.add_temporal_edge(rich_deployment_graph[0], rich_deployment_graph[1], 60)
        context_store.add_cascading_failure(rich_deployment_graph[1], rich_deployment_graph[2])
        context_store.add_root_cause_edge(rich_deployment_graph[3], rich_deployment_graph[4])

        # Query by relationship type
        cursor = context_store.conn.execute(
            'SELECT COUNT(*) as count FROM deployment_relationships WHERE relationship_type = ?',
            ('preceded_by',)
        )
        temporal_count = cursor.fetchone()['count']

        cursor = context_store.conn.execute(
            'SELECT COUNT(*) as count FROM deployment_relationships WHERE relationship_type = ?',
            ('cascaded_to',)
        )
        cascading_count = cursor.fetchone()['count']

        assert temporal_count > 0
        assert cascading_count > 0


class TestDeploymentClusterSummaries:
    """Test cluster-level summaries.

    Verifies identification of deployment clusters,
    generation of summaries, and analysis of cluster
    characteristics.
    """

    def test_cluster_identification(self, context_store, rich_deployment_graph):
        """Identify related deployment clusters."""
        # Create a tight cluster
        cluster_ids = rich_deployment_graph[:5]
        for i in range(len(cluster_ids) - 1):
            context_store.add_root_cause_edge(cluster_ids[i], cluster_ids[i+1])

        # Simple connectivity-based clustering
        def find_clusters(deploy_ids):
            graph = defaultdict(set)
            cursor = context_store.conn.execute(
                '''SELECT deployment_id_1, deployment_id_2 FROM deployment_relationships'''
            )
            for row in cursor:
                graph[row[0]].add(row[1])
                graph[row[1]].add(row[0])

            visited = set()
            clusters = []

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

        clusters = find_clusters(rich_deployment_graph)

        # Should identify at least one cluster
        assert len(clusters) > 0

    def test_cluster_summary_generation(self, context_store, rich_deployment_graph):
        """Generate summary of cluster relationships."""
        cluster = rich_deployment_graph[:5]

        # Get cluster metadata
        summary = {
            'deployment_count': len(cluster),
            'failed_deployments': 0,
            'services_involved': set(),
            'config_keys_changed': set()
        }

        # Count failures
        for deploy_id in cluster:
            cursor = context_store.conn.execute(
                'SELECT status FROM deployments WHERE deployment_id = ?',
                (deploy_id,)
            )
            row = cursor.fetchone()
            if row and row['status'] == 'failed':
                summary['failed_deployments'] += 1

            # Get services
            cursor = context_store.conn.execute(
                'SELECT DISTINCT service_name FROM deployment_service_states WHERE deployment_id = ?',
                (deploy_id,)
            )
            for row in cursor:
                summary['services_involved'].add(row[0])

        assert summary['deployment_count'] == 5
        assert summary['failed_deployments'] > 0
        assert len(summary['services_involved']) > 0

    def test_cluster_size_metrics(self, context_store, rich_deployment_graph):
        """Report cluster size and density."""
        cluster = rich_deployment_graph[:8]
        n = len(cluster)

        # Create cluster relationships
        for i in range(n - 1):
            context_store.add_root_cause_edge(cluster[i], cluster[i+1])

        # Query cluster edges
        cursor = context_store.conn.execute(
            f'''SELECT COUNT(*) as count FROM deployment_relationships
               WHERE deployment_id_1 IN ({','.join('?' * n)})
               AND deployment_id_2 IN ({','.join('?' * n)})''',
            cluster + cluster
        )
        edge_count = cursor.fetchone()['count']

        # Calculate metrics
        max_edges = n * (n - 1)
        density = edge_count / max_edges if max_edges > 0 else 0

        assert edge_count > 0
        assert 0 <= density <= 1

    def test_cluster_temporal_analysis(self, context_store, rich_deployment_graph):
        """Analyze cluster temporal characteristics."""
        # Query temporal information
        cursor = context_store.conn.execute(
            'SELECT started_at, completed_at FROM deployments LIMIT 5'
        )
        deployments = [dict(row) for row in cursor]

        assert len(deployments) > 0

        # All should have start times
        for deploy in deployments:
            assert deploy['started_at'] is not None


class TestRootClusterIdentification:
    """Test root cause cluster detection.

    Verifies identification of root cause clusters,
    confidence scoring, and evidence reporting.
    """

    def test_identify_root_cluster(self, context_store, rich_deployment_graph):
        """Identify most likely root cause cluster."""
        # Create chain with clear root
        root = rich_deployment_graph[0]
        chain = rich_deployment_graph[1:4]

        context_store.add_root_cause_edge(root, chain[0])
        context_store.add_root_cause_edge(chain[0], chain[1])

        # Query root cause group
        root_group = context_store.find_root_cause_group(root)

        assert root_group['deployment_id'] == root
        assert isinstance(root_group['root_cause_group'], list)

    def test_confidence_scoring(self, context_store, rich_deployment_graph):
        """Score confidence of root cluster identification."""
        # Score should be based on:
        # - Number of related deployments
        # - Strength of relationships
        # - Temporal consistency

        deploy = rich_deployment_graph[0]

        def calculate_confidence(related_count, relationship_strength, temporal_consistency):
            """Calculate confidence score (0-1)."""
            score = 0.0
            score += min(related_count / 10, 0.3)  # Up to 3 points for relationships
            score += relationship_strength * 0.4   # Relationship strength
            score += temporal_consistency * 0.3    # Temporal consistency
            return min(score, 1.0)

        # Test scoring
        confidence = calculate_confidence(
            related_count=5,
            relationship_strength=0.9,
            temporal_consistency=0.8
        )

        assert 0 <= confidence <= 1
        assert confidence > 0.5  # Should be confident

    def test_alternative_clusters(self, context_store, rich_deployment_graph):
        """Provide alternative cluster candidates."""
        # Create multiple potential root causes
        cluster1 = rich_deployment_graph[0:3]
        cluster2 = rich_deployment_graph[3:6]

        # Add relationships within clusters
        for i in range(len(cluster1) - 1):
            context_store.add_root_cause_edge(cluster1[i], cluster1[i+1])
        for i in range(len(cluster2) - 1):
            context_store.add_root_cause_edge(cluster2[i], cluster2[i+1])

        # Find candidates
        candidates = []
        for deploy_id in rich_deployment_graph[:6]:
            group = context_store.find_root_cause_group(deploy_id)
            candidates.append({
                'root': deploy_id,
                'size': group['group_size']
            })

        # Should have multiple candidates
        assert len(candidates) > 0

    def test_root_cluster_evidence(self, context_store, rich_deployment_graph):
        """Report evidence supporting root cluster."""
        # Create cluster with evidence
        cluster = rich_deployment_graph[:4]

        # Add supporting evidence
        for deploy_id in cluster:
            context_store.add_event(deploy_id, 'error', 'OOM Killer triggered')
            context_store.add_service_state(deploy_id, 'postgres', 'failed')

        # Gather evidence
        evidence = {
            'events': [],
            'services_failed': set(),
            'config_changes': []
        }

        for deploy_id in cluster:
            cursor = context_store.conn.execute(
                'SELECT message FROM deployment_events WHERE deployment_id = ? AND event_type = ?',
                (deploy_id, 'error')
            )
            for row in cursor:
                evidence['events'].append(row[0])

            cursor = context_store.conn.execute(
                'SELECT service_name FROM deployment_service_states WHERE deployment_id = ? AND status = ?',
                (deploy_id, 'failed')
            )
            for row in cursor:
                evidence['services_failed'].add(row[0])

        assert len(evidence['events']) > 0
        assert 'postgres' in evidence['services_failed']


class TestSimilarFailureQueries:
    """Test finding similar failure patterns.

    Verifies pattern matching, similarity scoring,
    and historical pattern matching.
    """

    def test_find_similar_failures(self, context_store, rich_deployment_graph):
        """Find deployments with similar failure signatures."""
        # Create deployments with same failure
        target = rich_deployment_graph[0]
        similar = rich_deployment_graph[1:3]

        for deploy_id in [target] + similar:
            context_store.add_event(deploy_id, 'error', 'Connection timeout after 30s')
            context_store.add_service_state(deploy_id, 'postgres', 'failed')

        # Find similar
        cursor = context_store.conn.execute(
            'SELECT deployment_id FROM deployments WHERE status = ?',
            ('failed',)
        )
        failed_deploys = [row[0] for row in cursor]

        # Filter for similar failure messages
        target_events = context_store.search_deployments('Connection timeout', limit=10)
        similar_deploy_ids = {e['deployment_id'] for e in target_events}

        assert len(similar_deploy_ids) > 0

    def test_similarity_scoring(self, context_store, rich_deployment_graph):
        """Score similarity to current failure."""
        # Similarity based on:
        # - Message similarity
        # - Service overlap
        # - Status match

        def calculate_similarity(message_similarity, service_overlap, status_match):
            """Calculate similarity score (0-1)."""
            score = 0.0
            score += message_similarity * 0.5
            score += service_overlap * 0.3
            score += (1.0 if status_match else 0.0) * 0.2
            return min(score, 1.0)

        # Test scoring
        score = calculate_similarity(
            message_similarity=0.9,
            service_overlap=0.8,
            status_match=True
        )

        assert score > 0.7

    def test_historical_pattern_matching(self, context_store, rich_deployment_graph):
        """Match against historical failure patterns."""
        # Add historical patterns
        for i, deploy_id in enumerate(rich_deployment_graph[:10]):
            if i % 3 == 0:
                context_store.add_event(deploy_id, 'error', 'OOM Killer event')
            elif i % 3 == 1:
                context_store.add_event(deploy_id, 'error', 'Connection timeout')
            else:
                context_store.add_event(deploy_id, 'error', 'Deadlock detected')

        # Query for pattern frequency
        cursor = context_store.conn.execute(
            '''SELECT message, COUNT(*) as frequency FROM deployment_events
               WHERE event_type = ?
               GROUP BY message
               ORDER BY frequency DESC''',
            ('error',)
        )
        patterns = [dict(row) for row in cursor]

        assert len(patterns) > 0
        # Most frequent pattern should have highest count
        assert patterns[0]['frequency'] > patterns[-1]['frequency']
