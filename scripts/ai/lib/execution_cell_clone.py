"""Self-contained clone primitive — Foundation C, C3b R2 (offline, deny-closed).

Implements ONLY the primitive authorized by
`.agents/plans/aqos-foundation-c/C3B-R2-DESIGN-AND-AUTHORIZATION.md`
(status R2_REVIEWED_PASS): a transactional, self-contained git clone at a
grant's verified base OID, a TOCTOU-safe trusted path rebase, and a typed
failure / quarantine / reconcile API. This module is a filesystem/git
primitive — it opens NO socket, invokes NO bwrap, touches NO Nix/systemd
surface, makes NO network call of its own (git operates only against a
caller-supplied local bare mirror path), and is fully offline-testable with
temp directories. It DESIGN-ONLY authorizes no runner service, no
confinement, no switchboard adapter, no activation (design §0).

Consumes `scripts/ai/lib/execution_grant.py`'s (R1, pure) `VerifiedGrant`,
`PathPlan`, `verify_freshness`, `verify_epoch`, and the replay-reservation
contract (`reserve_replay`) — this module does NOT reimplement grant
verification. `create_cell` re-checks freshness + epoch (and applies an
R2-local single-use guard over the SAME reservation contract) before any
disk write (design §6, §8-8).

Directory layout under `cell_state_root` (private state dir, never inside
the live repo):

    <cell_state_root>/cells/<cell_id>/.staging/clone/   # while being built
    <cell_state_root>/cells/<cell_id>/ready/clone/      # after atomic rename
    <cell_state_root>/cells/<cell_id>/ready/receipt.json
    <cell_state_root>/quarantine/<cell_id>/...          # partial/failed cells

Every operation returns a typed, immutable result and NEVER raises to its
caller (any unexpected exception is caught and reported as a typed failure —
fail-closed, design §5/§8). Nothing "deletes and reports success": a cell
that cannot be proven READY is QUARANTINED, never marked ready; a teardown
that cannot prove removal is QUARANTINED, never TornDown.

Trusted path rebase (design §4): every logical path is resolved to a host
path ONLY under the cell root via descriptor-relative resolution — on Linux,
`openat2(RESOLVE_BENEATH|RESOLVE_NO_SYMLINKS)` (called via `ctypes`/raw
syscall, syscall number 437 on x86-64, since Python has no native wrapper),
falling back to an fd-only `openat(O_NOFOLLOW)` component walk when
`openat2` is unavailable (ENOSYS) or the host is not x86-64. Neither path
ever does a `realpath`-precheck-then-open. A target logical path must
already exist in the cloned tree at cell-create time — R2 confines to
resolving pre-existing repo content post-clone; producing not-yet-existing
write targets is out of this primitive's scope (a deliberate, documented
scope boundary, not an oversight).
"""

from __future__ import annotations

import ctypes
import errno
import json
import os
import platform
import shutil
import stat
import subprocess
import sys
import types
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional, Sequence, Union

_LIB = os.path.dirname(os.path.abspath(__file__))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import execution_grant as eg  # noqa: E402


# --------------------------------------------------------------------------
# Directory-layout constants (this module's own convention — not part of any
# frozen external schema, so free to name; kept as constants for consistency
# between `create_cell`, `teardown_cell`, and `reconcile`).
# --------------------------------------------------------------------------

_CELLS_DIRNAME = "cells"
_QUARANTINE_DIRNAME = "quarantine"
_STAGING_DIRNAME = ".staging"
_READY_DIRNAME = "ready"
_CLONE_DIRNAME = "clone"
_RECEIPT_FILENAME = "receipt.json"

# --------------------------------------------------------------------------
# Typed failure vocabulary (design §5 closed set, plus the R1 freshness/
# epoch/replay denial codes reused verbatim for R2's pre-disk-write
# re-checks — see `create_cell` docstring).
# --------------------------------------------------------------------------

FAILURE_BASE_OID_UNREACHABLE = "base-oid-unreachable"
FAILURE_CLONE_FAILED = "clone-failed"
FAILURE_ISOLATION_VIOLATION = "isolation-violation"
FAILURE_PATH_ESCAPE = "path-escape"
FAILURE_DISK_EXHAUSTED = "disk-exhausted"
FAILURE_QUARANTINED = "quarantined"


# --------------------------------------------------------------------------
# Typed dataclasses (design §5) — small, frozen, never raised.
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class TypedFailure:
    """A typed, terminal failure verdict from `create_cell`. `code` is one
    of the FAILURE_* constants above, or a reused R1 `execution_grant.DENY_*`
    code when the failure is a pre-disk-write freshness/epoch/replay
    re-check (`create_cell` never invents a second vocabulary for a check
    R1 already names). `detail` is human-readable, not for programmatic
    branching."""

    code: str
    detail: str = ""


