#!/usr/bin/env python3
"""Fixture tests for aq-graph-build: edge/node types, import resolution, determinism,
understand_graph.py compatibility, LLM summary carry-forward, --check freshness."""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "ai" / "lib"))
import graph_build as gb  # noqa: E402
import understand_graph as ug  # noqa: E402

CLI = REPO / "scripts" / "ai" / "aq-graph-build"

FILES = {
    "pkg/__init__.py": "",
    "pkg/util.py": '"""Helpers for the demo package."""\n\n\nclass Base:\n    """Base class."""\n\n    def ping(self):\n        return 1\n\n\ndef helper(x):\n    """Double x."""\n    return x * 2\n\n\ndef undocumented(a, b=2):\n    return a + b\n',
    "pkg/core.py": 'import json\nfrom .util import helper, Base\nfrom pkg import util\n\n\nclass Child(Base):\n    def go(self):\n        return self.ping()\n\n\ndef run():\n    """Run the demo."""\n    util.undocumented(1)\n    Child().go()\n    return helper(json.dumps({}))\n\n\nif __name__ == "__main__":\n    run()\n',
    "lib/util2.py": "# Second helper module (comment header only).\n\ndef shared():\n    return 3\n",
    "scripts/ai/aq-demo": '#!/usr/bin/env python3\n"""aq-demo -- demo CLI."""\nimport sys\nsys.path.insert(0, "lib")\nimport util2\nfrom pkg.core import run\n\n\ndef main():\n    util2.shared()\n    run()\n\n\nmain()\n',
    "scripts/run.sh": "#!/usr/bin/env bash\n# Run the demo stack.\nset -e\nsource ./common.sh\nscripts/ai/aq-demo --go\naq-demo again\n",
    "scripts/common.sh": "#!/usr/bin/env bash\n# Shared shell helpers.\nlog() { echo \"$@\"; }\n",
    "nix/modules/core/options.nix": '{lib, ...}: {\n  options.mySystem = {\n    demo = {\n      enable = lib.mkEnableOption "demo service";\n      port = lib.mkOption {\n        type = lib.types.port;\n        description = "Port the demo listens on.";\n      };\n    };\n  };\n}\n',
    "nix/modules/svc.nix": '# Demo service module.\n{config, lib, pkgs, ...}: let\n  cfg = config.mySystem.demo;\nin {\n  imports = [ ./extra.nix ];\n  config = lib.mkIf cfg.enable {\n    systemd.services.demo = {\n      description = "Demo service";\n      serviceConfig.ExecStart = "${pkgs.python3}/bin/python3 /repo/scripts/ai/aq-demo --port ${toString cfg.port}";\n    };\n    systemd.timers.demo = {\n      description = "Demo timer";\n      timerConfig.OnCalendar = "daily";\n    };\n  };\n}\n',
    "nix/modules/extra.nix": "{...}: {}\n",
    "README.md": "# Demo repo\n\nIntro paragraph.\n\nSee `scripts/ai/aq-demo` and [core](pkg/core.py); module `nix/modules/svc.nix`.\n",
    "tests/test_core.py": "from pkg.core import run\n\n\ndef test_run():\n    assert run() is not None\n",
    "scripts/testing/test-demo.sh": "#!/usr/bin/env bash\n# Exercises the demo CLI.\nscripts/ai/aq-demo\n",
    "config/capability-index.json": json.dumps({"entries": [
        {"category": "Demo", "class": "ACTIVE", "kind": "script", "name": "aq-demo", "path": "scripts/ai/aq-demo", "purpose": "demo"}]}),
}

OLD_LLM = {
    "metadata": {"version": "2.8.1", "generated": "2026-07-01T00:00:00Z", "project": "demo-project"},
    "nodes": [
        {"id": "file:pkg/util.py", "type": "file", "name": "util.py", "filePath": "pkg/util.py",
         "summary": "LLM: should lose to the module docstring.", "tags": ["llm-tag"]},
        {"id": "function:pkg/util.py:undocumented", "type": "function", "name": "undocumented", "filePath": "pkg/util.py",
         "summary": "LLM summary: adds two numbers, second defaulting to 2, used by the core demo flow.", "tags": ["math"]},
        {"id": "function:pkg/util.py:helper", "type": "function:", "name": "helper", "filePath": "pkg/util.py",
         "summary": "LLM: helper that should lose to the docstring Double x.", "tags": []},
        {"id": "file:gone.py", "type": "file", "name": "gone.py", "filePath": "gone.py", "summary": "deleted file"},
    ],
    "edges": [],
}


def git(root, *a):
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t",
               GIT_COMMITTER_EMAIL="t@t", GIT_AUTHOR_DATE="2026-10-01T00:00:00Z", GIT_COMMITTER_DATE="2026-10-01T00:00:00Z")
    subprocess.run(["git", "-C", str(root), *a], check=True, capture_output=True, env=env)


