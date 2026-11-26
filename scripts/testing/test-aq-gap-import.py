#!/usr/bin/env python3
"""Exercise both gap-import entry points without using live services."""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import TypedDict

SOURCE = Path(__file__).resolve().parents[1] / "ai"
LOCAL_TID = "local-20261124-113021-abc123"
GEMINI_TID = "gemini-20261124-113021-abc123"
SQL = r"DELETE FROM query_gaps WHERE query_text ILIKE :'pattern' ESCAPE '\' RETURNING id;"
STUB = r"""
import json
import os
import sys
from pathlib import Path

name = Path(sys.argv[0]).name
args = sys.argv[1:]
stdin = sys.stdin.read() if name in {"curl", "psql"} else ""
with open(os.environ["CALLS"], "a", encoding="utf-8") as log:
    print(json.dumps({"name": name, "args": args, "stdin": stdin}), file=log)

if name.startswith("delegate-to-"):
    lane = name.removeprefix("delegate-to-")
    if args[0] == "--check":
        print("Generated reference")
    else:
        outcome = os.environ.get(lane.upper() + "_OUTCOME", "ok")
        if outcome == "defer":
            sys.exit(5)
        if outcome != "no-id":
            print(f"Task: {lane}-20261124-113021-abc123")
elif name == "curl":
    print(os.environ.get("STUB_HTTP_CODE", "201"))
    sys.exit(int(os.environ.get("STUB_CURL_EXIT", "0")))
elif name == "psql":
    print(os.environ.get("STUB_DELETED_IDS", "17\n18"), end="")
    sys.exit(int(os.environ.get("STUB_PSQL_EXIT", "0")))
"""


class Call(TypedDict):
    name: str
    args: list[str]
    stdin: str


