from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import os
from pydantic import BaseModel

from .config_loader import load_config


class EmbeddingsSettings(BaseModel):
    model: str = "nomic-ai/nomic-embed-text-v1.5"
    port: int = 8081
    max_input_length: int = 10000
    max_batch_size: int = 32
    request_timeout: int = 30
    model_load_retries: int = 3
    model_load_retry_delay: int = 5
    batch_max_size: int = 64
    batch_max_latency_ms: int = 25
    batch_queue_max: int = 1024
    api_key_file: Optional[str] = None

    @classmethod
    def load(cls, env_var: str = "EMBEDDINGS_CONFIG") -> "EmbeddingsSettings":
        config_path = Path(os.getenv(env_var, "/app/config/config.yaml"))
        raw = load_config(config_path)
        embeddings_cfg: Dict[str, Any] = dict(raw.get("embeddings", {}) or {})
        security_cfg = raw.get("security", {}) or {}

        batch_cfg = embeddings_cfg.pop("batch", {}) or {}
        embeddings_cfg.setdefault("batch_max_size", batch_cfg.get("max_size", cls().batch_max_size))
        embeddings_cfg.setdefault(
            "batch_max_latency_ms", batch_cfg.get("max_latency_ms", cls().batch_max_latency_ms)
        )
        embeddings_cfg.setdefault("batch_queue_max", batch_cfg.get("queue_max", cls().batch_queue_max))
        embeddings_cfg.setdefault("api_key_file", security_cfg.get("api_key_file"))
        return cls(**embeddings_cfg)


class HybridSettings(BaseModel):
    server_port: int = 8092
    qdrant_url: str = "http://localhost:6333"
    qdrant_hnsw_m: int = 16
    qdrant_hnsw_ef_construct: int = 64
    qdrant_hnsw_full_scan_threshold: int = 10000
    llama_cpp_url: str = "http://localhost:8080"
    embedding_service_url: str = "http://localhost:8081"
    embedding_model: str = "nomic-ai/nomic-embed-text-v1.5"
    embedding_dimensions: int = 768
    local_confidence_threshold: float = 0.7
    high_value_threshold: float = 0.7
    pattern_extraction_enabled: bool = True
    api_key_file: Optional[str] = None
    telemetry_path: Optional[str] = None
    finetune_data_path: Optional[str] = None

    @classmethod
    def load(cls, env_var: str = "HYBRID_CONFIG") -> "HybridSettings":
        config_path = Path(os.getenv(env_var, "/app/config/config.yaml"))
        raw = load_config(config_path)
        hybrid_cfg: Dict[str, Any] = dict(raw.get("hybrid", {}) or {})
        security_cfg = raw.get("security", {}) or {}

        qdrant_cfg = hybrid_cfg.pop("qdrant_hnsw", {}) or {}
        hybrid_cfg.setdefault("qdrant_hnsw_m", qdrant_cfg.get("m", cls().qdrant_hnsw_m))
        hybrid_cfg.setdefault(
            "qdrant_hnsw_ef_construct",
            qdrant_cfg.get("ef_construct", cls().qdrant_hnsw_ef_construct),
        )
        hybrid_cfg.setdefault(
            "qdrant_hnsw_full_scan_threshold",
            qdrant_cfg.get("full_scan_threshold", cls().qdrant_hnsw_full_scan_threshold),
        )
        hybrid_cfg.setdefault("api_key_file", security_cfg.get("api_key_file"))
        return cls(**hybrid_cfg)
