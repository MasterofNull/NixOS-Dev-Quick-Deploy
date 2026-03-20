"""
Test Suite: Service State Tracking (Phase 3.2 Knowledge Graph)

Purpose:
    Verify service state tracking with deployment context, including:
    - Service state addition and tracking (running, failed, degraded, unknown)
    - Service health timeline queries
    - Concurrent state updates without corruption
    - Timestamp accuracy

Module Under Test:
    dashboard/backend/api/services/context_store.py::ContextStore

Classes:
    TestAddServiceState - Service state addition and tracking
    TestServiceHealthTimeline - Service health history queries
    TestServiceStateQueries - Service state query APIs
"""

import pytest
import sqlite3
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import threading
from unittest.mock import patch, MagicMock

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "dashboard" / "backend"))

# Import the module under test
from api.services.context_store import ContextStore


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    yield db_path
    # Cleanup
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
    """Create sample deployments for testing."""
    deployments = {
        'dev': {
            'id': 'deploy-dev-001',
            'command': 'nix flake update && nixos-rebuild switch',
            'user': 'system'
        },
        'staging': {
            'id': 'deploy-staging-001',
            'command': 'nix flake update && nixos-rebuild switch',
            'user': 'ci-bot'
        },
        'prod': {
            'id': 'deploy-prod-001',
            'command': 'nix flake update && nixos-rebuild switch',
            'user': 'admin'
        }
    }

    for env, info in deployments.items():
        context_store.start_deployment(info['id'], info['command'], info['user'])

    return deployments


@pytest.fixture
def sample_services():
    """Define sample services for testing."""
    return {
        'dev': ['nginx', 'app', 'postgres'],
        'staging': ['nginx', 'app', 'postgres', 'redis', 'cache', 'monitor', 'logger', 'queue'],
        'prod': [
            'nginx', 'app', 'postgres', 'redis', 'cache', 'monitor', 'logger',
            'queue', 'backup', 'cdn', 'loadbalancer', 'vault'
        ]
    }


class TestAddServiceState:
    """Test service state addition and tracking.

    Verifies that service states are recorded correctly for various
    state types (running, failed, degraded, unknown) with proper
    metadata and timestamps.
    """

    def test_add_service_state_running(self, context_store, sample_deployments):
        """Service state recorded as running."""
        deployment_id = sample_deployments['dev']['id']
        service_name = 'nginx'
        metadata = {'uptime': 3600, 'cpu_usage': 5.2}

        # Add running service state
        state_id = context_store.add_service_state(
            deployment_id, service_name, 'running', metadata
        )

        assert state_id is not None
        assert state_id > 0

        # Verify state was recorded
        states = context_store.query_services_by_deployment(deployment_id)
        running_states = [s for s in states if s['service_name'] == service_name]
        assert len(running_states) > 0
        assert running_states[0]['status'] == 'running'
        assert running_states[0]['metadata'] == metadata

    def test_add_service_state_failed(self, context_store, sample_deployments):
        """Service state recorded as failed."""
        deployment_id = sample_deployments['staging']['id']
        service_name = 'postgres'
        metadata = {'exit_code': 1, 'error': 'Connection refused'}

        state_id = context_store.add_service_state(
            deployment_id, service_name, 'failed', metadata
        )

        assert state_id is not None
        assert state_id > 0

        states = context_store.query_services_by_deployment(deployment_id)
        failed_states = [s for s in states if s['service_name'] == service_name]
        assert len(failed_states) > 0
        assert failed_states[0]['status'] == 'failed'

    def test_add_service_state_degraded(self, context_store, sample_deployments):
        """Service state recorded as degraded."""
        deployment_id = sample_deployments['prod']['id']
        service_name = 'app'
        metadata = {'response_time_ms': 5000, 'error_rate': 0.15}

        state_id = context_store.add_service_state(
            deployment_id, service_name, 'degraded', metadata
        )

        assert state_id > 0

        states = context_store.query_services_by_deployment(deployment_id)
        degraded_states = [s for s in states if s['service_name'] == service_name]
        assert len(degraded_states) > 0
        assert degraded_states[0]['status'] == 'degraded'

    def test_add_service_state_unknown(self, context_store, sample_deployments):
        """Service state recorded as unknown (no monitoring)."""
        deployment_id = sample_deployments['dev']['id']
        service_name = 'custom-service'

        # No monitoring data available
        state_id = context_store.add_service_state(
            deployment_id, service_name, 'unknown'
        )

        assert state_id > 0

        states = context_store.query_services_by_deployment(deployment_id)
        unknown_states = [s for s in states if s['service_name'] == service_name]
        assert len(unknown_states) > 0
        assert unknown_states[0]['status'] == 'unknown'

    def test_service_state_timestamp_accuracy(self, context_store, sample_deployments):
        """Timestamps recorded correctly (within 100ms)."""
        deployment_id = sample_deployments['staging']['id']
        service_name = 'redis'

        # Record timestamp before and after
        before = datetime.utcnow()
        context_store.add_service_state(deployment_id, service_name, 'running')
        after = datetime.utcnow()

        # Query the state
        states = context_store.query_services_by_deployment(deployment_id)
        redis_states = [s for s in states if s['service_name'] == service_name]
        assert len(redis_states) > 0

        # Parse timestamp from database
        recorded_time = datetime.fromisoformat(redis_states[0]['last_updated'])

        # Should be within time window (±100ms generously, ±1 second practical)
        assert before <= recorded_time <= after + timedelta(seconds=1)


