#!/usr/bin/env python3
"""Regression checks for the bounded local surface scanner."""

from __future__ import annotations

import importlib.machinery
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "ai" / "aq-local-surface-scan"

loader = importlib.machinery.SourceFileLoader("local_surface_scan", str(SCRIPT))
module = importlib.util.module_from_spec(importlib.util.spec_from_loader("local_surface_scan", loader))
loader.exec_module(module)


def main() -> int:
    assert module._validate_url("http://127.0.0.1:8889/")[0] is True
    assert module._validate_url("http://localhost:8003/health")[0] is True
    assert module._validate_url("http://10.0.0.2/")[0] is True
    assert module._validate_url("http://192.168.1.1/")[0] is True
    assert module._validate_url("https://example.com/")[0] is False
    assert module._validate_url("file:///etc/passwd")[0] is False
    refused = module.scan_url("https://example.com/", timeout=0.1, max_bytes=1024)
    assert refused["status"] == "refused"
    assert "not loopback/private" in refused["reason"]
    assert module._extract_title("<html><title> Demo Site </title></html>") == "Demo Site"
    print("PASS: local surface scanner is bounded to local/private HTTP targets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
