"""
Phase 3.3 Integration Tests: Service and Config Context-Aware Retrieval

Validates service health timeline integration, config impact timeline integration,
and query intent detection for context-aware deployment search.

Run:
    pytest tests/unit/test_phase_3_3_service_config_retrieval.py -v
"""

import pytest
import tempfile
import os
from pathlib import Path

# Import the context store
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "dashboard" / "backend"))

from api.services.context_store import ContextStore


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    yield db_path
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def context_store(temp_db):
    """Create a ContextStore instance with a temporary database."""
    store = ContextStore(db_path=temp_db)
    return store


class TestPhase33QueryIntentDetection:
    """Test Phase 3.3 query intent detection methods."""

    def test_detect_service_intent_with_service_keyword(self):
        """Service intent should detect 'service' keyword."""
        assert ContextStore.detect_service_intent("why is the service failing") is True

    def test_detect_service_intent_with_service_name(self):
        """Service intent should detect known service names."""
        assert ContextStore.detect_service_intent("hybrid-coordinator failing") is True
        assert ContextStore.detect_service_intent("qdrant down") is True
        assert ContextStore.detect_service_intent("dashboard health status") is True

    def test_detect_service_intent_with_health_keywords(self):
        """Service intent should detect health-related keywords."""
        assert ContextStore.detect_service_intent("service health status") is True
        assert ContextStore.detect_service_intent("running status") is True
        assert ContextStore.detect_service_intent("process failed") is True

    def test_detect_service_intent_false(self):
        """Service intent should be false for non-service queries."""
        assert ContextStore.detect_service_intent("deployment failed") is False
        assert ContextStore.detect_service_intent("deployment progress") is False
        assert ContextStore.detect_service_intent("config changes") is False

    def test_detect_config_intent_with_config_keyword(self):
        """Config intent should detect 'config' keyword."""
        assert ContextStore.detect_config_intent("configuration issues") is True
        assert ContextStore.detect_config_intent("config changes") is True

    def test_detect_config_intent_with_setting_keywords(self):
        """Config intent should detect setting-related keywords."""
        assert ContextStore.detect_config_intent("port configuration") is True
        assert ContextStore.detect_config_intent("parameter settings") is True
        assert ContextStore.detect_config_intent("nix module changes") is True

    def test_detect_config_intent_false(self):
        """Config intent should be false for non-config queries."""
        assert ContextStore.detect_config_intent("service health") is False
        assert ContextStore.detect_config_intent("deployment logs") is False


class TestPhase33KeywordExtraction:
    """Test Phase 3.3 keyword/name extraction methods."""

    def test_build_fts_query_normalizes_hyphenated_terms(self):
        """FTS query builder should sanitize punctuation-heavy free-text queries."""
        assert ContextStore._build_fts_query("hybrid-coordinator status") == "hybrid coordinator status"
        assert ContextStore._build_fts_query("dashboard-api status") == "dashboard api status"
        assert ContextStore._build_fts_query("database_url config") == "database url config"

    def test_extract_service_names_single(self):
        """Should extract single service name from query."""
        names = ContextStore._extract_service_names_from_query("hybrid-coordinator failing")
        assert "hybrid-coordinator" in names

    def test_extract_service_names_multiple(self):
        """Should extract multiple service names from query."""
        names = ContextStore._extract_service_names_from_query("hybrid-coordinator and qdrant are down")
        assert "hybrid-coordinator" in names
        assert "qdrant" in names

    def test_extract_service_names_empty(self):
        """Should return empty list when no service names found."""
        names = ContextStore._extract_service_names_from_query("deployment status")
        assert isinstance(names, list)
        assert len(names) == 0

    def test_extract_config_keys_single(self):
        """Should extract config keys from query."""
        keys = ContextStore._extract_config_keys_from_query("port configuration issue")
        assert isinstance(keys, list)
        # Should extract 'port' at minimum
        assert len(keys) > 0

    def test_extract_config_keys_empty(self):
        """Should return empty or small list for generic queries."""
        keys = ContextStore._extract_config_keys_from_query("what is happening")
        assert isinstance(keys, list)


class TestPhase33ServiceContextSearch:
    """Test Phase 3.3 service context search methods."""

    def test_search_service_context_returns_list(self, context_store):
        """search_service_context should return a list."""
        result = context_store.search_service_context("hybrid-coordinator failing")
        assert isinstance(result, list)

    def test_search_service_context_empty_when_no_services(self, context_store):
        """search_service_context should return empty list for non-service query."""
        result = context_store.search_service_context("deployment logs")
        assert isinstance(result, list)
        assert len(result) == 0

    def test_search_service_context_adds_service_health_data(self, context_store):
        """search_service_context should add service data when service mentioned."""
        # Add a service health entry
        context_store.add_service_state(
            deployment_id="deploy-123",
            service_name="hybrid-coordinator",
            status="failed",
            metadata={"reason": "port conflict"}
        )

        result = context_store.search_service_context("hybrid-coordinator failing")
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["source"] == "service"
        assert result[0]["metadata"]["service_name"] == "hybrid-coordinator"
        assert result[0]["metadata"]["health_issue"] is True


