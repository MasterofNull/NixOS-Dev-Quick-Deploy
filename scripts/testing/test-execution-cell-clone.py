#!/usr/bin/env python3
"""Offline acceptance tests — Foundation C C3b R2 self-contained clone
primitive.

Exercises `scripts/ai/lib/execution_cell_clone.py` per
`.agents/plans/aqos-foundation-c/C3B-R2-DESIGN-AND-AUTHORIZATION.md`
(status R2_REVIEWED_PASS) §7 acceptance + §8 review obligations. Fully
offline: builds a THROWAWAY tiny git repo + bare mirror under a temp dir (no
network, no dependence on the live repo, no service). Asserts:

  1. create_cell at a valid OID -> CellReady; HEAD == oid; no alternates /
     no external .git pointer / no symlink escape.
  2. unreachable OID -> base-oid-unreachable + quarantined partial, never
     READY, never a success receipt.
  3. simulated failures (corrupt/missing mirror; non-writable parent) ->
     typed failure + quarantine.
  4. path rebase: every escape class (abs, .., symlink swap, out-of-cell,
     prefix-not-containment) -> path-escape deny; a valid in-cell path ->
     resolved fd under the cell root.
  5. teardown that cannot prove removal -> Quarantined; reconcile()
     reclaims orphans idempotently, is a no-op on clean state, and never
     escapes cell_state_root.
  6. stale/expired grant at create time -> deny before any disk write
     (asserts no cell directory is ever created).
  7. isolation fuzz: a crafted alternates file / outward symlink injected
     into a clone -> `check_clone_isolation` rejects it.

Run directly: `python3 scripts/testing/test-execution-cell-clone.py`
Exits 0 iff every test passes; prints "N/N passed".
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
import tempfile
import types
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_LIB_DIR = str(_REPO_ROOT / "scripts" / "ai" / "lib")
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import execution_cell_clone as ecc  # noqa: E402
import execution_grant as eg  # noqa: E402


# --------------------------------------------------------------------------
# Test harness (no external deps — matches test-execution-grant.py)
# --------------------------------------------------------------------------

_RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    _RESULTS.append((name, bool(condition), detail))


def _report_and_exit() -> None:
    failed = [r for r in _RESULTS if not r[1]]
    for name, ok, detail in _RESULTS:
        status = "PASS" if ok else "FAIL"
        line = f"[{status}] {name}"
        if detail and not ok:
            line += f" — {detail}"
        print(line)
    print(f"\n{len(_RESULTS) - len(failed)}/{len(_RESULTS)} passed")
    if failed:
        print(f"FAILED: {[f[0] for f in failed]}")
        sys.exit(1)
    sys.exit(0)


# --------------------------------------------------------------------------
# Fixture helpers — throwaway git repo + bare mirror, all under one temp dir
# --------------------------------------------------------------------------

_TEMP_ROOTS: list[str] = []


def _mkdtemp(prefix: str) -> str:
    d = tempfile.mkdtemp(prefix=f"c3b-r2-{prefix}-")
    _TEMP_ROOTS.append(d)
    return d


def _run_git(args: list[str], cwd: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git"] + args,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "GIT_AUTHOR_NAME": "R2 Test", "GIT_AUTHOR_EMAIL": "r2-test@example.invalid",
             "GIT_COMMITTER_NAME": "R2 Test", "GIT_COMMITTER_EMAIL": "r2-test@example.invalid"},
    )


def _build_source_repo() -> tuple[str, str]:
    """Builds a tiny throwaway repo with two committed files and returns
    (source_repo_path, head_oid)."""
    src = _mkdtemp("source")
    assert _run_git(["init", "-q", "-b", "main"], src).returncode == 0
    (Path(src) / "README.md").write_text("hello world\n", encoding="utf-8")
    os.makedirs(Path(src) / "allowed_dir", exist_ok=True)
    (Path(src) / "allowed_dir" / "inner.txt").write_text("inner\n", encoding="utf-8")
    assert _run_git(["add", "-A"], src).returncode == 0
    commit = _run_git(["commit", "-q", "-m", "initial"], src)
    assert commit.returncode == 0, commit.stderr
    rev = _run_git(["rev-parse", "HEAD"], src)
    assert rev.returncode == 0, rev.stderr
    return src, rev.stdout.strip()


def _build_bare_mirror(source_repo: str) -> str:
    mirror = os.path.join(_mkdtemp("mirror-parent"), "mirror.git")
    result = subprocess.run(
        ["git", "clone", "-q", "--mirror", source_repo, mirror],
        check=False, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    return mirror


def _chmod_tree_readonly(path: str) -> None:
    for dirpath, dirnames, filenames in os.walk(path):
        for name in dirnames:
            os.chmod(os.path.join(dirpath, name), 0o555)
        for name in filenames:
            os.chmod(os.path.join(dirpath, name), 0o444)
    os.chmod(path, 0o555)


def _chmod_tree_writable(path: str) -> None:
    for dirpath, dirnames, filenames in os.walk(path):
        for name in dirnames:
            try:
                os.chmod(os.path.join(dirpath, name), 0o700)
            except OSError:
                pass
        for name in filenames:
            try:
                os.chmod(os.path.join(dirpath, name), 0o600)
            except OSError:
                pass
    try:
        os.chmod(path, 0o700)
    except OSError:
        pass


def _make_verified_grant(
    *,
    base_revision: str,
    logical_paths: list[str],
    allowlist: tuple[str, ...],
    issued_at: datetime,
    expires_at: datetime,
    revocation_epoch: int,
    grant_id: str = None,
) -> eg.VerifiedGrant:
    """Constructs a `VerifiedGrant` DIRECTLY (bypassing R1's Ed25519
    signing machinery, which is out of R2's scope to re-test) — `raw`
    carries exactly the fields R2's own freshness/epoch re-checks read
    (`issued_at`, `expires_at`, `revocation_epoch`), matching
    `execution_grant.verify_freshness`/`verify_epoch`'s actual field
    access, not the full closed schema."""
    entries = tuple((p, tuple(c for c in p.split("/") if c)) for p in logical_paths)
    raw = types.MappingProxyType({
        "issued_at": issued_at.isoformat(),
        "expires_at": expires_at.isoformat(),
        "revocation_epoch": revocation_epoch,
    })
    gid = grant_id or uuid.uuid4().hex + uuid.uuid4().hex
    return eg.VerifiedGrant(
        grant_id=gid,
        lease_id="lease-" + gid[:8],
        task_id="task-" + gid[:8],
        request_id="req-" + gid[:8],
        base_revision=base_revision,
        exec_class="none",
        trusted_repo_id="r2-test-repo",
        resource_limits=types.MappingProxyType({"timeout_s": 30, "max_output_bytes": 1024, "cell_class": "small"}),
        grant_digest="digest-" + gid,
        classification=eg.Classification(effects=()),
        path_plan=eg.PathPlan(allowlist=allowlist, entries=entries),
        raw=raw,
    )


def _fresh_window() -> tuple[datetime, datetime, datetime]:
    now = datetime.now(timezone.utc)
    return now - timedelta(minutes=1), now, now + timedelta(hours=1)


# --------------------------------------------------------------------------
# Shared fixture (built once)
# --------------------------------------------------------------------------

_SOURCE_REPO, _HEAD_OID = _build_source_repo()
_MIRROR = _build_bare_mirror(_SOURCE_REPO)
_chmod_tree_readonly(_MIRROR)  # kernel-enforced: any accidental write -> EACCES


# --------------------------------------------------------------------------
# 1. Happy path — CellReady, HEAD matches, isolation clean
# --------------------------------------------------------------------------


def test_create_cell_happy_path():
    state_root = _mkdtemp("state-happy")
    issued_at, now, expires_at = _fresh_window()
    grant = _make_verified_grant(
        base_revision=_HEAD_OID,
        logical_paths=["README.md", "allowed_dir/inner.txt"],
        allowlist=("README.md", "allowed_dir"),
        issued_at=issued_at, expires_at=expires_at, revocation_epoch=5,
    )
    reservation = eg.ReplayReservationSet()
    result = ecc.create_cell(
        grant, bare_mirror_path=_MIRROR, cell_state_root=state_root,
        now=now, current_epoch=5, reservation_set=reservation,
    )
    check("happy_path_is_cell_ready", isinstance(result, ecc.CellReady), f"got {result!r}")
    if not isinstance(result, ecc.CellReady):
        return

    head = subprocess.run(["git", "-C", result.cell_root, "rev-parse", "HEAD"],
                           capture_output=True, text=True)
    check("happy_path_head_matches_oid", head.stdout.strip() == _HEAD_OID, head.stdout)

    check("happy_path_no_alternates",
          not os.path.lexists(os.path.join(result.cell_root, ".git", "objects", "info", "alternates")))
    check("happy_path_git_is_real_dir",
          os.path.isdir(os.path.join(result.cell_root, ".git"))
          and not os.path.islink(os.path.join(result.cell_root, ".git")))
    check("happy_path_isolation_clean", ecc.check_clone_isolation(result.cell_root) is None)
    check("happy_path_resolved_paths_present",
          set(result.resolved_paths.keys()) == {"README.md", "allowed_dir/inner.txt"})
    check("happy_path_grant_digest_bound", result.readiness_receipt["grant_digest"] == grant.grant_digest)
    check("happy_path_base_oid_bound", result.readiness_receipt["base_oid"] == _HEAD_OID)
    check("happy_path_receipt_on_disk",
          os.path.exists(os.path.join(os.path.dirname(result.cell_root), "receipt.json")))
    check("happy_path_reservation_committed",
          reservation.state_of(grant.grant_id) == eg.RESERVATION_COMMITTED)

    # Second create_cell with the SAME grant_id must be denied (single-use).
    result2 = ecc.create_cell(
        grant, bare_mirror_path=_MIRROR, cell_state_root=state_root,
        now=now, current_epoch=5, reservation_set=reservation,
    )
    check("happy_path_single_use_denied",
          isinstance(result2, ecc.TypedFailure) and result2.code == eg.DENY_REPLAYED, f"got {result2!r}")


# --------------------------------------------------------------------------
# 2. Unreachable base OID -> typed failure, quarantined partial, never READY
# --------------------------------------------------------------------------


def test_unreachable_oid_quarantines():
    state_root = _mkdtemp("state-unreachable")
    issued_at, now, expires_at = _fresh_window()
    fake_oid = "f" * 40
    grant = _make_verified_grant(
        base_revision=fake_oid,
        logical_paths=["README.md"],
        allowlist=("README.md",),
        issued_at=issued_at, expires_at=expires_at, revocation_epoch=1,
    )
    reservation = eg.ReplayReservationSet()
    result = ecc.create_cell(
        grant, bare_mirror_path=_MIRROR, cell_state_root=state_root,
        now=now, current_epoch=1, reservation_set=reservation,
    )
    check("unreachable_oid_typed_failure",
          isinstance(result, ecc.TypedFailure) and result.code == ecc.FAILURE_BASE_OID_UNREACHABLE,
          f"got {result!r}")

    cells_dir = os.path.join(state_root, "cells")
    ready_dirs = []
    if os.path.isdir(cells_dir):
        for cell_id in os.listdir(cells_dir):
            ready_dirs.append(os.path.join(cells_dir, cell_id, "ready"))
    check("unreachable_oid_never_ready", not any(os.path.isdir(d) for d in ready_dirs))

    quarantine_dir = os.path.join(state_root, "quarantine")
    check("unreachable_oid_quarantined", os.path.isdir(quarantine_dir) and len(os.listdir(quarantine_dir)) == 1)

    check("unreachable_oid_reservation_failed",
          reservation.state_of(grant.grant_id) == eg.RESERVATION_FAILED)


# --------------------------------------------------------------------------
# 3. Simulated failures — corrupt/missing mirror; non-writable parent
# --------------------------------------------------------------------------


def test_missing_mirror_clone_failed():
    state_root = _mkdtemp("state-missing-mirror")
    issued_at, now, expires_at = _fresh_window()
    grant = _make_verified_grant(
        base_revision=_HEAD_OID, logical_paths=["README.md"], allowlist=("README.md",),
        issued_at=issued_at, expires_at=expires_at, revocation_epoch=1,
    )
    bogus_mirror = os.path.join(_mkdtemp("bogus"), "does-not-exist.git")
    reservation = eg.ReplayReservationSet()
    result = ecc.create_cell(
        grant, bare_mirror_path=bogus_mirror, cell_state_root=state_root,
        now=now, current_epoch=1, reservation_set=reservation,
    )
    check("missing_mirror_clone_failed",
          isinstance(result, ecc.TypedFailure) and result.code == ecc.FAILURE_CLONE_FAILED, f"got {result!r}")
    quarantine_dir = os.path.join(state_root, "quarantine")
    check("missing_mirror_quarantined", os.path.isdir(quarantine_dir) and len(os.listdir(quarantine_dir)) == 1)


def test_nonwritable_parent_typed_failure_no_disk_effect():
    state_root = _mkdtemp("state-nonwritable")
    locked_child = os.path.join(state_root, "locked")
    os.makedirs(locked_child, mode=0o500)
    try:
        issued_at, now, expires_at = _fresh_window()
        grant = _make_verified_grant(
            base_revision=_HEAD_OID, logical_paths=["README.md"], allowlist=("README.md",),
            issued_at=issued_at, expires_at=expires_at, revocation_epoch=1,
        )
        reservation = eg.ReplayReservationSet()
        result = ecc.create_cell(
            grant, bare_mirror_path=_MIRROR, cell_state_root=locked_child,
            now=now, current_epoch=1, reservation_set=reservation,
        )
        check("nonwritable_parent_typed_failure",
              isinstance(result, ecc.TypedFailure)
              and result.code in (ecc.FAILURE_CLONE_FAILED, ecc.FAILURE_DISK_EXHAUSTED),
              f"got {result!r}")
    finally:
        os.chmod(locked_child, 0o700)


# --------------------------------------------------------------------------
# 4. Path rebase — every escape class + a valid in-cell resolution
# --------------------------------------------------------------------------


def test_rebase_escape_classes():
    state_root = _mkdtemp("state-rebase")
    issued_at, now, expires_at = _fresh_window()
    grant = _make_verified_grant(
        base_revision=_HEAD_OID,
        logical_paths=["README.md", "allowed_dir/inner.txt"],
        allowlist=("README.md", "allowed_dir"),
        issued_at=issued_at, expires_at=expires_at, revocation_epoch=1,
    )
    reservation = eg.ReplayReservationSet()
    result = ecc.create_cell(
        grant, bare_mirror_path=_MIRROR, cell_state_root=state_root,
        now=now, current_epoch=1, reservation_set=reservation,
    )
    check("rebase_fixture_cell_ready", isinstance(result, ecc.CellReady), f"got {result!r}")
    if not isinstance(result, ecc.CellReady):
        return
    cell_root = result.cell_root
    allowlist = ("README.md", "allowed_dir")

    # -- valid in-cell path -> resolved fd under the cell root
    fd = ecc.rebase_logical_path(cell_root, "README.md", allowlist)
    check("rebase_valid_path_returns_fd", isinstance(fd, int) and fd >= 0, f"got {fd!r}")
    if isinstance(fd, int):
        real = os.readlink(f"/proc/self/fd/{fd}")
        cell_real = os.path.realpath(cell_root)
        check("rebase_valid_fd_under_cell_root", real == os.path.realpath(os.path.join(cell_root, "README.md")))
        check("rebase_valid_fd_is_within_cell", real == cell_real or real.startswith(cell_real + os.sep))
        os.close(fd)

    # -- absolute host path
    r = ecc.rebase_logical_path(cell_root, "/etc/passwd", allowlist)
    check("rebase_abs_path_denied", isinstance(r, ecc.PathEscape), f"got {r!r}")

    # -- traversal
    r = ecc.rebase_logical_path(cell_root, "../../etc/passwd", allowlist)
    check("rebase_traversal_denied", isinstance(r, ecc.PathEscape), f"got {r!r}")

    r = ecc.rebase_logical_path(cell_root, "allowed_dir/../../../etc/passwd", allowlist)
    check("rebase_embedded_traversal_denied", isinstance(r, ecc.PathEscape), f"got {r!r}")

    # -- out-of-cell / prefix-not-containment (not under any allowlist prefix)
    r = ecc.rebase_logical_path(cell_root, "not_allowed/other.txt", allowlist)
    check("rebase_out_of_allowlist_denied", isinstance(r, ecc.PathEscape), f"got {r!r}")

    # component-prefix-not-containment: "allowed_dirX" shares a STRING
    # prefix with "allowed_dir" but is NOT component-contained under it.
    os.makedirs(os.path.join(cell_root, "allowed_dirX"), exist_ok=True)
    Path(os.path.join(cell_root, "allowed_dirX", "sneaky.txt")).write_text("x\n")
    r = ecc.rebase_logical_path(cell_root, "allowed_dirX/sneaky.txt", allowlist)
    check("rebase_prefix_not_containment_denied", isinstance(r, ecc.PathEscape), f"got {r!r}")

    # -- symlink swap: a real symlink placed INSIDE the cell (under an
    # allowed prefix) pointing OUTSIDE the cell root. String-level
    # containment would say "allowed_dir/escape" is fine; the TOCTOU-safe
    # fd walk must catch the symlink and deny.
    outside_target = _mkdtemp("outside-target")
    Path(os.path.join(outside_target, "secret.txt")).write_text("secret\n")
    escape_link = os.path.join(cell_root, "allowed_dir", "escape")
    os.symlink(outside_target, escape_link)
    r = ecc.rebase_logical_path(cell_root, "allowed_dir/escape", allowlist)
    check("rebase_symlink_swap_denied", isinstance(r, ecc.PathEscape), f"got {r!r}")
    r2 = ecc.rebase_logical_path(cell_root, "allowed_dir/escape/secret.txt", allowlist)
    check("rebase_symlink_swap_leaf_denied", isinstance(r2, ecc.PathEscape), f"got {r2!r}")

    check("rebase_resolution_mechanism_known", ecc.resolution_mechanism() in ("openat2", "fallback"))


# --------------------------------------------------------------------------
# 5. teardown_cell (unprovable removal -> Quarantined) + reconcile
# --------------------------------------------------------------------------


def test_teardown_and_reconcile():
    state_root = _mkdtemp("state-teardown")
    issued_at, now, expires_at = _fresh_window()
    grant = _make_verified_grant(
        base_revision=_HEAD_OID, logical_paths=["README.md"], allowlist=("README.md",),
        issued_at=issued_at, expires_at=expires_at, revocation_epoch=1,
    )
    reservation = eg.ReplayReservationSet()
    result = ecc.create_cell(
        grant, bare_mirror_path=_MIRROR, cell_state_root=state_root,
        now=now, current_epoch=1, reservation_set=reservation,
    )
    check("teardown_fixture_cell_ready", isinstance(result, ecc.CellReady), f"got {result!r}")
    if not isinstance(result, ecc.CellReady):
        return

    # Simulate "cannot prove removal": strip write permission on the clone
    # directory itself so entries inside it cannot be unlinked (rmtree will
    # raise partway through; the top-level cell_state_dir survives).
    protected_dir = result.cell_root
    os.chmod(protected_dir, 0o500)
    # NOTE: `teardown_cell`'s quarantine step relocates the whole cell dir
    # via `os.rename` (a directory-entry op that needs write only on the
    # PARENT, never on `protected_dir`'s own contents) — so `protected_dir`
    # itself will no longer exist at this path afterward even though its
    # 0o500 mode blocked in-place deletion. Permissions are restored
    # test-wide at the very end via `_chmod_tree_writable` on every temp
    # root, so no per-path chmod-back is needed here.
    outcome = ecc.teardown_cell(result)
    check("teardown_unprovable_is_quarantined", isinstance(outcome, ecc.Quarantined), f"got {outcome!r}")
    if os.path.exists(protected_dir):
        os.chmod(protected_dir, 0o700)
    # The permission block that made removal unprovable is now "fixed"
    # (simulating an operator resolving whatever caused it) so a LATER
    # reconcile() sweep can actually reclaim it with verified proof.
    if isinstance(outcome, ecc.Quarantined) and outcome.quarantine_path:
        _chmod_tree_writable(outcome.quarantine_path)

    # A clean second cell tears down normally (TornDown).
    grant2 = _make_verified_grant(
        base_revision=_HEAD_OID, logical_paths=["README.md"], allowlist=("README.md",),
        issued_at=issued_at, expires_at=expires_at, revocation_epoch=1,
    )
    reservation2 = eg.ReplayReservationSet()
    result2 = ecc.create_cell(
        grant2, bare_mirror_path=_MIRROR, cell_state_root=state_root,
        now=now, current_epoch=1, reservation_set=reservation2,
    )
    check("teardown_second_fixture_ready", isinstance(result2, ecc.CellReady), f"got {result2!r}")
    if isinstance(result2, ecc.CellReady):
        outcome2 = ecc.teardown_cell(result2)
        check("teardown_clean_is_torn_down", isinstance(outcome2, ecc.TornDown), f"got {outcome2!r}")
        check("teardown_clean_dir_gone", not os.path.exists(result2.cell_state_dir))

    # reconcile() reclaims the still-quarantined orphan from the unprovable
    # teardown above (its permissions were restored so it's now reclaimable).
    report = ecc.reconcile(state_root)
    check("reconcile_report_type", isinstance(report, ecc.ReconcileReport), f"got {report!r}")
    check("reconcile_reclaimed_at_least_one", report.reclaimed >= 1, f"got {report!r}")
    check("reconcile_quarantine_now_empty_or_reduced", report.remaining_quarantined == 0, f"got {report!r}")

    # Idempotent: a second sweep on now-clean state reclaims nothing.
    report2 = ecc.reconcile(state_root)
    check("reconcile_idempotent_noop", report2.reclaimed == 0 and report2.remaining_quarantined == 0,
          f"got {report2!r}")

    # reconcile() never escapes cell_state_root: a sibling directory outside
    # state_root must survive untouched even if reconcile is pointed at a
    # DIFFERENT root that happens to be a sibling.
    sibling = _mkdtemp("reconcile-sibling")
    Path(os.path.join(sibling, "must-survive.txt")).write_text("keep me\n")
    unrelated_root = _mkdtemp("state-unrelated-empty")
    ecc.reconcile(unrelated_root)
    check("reconcile_never_touches_outside_root", os.path.exists(os.path.join(sibling, "must-survive.txt")))

    # reconcile() on a nonexistent root is a graceful no-op, never raises.
    report3 = ecc.reconcile(os.path.join(state_root, "does-not-exist"))
    check("reconcile_nonexistent_root_noop",
          report3.reclaimed == 0 and report3.remaining_quarantined == 0 and report3.errors == ())


# --------------------------------------------------------------------------
# 6. Stale / expired / stale-epoch grant -> deny before any disk write
# --------------------------------------------------------------------------


def test_stale_grant_denies_before_disk_write():
    state_root = _mkdtemp("state-stale")
    now = datetime.now(timezone.utc)

    expired_grant = _make_verified_grant(
        base_revision=_HEAD_OID, logical_paths=["README.md"], allowlist=("README.md",),
        issued_at=now - timedelta(hours=2), expires_at=now - timedelta(hours=1), revocation_epoch=1,
    )
    reservation = eg.ReplayReservationSet()
    result = ecc.create_cell(
        expired_grant, bare_mirror_path=_MIRROR, cell_state_root=state_root,
        now=now, current_epoch=1, reservation_set=reservation,
    )
    check("expired_grant_denied",
          isinstance(result, ecc.TypedFailure) and result.code == eg.DENY_EXPIRED, f"got {result!r}")
    check("expired_grant_no_disk_effect", not os.path.exists(os.path.join(state_root, "cells")))
    check("expired_grant_reservation_never_touched", reservation.state_of(expired_grant.grant_id) is None)

    not_yet_grant = _make_verified_grant(
        base_revision=_HEAD_OID, logical_paths=["README.md"], allowlist=("README.md",),
        issued_at=now + timedelta(hours=1), expires_at=now + timedelta(hours=2), revocation_epoch=1,
    )
    result2 = ecc.create_cell(
        not_yet_grant, bare_mirror_path=_MIRROR, cell_state_root=state_root,
        now=now, current_epoch=1, reservation_set=eg.ReplayReservationSet(),
    )
    check("not_yet_valid_grant_denied",
          isinstance(result2, ecc.TypedFailure) and result2.code == eg.DENY_NOT_YET_VALID, f"got {result2!r}")
    check("not_yet_valid_no_disk_effect", not os.path.exists(os.path.join(state_root, "cells")))

    stale_epoch_grant = _make_verified_grant(
        base_revision=_HEAD_OID, logical_paths=["README.md"], allowlist=("README.md",),
        issued_at=now - timedelta(minutes=1), expires_at=now + timedelta(hours=1), revocation_epoch=1,
    )
    result3 = ecc.create_cell(
        stale_epoch_grant, bare_mirror_path=_MIRROR, cell_state_root=state_root,
        now=now, current_epoch=5, reservation_set=eg.ReplayReservationSet(),
    )
    check("stale_epoch_grant_denied",
          isinstance(result3, ecc.TypedFailure) and result3.code == eg.DENY_STALE_EPOCH, f"got {result3!r}")
    check("stale_epoch_no_disk_effect", not os.path.exists(os.path.join(state_root, "cells")))

    result4 = ecc.create_cell(
        stale_epoch_grant, bare_mirror_path=_MIRROR, cell_state_root=state_root,
        now=now, current_epoch=None, reservation_set=eg.ReplayReservationSet(),
    )
    check("unresolvable_epoch_denied",
          isinstance(result4, ecc.TypedFailure) and result4.code == eg.DENY_STALE_EPOCH, f"got {result4!r}")


# --------------------------------------------------------------------------
# 7. Isolation fuzz — crafted alternates / outward symlink rejected
# --------------------------------------------------------------------------


def test_isolation_fuzz_rejects_crafted_clone():
    crafted_root = _mkdtemp("crafted-clone")
    clone_dir = os.path.join(crafted_root, "clone")
    result = subprocess.run(["git", "clone", "-q", "--template=", "--no-local", "--no-hardlinks",
                              _MIRROR, clone_dir], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr

    check("isolation_fuzz_clean_clone_passes", ecc.check_clone_isolation(clone_dir) is None)

    alternates_path = os.path.join(clone_dir, ".git", "objects", "info", "alternates")
    os.makedirs(os.path.dirname(alternates_path), exist_ok=True)
    Path(alternates_path).write_text(os.path.join(_SOURCE_REPO, ".git", "objects") + "\n", encoding="utf-8")
    check("isolation_fuzz_alternates_rejected", ecc.check_clone_isolation(clone_dir) is not None)
    os.remove(alternates_path)
    check("isolation_fuzz_clean_again_after_removal", ecc.check_clone_isolation(clone_dir) is None)

    outside = _mkdtemp("crafted-outside")
    Path(os.path.join(outside, "leak.txt")).write_text("leak\n")
    rogue_link = os.path.join(clone_dir, "rogue_link")
    os.symlink(outside, rogue_link)
    check("isolation_fuzz_symlink_escape_rejected", ecc.check_clone_isolation(clone_dir) is not None)
    os.remove(rogue_link)

    # gitfile-pointer style .git (worktree-style) must be rejected too.
    gitfile_root = _mkdtemp("crafted-gitfile")
    real_git_dir = os.path.join(clone_dir, ".git")
    tmp_holder = os.path.join(gitfile_root, "fake-clone")
    os.makedirs(tmp_holder, exist_ok=True)
    Path(os.path.join(tmp_holder, ".git")).write_text(f"gitdir: {real_git_dir}\n", encoding="utf-8")
    check("isolation_fuzz_gitfile_pointer_rejected", ecc.check_clone_isolation(tmp_holder) is not None)


# --------------------------------------------------------------------------
# 8. Never raises — garbage input fuzz on the public surface
# --------------------------------------------------------------------------


def test_never_raises_on_garbage_input():
    garbage_values = [None, 123, "", [], {}, object()]
    for g in garbage_values:
        try:
            r = ecc.rebase_logical_path(g, "README.md", ("README.md",))
            check(f"rebase_never_raises_cell_root[{g!r}]", isinstance(r, ecc.PathEscape))
        except Exception as exc:  # noqa: BLE001
            check(f"rebase_never_raises_cell_root[{g!r}]", False, f"raised {type(exc).__name__}: {exc}")

        try:
            r = ecc.rebase_logical_path("/tmp", g, ("README.md",))
            check(f"rebase_never_raises_logical_path[{g!r}]", isinstance(r, ecc.PathEscape))
        except Exception as exc:  # noqa: BLE001
            check(f"rebase_never_raises_logical_path[{g!r}]", False, f"raised {type(exc).__name__}: {exc}")

    try:
        report = ecc.reconcile(None)  # type: ignore[arg-type]
        check("reconcile_never_raises_on_none", isinstance(report, ecc.ReconcileReport))
    except Exception as exc:  # noqa: BLE001
        check("reconcile_never_raises_on_none", False, f"raised {type(exc).__name__}: {exc}")


# --------------------------------------------------------------------------
# Runner
# --------------------------------------------------------------------------

if __name__ == "__main__":
    try:
        test_create_cell_happy_path()
        test_unreachable_oid_quarantines()
        test_missing_mirror_clone_failed()
        test_nonwritable_parent_typed_failure_no_disk_effect()
        test_rebase_escape_classes()
        test_teardown_and_reconcile()
        test_stale_grant_denies_before_disk_write()
        test_isolation_fuzz_rejects_crafted_clone()
        test_never_raises_on_garbage_input()
    finally:
        _chmod_tree_writable(_MIRROR)
        for root in _TEMP_ROOTS:
            _chmod_tree_writable(root)
            shutil.rmtree(root, ignore_errors=True)

    _report_and_exit()
