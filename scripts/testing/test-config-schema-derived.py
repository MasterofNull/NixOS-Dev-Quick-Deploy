#!/usr/bin/env python3
"""CONFIG_SCHEMA_REGISTRY is derived from the YAML registry and 1:1 with @register (N6, S1)."""
from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from contracts import config  # noqa: E402


def dangling_schema_refs(root: Path, exceptions: list[dict], today: str) -> list[str]:
    """Problems with `$schema` file references in config/*.json versus the dated exceptions."""
    import json

    found: dict[tuple[str, str], bool] = {}
    for f in sorted((root / "config").glob("*.json")):
        try:
            ref = json.loads(f.read_text(encoding="utf-8")).get("$schema")
        except (ValueError, AttributeError):
            continue
        if isinstance(ref, str) and ref.startswith("."):
            found[(f.relative_to(root).as_posix(), ref)] = not (f.parent / ref).exists()
    listed = {(e["path"], e["ref"]): e for e in exceptions}
    # Scope: the exceptions S1 records. Four other configs also carry a dangling `$schema`
    # (capability-lifecycle-registry, reasoning-profiles, route-aliases, tool-pins); they are
    # reported in the S1 evidence document, not gated here, until their owning slices register them.
    problems: list[str] = []
    for key, e in listed.items():
        if key not in found or not found[key]:
            problems.append(f"{key[0]}: reference_exception for {key[1]} is stale (reference gone or the file now exists); remove the row")
        if e["expiry"] < today:
            problems.append(f"{key[0]}: reference_exception for {key[1]} expired {e['expiry']}")
    return problems


def main() -> int:
    assert config.verify_derived() == [], "real tree must be 1:1"
    assert set(config.CONFIG_SCHEMA_REGISTRY) == set(config.declared_config_paths()), "keys must be derived from YAML"
    assert "config/switchboard-profiles.yaml" in config.registry()

    # A YAML row without a model, and a model without a YAML row, both fail.
    tmp = Path(tempfile.mkdtemp())
    (tmp / "config").mkdir()
    shutil.copy(ROOT / config.REGISTRY_YAML, tmp / config.REGISTRY_YAML)
    text = (tmp / config.REGISTRY_YAML).read_text()
    (tmp / "config/switchboard-profiles.yaml").write_text("x: 1\n")
    (tmp / config.REGISTRY_YAML).write_text(text.replace(", config_files: [config/switchboard-profiles.yaml]", ""))
    problems = config.verify_derived(tmp)
    assert any("no decision row lists it" in p for p in problems), problems
    (tmp / config.REGISTRY_YAML).write_text(text.replace("config/switchboard-profiles.yaml]", "config/switchboard-profiles.yaml, config/ghost.yaml]", 1))
    problems = config.verify_derived(tmp)
    assert any("ghost.yaml" in p and "no @register model" in p for p in problems), problems
    shutil.rmtree(tmp, ignore_errors=True)

    import datetime
    import yaml

    excs = yaml.safe_load((ROOT / config.REGISTRY_YAML).read_text(encoding="utf-8")).get("reference_exceptions") or []
    today = datetime.date.today().isoformat()
    assert dangling_schema_refs(ROOT, excs, today) == [], dangling_schema_refs(ROOT, excs, today)
    assert any("stale" in p for p in dangling_schema_refs(ROOT, excs + [{"path": "config/x.json", "ref": "./y.json", "expiry": "2099-01-01"}], today))
    assert any("expired" in p for p in dangling_schema_refs(ROOT, [dict(excs[0], expiry="2020-01-01")], today))
    print("test-config-schema-derived: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
