#!/usr/bin/env python3
"""Regression checks for local model catalog/profile freshness telemetry."""

from __future__ import annotations

import datetime as dt
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROFILE = ROOT / "config" / "model-profile.json"
CATALOG = ROOT / "ai-stack" / "mcp-servers" / "shared" / "model_catalog.py"
MODELS_ROUTE = ROOT / "dashboard" / "backend" / "api" / "routes" / "models.py"
DASHBOARD_JS = ROOT / "assets" / "dashboard.js"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def parse_ts(value: str) -> dt.datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return dt.datetime.fromisoformat(value).astimezone(dt.timezone.utc)


def age_days(value: str) -> float:
    return (dt.datetime.now(dt.timezone.utc) - parse_ts(value)).total_seconds() / 86400


def main() -> int:
    profile = json.loads(PROFILE.read_text(encoding="utf-8"))
    meta = profile.get("_meta", {})
    max_age = int(profile.get("freshness_max_age_days", 0))

    assert_true(max_age >= 30, "model profile must declare a realistic freshness window")
    assert_true(profile.get("model_id"), "model_id is required")
    assert_true(profile.get("probe_model_id") == profile.get("model_id"), "probe_model_id must match model_id")
    assert_true(profile.get("model_path"), "model_path is required")
    assert_true(profile.get("probed_at"), "probed_at is required")
    assert_true(meta.get("reviewed_at"), "_meta.reviewed_at is required")
    assert_true(age_days(meta["reviewed_at"]) <= max_age, "model profile review is stale")
    assert_true(age_days(profile["probed_at"]) <= max_age, "model probe is stale")

    spec = importlib.util.spec_from_file_location("model_catalog", CATALOG)
    assert_true(spec and spec.loader, "model_catalog import spec should load")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    catalog_meta = getattr(module, "CATALOG_METADATA", {})
    assert_true(catalog_meta.get("catalog_version"), "catalog metadata must expose catalog_version")
    assert_true(catalog_meta.get("catalog_reviewed_at"), "catalog metadata must expose catalog_reviewed_at")
    assert_true(age_days(catalog_meta["catalog_reviewed_at"]) <= int(catalog_meta.get("freshness_max_age_days", 0)), "model catalog review is stale")

    route_text = MODELS_ROUTE.read_text(encoding="utf-8")
    assert_true("freshness" in route_text and "_model_freshness" in route_text, "/api/models must expose freshness payload")
    assert_true("active_model_path_state" in route_text, "/api/models must distinguish restricted and missing active model paths")
    dash_text = DASHBOARD_JS.read_text(encoding="utf-8")
    assert_true("mlFreshness" in dash_text and "freshness" in dash_text, "dashboard Model Lifecycle must render freshness")

    print("PASS: model catalog/profile freshness telemetry is wired")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