def make_repo(tmp: Path) -> Path:
    root = tmp / "repo"
    for rel, body in FILES.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body)
    git(root.parent, "init", "-q", str(root))
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "fixture")
    ua = root / ".understand-anything"
    ua.mkdir()
    (ua / "knowledge-graph.json").write_text(json.dumps(OLD_LLM))
    return root


def edge_set(g, etype):
    return {(e["source"], e["target"]) for e in g["edges"] if e["type"] == etype}


def test_build(root: Path):
    old = gb.load_llm(root, root / ".understand-anything")
    assert old and old["metadata"]["project"] == "demo-project"
    g, info = gb.build(root, old)
    N = {n["id"]: n for n in g["nodes"]}
    meta = g["metadata"]
    assert meta["generator"] == "aq-graph-build" and meta["mode"] == "deterministic"
    assert meta["version"] == "2.8.1" and meta["project"] == "demo-project"
    assert meta["generated"] == "2026-10-01T00:00:00Z" and len(meta["git_head"]) == 40

    # node types / ids
    for nid in ("file:pkg/util.py", "class:pkg/util.py:Base", "function:pkg/util.py:helper",
                "function:pkg/util.py:Base.ping", "file:scripts/ai/aq-demo", "file:scripts/run.sh",
                "file:nix/modules/svc.nix", "file:README.md", "service:demo", "timer:demo",
                "option:mySystem.demo.port", "option:mySystem.demo.enable"):
        assert nid in N, nid
    assert N["service:demo"]["type"] == "service" and N["timer:demo"]["type"] == "service"
    assert N["file:README.md"]["type"] == "document" and N["file:README.md"]["summary"].startswith("Demo repo")
    assert N["file:scripts/run.sh"]["summary"] == "Run the demo stack."
    assert N["option:mySystem.demo.port"]["summary"] == "Port the demo listens on."
    assert N["function:pkg/util.py:helper"]["startLine"] == 11
    assert N["function:pkg/util.py:undocumented"]["startLine"] and N["service:demo"]["summary"] == "Demo service"
    assert "cap:ACTIVE" in N["file:scripts/ai/aq-demo"]["tags"]
    assert all({"id", "type", "name", "filePath", "summary", "tags", "complexity"} <= set(n) for n in g["nodes"])
    assert all({"source", "target", "type", "direction"} <= set(e) for e in g["edges"])
    assert {e["source"] for e in g["edges"]} <= set(N) and {e["target"] for e in g["edges"]} <= set(N)

    # edge types
    kinds = {e["type"] for e in g["edges"]}
    assert {"contains", "imports", "calls", "extends", "tests", "tested_by", "documents", "configures"} <= kinds, kinds
    imports = edge_set(g, "imports")
    assert ("file:pkg/core.py", "file:pkg/util.py") in imports  # package-relative
    assert ("file:scripts/ai/aq-demo", "file:lib/util2.py") in imports  # sys.path.insert style
    assert ("file:scripts/ai/aq-demo", "file:pkg/core.py") in imports
    assert ("file:scripts/run.sh", "file:scripts/common.sh") in imports  # shell source
    assert ("file:nix/modules/svc.nix", "file:nix/modules/extra.nix") in imports  # nix imports list
    assert not any(t == "file:json" for _, t in imports)  # stdlib is not a repo edge
    calls = {(e["source"], e["target"]): e["weight"] for e in g["edges"] if e["type"] == "calls"}
    assert calls[("function:pkg/core.py:run", "function:pkg/util.py:helper")] >= 0.9
    assert calls[("function:pkg/core.py:run", "function:pkg/util.py:undocumented")] >= 0.9  # module attr
    assert ("function:pkg/core.py:Child.go", "function:pkg/util.py:Base.ping") in calls  # self.ping via base
    assert ("file:pkg/core.py", "function:pkg/core.py:run") in calls  # __main__ block
    assert ("file:scripts/run.sh", "file:scripts/ai/aq-demo") in calls
    assert ("service:demo", "file:scripts/ai/aq-demo") in calls  # ExecStart -> script
    assert ("timer:demo", "service:demo") in calls
    assert ("class:pkg/core.py:Child", "class:pkg/util.py:Base") in edge_set(g, "extends")
    assert ("file:nix/modules/svc.nix", "service:demo") in edge_set(g, "configures")
    assert ("file:nix/modules/svc.nix", "option:mySystem.demo.port") in edge_set(g, "configures")
    assert ("file:README.md", "file:scripts/ai/aq-demo") in edge_set(g, "documents")
    assert ("file:README.md", "file:pkg/core.py") in edge_set(g, "documents")
    assert ("file:tests/test_core.py", "file:pkg/core.py") in edge_set(g, "tests")
    assert ("file:pkg/core.py", "file:tests/test_core.py") in edge_set(g, "tested_by")
    assert ("file:scripts/testing/test-demo.sh", "file:scripts/ai/aq-demo") in edge_set(g, "tests")

    # import-resolution accounting: every repo-internal import resolved, stdlib separated
    py = info["python"]
    assert py["resolved_to_repo_files"] >= 6 and py["stdlib"] >= 2, py
    return g


