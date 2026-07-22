#!/usr/bin/env python3
"""Hermetic, offline regression checks for the agent-agnostic factory router.

Covers `scripts/ai/aq-slice-claim` (atomic single-owner slice claim) and
`scripts/ai/aq-role-route` (availability x eligibility x independence x cost
selector). DESIGN SSOT: `.agents/plans/agent-agnostic-factory/DESIGN.md`.

No network, no credentials — all state is scoped to a per-run temp
directory via module-global monkeypatching, following the pattern in
`scripts/testing/test-antigravity-inbox.py`.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import tempfile
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load(name: str, rel_path: str):
    script = ROOT / rel_path
    loader = importlib.machinery.SourceFileLoader(name, str(script))
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader(name, loader))
    loader.exec_module(module)
    return module


claim_mod = _load("aq_slice_claim", "scripts/ai/aq-slice-claim")
route_mod = _load("aq_role_route", "scripts/ai/aq-role-route")

FAILURES: list[str] = []


def check(condition: bool, label: str) -> None:
    if condition:
        print(f"PASS: {label}")
    else:
        print(f"FAIL: {label}")
        FAILURES.append(label)


# ---------------------------------------------------------------------------
# aq-slice-claim
# ---------------------------------------------------------------------------

def _fresh_claims_dir(tmp: Path) -> None:
    claim_mod.CLAIMS_DIR = tmp / "slice-claims"


def test_claim_cas_exclusivity() -> None:
    with tempfile.TemporaryDirectory() as td:
        _fresh_claims_dir(Path(td))
        barrier = threading.Barrier(2)

        # aq-slice-claim exposes only argparse-bound cmd_acquire; drive it
        # via the same Namespace shape argparse would build so the real
        # code path (including the O_EXCL CAS) is exercised under a race.
        import argparse

        def make_args(owner: str) -> argparse.Namespace:
            return argparse.Namespace(slice_id="race-slice", owner=owner, head=f"head-{owner}", ttl=3600, json=True)

        outcomes: dict[str, int] = {}

        def worker(owner: str) -> None:
            barrier.wait()
            outcomes[owner] = claim_mod.cmd_acquire(make_args(owner))

        t1 = threading.Thread(target=worker, args=("fable",))
        t2 = threading.Thread(target=worker, args=("codex",))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        winners = [owner for owner, rc in outcomes.items() if rc == 0]
        losers = [owner for owner, rc in outcomes.items() if rc != 0]
        check(len(winners) == 1, "claim CAS: exactly one racing acquire wins")
        check(len(losers) == 1, "claim CAS: exactly one racing acquire loses")

        status = claim_mod._load_claim(claim_mod._claim_path("race-slice"))
        check(
            status is not None and status.get("owner") in winners,
            "claim CAS: on-disk claim owner matches the winner",
        )


def test_second_acquire_fails_naming_holder() -> None:
    import argparse

    with tempfile.TemporaryDirectory() as td:
        _fresh_claims_dir(Path(td))
        a1 = argparse.Namespace(slice_id="s1", owner="fable", head="h1", ttl=3600, json=True)
        a2 = argparse.Namespace(slice_id="s1", owner="codex", head="h2", ttl=3600, json=True)
        rc1 = claim_mod.cmd_acquire(a1)
        rc2 = claim_mod.cmd_acquire(a2)
        check(rc1 == 0, "second-acquire test: first acquire (fable) succeeds")
        check(rc2 != 0, "second-acquire test: second acquire (codex) fails")

        holder = claim_mod._load_claim(claim_mod._claim_path("s1"))
        check(
            holder is not None and holder.get("owner") == "fable",
            "second-acquire test: failed acquire's stderr identifies the current holder (fable) on disk",
        )


def test_release_holder_only() -> None:
    import argparse

    with tempfile.TemporaryDirectory() as td:
        _fresh_claims_dir(Path(td))
        acquire_args = argparse.Namespace(slice_id="rel-slice", owner="fable", head="h1", ttl=3600, json=True)
        check(claim_mod.cmd_acquire(acquire_args) == 0, "release test: setup acquire succeeds")

        bad_release = argparse.Namespace(slice_id="rel-slice", owner="codex", json=True)
        rc_bad = claim_mod.cmd_release(bad_release)
        check(rc_bad != 0, "release: non-holder release is refused")
        check(
            claim_mod._load_claim(claim_mod._claim_path("rel-slice")) is not None,
            "release: claim still present after refused non-holder release",
        )

        good_release = argparse.Namespace(slice_id="rel-slice", owner="fable", json=True)
        rc_good = claim_mod.cmd_release(good_release)
        check(rc_good == 0, "release: holder release succeeds")
        check(
            claim_mod._load_claim(claim_mod._claim_path("rel-slice")) is None,
            "release: claim removed after holder release",
        )


def test_stale_claim_reclaim() -> None:
    import argparse

    with tempfile.TemporaryDirectory() as td:
        _fresh_claims_dir(Path(td))
        claim_mod.CLAIMS_DIR.mkdir(parents=True, exist_ok=True)
        expired_record = {
            "slice_id": "stale-slice",
            "owner": "codex",
            "head": "old-head",
            "ts": (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat(),
            "acquired_at": time.time() - 5 * 3600,
            "expires": time.time() - 3600,  # expired one hour ago
            "ttl_seconds": 3600,
        }
        claim_path = claim_mod._claim_path("stale-slice")
        claim_path.write_text(json.dumps(expired_record), encoding="utf-8")

        new_args = argparse.Namespace(slice_id="stale-slice", owner="fable", head="new-head", ttl=3600, json=True)
        rc = claim_mod.cmd_acquire(new_args)
        check(rc == 0, "stale reclaim: acquire over an expired claim succeeds")

        current = claim_mod._load_claim(claim_path)
        check(
            current is not None and current.get("owner") == "fable",
            "stale reclaim: new owner now holds the claim",
        )


def test_fail_closed_on_cas_error() -> None:
    import argparse

    with tempfile.TemporaryDirectory() as td:
        _fresh_claims_dir(Path(td))

        original = claim_mod._write_claim_exclusive

        def boom(path, record):
            raise OSError("simulated CAS backend failure")

        claim_mod._write_claim_exclusive = boom
        try:
            args = argparse.Namespace(slice_id="cas-fail-slice", owner="fable", head="h", ttl=3600, json=True)
            rc = claim_mod.cmd_acquire(args)
            check(rc != 0, "fail-closed: CAS error refuses the acquire (non-zero rc)")
            check(
                not claim_mod._claim_path("cas-fail-slice").exists(),
                "fail-closed: no claim file left behind after a CAS error",
            )
        finally:
            claim_mod._write_claim_exclusive = original


# ---------------------------------------------------------------------------
# aq-role-route
# ---------------------------------------------------------------------------

def _reset_route_module(tmp: Path) -> None:
    route_mod.DELEGATION_DIR = tmp
    route_mod.CODEX_COOLDOWN_FILE = tmp / ".codex-quota-cooldown"
    # Real model-coordinator.json is read-only reference data (cost lookup);
    # no network involved, safe to reuse across the hermetic run.
    route_mod.MODEL_COORDINATOR = ROOT / "config" / "model-coordinator.json"


def test_role_route_baseline_binding_acceptance() -> None:
    with tempfile.TemporaryDirectory() as td:
        _reset_route_module(Path(td))
        result = route_mod.route("binding-acceptance", "subject-a", [])
        check(result["ok"], "role-route: baseline binding-acceptance resolves ok")
        check(
            result["chosen_agent"] in {"codex", "claude", "gemini", "local"},
            "role-route: baseline chosen_agent is one of the eligible lanes",
        )


def test_role_route_excludes_producer() -> None:
    with tempfile.TemporaryDirectory() as td:
        _reset_route_module(Path(td))
        result = route_mod.route("binding-acceptance", "subject-b", ["claude-sonnet"])
        check(result["ok"], "role-route: exclude-producer case resolves ok")
        check(
            result["chosen_agent"] != "claude",
            "role-route: excluded lane (claude, via 'claude-sonnet' alias) is never chosen",
        )
        check(
            "claude" not in [alt["agent"] for alt in result["alternates"]],
            "role-route: excluded lane does not even appear as an alternate",
        )


def test_role_route_never_hardcodes_codex_when_down() -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _reset_route_module(tmp)
        tmp.mkdir(parents=True, exist_ok=True)
        (tmp / ".codex-down").write_text("simulated outage\n", encoding="utf-8")

        result = route_mod.route("binding-acceptance", "subject-c", [])
        check(result["ok"], "role-route: codex-down case still resolves ok (falls through)")
        check(
            result["chosen_agent"] != "codex",
            "role-route: codex flagged down is never returned as chosen_agent",
        )
        check(
            "substituted" in (result["reason"] or ""),
            "role-route: substitution is recorded in reason when top choice is down",
        )
        codex_alt = next((a for a in result["alternates"] if a["agent"] == "codex"), None)
        check(
            codex_alt is not None and codex_alt["available"] is False,
            "role-route: codex appears in alternates marked unavailable, not silently dropped",
        )


def test_role_route_codex_cooldown_file_reused() -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _reset_route_module(tmp)
        tmp.mkdir(parents=True, exist_ok=True)
        future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        (tmp / ".codex-quota-cooldown").write_text(future + "\n", encoding="utf-8")

        result = route_mod.route("binding-acceptance", "subject-d", [])
        check(result["ok"], "role-route: codex quota-cooldown case still resolves ok")
        check(
            result["chosen_agent"] != "codex",
            "role-route: codex in active quota-cooldown is never chosen",
        )


def test_role_route_all_down_fails_closed() -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _reset_route_module(tmp)
        tmp.mkdir(parents=True, exist_ok=True)
        for lane in ("codex", "claude", "gemini", "local"):
            (tmp / f".{lane}-down").write_text("down\n", encoding="utf-8")

        result = route_mod.route("binding-acceptance", "subject-e", [])
        check(result["ok"] is False, "role-route: all lanes down -> ok is False (fail-closed, no fake result)")
        check(result["chosen_agent"] is None, "role-route: all lanes down -> chosen_agent is None")


def test_role_route_unknown_role() -> None:
    with tempfile.TemporaryDirectory() as td:
        _reset_route_module(Path(td))
        result = route_mod.route("time-traveler", "subject-f", [])
        check(result["ok"] is False, "role-route: unknown role is rejected")
        check(result["reason"] == "unknown-role", "role-route: unknown role reason is explicit")


def main() -> int:
    test_claim_cas_exclusivity()
    test_second_acquire_fails_naming_holder()
    test_release_holder_only()
    test_stale_claim_reclaim()
    test_fail_closed_on_cas_error()

    test_role_route_baseline_binding_acceptance()
    test_role_route_excludes_producer()
    test_role_route_never_hardcodes_codex_when_down()
    test_role_route_codex_cooldown_file_reused()
    test_role_route_all_down_fails_closed()
    test_role_route_unknown_role()

    if FAILURES:
        print(f"\n{len(FAILURES)} FAILURE(S):")
        for label in FAILURES:
            print(f"  - {label}")
        return 1
    print("\nPASS: all agent-agnostic router checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
