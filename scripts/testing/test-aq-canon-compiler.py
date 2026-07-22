#!/usr/bin/env python3
"""B3-C1 offline tests for scripts/governance/aq-canon-compiler.py.

Proves the Foundation B3 authorization invariants without touching any live
system: zero side-effect imports, fail-closed validation on malformed input,
and byte-for-byte deterministic output across repeated runs (both as an
in-process call and as a fresh subprocess invocation of the CLI).
"""
from __future__ import annotations

import ast
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

REPO = Path(__file__).resolve().parents[2]
MODULE = REPO / "scripts/governance/aq-canon-compiler.py"
META_SCHEMA = REPO / "config/schemas/aq-canon-spec-v1.json"

spec = importlib.util.spec_from_file_location("aq_canon_compiler_b3c1", MODULE)
assert spec and spec.loader
compiler = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = compiler
spec.loader.exec_module(compiler)

FORBIDDEN_IMPORTS = {
    "subprocess", "socket", "urllib", "requests", "shutil",
    "sqlite3", "psycopg2", "http", "ftplib", "smtplib",
}

VALID_TARGET_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "aq.test.widget/1.0",
    "type": "object",
    "additionalProperties": False,
    "required": ["widget_id", "count"],
    "properties": {
        "widget_id": {"type": "string", "minLength": 1},
        "count": {"type": "integer", "minimum": 0},
        "tags": {"type": "array", "items": {"type": "string"}},
        "status": {"enum": ["active", "retired"]},
        "meta": {
            "type": "object",
            "additionalProperties": False,
            "properties": {"note": {"type": ["string", "null"]}},
        },
    },
}

INVALID_TARGET_SCHEMA = {
    "$id": "aq.test.broken/1.0",
    "type": "object",
    "properties": {"x": {"type": "not-a-real-type"}},
}


def _write_json(path: Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document), encoding="utf-8")


