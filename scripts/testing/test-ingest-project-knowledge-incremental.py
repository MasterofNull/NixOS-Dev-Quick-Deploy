#!/usr/bin/env python3
"""Incremental-ingest tests for scripts/data/ingest-project-knowledge.py (stdlib, HTTP mocked)."""
import importlib.util
import io
import os
import sys
import tempfile
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "data" / "ingest-project-knowledge.py"
spec = importlib.util.spec_from_file_location("ipk", SCRIPT)
ipk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ipk)


class Boom(Exception):
    pass


def run(repo, state, posts, *extra, fail_after=None):
    ipk.REPO_ROOT = repo
    ipk._load_api_key = lambda: "k"
    ipk._health_check = lambda k: None
    ipk.time.sleep = lambda s: None
    ipk.STATE_FLUSH_EVERY = 2

    def fake_post(api_key, content, title, relative_path, project, dry_run, **kw):
        if fail_after is not None and len(posts) >= fail_after:
            raise Boom()
        posts.append(relative_path)
        return True

    ipk._post_document = fake_post
    buf = io.StringIO()
    with redirect_stdout(buf), redirect_stderr(buf):
        rc = ipk.main(["--paths", "docs", "--delay", "0", "--state-file", str(state), *extra])
    return rc


def main():
    with tempfile.TemporaryDirectory() as td:
        repo = Path(td) / "repo"
        (repo / "docs").mkdir(parents=True)
        (repo / "docs" / "a.md").write_text("alpha\n" * 1000)   # multi-chunk
        (repo / "docs" / "b.md").write_text("beta")
        (repo / "docs" / "c.md").write_text("gamma")
        state = Path(td) / "state.json"

        p = []
        run(repo, state, p)
        n = len(p)
        assert n >= 4, n
        print(f"first run posted {n}")

        p = []
        run(repo, state, p)
        assert p == [], p

        (repo / "docs" / "b.md").write_text("beta changed")
        p = []
        run(repo, state, p)
        assert p == ["docs/b.md"], p

        p = []
        run(repo, state, p, "--full")
        assert len(p) == n, (len(p), n)

        # dry-run reports and does not touch state
        before = state.read_bytes()
        p = []
        run(repo, state, p, "--dry-run")
        assert p == [] and state.read_bytes() == before

        # interrupted run: raise after k posts, state persists the k
        state.unlink()
        k = 3
        p = []
        try:
            run(repo, state, p, fail_after=k)
            raise AssertionError("expected Boom")
        except Boom:
            pass
        assert len(p) == k
        assert len(ipk._load_state(str(state))) == k
        assert not list(Path(td).glob("state.json.tmp.*"))
        p = []
        run(repo, state, p)
        assert len(p) == n - k, (len(p), n, k)
    print("PASS")


if __name__ == "__main__":
    main()
