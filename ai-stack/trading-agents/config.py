"""
Trading agents configuration.
Adapted from tauricresearch/tradingagents for local llama.cpp (Qwen3.6-35B).

All service URLs are read from environment variables — never hardcoded.
"""
from __future__ import annotations

import os
from pathlib import Path


def get_config() -> dict:
    home = Path.home()
    data_dir = home / ".tradingagents"

    return {
        # Storage
        "results_dir": str(data_dir / "results"),
        "data_cache_dir": str(data_dir / "data_cache"),
        "memory_dir": str(data_dir / "memory"),

        # Local LLM — reads from env vars set by NixOS service
        "llm_provider": os.getenv("TRADING_LLM_PROVIDER", "openai"),
        "llm_base_url": os.getenv("LLAMA_BASE_URL", "http://127.0.0.1:8080") + "/v1",
        "llm_api_key": os.getenv("LLAMA_API_KEY", "local"),

        # Model routing: deep reasoning vs. quick ops
        "deep_think_llm": os.getenv("TRADING_DEEP_MODEL", "qwen3.6-35b"),
        "quick_think_llm": os.getenv("TRADING_QUICK_MODEL", "qwen3.6-35b"),

        # Debate rounds
        "max_debate_rounds": int(os.getenv("TRADING_MAX_DEBATE_ROUNDS", "1")),
        "max_risk_discuss_rounds": int(os.getenv("TRADING_MAX_RISK_ROUNDS", "1")),

        # Memory
        "max_memory_items": int(os.getenv("TRADING_MAX_MEMORY_ITEMS", "100")),
        "prune_resolved_memory": os.getenv("TRADING_PRUNE_MEMORY", "true").lower() == "true",

        # Checkpointing
        "enable_checkpoints": os.getenv("TRADING_ENABLE_CHECKPOINTS", "false").lower() == "true",
        "checkpoint_dir": str(data_dir / "checkpoints"),

        # Data vendors (Alpha Vantage key must be set externally)
        "alpha_vantage_key": os.getenv("ALPHA_VANTAGE_API_KEY", ""),
        "data_vendor": os.getenv("TRADING_DATA_VENDOR", "yfinance"),  # yfinance | alpha_vantage

        # AIDB integration for knowledge retrieval
        "aidb_url": os.getenv("AIDB_URL", "http://127.0.0.1:8002"),
        "aidb_key_file": os.getenv("AIDB_KEY_FILE", "/run/secrets/aidb_api_key"),

        # Analyst team configuration
        "analyst_types": os.getenv(
            "TRADING_ANALYST_TYPES", "market,fundamentals,news,sentiment"
        ).split(","),

        # Output
        "output_language": "English",
        "log_dir": str(data_dir / "logs"),
    }
