"""
Shared mock config helper for route-handler unit tests.

Provides URL constants that respect environment overrides (matching
config/service-endpoints.sh conventions), so tests don't hardcode ports.

Usage in route-handler test stubs:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent))
    import _mock_config as _mc

    sys.modules.setdefault("config", types.SimpleNamespace(
        Config=types.SimpleNamespace(
            LLAMA_CPP_URL=_mc.LLAMA_URL,
            SWITCHBOARD_URL=_mc.SWITCHBOARD_URL,
            ...
        )
    ))
"""
import os


def _svc_url(env_url_key: str, env_host_key: str, env_port_key: str,
             default_host: str, default_port: str) -> str:
    """Return a service URL from env vars (matching service-endpoints.sh)."""
    if os.getenv(env_url_key):
        return os.environ[env_url_key]
    host = os.getenv(env_host_key, default_host)
    port = os.getenv(env_port_key, default_port)
    return f"http://{host}:{port}"


LLAMA_URL = _svc_url("LLAMA_URL", "LLAMA_HOST", "LLAMA_PORT", "127.0.0.1", "8080")
EMBEDDINGS_URL = _svc_url("EMBEDDINGS_URL", "EMBEDDINGS_HOST", "EMBEDDINGS_PORT", "127.0.0.1", "8081")
AIDB_URL = _svc_url("AIDB_URL", "AIDB_HOST", "AIDB_PORT", "127.0.0.1", "8002")
HYBRID_URL = _svc_url("HYBRID_URL", "HYBRID_HOST", "HYBRID_PORT", "127.0.0.1", "8003")
RALPH_URL = _svc_url("RALPH_URL", "RALPH_HOST", "RALPH_PORT", "127.0.0.1", "8004")
SWITCHBOARD_URL = _svc_url("SWITCHBOARD_URL", "SWITCHBOARD_HOST", "SWITCHBOARD_PORT", "127.0.0.1", "8085")