@dataclass(frozen=True)
class PathEscape:
    """A typed denial from `rebase_logical_path` — any escape (absolute
    host path, `..`, symlink, out-of-cell, component-prefix-not-
    containment) or unresolvable target. `detail` is human-readable."""

    detail: str


@dataclass(frozen=True)
class CellReady:
    """The verified, isolated workspace `create_cell` hands to a later
    (not-yet-authorized) R3 stage. `cell_root` is the git working-tree
    directory (the READY, post-rename `.../ready/clone`). `resolved_paths`
    maps each grant-declared logical path to the absolute host path it
    resolved to AT CELL-CREATION TIME — informational; R3 MUST re-resolve
    via `rebase_logical_path` at actual bind/use time using the same
    TOCTOU-safe discipline, never trust these strings as a substitute for a
    fresh fd-relative resolution. `cell_state_dir` is this module's own
    per-cell bookkeeping directory (`.../cells/<cell_id>`), used internally
    by `teardown_cell`/`reconcile` — not itself part of the R1→R2→R3
    contract surface, but exposed since it is the only durable handle a
    caller has for later teardown."""

    cell_root: str
    resolved_paths: "types.MappingProxyType[str, str]"
    grant_digest: str
    base_oid: str
    readiness_receipt: "types.MappingProxyType[str, Any]"
    cell_state_dir: str


@dataclass(frozen=True)
class TornDown:
    """Cleanup succeeded and removal was VERIFIED (re-checked absent after
    `rmtree`, not merely "rmtree didn't raise")."""

    cell_id: str
    detail: str = ""


@dataclass(frozen=True)
class Quarantined:
    """A cleanup (`teardown_cell`) or creation (`create_cell`) that could
    not be completed/verified. Never a success — the terminal, honest
    outcome for anything that cannot prove its own effect."""

    cell_id: str
    code: str
    detail: str = ""
    quarantine_path: Optional[str] = None


@dataclass(frozen=True)
class ReconcileReport:
    """Result of one `reconcile()` sweep. `reclaimed` counts directories
    verifiably removed this pass; `remaining_quarantined` is the quarantine
    backlog still present afterward; `errors` are best-effort diagnostic
    strings for entries that could not be reclaimed this pass (never
    raised)."""

    reclaimed: int
    remaining_quarantined: int
    errors: tuple[str, ...] = ()


# --------------------------------------------------------------------------
# Durable-write helpers
# --------------------------------------------------------------------------


