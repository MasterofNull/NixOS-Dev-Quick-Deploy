"""dispatch_consult — shared router/claim consult library for live dispatch.

DESIGN SSOT: `.agents/plans/agent-agnostic-factory/DISPATCH-INTEGRATION-DESIGN.md`.

Makes `aq-role-route` (lane selection) and `aq-slice-claim` (single-owner
locking) fire automatically on real dispatches instead of depending on an
orchestrator invoking them by hand. This module is the ONE small library
every lane's dispatch shim can call — see the design doc's "Reference
integration" section for the local-lane wiring (`lib/dispatch.py`).

FAIL-OPEN, ADVISORY (hard requirement): if either external tool is missing,
errors, times out, or returns unparseable output, `consult_before_dispatch`
returns `ok=True, degraded=True` and the caller's dispatch PROCEEDS. This
layer must NEVER be able to block a live dispatch because of its own
failure — only an explicit `already-held` response from a HEALTHY
`aq-slice-claim` blocks.

Substitution is surfaced, never silently applied: if `aq-role-route` names a
different lane than the caller's `requested_lane`, that is recorded in the
result (`routed_lane` + `substituted` + `reason`) but the claim is still
acquired for `requested_lane` — this module never redirects the caller's own
dispatch to a different lane; it only tells the caller what the router
thinks and lets the caller's own policy (if any) act on it.

No network, no credentials. Subprocess calls to the two tools always use
absolute paths resolved from this file's directory; never `shell=True`.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Optional

_HERE = Path(__file__).resolve().parent
_SCRIPTS_AI = _HERE.parent  # scripts/ai/lib -> scripts/ai
ROLE_ROUTE_BIN = _SCRIPTS_AI / "aq-role-route"
SLICE_CLAIM_BIN = _SCRIPTS_AI / "aq-slice-claim"

DEFAULT_SUBPROCESS_TIMEOUT = 8.0


@dataclass
class ConsultResult:
    """Outcome of a router+claim consult. `blocked` is the ONLY signal a
    caller should treat as "do not launch" — everything else (including
    `degraded=True`) means proceed."""

    ok: bool
    blocked: bool = False
    degraded: bool = False
    reason: Optional[str] = None
    routed_lane: Optional[str] = None
    requested_lane: Optional[str] = None
    substituted: bool = False
    claim_token: Optional[str] = None  # subject id, opaque to the caller
    claim_owner: Optional[str] = None  # owner string the claim was acquired under
    current_owner: Optional[str] = None  # set only when blocked (already-held)
    raw_route: Optional[dict[str, Any]] = None
    raw_claim: Optional[dict[str, Any]] = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "blocked": self.blocked,
            "degraded": self.degraded,
            "reason": self.reason,
            "routed_lane": self.routed_lane,
            "requested_lane": self.requested_lane,
            "substituted": self.substituted,
            "claim_token": self.claim_token,
            "claim_owner": self.claim_owner,
            "current_owner": self.current_owner,
        }


def _run_tool(
    bin_path: Path, args: list[str], *, timeout: float = DEFAULT_SUBPROCESS_TIMEOUT
) -> tuple[bool, Optional[dict[str, Any]], Optional[str]]:
    """Run one of the consult tools via an absolute path. Never raises —
    any failure surfaces as (False, None, <short reason>). `shell=True` is
    never used; the interpreter + absolute script path are passed as an
    argv list."""
    try:
        proc = subprocess.run(
            [sys.executable, str(bin_path), *args],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        return False, None, f"tool-missing:{bin_path.name}"
    except subprocess.TimeoutExpired:
        return False, None, f"tool-timeout:{bin_path.name}"
    except OSError as exc:
        return False, None, f"tool-error:{bin_path.name}:{exc}"

    raw = (proc.stdout or "").strip()
    if not raw:
        err = (proc.stderr or "").strip()[:160]
        return False, None, f"tool-empty-output:{bin_path.name}:{err}"
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return False, None, f"tool-unparseable-output:{bin_path.name}"
    if not isinstance(payload, dict):
        return False, None, f"tool-unparseable-output:{bin_path.name}"
    return True, payload, None


def _degrade_or_block(
    reason: str,
    *,
    fail_open: bool,
    routed_lane: Optional[str],
    requested_lane: str,
    substituted: bool,
    raw_route: Optional[dict[str, Any]] = None,
    raw_claim: Optional[dict[str, Any]] = None,
) -> ConsultResult:
    """Single decision point for every "tool problem" branch (missing,
    erroring, timed out, unparseable, or a non-already-held claim failure).

    With `fail_open=True` (the only value any production caller ever
    passes) this ALWAYS degrades to `ok=True` and the caller proceeds.
    `fail_open=False` exists solely so the test suite can prove the
    fail-open branch is load-bearing (test 4's negative control): same
    inputs, only the flag differs, and the outcome flips from
    proceed-degraded to blocked. No production code path ever sets it.
    """
    if fail_open:
        return ConsultResult(
            ok=True,
            degraded=True,
            reason=reason,
            routed_lane=routed_lane,
            requested_lane=requested_lane,
            substituted=substituted,
            raw_route=raw_route,
            raw_claim=raw_claim,
        )
    return ConsultResult(
        ok=False,
        blocked=True,
        degraded=False,
        reason=f"no-fail-open-would-block:{reason}",
        routed_lane=routed_lane,
        requested_lane=requested_lane,
        substituted=substituted,
        raw_route=raw_route,
        raw_claim=raw_claim,
    )


def consult_before_dispatch(
    subject: str,
    role: str,
    requested_lane: str,
    head: Optional[str] = None,
    *,
    ttl: Optional[int] = None,
    exclude: Optional[list[str]] = None,
    timeout: float = DEFAULT_SUBPROCESS_TIMEOUT,
    role_route_bin: Path = ROLE_ROUTE_BIN,
    slice_claim_bin: Path = SLICE_CLAIM_BIN,
    _fail_open: bool = True,
) -> ConsultResult:
    """Consult `aq-role-route` then `aq-slice-claim` before a live dispatch.

    Returns a `ConsultResult`. Callers must check `.blocked` — that is the
    only field meaning "refuse to launch"; `ok=True` (including
    `degraded=True`) always means proceed.

    `role_route_bin` / `slice_claim_bin` / `_fail_open` are override points
    for tests only; production callers never pass them.
    """
    if not subject or not role or not requested_lane:
        return ConsultResult(
            ok=True, degraded=True, reason="missing-required-arg-degraded",
            requested_lane=requested_lane,
        )

    # 1. Route: ask which lane is eligible+available+cheapest for this role.
    # A substitution here is advisory only — this module never redirects the
    # caller's own dispatch, it only surfaces what the router thinks.
    route_args = [role, "--subject", subject, "--json"]
    if exclude:
        route_args += ["--exclude", *exclude]
    route_ok, route_payload, route_err = _run_tool(role_route_bin, route_args, timeout=timeout)

    if not route_ok:
        return _degrade_or_block(
            f"route-degraded:{route_err}",
            fail_open=_fail_open,
            routed_lane=None,
            requested_lane=requested_lane,
            substituted=False,
        )

    routed_lane = requested_lane
    substituted = False
    route_reason = None
    if not route_payload.get("ok", False):
        return _degrade_or_block(
            f"route-degraded:{route_payload.get('reason', 'route-not-ok')}",
            fail_open=_fail_open,
            routed_lane=None,
            requested_lane=requested_lane,
            substituted=False,
            raw_route=route_payload,
        )

    chosen = route_payload.get("chosen_agent")
    if chosen:
        routed_lane = chosen
        if chosen != requested_lane:
            substituted = True
            route_reason = (
                f"router chose '{chosen}' over requested '{requested_lane}': "
                f"{route_payload.get('reason')}"
            )

    # 2. Claim: the requested lane (the caller's own identity), never the
    # routed lane — substitution is advisory, not an override (see module
    # docstring).
    owner = requested_lane
    claim_args = ["acquire", subject, "--owner", owner, "--json"]
    if head:
        claim_args += ["--head", head]
    if ttl:
        claim_args += ["--ttl", str(ttl)]
    claim_ok, claim_payload, claim_err = _run_tool(slice_claim_bin, claim_args, timeout=timeout)

    if not claim_ok:
        return _degrade_or_block(
            f"claim-degraded:{claim_err}",
            fail_open=_fail_open,
            routed_lane=routed_lane,
            requested_lane=requested_lane,
            substituted=substituted,
            raw_route=route_payload,
        )

    if claim_payload.get("ok"):
        return ConsultResult(
            ok=True,
            degraded=False,
            reason=route_reason,
            routed_lane=routed_lane,
            requested_lane=requested_lane,
            substituted=substituted,
            claim_token=subject,
            claim_owner=owner,
            raw_route=route_payload,
            raw_claim=claim_payload,
        )

    if claim_payload.get("reason") == "already-held":
        # A HEALTHY claim tool reporting a real hold — this is the ONE case
        # that blocks unconditionally, regardless of _fail_open.
        return ConsultResult(
            ok=False,
            blocked=True,
            degraded=False,
            reason="already-held",
            routed_lane=routed_lane,
            requested_lane=requested_lane,
            substituted=substituted,
            current_owner=claim_payload.get("current_owner"),
            raw_route=route_payload,
            raw_claim=claim_payload,
        )

    # Any other non-ok claim reason (invalid-slice-id, cas-error,
    # corrupt-claim-refuse, transient-race-retry, ...) is a tool-health
    # problem, not a legitimate hold by another owner — fail open.
    return _degrade_or_block(
        f"claim-degraded:{claim_payload.get('reason')}",
        fail_open=_fail_open,
        routed_lane=routed_lane,
        requested_lane=requested_lane,
        substituted=substituted,
        raw_route=route_payload,
        raw_claim=claim_payload,
    )


def release_after_dispatch(
    result: ConsultResult,
    *,
    timeout: float = DEFAULT_SUBPROCESS_TIMEOUT,
    slice_claim_bin: Path = SLICE_CLAIM_BIN,
) -> bool:
    """Best-effort release of a claim acquired via `consult_before_dispatch`.

    No-ops (returns False) when there is nothing to release: a blocked
    consult never acquired a claim (someone else holds it — releasing would
    be releasing another owner's claim, which `aq-slice-claim release`
    itself refuses via `not-holder`), and a degraded consult with no
    `claim_token` never got as far as a successful acquire either. Never
    raises.
    """
    if result is None or not result.claim_token or not result.claim_owner:
        return False
    ok, payload, _err = _run_tool(
        slice_claim_bin,
        ["release", result.claim_token, "--owner", result.claim_owner, "--json"],
        timeout=timeout,
    )
    if not ok or payload is None:
        return False
    return bool(payload.get("ok"))


@contextlib.contextmanager
def dispatch_consult(
    subject: str,
    role: str,
    requested_lane: str,
    head: Optional[str] = None,
    *,
    ttl: Optional[int] = None,
    exclude: Optional[list[str]] = None,
    timeout: float = DEFAULT_SUBPROCESS_TIMEOUT,
    role_route_bin: Path = ROLE_ROUTE_BIN,
    slice_claim_bin: Path = SLICE_CLAIM_BIN,
) -> Iterator[ConsultResult]:
    """Context-manager sugar: consult on enter, release on exit (normal exit
    AND exception). Yields the `ConsultResult` — the caller MUST check
    `.blocked` itself before doing any launch work inside the `with` block;
    this context manager does not raise or otherwise prevent entry on a
    blocked result, it only guarantees release happens (when there was
    anything to release) no matter how the `with` block exits.
    """
    result = consult_before_dispatch(
        subject,
        role,
        requested_lane,
        head,
        ttl=ttl,
        exclude=exclude,
        timeout=timeout,
        role_route_bin=role_route_bin,
        slice_claim_bin=slice_claim_bin,
    )
    try:
        yield result
    finally:
        if not result.blocked:
            release_after_dispatch(result, timeout=timeout, slice_claim_bin=slice_claim_bin)


# ── CLI — resolution B shim seam ────────────────────────────────────────────
# Amendment (see DISPATCH-INTEGRATION-DESIGN.md "Amendment: resolution B"):
# dispatch.py is pinned by the L2B frozen-source manifest and stays untouched.
# This CLI is the ONLY new surface — a thin wrapper so bash `delegate-to-*`
# shims (non-frozen) can call the same consult/release logic as a subprocess,
# without any lane needing a Python import. The library functions above are
# unchanged; this section only adds argv/stdout plumbing around them.


def _cli_consult(args: argparse.Namespace) -> int:
    """Print a ConsultResult as JSON; exit 0 to proceed, 3 when blocked.
    Never lets an internal exception propagate — a crash here must never be
    able to block a caller's dispatch, so any exception degrades to the same
    ok=True/degraded=True shape consult_before_dispatch itself would return
    for a tool-health problem."""
    try:
        result = consult_before_dispatch(
            args.subject,
            args.role,
            args.lane,
            args.head,
            ttl=args.ttl,
            exclude=args.exclude,
            role_route_bin=Path(args.role_route_bin) if args.role_route_bin else ROLE_ROUTE_BIN,
            slice_claim_bin=Path(args.slice_claim_bin) if args.slice_claim_bin else SLICE_CLAIM_BIN,
        )
    except Exception as exc:  # noqa: BLE001 - deliberate catch-all, see docstring
        fallback = ConsultResult(
            ok=True, degraded=True, reason=f"cli-exception-degraded:{exc}",
            requested_lane=args.lane,
        )
        print(json.dumps(fallback.as_dict()))
        return 0

    print(json.dumps(result.as_dict()))
    return 3 if result.blocked else 0


def _cli_release(args: argparse.Namespace) -> int:
    """Best-effort release of a claim previously acquired via `consult`.
    Always exits 0 — a release-side failure is never grounds to fail a
    caller's shell script after its dispatch already ran."""
    payload: dict[str, Any]
    try:
        fake_result = ConsultResult(ok=True, claim_token=args.subject, claim_owner=args.owner)
        slice_claim_bin = Path(args.slice_claim_bin) if args.slice_claim_bin else SLICE_CLAIM_BIN
        released = release_after_dispatch(fake_result, slice_claim_bin=slice_claim_bin)
        payload = {"ok": bool(released), "subject": args.subject, "owner": args.owner}
    except Exception as exc:  # noqa: BLE001 - best-effort, see docstring
        payload = {
            "ok": False, "subject": args.subject, "owner": args.owner,
            "reason": f"cli-exception:{exc}",
        }
    print(json.dumps(payload))
    return 0


def _build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dispatch_consult.py",
        description=(
            "Thin CLI wrapper over consult_before_dispatch()/release_after_dispatch() "
            "so non-Python delegate-to-* shims can drive the same router/claim consult."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    consult_p = sub.add_parser("consult", help="Consult router+claim before a live dispatch.")
    consult_p.add_argument("--subject", required=True)
    consult_p.add_argument("--role", required=True)
    consult_p.add_argument("--lane", required=True)
    consult_p.add_argument("--head", default=None)
    consult_p.add_argument("--ttl", type=int, default=None)
    consult_p.add_argument("--exclude", action="append", default=None)
    # Test-only override points, mirroring consult_before_dispatch's own
    # role_route_bin/slice_claim_bin kwargs. Production callers never pass these.
    consult_p.add_argument("--role-route-bin", default=None, help=argparse.SUPPRESS)
    consult_p.add_argument("--slice-claim-bin", default=None, help=argparse.SUPPRESS)
    consult_p.set_defaults(func=_cli_consult)

    release_p = sub.add_parser("release", help="Best-effort release of a claim acquired via consult.")
    release_p.add_argument("--subject", required=True)
    release_p.add_argument("--owner", required=True)
    release_p.add_argument("--slice-claim-bin", default=None, help=argparse.SUPPRESS)
    release_p.set_defaults(func=_cli_release)

    return parser


def _main(argv: Optional[list[str]] = None) -> int:
    parser = _build_cli_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(_main())
