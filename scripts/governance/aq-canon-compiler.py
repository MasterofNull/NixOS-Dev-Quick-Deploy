#!/usr/bin/env python3
"""aq-canon-compiler — read-only schema-to-docs/client compiler (B3-C1).

Parses frozen JSON/YAML schemas in config/schemas/ and compiles, per module
declared in a canon spec manifest (validated against
config/schemas/aq-canon-spec-v1.json):

  * a typed client interface  (<name>.client.ts)
  * API markdown              (<name>.api.md)
  * a dashboard view-model stub (<name>.viewmodel.js)

Invariants (Foundation B3 authorization, Section 3):
  1. Non-authoritative — output is advisory/documentation only. Nothing here
     is read back by any runtime service as execution authority.
  2. Pure determinism — the same spec + schema bytes always produce
     byte-for-byte identical output. Object keys are rendered in sorted
     order; no timestamps, PIDs, hostnames, or set/dict-iteration-order
     dependent content ever appear in generated artifacts.
  3. No network or filesystem mutation beyond explicitly designated build
     target paths — the compiler is pure in-memory unless --out-dir is
     given, and writes only stdout by default.
  4. Fail-closed validation — a malformed spec or a malformed target schema
     causes a non-zero exit with a schema validation error message; nothing
     partial is ever written.

Usage:
    aq-canon-compiler.py --spec <canon-spec.json>              # prints JSON bundle to stdout
    aq-canon-compiler.py --spec <canon-spec.json> --out-dir DIR # writes designated build target files
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, SchemaError

REPO = Path(__file__).resolve().parents[2]
META_SCHEMA_PATH = REPO / "config/schemas/aq-canon-spec-v1.json"


class CanonCompilerError(Exception):
    """Fail-closed error: malformed spec, malformed schema, or missing input."""


# --------------------------------------------------------------------------
# Loading + fail-closed validation
# --------------------------------------------------------------------------

def _load_json(path: Path) -> Any:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CanonCompilerError(f"cannot read {path}: {exc}") from exc
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CanonCompilerError(f"invalid JSON in {path}: {exc}") from exc


def _load_schema_document(path: Path) -> Any:
    """Load a target schema. JSON is read directly; YAML requires PyYAML."""
    if path.suffix in (".yaml", ".yml"):
        try:
            import yaml
        except ImportError as exc:
            raise CanonCompilerError(
                f"cannot compile {path}: PyYAML not available for YAML schema input"
            ) from exc
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise CanonCompilerError(f"cannot read {path}: {exc}") from exc
        try:
            return yaml.safe_load(raw)
        except yaml.YAMLError as exc:
            raise CanonCompilerError(f"invalid YAML in {path}: {exc}") from exc
    return _load_json(path)


def load_and_validate_spec(spec_path: Path, meta_schema_path: Path = META_SCHEMA_PATH) -> dict:
    """Load the canon spec manifest and validate it against aq-canon-spec-v1.json.

    Fail-closed: any structural or schema violation raises CanonCompilerError.
    """
    meta_schema = _load_json(meta_schema_path)
    try:
        Draft202012Validator.check_schema(meta_schema)
    except SchemaError as exc:
        raise CanonCompilerError(f"meta-schema itself is invalid: {exc}") from exc

    spec = _load_json(spec_path)
    validator = Draft202012Validator(meta_schema)
    errors = sorted(validator.iter_errors(spec), key=lambda e: list(e.path))
    if errors:
        details = "; ".join(f"{list(e.path)}: {e.message}" for e in errors)
        raise CanonCompilerError(f"canon spec {spec_path} failed schema validation: {details}")
    return spec


def load_and_validate_target_schema(schema_path: Path) -> dict:
    """Load a referenced target schema and confirm it is a valid Draft 2020-12 schema."""
    if not schema_path.exists():
        raise CanonCompilerError(f"target schema not found: {schema_path}")
    document = _load_schema_document(schema_path)
    if not isinstance(document, dict):
        raise CanonCompilerError(f"target schema {schema_path} is not a JSON object")
    try:
        Draft202012Validator.check_schema(document)
    except SchemaError as exc:
        raise CanonCompilerError(f"target schema {schema_path} is not a valid Draft 2020-12 schema: {exc}") from exc
    return document


# --------------------------------------------------------------------------
# Deterministic rendering — every collection is walked in sorted-key order.
# --------------------------------------------------------------------------

def _sorted_items(mapping: dict) -> list[tuple[str, Any]]:
    return sorted(mapping.items(), key=lambda kv: kv[0])


def _ts_type(prop: dict) -> str:
    if "const" in prop:
        return json.dumps(prop["const"], sort_keys=True)
    if "enum" in prop:
        return " | ".join(json.dumps(v, sort_keys=True) for v in prop["enum"])
    raw_type = prop.get("type")
    types = raw_type if isinstance(raw_type, list) else [raw_type] if raw_type is not None else []
    if not types:
        return "unknown"
    rendered = [_ts_type_scalar(t, prop) for t in sorted(types, key=lambda t: str(t))]
    return " | ".join(rendered)


def _ts_type_scalar(t: str, prop: dict) -> str:
    if t == "string":
        return "string"
    if t in ("integer", "number"):
        return "number"
    if t == "boolean":
        return "boolean"
    if t == "null":
        return "null"
    if t == "array":
        items = prop.get("items", {})
        return f"Array<{_ts_type(items)}>"
    if t == "object":
        return _ts_object_literal(prop)
    return "unknown"


def _ts_object_literal(schema: dict) -> str:
    props = schema.get("properties", {})
    required = set(schema.get("required", []))
    fields = []
    for key, prop in _sorted_items(props):
        optional = "" if key in required else "?"
        fields.append(f"{key}{optional}: {_ts_type(prop)}")
    return "{ " + "; ".join(fields) + " }" if fields else "Record<string, unknown>"


def render_client_interface(name: str, schema: dict) -> str:
    pascal = "".join(part.capitalize() for part in name.split("_"))
    props = schema.get("properties", {})
    required = set(schema.get("required", []))
    lines = [
        f"// GENERATED by aq-canon-compiler.py — do not hand-edit. Source: {schema.get('$id', name)}",
        f"export interface {pascal} {{",
    ]
    for key, prop in _sorted_items(props):
        optional = "" if key in required else "?"
        lines.append(f"  {key}{optional}: {_ts_type(prop)};")
    lines.append("}")
    return "\n".join(lines) + "\n"


def render_api_markdown(name: str, schema: dict) -> str:
    props = schema.get("properties", {})
    required = set(schema.get("required", []))
    lines = [
        f"# {name}",
        "",
        f"GENERATED by aq-canon-compiler.py — do not hand-edit.",
        "",
        f"Source schema: `{schema.get('$id', name)}`",
        "",
        "| Field | Type | Required |",
        "|---|---|---|",
    ]
    for key, prop in _sorted_items(props):
        lines.append(f"| `{key}` | `{_ts_type(prop)}` | {'yes' if key in required else 'no'} |")
    return "\n".join(lines) + "\n"


def render_dashboard_viewmodel(name: str, schema: dict) -> str:
    props = schema.get("properties", {})
    required = sorted(schema.get("required", []))
    fields = []
    for key, prop in _sorted_items(props):
        fields.append({"key": key, "type": _ts_type(prop), "required": key in required})
    viewmodel = {"name": name, "fields": fields, "required": required}
    body = json.dumps(viewmodel, indent=2, sort_keys=True)
    return (
        f"// GENERATED by aq-canon-compiler.py — do not hand-edit. Source: {schema.get('$id', name)}\n"
        f"export const {name}ViewModel = {body};\n"
    )


# --------------------------------------------------------------------------
# Compilation
# --------------------------------------------------------------------------

def compile_module(module: dict, repo_root: Path = REPO) -> dict:
    name = module["name"]
    schema_path = repo_root / module["schema_path"]
    schema = load_and_validate_target_schema(schema_path)
    return {
        "name": name,
        "schema_path": module["schema_path"],
        "client_interface": render_client_interface(name, schema),
        "api_markdown": render_api_markdown(name, schema),
        "dashboard_viewmodel": render_dashboard_viewmodel(name, schema),
    }


def compile_spec(spec: dict, repo_root: Path = REPO) -> dict:
    modules = sorted(spec["modules"], key=lambda m: m["name"])
    compiled = [compile_module(module, repo_root) for module in modules]
    return {"spec_version": spec["spec_version"], "modules": compiled}


def render_bundle_json(bundle: dict) -> str:
    return json.dumps(bundle, indent=2, sort_keys=True) + "\n"


def write_bundle(bundle: dict, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for module in bundle["modules"]:
        name = module["name"]
        (out_dir / f"{name}.client.ts").write_text(module["client_interface"], encoding="utf-8")
        (out_dir / f"{name}.api.md").write_text(module["api_markdown"], encoding="utf-8")
        (out_dir / f"{name}.viewmodel.js").write_text(module["dashboard_viewmodel"], encoding="utf-8")


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", required=True, help="Path to a canon spec manifest (validated against aq-canon-spec-v1.json)")
    parser.add_argument("--meta-schema", default=str(META_SCHEMA_PATH), help="Path to the canon spec meta-schema (default: config/schemas/aq-canon-spec-v1.json)")
    parser.add_argument("--out-dir", default=None, help="Designated build target directory; default writes a JSON bundle to stdout only")
    parser.add_argument("--repo-root", default=str(REPO), help="Root that schema_path entries resolve against (default: this repo's root)")
    args = parser.parse_args(argv)

    try:
        spec = load_and_validate_spec(Path(args.spec), Path(args.meta_schema))
        bundle = compile_spec(spec, repo_root=Path(args.repo_root))
    except CanonCompilerError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.out_dir:
        write_bundle(bundle, Path(args.out_dir))
        print(f"OK: compiled {len(bundle['modules'])} module(s) to {args.out_dir}")
    else:
        sys.stdout.write(render_bundle_json(bundle))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
