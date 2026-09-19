#!/usr/bin/env python3
"""Hermetic, offline regression checks for `scripts/ai/lib/model_tiering.py`'s
health-aware `get_recommended_model()`.

Covers the "model-router recommends a dead lane" defect: the router used to
hardcode `return "qwen-3-35b"` / `return "llama-3-8b"` with no health check
and no fallback, and those model ids don't even match
`config/model-coordinator.json`'s real `models` keys. This regression suite
proves the fixed version (a) never recommends a flagged-down lane, (b) falls
back through the `local -> codex -> claude` ladder to the next healthy lane,
(c) returns the normal preferred lane when nothing is down, and (d) always
resolves to a real `config/model-coordinator.json` model key.

No network, no credentials — all lane-health state is scoped to a per-run
temp directory via module-global monkeypatching on the dynamically-loaded
aq-role-route module, following the pattern in
`scripts/testing/test-agent-agnostic-router.py`.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load(name: str, rel_path: str):
    script = ROOT / rel_path
    loader = importlib.machinery.SourceFileLoader(name, str(script))
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader(name, loader))
    loader.exec_module(module)
    return module


model_tiering = _load("model_tiering_under_test", "scripts/ai/lib/model_tiering.py")

FAILURES: list[str] = []


def check(condition: bool, label: str) -> None:
    if condition:
        print(f"PASS: {label}")
    else:
        print(f"FAIL: {label}")
        FAILURES.append(label)


def _reset_health(tmp: Path) -> None:
    """Point the dynamically-loaded aq-role-route submodule's health-signal
    paths at an empty per-test temp directory, exactly as
    test-agent-agnostic-router.py resets them for aq-role-route directly."""
    role_route = model_tiering._ROLE_ROUTE
    assert role_route is not None, "aq-role-route failed to load — cannot test health-awareness"
    role_route.DELEGATION_DIR = tmp
    role_route.CODEX_COOLDOWN_FILE = tmp / ".codex-quota-cooldown"


REAL_MODEL_COORDINATOR = json.loads((ROOT / "config" / "model-coordinator.json").read_text(encoding="utf-8"))
REAL_MODEL_KEYS = set(REAL_MODEL_COORDINATOR.get("models", {}).keys())

STALE_MODEL_IDS = {"llama-3-8b", "qwen-3-35b"}


# ---------------------------------------------------------------------------
# (a) local flagged down -> recommendation is NOT the local/qwen lane, and
#     the fallback is recorded in `reason`.
# ---------------------------------------------------------------------------

def test_local_down_never_recommends_local() -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _reset_health(tmp)
        tmp.mkdir(parents=True, exist_ok=True)
        (tmp / ".local-down").write_text("simulated local outage\n", encoding="utf-8")

        for complexity in ("L1", "L2"):
            decision = model_tiering.get_recommended_model_with_reason(complexity)
            check(
                decision["lane"] != "local",
                f"local-down[{complexity}]: chosen lane is never 'local' while it is flagged down",
            )
            check(
                decision["model"] not in STALE_MODEL_IDS,
                f"local-down[{complexity}]: recommended model is not a stale id",
            )
            check(
                decision["model"] != "llama-cpp-local",
                f"local-down[{complexity}]: recommended model is not the down local model id",
            )
            check(
                "substituted" in (decision["reason"] or ""),
                f"local-down[{complexity}]: substitution is recorded in reason",
            )
            local_alt = next((a for a in decision["alternates"] if a["lane"] == "local"), None)
            check(
                local_alt is not None and local_alt["unavailable_reason"] == "flagged-down",
                f"local-down[{complexity}]: local appears in alternates marked flagged-down, not silently dropped",
            )


# ---------------------------------------------------------------------------
# (b) with local (and a further-down lane) unavailable and codex healthy,
#     it lands exactly on codex.
# ---------------------------------------------------------------------------

def test_local_and_claude_down_recommends_codex() -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _reset_health(tmp)
        tmp.mkdir(parents=True, exist_ok=True)
        (tmp / ".local-down").write_text("down\n", encoding="utf-8")
        (tmp / ".claude-down").write_text("down\n", encoding="utf-8")

        for complexity in ("L1", "L2"):
            decision = model_tiering.get_recommended_model_with_reason(complexity)
            check(
                decision["lane"] == "codex",
                f"local+claude-down[{complexity}]: falls through to the next healthy ladder lane (codex)",
            )
            check(
                decision["model"] == "codex",
                f"local+claude-down[{complexity}]: recommended model resolves to the real 'codex' key",
            )


# ---------------------------------------------------------------------------
# (c) with no health flags at all, the normal preferred lane (local) is
#     returned, with a real (non-stale) model id.
# ---------------------------------------------------------------------------

def test_no_flags_returns_preferred_local_lane() -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _reset_health(tmp)

        decision_l1 = model_tiering.get_recommended_model_with_reason("L1")
        decision_l2 = model_tiering.get_recommended_model_with_reason("L2")

        check(decision_l1["lane"] == "local", "no-flags[L1]: preferred lane 'local' is chosen when healthy")
        check(decision_l2["lane"] == "local", "no-flags[L2]: preferred lane 'local' is chosen when healthy")
        check(
            decision_l1["model"] == "llama-cpp-local",
            "no-flags[L1]: resolves to the real 'llama-cpp-local' model key",
        )
        check(
            "cheapest healthy lane" in (decision_l1["reason"] or ""),
            "no-flags[L1]: reason reflects the normal (non-substituted) path",
        )


# ---------------------------------------------------------------------------
# (d) stale model names are gone: every id this module can ever return is a
#     real config/model-coordinator.json `models` key, and the historical
#     stale literals never appear.
# ---------------------------------------------------------------------------

def test_stale_model_names_gone_and_ids_are_real_config_keys() -> None:
    check(
        STALE_MODEL_IDS.isdisjoint(model_tiering._LANE_MODEL_KEYS.values()),
        "stale-names: _LANE_MODEL_KEYS contains no stale literal ('llama-3-8b'/'qwen-3-35b')",
    )
    check(
        STALE_MODEL_IDS.isdisjoint(model_tiering._CLAUDE_MODEL_FOR_COMPLEXITY.values()),
        "stale-names: _CLAUDE_MODEL_FOR_COMPLEXITY contains no stale literal",
    )

    all_possible_ids = set(model_tiering._LANE_MODEL_KEYS.values()) | set(
        model_tiering._CLAUDE_MODEL_FOR_COMPLEXITY.values()
    )
    check(
        all_possible_ids.issubset(REAL_MODEL_KEYS),
        f"stale-names: every resolvable model id {sorted(all_possible_ids)} is a real "
        f"config/model-coordinator.json 'models' key {sorted(REAL_MODEL_KEYS)}",
    )

    # Exercise the actual resolution path too, not just the static tables.
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _reset_health(tmp)
        for complexity in ("L1", "L2"):
            model = model_tiering.get_recommended_model(complexity)
            check(
                model in REAL_MODEL_KEYS,
                f"stale-names: get_recommended_model('{complexity}') returns a real model-coordinator.json key",
            )
            check(
                model not in STALE_MODEL_IDS,
                f"stale-names: get_recommended_model('{complexity}') is never a stale literal",
            )


def main() -> int:
    test_local_down_never_recommends_local()
    test_local_and_claude_down_recommends_codex()
    test_no_flags_returns_preferred_local_lane()
    test_stale_model_names_gone_and_ids_are_real_config_keys()

    if FAILURES:
        print(f"\n{len(FAILURES)} FAILURE(S):")
        for label in FAILURES:
            print(f"  - {label}")
        return 1
    print("\nPASS: all model-tiering health-awareness checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
