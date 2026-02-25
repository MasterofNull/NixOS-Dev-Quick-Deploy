"""
Centralized service endpoint configuration.

All AI stack service URLs are defined here. Override via environment variables.
"""
import os
import re
from urllib.parse import urlparse

SERVICE_HOST = os.getenv("SERVICE_HOST", "localhost")
AI_STACK_NAMESPACE = os.getenv("AI_STACK_NAMESPACE", "ai-stack")

def _parse_port(env_key: str, default: int) -> int:
    raw = os.getenv(env_key, "")
    if raw.isdigit():
        return int(raw)
    if raw:
        try:
            parsed = urlparse(raw)
            if parsed.port:
                return int(parsed.port)
        except ValueError:
            pass
        match = re.search(r":(\d+)$", raw)
        if match:
            return int(match.group(1))
    return default


# Port defaults (match declarative host-mode registry); tolerate URL-like env values.
AIDB_PORT = _parse_port("AIDB_PORT", 8002)
HYBRID_COORDINATOR_PORT = _parse_port("HYBRID_COORDINATOR_PORT", 8003)
QDRANT_PORT = _parse_port("QDRANT_PORT", 6333)
LLAMA_CPP_PORT = _parse_port("LLAMA_CPP_PORT", 8080)
EMBEDDINGS_PORT = _parse_port("EMBEDDINGS_PORT", 8081)
SWITCHBOARD_PORT = _parse_port("SWITCHBOARD_PORT", 8085)
EMBEDDING_DIMENSIONS = _parse_port("EMBEDDING_DIMENSIONS", 768)
OPEN_WEBUI_PORT = _parse_port("OPEN_WEBUI_PORT", 3001)
GRAFANA_PORT = _parse_port("GRAFANA_PORT", 3000)
PROMETHEUS_PORT = _parse_port("PROMETHEUS_PORT", 9090)
MINDSDB_PORT = _parse_port("MINDSDB_PORT", 47334)
DASHBOARD_API_PORT = _parse_port("DASHBOARD_API_PORT", 8889)
POSTGRES_PORT = _parse_port("POSTGRES_PORT", 5432)
REDIS_PORT = _parse_port("REDIS_PORT", 6379)
RALPH_PORT = _parse_port("RALPH_PORT", 8004)

# Full service URLs (overridable)
AIDB_URL = os.getenv("AIDB_URL", f"http://{SERVICE_HOST}:{AIDB_PORT}")
HYBRID_URL = os.getenv("HYBRID_URL", f"http://{SERVICE_HOST}:{HYBRID_COORDINATOR_PORT}")
QDRANT_URL = os.getenv("QDRANT_URL", f"http://{SERVICE_HOST}:{QDRANT_PORT}")
LLAMA_URL = os.getenv("LLAMA_URL", f"http://{SERVICE_HOST}:{LLAMA_CPP_PORT}")
EMBEDDINGS_URL = os.getenv("EMBEDDINGS_URL", f"http://{SERVICE_HOST}:{EMBEDDINGS_PORT}")
SWITCHBOARD_URL = os.getenv("SWITCHBOARD_URL", f"http://{SERVICE_HOST}:{SWITCHBOARD_PORT}")
OPEN_WEBUI_URL = os.getenv("OPEN_WEBUI_URL", f"http://{SERVICE_HOST}:{OPEN_WEBUI_PORT}")
GRAFANA_URL = os.getenv("GRAFANA_URL", f"http://{SERVICE_HOST}:{GRAFANA_PORT}")
PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", f"http://{SERVICE_HOST}:{PROMETHEUS_PORT}")
MINDSDB_URL = os.getenv("MINDSDB_URL", f"http://{SERVICE_HOST}:{MINDSDB_PORT}")
RALPH_URL = os.getenv("RALPH_URL", f"http://{SERVICE_HOST}:{RALPH_PORT}")