class GapImportTest(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        self.ai = root / "scripts" / "ai"
        self.ai.mkdir(parents=True)
        bin_dir = root / "bin"
        bin_dir.mkdir()
        config = root / "config"
        config.mkdir()
        (config / "service-endpoints.sh").write_text(
            'AIDB_URL="$STUB_AIDB_URL"\nPOSTGRES_PORT="$STUB_PG_PORT"\n',
            encoding="utf-8",
        )
        for name in ("aq-gap-import", "aq-knowledge-import.sh"):
            shutil.copyfile(SOURCE / name, self.ai / name)
        for stub in (
            self.ai / "delegate-to-local",
            self.ai / "delegate-to-gemini",
            bin_dir / "curl",
            bin_dir / "psql",
            bin_dir / "record-rebuild",
        ):
            stub.write_text(f"#!{sys.executable}\n{STUB}", encoding="utf-8")
            stub.chmod(0o755)
        (self.ai / "rebuild-qdrant-collections.sh").write_text(
            "exec record-rebuild\n", encoding="utf-8"
        )
        self.gaps = root / """query ' " ; $(never-execute).jsonl"""
        self.log = root / "calls.jsonl"
        self.env = {
            "PATH": os.pathsep.join((str(bin_dir), os.environ["PATH"])),
            "HOME": str(root),
            "AIDB_API_KEY": "stub-key",
            "AIDB_API_KEY_FILE": str(root / "missing-aidb-key"),
            "POSTGRES_PASSWORD_FILE": str(root / "missing-postgres-password"),
            "CALLS": str(self.log),
            "STUB_AIDB_URL": "https://aidb.invalid",
            "STUB_PG_PORT": "stub-port",
            "GAPS_JSONL": str(self.gaps),
            "SKIP_QDRANT_REBUILD": "1",
        }

    def run_import(self, script: str, *args: str, **env: str) -> subprocess.CompletedProcess[str]:
        self.log.write_text("", encoding="utf-8")
        return subprocess.run(
            ["bash", str(self.ai / script), *args],
            env=self.env | env,
            capture_output=True,
            text=True,
            timeout=4,
            check=False,
        )

    def write_gaps(self, *gaps: tuple[str, int]) -> None:
        self.gaps.write_text(
            "".join(
                json.dumps({"query_text": topic, "occurrences": count}) + "\n"
                for topic, count in gaps
            ),
            encoding="utf-8",
        )

    def calls(self, name: str = "") -> list[Call]:
        events: list[Call] = [
            json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines()
        ]
        return [event for event in events if not name or event["name"] == name]

    def assert_delegate(self, lane: str, mode: str, tid: str, topic: str) -> None:
        dispatch, check = self.calls(f"delegate-to-{lane}")
        self.assertEqual(dispatch["args"][0], "--prompt")
        self.assertIn(f"explaining: {topic}\n", dispatch["args"][1])
        self.assertEqual(dispatch["args"][2:], ["--mode", mode, "--role", "research", "--wait"])
        self.assertEqual(check["args"], ["--check", tid])

    def test_junk_only_skips_delegates(self) -> None:
        self.write_gaps(*(
            (topic, 31) for topic in (
                "ping", "Hello, how are you today?", "hi", "test", "status", "thanks!",
                "can you please", "what's up?", "can you please.", "what is it.",
                "...", "/", "???", "hi :)",
            )
        ))
        result = self.run_import("aq-gap-import")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("INFO  Skipped 14 trivial/non-technical gap(s)", result.stderr)
        self.assertIn("No eligible gaps to import", result.stdout)
        self.assertNotIn("Skipped", result.stdout)
        self.assertEqual(self.calls(), [])

    def test_technical_markers_survive_noise_filter(self) -> None:
        for topic in (
            "systemd.tmpfiles.rules", "what is lib.mkForce", "NixOS flake overlay priority",
            "--clear-gaps", "/etc/nixos/configuration.nix",
        ):
            with self.subTest(topic=topic):
                self.write_gaps((topic, 9))
                result = self.run_import("aq-gap-import")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assert_delegate("local", "direct", LOCAL_TID, topic)
                self.assertEqual(len(self.calls("curl")), 1)

    def test_technical_gaps_rank_by_max_count_and_preserve_topic(self) -> None:
        special = """Inspect lib.mkForce ' " ;\nwith NixOS"""
        self.write_gaps(
            ("ping", 100),
            ("what is lib.mkForce", 3),
            ("what is lib.mkForce", 3),
            ("NixOS flake overlay priority", 7),
            ("systemd.tmpfiles.rules", 5),
            ("systemd.tmpfiles.rules", 2),
            (special, 8),
        )
        result = self.run_import(
            "aq-gap-import", MIN_OCCURRENCES="4", MAX_GAPS="2", SKIP_QDRANT_REBUILD="0"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        imports = [json.loads(call["stdin"])["title"] for call in self.calls("curl")]
        self.assertEqual(imports, [special, "NixOS flake overlay priority"])
        self.assertEqual(len(self.calls("record-rebuild")), 1)

        result = self.run_import("aq-gap-import", MIN_OCCURRENCES="3", MAX_GAPS="5")
        self.assertEqual(result.returncode, 0, result.stderr)
        imports = [json.loads(call["stdin"])["title"] for call in self.calls("curl")]
        self.assertEqual(
            imports, [special, "NixOS flake overlay priority", "Systemd.tmpfiles.rules",
                      "What is lib.mkForce"]
        )

    def test_invalid_integer_settings_fail_without_dispatch(self) -> None:
        self.write_gaps(("systemd.tmpfiles.rules", 9))
        for overrides in ({"MIN_OCCURRENCES": "bad"}, {"MAX_GAPS": "-1"}):
            with self.subTest(overrides=overrides):
                result = self.run_import("aq-gap-import", **overrides)
                self.assertEqual(result.returncode, 1)
                self.assertIn("must be non-negative integers", result.stderr)
                self.assertEqual(self.calls(), [])

    def test_default_prefers_local(self) -> None:
        topic = "what is lib.mkForce"
        self.write_gaps((topic, 9))
        result = self.run_import("aq-gap-import")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_delegate("local", "direct", LOCAL_TID, topic)
        self.assertEqual(self.calls("delegate-to-gemini"), [])

    def test_auto_falls_back_to_gemini_on_failure_or_missing_id(self) -> None:
        topic = "NixOS flake overlay priority"
        self.write_gaps((topic, 9))
        for outcome in ("defer", "no-id"):
            with self.subTest(outcome=outcome):
                result = self.run_import("aq-gap-import", LOCAL_OUTCOME=outcome)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("trying Gemini", result.stderr)
                self.assertEqual(len(self.calls("delegate-to-local")), 1)
                self.assert_delegate("gemini", "plan", GEMINI_TID, topic)

    def test_explicit_lanes_and_invalid_lane(self) -> None:
        topic = "systemd.tmpfiles.rules"
        self.write_gaps((topic, 9))
        result = self.run_import("aq-gap-import", GAP_IMPORT_LANE="local", LOCAL_OUTCOME="defer")
        self.assertEqual(result.returncode, 1)
        self.assertIn("delegate-to-local failed", result.stderr)
        self.assertEqual(self.calls("delegate-to-gemini"), [])

        result = self.run_import("aq-gap-import", GAP_IMPORT_LANE="gemini")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls("delegate-to-local"), [])
        self.assert_delegate("gemini", "plan", GEMINI_TID, topic)

        for script, args in (("aq-gap-import", []), ("aq-knowledge-import.sh", [topic])):
            with self.subTest(script=script):
                result = self.run_import(script, *args, GAP_IMPORT_LANE="bogus")
                self.assertEqual(result.returncode, 1)
                self.assertIn("ERROR  Invalid GAP_IMPORT_LANE", result.stderr)
                self.assertEqual(self.calls(), [])

    def test_preflight_respects_delegate_availability(self) -> None:
        topic = "systemd.tmpfiles.rules"
        self.write_gaps((topic, 9))
        (self.ai / "delegate-to-local").chmod(0o644)
        result = self.run_import("aq-gap-import")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls("delegate-to-local"), [])
        self.assert_delegate("gemini", "plan", GEMINI_TID, topic)

        result = self.run_import("aq-gap-import", GAP_IMPORT_LANE="local")
        self.assertEqual(result.returncode, 1)
        self.assertIn("No executable delegate", result.stderr)
        self.assertEqual(self.calls(), [])

        (self.ai / "delegate-to-gemini").chmod(0o644)
        for lane in ("auto", "gemini"):
            with self.subTest(lane=lane):
                result = self.run_import("aq-gap-import", GAP_IMPORT_LANE=lane)
                self.assertEqual(result.returncode, 1)
                self.assertIn("No executable delegate", result.stderr)
                self.assertEqual(self.calls(), [])

    def test_slug_sanitizes_path_and_hashes_distinct_topics(self) -> None:
        paths: list[str] = []
        for topic in ("../../etc/passwd?x=1", "../../etc/passwd!x=1", "???"):
            with self.subTest(topic=topic):
                result = self.run_import("aq-knowledge-import.sh", topic, "--project", "nixos-docs")
                self.assertEqual(result.returncode, 0, result.stderr)
                request, = self.calls("curl")
                self.assertEqual(request["args"][-2:], ["--data-binary", "@-"])
                payload = json.loads(request["stdin"])
                self.assertEqual(payload["project"], "nixos-docs")
                path: str = payload["relative_path"]
                self.assertIsNotNone(re.fullmatch(r"knowledge/[a-z0-9-]+\.md", path))
                digest = hashlib.sha256(topic.encode("utf-8")).hexdigest()[:8]
                name = digest if topic == "???" else f"etc-passwd-x-1-{digest}"
                self.assertEqual(path, f"knowledge/{name}.md")
                paths.append(path)
        self.assertEqual(len(set(paths)), len(paths))

    def test_clear_gaps_sends_escaped_pattern_as_psql_variable(self) -> None:
        topic = r"foo'; DROP TABLE query_gaps; -- %_" + "\\"
        result = self.run_import("aq-knowledge-import.sh", topic, "--clear-gaps")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Cleared 2 matching gap entries", result.stdout)
        call, = self.calls("psql")
        self.assertEqual(call["stdin"], SQL + "\n")
        self.assertEqual(call["args"][-6:], [
            "-v", "ON_ERROR_STOP=1", "-v",
            r"pattern=%foo'; DROP TABLE query\_gaps; -- \%\_\\%", "--file", "-",
        ])

    def test_clear_gaps_counts_only_nonblank_rows(self) -> None:
        for rows, count in (("", 0), ("\n \n\t\n", 0), ("17\n\n \n18", 2)):
            with self.subTest(rows=rows):
                result = self.run_import(
                    "aq-knowledge-import.sh", "systemd.tmpfiles.rules", "--clear-gaps",
                    STUB_DELETED_IDS=rows,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(f"Cleared {count} matching gap entries", result.stdout)
                self.assertEqual(len(self.calls("psql")), 1)

    def test_all_real_imports_failing_reports_error(self) -> None:
        self.write_gaps(("NixOS flake overlay priority", 9))
        result = self.run_import("aq-gap-import", LOCAL_OUTCOME="defer", GEMINI_OUTCOME="defer")
        self.assertEqual(result.returncode, 1)
        self.assertIn("ERROR all 1 gap import(s) failed", result.stderr)
        self.assertEqual(
            [call["name"] for call in self.calls()], ["delegate-to-local", "delegate-to-gemini"]
        )

    def test_curl_transport_failure_skips_clear_gaps(self) -> None:
        result = self.run_import(
            "aq-knowledge-import.sh", "systemd.tmpfiles.rules", "--clear-gaps", STUB_CURL_EXIT="7"
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("FAIL  curl request failed", result.stderr)
        self.assertEqual(self.calls("psql"), [])


if __name__ == "__main__":
    unittest.main()
