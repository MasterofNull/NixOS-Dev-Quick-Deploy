#!/usr/bin/env python3
import json
import os
import subprocess
import tempfile
import unittest
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).with_name("resolve.py")
SPEC = spec_from_file_location("stack_resolve", SCRIPT)
resolver = module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(resolver)


class ResolveTests(unittest.TestCase):
    def run_resolve(self, root, *args, path=None):
        env = {**os.environ}
        if path is not None:
            env["PATH"] = path
        result = subprocess.run([os.sys.executable, str(SCRIPT), str(root), *args], text=True, capture_output=True, env=env, check=True)
        return json.loads(result.stdout)

    def fixture(self, files):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name) / "repo with spaces"
        root.mkdir()
        for name, content in files.items():
            (root / name).write_text(content, encoding="utf-8")
        return temp, root

    def test_each_marker_and_generic(self):
        cases = {"python": {"pyproject.toml": "[build-system]\nrequires=[]\nbuild-backend='x'\n[tool.pytest.ini_options]\n"}, "node": {"package.json": '{"scripts":{"test":"anything"}}'}, "rust": {"Cargo.toml": "[package]\nname='x'\nversion='0.1.0'"}, "go": {"go.mod": "module example.test/x"}, "nix": {"flake.nix": "{}"}, "generic": {}}
        for expected, files in cases.items():
            with self.subTest(expected=expected):
                temp, root = self.fixture(files)
                with temp:
                    self.assertEqual(self.run_resolve(root)["stacks"], [expected])

    def test_mixed_malformed_override_and_missing_tool(self):
        temp, root = self.fixture({"pyproject.toml": "not: valid: toml", "package.json": "{bad", "Cargo.toml": "[package]"})
        with temp:
            result = self.run_resolve(root, path="")
            self.assertEqual(result["stacks"], ["python", "node", "rust"])
            self.assertEqual(result["profiles"]["rust"]["checks"]["build"]["state"], "UNCONFIGURED")
            self.assertEqual(self.run_resolve(root, "--override", "generic")["stacks"], ["generic"])

    def test_profiles_are_metadata_driven_and_never_run_subprocesses(self):
        temp, root = self.fixture({
            "pyproject.toml": "[build-system]\nrequires=[]\nbuild-backend='x'\n[tool.pytest.ini_options]\n[tool.ruff]\n",
            "package.json": '{"scripts":{"test":"metadata-defined","ignored":"not allowed"}}',
        })
        with temp, patch.object(resolver.shutil, "which", return_value="/safe/tool"), patch(
            "subprocess.run", side_effect=AssertionError("detector must not run subprocesses")
        ):
            result = resolver.resolve(root)
        python = result["profiles"]["python"]["checks"]
        self.assertEqual(python["test"]["command"], "python -m pytest")
        self.assertEqual(python["test"]["state"], "UNCONFIGURED")
        self.assertEqual(python["test"]["requires"], ["python", "pytest"])
        self.assertEqual(python["secret_scan"]["command"], "gitleaks detect --no-git --redact")
        self.assertEqual(python["secret_scan"]["state"], "READY")
        node = result["profiles"]["node"]["checks"]
        self.assertEqual(node["test"]["command"], "npm run test")
        self.assertEqual(node["build"]["state"], "UNCONFIGURED")

    def test_override_needs_its_marker_even_when_tools_are_present(self):
        temp, root = self.fixture({})
        with temp, patch.object(resolver.shutil, "which", return_value="/safe/tool"):
            for stack in ("rust", "go", "nix"):
                with self.subTest(stack=stack):
                    result = resolver.resolve(root, stack)["profiles"][stack]
                    self.assertFalse(result["marker_present"])
                    self.assertEqual(result["checks"]["build"]["state"], "UNCONFIGURED")
                    self.assertEqual(result["checks"]["secret_scan"]["state"], "READY")
            for stack, marker in resolver.STACKS.items():
                if stack not in ("rust", "go", "nix"):
                    continue
                (root / marker).write_text("marker", encoding="utf-8")
                result = resolver.resolve(root, stack)["profiles"][stack]
                self.assertTrue(result["marker_present"])
                self.assertEqual(result["checks"]["build"]["state"], "READY")


if __name__ == "__main__":
    unittest.main()
