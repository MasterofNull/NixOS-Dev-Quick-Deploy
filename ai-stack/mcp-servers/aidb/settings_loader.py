from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional
from urllib.parse import quote_plus

from shared.config_loader import load_config
from pydantic import BaseModel, Field


def _read_secret(path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    secret_path = Path(path)
    if not secret_path.exists():
        return None
    return secret_path.read_text(encoding="utf-8").strip()


def _parse_size(value: str) -> int:
    units = {"kb": 1024, "mb": 1024**2, "gb": 1024**3}
    value = value.strip().lower()
    if value.isdigit():
        return int(value)
    for suffix, multiplier in units.items():
        if value.endswith(suffix):
            number = float(value[: -len(suffix)].strip())
            return int(number * multiplier)
    raise ValueError(f"Unsupported size value: {value}")


class Settings(BaseModel):
    server_host: str = "0.0.0.0"
    server_port: int = 8791
    api_port: int = 8091
    worker_count: int = 1
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dimension: int = 384
    parallel_processing_enabled: bool = False
    parallel_simple_model: str = "GLM-4.5-Air-UD-Q4K-XL-GGUF"
    parallel_complex_model: str = "gpt-oss-20b-mxfp4-GGUF"
    parallel_diversity_mode: bool = False
    postgres_dsn: str
    redis_url: str
    postgres_pool_size: int = 5
    postgres_max_overflow: int = 10
    postgres_pool_timeout: int = 30
    postgres_pool_recycle: int = 1800
    postgres_pool_pre_ping: bool = True
    postgres_pool_use_lifo: bool = True
    redis_max_connections: int = 50
    redis_socket_timeout: int = 5
    redis_socket_connect_timeout: int = 5
    pgvector_hnsw_m: int = 16
    pgvector_hnsw_ef_construction: int = 64
    embedding_cache_enabled: bool = True
    embedding_cache_ttl: int = 86400
    vector_search_cache_ttl: int = 300
    llama_cpp_url: str = "http://localhost:8080"
    llama_cpp_models: List[str] = Field(default_factory=list)
    tool_schema_cache: Path = Field(default=Path(".mcp_cache/tool_schemas.json"))
    sandbox_enabled: bool = True
    sandbox_runner: str = "bubblewrap"
    sandbox_profile: Optional[Path] = None
    sandbox_timeout: int = 30
    sandbox_extra_args: List[str] = Field(default_factory=list)
    default_tool_mode: str = "minimal"
    full_tool_disclosure_requires_key: bool = True
    tool_cache_ttl: int = 3600
    log_level: str = "INFO"
    log_file: Path = Field(default=Path("/tmp/aidb-mcp.log"))
    log_max_bytes: int = 10 * 1024 * 1024
    log_backup_count: int = 5
    telemetry_enabled: bool = True
    telemetry_path: Path = Field(
        default=Path("~/.local/share/nixos-ai-stack/telemetry/aidb-events.jsonl").expanduser()
    )
    rate_limit_enabled: bool = False
    rate_limit_rpm: int = 60
    api_key: Optional[str] = None
    catalog_path: Path
    google_api_key: Optional[str] = None
    google_cse_id: Optional[str] = None


def load_settings(config_path: Optional[Path] = None) -> Settings:
    repo_root = Path(__file__).resolve().parents[1]
    default_config = repo_root / "config" / "config.yaml"
    cfg_path = config_path or Path(os.environ.get("AIDB_CONFIG", default_config))
    raw = load_config(Path(cfg_path))

    server_cfg = raw.get("server", {})
    db_cfg = raw.get("database", {})
    llm_cfg = raw.get("llm", {})
    parallel_cfg = llm_cfg.get("parallel_processing", {})
    tools_cfg = raw.get("tools", {})
    disclosure_cfg = tools_cfg.get("disclosure", {})
    logging_cfg = raw.get("logging", {})
    security_cfg = raw.get("security", {})
    rag_cfg = raw.get("rag", {})

    postgres_cfg = db_cfg.get("postgres", {})
    postgres_pool_cfg = postgres_cfg.get("pool", {})
    pg_password = (
        _read_secret(postgres_cfg.get("password_file"))
        or postgres_cfg.get("password", "")
        or os.environ.get("AIDB_POSTGRES_PASSWORD", "")
    )
    quoted_pw = quote_plus(pg_password) if pg_password else ""
    if quoted_pw:
        auth = f"{postgres_cfg.get('user','mcp')}:{quoted_pw}@"
    else:
        auth = f"{postgres_cfg.get('user','mcp')}@"
    postgres_dsn = (
        f"postgresql+psycopg://{auth}"
        f"{postgres_cfg.get('host','localhost')}:{postgres_cfg.get('port',5432)}/{postgres_cfg.get('database','mcp')}"
    )

    redis_cfg = db_cfg.get("redis", {})
    redis_pool_cfg = redis_cfg.get("pool", {})
    redis_password = (
        _read_secret(redis_cfg.get("password_file"))
        or redis_cfg.get("password", "")
        or os.environ.get("AIDB_REDIS_PASSWORD", "")
    )
    if redis_password:
        redis_auth = f":{quote_plus(redis_password)}@"
    else:
        redis_auth = ""
    redis_url = f"redis://{redis_auth}{redis_cfg.get('host','localhost')}:{redis_cfg.get('port',6379)}/{redis_cfg.get('db',0)}"

    llama_cpp_cfg = llm_cfg.get("llama_cpp") or llm_cfg.get("llama-cpp") or {}
    llama_cpp_url = os.environ.get("LLAMA_CPP_BASE_URL") or llama_cpp_cfg.get("host") or "http://localhost:8080"
    llama_cpp_models = llama_cpp_cfg.get("models", [])

    sandbox_cfg = tools_cfg.get("sandbox", {})
    cache_cfg = tools_cfg.get("cache", {})

    log_path = Path(logging_cfg.get("file", "/tmp/aidb-mcp.log"))
    log_path.parent.mkdir(parents=True, exist_ok=True)

    log_size = logging_cfg.get("max_size", "10MB")
    catalog_path = repo_root / "data" / "catalog" / "mcp_servers.json"
    websearch_cfg = raw.get("websearch", {})
    google_api_key = os.environ.get("GOOGLE_SEARCH_API_KEY") or websearch_cfg.get("google_api_key")
    google_cse_id = os.environ.get("GOOGLE_SEARCH_CX") or websearch_cfg.get("google_cse_id")

    api_key = (
        _read_secret(security_cfg.get("api_key_file"))
        or security_cfg.get("api_key")
        or os.environ.get("AIDB_API_KEY")
    )

    telemetry_cfg = raw.get("telemetry", {})
    telemetry_enabled = telemetry_cfg.get("enabled", True)
    telemetry_path = Path(
        os.environ.get("AIDB_TELEMETRY_PATH")
        or telemetry_cfg.get("path", "~/.local/share/nixos-ai-stack/telemetry/aidb-events.jsonl")
    ).expanduser()
    telemetry_path.parent.mkdir(parents=True, exist_ok=True)

    return Settings(
        server_host=server_cfg.get("host", "0.0.0.0"),
        server_port=server_cfg.get("port", 8791),
        api_port=server_cfg.get("api_port", 8091),
        worker_count=server_cfg.get("workers", 1),
        postgres_dsn=postgres_dsn,
        redis_url=redis_url,
        postgres_pool_size=int(postgres_pool_cfg.get("size", 5)),
        postgres_max_overflow=int(postgres_pool_cfg.get("max_overflow", 10)),
        postgres_pool_timeout=int(postgres_pool_cfg.get("timeout", 30)),
        postgres_pool_recycle=int(postgres_pool_cfg.get("recycle", 1800)),
        postgres_pool_pre_ping=bool(postgres_pool_cfg.get("pre_ping", True)),
        postgres_pool_use_lifo=bool(postgres_pool_cfg.get("use_lifo", True)),
        redis_max_connections=int(redis_pool_cfg.get("max_connections", 50)),
        redis_socket_timeout=int(redis_pool_cfg.get("socket_timeout", 5)),
        redis_socket_connect_timeout=int(redis_pool_cfg.get("socket_connect_timeout", 5)),
        llama_cpp_url=llama_cpp_url,
        llama_cpp_models=llama_cpp_models,
        sandbox_enabled=sandbox_cfg.get("enabled", True),
        sandbox_runner=sandbox_cfg.get("runner", "bubblewrap"),
        sandbox_profile=Path(sandbox_cfg["profile"]) if sandbox_cfg.get("profile") else None,
        sandbox_timeout=sandbox_cfg.get("timeout", 30),
        sandbox_extra_args=sandbox_cfg.get("extra_args", []),
        tool_schema_cache=Path(tools_cfg.get("schema_cache", ".mcp_cache/tool_schemas.json")),
        default_tool_mode=tools_cfg.get("discovery_mode", "minimal"),
        full_tool_disclosure_requires_key=disclosure_cfg.get("full_requires_api_key", True),
        tool_cache_ttl=cache_cfg.get("ttl", 3600),
        embedding_cache_enabled=bool(cache_cfg.get("enabled", True)),
        embedding_cache_ttl=int(cache_cfg.get("embeddings_ttl", 86400)),
        vector_search_cache_ttl=int(cache_cfg.get("vector_search_ttl", 300)),
        log_level=logging_cfg.get("level", "INFO").upper(),
        log_file=log_path,
        log_max_bytes=_parse_size(log_size),
        log_backup_count=logging_cfg.get("backup_count", 5),
        telemetry_enabled=telemetry_enabled,
        telemetry_path=telemetry_path,
        rate_limit_enabled=security_cfg.get("rate_limit", {}).get("enabled", False),
        rate_limit_rpm=security_cfg.get("rate_limit", {}).get("requests_per_minute", 60),
        api_key=api_key,
        catalog_path=catalog_path,
        embedding_model=rag_cfg.get("embedding_model", "sentence-transformers/all-MiniLM-L6-v2"),
        embedding_dimension=int(rag_cfg.get("embedding_dimension", 384)),
        pgvector_hnsw_m=int(rag_cfg.get("pgvector", {}).get("hnsw_m", 16)),
        pgvector_hnsw_ef_construction=int(rag_cfg.get("pgvector", {}).get("hnsw_ef_construction", 64)),
        parallel_processing_enabled=parallel_cfg.get("enabled", False),
        parallel_simple_model=parallel_cfg.get("simple_model", "GLM-4.5-Air-UD-Q4K-XL-GGUF"),
        parallel_complex_model=parallel_cfg.get("complex_model", "gpt-oss-20b-mxfp4-GGUF"),
        parallel_diversity_mode=parallel_cfg.get("diversity_mode", False),
        google_api_key=google_api_key,
        google_cse_id=google_cse_id,
    )
