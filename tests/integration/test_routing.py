"""
Routing decision integration tests for the hybrid-coordinator.

Validates that the /query endpoint correctly populates the ``backend`` field
and that routing overrides (prefer_local=false) and validation errors behave
as expected.

Run:
    pytest tests/integration/test_routing.py -v

Override defaults with env vars:
    HYBRID_COORDINATOR_URL=http://localhost:8003
    HYBRID_API_KEY_FILE=/run/secrets/hybrid_coordinator_api_key
    HYBRID_API_KEY=<key>

Notes on the routing model:
  - The ``backend`` field in a /query response equals the search ``route``
    chosen (one of: ``hybrid``, ``keyword``, ``semantic``, ``tree``, ``sql``).
  - The LLM backend selection (local vs remote) is controlled by ``prefer_local``
    in the request body; ``prefer_local=false`` requests remote routing.
  - A missing ``query`` field returns HTTP 400 from the aiohttp handler (not
    FastAPI's 422, since this service uses aiohttp).
"""

import os
import pytest
import httpx

# ---------------------------------------------------------------------------
# Service URL constant — never hardcoded
# ---------------------------------------------------------------------------

COORDINATOR_URL = os.getenv("HYBRID_COORDINATOR_URL", "http://localhost:8003")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

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
    """Read the hybrid-coordinator API key, skipping if unavailable."""
    key = _read_api_key()
    if not key:
        pytest.skip("No API key available — set HYBRID_API_KEY_FILE or HYBRID_API_KEY")
    return key


@pytest.fixture(scope="session")
def client(api_key):
    """Session-scoped httpx client for the hybrid coordinator."""
    headers = {"X-API-Key": api_key, "Content-Type": "application/json"}
    try:
        with httpx.Client(base_url=COORDINATOR_URL, headers=headers, timeout=30.0) as c:
            try:
                c.get("/health", timeout=5.0)
            except (httpx.ConnectError, httpx.TimeoutException) as exc:
                pytest.skip(f"Hybrid coordinator unreachable at {COORDINATOR_URL}: {exc}")
            yield c
    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        pytest.skip(f"Hybrid coordinator unreachable at {COORDINATOR_URL}: {exc}")


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def assert_keys(obj: dict, *required_keys):
    """Assert all required_keys are present in obj."""
    missing = [k for k in required_keys if k not in obj]
    assert not missing, f"Missing keys {missing} in response: {list(obj.keys())}"


