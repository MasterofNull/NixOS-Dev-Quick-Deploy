#!/usr/bin/env python3
"""P0-B provider projection: determinism, drift, refusal, brownfield preservation."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "ai" / "lib"))
import provider_projection as pp  # noqa: E402

CLI = ROOT / "scripts" / "ai" / "aq-provider-projection"
COPY = ["canon", "AGENTS.md", "CLAUDE.md", ".agent/CODEX.md", ".agent/GEMINI.md",
        ".agent/LOCAL-AGENT.md", ".agent/WORKFLOW-CANON.md",
        "docs/architecture/role-matrix.md", "config/agent-capability-contract.json",
        ".claude/settings.json"]


def fixture(tmp: Path) -> Path:
    repo = tmp / "repo"
    for rel in COPY:
        src, dst = ROOT / rel, repo / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)
    return repo


def cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(CLI), *args], capture_output=True, text=True, check=False)


def expect_refused(repo: Path, reason: str) -> None:
    try:
        pp.project(repo)
    except pp.ProjectionError as exc:
        assert exc.reason == reason, f"wanted {reason}, got {exc.reason}"
        return
    raise AssertionError(f"projection was not refused ({reason})")


def main() -> int:
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        repo = fixture(tmp)

        # byte-determinism across two CLI runs, four providers present, hash printed
        a, b = cli("--repo", str(repo), "preview"), cli("--repo", str(repo), "preview")
        assert a.returncode == 0 and a.stdout == b.stdout and a.stderr == b.stderr, "non-deterministic"
        doc = json.loads(a.stdout)
        assert {"codex", "claude", "gemini", "local"} <= set(doc["providers"])
        assert f"output_sha256={doc['output_sha256']}" in a.stderr
        assert doc["output_sha256"] == pp.output_hash({"schema": doc["schema"], "providers": doc["providers"]})

        # clean fixture: no drift, exit 0
        assert cli("--repo", str(repo), "check").returncode == 0

        # brownfield: extra adopted content outside canon regions is preserved, not drift
        gem = repo / ".agent/GEMINI.md"
        gem.write_text(gem.read_text() + "\n## Adopted local section\nkeep me\n")
        r = cli("--repo", str(repo), "check")
        rep = json.loads(r.stdout)
        assert r.returncode == 0 and rep["status"] == "clean", r.stdout
        assert rep["preserved"]["gemini:.agent/GEMINI.md"]["status"] == "preserved"
        assert "keep me" in gem.read_text(), "check must never write"

        # drift: altered owned region is detected, exit 1
        cl = repo / "CLAUDE.md"
        original = cl.read_text()
        cl.write_text(original.replace("<!-- canon:end fable-parity -->", "tampered\n<!-- canon:end fable-parity -->", 1))
        r = cli("--repo", str(repo), "check")
        rep = json.loads(r.stdout)
        assert r.returncode == 1 and rep["status"] == "drift", r.stdout
        assert any(f["provider"] == "claude" and f["block"] == "fable-parity" and f["status"] == "drift"
                   for f in rep["drift"])
        assert cl.read_text() != original, "check must not repair"
        cl.write_text(original)

        # missing region marker and missing file reported
        cx = repo / ".agent/CODEX.md"
        cx_text = cx.read_text()
        cx.write_text(cx_text.replace("<!-- canon:begin fable-parity -->", "", 1))
        assert any(f["status"] == "region_missing" for f in pp.check(repo)["drift"])
        cx.write_text(cx_text)
        (repo / ".agent/LOCAL-AGENT.md").unlink()
        assert any(f["status"] == "file_missing" for f in pp.check(repo)["drift"])
        shutil.copy2(ROOT / ".agent/LOCAL-AGENT.md", repo / ".agent/LOCAL-AGENT.md")

        # unknown field refused
        manifest = repo / "canon/canon.yaml"
        base = manifest.read_text()
        manifest.write_text(base.replace("    source: blocks/behavioral-rules.md\n",
                                         "    source: blocks/behavioral-rules.md\n    surprise: 1\n", 1))
        expect_refused(repo, "unknown_field")
        # unknown target path refused
        manifest.write_text(base.replace("      - .agent/CODEX.md\n", "      - docs/elsewhere.md\n", 1))
        expect_refused(repo, "unknown_target")
        # colliding (same target twice in one block) refused
        manifest.write_text(base.replace("      - .agent/CODEX.md\n", "      - .agent/GEMINI.md\n", 1))
        expect_refused(repo, "colliding_field")
        manifest.write_text(base)
        assert cli("--repo", str(repo), "preview").returncode == 0

        # secret-shaped value refused (built at runtime, never stored in source)
        fake = "sk-" + "A1b2C3d4" * 4
        blk = repo / "canon/blocks/fable-parity.md"
        blk_text = blk.read_text()
        blk.write_text(blk_text + f"\napi_key = {fake}\n")
        expect_refused(repo, "secret_shaped_value")
        r = cli("--repo", str(repo), "preview")
        assert r.returncode == 2 and fake not in r.stdout + r.stderr, "secret must not be echoed"
        blk.write_text(blk_text)

        # CLI has no write mode
        assert cli("apply").returncode != 0

    print("PASS: provider projection fixtures (determinism, drift, brownfield, refusals, no write mode)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