class TestPhase33ConfigContextSearch:
    """Test Phase 3.3 config context search methods."""

    def test_search_config_context_returns_list(self, context_store):
        """search_config_context should return a list."""
        result = context_store.search_config_context("port configuration issue")
        assert isinstance(result, list)

    def test_search_config_context_empty_when_no_configs(self, context_store):
        """search_config_context should return empty list for non-config query."""
        result = context_store.search_config_context("deployment logs")
        assert isinstance(result, list)
        assert len(result) == 0

    def test_search_config_context_adds_config_data(self, context_store):
        """search_config_context should include config change data when available."""
        # Add a config change entry
        context_store.add_config_change(
            deployment_id="deploy-456",
            config_key="database_url",
            config_value="8080",
            change_type="update",
            metadata={"file": "config/app.yaml"}
        )

        result = context_store.search_config_context("database configuration")
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["source"] == "config"
        assert result[0]["metadata"]["config_key"] == "database_url"
        assert result[0]["metadata"]["change_type"] == "update"


class TestPhase33SearchDeploymentContextIntegration:
    """Test Phase 3.3 integration into search_deployment_context."""

    def test_search_deployments_handles_hyphenated_query(self, context_store):
        """search_deployments should not raise or silently fail on hyphenated service names."""
        context_store.start_deployment("deploy-fts-test", "deploy hybrid-coordinator")
        context_store.add_event(
            "deploy-fts-test",
            "info",
            "hybrid-coordinator status active",
            progress=10,
        )

        result = context_store.search_deployments("hybrid-coordinator status")
        assert isinstance(result, list)
        assert len(result) >= 1
        assert any("hybrid-coordinator" in str(item.get("message") or "") for item in result)

    def test_search_deployment_context_with_service_query(self, context_store):
        """search_deployment_context should include service results for service queries."""
        # Start a deployment
        context_store.start_deployment("deploy-service-test", "deploy system --some-flag")

        # Add a service state
        context_store.add_service_state(
            deployment_id="deploy-service-test",
            service_name="hybrid-coordinator",
            status="active",
            metadata={}
        )

        result = context_store.search_deployment_context("hybrid-coordinator status")
        assert isinstance(result, dict)
        assert "results" in result
        assert "sources" in result

        sources = result.get("sources", {})
        assert sources.get("service", 0) >= 1
        assert any(item.get("source") == "service" for item in result["results"])

    def test_search_deployment_context_with_config_query(self, context_store):
        """search_deployment_context should include config results for config queries."""
        # Start a deployment
        context_store.start_deployment("deploy-config-test", "deploy system")

        # Add a config change
        context_store.add_config_change(
            deployment_id="deploy-config-test",
            config_key="database_url",
            config_value="postgres://localhost",
            change_type="update"
        )

        result = context_store.search_deployment_context("config database")
        assert isinstance(result, dict)
        assert "results" in result
        assert "sources" in result

        sources = result.get("sources", {})
        assert sources.get("config", 0) >= 1
        assert any(item.get("source") == "config" for item in result["results"])

    def test_search_deployment_context_returns_proper_structure(self, context_store):
        """search_deployment_context should return proper result structure."""
        result = context_store.search_deployment_context("test query")
        assert isinstance(result, dict)
        assert "results" in result
        assert "query_analysis" in result
        assert "operator_guidance" in result
        assert "effective_mode" in result
        assert "sources" in result

        # Verify sources dictionary structure
        sources = result.get("sources", {})
        assert "deployment" in sources
        assert "logs" in sources
        assert "service" in sources  # Phase 3.3 addition
        assert "config" in sources   # Phase 3.3 addition
        assert "code" in sources


class TestPhase33ServiceDataStructure:
    """Test Phase 3.3 service context data structure."""

    def test_service_result_has_required_fields(self, context_store):
        """Service search results should have required fields."""
        # Add service data
        context_store.add_service_state(
            deployment_id="deploy-001",
            service_name="test-service",
            status="failed",
            metadata={"error": "connection refused"}
        )

        result = context_store.search_service_context("test-service failing")

        assert len(result) == 1
        item = result[0]
        assert "id" in item
        assert "source" in item
        assert item["source"] == "service"
        assert "message" in item
        assert "metadata" in item
        assert "explanation" in item


class TestPhase33ConfigDataStructure:
    """Test Phase 3.3 config context data structure."""

    def test_config_result_has_required_fields(self, context_store):
        """Config search results should have required fields."""
        # Add config data
        context_store.add_config_change(
            deployment_id="deploy-002",
            config_key="api_key",
            config_value="secret123",
            change_type="update",
            metadata={"file": "config/secrets.yaml"}
        )

        result = context_store.search_config_context("api_key configuration")

        assert len(result) == 1
        item = result[0]
        assert "id" in item
        assert "source" in item
        assert item["source"] == "config"
        assert "message" in item
        assert "metadata" in item
        assert "explanation" in item


class TestPhase33RankingEnhancements:
    """Test Phase 3.3 ranking enhancements for services and configs."""

    def test_score_context_result_boosts_service_results(self, context_store):
        """_score_context_result should boost service results in service-focused queries."""
        query_analysis = ContextStore.analyze_deployment_query("hybrid-coordinator health")

        # Service result
        service_item = {
            "source": "service",
            "message": "Service hybrid-coordinator status: failed",
            "metadata": {"health_issue": True},
            "explanation": {"matched_terms": ["hybrid-coordinator"]},
            "relevance_score": 1
        }

        score = ContextStore._score_context_result(query_analysis, service_item)
        assert isinstance(score, int)
        assert score > 0

    def test_score_context_result_boosts_config_results(self, context_store):
        """_score_context_result should boost config results in config-focused queries."""
        query_analysis = ContextStore.analyze_deployment_query("port configuration issue")

        # Config result
        config_item = {
            "source": "config",
            "message": "Config port changed: 8080",
            "metadata": {"config_key": "port"},
            "explanation": {"matched_terms": ["port", "config"]},
            "relevance_score": 1
        }

        score = ContextStore._score_context_result(query_analysis, config_item)
        assert isinstance(score, int)
        assert score > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
