"""Config schemas + the registry that maps config files to their models.

CONFIG_SCHEMA_REGISTRY is DERIVED from the ownership registry: the set of config paths is the union
of `config_files` over the decision rows of config/system-state-authorities.yaml, so a config
cannot be schema-bound without an owner row (control-plane consolidation S1, D-R5-3). This module
holds no ownership assertions; `@register(path)` only supplies the pydantic model for a path.
verify_derived() is the 1:1 gate (tier0.d/check-config-contracts.sh, test-config-schema-derived.py):
a registered model with no YAML row, or a YAML config path with no model, fails.
Unregistered configs are untouched.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from pydantic import BaseModel

REGISTRY_YAML = "config/system-state-authorities.yaml"

# path (repo-relative) -> model class, filled by @register when a schema module is imported.
_MODELS: dict[str, type[BaseModel]] = {}


def declared_config_paths(root: Path | None = None) -> list[str]:
    """Config paths declared by `config_files` on the registry's decision rows, sorted."""
    import yaml

    base = root or Path(__file__).resolve().parents[2]
    doc = yaml.safe_load((base / REGISTRY_YAML).read_text(encoding="utf-8")) or {}
    paths: set[str] = set()
    for row in doc.get("decisions") or []:
        paths.update(row.get("config_files") or [])
    return sorted(paths)


def _loader(path: str) -> Callable[[], type[BaseModel]]:
    def load() -> type[BaseModel]:
        _register_all()
        return _MODELS[path]

    return load


def _derive() -> dict[str, Callable[[], type[BaseModel]]]:
    # Lazy (callable) so importing this package never forces every schema module.
    try:
        return {p: _loader(p) for p in declared_config_paths()}
    except Exception:  # registry unreadable: verify_derived() reports it, nothing is silently bound
        return {}


CONFIG_SCHEMA_REGISTRY: dict[str, Callable[[], type[BaseModel]]] = _derive()


def register(path: str) -> Callable[[type[BaseModel]], type[BaseModel]]:
    """Decorator: supply the root schema model for a config path declared in the YAML registry."""

    def _decorate(model: type[BaseModel]) -> type[BaseModel]:
        _MODELS[path] = model
        return model

    return _decorate


def _register_all() -> None:
    """Import schema modules so their @register decorators run. Idempotent."""
    from . import switchboard_profiles  # noqa: F401


def registry() -> dict[str, type[BaseModel]]:
    """Return the resolved {path: model} map (imports schema modules on demand)."""
    return {path: factory() for path, factory in CONFIG_SCHEMA_REGISTRY.items()}


def verify_derived(root: Path | None = None) -> list[str]:
    """1:1 check between @register models and the YAML `config_files` rows; [] when they agree."""
    _register_all()
    declared = set(declared_config_paths(root))
    models = set(_MODELS)
    problems = [f"{p}: model registered but no decision row lists it in config_files" for p in sorted(models - declared)]
    problems += [f"{p}: listed in config_files but no @register model exists" for p in sorted(declared - models)]
    base = root or Path(__file__).resolve().parents[2]
    problems += [f"{p}: listed in config_files but the file does not exist" for p in sorted(declared) if not (base / p).exists()]
    return problems