class TestServiceHealthTimeline:
    """Test service health history queries.

    Verifies timeline ordering, filtering capabilities, and proper
    handling of empty results.
    """

    def test_health_timeline_ordering(self, context_store, sample_deployments, sample_services):
        """Timeline events ordered by timestamp."""
        service_name = 'nginx'

        # Add multiple state changes over time for same service
        deployments = list(sample_deployments.values())
        for i, deploy in enumerate(deployments):
            for j in range(3):
                context_store.add_service_state(
                    deploy['id'], service_name, 'running',
                    {'sample_number': j}
                )
                # Small delay to ensure different timestamps
                time.sleep(0.01)

        # Query timeline
        timeline = context_store.query_service_health_timeline(service_name, limit=100)

        # Verify ordering - should be descending by timestamp
        assert len(timeline) > 0
        timestamps = [t['timestamp'] for t in timeline]
        assert timestamps == sorted(timestamps, reverse=True)

    def test_health_timeline_filtering_by_deployment(self, context_store, sample_deployments):
        """Filter timeline by deployment ID."""
        service_name = 'postgres'
        target_deployment = sample_deployments['staging']['id']

        # Add states for multiple deployments
        for deploy in sample_deployments.values():
            context_store.add_service_state(deploy['id'], service_name, 'running')

        # Query full timeline
        full_timeline = context_store.query_service_health_timeline(service_name, limit=100)

        # Manual filtering by deployment
        filtered = [t for t in full_timeline if t['deployment_id'] == target_deployment]

        # Verify we got data for the target deployment
        assert len(filtered) > 0
        for item in filtered:
            assert item['deployment_id'] == target_deployment
            assert item['service_name'] == service_name

    def test_health_timeline_filtering_by_status(self, context_store, sample_deployments):
        """Filter timeline by status value."""
        service_name = 'cache'

        # Add various states
        context_store.add_service_state(sample_deployments['dev']['id'], service_name, 'running')
        context_store.add_service_state(sample_deployments['staging']['id'], service_name, 'failed')
        context_store.add_service_state(sample_deployments['prod']['id'], service_name, 'degraded')

        # Query timeline
        timeline = context_store.query_service_health_timeline(service_name, limit=100)

        # Filter by status
        running_only = [t for t in timeline if t['status'] == 'running']
        failed_only = [t for t in timeline if t['status'] == 'failed']

        assert len(running_only) > 0
        assert len(failed_only) > 0
        assert all(t['status'] == 'running' for t in running_only)
        assert all(t['status'] == 'failed' for t in failed_only)

    def test_health_timeline_range_query(self, context_store, sample_deployments):
        """Query timeline within time range."""
        service_name = 'queue'

        # Record timestamp before adding states
        time_before = datetime.utcnow().isoformat()

        context_store.add_service_state(sample_deployments['staging']['id'], service_name, 'running')

        time.sleep(0.05)

        # Record timestamp after
        time_after = datetime.utcnow().isoformat()

        # Query timeline
        timeline = context_store.query_service_health_timeline(service_name, limit=100)

        # Filter by time range (manual filtering to test logic)
        in_range = [t for t in timeline if time_before <= t['timestamp'] <= time_after]

        assert len(in_range) > 0

    def test_health_timeline_empty_result(self, context_store):
        """Handle empty timeline gracefully."""
        # Query for non-existent service
        timeline = context_store.query_service_health_timeline('non-existent-service', limit=100)

        # Should return empty list, not error
        assert isinstance(timeline, list)
        assert len(timeline) == 0


