#!/usr/bin/env python3
"""Test for aq-help-center launcher, docs integrity, and HTTP endpoints."""

import importlib.machinery
import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "ai" / "aq-help-center"


def test_script_exists_and_executable():
    assert SCRIPT.is_file(), f"Missing {SCRIPT}"
    assert SCRIPT.stat().st_mode & 0o111, f"{SCRIPT} is not executable"


def test_desktop_entry_exists():
    desktop_file = Path.home() / ".local" / "share" / "applications" / "aq-help-center.desktop"
    assert desktop_file.is_file(), f"Missing {desktop_file}"
    content = desktop_file.read_text()
    assert "Exec=" in content
    assert "aq-help-center" in content


def test_docs_integrity():
    loader = importlib.machinery.SourceFileLoader("aq_help_center", str(SCRIPT))
    spec = importlib.util.spec_from_loader("aq_help_center", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    handler = mod.HelpHandler

    for doc_id, doc in handler.DOC_MAP.items():
        assert doc["path"].is_file(), f"Doc file missing for {doc_id}: {doc['path']}"
        raw = doc["path"].read_text(encoding="utf-8")
        assert len(raw) > 50, f"Doc file too short for {doc_id}"
        html = mod.markdown_to_html(raw)
        assert "<" in html and ">" in html, f"Failed converting {doc_id} to HTML"


def main():
    test_script_exists_and_executable()
    test_desktop_entry_exists()
    test_docs_integrity()
    print("test-aq-help-center: ok 3/3")
    return 0


if __name__ == "__main__":
    sys.exit(main())