class CanonCompilerB3C1(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo_root = Path(self._tmp.name)
        _write_json(self.repo_root / "config/schemas/widget.schema.json", VALID_TARGET_SCHEMA)
        _write_json(self.repo_root / "config/schemas/broken.schema.json", INVALID_TARGET_SCHEMA)
        self.valid_spec = {
            "spec_version": "1.0",
            "modules": [
                {"name": "widget", "schema_path": "config/schemas/widget.schema.json"},
            ],
        }

    def tearDown(self) -> None:
        self._tmp.cleanup()

    # -- invariant: pure, no side-effect imports -----------------------------
    def test_01_module_imports_no_side_effect_capable_libraries(self) -> None:
        tree = ast.parse(MODULE.read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertFalse(
            imported & FORBIDDEN_IMPORTS,
            f"forbidden side-effect-capable import(s) found: {imported & FORBIDDEN_IMPORTS}",
        )
        # os is intentionally absent too — only pathlib is used for filesystem access.
        self.assertNotIn("os", imported)

    def test_02_meta_schema_is_a_valid_draft_2020_12_schema(self) -> None:
        meta_schema = json.loads(META_SCHEMA.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(meta_schema)  # raises SchemaError on failure

    # -- invariant: fail-closed validation ------------------------------------
    def test_03_valid_spec_validates_cleanly(self) -> None:
        spec_path = self.repo_root / "canon-spec.json"
        _write_json(spec_path, self.valid_spec)
        loaded = compiler.load_and_validate_spec(spec_path, META_SCHEMA)
        self.assertEqual(loaded["spec_version"], "1.0")

    def test_04_malformed_spec_fails_closed(self) -> None:
        bad_spec = {"spec_version": "1.0", "modules": []}  # violates minItems: 1
        spec_path = self.repo_root / "bad-spec.json"
        _write_json(spec_path, bad_spec)
        with self.assertRaises(compiler.CanonCompilerError):
            compiler.load_and_validate_spec(spec_path, META_SCHEMA)

    def test_05_unknown_field_in_spec_fails_closed(self) -> None:
        bad_spec = dict(self.valid_spec)
        bad_spec["unexpected_field"] = True
        spec_path = self.repo_root / "unexpected-spec.json"
        _write_json(spec_path, bad_spec)
        with self.assertRaises(compiler.CanonCompilerError):
            compiler.load_and_validate_spec(spec_path, META_SCHEMA)

    def test_06_missing_target_schema_fails_closed(self) -> None:
        missing_module = {"name": "ghost", "schema_path": "config/schemas/does-not-exist.json"}
        with self.assertRaises(compiler.CanonCompilerError):
            compiler.compile_module(missing_module, repo_root=self.repo_root)

    def test_07_invalid_target_schema_fails_closed(self) -> None:
        broken_module = {"name": "broken", "schema_path": "config/schemas/broken.schema.json"}
        with self.assertRaises(compiler.CanonCompilerError):
            compiler.compile_module(broken_module, repo_root=self.repo_root)

    # -- compiled artifact shape ----------------------------------------------
    def test_08_compile_module_produces_three_typed_artifacts(self) -> None:
        module = {"name": "widget", "schema_path": "config/schemas/widget.schema.json"}
        compiled = compiler.compile_module(module, repo_root=self.repo_root)
        self.assertIn("export interface Widget", compiled["client_interface"])
        self.assertIn("widget_id: string", compiled["client_interface"])
        self.assertIn("tags?: Array<string>", compiled["client_interface"])
        self.assertIn("| `widget_id` | `string` | yes |", compiled["api_markdown"])
        self.assertIn("export const widgetViewModel", compiled["dashboard_viewmodel"])

    # -- invariant: pure determinism -------------------------------------------
    def test_09_compile_spec_is_byte_identical_across_repeated_in_process_calls(self) -> None:
        bundle_a = compiler.render_bundle_json(compiler.compile_spec(self.valid_spec, repo_root=self.repo_root))
        bundle_b = compiler.render_bundle_json(compiler.compile_spec(self.valid_spec, repo_root=self.repo_root))
        self.assertEqual(bundle_a, bundle_b)
        self.assertEqual(bundle_a.encode("utf-8"), bundle_b.encode("utf-8"))

    def test_10_cli_stdout_is_byte_identical_across_two_fresh_subprocess_runs(self) -> None:
        spec_path = self.repo_root / "canon-spec.json"
        _write_json(spec_path, self.valid_spec)
        cmd = [sys.executable, str(MODULE), "--spec", str(spec_path), "--repo-root", str(self.repo_root)]
        run_a = subprocess.run(cmd, cwd=self.repo_root, capture_output=True, check=True)
        run_b = subprocess.run(cmd, cwd=self.repo_root, capture_output=True, check=True)
        self.assertEqual(run_a.returncode, 0)
        self.assertEqual(run_b.returncode, 0)
        self.assertEqual(run_a.stdout, run_b.stdout)

    def test_11_cli_fails_closed_with_nonzero_exit_on_invalid_target_schema(self) -> None:
        bad_spec = {
            "spec_version": "1.0",
            "modules": [{"name": "broken", "schema_path": "config/schemas/broken.schema.json"}],
        }
        spec_path = self.repo_root / "broken-spec.json"
        _write_json(spec_path, bad_spec)
        cmd = [sys.executable, str(MODULE), "--spec", str(spec_path), "--repo-root", str(self.repo_root)]
        result = subprocess.run(cmd, cwd=self.repo_root, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("error:", result.stderr)

    # -- invariant: no filesystem mutation unless --out-dir is explicit --------
    def test_12_default_invocation_writes_nothing_to_disk(self) -> None:
        spec_path = self.repo_root / "canon-spec.json"
        _write_json(spec_path, self.valid_spec)
        before = sorted(p.relative_to(self.repo_root).as_posix() for p in self.repo_root.rglob("*") if p.is_file())
        cmd = [sys.executable, str(MODULE), "--spec", str(spec_path), "--repo-root", str(self.repo_root)]
        subprocess.run(cmd, cwd=self.repo_root, capture_output=True, check=True)
        after = sorted(p.relative_to(self.repo_root).as_posix() for p in self.repo_root.rglob("*") if p.is_file())
        self.assertEqual(before, after)

    def test_13_out_dir_writes_only_designated_build_target_files(self) -> None:
        spec_path = self.repo_root / "canon-spec.json"
        _write_json(spec_path, self.valid_spec)
        out_dir = self.repo_root / "build"
        cmd = [sys.executable, str(MODULE), "--spec", str(spec_path), "--out-dir", str(out_dir), "--repo-root", str(self.repo_root)]
        result = subprocess.run(cmd, cwd=self.repo_root, capture_output=True, text=True, check=True)
        self.assertIn("OK: compiled 1 module", result.stdout)
        written = sorted(p.name for p in out_dir.iterdir())
        self.assertEqual(written, ["widget.api.md", "widget.client.ts", "widget.viewmodel.js"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
