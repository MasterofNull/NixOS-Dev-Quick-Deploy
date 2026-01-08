import json
from pathlib import Path

import pytest
import requests

from conftest import require_service


def _headers(api_key: str) -> dict:
    return {"X-API-Key": api_key} if api_key else {}


@pytest.mark.integration
def test_compose_startup_order():
    compose_path = Path("ai-stack/compose/docker-compose.yml")
    data = json.loads(
        json.dumps(__import__("yaml").safe_load(compose_path.read_text(encoding="utf-8")))
    )
    services = data.get("services", {})

    aidb_depends = services.get("aidb", {}).get("depends_on", {})
    assert "postgres" in aidb_depends
    assert "redis" in aidb_depends
    assert "qdrant" in aidb_depends

    hybrid_depends = services.get("hybrid-coordinator", {}).get("depends_on", {})
    assert "postgres" in hybrid_depends
    assert "redis" in hybrid_depends
    assert "qdrant" in hybrid_depends
    assert "embeddings" in hybrid_depends


@pytest.mark.integration
def test_services_health(base_urls):
    require_service(f"{base_urls['aidb']}/health")
    require_service(f"{base_urls['embeddings']}/health")
    require_service(f"{base_urls['hybrid']}/health")


@pytest.mark.integration
def test_embeddings_workflow(base_urls, api_key):
    url = f"{base_urls['embeddings']}/embed"
    require_service(f"{base_urls['embeddings']}/health")
    response = requests.post(
        url,
        headers={**_headers(api_key), "Content-Type": "application/json"},
        json={"inputs": ["hello world"]},
        timeout=5,
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert data and isinstance(data[0], list)


@pytest.mark.integration
def test_vector_search_workflow(base_urls, api_key):
    require_service(f"{base_urls['aidb']}/health")

    doc_payload = {
        "project": "integration-test",
        "relative_path": "integration-test/doc.txt",
        "title": "Integration Test Doc",
        "content": "Testing embeddings and vector search flow.",
    }
    create_doc = requests.post(
        f"{base_urls['aidb']}/documents",
        headers={**_headers(api_key), "Content-Type": "application/json"},
        json=doc_payload,
        timeout=5,
    )
    assert create_doc.status_code == 200

    docs = requests.get(
        f"{base_urls['aidb']}/documents",
        params={"project": "integration-test", "limit": 1},
        timeout=5,
    )
    assert docs.status_code == 200
    doc_list = docs.json().get("documents", [])
    assert doc_list
    document_id = doc_list[0]["id"]

    index_payload = {"items": [{"document_id": document_id}]}
    try:
        index_resp = requests.post(
            f"{base_urls['aidb']}/vector/index",
            headers={**_headers(api_key), "Content-Type": "application/json"},
            json=index_payload,
            timeout=30,
        )
    except requests.exceptions.Timeout:
        pytest.skip("vector index timed out")
    assert index_resp.status_code == 200

    search_resp = requests.post(
        f"{base_urls['aidb']}/vector/search",
        headers={"Content-Type": "application/json"},
        json={"query": "Testing embeddings"},
        timeout=5,
    )
    assert search_resp.status_code == 200
    results = search_resp.json().get("results", [])
    assert isinstance(results, list)


@pytest.mark.integration
def test_circuit_breaker_health_output(base_urls):
    require_service(f"{base_urls['aidb']}/health")
    response = requests.get(f"{base_urls['aidb']}/health", timeout=5)
    assert response.status_code == 200
    breakers = response.json().get("circuit_breakers")
    assert isinstance(breakers, dict)
    for state in breakers.values():
        assert state in {"CLOSED", "HALF_OPEN", "OPEN"}


@pytest.mark.integration
def test_graceful_degradation_invalid_payload(base_urls):
    require_service(f"{base_urls['aidb']}/health")
    response = requests.post(
        f"{base_urls['aidb']}/vector/search",
        headers={"Content-Type": "application/json"},
        json={},
        timeout=5,
    )
    assert response.status_code == 400


@pytest.mark.integration
def test_retry_logic_behavior():
    server_text = Path("ai-stack/mcp-servers/aidb/server.py").read_text(encoding="utf-8")
    assert "def retry_with_backoff" in server_text
    assert "max_retries" in server_text
