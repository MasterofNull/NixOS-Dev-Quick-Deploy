#!/usr/bin/env python3
"""Runtime writers must not rewrite tracked build-affecting config (deploy guard needs a clean tree).

Runs aq-prompt-eval and aq-radar-ingest against temp copies and asserts the tracked files are
byte-identical afterwards while the gitignored state files hold the new values, and that readers
merge the state.
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from importlib.machinery import SourceFileLoader
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROMPT_EVAL = ROOT / "scripts/ai/aq-prompt-eval"
RADAR = ROOT / "scripts/ai/aq-radar-ingest"
REPORT = ROOT / "scripts/ai/aq-report"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_loader(name, SourceFileLoader(name, str(path)))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_prompt_eval(tmp: Path) -> None:
    reg = tmp / "registry.yaml"
    shutil.copyfile(ROOT / "ai-stack/prompts/registry.yaml", reg)
    before = reg.read_bytes()
    state = tmp / "eval-state.json"
    os.environ.pop("AQ_PROMPT_EVAL_STATE", None)

    mod = _load("aq_prompt_eval_state", PROMPT_EVAL)
    mod.wait_for_llama_ready = lambda *a, **k: True
    mod.llm_call = lambda *a, **k: ("route_search_synthesis nixos answer", 1.0)
    mod.run_eval(registry_path=reg, target_id="route_search_synthesis", dry_run=False,
                 verbose=False, model="local")

    assert reg.read_bytes() == before, "tracked registry.yaml was rewritten by aq-prompt-eval"
    data = json.loads(state.read_text(encoding="utf-8"))
    entry = data["route_search_synthesis"]
    assert entry["last_evaluated"] and isinstance(entry["mean_score"], float), entry

    # reader merges state (state wins)
    state.write_text(json.dumps({"route_search_synthesis": {"mean_score": 0.123, "last_evaluated": "2026-01-02"}}))
    os.environ["REGISTRY_PATH"] = str(reg)
    report = _load("aq_report_state", REPORT)
    by_id = {p["id"]: p for p in report.read_prompt_registry()}
    assert by_id["route_search_synthesis"]["mean_score"] == 0.123, by_id["route_search_synthesis"]
    print("PASS: aq-prompt-eval leaves registry.yaml untouched, writes eval-state.json, aq-report merges it")


def test_radar(tmp: Path) -> None:
    reg = tmp / "radar.json"
    shutil.copyfile(ROOT / "config/frontier-radar-registry.json", reg)
    assert "updated_at" not in reg.read_text(), "tracked radar registry must not carry updated_at"
    static_bytes = reg.read_bytes()
    state = tmp / "radar-state.json"
    env = {**os.environ, "AQ_RADAR_REGISTRY_PATH": str(reg), "AQ_RADAR_STATE_PATH": str(state)}

    def run(*args):
        return subprocess.run([sys.executable, str(RADAR), *args], capture_output=True, text=True, env=env)

    # a discover that finds no new source must not touch the tracked file at all
    assert run("discover", "--id", "cisa-kev", "--name", "x", "--category", "discovered_targets",
               "--url", "https://example.org/a", "--type", "rss",
               "--trust-tier", "tier2_peer_reviewed").returncode == 0
    assert reg.read_bytes() == static_bytes, "no-new-source discover rewrote the tracked registry"
    assert run("discover", "--id", "t1", "--name", "T1", "--category", "discovered_targets", "--url", "https://example.org/a",
               "--type", "rss", "--trust-tier", "tier2_peer_reviewed").returncode == 0
    stamp1 = json.loads(state.read_text())["updated_at"]
    assert "updated_at" not in json.loads(reg.read_text()), "updated_at must not live in tracked registry"
    after_first = reg.read_bytes()
    # re-running a no-op save path (same id) must not change the tracked file either
    assert run("discover", "--id", "t1", "--name", "T1", "--category", "discovered_targets", "--url", "https://example.org/a",
               "--type", "rss", "--trust-tier", "tier2_peer_reviewed").returncode == 0
    assert reg.read_bytes() == after_first
    assert f"updated {stamp1}" in run("list").stdout, "list must show the state timestamp"
    # a second real write moves the state stamp but leaves the registry bytes differing only by the new source
    assert run("discover", "--id", "t2", "--name", "T2", "--category", "discovered_targets", "--url", "https://example.org/b",
               "--type", "rss", "--trust-tier", "tier2_peer_reviewed").returncode == 0
    stamp2 = json.loads(state.read_text())["updated_at"]
    assert stamp2 >= stamp1
    assert "updated_at" not in reg.read_text()
    print("PASS: aq-radar-ingest keeps updated_at in the state file, not the tracked registry")


def main() -> int:
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "p").mkdir()
        (Path(d) / "r").mkdir()
        test_prompt_eval(Path(d) / "p")
        test_radar(Path(d) / "r")
    print("ALL RUNTIME-STATE TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
