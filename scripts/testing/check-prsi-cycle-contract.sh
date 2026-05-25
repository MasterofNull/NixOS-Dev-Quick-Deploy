#!/usr/bin/env bash
set -euo pipefail

# Validate PRSI cycle artifact contract (Phase 7.1 gate).
# - Confirms schema files exist and parse.
# - Validates example artifacts against schemas.
# - Verifies runtime PRSI policy references required artifact names.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCHEMA_DIR="${ROOT_DIR}/config/schemas/prsi"
EXAMPLE_DIR="${ROOT_DIR}/data/prsi-artifacts/examples"
POLICY_FILE="${ROOT_DIR}/config/runtime-prsi-policy.json"

python3 - "$SCHEMA_DIR" "$EXAMPLE_DIR" "$POLICY_FILE" <<'PY'
import json
import sys
from pathlib import Path

schema_dir = Path(sys.argv[1])
example_dir = Path(sys.argv[2])
policy_file = Path(sys.argv[3])

required_schema_map = {
    "cycle_plan.json": "cycle-plan.schema.json",
    "validation_report.json": "validation-report.schema.json",
    "cycle_outcome.json": "cycle-outcome.schema.json",
}

expected_non_json_artifacts = ["patch.diff", "rollback_notes.md"]

class ValidationError(Exception):
    pass

def load_json(path: Path):
    if not path.exists():
        raise ValidationError(f"missing file: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValidationError(f"invalid JSON in {path}: {exc}") from exc

def type_ok(value, schema_type):
    if isinstance(schema_type, list):
        return any(type_ok(value, t) for t in schema_type)
    if schema_type == "object":
        return isinstance(value, dict)
    if schema_type == "array":
        return isinstance(value, list)
    if schema_type == "string":
        return isinstance(value, str)
    if schema_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if schema_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if schema_type == "boolean":
        return isinstance(value, bool)
    return True

def validate_instance(instance, schema, path="$"):
    st = schema.get("type")
    if st is not None and not type_ok(instance, st):
        raise ValidationError(f"{path}: expected type {st}, got {type(instance).__name__}")

    if "const" in schema and instance != schema["const"]:
        raise ValidationError(f"{path}: expected const {schema['const']!r}, got {instance!r}")

    if "enum" in schema and instance not in schema["enum"]:
        raise ValidationError(f"{path}: expected one of {schema['enum']!r}, got {instance!r}")

    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < int(schema["minLength"]):
            raise ValidationError(f"{path}: string too short, minLength={schema['minLength']}")

    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            raise ValidationError(f"{path}: value {instance} below minimum {schema['minimum']}")
        if "maximum" in schema and instance > schema["maximum"]:
            raise ValidationError(f"{path}: value {instance} above maximum {schema['maximum']}")

    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < int(schema["minItems"]):
            raise ValidationError(f"{path}: list has {len(instance)} items, minItems={schema['minItems']}")
        item_schema = schema.get("items")
        if item_schema is not None:
            for i, item in enumerate(instance):
                validate_instance(item, item_schema, f"{path}[{i}]")

    if isinstance(instance, dict):
        req = schema.get("required", [])
        for key in req:
            if key not in instance:
                raise ValidationError(f"{path}: missing required key '{key}'")

        props = schema.get("properties", {})
        for key, sub_schema in props.items():
            if key in instance:
                validate_instance(instance[key], sub_schema, f"{path}.{key}")

        if schema.get("additionalProperties") is False:
            unknown = sorted(k for k in instance if k not in props)
            if unknown:
                raise ValidationError(f"{path}: additional properties not allowed: {unknown}")


def try_jsonschema(instance, schema):
    try:
        import jsonschema  # type: ignore
    except Exception:
        return False
    jsonschema.Draft202012Validator(schema).validate(instance)
    return True

# Validate runtime policy contract links to required artifacts
policy = load_json(policy_file)
cycle = policy.get("cycle")
if not isinstance(cycle, dict):
    raise ValidationError("runtime-prsi-policy missing 'cycle' object")

required_artifacts = cycle.get("required_artifacts")
if not isinstance(required_artifacts, list):
    raise ValidationError("runtime-prsi-policy.cycle.required_artifacts must be a list")

for expected in list(required_schema_map.keys()) + expected_non_json_artifacts:
    if expected not in required_artifacts:
        raise ValidationError(f"runtime-prsi-policy missing required artifact '{expected}'")

max_mutating = cycle.get("max_mutating_actions")
if max_mutating != 1:
    raise ValidationError("runtime-prsi-policy.cycle.max_mutating_actions must be 1 for Phase 7.1 contract")

# Validate schemas and examples
example_cycle_id = None
for artifact_name, schema_name in required_schema_map.items():
    schema_path = schema_dir / schema_name
    example_path = example_dir / artifact_name

    schema = load_json(schema_path)
    if schema.get("type") != "object":
        raise ValidationError(f"schema {schema_path} must be type=object")

    instance = load_json(example_path)

    used_jsonschema = False
    try:
        used_jsonschema = try_jsonschema(instance, schema)
    except Exception as exc:
        raise ValidationError(f"jsonschema validation failed for {artifact_name}: {exc}") from exc

    if not used_jsonschema:
        validate_instance(instance, schema)

    cycle_id = instance.get("cycle_id")
    if not isinstance(cycle_id, str) or not cycle_id:
        raise ValidationError(f"{artifact_name} missing non-empty cycle_id")
    if example_cycle_id is None:
        example_cycle_id = cycle_id
    elif example_cycle_id != cycle_id:
        raise ValidationError(
            f"example artifact cycle_id mismatch: expected {example_cycle_id!r}, got {cycle_id!r} in {artifact_name}"
        )

print("PASS: PRSI cycle contract schemas and examples validated")
PY