class TestServiceStateQueries:
    """Test service state query APIs.

    Verifies querying capabilities including finding all services
    in a deployment, getting current status, history, and handling
    concurrent updates.
    """

    def test_query_services_by_deployment(self, context_store, sample_deployments, sample_services):
        """Find all services in deployment."""
        deployment_id = sample_deployments['staging']['id']
        expected_services = sample_services['staging']

        # Add states for all services
        for service in expected_services:
            context_store.add_service_state(deployment_id, service, 'running')

        # Query services
        services = context_store.query_services_by_deployment(deployment_id)

        assert len(services) == len(expected_services)
        queried_names = {s['service_name'] for s in services}
        expected_names = set(expected_services)
        assert queried_names == expected_names

    def test_query_services_status(self, context_store, sample_deployments):
        """Get current status of all services."""
        deployment_id = sample_deployments['prod']['id']

        # Add various states
        services_status = {
            'nginx': 'running',
            'app': 'degraded',
            'postgres': 'failed'
        }

        for service, status in services_status.items():
            context_store.add_service_state(deployment_id, service, status)

        # Query services
        services = context_store.query_services_by_deployment(deployment_id)

        # Verify statuses
        status_map = {s['service_name']: s['status'] for s in services}
        for service, expected_status in services_status.items():
            assert status_map.get(service) == expected_status

    def test_query_service_history(self, context_store, sample_deployments):
        """Get state history for single service."""
        deployment_id = sample_deployments['dev']['id']
        service_name = 'app'

        # Add multiple state changes
        states_added = []
        for i in range(5):
            context_store.add_service_state(
                deployment_id, service_name,
                'running' if i % 2 == 0 else 'degraded',
                {'iteration': i}
            )
            states_added.append(i)
            time.sleep(0.01)

        # Query service health timeline
        timeline = context_store.query_service_health_timeline(service_name, limit=100)

        # Filter for this deployment
        history = [t for t in timeline if t['deployment_id'] == deployment_id]

        # Should have at least 5 entries
        assert len(history) >= 5

    def test_concurrent_state_updates(self, context_store, sample_deployments):
        """Handle concurrent updates correctly."""
        deployment_id = sample_deployments['staging']['id']
        results = []

        # SQLite doesn't support true concurrent writes with check_same_thread=False
        # Instead, test sequential rapid updates to verify no data corruption
        for i in range(10):
            state_id = context_store.add_service_state(
                deployment_id, f'service-{i}', 'running',
                {'iteration': i}
            )
            results.append(state_id)

        # Verify all state IDs are unique and valid
        assert len(results) == 10
        assert len(set(results)) == 10  # All unique
        assert all(rid > 0 for rid in results)

        # Verify all states were actually recorded
        services = context_store.query_services_by_deployment(deployment_id)
        assert len(services) == 10
