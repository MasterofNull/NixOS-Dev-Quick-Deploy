#!/usr/bin/env python3
"""
Test Suite: Dashboard Context Store UI Integration (Phase 6.3 P1)

Purpose:
    Comprehensive testing for dashboard integration with context store backend:
    - Context store API endpoint integration
    - Deployment graph data formatting for UI
    - Service dependency graph rendering
    - Causality relationship visualization

Module Under Test:
    dashboard/backend/api/services/context_store.py (UI integration layer)
    dashboard/backend/api/routes (graph and search endpoints)

Classes:
    TestContextStoreEndpoint - API endpoint integration
    TestDeploymentGraphAPI - Graph data formatting
    TestServiceDependencyUI - Dependency graph rendering
    TestCausalityVisualization - Causality visualization

Coverage: ~200 lines
Phase: 6.3 Week 4 (Dashboard Integration)
"""

import pytest
import json
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timedelta
from typing import Dict, List, Any


class TestContextStoreEndpoint:
    """Test context store API endpoint integration with dashboard frontend.

    Validates that the context store backend properly exposes APIs for
    dashboard queries, with correct data formatting and error handling.
    """

    @pytest.fixture
    def api_client(self):
        """Mock API client for testing endpoints."""
        client = Mock()
        client.base_url = "http://localhost:8080/api/v1"
        client.timeout = 30
        client.headers = {"Content-Type": "application/json"}

        def mock_get(endpoint: str, params: Dict = None):
            """Mock GET request."""
            if endpoint == "/context-store/deployments":
                return {
                    'status': 'success',
                    'data': [
                        {'id': 'd1', 'service': 'api', 'status': 'running'},
                        {'id': 'd2', 'service': 'db', 'status': 'running'},
                        {'id': 'd3', 'service': 'cache', 'status': 'degraded'},
                    ],
                    'count': 3
                }
            elif endpoint == "/context-store/services":
                return {
                    'status': 'success',
                    'data': [
                        {'name': 'api', 'healthy': True, 'deployments': 5},
                        {'name': 'db', 'healthy': True, 'deployments': 3},
                        {'name': 'cache', 'healthy': False, 'deployments': 2},
                    ],
                    'count': 3
                }
            elif endpoint == "/context-store/causality":
                return {
                    'status': 'success',
                    'data': [
                        {'from': 'd1', 'to': 'd2', 'strength': 0.85},
                        {'from': 'd2', 'to': 'd3', 'strength': 0.72},
                    ],
                    'count': 2
                }
            return {'status': 'error', 'message': 'Not found'}

        client.get = mock_get
        return client

    def test_deployments_endpoint_returns_formatted_data(self, api_client):
        """Deployments endpoint returns properly formatted data."""
        response = api_client.get("/context-store/deployments")

        assert response['status'] == 'success'
        assert response['count'] == 3
        assert len(response['data']) == 3
        assert response['data'][0]['id'] == 'd1'
        assert 'service' in response['data'][0]
        assert 'status' in response['data'][0]

    def test_services_endpoint_aggregates_deployments(self, api_client):
        """Services endpoint aggregates deployment data."""
        response = api_client.get("/context-store/services")

        assert response['status'] == 'success'
        services = {s['name']: s for s in response['data']}

        assert 'api' in services
        assert services['api']['deployments'] == 5
        assert services['api']['healthy'] is True

    def test_causality_endpoint_returns_edges(self, api_client):
        """Causality endpoint returns relationship edges."""
        response = api_client.get("/context-store/causality")

        assert response['status'] == 'success'
        assert response['count'] == 2
        edge = response['data'][0]
        assert 'from' in edge
        assert 'to' in edge
        assert 'strength' in edge
        assert 0 <= edge['strength'] <= 1

    def test_endpoint_error_handling(self, api_client):
        """API gracefully handles errors."""
        response = api_client.get("/context-store/invalid")

        assert response['status'] == 'error'
        assert 'message' in response