def _fsync_write_json(path: str, obj: dict) -> None:
    """Write `obj` as JSON to `path` durably: write-to-temp, fsync the file,
    atomically replace, then fsync the containing directory (the directory
    entry itself is not durable until its directory is fsync'd too). Raises
    OSError on failure — callers wrap this in their own fail-closed
    handling; it is NOT itself total (a receipt write failing is a real
    condition callers must react to, not silently swallow)."""
    data = json.dumps(obj, sort_keys=True, indent=2, default=str).encode("utf-8") + b"\n"
    tmp_path = f"{path}.tmp-{uuid.uuid4().hex}"
    fd = os.open(tmp_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_CLOEXEC, 0o600)
    try:
        os.write(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(tmp_path, path)
    dir_fd = os.open(os.path.dirname(os.path.abspath(path)), os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)


def _mirror_fingerprint(bare_mirror_path: str) -> Optional[tuple]:
    """Best-effort, cheap fingerprint of the bare mirror's top-level and
    `objects/` mtimes — a defensive assertion that the mirror was not
    written during a clone (design §3.3 "the bare mirror is opened
    read-only and never written by a cell"). Not a cryptographic guarantee;
    the authoritative guarantee in tests is OS-enforced read-only
    permissions on the mirror tree. Returns None if the mirror cannot be
    stat'd (never raises)."""
    try:
        top = os.stat(bare_mirror_path)
        objects_dir = os.path.join(bare_mirror_path, "objects")
        obj_stat = os.stat(objects_dir) if os.path.isdir(objects_dir) else None
        return (top.st_mtime_ns, obj_stat.st_mtime_ns if obj_stat else None)
    except OSError:
        return None


# --------------------------------------------------------------------------
# Isolation invariants (design §3.3) — asserted, tested.
# --------------------------------------------------------------------------


def check_clone_isolation(clone_dir: str) -> Optional[str]:
    """Assert the isolation invariants of a freshly cloned cell tree:
    `.git` is a real directory (never a symlink, never a worktree-style
    "gitdir: ..." gitfile pointer — a worktree's `.git` is a plain FILE, so
    `not isdir` alone already detects it); no `objects/info/alternates`
    (would leak the source's live object store); no symlink anywhere in the
    tree resolving outside the clone. Returns None if clean, else a
    human-readable violation detail. Fail-closed: any error while checking
    is itself reported as a violation (never silently "assume clean" on an
    internal error)."""
    try:
        git_path = os.path.join(clone_dir, ".git")
        if os.path.islink(git_path):
            return f".git is a symlink (not a self-contained clone): {git_path}"
        if not os.path.isdir(git_path):
            return f".git is not a directory — possible worktree gitfile pointer or missing: {git_path}"

        alternates_path = os.path.join(git_path, "objects", "info", "alternates")
        if os.path.lexists(alternates_path):
            return f"objects/info/alternates present (shared object store): {alternates_path}"

        clone_real = os.path.realpath(clone_dir)
        for dirpath, dirnames, filenames in os.walk(clone_dir, followlinks=False):
            for name in list(dirnames) + list(filenames):
                full = os.path.join(dirpath, name)
                if os.path.islink(full):
                    target_real = os.path.realpath(full)
                    if target_real != clone_real and not target_real.startswith(clone_real + os.sep):
                        return f"symlink escapes cell root: {full} -> {target_real}"
        return None
    except Exception as exc:  # noqa: BLE001 — fail-closed: a check error IS a violation
        return f"isolation check raised {type(exc).__name__}: {exc}"


# --------------------------------------------------------------------------
# Trusted path rebase (design §4) — TOCTOU-safe, fd-relative.
# --------------------------------------------------------------------------

_SYS_OPENAT2_X86_64 = 437
_RESOLVE_BENEATH = 0x08
_RESOLVE_NO_SYMLINKS = 0x04


class _OpenHow(ctypes.Structure):
    """Mirrors Linux's `struct open_how` (linux/openat2.h): three u64
    fields, in this exact order — flags, mode, resolve."""

    _fields_ = [
        ("flags", ctypes.c_uint64),
        ("mode", ctypes.c_uint64),
        ("resolve", ctypes.c_uint64),
    ]


_libc_handle = None


def _libc() -> ctypes.CDLL:
    global _libc_handle
    if _libc_handle is None:
        handle = ctypes.CDLL(None, use_errno=True)
        handle.syscall.restype = ctypes.c_long
        _libc_handle = handle
    return _libc_handle


def _raw_openat2(dir_fd: int, relative_path: str, open_flags: int) -> int:
    """Direct `openat2(2)` invocation via `ctypes`/raw syscall (Python has
    no native wrapper). Resolves `relative_path` beneath `dir_fd` with
    RESOLVE_BENEATH|RESOLVE_NO_SYMLINKS — a single kernel-side resolution
    that cannot ascend above `dir_fd` (blocks `..`/absolute escape) and
    cannot traverse ANY symlink component (blocks symlink-swap escape).
    Raises OSError (errno=ENOSYS if the syscall itself is unavailable, or
    the kernel's genuine resolution-denied errno otherwise) — callers
    distinguish "unsupported, fall back" from "genuinely denied" by errno.
    Only defined for x86-64 (syscall number 437 is architecture-specific);
    any other architecture raises ENOSYS to route straight to the portable
    fallback."""
    if platform.machine() not in ("x86_64", "AMD64"):
        raise OSError(errno.ENOSYS, "openat2 syscall number not defined for this architecture")
    how = _OpenHow(flags=open_flags, mode=0, resolve=_RESOLVE_BENEATH | _RESOLVE_NO_SYMLINKS)
    path_bytes = os.fsencode(relative_path)
    result = _libc().syscall(
        ctypes.c_long(_SYS_OPENAT2_X86_64),
        ctypes.c_int(dir_fd),
        ctypes.c_char_p(path_bytes),
        ctypes.byref(how),
        ctypes.c_size_t(ctypes.sizeof(how)),
    )
    if result < 0:
        err = ctypes.get_errno()
        raise OSError(err, os.strerror(err), relative_path)
    return result


def _resolve_fallback_walk(root_fd: int, components: Sequence[str]) -> int:
    """Portable fallback when `openat2` is unavailable: an fd-only
    component walk using `O_PATH|O_NOFOLLOW` (`O_DIRECTORY` on every
    non-final component) via `os.open(..., dir_fd=...)`. Each hop opens
    strictly relative to the fd retained from the PREVIOUS hop — never
    re-resolves a checked pathname, never does a `realpath`-precheck. A
    symlink at any hop raises ELOOP (O_NOFOLLOW), which propagates as
    OSError to the caller. Raises OSError on any resolution failure;
    caller (`rebase_logical_path`) converts that to a typed `PathEscape`."""
    current_fd = os.dup(root_fd)
    try:
        last_index = len(components) - 1
        for index, component in enumerate(components):
            flags = os.O_PATH | os.O_NOFOLLOW | os.O_CLOEXEC
            if index != last_index:
                flags |= os.O_DIRECTORY
            next_fd = os.open(component, flags, dir_fd=current_fd)
            os.close(current_fd)
            current_fd = next_fd
        return current_fd
    except BaseException:
        try:
            os.close(current_fd)
        except OSError:
            pass
        raise


def _resolve_fd(root_fd: int, components: Sequence[str]) -> int:
    """Resolve `components` beneath `root_fd`: prefer a single `openat2`
    call (RESOLVE_BENEATH|RESOLVE_NO_SYMLINKS), falling back to the
    portable component walk ONLY when `openat2` reports ENOSYS (unsupported
    on this kernel/architecture) — a genuine resolution denial (ELOOP,
    ENOENT, etc.) from `openat2` is returned as-is and never silently
    retried via the fallback (that would blur "unsupported syscall" with
    "real escape/missing-target denial")."""
    joined = "/".join(components)
    try:
        return _raw_openat2(root_fd, joined, os.O_PATH | os.O_NOFOLLOW | os.O_CLOEXEC)
    except OSError as exc:
        if exc.errno == errno.ENOSYS:
            return _resolve_fallback_walk(root_fd, components)
        raise


def resolution_mechanism() -> str:
    """Diagnostic: which resolution mechanism `rebase_logical_path` will
    actually use on THIS host right now — `"openat2"` or `"fallback"`.
    Probes by resolving `"."` beneath `/` (always safe, always exists)."""
    try:
        probe_fd = os.open("/", os.O_DIRECTORY | os.O_CLOEXEC)
    except OSError:
        return "fallback"
    try:
        fd = _raw_openat2(probe_fd, ".", os.O_PATH | os.O_DIRECTORY | os.O_CLOEXEC)
        os.close(fd)
        return "openat2"
    except OSError:
        return "fallback"
    finally:
        os.close(probe_fd)


def rebase_logical_path(
    cell_root: str,
    logical_path: str,
    allowlist: Sequence[str],
) -> Union[int, PathEscape]:
    """Design §4 — resolve a single grant-declared logical path to a host
    path ONLY under `cell_root`, TOCTOU-safely. Re-checks (independently of
    R1's `execution_grant.classify_paths`, "not just the strings", design
    §4) that `logical_path` is syntactically clean and component-contained
    under `allowlist`, THEN performs the real fd-relative resolution
    against the live filesystem. Any escape class — absolute host path,
    `..` traversal, symlink (anywhere in the path, including the leaf),
    out-of-cell, or component-prefix-not-containment — returns a typed
    `PathEscape`. On success returns an OPEN file descriptor (caller owns
    it and MUST `os.close()` it) referencing the resolved target beneath
    `cell_root`. The target must already exist in the cell (see module
    docstring's documented scope boundary); a missing target is reported
    as `PathEscape`, not a distinct "not found" outcome — R2 does not
    materialize not-yet-existing write targets. Never raises."""
    try:
        if not isinstance(logical_path, str) or not logical_path:
            return PathEscape("empty or non-string logical path")
        if logical_path.startswith("/"):
            return PathEscape(f"absolute host path rejected: {logical_path!r}")
        if "\\" in logical_path:
            return PathEscape(f"backslash escape marker rejected: {logical_path!r}")

        components = tuple(c for c in logical_path.split("/") if c != "")
        if not components:
            return PathEscape(f"empty path after normalization: {logical_path!r}")
        if ".." in components or "." in components:
            return PathEscape(f"traversal/self component rejected: {logical_path!r}")

        allow_components = [tuple(c for c in p.split("/") if c != "") for p in allowlist]
        contained = any(
            prefix and len(components) >= len(prefix) and components[: len(prefix)] == prefix
            for prefix in allow_components
        )
        if not contained:
            return PathEscape(f"not component-contained under any allowlist prefix: {logical_path!r}")

        if not isinstance(cell_root, str) or not cell_root:
            return PathEscape("invalid cell_root")

        try:
            root_fd = os.open(cell_root, os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        except OSError as exc:
            return PathEscape(f"cell_root not resolvable: {exc}")

        try:
            fd = _resolve_fd(root_fd, components)
        except OSError as exc:
            return PathEscape(f"resolution denied (errno={exc.errno}): {exc}")
        finally:
            os.close(root_fd)

        # Linux quirk (not a bug in the resolver above): `O_PATH|O_NOFOLLOW`
        # on a trailing component that IS itself a symlink does not fail —
        # it returns an fd referring to the symlink object itself rather
        # than raising ELOOP (this differs from a symlink encountered as an
        # INTERMEDIATE component, which openat2's RESOLVE_NO_SYMLINKS/the
        # fallback walk's O_NOFOLLOW does correctly reject). A trailing
        # symlink must still be treated as an escape candidate (design §4:
        # "the leaf" is explicitly in scope for the escape check) since its
        # target is unverified and could point outside the cell.
        try:
            leaf_stat = os.fstat(fd)
        except OSError as exc:
            os.close(fd)
            return PathEscape(f"post-resolution fstat failed: {exc}")
        if stat.S_ISLNK(leaf_stat.st_mode):
            os.close(fd)
            return PathEscape(f"resolved leaf is itself a symlink: {logical_path!r}")

        return fd
    except Exception as exc:  # noqa: BLE001 — total fail-closed
        return PathEscape(f"internal rebase error: {type(exc).__name__}: {exc}")


# --------------------------------------------------------------------------
# Quarantine helper (shared by create_cell + teardown_cell)
# --------------------------------------------------------------------------


def _quarantine_partial(
    cell_state_root: str,
    cell_id: str,
    source_dir: Optional[str],
    code: str,
    detail: str,
    grant_digest: Optional[str],
) -> Optional[str]:
    """Move whatever exists at `source_dir` (if anything) into
    `<cell_state_root>/quarantine/<cell_id>` and write a best-effort typed
    quarantine receipt. Never raises — a receipt-write failure is swallowed
    (the QUARANTINED verdict itself is what the caller must honor; the
    receipt is audit sugar, not the safety mechanism). Returns the
    quarantine path if the move succeeded, else None."""
    try:
        quarantine_root = os.path.join(cell_state_root, _QUARANTINE_DIRNAME)
        os.makedirs(quarantine_root, mode=0o700, exist_ok=True)
        dest = os.path.join(quarantine_root, cell_id)
        moved = False
        if source_dir and os.path.exists(source_dir):
            try:
                os.rename(source_dir, dest)
                moved = True
            except OSError:
                moved = False
        receipt = {
            "cell_id": cell_id,
            "code": code,
            "detail": detail,
            "grant_digest": grant_digest,
            "quarantined_at": datetime.now(timezone.utc).isoformat(),
            "moved": moved,
        }
        receipt_dir = dest if moved else quarantine_root
        receipt_name = "quarantine-receipt.json" if moved else f"{cell_id}.quarantine-receipt.json"
        try:
            os.makedirs(receipt_dir, mode=0o700, exist_ok=True)
            _fsync_write_json(os.path.join(receipt_dir, receipt_name), receipt)
        except OSError:
            pass
        return dest if moved else None
    except Exception:  # noqa: BLE001 — total fail-closed, quarantining must never itself raise
        return None


def _fail_reservation(reservation_set: Any, grant_id: str) -> None:
    """Best-effort reserved -> failed transition on the R2 single-use
    reservation store (see `create_cell`). Never raises — an unreliable
    reservation store is already fail-closed by construction (it started
    "reserved", so no later caller can reuse this `grant_id` regardless of
    whether this transition succeeds)."""
    fail_fn = getattr(reservation_set, "fail", None)
    if callable(fail_fn):
        try:
            fail_fn(grant_id)
        except Exception:
            pass


# --------------------------------------------------------------------------
# create_cell (design §3.2) — transactional, self-contained.
# --------------------------------------------------------------------------


def create_cell(
    verified_grant: "eg.VerifiedGrant",
    *,
    bare_mirror_path: str,
    cell_state_root: str,
    now: Optional[datetime],
    current_epoch: Optional[int],
    reservation_set: Any,
) -> Union[CellReady, TypedFailure]:
    """Design §3.2 — build a fresh, self-contained cell at
    `verified_grant.base_revision`, cloned from `bare_mirror_path` (a
    dedicated, read-only bare mirror — never the live repo's `.git`, never
    written by this function). Order of operations (fixed, matches design
    §6/§8-8 — freshness/epoch re-checked FIRST, before any disk write):

    1. Re-verify freshness (`execution_grant.verify_freshness`) and epoch
       (`execution_grant.verify_epoch`) against `verified_grant.raw` — a
       grant that was fresh at admission time may have gone stale/expired
       or been revoked by the time a cell is actually built. Failure here
       returns a `TypedFailure` reusing R1's own denial code and touches
       NO disk.
    2. R2-local single-use guard: `reservation_set` (the SAME
       try_reserve/commit/fail contract as R1's `ReplayReservationSet` —
       but a DIFFERENT store/instance than the admission gate's, since the
       cell-build boundary is a distinct privileged boundary, design §3
       SF-1) reserves `verified_grant.grant_id`; already-reserved denies
       (`execution_grant.DENY_REPLAYED`) — a grant mints at most one cell.
    3. Allocate `<cell_state_root>/cells/<cell_id>/.staging/`.
    4. `git clone --template= --no-local --no-hardlinks <bare_mirror_path>
       <staging>/clone` (self-contained: own `.git`, no alternates).
    5. Verify the base OID is present AND becomes HEAD: `cat-file -e
       <oid>^{commit}`, `checkout --detach <oid>`, `rev-parse HEAD == oid`.
       Any failure -> `base-oid-unreachable`.
    6. Assert isolation invariants (`check_clone_isolation`) and that the
       bare mirror's fingerprint did not change during the clone. Any
       violation -> `isolation-violation`.
    7. Resolve every `verified_grant.path_plan` entry via
       `rebase_logical_path`. Any escape -> `path-escape`.
    8. Only if ALL of the above passed: atomically rename `.staging` ->
       `ready` (same filesystem), then write+fsync a typed readiness
       receipt bound to `grant_digest` + `base_oid`. Only NOW is the
       reservation committed and a `CellReady` returned.

    Any failure at steps 3-8 quarantines whatever partial state exists
    (`_quarantine_partial`) and fails the reservation
    (`_fail_reservation`) — never a READY cell, never a success receipt,
    on any of those paths. Never raises: any unexpected exception anywhere
    is caught and reported as `TypedFailure(FAILURE_QUARANTINED, ...)`."""
    try:
        # `execution_grant.verify_epoch` requires `isinstance(grant, dict)`
        # (R1 source, `execution_grant.py`); `VerifiedGrant.raw` is typed as
        # a `MappingProxyType` (R1's own dataclass), which is NOT a `dict`
        # instance and would always deny with `stale-epoch` regardless of
        # actual staleness if passed through as-is. Converting to a plain
        # `dict` here is a type ADAPTER, not a reimplementation — every
        # field value and every check inside `verify_freshness`/
        # `verify_epoch` is still R1's own, unmodified logic.
        raw = dict(verified_grant.raw)

        freshness_verdict = eg.verify_freshness(raw, now)
        if freshness_verdict != eg.VERIFY_OK:
            return TypedFailure(freshness_verdict, "grant freshness re-check failed at cell-create time")

        epoch_verdict = eg.verify_epoch(raw, current_epoch)
        if epoch_verdict != eg.VERIFY_OK:
            return TypedFailure(epoch_verdict, "grant epoch re-check failed at cell-create time")

        replay_verdict = eg.reserve_replay(verified_grant.grant_id, reservation_set)
        if replay_verdict != eg.REPLAY_RESERVED:
            return TypedFailure(eg.DENY_REPLAYED, "grant_id already used to create a cell (single-use)")

        cell_id = uuid.uuid4().hex
        cell_dir = os.path.join(cell_state_root, _CELLS_DIRNAME, cell_id)
        staging_dir = os.path.join(cell_dir, _STAGING_DIRNAME)
        clone_dir = os.path.join(staging_dir, _CLONE_DIRNAME)

        def _fail(code: str, detail: str) -> TypedFailure:
            _quarantine_partial(cell_state_root, cell_id, cell_dir, code, detail, verified_grant.grant_digest)
            _fail_reservation(reservation_set, verified_grant.grant_id)
            return TypedFailure(code, detail)

        mirror_fingerprint_before = _mirror_fingerprint(bare_mirror_path)

        try:
            os.makedirs(staging_dir, mode=0o700, exist_ok=False)
        except OSError as exc:
            code = FAILURE_DISK_EXHAUSTED if exc.errno == errno.ENOSPC else FAILURE_CLONE_FAILED
            return _fail(code, f"failed to allocate cell staging directory: {exc}")

        clone_proc = subprocess.run(
            ["git", "clone", "--template=", "--no-local", "--no-hardlinks", bare_mirror_path, clone_dir],
            check=False,
            capture_output=True,
            text=True,
        )
        if clone_proc.returncode != 0:
            return _fail(FAILURE_CLONE_FAILED, f"git clone failed: {clone_proc.stderr.strip()}")

        oid = verified_grant.base_revision

        cat_file = subprocess.run(
            ["git", "-C", clone_dir, "cat-file", "-e", f"{oid}^{{commit}}"],
            check=False,
            capture_output=True,
            text=True,
        )
        if cat_file.returncode != 0:
            return _fail(
                FAILURE_BASE_OID_UNREACHABLE,
                f"base OID not reachable in mirror: {cat_file.stderr.strip()}",
            )

        checkout = subprocess.run(
            ["git", "-C", clone_dir, "checkout", "--detach", oid],
            check=False,
            capture_output=True,
            text=True,
        )
        if checkout.returncode != 0:
            return _fail(
                FAILURE_BASE_OID_UNREACHABLE,
                f"checkout --detach failed: {checkout.stderr.strip()}",
            )

        rev_parse = subprocess.run(
            ["git", "-C", clone_dir, "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
        )
        head = rev_parse.stdout.strip()
        if rev_parse.returncode != 0 or head != oid:
            return _fail(
                FAILURE_BASE_OID_UNREACHABLE,
                f"HEAD ({head!r}) does not match verified base OID ({oid!r})",
            )

        violation = check_clone_isolation(clone_dir)
        if violation is not None:
            return _fail(FAILURE_ISOLATION_VIOLATION, violation)

        mirror_fingerprint_after = _mirror_fingerprint(bare_mirror_path)
        if mirror_fingerprint_before != mirror_fingerprint_after:
            return _fail(FAILURE_ISOLATION_VIOLATION, "bare mirror fingerprint changed during clone (possible write)")

        resolved: dict[str, str] = {}
        for logical_path, _components in verified_grant.path_plan.entries:
            result = rebase_logical_path(clone_dir, logical_path, verified_grant.path_plan.allowlist)
            if isinstance(result, PathEscape):
                return _fail(FAILURE_PATH_ESCAPE, f"{logical_path}: {result.detail}")
            os.close(result)
            resolved[logical_path] = os.path.join(clone_dir, logical_path)

        ready_dir = os.path.join(cell_dir, _READY_DIRNAME)
        try:
            os.rename(staging_dir, ready_dir)
        except OSError as exc:
            return _fail(FAILURE_CLONE_FAILED, f"atomic rename to ready failed: {exc}")

        final_clone_dir = os.path.join(ready_dir, _CLONE_DIRNAME)
        final_resolved = {
            logical_path: os.path.join(final_clone_dir, logical_path) for logical_path in resolved
        }

        receipt = {
            "cell_id": cell_id,
            "grant_id": verified_grant.grant_id,
            "grant_digest": verified_grant.grant_digest,
            "base_oid": oid,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            _fsync_write_json(os.path.join(ready_dir, _RECEIPT_FILENAME), receipt)
        except OSError as exc:
            # The rename succeeded but the receipt did not durably land —
            # do not claim READY without a receipt bound to it (design §5).
            return _fail(FAILURE_CLONE_FAILED, f"readiness receipt write failed: {exc}")

        commit_fn = getattr(reservation_set, "commit", None)
        if callable(commit_fn):
            try:
                commit_fn(verified_grant.grant_id)
            except Exception:
                pass

        return CellReady(
            cell_root=final_clone_dir,
            resolved_paths=types.MappingProxyType(final_resolved),
            grant_digest=verified_grant.grant_digest,
            base_oid=oid,
            readiness_receipt=types.MappingProxyType(receipt),
            cell_state_dir=cell_dir,
        )
    except Exception as exc:  # noqa: BLE001 — total fail-closed, never raise
        return TypedFailure(FAILURE_QUARANTINED, f"internal create_cell error: {type(exc).__name__}: {exc}")


# --------------------------------------------------------------------------
# teardown_cell / reconcile (design §5) — typed, idempotent, never
# "delete-and-report-success".
# --------------------------------------------------------------------------


def _try_verified_rmtree(path: str) -> tuple[bool, Optional[str]]:
    """Attempt `shutil.rmtree(path)` and then RE-CHECK `path` is actually
    gone — "rmtree didn't raise" is not proof of removal (e.g. NFS/overlay
    quirks, or a race re-creating an entry). Returns (True, None) only if
    verified absent afterward; (False, detail) otherwise. Never raises."""
    try:
        shutil.rmtree(path)
    except OSError as exc:
        return False, str(exc)
    if os.path.lexists(path):
        return False, "path still exists after rmtree (unverified removal)"
    return True, None


def teardown_cell(cell: CellReady) -> Union[TornDown, Quarantined]:
    """Remove a cell's entire private state directory
    (`cell.cell_state_dir`) and VERIFY it is gone. A cleanup that cannot
    prove removal (EBUSY, partial rmtree, a remaining entry) is
    `Quarantined` with a typed receipt — never `TornDown`. Never raises."""
    cell_id = "unknown"
    try:
        cell_dir = cell.cell_state_dir
        cell_id = os.path.basename(cell_dir)
        ok, err = _try_verified_rmtree(cell_dir)
        if ok:
            return TornDown(cell_id=cell_id, detail="removed and verified absent")

        cell_state_root = os.path.dirname(os.path.dirname(cell_dir))
        detail = f"teardown could not verify removal: {err}"
        quarantine_path = _quarantine_partial(
            cell_state_root, cell_id, cell_dir if os.path.exists(cell_dir) else None,
            FAILURE_QUARANTINED, detail, cell.grant_digest,
        )
        return Quarantined(cell_id=cell_id, code=FAILURE_QUARANTINED, detail=detail, quarantine_path=quarantine_path)
    except Exception as exc:  # noqa: BLE001 — total fail-closed
        return Quarantined(
            cell_id=cell_id,
            code=FAILURE_QUARANTINED,
            detail=f"internal teardown error: {type(exc).__name__}: {exc}",
            quarantine_path=None,
        )


def _is_within(base: str, path: str) -> bool:
    try:
        base_real = os.path.realpath(base)
        path_real = os.path.realpath(path)
        return path_real == base_real or path_real.startswith(base_real + os.sep)
    except OSError:
        return False


def reconcile(cell_state_root: str) -> ReconcileReport:
    """Idempotent sweeper over `<cell_state_root>/quarantine/*` and
    `<cell_state_root>/cells/*` (design §5). Reclaims orphans with VERIFIED
    proof of removal:
      - every entry under `quarantine/` is, by definition, already dead —
        reclaim unconditionally.
      - an entry under `cells/<id>` WITHOUT a `ready/receipt.json` never
        completed successfully (crash-left partial, or a `create_cell` that
        died before its own quarantine-on-failure ran) — safe to reclaim,
        since nothing could be depending on a cell that was never READY.
      - an entry under `cells/<id>` WITH a `ready/receipt.json` is a live,
        completed cell — reconcile NEVER touches it (that is
        `teardown_cell`'s job, on explicit caller request).
    Safe to run repeatedly: a clean state (nothing reclaimable) is a
    genuine no-op. Never touches anything outside `cell_state_root` (every
    candidate path is re-verified `_is_within` before any `rmtree`). Never
    raises."""
    try:
        root = os.path.abspath(cell_state_root)
        if not os.path.isdir(root):
            return ReconcileReport(reclaimed=0, remaining_quarantined=0, errors=())

        reclaimed = 0
        errors: list[str] = []

        quarantine_root = os.path.join(root, _QUARANTINE_DIRNAME)
        if os.path.isdir(quarantine_root):
            for entry in sorted(os.listdir(quarantine_root)):
                target = os.path.join(quarantine_root, entry)
                if os.path.islink(target) or not _is_within(root, target):
                    errors.append(f"{entry}: skipped (symlink or outside cell_state_root)")
                    continue
                ok, err = _try_verified_rmtree(target)
                if ok:
                    reclaimed += 1
                elif err:
                    errors.append(f"{entry}: {err}")

        cells_root = os.path.join(root, _CELLS_DIRNAME)
        if os.path.isdir(cells_root):
            for entry in sorted(os.listdir(cells_root)):
                target = os.path.join(cells_root, entry)
                if os.path.islink(target) or not _is_within(root, target):
                    errors.append(f"{entry}: skipped (symlink or outside cell_state_root)")
                    continue
                receipt_path = os.path.join(target, _READY_DIRNAME, _RECEIPT_FILENAME)
                if os.path.exists(receipt_path):
                    continue  # live, READY cell — never reclaimed by reconcile
                ok, err = _try_verified_rmtree(target)
                if ok:
                    reclaimed += 1
                elif err:
                    errors.append(f"{entry}: {err}")

        remaining_quarantined = len(os.listdir(quarantine_root)) if os.path.isdir(quarantine_root) else 0

        return ReconcileReport(reclaimed=reclaimed, remaining_quarantined=remaining_quarantined, errors=tuple(errors))
    except Exception as exc:  # noqa: BLE001 — total fail-closed
        return ReconcileReport(
            reclaimed=0,
            remaining_quarantined=-1,
            errors=(f"internal reconcile error: {type(exc).__name__}: {exc}",),
        )
