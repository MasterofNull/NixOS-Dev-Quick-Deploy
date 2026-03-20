#!/usr/bin/env python3
"""Regression for aq-report prompt registry loading without PyYAML."""

from __future__ import annotations

import builtins
import importlib.util
import os
from importlib.machinery import SourceFileLoader
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("AI_STRICT_ENV", "false")

AQ_REPORT_PATH = ROOT / "scripts" / "ai" / "aq-report"
AQ_REPORT_SPEC = importlib.util.spec_from_loader(
    "aq_report_prompt_registry_fallback",
    SourceFileLoader("aq_report_prompt_registry_fallback", str(AQ_REPORT_PATH)),
)
if AQ_REPORT_SPEC is None or AQ_REPORT_SPEC.loader is None:
    raise SystemExit("ERROR: unable to load aq-report module")
aq_report = importlib.util.module_from_spec(AQ_REPORT_SPEC)
AQ_REPORT_SPEC.loader.exec_module(aq_report)


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    original_import = builtins.__import__

    def blocked_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "yaml":
            raise ModuleNotFoundError("No module named 'yaml'")
        return original_import(name, globals, locals, fromlist, level)

    builtins.__import__ = blocked_import
    try:
        prompts = aq_report.read_prompt_registry()
    finally:
        builtins.__import__ = original_import

    assert_true(len(prompts) >= 3, "expected prompt registry fallback to recover prompt entries")
    first = prompts[0]
    assert_true(first.get("id") == "route_search_synthesis", "expected first fallback prompt id")
    assert_true(first.get("name") == "Route-Search Context Synthesis", "expected first fallback prompt name")
    assert_true(isinstance(first.get("mean_score"), float), "expected mean_score parsed as float")

    print("PASS: aq-report prompt registry fallback works without PyYAML")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
