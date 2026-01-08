from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import os
import yaml


def _load_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    content = path.read_text(encoding="utf-8")
    return yaml.safe_load(content) or {}


def _merge_dicts(base: Dict[str, Any], overlay: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(base)
    for key, value in overlay.items():
        if (
            key in merged
            and isinstance(merged[key], dict)
            and isinstance(value, dict)
        ):
            merged[key] = _merge_dicts(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config(base_path: Path, env: Optional[str] = None) -> Dict[str, Any]:
    config = _load_yaml(base_path)
    env_name = env or os.getenv("STACK_ENV", "").strip()
    if not env_name:
        return config
    env_path = base_path.with_name(f"{base_path.stem}.{env_name}{base_path.suffix}")
    overlay = _load_yaml(env_path)
    return _merge_dicts(config, overlay)
