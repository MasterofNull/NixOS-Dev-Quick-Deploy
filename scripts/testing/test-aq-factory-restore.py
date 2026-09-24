#!/usr/bin/env python3
"""Disposable fp-3 integration proof; never contacts production services."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tarfile
import tempfile
import unittest
from io import BytesIO
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
RESTORE = REPO_ROOT / "scripts/ai/aq-factory-restore"


class FactoryRestoreIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.isolation = Path(tempfile.mkdtemp(prefix="aq-fp3-isolated-", dir="/tmp"))
        cls.key = cls.isolation / "target.agekey"
        cls.wrong_key = cls.isolation / "wrong.agekey"
        subprocess.run(["age-keygen", "-o", str(cls.key)], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["age-keygen", "-o", str(cls.wrong_key)], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        cls.recipient = subprocess.check_output(
            ["age-keygen", "-y", str(cls.key)], text=True
        ).strip()

        ephemeral = Path("/proc/sys/net/ipv4/ip_local_port_range").read_text().split()
        lower, upper = (int(value) for value in ephemeral)
        cls.pg_port = lower + (os.getpid() % (upper - lower))
        cls.pg_data = cls.isolation / "postgres-data"
        subprocess.run(
            ["initdb", "--pgdata", str(cls.pg_data), "--no-locale", "--encoding=UTF8",
             "--auth=trust"],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        cls.qdrant_state = cls.isolation / "qdrant-state.json"
        cls.fixture_bin = cls.isolation / "bin"
        cls.fixture_bin.mkdir()
        fake_psql = cls.fixture_bin / "psql"
        fake_psql.write_text("""#!/usr/bin/env python3
import os, re, subprocess, sys

args = sys.argv[1:]
if '--dbname' in args:
    database = args[args.index('--dbname') + 1]
elif '-d' in args:
    database = args[args.index('-d') + 1]
else:
    database = 'postgres'
if '-c' in args:
    sql = args[args.index('-c') + 1]
else:
    sql = sys.stdin.read()
result = subprocess.run(
    ['postgres', '--single', '-D', os.environ['AQ_PG_FIXTURE_DATA'], database],
    input=sql.replace('\\n', ' ') + '\\n', text=True,
    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
)
combined = result.stdout + result.stderr
if result.returncode:
    sys.stderr.write(combined)
    raise SystemExit(result.returncode)
markers = re.findall(r'(__(?:AQ_COUNTS|AQ_DEPLOY_ROWS)__\\|[0-9|]+)', combined)
if markers:
    print(markers[-1])
elif 'pg_catalog.pg_class' in sql:
    counts = re.findall(r'count = "(\\d+)"', combined)
    print(counts[-1] if counts else '0')
elif '-c' in args:
    values = re.findall(r'result = "([^"]*)"', combined)
    if values:
        print(values[-1].replace('\\\\n', '\\n'))
""", encoding="utf-8")
        fake_psql.chmod(0o700)
        fake_pg_restore = cls.fixture_bin / "pg_restore"
        fake_pg_restore.write_text("#!/bin/sh\nexec /run/current-system/sw/bin/pg_restore \"$@\"\n",
                                   encoding="utf-8")
        fake_pg_restore.chmod(0o700)
        fake_curl = cls.fixture_bin / "curl"
        fake_curl.write_text("""#!/usr/bin/env python3
import json, os, sys, urllib.parse
from pathlib import Path

args = sys.argv[1:]
method = args[args.index('--request') + 1]
url = args[-1]
path = urllib.parse.urlparse(url).path
rest = path[len('/collections/'):]
name, _, tail = rest.partition('/')
name = urllib.parse.unquote(name)
suffix = '/' + tail if tail else ''
state_path = Path(os.environ['AQ_QDRANT_FIXTURE_STATE'])
state = json.loads(state_path.read_text()) if state_path.exists() else {}
status = 200
if '--data-binary' in args:
    body = json.loads(args[args.index('--data-binary') + 1])
