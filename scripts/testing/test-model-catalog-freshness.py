#!/usr/bin/env python3
"""Regression checks for local model catalog/profile freshness telemetry."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
PROFILE = ROOT / "config" / "model-profile.json"
CATALOG = ROOT / "config" / "model-catalog.yaml"
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
    assert_true(
        profile.get("throughput_source") == "live_probe",
        "model throughput must come from a successful live probe, not a fallback",
    )
    assert_true(meta.get("reviewed_at"), "_meta.reviewed_at is required")
    assert_true(age_days(meta["reviewed_at"]) <= max_age, "model profile review is stale")
    assert_true(age_days(profile["probed_at"]) <= max_age, "model probe is stale")

    catalog = yaml.safe_load(CATALOG.read_text(encoding="utf-8")) or {}
    catalog_meta = catalog.get("_meta", {})
    assert_true(catalog_meta.get("version"), "runtime catalog metadata must expose version")
    assert_true(catalog_meta.get("last_updated"), "runtime catalog metadata must expose last_updated")
    assert_true(
        age_days(catalog_meta["last_updated"])
        <= int(catalog_meta.get("freshness_max_age_days", 0)),
        "runtime model catalog review is stale",
    )
    entries = {}
    for section in ("chat_models", "embedding_models"):
        entries.update(catalog.get(section, {}))
    declared_files = {entry.get("file") for entry in entries.values() if isinstance(entry, dict)}
    model_path = Path(profile["model_path"])
    assert_true(model_path.exists(), "active model path must exist")
    active_file = model_path.resolve(strict=True).name
    assert_true(active_file in declared_files, "active model target must be declared in runtime catalog")

    route_text = MODELS_ROUTE.read_text(encoding="utf-8")
    assert_true("freshness" in route_text and "_model_freshness" in route_text, "/api/models must expose freshness payload")
    assert_true("active_model_path_state" in route_text, "/api/models must distinguish restricted and missing active model paths")
    assert_true("active_model_catalogued" in route_text, "/api/models must expose active model catalog parity")
    dash_text = DASHBOARD_JS.read_text(encoding="utf-8")
    assert_true("mlFreshness" in dash_text and "freshness" in dash_text, "dashboard Model Lifecycle must render freshness")

    print("PASS: model catalog/profile freshness telemetry is wired")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