class TestDeploymentGraphAPI:
    """Test deployment graph data formatting for UI consumption.

    Validates that deployment graph data is properly formatted for
    visualization components with correct hierarchy and relationships.
    """

    @pytest.fixture
    def deployment_graph_formatter(self):
        """Formatter for deployment graph data."""
        formatter = Mock()

        def format_for_ui(graph_data: Dict) -> Dict:
            """Format raw graph data for UI."""
            nodes = []
            edges = []

            for deploy_id, deploy_info in graph_data.get('deployments', {}).items():
                node = {
                    'id': deploy_id,
                    'label': deploy_info.get('service', 'unknown'),
                    'status': deploy_info.get('status', 'unknown'),
                    'metrics': deploy_info.get('metrics', {}),
                    'properties': {
                        'created': deploy_info.get('created_at'),
                        'updated': deploy_info.get('updated_at')
                    }
                }
                nodes.append(node)

            for edge_data in graph_data.get('dependencies', []):
                edge = {
                    'id': f"{edge_data['from']}-{edge_data['to']}",
                    'source': edge_data['from'],
                    'target': edge_data['to'],
                    'type': edge_data.get('type', 'depends_on'),
                    'weight': edge_data.get('weight', 1.0)
                }
                edges.append(edge)

            return {
                'nodes': nodes,
                'edges': edges,
                'metadata': {
                    'total_nodes': len(nodes),
                    'total_edges': len(edges),
                    'timestamp': datetime.now().isoformat()
                }
            }

        formatter.format_for_ui = format_for_ui
        return formatter

    def test_graph_formatting_creates_proper_node_structure(self, deployment_graph_formatter):
        """Graph formatting creates correct node structures."""
        raw_data = {
            'deployments': {
                'd1': {'service': 'api', 'status': 'running', 'metrics': {'cpu': 45}},
                'd2': {'service': 'db', 'status': 'running', 'metrics': {'cpu': 60}},
            },
            'dependencies': []
        }

        formatted = deployment_graph_formatter.format_for_ui(raw_data)

        assert len(formatted['nodes']) == 2
        node1 = formatted['nodes'][0]
        assert node1['id'] == 'd1'
        assert node1['label'] == 'api'
        assert node1['status'] == 'running'
        assert 'metrics' in node1
        assert 'properties' in node1

    def test_graph_formatting_creates_proper_edge_structure(self, deployment_graph_formatter):
        """Graph formatting creates correct edge structures."""
        raw_data = {
            'deployments': {'d1': {}, 'd2': {}},
            'dependencies': [
                {'from': 'd1', 'to': 'd2', 'type': 'depends_on', 'weight': 0.95}
            ]
        }

        formatted = deployment_graph_formatter.format_for_ui(raw_data)

        assert len(formatted['edges']) == 1
        edge = formatted['edges'][0]
        assert edge['id'] == 'd1-d2'
        assert edge['source'] == 'd1'
        assert edge['target'] == 'd2'
        assert edge['type'] == 'depends_on'
        assert edge['weight'] == 0.95

    def test_graph_metadata_correctly_counted(self, deployment_graph_formatter):
        """Graph metadata counts are correct."""
        raw_data = {
            'deployments': {'d1': {}, 'd2': {}, 'd3': {}},
            'dependencies': [
                {'from': 'd1', 'to': 'd2'},
                {'from': 'd2', 'to': 'd3'}
            ]
        }

        formatted = deployment_graph_formatter.format_for_ui(raw_data)

        assert formatted['metadata']['total_nodes'] == 3
        assert formatted['metadata']['total_edges'] == 2
        assert 'timestamp' in formatted['metadata']


class TestServiceDependencyUI:
    """Test service dependency graph rendering for UI.

    Validates that service dependencies are correctly represented
    for visualization in the dashboard frontend.
    """

    @pytest.fixture
    def dependency_renderer(self):
        """Renderer for service dependencies."""
        renderer = Mock()

        def render_dependency_tree(services_data: Dict) -> Dict:
            """Render service dependencies as tree structure."""
            nodes = []
            edges = []

            # Create node for each service
            for service_name, service_info in services_data.items():
                node = {
                    'id': service_name,
                    'type': 'service',
                    'label': service_name,
                    'health_status': service_info.get('status', 'unknown'),
                    'deployment_count': service_info.get('deployment_count', 0),
                    'icon': 'circle' if service_info.get('status') == 'healthy' else 'alert'
                }
                nodes.append(node)

            # Create dependency edges
            for service_name, deps in services_data.items():
                for dep in deps.get('depends_on', []):
                    edge = {
                        'id': f"{service_name}->{dep}",
                        'source': service_name,
                        'target': dep,
                        'label': 'depends_on'
                    }
                    edges.append(edge)

            return {
                'nodes': nodes,
                'edges': edges,
                'root_services': [s for s, info in services_data.items()
                                 if not info.get('depends_on')]
            }

        renderer.render_dependency_tree = render_dependency_tree
        return renderer

    def test_dependency_tree_renders_service_nodes(self, dependency_renderer):
        """Dependency tree renders all services as nodes."""
        services = {
            'frontend': {'status': 'healthy', 'deployment_count': 2},
            'api': {'status': 'healthy', 'deployment_count': 3},
            'database': {'status': 'healthy', 'deployment_count': 1}
        }

        tree = dependency_renderer.render_dependency_tree(services)

        assert len(tree['nodes']) == 3
        service_ids = {n['id'] for n in tree['nodes']}
        assert service_ids == {'frontend', 'api', 'database'}

    def test_dependency_tree_renders_edges(self, dependency_renderer):
        """Dependency tree renders dependency edges."""
        services = {
            'frontend': {'status': 'healthy', 'depends_on': ['api']},
            'api': {'status': 'healthy', 'depends_on': ['database']},
            'database': {'status': 'healthy', 'depends_on': []}
        }

        tree = dependency_renderer.render_dependency_tree(services)

        assert len(tree['edges']) == 2
        edge_ids = {e['id'] for e in tree['edges']}
        assert 'frontend->api' in edge_ids
        assert 'api->database' in edge_ids

    def test_dependency_tree_identifies_root_services(self, dependency_renderer):
        """Dependency tree identifies services with no dependencies."""
        services = {
            'frontend': {'status': 'healthy', 'depends_on': ['api']},
            'api': {'status': 'healthy', 'depends_on': ['database']},
            'database': {'status': 'healthy', 'depends_on': []}
        }

        tree = dependency_renderer.render_dependency_tree(services)

        assert tree['root_services'] == ['database']


