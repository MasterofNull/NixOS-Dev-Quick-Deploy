import os
from pathlib import Path

import pytest


def pytest_configure():
    os.environ.setdefault("OTEL_TRACING_ENABLED", "false")


@pytest.fixture(scope="session")
def api_key() -> str:
    key_path = Path(os.getenv("AI_STACK_API_KEY_FILE", "ai-stack/compose/secrets/stack_api_key"))
    if key_path.exists():
        return key_path.read_text(encoding="utf-8").strip()
    return ""


@pytest.fixture(scope="session")
def base_urls():
    return {
        "aidb": os.getenv("AIDB_BASE_URL", "http://localhost:8091"),
        "embeddings": os.getenv("EMBEDDINGS_BASE_URL", "http://localhost:8081"),
        "hybrid": os.getenv("HYBRID_BASE_URL", "http://localhost:8092"),
    }


def require_service(url: str) -> None:
    import requests

    try:
        response = requests.get(url, timeout=1)
    except Exception as exc:
        pytest.skip(f"service unavailable: {url} ({exc})")
    if response.status_code >= 500:
        pytest.skip(f"service unhealthy: {url} ({response.status_code})")
