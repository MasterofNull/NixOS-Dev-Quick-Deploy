"""Config schemas + the registry that maps config files to their models.

Register a config here and it is validated by scripts/ai/lib/config_loader.py
and gated in CI (tier0.d/check-config-contracts.sh). Unregistered configs are
untouched — adoption is opt-in, one file at a time.
"""

from __future__ import annotations

from typing import Callable

from pydantic import BaseModel

# path (repo-relative) -> zero-arg loader returning the pydantic model class.
# Lazy (callable) so importing this package never forces every schema module.
CONFIG_SCHEMA_REGISTRY: dict[str, Callable[[], type[BaseModel]]] = {}


def register(path: str) -> Callable[[type[BaseModel]], type[BaseModel]]:
    """Decorator: bind a repo-relative config path to its root schema model."""

    def _decorate(model: type[BaseModel]) -> type[BaseModel]:
        CONFIG_SCHEMA_REGISTRY[path] = lambda: model
        return model

    return _decorate


def _register_all() -> None:
    """Import schema modules so their @register decorators run. Idempotent."""
    from . import switchboard_profiles  # noqa: F401


def registry() -> dict[str, type[BaseModel]]:
    """Return the resolved {path: model} map (imports schema modules on demand)."""
    _register_all()
    return {path: factory() for path, factory in CONFIG_SCHEMA_REGISTRY.items()}
