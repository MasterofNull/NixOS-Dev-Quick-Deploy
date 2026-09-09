#!/usr/bin/env python3
"""Regression tests for aq-wiki per-file body-hash cache gating."""

import importlib.machinery
import importlib.util
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
AQ_WIKI = ROOT / "scripts" / "ai" / "aq-wiki"
LOADER = importlib.machinery.SourceFileLoader("aq_wiki", str(AQ_WIKI))
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
aq_wiki = importlib.util.module_from_spec(SPEC)
LOADER.exec_module(aq_wiki)


class BodyHashCacheTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.wiki_dir = self.root / ".understand-anything" / "wiki"
        self.wiki_dir.mkdir(parents=True)
        self.source = self.root / "src" / "sample.py"
        self.source.parent.mkdir()
        self.source.write_bytes(b"print('alpha')\n")
        self.graph = self.root / ".understand-anything" / "knowledge-graph.json"
        self.graph.write_text(json.dumps({
            "metadata": {"generated": "2026-01-01T00:00:00Z"},
            "nodes": [{
                "id": "file:src/sample.py",
                "type": "file",
                "name": "sample.py",
                "filePath": "src/sample.py",
            }],
            "edges": [],
        }))

        replacements = {
            "_REPO": self.root,
            "_GRAPH": self.graph,
            "_WIKI_DIR": self.wiki_dir,
            "_WIKI_META": self.wiki_dir / ".wiki-meta.json",
            "SUBSYSTEMS": {
                "sample": {
                    "prefix": "src",
                    "desc": "test subsystem",
                    "related_docs": [],
                }
            },
        }
        for name, value in replacements.items():
            patcher = patch.object(aq_wiki, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        (self.wiki_dir / "sample.md").write_text("cached section")

    def _write_meta(self, *, include_hash: bool = True) -> None:
        meta = {
            "sample": {
                "graph_generated": "2026-01-01T00:00:00Z",
                "node_count": 1,
                "generated": "2026-01-02T00:00:00Z",
            }
        }
        if include_hash:
            meta["body_sha256"] = {
                "src/sample.py": aq_wiki._body_sha256("src/sample.py")
            }
        aq_wiki._WIKI_META.write_text(json.dumps(meta))

    def _update(self):
        output = io.StringIO()
        with patch.object(
            aq_wiki, "_git_changed_paths_since", return_value={"src/sample.py"}
        ), patch.object(aq_wiki, "_render_section", return_value="fresh section") as render:
            with redirect_stdout(output):
                aq_wiki.cmd_update()
        return output.getvalue(), render

    def test_same_body_skips_regeneration_and_reuses_cached_section(self) -> None:
        self._write_meta()

        output, render = self._update()

        render.assert_not_called()
        self.assertIn("No sections needed update.", output)
        self.assertEqual((self.wiki_dir / "sample.md").read_text(), "cached section")

    def test_changed_body_regenerates_and_updates_hash(self) -> None:
        self._write_meta()
        self.source.write_bytes(b"print('beta')\n")

        _output, render = self._update()

        render.assert_called_once()
        meta = json.loads(aq_wiki._WIKI_META.read_text())
        self.assertEqual(
            meta["body_sha256"]["src/sample.py"],
            aq_wiki._body_sha256("src/sample.py"),
        )
        self.assertEqual((self.wiki_dir / "sample.md").read_text(), "fresh section")

    def test_missing_hash_is_stale_and_regenerates(self) -> None:
        self._write_meta(include_hash=False)

        _output, render = self._update()

        render.assert_called_once()
        meta = json.loads(aq_wiki._WIKI_META.read_text())
        self.assertEqual(
            meta["body_sha256"]["src/sample.py"],
            aq_wiki._body_sha256("src/sample.py"),
        )


if __name__ == "__main__":
    unittest.main()
