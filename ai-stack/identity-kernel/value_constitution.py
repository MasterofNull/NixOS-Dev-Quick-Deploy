"""
Value Constitution — Phase 16.2

Loads a user-editable YAML value hierarchy and exposes it for runtime use.
Fails hard on missing or malformed YAML (startup gate).

Config path: IDENTITY_VALUE_CONSTITUTION env var or explicit path argument.
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger("identity-kernel")


class ValueConstitution:
    """
    Load and validate a value hierarchy from YAML.

    >>> vc = ValueConstitution("config/identity-values.yaml")
    >>> weights = vc.get_active_weights()   # {"reciprocity": 1.0, ...}
    """

    def __init__(self, path: str = "") -> None:
        resolved = path or os.environ.get(
            "IDENTITY_VALUE_CONSTITUTION",
            "config/identity-values.yaml",
        )
        self._path = Path(resolved)
        self._values: List[Dict[str, Any]] = []
        self._load()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load(self) -> None:
        if not self._path.exists():
            raise FileNotFoundError(
                f"value_constitution: config file not found: {self._path}"
            )

        try:
            import yaml  # type: ignore
        except ImportError as exc:
            raise ImportError(
                "value_constitution: PyYAML is required (pip install pyyaml)"
            ) from exc

        try:
            raw = self._path.read_text(encoding="utf-8")
            data = yaml.safe_load(raw)
        except Exception as exc:
            raise ValueError(
                f"value_constitution: failed to parse YAML from {self._path}: {exc}"
            ) from exc

        if not isinstance(data, dict) or "values" not in data:
            raise ValueError(
                f"value_constitution: YAML must have top-level 'values' list in {self._path}"
            )

        values_raw = data["values"]
        if not isinstance(values_raw, list) or len(values_raw) == 0:
            raise ValueError(
                f"value_constitution: 'values' must be a non-empty list in {self._path}"
            )

        validated: List[Dict[str, Any]] = []
        for i, item in enumerate(values_raw):
            if not isinstance(item, dict):
                raise ValueError(
                    f"value_constitution: values[{i}] must be a dict, got {type(item)}"
                )
            name = item.get("name", "").strip()
            if not name:
                raise ValueError(
                    f"value_constitution: values[{i}] missing 'name' field"
                )
            try:
                weight = float(item.get("weight", 1.0))
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"value_constitution: values[{i}].weight must be numeric: {exc}"
                ) from exc
            validated.append(
                {
                    "name": name,
                    "weight": weight,
                    "description": str(item.get("description", "")),
                }
            )

        self._values = validated
        logger.info(
            "value_constitution: loaded %d values from %s",
            len(self._values),
            self._path,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_values(self) -> List[Dict[str, Any]]:
        """Return ordered list of validated value dicts."""
        return list(self._values)

    def get_active_weights(self) -> Dict[str, float]:
        """Return {name: weight} for all values."""
        return {v["name"]: v["weight"] for v in self._values}
