#!/usr/bin/env python3
"""Validate MAEAH JSON Schema/OpenAPI contract artifacts."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = ROOT / "config" / "schemas" / "maeah"
OPENAPI = ROOT / "docs" / "api" / "maeah-openapi.yaml"


def require(text: str, needle: str, message: str) -> None:
    if needle not in text:
        raise AssertionError(message)


def main() -> int:
    for name in ("model-entry.schema.json", "lifecycle-event.schema.json"):
        data = json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))
        if data.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
            raise AssertionError(f"{name} must use JSON Schema 2020-12")
        if not data.get("$id"):
            raise AssertionError(f"{name} missing $id")
    model_schema = json.loads((SCHEMA_DIR / "model-entry.schema.json").read_text(encoding="utf-8"))
    states = set(model_schema["properties"]["state"]["enum"])
    expected = {"available", "downloading", "downloaded", "verified", "warming", "candidate", "active", "retiring", "archived", "failed"}
    if not expected <= states:
        raise AssertionError("model-entry schema missing durable lifecycle states")

    openapi = OPENAPI.read_text(encoding="utf-8")
    require(openapi, 'openapi: "3.1.0"', "MAEAH OpenAPI must be 3.1")
    for path in (
        "/v1/responses",
        "/admin/v1/models",
        "/admin/v1/models/{model_id}",
        "/admin/v1/models/{model_id}/download",
        "/admin/v1/models/{model_id}/promote",
        "/admin/v1/models/{model_id}/rollback",
        "/admin/v1/models/{model_id}/reset",
        "/.well-known/agent.json",
        "/a2a/tasks/send",
    ):
        require(openapi, path, f"OpenAPI missing {path}")
    for operation in ("addAdminModel", "deleteAdminModel", "downloadAdminModel", "promoteAdminModel", "rollbackAdminModel", "resetAdminFailedModel"):
        require(openapi, operation, f"OpenAPI missing operation {operation}")
    require(openapi, "X-Dashboard-Internal", "OpenAPI missing dashboard internal auth scheme")
    require(openapi, "X-OpenAI-Responses-Compat", "OpenAPI missing Responses compatibility header")
    require(openapi, "model-entry.schema.json", "OpenAPI should reference model-entry schema")
    require(openapi, "lifecycle-event.schema.json", "OpenAPI should reference lifecycle-event schema")
    require(openapi, "UserModelCreateRequest", "OpenAPI missing user model create schema")
    require(openapi, "Built-in and active models are protected", "OpenAPI delete contract must document model protections")
    require(openapi, "status: { const: added }", "OpenAPI add model response must expose added status")
    require(openapi, "status: { const: deleted }", "OpenAPI delete model response must expose deleted status")

    print("PASS: MAEAH contract artifacts are present and internally consistent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