def test_carry_forward(root: Path, g):
    N = {n["id"]: n for n in g["nodes"]}
    u = N["function:pkg/util.py:undocumented"]
    assert u["summary"].startswith("LLM summary: adds two numbers") and "summary:llm-2026-07" in u["tags"] and "math" in u["tags"]
    assert N["function:pkg/util.py:helper"]["summary"] == "Double x."  # docstring wins
    assert "summary:llm-2026-07" not in N["function:pkg/util.py:helper"]["tags"]
    assert N["file:pkg/util.py"]["summary"] == "Helpers for the demo package."
    assert "file:gone.py" not in N


def test_cli_determinism_backup_check(root: Path):
    ua = root / ".understand-anything"
    out = ua / "knowledge-graph.json"
    r = subprocess.run([sys.executable, str(CLI), "--root", str(root)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    backup = ua / "knowledge-graph.llm-2026-07-01.json"
    assert backup.exists() and json.loads(backup.read_text())["metadata"]["project"] == "demo-project"
    first = out.read_bytes()
    r = subprocess.run([sys.executable, str(CLI), "--root", str(root)], capture_output=True, text=True)
    assert r.returncode == 0 and out.read_bytes() == first, "two builds must be byte-identical"
    assert backup.exists() and json.loads(backup.read_text())["metadata"].get("generator") is None  # not clobbered
    alt = root.parent / "alt.json"
    subprocess.run([sys.executable, str(CLI), "--root", str(root), "--out", str(alt)], check=True, capture_output=True)
    assert alt.read_bytes() == first
    assert not list(ua.glob("*.tmp*"))

    # carry-forward survived the second build (backup is the carry source)
    g = json.loads(first)
    assert any("summary:llm-2026-07" in n["tags"] for n in g["nodes"])

    # schema compatibility with the consumers
    s = ug.summary(root)
    assert s["nodes"] == len(g["nodes"]) and s["edges"] == len(g["edges"])
    assert s["node_types"]["function"] > 0 and s["edge_types"]["calls"] > 0 and s["staleness"]["graph_present"]
    idx = ug.get_index(root)
    assert ug.search(idx, "helper")[0]["name"] == "helper"
    assert "pkg/core.py" in {d["file"] for d in ug.impact(idx, "pkg/util.py")["dependents"]}
    assert {d["file"] for d in ug.impact(idx, "pkg/core.py")["dependents"]} >= {"tests/test_core.py", "scripts/ai/aq-demo"}
    assert ug.neighbors(idx, "function:pkg/core.py:run", 1)
    assert ug.symbol(idx, "helper")[0]["called_by"] == ["run"]
    q = subprocess.run([sys.executable, str(REPO / "scripts/ai/aq-graph-query"), "--root", str(root), "impact", "pkg/util.py"],
                       capture_output=True, text=True)
    assert q.returncode == 0 and "core.py" in q.stdout

    # --check: fresh at the same HEAD, stale after an in-scope change, fresh after only-excluded change
    chk = lambda: subprocess.run([sys.executable, str(CLI), "--root", str(root), "--check"], capture_output=True, text=True)  # noqa: E731
    assert chk().returncode == 0, chk().stdout
    (root / "archive").mkdir()
    (root / "archive" / "x.py").write_text("x = 1\n")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "archive only")
    assert chk().returncode == 0, chk().stdout
    (root / "pkg" / "new.py").write_text("def n():\n    return 1\n")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "in scope")
    r = chk()
    assert r.returncode == 1 and r.stdout.startswith("STALE"), r.stdout
    subprocess.run([sys.executable, str(CLI), "--root", str(root)], check=True, capture_output=True)
    assert chk().returncode == 0
    # missing graph / foreign generator -> stale
    assert gb.check_fresh(root, root / "nope.json")[0] is False
    foreign = root.parent / "foreign.json"
    foreign.write_text(json.dumps(OLD_LLM))
    assert gb.check_fresh(root, foreign)[0] is False


def test_nix_masking():
    s = '{ a = "x { y"; b = \'\'z } \'\'; # c = {\n d = { }; }'
    m = gb.mask_nix(s)
    assert len(m) == len(s) and m.count("{") == m.count("}") == 2 and "c =" not in m


def main():
    with tempfile.TemporaryDirectory() as d:
        root = make_repo(Path(d))
        old = gb.load_llm(root, root / ".understand-anything")
        g = test_build(root)
        g2, _ = gb.build(root, old)
        test_carry_forward(root, g2)
        test_nix_masking()
        test_cli_determinism_backup_check(root)
    print("PASS: graph build (node/edge types, import resolution, determinism, schema compat, LLM carry-forward, --check)")


if __name__ == "__main__":
    main()
