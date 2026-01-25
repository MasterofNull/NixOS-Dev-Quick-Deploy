import requests

from conftest import require_service


def _get(url: str, timeout: int = 5):
    return requests.get(url, timeout=timeout)


def _post(url: str, payload: dict, timeout: int = 10):
    return requests.post(url, json=payload, timeout=timeout)


def test_aidb_health(base_urls):
    url = f"{base_urls['aidb']}/health"
    require_service(url)
    response = _get(url)
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") in {"ok", "healthy"}


def test_aidb_documents_list(base_urls):
    url = f"{base_urls['aidb']}/documents?limit=1"
    require_service(url)
    response = _get(url)
    assert response.status_code == 200
    data = response.json()
    assert "documents" in data


def test_hybrid_health(base_urls):
    url = f"{base_urls['hybrid']}/health"
    require_service(url)
    response = _get(url)
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") == "healthy"
    assert "collections" in data


def test_hybrid_augment_query(base_urls):
    url = f"{base_urls['hybrid']}/augment_query"
    require_service(f"{base_urls['hybrid']}/health")
    response = _post(
        url,
        {"query": "auto-commit feature request implementation", "agent_type": "remote"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "augmented_prompt" in data
    assert "context_count" in data


def test_qdrant_health():
    url = "http://localhost:6333/healthz"
    require_service(url)
    response = _get(url)
    assert response.status_code == 200


def test_llama_cpp_models():
    url = "http://localhost:8080/v1/models"
    require_service(url)
    response = _get(url)
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
