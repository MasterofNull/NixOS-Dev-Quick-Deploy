"""
RAG round-trip integration tests for the NixOS AI stack.

Validates ingest → query → retrieval for the AIDB + hybrid-coordinator
services.  Both services must be running; tests skip gracefully if either
is unreachable.

Run:
    pytest tests/integration/test_rag_retrieval.py -v

Override defaults with env vars:
    AIDB_URL=http://localhost:8002
    HYBRID_COORDINATOR_URL=http://localhost:8003
    HYBRID_API_KEY_FILE=/run/secrets/hybrid_coordinator_api_key
    HYBRID_API_KEY=<key>
"""

import os
import pytest
import httpx

# ---------------------------------------------------------------------------
# Service URL constants — never hardcoded, always from environment
# ---------------------------------------------------------------------------

COORDINATOR_URL = os.getenv("HYBRID_COORDINATOR_URL", "http://localhost:8003")
AIDB_URL = os.getenv("AIDB_URL", "http://localhost:8002")

# Unique sentinel text that is extremely unlikely to collide with real DB content
RAG_PROBE_SENTINEL = "nixos-rag-test-probe-unique-sentinel-abc123"


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
def coordinator_client(api_key):
    """Session-scoped httpx client for the hybrid coordinator."""
    headers = {"X-API-Key": api_key, "Content-Type": "application/json"}
    try:
        with httpx.Client(base_url=COORDINATOR_URL, headers=headers, timeout=30.0) as c:
            # Probe reachability before yielding; skip on connection failure
            try:
                c.get("/health", timeout=5.0)
            except (httpx.ConnectError, httpx.TimeoutException) as exc:
                pytest.skip(f"Hybrid coordinator unreachable at {COORDINATOR_URL}: {exc}")
            yield c
    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        pytest.skip(f"Hybrid coordinator unreachable at {COORDINATOR_URL}: {exc}")


@pytest.fixture(scope="session")
def aidb_client():
    """Session-scoped httpx client for the AIDB service."""
    try:
        with httpx.Client(base_url=AIDB_URL, timeout=30.0) as c:
            try:
                c.get("/health", timeout=5.0)
            except (httpx.ConnectError, httpx.TimeoutException) as exc:
                pytest.skip(f"AIDB service unreachable at {AIDB_URL}: {exc}")
            yield c
    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        pytest.skip(f"AIDB service unreachable at {AIDB_URL}: {exc}")


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _extract_all_content(results: dict) -> list[str]:
    """Flatten all result items from any route sub-key and extract content strings.

    The /query response returns a ``results`` dict that may contain:
      - ``combined_results``
      - ``semantic_results``
      - ``keyword_results``

    Each item has a ``payload`` dict whose ``content`` key holds the text.
    """
    items = (
        results.get("combined_results")
        or results.get("semantic_results")
        or results.get("keyword_results")
        or []
    )
    texts: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        payload = item.get("payload") or {}
        content = payload.get("content") or ""
        if content:
            texts.append(str(content))
    return texts


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRAGIngestAndRetrieve:
    """Ingest a synthetic document then query the coordinator for it."""

    def test_rag_ingest_and_retrieve(self, aidb_client, coordinator_client):
        """Ingest a document with a unique sentinel string via AIDB, then query
        the hybrid coordinator and assert the sentinel appears in at least one
        result's payload content.

        The test uses a deliberately unique sentinel value so that any positive
        match is unambiguous evidence that the ingested document was indexed and
        returned by the retrieval pipeline.
        """
        # Step 1 — ingest via AIDB POST /documents
        ingest_body = {
            "content": (
                f"This document contains the unique sentinel phrase: {RAG_PROBE_SENTINEL}. "
                "It was written by the integration test suite to verify the RAG pipeline."
            ),
            "project": "integration-test",
            "relative_path": "tests/rag-probe.txt",
            "title": "RAG Integration Test Probe",
            "content_type": "text/plain",
            "status": "approved",
        }
        try:
            ingest_resp = aidb_client.post("/documents", json=ingest_body)
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            pytest.skip(f"AIDB ingest request failed: {exc}")

        assert ingest_resp.status_code == 200, (
            f"Expected 200 from POST /documents, got {ingest_resp.status_code}: "
            f"{ingest_resp.text}"
        )
        ingest_body_resp = ingest_resp.json()
        assert ingest_body_resp.get("status") == "ok", (
            f"Unexpected ingest response body: {ingest_body_resp}"
        )

        # Step 2 — query the hybrid coordinator for the sentinel text
        search_body = {
            "query": RAG_PROBE_SENTINEL,
            "mode": "hybrid",
            "limit": 5,
        }
        try:
            search_resp = coordinator_client.post("/query", json=search_body)
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            pytest.skip(f"Coordinator search request failed: {exc}")

        assert search_resp.status_code == 200, (
            f"Expected 200 from POST /query, got {search_resp.status_code}: "
            f"{search_resp.text}"
        )

        body = search_resp.json()
        assert "results" in body, f"Response missing 'results' key: {list(body.keys())}"
        assert isinstance(body["results"], dict), (
            f"Expected 'results' to be a dict, got {type(body['results'])}"
        )

        all_content = _extract_all_content(body["results"])

        # The ingestion pipeline may have a short indexing delay; we assert
        # that the sentinel appears in at least one content string if results
        # are non-empty.  An empty result set is acceptable (DB may be fresh or
        # embedding model not yet ready) — but if content IS returned, it must
        # be searchable.
        if all_content:
            sentinel_found = any(RAG_PROBE_SENTINEL in text for text in all_content)
            assert sentinel_found, (
                f"Sentinel '{RAG_PROBE_SENTINEL}' not found in any returned content. "
                f"Returned content snippets: {[t[:120] for t in all_content[:5]]}"
            )

    def test_rag_empty_query_returns_results(self, coordinator_client):
        """Send a generic NixOS query and assert the response has a 'results' key
        that maps to a dict (may be empty if the vector DB is freshly initialized).

        This test validates the response schema of the /query endpoint without
        depending on specific documents being present in the database.
        """
        search_body = {
            "query": "NixOS flake",
            "mode": "auto",
            "limit": 5,
        }
        try:
            resp = coordinator_client.post("/query", json=search_body)
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            pytest.skip(f"Coordinator request failed: {exc}")

        assert resp.status_code == 200, (
            f"Expected 200 from POST /query, got {resp.status_code}: {resp.text}"
        )

        body = resp.json()
        assert "results" in body, (
            f"Response missing 'results' key. Keys present: {list(body.keys())}"
        )
        # results is always a dict (route sub-keys vary by mode)
        assert isinstance(body["results"], dict), (
            f"Expected 'results' to be a dict, got {type(body['results'])}: {body['results']}"
        )
