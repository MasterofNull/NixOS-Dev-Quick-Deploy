import os
import sys
from pathlib import Path

# Add relevant subdirectories to sys.path
AI_STACK_ROOT = Path(__file__).parent.resolve()

paths = [
    AI_STACK_ROOT,
    AI_STACK_ROOT / "aidb",
    AI_STACK_ROOT / "offloading",
    AI_STACK_ROOT / "mcp-servers" / "hybrid-coordinator",
    AI_STACK_ROOT / "mcp-servers" / "hybrid-coordinator" / "core",
    AI_STACK_ROOT / "mcp-servers" / "hybrid-coordinator" / "knowledge",
    AI_STACK_ROOT / "mcp-servers" / "aidb",
]
for p in reversed(paths):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

# Set mock environment variables to prevent RuntimeError during test collection
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("AIDB_URL", "http://localhost:8002")
os.environ.setdefault("HYBRID_URL", "http://localhost:8003")
os.environ.setdefault("HYBRID_COORDINATOR_API_KEY", "test-key")
os.environ.setdefault("LLAMA_CPP_BASE_URL", "http://localhost:8080")
os.environ.setdefault("POSTGRES_PORT", "5432")
os.environ.setdefault("REDIS_PORT", "6379")
os.environ.setdefault("STRICT_ENV", "false")
os.environ.setdefault("AI_STRICT_ENV", "false")

# Mock missing third-party modules that tests might import at module level
from unittest.mock import MagicMock
from types import ModuleType

def mock_module(name, attributes=None):
    m = ModuleType(name)
    m.__spec__ = MagicMock()
    if attributes:
        for k, v in attributes.items():
            setattr(m, k, v)
    sys.modules[name] = m
    return m

# Robust structlog mock
structlog_mock = mock_module("structlog")
structlog_mock.get_logger = MagicMock(return_value=MagicMock())

mock_module("prometheus_client", {
    "Counter": MagicMock,
    "Gauge": MagicMock,
    "Histogram": MagicMock,
    "Summary": MagicMock,
})
mock_module("psutil")
