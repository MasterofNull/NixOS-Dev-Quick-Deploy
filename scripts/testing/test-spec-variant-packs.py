#!/usr/bin/env python3
"""Regression coverage for derived Markdown/HTML/visual HTML spec packs."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "ai" / "lib"))
os.environ.setdefault("AI_STRICT_ENV", "false")

import spec_variant_packs as packs  # noqa: E402

SCHEMA = ROOT / "config" / "schemas" / "maeah" / "spec-variant-pack.schema.json"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def test_schema_contract() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert_true(schema["properties"]["schema_version"]["const"] == packs.SCHEMA_VERSION, "schema version mismatch")
    schema_variants = set(schema["properties"]["variants"]["items"]["properties"]["variant"]["enum"])
    assert_true(schema_variants == set(packs.VARIANTS), "variant enum mismatch")


def test_pack_generation_and_drift_detection() -> None:
    with tempfile.TemporaryDirectory(prefix="spec-variant-packs-") as tmp_dir:
        tmp = Path(tmp_dir)
        canonical = tmp / "slice.md"
        canonical.write_text("# Slice\n\nBuild the dashboard card.\n", encoding="utf-8")
        out_dir = tmp / "derived"
        pack = packs.build_spec_variant_pack(
            canonical,
            out_dir,
            mockup_assets=["mockups/card.png"],
        )
        packs.validate_spec_variant_pack(pack, current_canonical_hash=packs.sha256_file(canonical))
        assert_true({item["variant"] for item in pack["variants"]} == set(packs.VARIANTS), "expected all variants")
        assert_true(all(item["canonical"] is False for item in pack["variants"]), "derived variants must not be canonical")
        assert_true(all("not canonical" in item["label"].lower() for item in pack["variants"]), "labels must prevent SSOT drift")
        for item in pack["variants"]:
            derived_path = Path(item["derived_path"])
            assert_true(derived_path.exists(), f"{item['variant']} derived artifact should exist")
            assert_true(item["canonical_hash"] == pack["canonical_hash"], f"{item['variant']} hash should link source")
        visual = next(item for item in pack["variants"] if item["variant"] == "visual_html")
        assert_true(visual["mockup_assets"] == ["mockups/card.png"], "visual variant should retain mockup provenance")

        canonical.write_text("# Slice\n\nChanged requirement.\n", encoding="utf-8")
        try:
            packs.validate_spec_variant_pack(pack, current_canonical_hash=packs.sha256_file(canonical))
        except ValueError as exc:
            assert_true("drift" in str(exc), "expected source hash drift error")
        else:
            raise AssertionError("stale derived pack should fail drift validation")


def test_unknown_variant_rejected() -> None:
    with tempfile.TemporaryDirectory(prefix="spec-variant-packs-") as tmp_dir:
        canonical = Path(tmp_dir) / "slice.md"
        canonical.write_text("# Slice\n", encoding="utf-8")
        try:
            packs.build_spec_variant_pack(canonical, Path(tmp_dir) / "out", variants=("markdown", "pdf"))
        except ValueError as exc:
            assert_true("unknown variants" in str(exc), "expected unknown variant error")
        else:
            raise AssertionError("unknown spec variant should fail")


def main() -> int:
    test_schema_contract()
    test_pack_generation_and_drift_detection()
    test_unknown_variant_rejected()
    print("PASS: spec variant packs preserve Markdown SSOT and detect derived artifact drift")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