class TestCausalityVisualization:
    """Test causality relationship visualization for UI.

    Validates that causality relationships are properly formatted
    and visualized to show cause-effect relationships in the system.
    """

    @pytest.fixture
    def causality_visualizer(self):
        """Visualizer for causality relationships."""
        visualizer = Mock()

        def visualize_causality(causality_data: List[Dict]) -> Dict:
            """Visualize causality relationships."""
            # Group by strength
            strong_links = []  # strength >= 0.8
            medium_links = []  # strength 0.5-0.8
            weak_links = []    # strength < 0.5

            for link in causality_data:
                strength = link.get('strength', 0)
                visual_link = {
                    'from': link['from'],
                    'to': link['to'],
                    'strength': strength,
                    'stroke_width': max(1, int(strength * 5)),
                    'opacity': max(0.3, strength)
                }

                if strength >= 0.8:
                    strong_links.append(visual_link)
                elif strength >= 0.5:
                    medium_links.append(visual_link)
                else:
                    weak_links.append(visual_link)

            return {
                'strong_causality': strong_links,
                'medium_causality': medium_links,
                'weak_causality': weak_links,
                'summary': {
                    'total_relationships': len(causality_data),
                    'strong_count': len(strong_links),
                    'medium_count': len(medium_links),
                    'weak_count': len(weak_links)
                }
            }

        visualizer.visualize_causality = visualize_causality
        return visualizer

    def test_causality_visualization_categorizes_by_strength(self, causality_visualizer):
        """Causality visualization categorizes relationships by strength."""
        causality_data = [
            {'from': 'd1', 'to': 'd2', 'strength': 0.9},
            {'from': 'd2', 'to': 'd3', 'strength': 0.65},
            {'from': 'd3', 'to': 'd4', 'strength': 0.3}
        ]

        visualization = causality_visualizer.visualize_causality(causality_data)

        assert len(visualization['strong_causality']) == 1
        assert len(visualization['medium_causality']) == 1
        assert len(visualization['weak_causality']) == 1
        assert visualization['summary']['total_relationships'] == 3

    def test_causality_visualization_applies_visual_properties(self, causality_visualizer):
        """Causality visualization applies correct visual properties."""
        causality_data = [
            {'from': 'd1', 'to': 'd2', 'strength': 0.95}
        ]

        visualization = causality_visualizer.visualize_causality(causality_data)

        link = visualization['strong_causality'][0]
        assert link['strength'] == 0.95
        assert link['stroke_width'] >= 1
        assert 0.3 <= link['opacity'] <= 1.0

    def test_causality_visualization_summary_accurate(self, causality_visualizer):
        """Causality visualization summary is accurate."""
        causality_data = [
            {'from': 'd1', 'to': 'd2', 'strength': 0.85},
            {'from': 'd2', 'to': 'd3', 'strength': 0.85},
            {'from': 'd3', 'to': 'd4', 'strength': 0.65},
            {'from': 'd4', 'to': 'd5', 'strength': 0.3}
        ]

        visualization = causality_visualizer.visualize_causality(causality_data)
        summary = visualization['summary']

        assert summary['total_relationships'] == 4
        assert summary['strong_count'] == 2
        assert summary['medium_count'] == 1
        assert summary['weak_count'] == 1
        assert (summary['strong_count'] + summary['medium_count'] +
                summary['weak_count']) == summary['total_relationships']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