else:
    body = None
if method == 'GET':
    if name not in state:
        status, result = 404, {'status': 'not found'}
    else:
        result = {'result': {'points_count': len(state[name])}}
elif method == 'POST' and suffix == '/snapshots/upload':
    points = json.load(sys.stdin.buffer)['points']
    state[name] = {str(p['id']): p for p in points}
    result = {'result': True}
elif method == 'POST' and suffix == '/points/scroll':
    result = {'result': {'points': list(state[name].values()), 'next_page_offset': None}}
elif method == 'POST' and suffix == '/points':
    result = {'result': [state[name][str(i)] for i in body['ids'] if str(i) in state[name]]}
elif method == 'PUT' and suffix == '/points':
    for point in body['points']:
        state[name][str(point['id'])] = point
    result = {'result': {'status': 'completed'}}
elif method == 'DELETE':
    state.pop(name, None)
    result = {'result': True}
else:
    status, result = 404, {'status': 'not found'}
state_path.write_text(json.dumps(state))
sys.stdout.write(json.dumps(result) + '\\n' + str(status))
""", encoding="utf-8")
        fake_curl.chmod(0o700)

    @classmethod
    def tearDownClass(cls) -> None:
        print(f"ISOLATION_KEPT={cls.isolation}")

    def pg_env(self, database: str) -> dict[str, str]:
        return {
            **os.environ,
            "POSTGRES_HOST": str(self.isolation / "no-listener"),
            "POSTGRES_PORT": str(self.pg_port),
            "POSTGRES_USER": os.environ.get("USER", "hyperd"),
            "POSTGRES_DB": database,
            "QDRANT_URL": "http://qdrant-fixture.invalid",
            "AQ_QDRANT_FIXTURE_STATE": str(self.qdrant_state),
            "AQ_PG_FIXTURE_DATA": str(self.pg_data),
            "PATH": f"{self.fixture_bin}:{os.environ['PATH']}",
        }

    def set_qdrant(self, collections: dict[str, dict[str, dict]]) -> None:
        self.qdrant_state.write_text(json.dumps(collections), encoding="utf-8")

    def get_qdrant(self) -> dict[str, dict[str, dict]]:
        return json.loads(self.qdrant_state.read_text(encoding="utf-8"))

    def psql(self, database: str, sql: str) -> str:
        env = self.pg_env(database)
        output = subprocess.check_output(
            [str(self.fixture_bin / "psql"), "-d", database, "-c", sql],
            env=env, text=True,
        )
        return output.strip()

    def create_db(self, name: str) -> None:
        self.psql("postgres", f'CREATE DATABASE "{name}"')

    def encrypt(self, plaintext: bytes, destination: Path) -> None:
        subprocess.run(
            ["age", "-r", self.recipient, "-o", str(destination)],
            input=plaintext, check=True, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def make_pack(self, label: str) -> Path:
        pack = self.isolation / label
        (pack / "qdrant").mkdir(parents=True)
        (pack / "postgres").mkdir()
        (pack / "var-lib").mkdir()
        qdrant = pack / "qdrant/knowledge.snapshot.age"
        postgres = pack / "postgres/aidb.sql.age"
        var_lib = pack / "var-lib/lora-adapters.tar.age"
        self.encrypt(json.dumps({"points": [
            {"id": 1, "vector": [1.0, 0.0], "payload": {"text": "source"}},
            {"id": 2, "vector": [0.0, 1.0], "payload": {"text": "new"}},
        ]}).encode(), qdrant)
        self.encrypt(b"""
