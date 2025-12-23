# Shared Agent Utilities

**Status:** 🚧 Reserved for Future Implementation
**Version:** 0.1.0 (placeholder)

---

## Overview

Shared utilities and common code used across multiple agent skills. These utilities reduce code duplication and provide consistent interfaces for common operations.

---

## Planned Utilities

### Skill Base Classes
```python
from typing import Dict, Any

class AgentSkill:
    """Base class for all agent skills"""

    name: str
    description: str
    version: str
    parameters: Dict[str, ParameterSpec]

    async def execute(self, **kwargs) -> SkillResult:
        """Execute the skill with given parameters"""
        raise NotImplementedError

    async def validate(self, **kwargs) -> bool:
        """Validate parameters before execution"""
        return True

    def get_schema(self) -> Dict[str, Any]:
        """Get JSON schema for skill parameters"""
        pass
```

### HTTP Clients
```python
class HTTPClient:
    """Async HTTP client with retry and timeout"""

    async def get(self, url: str, **kwargs) -> Response:
        pass

    async def post(self, url: str, **kwargs) -> Response:
        pass

    async def with_retry(
        self,
        func: Callable,
        max_retries: int = 3
    ) -> Response:
        """Execute with exponential backoff"""
        pass
```

### Database Utilities
```python
class DatabaseClient:
    """Database connection manager"""

    async def query(self, sql: str, params: Dict) -> List[Dict]:
        pass

    async def execute(self, sql: str, params: Dict) -> int:
        pass

    async def transaction(self) -> AsyncContextManager:
        """Execute multiple queries in transaction"""
        pass
```

### Vector Search
```python
class VectorStore:
    """Qdrant vector database client"""

    async def add_documents(
        self,
        collection: str,
        documents: List[Document]
    ) -> List[str]:
        """Add documents with embeddings"""
        pass

    async def search(
        self,
        collection: str,
        query: str,
        limit: int = 10
    ) -> List[SearchResult]:
        """Semantic search"""
        pass
```

### Caching
```python
class CacheManager:
    """Redis cache manager"""

    async def get(self, key: str) -> Optional[Any]:
        pass

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int = 3600
    ) -> bool:
        pass

    async def invalidate(self, pattern: str) -> int:
        """Invalidate keys matching pattern"""
        pass
```

### Model Inference
```python
class ModelClient:
    """llama.cpp vLLM client"""

    async def generate(
        self,
        prompt: str,
        model: str = "default",
        max_tokens: int = 500
    ) -> str:
        """Generate completion"""
        pass

    async def embed(
        self,
        text: str,
        model: str = "default"
    ) -> List[float]:
        """Generate embeddings"""
        pass
```

### Logging & Telemetry
```python
class SkillLogger:
    """Structured logging for skills"""

    def info(self, message: str, **context):
        pass

    def error(self, message: str, exc: Exception, **context):
        pass

    def metric(self, name: str, value: float, **tags):
        """Record metric"""
        pass
```

### Configuration
```python
class ConfigManager:
    """Environment-aware configuration"""

    def get(self, key: str, default: Any = None) -> Any:
        """Get config value"""
        pass

    def get_required(self, key: str) -> Any:
        """Get required config (raises if missing)"""
        pass

    @property
    def is_production(self) -> bool:
        pass
```

---

## File Structure

```
ai-stack/agents/shared/
├── README.md               # This file
├── __init__.py
├── base.py                 # Base skill classes
├── http.py                 # HTTP utilities
├── database.py             # Database utilities
├── vector.py               # Vector search utilities
├── cache.py                # Caching utilities
├── inference.py            # Model inference utilities
├── logging.py              # Logging utilities
├── config.py               # Configuration utilities
└── validators.py           # Input validation utilities
```

---

## Usage Examples

### Using Base Skill Class
```python
from ai_stack.agents.shared import AgentSkill, SkillResult

class MySkill(AgentSkill):
    name = "my-skill"
    description = "My custom skill"
    version = "1.0.0"

    async def execute(self, **kwargs) -> SkillResult:
        # Use shared utilities
        logger = SkillLogger(self.name)
        cache = CacheManager()

        # Check cache first
        cached = await cache.get(f"{self.name}:{kwargs}")
        if cached:
            return SkillResult(success=True, data=cached)

        # Execute skill logic
        result = await self._do_work(**kwargs)

        # Cache result
        await cache.set(f"{self.name}:{kwargs}", result)

        return SkillResult(success=True, data=result)
```

### Using HTTP Client
```python
from ai_stack.agents.shared import HTTPClient

async def fetch_data(url: str) -> dict:
    client = HTTPClient()
    response = await client.with_retry(
        lambda: client.get(url),
        max_retries=3
    )
    return response.json()
```

---

## Development

This component is planned for **Phase 5** of the AI stack integration.

**Target Implementation:** v6.3.0 (Q3 2026)

---

## Dependencies

```txt
# Core
pydantic>=2.0.0
httpx>=0.27.0
tenacity>=8.0.0

# Database
sqlalchemy>=2.0.0
psycopg2-binary>=2.9.0
redis>=5.0.0
qdrant-client>=1.7.0

# Utilities
python-dotenv>=1.0.0
structlog>=24.0.0
```

---

## References

- [Agent Skills README](../README.md)
- [AIDB MCP Server](../../mcp-servers/aidb/README.md)
- [Agent Orchestrator](../orchestrator/README.md)

---

**Status:** Reserved for future implementation
**Last Updated:** 2025-12-12
