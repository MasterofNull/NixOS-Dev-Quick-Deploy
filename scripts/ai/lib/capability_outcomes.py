"""Bounded, schema-backed reader for capability outcome catalog metadata."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError


MAX_OUTCOME_CATALOG_BYTES = 1_048_576
MAX_OUTCOMES = 256
REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_PATH = REPO_ROOT / "config" / "schemas" / "capability-gap-catalog.schema.json"


@lru_cache(maxsize=1)
def _validator() -> Draft202012Validator:
    try:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        return Draft202012Validator(schema)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, SchemaError, ValueError) as error:
        raise ValueError("catalog_schema_unavailable") from error


def validate_outcome_catalog(catalog: object) -> list[dict]:
    """Return validated outcomes or a stable, non-content-bearing error code."""
    errors = sorted(_validator().iter_errors(catalog), key=lambda item: list(item.absolute_path))
    if errors:
        raise ValueError("catalog_schema_invalid")
    if not isinstance(catalog, dict):
        raise ValueError("catalog_schema_invalid")
    outcomes = catalog.get("outcomes")
    if not isinstance(outcomes, list):
        raise ValueError("catalog_schema_invalid")
    if len(outcomes) > MAX_OUTCOMES:
        raise ValueError("catalog_outcome_limit")

    ids = [entry.get("id") for entry in outcomes if isinstance(entry, dict)]
    if len(ids) != len(set(ids)):
        raise ValueError("catalog_duplicate_outcome_id")
    return outcomes


def load_outcome_catalog(path: Path) -> dict:
    """Load at most 1 MiB, validate it, and expose no parsed error content."""
    with path.open("rb") as catalog_file:
        raw = catalog_file.read(MAX_OUTCOME_CATALOG_BYTES + 1)
    if len(raw) > MAX_OUTCOME_CATALOG_BYTES:
        raise ValueError("catalog_byte_limit")
    try:
        catalog = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as error:
        raise ValueError("catalog_invalid_json") from error
    validate_outcome_catalog(catalog)
    return catalog