CREATE TABLE public.items (id integer PRIMARY KEY, value text NOT NULL);
INSERT INTO public.items VALUES (1, 'source'), (2, 'new');
""", postgres)
        tar_bytes = BytesIO()
        with tarfile.open(fileobj=tar_bytes, mode="w") as archive:
            for name, value in (("adapters/new.bin", b"new-adapter"),
                                ("adapters/collision.bin", b"packed-value")):
                info = tarfile.TarInfo(name)
                info.size = len(value)
                info.mode = 0o600
                archive.addfile(info, BytesIO(value))
        self.encrypt(tar_bytes.getvalue(), var_lib)

        components = []
        for name, kind, relative in (
            ("qdrant:knowledge", "qdrant_snapshot", "qdrant/knowledge.snapshot.age"),
            ("postgres:aidb", "pg_dump", "postgres/aidb.sql.age"),
            ("var-lib:lora-adapters", "var_lib_state", "var-lib/lora-adapters.tar.age"),
        ):
            path = pack / relative
            components.append({
                "name": name, "kind": kind, "path": relative,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "size_bytes": path.stat().st_size, "encrypted": True,
                "encryption": {"algorithm": "age", "recipients": [self.recipient]},
            })
        (pack / "manifest.json").write_text(json.dumps({
            "schema_version": "aq-factory-push.v1", "tool": "aq-factory-push",
            "slice": "fp-2", "components": components,
        }), encoding="utf-8")
        return pack

    def restore(self, pack: Path, mode: str, database: str, root: Path,
                identity: Path | None = None) -> subprocess.CompletedProcess[str]:
        env = self.pg_env(database)
        env["AQ_FACTORY_RESTORE_VAR_LIB_ROOT"] = str(root)
        return subprocess.run(
            [str(RESTORE), "--pack-dir", str(pack), "--mode", mode,
             "--identity", str(identity or self.key)],
            env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            check=False,
        )

    def test_deploy_append_idempotency_and_fail_closed_preflight(self) -> None:
        pack = self.make_pack("pack")

        self.create_db("fp3_deploy")
        self.set_qdrant({})
        deploy_root = self.isolation / "deploy-var-lib"
        first = self.restore(pack, "deploy", "fp3_deploy", deploy_root)
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(self.psql(
            "fp3_deploy",
            "SELECT string_agg(id||'|'||value, E'\\\\n' ORDER BY id) AS result FROM items;",
        ), "1|source\n2|new")
        self.assertEqual(set(self.get_qdrant()["knowledge"]), {"1", "2"})
        self.assertEqual((deploy_root / "adapters/new.bin").read_bytes(), b"new-adapter")
        again = self.restore(pack, "deploy", "fp3_deploy", deploy_root)
        self.assertEqual(again.returncode, 0, again.stderr)
        deploy_summary = json.loads(again.stdout)
        self.assertTrue(all(c["added"] == 0 and c["updated"] == 0
                            for c in deploy_summary["components"]))

        self.create_db("fp3_append")
        self.psql("fp3_append", "CREATE TABLE items(id integer PRIMARY KEY,value text NOT NULL);"
                  "INSERT INTO items VALUES(1,'target-old'),(3,'keep');")
        self.set_qdrant({"knowledge": {
            "1": {"id": 1, "vector": [9.0, 9.0], "payload": {"text": "old"}},
            "3": {"id": 3, "vector": [3.0, 3.0], "payload": {"text": "keep"}},
        }})
        append_root = self.isolation / "append-var-lib"
        (append_root / "adapters").mkdir(parents=True)
        (append_root / "adapters/existing.bin").write_bytes(b"keep-me")
        (append_root / "adapters/collision.bin").write_bytes(b"target-wins")
        merged = self.restore(pack, "append", "fp3_append", append_root)
        self.assertEqual(merged.returncode, 0, merged.stderr)
        self.assertEqual(
            self.psql(
                "fp3_append",
                "SELECT string_agg(id||'|'||value, E'\\\\n' ORDER BY id) AS result FROM items;",
            ),
            "1|source\n2|new\n3|keep",
        )
        qdrant = self.get_qdrant()
        self.assertEqual(set(qdrant["knowledge"]), {"1", "2", "3"})
        self.assertEqual(qdrant["knowledge"]["3"]["payload"]["text"], "keep")
        self.assertEqual((append_root / "adapters/existing.bin").read_bytes(), b"keep-me")
        self.assertEqual((append_root / "adapters/collision.bin").read_bytes(), b"target-wins")
        self.assertEqual((append_root / "adapters/new.bin").read_bytes(), b"new-adapter")
        rerun = self.restore(pack, "append", "fp3_append", append_root)
        self.assertEqual(rerun.returncode, 0, rerun.stderr)
        rerun_summary = json.loads(rerun.stdout)
        for component in rerun_summary["components"]:
            self.assertEqual(component["added"], 0)
            self.assertEqual(component["updated"], 0)

        self.create_db("fp3_wrong_key")
        self.set_qdrant({})
        wrong_root = self.isolation / "wrong-var-lib"
        wrong = self.restore(pack, "deploy", "fp3_wrong_key", wrong_root, self.wrong_key)
        self.assertNotEqual(wrong.returncode, 0)
        self.assertIn("wrong recipient or key", wrong.stderr)
        self.assertEqual(self.psql(
            "fp3_wrong_key",
            "SELECT count(*)::text AS result FROM pg_tables WHERE schemaname='public';",
        ), "0")
        self.assertNotIn("knowledge", self.get_qdrant())
        self.assertFalse(wrong_root.exists())

        self.create_db("fp3_mismatch")
        bad_pack = self.make_pack("bad-pack")
        manifest_path = bad_pack / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["components"][-1]["sha256"] = "0" * 64
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        self.set_qdrant({})
        mismatch_root = self.isolation / "mismatch-var-lib"
        mismatch = self.restore(bad_pack, "deploy", "fp3_mismatch", mismatch_root)
        self.assertNotEqual(mismatch.returncode, 0)
        self.assertIn("sha256 mismatch", mismatch.stderr)
        self.assertEqual(self.psql(
            "fp3_mismatch",
            "SELECT count(*)::text AS result FROM pg_tables WHERE schemaname='public';",
        ), "0")
        self.assertNotIn("knowledge", self.get_qdrant())
        self.assertFalse(mismatch_root.exists())
        print("DEPLOY_RERUN_SUMMARY=" + json.dumps(deploy_summary, sort_keys=True))
        print("APPEND_FIRST_SUMMARY=" + json.dumps(json.loads(merged.stdout), sort_keys=True))
        print("APPEND_RERUN_SUMMARY=" + json.dumps(rerun_summary, sort_keys=True))
        print("APPEND_POSTGRES_ROWS=1|source,2|new,3|keep")
        print("APPEND_QDRANT_IDS=1,2,3;PREEXISTING_ID_3=keep")
        print("APPEND_FILES=existing:kept,collision:target-wins,new:added")
        print("WRONG_RECIPIENT_ABORT=" + wrong.stderr.strip().splitlines()[-1])
        print("SHA256_MISMATCH_ABORT=" + mismatch.stderr.strip().splitlines()[-1])

    def test_var_lib_parent_symlink_is_rejected_and_external_file_is_preserved(self) -> None:
        pack = self.make_pack("symlink-pack")
        self.create_db("fp3_symlink")
        self.set_qdrant({})
        declared_root = self.isolation / "declared-var-lib"
        outside = self.isolation / "outside-var-lib"
        declared_root.mkdir()
        (outside / "adapters").mkdir(parents=True)
        external = outside / "adapters/new.bin"
        external.write_bytes(b"external-must-survive")
        (declared_root / "adapters").symlink_to(outside / "adapters", target_is_directory=True)

        result = self.restore(pack, "deploy", "fp3_symlink", declared_root)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("symlinked ancestor", result.stderr)
        self.assertEqual(external.read_bytes(), b"external-must-survive")
        self.assertEqual(self.psql(
            "fp3_symlink",
            "SELECT count(*)::text AS result FROM pg_tables WHERE schemaname='public';",
        ), "0")
        self.assertNotIn("knowledge", self.get_qdrant())


if __name__ == "__main__":
    unittest.main(verbosity=2)
