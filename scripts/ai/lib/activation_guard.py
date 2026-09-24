"""activation_guard — dead-man auto-revert guard for enforcement activations.

Foundation C SAFETY layer (owner-directed 2026-09-24). Purpose: when a security
enforcement control is switched ON, auto-revert it OFF if the system does not
stay healthy within a bounded window, so a bad activation self-heals without a
human catching it. This ADDS a layer; it never replaces the existing manual
kill-switches (CAPABILITY_LEASE_ENFORCEMENT / CAPABILITY_CELL_ADAPTER env flags
in nix/modules/services/switchboard.nix, the C6 `aq-epoch-bump` lever) or the
health-spider/dashboard health signals — this module composes with those, it
does not reimplement them.

Generic by design: this file has NO per-control knowledge (no C6-specific or
C2-specific branches). Every armed activation carries its OWN health-check
command and its OWN revert command, supplied by the caller at `arm` time — the
exact documented kill action a human would run for that control. That is a
deliberate scope decision (see module docstring in aq-activation-guard): a
hardcoded per-control registry would need to grow with every new control and
would silently go stale; a caller-supplied command composes with anything
(health-spider check, dashboard curl, systemctl, aq-epoch-bump, a kill-file
write) without this module ever being touched again.

State machine (see aq-activation-guard for the CLI):
  arm     -> durable armed/<control-id>.json record (0600), deadline = now + window
  confirm -> human (or any external automation) cancels the auto-revert early
  disarm  -> same as confirm, explicit "no action needed" framing
  sweep   -> run by the systemd timer; for every armed record past its
             deadline: health GREEN -> auto-confirm; NOT-GREEN or the health
             check itself failing/erroring/timing out -> execute revert_cmd +
             emit a LOUD alert. FAIL-SAFE: any ambiguity (can't read health,
             internal error) resolves to the revert+alert branch, never to
             silently leaving a bad activation armed and untouched.

Events are emitted via the `aq-event` CLI (the canonical event spine) —
PULSE/RESUME are projections and are never hand-written here. Event emission
is best-effort and MUST NOT block or swallow the safety action: an alert that
fails to emit is logged to stderr (journald under systemd) and to a local
fallback file so it is never silently lost.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_HERE = Path(__file__).resolve().parent
_AQ_EVENT_BIN = _HERE.parent / "aq-event"

DEFAULT_STATE_DIR = "/var/lib/aq-activation-guard"
ARMED_SUBDIR = "armed"
HISTORY_FILE = "history.jsonl"
EMIT_FAILURES_FILE = "emit-failures.log"

SCHEMA_VERSION = "aq.activation-guard.armed/1"

_CONTROL_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")

HEALTH_GREEN = "green"
HEALTH_RED = "red"
HEALTH_UNREADABLE = "unreadable"


class ActivationGuardError(Exception):
    """Caller-facing error (bad control-id, already-armed, not-armed, ...)."""


def _now() -> float:
    return time.time()


def _iso(epoch: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(epoch))


def state_dir(override: Optional[str] = None) -> Path:
    """Resolve the state directory: explicit arg > env > default.

    Never creates the directory itself — that is a Nix `systemd.tmpfiles.rules`
    declaration (Rule 13, declarative-only) when running under the systemd
    module; callers running standalone (tests, ad-hoc CLI use) create it via
    `_ensure_dir`.
    """
    if override:
        return Path(override)
    env = os.environ.get("AQ_ACTIVATION_GUARD_STATE_DIR")
    if env:
        return Path(env)
    return Path(DEFAULT_STATE_DIR)


def _ensure_dir(path: Path, mode: int = 0o700) -> None:
    path.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path, mode)
    except OSError:
        # Best-effort — under the NixOS module the mode is already set by
        # systemd.tmpfiles.rules; a permission failure here just means we
        # can't tighten it further from an unprivileged context (tests).
        pass


def _armed_dir(sdir: Path) -> Path:
    d = sdir / ARMED_SUBDIR
    _ensure_dir(d)
    return d


def _validate_control_id(control_id: str) -> str:
    if not control_id or not _CONTROL_ID_RE.match(control_id):
        raise ActivationGuardError(
            f"invalid control-id {control_id!r} — must match {_CONTROL_ID_RE.pattern} "
            "(prevents path traversal via the armed-record filename)"
        )
    return control_id


def _armed_path(sdir: Path, control_id: str) -> Path:
    return _armed_dir(sdir) / f"{_validate_control_id(control_id)}.json"


def _write_json_atomic(path: Path, data: Dict[str, Any], mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp{os.getpid()}")
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)
            f.write("\n")
        os.replace(tmp, path)
    except BaseException:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise


def _append_history(sdir: Path, record: Dict[str, Any]) -> None:
    _ensure_dir(sdir)
    path = sdir / HISTORY_FILE
    line = json.dumps(record, sort_keys=True)
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        with os.fdopen(fd, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def _log_emit_failure(sdir: Path, event_type: str, subject: str, detail: str) -> None:
    msg = f"[activation-guard] CRITICAL: aq-event emit failed type={event_type} subject={subject} detail={detail}"
    # journald captures stderr when this runs under the systemd service — this
    # is the last-resort visibility path if the event spine itself is down.
    print(msg, file=sys.stderr)
    try:
        _ensure_dir(sdir)
        with open(sdir / EMIT_FAILURES_FILE, "a", encoding="utf-8") as f:
            f.write(f"{_now():.0f} {msg}\n")
    except OSError:
        pass


def emit_event(
    agent: str,
    event_type: str,
    subject: str,
    payload: Dict[str, Any],
    sdir: Optional[Path] = None,
) -> bool:
    """Best-effort emit via the `aq-event` CLI. Never raises.

    Module-level function (not a method) so tests can monkeypatch
    `activation_guard.emit_event` directly without touching the real event
    log or spawning a subprocess.
    """
    sdir = sdir or state_dir()
    try:
        r = subprocess.run(
            [
                sys.executable,
                str(_AQ_EVENT_BIN),
                "emit",
                "--agent", agent,
                "--type", event_type,
                "--subject", subject,
                "--payload", json.dumps(payload),
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if r.returncode != 0:
            _log_emit_failure(sdir, event_type, subject, r.stderr.strip() or f"rc={r.returncode}")
            return False
        return True
    except Exception as exc:  # noqa: BLE001 — alerting must never blow up the guard
        _log_emit_failure(sdir, event_type, subject, str(exc))
        return False


def emit_pulse(agent: str, action: str, scope: str, outcome: str, sdir: Optional[Path] = None) -> bool:
    """Best-effort `aq-event pulse` (Rule 8a). Never raises."""
    sdir = sdir or state_dir()
    try:
        r = subprocess.run(
            [
                sys.executable, str(_AQ_EVENT_BIN), "pulse",
                "--agent", agent, "--action", action, "--scope", scope, "--outcome", outcome,
            ],
            capture_output=True, text=True, timeout=15,
        )
        return r.returncode == 0
    except Exception:  # noqa: BLE001
        return False


# ── arm / confirm / disarm ──────────────────────────────────────────────────


def arm(
    control_id: str,
    window_minutes: float,
    health_check_cmd: str,
    revert_cmd: str,
    agent: str = "operator",
    reason: Optional[str] = None,
    sdir: Optional[Path] = None,
    force: bool = False,
) -> Dict[str, Any]:
    control_id = _validate_control_id(control_id)
    if window_minutes <= 0:
        raise ActivationGuardError("--window must be a positive number of minutes")
    if not health_check_cmd or not health_check_cmd.strip():
        raise ActivationGuardError(
            "arm refused: no --health-check supplied — a dead-man guard with no health "
            "signal has nothing to decide on (fail-safe: refuse to arm rather than arm blind)"
        )
    if not revert_cmd or not revert_cmd.strip():
        raise ActivationGuardError(
            "arm refused: no --revert-cmd supplied — this guard is generic and carries no "
            "built-in per-control revert knowledge; arming without the exact documented kill "
            "action would leave the fail-safe branch with nothing to execute"
        )

    sdir = sdir or state_dir()
    path = _armed_path(sdir, control_id)
    if path.exists() and not force:
        raise ActivationGuardError(
            f"control {control_id!r} is already armed ({path}); confirm/disarm it first or pass force=True"
        )

    now = _now()
    record = {
        "schema_version": SCHEMA_VERSION,
        "control_id": control_id,
        "armed_at": _iso(now),
        "armed_at_epoch": now,
        "window_minutes": window_minutes,
        "deadline_epoch": now + (window_minutes * 60.0),
        "health_check_cmd": health_check_cmd,
        "revert_cmd": revert_cmd,
        "agent": agent,
        "reason": reason,
        "state": "armed",
    }
    _write_json_atomic(path, record)
    emit_event(
        agent, "activation.armed", control_id,
        {
            "control_id": control_id, "window_minutes": window_minutes,
            "deadline_epoch": record["deadline_epoch"], "health_check_cmd": health_check_cmd,
            "revert_cmd": revert_cmd, "reason": reason,
        },
        sdir=sdir,
    )
    return record


def _terminate(
    control_id: str, new_state: str, event_type: str, agent: str, sdir: Path,
    extra: Optional[Dict[str, Any]] = None, loud: bool = False,
) -> Dict[str, Any]:
    """Move an armed record to terminal state: append to history, remove the armed file."""
    path = _armed_path(sdir, control_id)
    if not path.exists():
        raise ActivationGuardError(f"control {control_id!r} is not currently armed (no {path})")
    record = json.loads(path.read_text(encoding="utf-8"))
    record["state"] = new_state
    record["resolved_at"] = _iso(_now())
    record["resolved_at_epoch"] = _now()
    if extra:
        record.update(extra)
    _append_history(sdir, record)
    try:
        path.unlink()
    except OSError:
        pass
    payload = {"control_id": control_id, "state": new_state}
    if extra:
        payload.update({k: v for k, v in extra.items() if k not in ("revert_cmd",) or loud})
    emit_event(agent, event_type, control_id, payload, sdir=sdir)
    if loud:
        emit_pulse(agent, new_state, control_id, json.dumps(payload)[:400])
    return record


def confirm(control_id: str, agent: str = "operator", sdir: Optional[Path] = None) -> Dict[str, Any]:
    sdir = sdir or state_dir()
    return _terminate(
        control_id, "confirmed", "activation.confirmed", agent, sdir,
        extra={"confirm_source": "manual"},
    )


def disarm(
    control_id: str, agent: str = "operator", reason: Optional[str] = None, sdir: Optional[Path] = None,
) -> Dict[str, Any]:
    sdir = sdir or state_dir()
    return _terminate(
        control_id, "disarmed", "activation.disarmed", agent, sdir,
        extra={"disarm_reason": reason},
    )


def list_armed(sdir: Optional[Path] = None) -> List[Dict[str, Any]]:
    sdir = sdir or state_dir()
    d = _armed_dir(sdir)
    out = []
    for p in sorted(d.glob("*.json")):
        try:
            out.append(json.loads(p.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    return out


# ── health-check / revert execution ─────────────────────────────────────────


def run_health_check(cmd: str, timeout: int = 30) -> Tuple[str, Dict[str, Any]]:
    """Run the armed activation's health-check command.

    Returns (status, detail) where status is one of HEALTH_GREEN / HEALTH_RED /
    HEALTH_UNREADABLE. Exit code 0 == GREEN; any other exit code == RED.
    ANY exception (bad command, timeout, permission error, missing binary) is
    caught here and mapped to UNREADABLE — this is the fail-safe boundary:
    the caller (sweep) treats RED and UNREADABLE identically (revert+alert),
    so a broken health probe can never be mistaken for a healthy system.
    """
    if not cmd or not cmd.strip():
        return HEALTH_UNREADABLE, {"error": "no health_check_cmd configured"}
    try:
        r = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout,
        )
        detail = {
            "returncode": r.returncode,
            "stdout": r.stdout[-2000:],
            "stderr": r.stderr[-2000:],
        }
        return (HEALTH_GREEN if r.returncode == 0 else HEALTH_RED), detail
    except subprocess.TimeoutExpired as exc:
        return HEALTH_UNREADABLE, {"error": f"health check timed out after {timeout}s: {exc}"}
    except Exception as exc:  # noqa: BLE001 — fail-safe: any error == unreadable, never crash the sweep
        return HEALTH_UNREADABLE, {"error": f"health check raised: {exc}"}


def run_revert(cmd: str, timeout: int = 60) -> Dict[str, Any]:
    """Execute the armed activation's documented revert command.

    Never raises — always returns a result dict so the caller can proceed to
    alert regardless of whether the revert itself succeeded. A revert that
    fails to execute is still a LOUD event (arguably louder): the operator
    needs to know the auto-heal did NOT happen, not have it disappear.
    """
    if not cmd or not cmd.strip():
        return {"ok": False, "error": "no revert_cmd configured"}
    try:
        r = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout,
        )
        return {
            "ok": r.returncode == 0,
            "returncode": r.returncode,
            "stdout": r.stdout[-2000:],
            "stderr": r.stderr[-2000:],
        }
    except subprocess.TimeoutExpired as exc:
        return {"ok": False, "error": f"revert command timed out after {timeout}s: {exc}"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"revert command raised: {exc}"}


# ── sweep (the dead-man enforcement pass, run by the systemd timer) ────────


def sweep(
    sdir: Optional[Path] = None,
    now: Optional[float] = None,
    health_timeout: int = 30,
    revert_timeout: int = 60,
    agent: str = "activation-guard-timer",
) -> List[Dict[str, Any]]:
    """Process every armed record whose deadline has passed.

    FAIL-SAFE CONTRACT (the property this module exists for): for any record
    past its deadline, the ONLY way to end up NOT reverted is an explicit,
    successfully-read GREEN health check. Every other outcome — RED, an
    unreadable/erroring health check, a corrupt armed record, or an
    unexpected exception anywhere in this function — resolves toward
    executing the revert command and emitting a LOUD alert. Never toward
    silently leaving a bad activation on.

    This is a thin wrapper around `_sweep_inner`: a total sweep failure (an
    exception BEFORE the per-record try/except below is even reached — e.g.
    the armed-dir listing/mkdir failing, a permissions problem on the state
    dir) would otherwise be a silent stack trace in a systemd timer's
    journald output that nobody is watching in real time. Catching it here
    and routing it through the same `emit_event`/`emit_pulse` LOUD-alert path
    the per-record auto-revert branch uses means "the guard itself died" gets
    exactly as much visibility as "a control got reverted" — both are things
    an operator must see, and both use one alerting path instead of two.
    """
    sdir = sdir or state_dir()
    now = _now() if now is None else now
    try:
        return _sweep_inner(sdir, now, health_timeout, revert_timeout, agent)
    except Exception as exc:  # noqa: BLE001 — the guard itself must never die quietly
        detail = {"error": str(exc), "error_type": type(exc).__name__, "state_dir": str(sdir)}
        emit_event(agent, "activation.sweep-failed", "sweep", detail, sdir=sdir)
        emit_pulse(agent, "sweep-failed", "activation-guard", f"total sweep failure: {exc}"[:400])
        return [{"control_id": None, "action": "sweep-failed", "ok": False, "error": str(exc)}]


def _sweep_inner(
    sdir: Path,
    now: float,
    health_timeout: int,
    revert_timeout: int,
    agent: str,
) -> List[Dict[str, Any]]:
    """The actual sweep pass — see `sweep()` for the fail-safe contract and
    the total-failure catch-all this is wrapped by."""
    results: List[Dict[str, Any]] = []

    for p in sorted(_armed_dir(sdir).glob("*.json")):
        control_id = p.stem
        try:
            record = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            # Can't even parse the armed record — worst case: we don't know the
            # revert command. We CANNOT invent one (this module has no per-control
            # knowledge), so this is the one case that cannot self-heal via revert.
            # It still gets the loudest possible alert and is left armed (never
            # silently dropped) so a human has to intervene.
            emit_event(
                agent, "activation.guard_internal_error", control_id,
                {"error": f"corrupt armed record: {exc}", "path": str(p)}, sdir=sdir,
            )
            results.append({"control_id": control_id, "action": "error", "ok": False, "error": str(exc)})
            continue

        deadline = record.get("deadline_epoch", 0)
        if deadline > now:
            results.append({"control_id": control_id, "action": "not-due", "ok": True})
            continue

        try:
            health_status, health_detail = run_health_check(record.get("health_check_cmd", ""), timeout=health_timeout)
        except Exception as exc:  # noqa: BLE001 — belt-and-braces: run_health_check already
            # catches everything, but if IT somehow raises, still fail toward unreadable.
            health_status, health_detail = HEALTH_UNREADABLE, {"error": f"health check dispatch raised: {exc}"}

        if health_status == HEALTH_GREEN:
            try:
                _terminate(
                    control_id, "confirmed", "activation.confirmed", agent, sdir,
                    extra={"confirm_source": "auto-health-green", "health_detail": health_detail},
                )
                results.append({"control_id": control_id, "action": "confirmed", "ok": True, "health_status": health_status})
            except Exception as exc:  # noqa: BLE001 — if we can't even record the confirm cleanly,
                # do NOT leave it ambiguous: fall through to revert+alert instead of trusting a
                # write we couldn't verify.
                revert_result = run_revert(record.get("revert_cmd", ""), timeout=revert_timeout)
                emit_event(
                    agent, "activation.auto-reverted", control_id,
                    {
                        "reason": "health_green_but_confirm_write_failed", "confirm_error": str(exc),
                        "revert_result": revert_result,
                    },
                    sdir=sdir,
                )
                emit_pulse(agent, "auto-reverted", control_id, f"confirm-write-failed:{exc}")
                results.append({
                    "control_id": control_id, "action": "auto-reverted", "ok": revert_result.get("ok", False),
                    "health_status": health_status, "revert_result": revert_result,
                    "note": "confirm write failed after GREEN health — reverted out of caution",
                })
            continue

        # RED or UNREADABLE — identical fail-safe handling.
        #
        # Disarm-race guard: the health check above can take up to
        # health_timeout seconds, during which a human (or other automation)
        # may have legitimately confirmed/disarmed this exact control — the
        # armed record would then already be gone. Re-check existence
        # IMMEDIATELY before executing revert_cmd so that a legitimate,
        # in-window cancellation does not also earn an unnecessary revert.
        # FAIL-SAFE: if the existence re-check itself raises (e.g. EACCES on
        # the armed dir), that is NOT evidence of a legitimate disarm — treat
        # it as still-armed and fall through to revert+alert exactly as
        # before. This check may only SKIP a revert when it has positive
        # proof (a clean, successful "file is gone") that the record was
        # resolved elsewhere; it must never become a new way to suppress a
        # needed revert.
        try:
            still_armed = p.exists()
        except Exception:  # noqa: BLE001 — can't tell -> assume armed, fail toward revert
            still_armed = True

        if not still_armed:
            emit_event(
                agent, "activation.sweep-skipped-disarm-race", control_id,
                {
                    "health_status": health_status, "health_detail": health_detail,
                    "reason": "armed record was disarmed/confirmed during the health-check window",
                },
                sdir=sdir,
            )
            results.append({
                "control_id": control_id, "action": "skipped-disarmed-race", "ok": True,
                "health_status": health_status,
            })
            continue

        revert_result = run_revert(record.get("revert_cmd", ""), timeout=revert_timeout)
        try:
            _terminate(
                control_id, "auto-reverted", "activation.auto-reverted", agent, sdir,
                extra={
                    "health_status": health_status, "health_detail": health_detail,
                    "revert_result": revert_result,
                },
                loud=True,
            )
        except Exception as exc:  # noqa: BLE001 — the revert already ran; a bookkeeping failure
            # must not hide that from the operator.
            emit_event(
                agent, "activation.auto-reverted", control_id,
                {
                    "health_status": health_status, "revert_result": revert_result,
                    "bookkeeping_error": str(exc),
                },
                sdir=sdir,
            )
            emit_pulse(agent, "auto-reverted", control_id, f"bookkeeping-failed:{exc}")
        results.append({
            "control_id": control_id, "action": "auto-reverted", "ok": revert_result.get("ok", False),
            "health_status": health_status, "revert_result": revert_result,
        })

    return results
