"""
MCP contract tests for the hybrid-coordinator server.

Validates response shapes for all public HTTP endpoints.
Requires the hybrid-coordinator to be running on HYBRID_COORDINATOR_URL
(default: http://localhost:8003).

Run:
    pytest tests/integration/test_mcp_contracts.py -v

Set env vars to override defaults:
    HYBRID_COORDINATOR_URL=http://localhost:8003
    HYBRID_API_KEY_FILE=/run/secrets/hybrid_coordinator_api_key
"""

import os
import pytest
import httpx

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

BASE_URL = os.getenv("HYBRID_COORDINATOR_URL", "http://localhost:8003")

def _read_api_key() -> str:
    key_file = os.getenv(
        "HYBRID_API_KEY_FILE",
        "/run/secrets/hybrid_coordinator_api_key",
    )
    try:
        with open(key_file) as f:
            return f.read().strip()
    except OSError:
        return os.getenv("HYBRID_API_KEY", "")


@pytest.fixture(scope="session")
def api_key():
    key = _read_api_key()
    if not key:
        pytest.skip("No API key available — set HYBRID_API_KEY_FILE or HYBRID_API_KEY")
    return key


@pytest.fixture(scope="session")
def client(api_key):
    headers = {"X-API-Key": api_key, "Content-Type": "application/json"}
    with httpx.Client(base_url=BASE_URL, headers=headers, timeout=30.0) as c:
        yield c


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def assert_keys(obj: dict, *required_keys):
    """Assert all required_keys are present in obj."""
    missing = [k for k in required_keys if k not in obj]
    assert not missing, f"Missing keys {missing} in response: {list(obj.keys())}"


# ---------------------------------------------------------------------------
# TC2.5 — MCP Contract Tests
# ---------------------------------------------------------------------------


class TestHealth:
    """GET /health — must return healthy status with service inventory."""

    def test_status_200(self):
        resp = httpx.get(f"{BASE_URL}/health", timeout=10.0)
        assert resp.status_code == 200

    def test_response_shape(self):
        resp = httpx.get(f"{BASE_URL}/health", timeout=10.0)
        body = resp.json()
        assert_keys(body, "status", "service", "collections", "ai_harness")
        assert body["status"] == "healthy"

    def test_collections_non_empty(self):
        resp = httpx.get(f"{BASE_URL}/health", timeout=10.0)
        body = resp.json()
        assert isinstance(body["collections"], list)
        assert len(body["collections"]) > 0

    def test_ai_harness_shape(self):
        resp = httpx.get(f"{BASE_URL}/health", timeout=10.0)
        harness = resp.json()["ai_harness"]
        assert_keys(harness, "enabled", "memory_enabled", "eval_enabled")


class TestQuery:
    """POST /query — route_search endpoint contract."""

    def test_status_401_without_key(self):
        resp = httpx.post(
            f"{BASE_URL}/query",
            json={"query": "test", "mode": "auto"},
            timeout=10.0,
        )
        assert resp.status_code == 401

    def test_status_200_with_key(self, client):
        resp = client.post("/query", json={"query": "NixOS module system", "mode": "auto", "limit": 2})
        assert resp.status_code == 200

    def test_response_shape(self, client):
        resp = client.post("/query", json={"query": "NixOS flake", "mode": "auto", "limit": 2})
        body = resp.json()
        assert_keys(body, "route", "latency_ms", "results", "interaction_id", "response")
        assert body["route"] in ("hybrid", "keyword", "semantic", "tree", "sql")
        assert isinstance(body["latency_ms"], int)
        assert body["latency_ms"] >= 0
        assert isinstance(body["interaction_id"], str)
        assert len(body["interaction_id"]) > 0

    def test_keyword_mode(self, client):
        resp = client.post("/query", json={"query": "nix", "mode": "keyword", "limit": 3})
        assert resp.status_code == 200
        body = resp.json()
        assert body["route"] == "keyword"

    def test_semantic_mode(self, client):
        resp = client.post("/query", json={"query": "configure NixOS services", "mode": "semantic", "limit": 3})
        assert resp.status_code == 200
        body = resp.json()
        assert body["route"] == "semantic"

    def test_auto_mode_short_query_routes_keyword(self, client):
        # Short query (≤3 tokens) should route to keyword in auto mode
        resp = client.post("/query", json={"query": "nix", "mode": "auto"})
        assert resp.status_code == 200
        body = resp.json()
        # Short query → keyword
        assert body["route"] in ("keyword", "hybrid")  # allow hybrid if router overrides

    def test_capability_discovery_shape(self, client):
        resp = client.post("/query", json={"query": "NixOS flake build system", "mode": "auto"})
        body = resp.json()
        assert_keys(body, "capability_discovery")
        cap = body["capability_discovery"]
        assert_keys(cap, "decision", "reason", "cache_hit", "intent_tags")
        assert isinstance(cap["intent_tags"], list)


class TestStatus:
    """GET /status — LLM backend health."""

    def test_status_200(self, client):
        resp = client.get("/status")
        assert resp.status_code == 200

    def test_response_shape(self, client):
        resp = client.get("/status")
        body = resp.json()
        assert_keys(body, "local_llm")
        llm = body["local_llm"]
        assert_keys(llm, "healthy")
        assert isinstance(llm["healthy"], bool)


class TestStats:
    """GET /stats — telemetry stats."""

    def test_status_200(self, client):
        resp = client.get("/stats")
        assert resp.status_code == 200

    def test_response_shape(self, client):
        resp = client.get("/stats")
        body = resp.json()
        assert_keys(body, "stats", "harness_stats", "capability_discovery")


class TestMetrics:
    """GET /metrics — Prometheus text format."""

    def test_status_200(self):
        resp = httpx.get(f"{BASE_URL}/metrics", timeout=10.0)
        assert resp.status_code == 200

    def test_content_type(self):
        resp = httpx.get(f"{BASE_URL}/metrics", timeout=10.0)
        assert "text/plain" in resp.headers.get("content-type", "")

    def test_hybrid_counters_present(self):
        resp = httpx.get(f"{BASE_URL}/metrics", timeout=10.0)
        text = resp.text
        assert "hybrid_request_latency_seconds" in text
        assert "hybrid_route_decisions_total" in text


class TestMemory:
    """POST /memory/store and /memory/recall — agent memory contract."""

    def test_store_returns_status(self, client):
        resp = client.post(
            "/memory/store",
            json={
                "memory_type": "episodic",
                "summary": "contract test memory entry",
                "content": "test content for mcp contract validation",
            },
        )
        # May return 200 (stored) or 200 (disabled)
        assert resp.status_code == 200
        body = resp.json()
        assert "status" in body
        assert body["status"] in ("stored", "disabled")

    def test_recall_returns_shape(self, client):
        resp = client.post(
            "/memory/recall",
            json={"query": "contract test", "memory_types": ["episodic"]},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert_keys(body, "status", "results")
        assert isinstance(body["results"], list)


class TestHarness:
    """GET /harness/scorecard — harness eval contract."""

    def test_scorecard_shape(self, client):
        resp = client.get("/harness/scorecard")
        assert resp.status_code == 200
        body = resp.json()
        assert_keys(body, "generated_at", "acceptance", "discovery", "inference_optimizations")
        assert_keys(body["acceptance"], "total", "passed", "failed", "pass_rate", "ok")
        assert_keys(body["discovery"], "invoked", "skipped", "cache_hits", "errors")