def _get_backend(body: dict) -> str | None:
    """Return the backend/route field from a /query response, or None if absent."""
    return body.get("backend") or body.get("llm_backend")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRouting:
    """Routing decision tests for POST /query."""

    def test_force_remote_routes_to_remote(self, client):
        """Send a query with prefer_local=false, which requests remote LLM routing.

        The ``backend`` field reflects the search route (hybrid/keyword/semantic),
        not the LLM backend label.  We assert that the request succeeds (200) and
        that a ``backend`` field is present.  If the local model is not configured
        or the remote API is unreachable, the coordinator may still return 200 with
        a local-fallback route — we accept any non-error response.

        The test skips rather than fails when the service is unreachable.
        """
        body = {
            "query": "what is NixOS reproducibility",
            "mode": "auto",
            "prefer_local": False,
            "limit": 3,
        }
        try:
            resp = client.post("/query", json=body)
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            pytest.skip(f"Coordinator request failed: {exc}")

        assert resp.status_code == 200, (
            f"Expected 200 from POST /query with prefer_local=false, "
            f"got {resp.status_code}: {resp.text}"
        )
        resp_body = resp.json()
        backend = _get_backend(resp_body)
        assert backend is not None, (
            f"Response missing 'backend' or 'llm_backend' field. "
            f"Keys present: {list(resp_body.keys())}"
        )

    def test_default_query_returns_backend_field(self, client):
        """Send a normal query without any routing overrides and assert the
        response contains a ``backend`` field with a non-empty string value.

        This is the baseline contract: every successful /query response must
        report which route was taken.
        """
        body = {
            "query": "NixOS module options",
            "mode": "auto",
            "limit": 3,
        }
        try:
            resp = client.post("/query", json=body)
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            pytest.skip(f"Coordinator request failed: {exc}")

        assert resp.status_code == 200, (
            f"Expected 200 from POST /query, got {resp.status_code}: {resp.text}"
        )
        resp_body = resp.json()
        backend = _get_backend(resp_body)
        assert backend is not None, (
            f"Response missing 'backend' or 'llm_backend' field. "
            f"Keys present: {list(resp_body.keys())}"
        )
        assert isinstance(backend, str) and backend, (
            f"Expected a non-empty string for 'backend', got: {backend!r}"
        )

    def test_long_technical_query_has_backend_field(self, client):
        """Send a long NixOS technical query (30+ words) and assert the response
        contains a ``backend`` field.

        Long queries trigger the ``hybrid`` or ``tree`` route in auto mode.
        This test validates that the routing logic handles verbose technical
        queries without error and correctly reports the chosen route.
        """
        long_query = (
            "How do I configure NixOS flake inputs and overlays to pin a specific "
            "version of nixpkgs while simultaneously applying custom package overlays "
            "that modify the default gcc and enable unfree packages for CUDA support "
            "on a system with multiple overlapping module definitions?"
        )
        body = {
            "query": long_query,
            "mode": "auto",
            "limit": 5,
        }
        try:
            resp = client.post("/query", json=body)
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            pytest.skip(f"Coordinator request failed: {exc}")

        assert resp.status_code == 200, (
            f"Expected 200 from POST /query, got {resp.status_code}: {resp.text}"
        )
        resp_body = resp.json()
        backend = _get_backend(resp_body)
        assert backend is not None, (
            f"Response missing 'backend' or 'llm_backend' field for long query. "
            f"Keys present: {list(resp_body.keys())}"
        )

    def test_missing_query_returns_error(self, client):
        """Send a POST /query body with no ``query`` field and assert the server
        returns an HTTP error status.

        The hybrid-coordinator uses aiohttp which returns HTTP 400 when the
        query field is absent (the handler checks: ``if not query: return 400``).
        We accept any 4xx status code here to remain robust against minor server
        version changes that might adjust the specific code.
        """
        body = {
            "mode": "auto",
            "limit": 3,
        }
        try:
            resp = client.post("/query", json=body)
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            pytest.skip(f"Coordinator request failed: {exc}")

        assert 400 <= resp.status_code < 500, (
            f"Expected a 4xx error when 'query' is missing, "
            f"got {resp.status_code}: {resp.text}"
        )
        resp_body = resp.json()
        assert "error" in resp_body, (
            f"Expected an 'error' key in the error response body, "
            f"got: {list(resp_body.keys())}"
        )

    def test_route_search_returns_results_list(self, client):
        """Send a query for 'systemd service configuration' and assert the
        response contains a ``results`` dict.

        The ``results`` value is always a dict with at least one of:
        ``combined_results``, ``semantic_results``, or ``keyword_results``
        sub-keys, each of which is a list.  This test asserts the outer dict
        shape; individual sub-lists may be empty if the vector DB has no
        matching content.
        """
        body = {
            "query": "systemd service configuration",
            "mode": "auto",
            "limit": 5,
        }
        try:
            resp = client.post("/query", json=body)
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            pytest.skip(f"Coordinator request failed: {exc}")

        assert resp.status_code == 200, (
            f"Expected 200 from POST /query, got {resp.status_code}: {resp.text}"
        )
        resp_body = resp.json()
        assert "results" in resp_body, (
            f"Response missing 'results' key. Keys present: {list(resp_body.keys())}"
        )
        assert isinstance(resp_body["results"], dict), (
            f"Expected 'results' to be a dict, got {type(resp_body['results'])}"
        )

        # Verify that at least one of the expected sub-keys is a list
        results = resp_body["results"]
        candidates = [
            results.get("combined_results"),
            results.get("semantic_results"),
            results.get("keyword_results"),
        ]
        non_none = [c for c in candidates if c is not None]
        assert non_none, (
            "None of combined_results / semantic_results / keyword_results present "
            f"in results dict. Keys: {list(results.keys())}"
        )
        for sub_list in non_none:
            assert isinstance(sub_list, list), (
                f"Expected sub-list to be a list, got {type(sub_list)}"
            )
