#!/usr/bin/env python3
"""C3b R4 execution-cell performance-measurement harness (NON-ENFORCEMENT).

Implements ONLY the measurement harness authorized by
`.agents/plans/aqos-foundation-c/C3B-R4-DESIGN-AND-AUTHORIZATION.md`
(status R4_REVIEWED_PASS) §3 (budgets), §4 (protocol), §5
(revocation-under-load), §6 (harness surface), §7 (acceptance).

This module DRIVES the already-built, still-dormant C3b R3 runner
(`ai-stack/switchboard/execution_cell_runner.py`, flag+enable OFF,
`ccbc0718`) over a REAL Unix domain socket, minting valid signed grants via
R1's TEST-ONLY `execution_grant.sign()`, against a throwaway self-contained
bare-mirror fixture (R2, `execution_cell_clone.py`) -- exactly the hermetic
pattern already used by `scripts/testing/test-execution-cell-runner.py`.

It is NON-ENFORCEMENT measurement tooling: it CONSUMES R1/R2/R3 as-is and
NEVER modifies them. It opens no live/production socket, wires nothing into
the switchboard, and activates nothing. Per design §9 freeze criteria, the
predecessor hashes (R3 runner, R1 grant, R2 clone) are unaffected by
anything in this module -- confirmed by an empty `git diff` on those three
files after any run of this harness (see the accompanying
`scripts/testing/test-execution-cell-perf-harness.py` self-test and the
VALIDATE step in the R4 build record).

Instrumentation note (why + how, since this is the one subtle part of the
design): the R3 runner's own typed receipt
(`execution_cell_runner.receipt_of`) intentionally carries only a single
`duration_ms` total -- it does NOT expose the six named per-stage
monotonic boundaries the frozen §4 protocol requires
(`clone_done_ns`, `bwrap_started_ns`, `process_terminal_ns`,
`tree_absent_ns`, `validation_done_ns`, `receipt_published_ns`). Since this
harness may NOT edit the runner's source to add that instrumentation, it
obtains those boundaries the same way an external profiler/tracer would:
by rebinding a small number of MODULE-LEVEL function references, at
runtime, in this harness's own process, to thin wrapper functions that
record a timestamp and then delegate 100% of behavior to the ORIGINAL
function -- never skipping a check, never altering an outcome, never
persisted to any file. This is a measurement technique, not a modification
of enforcement code (the on-disk `.py` files are byte-for-byte unchanged;
`git diff` proves it). `receipt_published_ns` and the receipt_id
correlation key require NO patching at all -- `RunnerConfig.receipt_sink`
is an already-existing, already-authorized extension point (R3 design §3)
built exactly for this kind of external consumption.

Run for real (operator, full protocol, on the actual APU):
    python3 scripts/testing/perf/execution-cell-perf-harness.py \\
        --out /tmp/r4-acceptance-report.json --n 40

Fast/self-test mode (tiny N, used by the offline self-test only):
    python3 scripts/testing/perf/execution-cell-perf-harness.py --fast

Revocation-under-load mode (§5):
    python3 scripts/testing/perf/execution-cell-perf-harness.py \\
        --revocation-under-load --concurrency-cap 2
"""

from __future__ import annotations

import argparse
import ctypes
import errno
import hashlib
import json
import math
import os
import platform
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import types
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Optional

_THIS_FILE = Path(__file__).resolve()
_REPO_ROOT = _THIS_FILE.parents[3]
_LIB_DIR = str(_REPO_ROOT / "scripts" / "ai" / "lib")
_SWITCHBOARD_DIR = str(_REPO_ROOT / "ai-stack" / "switchboard")
for _p in (_LIB_DIR, _SWITCHBOARD_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import execution_grant as eg  # noqa: E402
import execution_cell_clone as ecc  # noqa: E402
import execution_cell_runner as runner  # noqa: E402
import execution_cell_validator as validator  # noqa: E402

# ---------------------------------------------------------------------------
# Frozen constants (design §3/§4 -- do not hand-tune to make a run pass; a
# budget miss is a real R3 finding, never a harness-side adjustment).
# ---------------------------------------------------------------------------

SCHEMA_VERSION = 1

COMMAND_NOOP = runner.COMMAND_NOOP
COMMAND_READ_VALIDATE = runner.COMMAND_READ_VALIDATE
COMMAND_SINGLE_FILE_WRITE = runner.COMMAND_SINGLE_FILE_WRITE
COMMAND_CLASSES = (COMMAND_NOOP, COMMAND_READ_VALIDATE, COMMAND_SINGLE_FILE_WRITE)

COHORT_COLD = "cold"
COHORT_WARM = "warm"
CACHE_COHORTS = (COHORT_COLD, COHORT_WARM)

DEFAULT_N = 40
DEFAULT_DISCARDED_SETUP_ITERATIONS = 5
COLD_RESIDENCY_MAX_PCT = 5.0
WARM_RESIDENCY_MIN_PCT = 95.0
ACCEPTANCE_MIN_MEM_AVAILABLE_BYTES = 8 * 1024 * 1024 * 1024
PRESSURE_MIN_MEM_AVAILABLE_BYTES = 6 * 1024 * 1024 * 1024
DEFAULT_CONCURRENCY = 1
MAX_CONCURRENCY_BEFORE_REVIEW = 2
REVOCATION_TEARDOWN_BUDGET_S = 5.0

BUDGET_CLONE_LATENCY_P95_S = 3.0
BUDGET_BWRAP_SPAWN_LATENCY_P95_S = 0.250
BUDGET_PEAK_INCREMENTAL_RSS_BYTES = 768 * 1024 * 1024
BUDGET_TEARDOWN_LATENCY_P95_S = 5.0
BUDGET_UNTYPED_OUTCOME_COUNT = 0

BUDGETS: dict = {
    "clone_latency_p95_s": {
        "limit": BUDGET_CLONE_LATENCY_P95_S, "unit": "s", "agg": "p95",
        "source": "clone_done_ns - monotonic_start_ns",
    },
    "bwrap_spawn_latency_p95_s": {
        "limit": BUDGET_BWRAP_SPAWN_LATENCY_P95_S, "unit": "s", "agg": "p95",
        "source": "bwrap_started_ns - clone_done_ns",
    },
    "peak_incremental_rss_bytes": {
        "limit": BUDGET_PEAK_INCREMENTAL_RSS_BYTES, "unit": "bytes", "agg": "max",
        "source": "cgroup_peak_bytes - idle_baseline_bytes",
    },
    "teardown_latency_p95_s": {
        "limit": BUDGET_TEARDOWN_LATENCY_P95_S, "unit": "s", "agg": "p95",
        "source": "revocation-under-load: tree_absent_ns - epoch_bump_ns",
    },
    "untyped_outcome_count": {
        "limit": BUDGET_UNTYPED_OUTCOME_COUNT, "unit": "count", "agg": "sum",
        "source": "rows whose outcome/denial_code is outside the known typed vocabulary",
    },
}

VERDICT_PASS = "PASS"
VERDICT_FAIL = "FAIL"
VERDICT_INVALID = "INVALID"

# Typed outcome vocabulary this harness itself assigns to a sample row
# (design §4: "No failed/denied sample is discarded"). `harness-transport`
# covers a genuine client<->UDS transport failure (timeout, malformed
# response) -- still a TYPED, accounted-for outcome, never silently dropped.
OUTCOME_GREEN = runner.DECISION_GREEN
OUTCOME_RED = runner.DECISION_RED
OUTCOME_QUARANTINED = runner.DECISION_QUARANTINED
OUTCOME_DENIED = runner.DECISION_DENIED
OUTCOME_HARNESS_TRANSPORT = "harness-transport-error"
ALLOWED_OUTCOMES = frozenset({
    OUTCOME_GREEN, OUTCOME_RED, OUTCOME_QUARANTINED, OUTCOME_DENIED, OUTCOME_HARNESS_TRANSPORT,
})

# The runner/R1/R2's own closed typed-reason vocabulary -- used only to
# validate that a non-null `denial_code` is a KNOWN code, never invented by
# this harness (the "zero unaccounted/untyped outcomes" gate, design §4/§5).
_KNOWN_RUNNER_REASONS = frozenset({
    runner.REASON_FLAG_OFF, runner.REASON_PEER_REJECTED, runner.REASON_REQUEST_MALFORMED,
    runner.REASON_CONFINEMENT_UNAVAILABLE, runner.REASON_COMMAND_UNSUPPORTED,
    runner.REASON_UNKNOWN_TRUSTED_REPO, runner.REASON_TREE_NOT_PROVEN_ABSENT,
    runner.REASON_MALFORMED_RESULT, runner.REASON_COMMAND_FAILED, runner.REASON_FINAL_FENCE_FAILED,
    runner.REASON_RUNNER_INTERNAL_ERROR, runner.REASON_RUNNER_BUSY, runner.REASON_OK,
})
_KNOWN_R1_DENIALS = frozenset({
    eg.DENY_MALFORMED, eg.DENY_BAD_SIGNATURE, eg.DENY_EXPIRED, eg.DENY_NOT_YET_VALID,
    eg.DENY_UNKNOWN_VERSION, eg.DENY_STALE_EPOCH, eg.DENY_REPLAYED,
    eg.DENY_CLASSIFICATION_AMBIGUOUS, eg.DENY_PATH_INVALID,
})
_KNOWN_R2_FAILURES = frozenset({
    ecc.FAILURE_BASE_OID_UNREACHABLE, ecc.FAILURE_CLONE_FAILED, ecc.FAILURE_ISOLATION_VIOLATION,
    ecc.FAILURE_PATH_ESCAPE, ecc.FAILURE_DISK_EXHAUSTED, ecc.FAILURE_QUARANTINED,
})
KNOWN_DENIAL_CODES = _KNOWN_RUNNER_REASONS | _KNOWN_R1_DENIALS | _KNOWN_R2_FAILURES


def _is_known_denial_code(code: Optional[str]) -> bool:
    """A `denial_code` is known-typed if it is exactly one of the closed
    codes above, OR is a `f"{REASON_RUNNER_INTERNAL_ERROR}:{ExceptionName}"` /
    `f"validator:{reason}"` composite -- both of those prefixes are
    themselves part of the runner's own typed vocabulary (see
    `execution_cell_runner.process_grant`/`_confine_run_validate`); the
    suffix is an unbounded-but-still-typed detail, not an untyped escape."""
    if code is None:
        return True
    if code in KNOWN_DENIAL_CODES:
        return True
    if code.startswith(f"{runner.REASON_RUNNER_INTERNAL_ERROR}:"):
        return True
    if code.startswith("validator:"):
        return True
    if code.startswith("harness-transport:"):
        return True
    if code.startswith("unrecognized-decision:"):
        return True
    return False


# ---------------------------------------------------------------------------
# Pure math: nearest-rank p95 (design §4 -- "no averaging of percentiles").
# ---------------------------------------------------------------------------


def p95_nearest_rank(samples: "list[float] | tuple[float, ...]") -> Optional[float]:
    """`sorted[ceil(0.95*N)-1]` -- the exact nearest-rank definition frozen
    by design §4. Returns None for an empty input (never fabricates a
    number for zero samples)."""
    values = sorted(samples)
    n = len(values)
    if n == 0:
        return None
    k = math.ceil(0.95 * n)
    k = max(1, min(k, n))
    return values[k - 1]


# ---------------------------------------------------------------------------
# Host bounds (design §4: CPU governor, kernel, build revision, MemAvailable,
# swap delta).
# ---------------------------------------------------------------------------


def _read_meminfo() -> dict:
    out: dict = {}
    try:
        with open("/proc/meminfo", "r", encoding="utf-8") as fh:
            for line in fh:
                parts = line.split(":")
                if len(parts) != 2:
                    continue
                key = parts[0].strip()
                value_str = parts[1].strip().split()[0]
                try:
                    out[key] = int(value_str) * 1024  # kB -> bytes
                except ValueError:
                    continue
    except OSError:
        pass
    return out


def mem_available_bytes() -> Optional[int]:
    return _read_meminfo().get("MemAvailable")


def swap_free_bytes() -> Optional[int]:
    return _read_meminfo().get("SwapFree")


def cpu_governor() -> Optional[str]:
    try:
        path = "/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor"
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as fh:
                return fh.read().strip()
    except OSError:
        pass
    return None


def git_build_revision() -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", str(_REPO_ROOT), "rev-parse", "HEAD"],
            check=False, capture_output=True, text=True, timeout=10,
        )
        if proc.returncode == 0:
            return proc.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    return "unknown"


def host_fingerprint() -> dict:
    return {
        "hostname": platform.node(),
        "machine": platform.machine(),
        "kernel": platform.release(),
        "cpu_governor": cpu_governor(),
        "mem_total_bytes": _read_meminfo().get("MemTotal"),
    }


# ---------------------------------------------------------------------------
# Cache validity: posix_fadvise(DONTNEED) eviction + ctypes mincore residency
# (design §4). The DECISION logic (`cohort_cache_valid`) is a pure function
# of a measured percentage so it is independently unit-testable without any
# real I/O -- the self-test exercises exactly that pure function.
# ---------------------------------------------------------------------------

_libc_handle: Optional[ctypes.CDLL] = None


def _libc() -> ctypes.CDLL:
    global _libc_handle
    if _libc_handle is None:
        handle = ctypes.CDLL("libc.so.6", use_errno=True)
        handle.mmap.restype = ctypes.c_void_p
        handle.mmap.argtypes = [
            ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_long,
        ]
        handle.munmap.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
        handle.munmap.restype = ctypes.c_int
        handle.mincore.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_ubyte)]
        handle.mincore.restype = ctypes.c_int
        _libc_handle = handle
    return _libc_handle


_PROT_READ = 0x1
_MAP_SHARED = 0x1
_MAP_FAILED = ctypes.c_void_p(-1).value


def mincore_residency_pct(path: str) -> float:
    """Real `mmap(2)` + `mincore(2)` via ctypes (design §4 explicitly names
    `mincore`; Python has no stdlib wrapper). Returns the percentage of the
    file's pages currently resident in the page cache. Raises OSError on
    any genuine failure -- callers decide how to treat an unmeasurable
    file (never silently reported as 0% or 100%)."""
    fd = os.open(path, os.O_RDONLY)
    try:
        size = os.fstat(fd).st_size
        if size == 0:
            return 100.0
        pagesize = os.sysconf("SC_PAGE_SIZE")
        length = ((size + pagesize - 1) // pagesize) * pagesize
        libc = _libc()
        addr = libc.mmap(None, length, _PROT_READ, _MAP_SHARED, fd, 0)
        if addr is None or addr == 0 or addr == _MAP_FAILED:
            err = ctypes.get_errno()
            raise OSError(err, f"mmap failed: {os.strerror(err)}", path)
        try:
            npages = length // pagesize
            vec = (ctypes.c_ubyte * npages)()
            ret = libc.mincore(ctypes.c_void_p(addr), ctypes.c_size_t(length), vec)
            if ret != 0:
                err = ctypes.get_errno()
                raise OSError(err, f"mincore failed: {os.strerror(err)}", path)
            resident = sum(1 for b in vec if (b & 1))
            return 100.0 * resident / npages
        finally:
            libc.munmap(ctypes.c_void_p(addr), length)
    finally:
        os.close(fd)


def evict_cache(path: str) -> None:
    """`posix_fadvise(fd, 0, 0, POSIX_FADV_DONTNEED)` over the whole file
    (design §4). An `fsync` immediately precedes the advise call: DONTNEED
    only ever drops CLEAN pages, and a just-written file's pages are still
    dirty until written back, so without the fsync the advise is silently a
    no-op on a real (non-tmpfs) filesystem. Best-effort at the OS level
    (the kernel MAY keep pages it deems still useful) -- the caller always
    re-verifies via `mincore_residency_pct` rather than trusting this call
    succeeded."""
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
        os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_DONTNEED)
    finally:
        os.close(fd)


def prime_cache(path: str) -> None:
    """Untimed full sequential read to bring every page of `path` into the
    page cache (design §4: warm cohort's "untimed priming run")."""
    with open(path, "rb") as fh:
        while fh.read(1 << 20):
            pass


def cohort_cache_valid(cohort: str, residency_pct: float) -> bool:
    """Pure decision (design §4): cold requires <=5% resident, warm
    requires >=95% resident. Deliberately separated from the real I/O
    (`mincore_residency_pct`/`evict_cache`/`prime_cache`) so the DECISION
    logic is unit-testable on synthetic percentages without any real
    eviction/priming (see the self-test)."""
    if cohort == COHORT_COLD:
        return residency_pct <= COLD_RESIDENCY_MAX_PCT
    if cohort == COHORT_WARM:
        return residency_pct >= WARM_RESIDENCY_MIN_PCT
    raise ValueError(f"unknown cache cohort: {cohort!r}")


def verify_cache_cohort(path: str, cohort: str) -> "tuple[bool, float]":
    """Real I/O + real decision for one sample: cold evicts-then-measures;
    warm just measures (priming already happened once, untimed, before the
    cohort's sampling loop began). Returns `(valid, residency_pct)`."""
    if cohort == COHORT_COLD:
        evict_cache(path)
    pct = mincore_residency_pct(path)
    return cohort_cache_valid(cohort, pct), pct


# ---------------------------------------------------------------------------
# Fixture builders (reuses the exact hermetic pattern of
# scripts/testing/test-execution-cell-runner.py).
# ---------------------------------------------------------------------------


def _fs_type_of(path: str) -> Optional[str]:
    """Best-effort filesystem type of the mount covering `path`, via the
    longest-prefix-matching entry in `/proc/mounts`. Returns None if
    unresolvable (never raises)."""
    try:
        real = os.path.realpath(path)
    except OSError:
        return None
    best_match = ""
    best_type: Optional[str] = None
    try:
        with open("/proc/mounts", "r", encoding="utf-8") as fh:
            for line in fh:
                parts = line.split()
                if len(parts) < 3:
                    continue
                mountpoint, fstype = parts[1], parts[2]
                if real == mountpoint or real.startswith(mountpoint.rstrip("/") + "/") or mountpoint == "/":
                    if len(mountpoint) >= len(best_match):
                        best_match = mountpoint
                        best_type = fstype
    except OSError:
        return None
    return best_type


_DISK_BACKED_TMP_ROOT: Optional[str] = None
_TMPFS_LIKE_FSTYPES = frozenset({"tmpfs", "ramfs"})


def disk_backed_tmp_root() -> str:
    """The cold/warm cache-validity protocol (design §4) requires a REAL
    page-cache-backed file: `posix_fadvise(DONTNEED)` is a silent no-op on
    tmpfs/ramfs (there is no separate backing store to evict to -- the
    "page cache" entry IS the storage), which would make every cold-cohort
    residency check falsely report 100% resident forever. This picks the
    first writable, non-tmpfs/ramfs candidate directory
    (`AQ_R4_PERF_TMPDIR` env override, then `/var/tmp`, then the platform
    temp dir, then `$HOME`) and raises loudly if none qualifies -- never
    silently falls back to a tmpfs path that would make cache-validity
    unmeasurable."""
    global _DISK_BACKED_TMP_ROOT
    if _DISK_BACKED_TMP_ROOT is not None:
        return _DISK_BACKED_TMP_ROOT
    candidates = []
    env_override = os.environ.get("AQ_R4_PERF_TMPDIR")
    if env_override:
        candidates.append(env_override)
    candidates += ["/var/tmp", tempfile.gettempdir(), os.path.expanduser("~")]
    for candidate in candidates:
        try:
            if not os.path.isdir(candidate) or not os.access(candidate, os.W_OK):
                continue
            if _fs_type_of(candidate) in _TMPFS_LIKE_FSTYPES:
                continue
            _DISK_BACKED_TMP_ROOT = candidate
            return candidate
        except OSError:
            continue
    raise RuntimeError(
        "no disk-backed writable temp directory found for cache-validity fixtures "
        "(design §4 requires real page-cache eviction, which tmpfs/ramfs cannot provide) -- "
        "set AQ_R4_PERF_TMPDIR to a non-tmpfs path"
    )


_TEMP_ROOTS: "list[str]" = []


def _mkdtemp(prefix: str) -> str:
    d = tempfile.mkdtemp(prefix=f"c3b-r4-perf-{prefix}-", dir=disk_backed_tmp_root())
    _TEMP_ROOTS.append(d)
    return d


def cleanup_temp_roots() -> None:
    for d in _TEMP_ROOTS:
        shutil.rmtree(d, ignore_errors=True)
    _TEMP_ROOTS.clear()


def _run_git(args: "list[str]", cwd: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git"] + args, cwd=cwd, check=False, capture_output=True, text=True,
        env={
            **os.environ, "GIT_AUTHOR_NAME": "R4 Perf Harness", "GIT_AUTHOR_EMAIL": "r4-perf@example.invalid",
            "GIT_COMMITTER_NAME": "R4 Perf Harness", "GIT_COMMITTER_EMAIL": "r4-perf@example.invalid",
        },
    )


def build_source_repo() -> "tuple[str, str]":
    src = _mkdtemp("source")
    assert _run_git(["init", "-q", "-b", "main"], src).returncode == 0
    os.makedirs(os.path.join(src, "allowed_dir"), exist_ok=True)
    Path(src, "allowed_dir", "writable.txt").write_text("initial content\n", encoding="utf-8")
    Path(src, "allowed_dir", "inner.txt").write_text("read-validate me\n", encoding="utf-8")
    assert _run_git(["add", "-A"], src).returncode == 0
    commit = _run_git(["commit", "-q", "-m", "initial"], src)
    assert commit.returncode == 0, commit.stderr
    rev = _run_git(["rev-parse", "HEAD"], src)
    assert rev.returncode == 0, rev.stderr
    return src, rev.stdout.strip()


def build_bare_mirror(source_repo: str) -> str:
    """Builds a bare mirror AND repacks it into a single pack file -- the
    dedicated "trusted test-object source" this harness evicts/primes for
    cache-validity (design §4). A single consolidated pack file gives a
    concrete, mmap-able target; a freshly `--mirror`-cloned tiny repo may
    otherwise keep only loose objects, which is not a stable eviction
    target."""
    mirror = os.path.join(_mkdtemp("mirror-parent"), "mirror.git")
    result = subprocess.run(
        ["git", "clone", "-q", "--mirror", source_repo, mirror], check=False, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    repack = subprocess.run(
        ["git", "-C", mirror, "repack", "-a", "-d", "-f", "-q"], check=False, capture_output=True, text=True,
    )
    assert repack.returncode == 0, repack.stderr
    return mirror


def find_trusted_object_source(mirror_path: str) -> str:
    """The concrete file this harness evicts/primes: the (single, after
    `repack -a -d -f`) pack file under `<mirror>/objects/pack/*.pack`."""
    pack_dir = os.path.join(mirror_path, "objects", "pack")
    candidates = sorted(p for p in os.listdir(pack_dir) if p.endswith(".pack"))
    if not candidates:
        raise RuntimeError(f"no consolidated pack file found under {pack_dir!r}")
    return os.path.join(pack_dir, candidates[0])


_CGROUP_PARENT_CACHE: "Optional[str]" = None
_CGROUP_PARENT_PROBED = False


def detect_delegated_cgroup_parent() -> "Optional[str]":
    """Same discovery as `test-execution-cell-runner.py`: a real, writable,
    delegated cgroup v2 subtree this process can create/remove child
    cgroups under. Returns None if the host offers nothing usable -- the
    caller records `UNAVAILABLE`, never a fabricated number."""
    global _CGROUP_PARENT_CACHE, _CGROUP_PARENT_PROBED
    if _CGROUP_PARENT_PROBED:
        return _CGROUP_PARENT_CACHE
    _CGROUP_PARENT_PROBED = True
    uid = os.getuid()
    candidates = [
        f"/sys/fs/cgroup/user.slice/user-{uid}.slice/user@{uid}.service/background.slice",
        f"/sys/fs/cgroup/user.slice/user-{uid}.slice/user@{uid}.service/app.slice",
        "/sys/fs/cgroup/aq-r4-perf.slice",
    ]
    for base in candidates:
        if not os.path.isdir(base):
            continue
        probe = os.path.join(base, f"aq-r4-probe-{os.getpid()}")
        try:
            os.mkdir(probe)
            os.rmdir(probe)
            _CGROUP_PARENT_CACHE = base
            return base
        except OSError:
            continue
    return None


def measure_idle_cgroup_baseline(cgroup_parent: str) -> "Optional[int]":
    """The "measured idle-runner baseline" design §4 subtracts from a
    cell's peak `memory.current`: a freshly created, empty delegated
    cgroup's own `memory.current` (accounting overhead, not any cell
    workload). Returns None (UNAVAILABLE) if it cannot be measured."""
    path = runner.create_cgroup(cgroup_parent, f"idle-baseline-{uuid.uuid4().hex[:12]}")
    if path is None:
        return None
    try:
        value = _read_cgroup_memory_current(path)
        return value
    finally:
        try:
            os.rmdir(path)
        except OSError:
            pass


def _read_cgroup_memory_current(cgroup_path: str) -> "Optional[int]":
    try:
        with open(os.path.join(cgroup_path, "memory.current"), "r", encoding="utf-8") as fh:
            return int(fh.read().strip())
    except (OSError, ValueError):
        return None


def _read_cgroup_memory_peak(cgroup_path: str) -> "Optional[int]":
    try:
        with open(os.path.join(cgroup_path, "memory.peak"), "r", encoding="utf-8") as fh:
            return int(fh.read().strip())
    except (OSError, ValueError):
        return _read_cgroup_memory_current(cgroup_path)


_BWRAP_PATH = shutil.which("bwrap")
_PYTHON_BIN = os.path.realpath(sys.executable)


def _rfc3339(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def make_signed_grant(
    private_key,
    *,
    base_revision: str,
    trusted_repo_id: str,
    command_class: str,
    revocation_epoch: int = 0,
    timeout_s: int = 30,
) -> dict:
    """Builds a fresh, TEST-ONLY-signed grant (R1's `sign()`) for exactly
    one of the three closed R3 command classes (design §4)."""
    now = datetime.now(timezone.utc)
    if command_class == COMMAND_NOOP:
        effect_set = [{"effect": "read", "scope": {"paths": ["allowed_dir/inner.txt"], "mode": "read"}}]
    elif command_class == COMMAND_READ_VALIDATE:
        import hashlib as _hashlib

        expected = _hashlib.sha256(b"read-validate me\n").hexdigest()
        effect_set = [{
            "effect": "deterministic-validate",
            "scope": {"paths": ["allowed_dir/inner.txt"], "expected_sha256": expected},
        }]
    elif command_class == COMMAND_SINGLE_FILE_WRITE:
        effect_set = [{
            "effect": "write",
            "scope": {
                "paths": ["allowed_dir/writable.txt"], "mode": "write",
                "content": f"perf-sample {uuid.uuid4().hex}\n", "encoding": "utf-8",
            },
        }]
    else:
        raise ValueError(f"unknown command class: {command_class!r}")

    grant = {
        "grant_schema_version": 1,
        "grant_id": uuid.uuid4().hex + uuid.uuid4().hex,
        "lease_id": "lease-" + uuid.uuid4().hex,
        "task_id": "task-" + uuid.uuid4().hex,
        "request_id": "req-" + uuid.uuid4().hex,
        "issued_at": _rfc3339(now - timedelta(seconds=1)),
        "expires_at": _rfc3339(now + timedelta(minutes=10)),
        "revocation_epoch": revocation_epoch,
        "base_revision": base_revision,
        "effect_set": effect_set,
        "exec_class": "sandbox-required",
        "trusted_repo_id": trusted_repo_id,
        "logical_paths": ["allowed_dir"],
        "resource_limits": {"timeout_s": timeout_s, "max_output_bytes": 65536, "cell_class": "small"},
    }
    return eg.sign(grant, private_key)


# ---------------------------------------------------------------------------
# Instrumentation (see module docstring): thin, delegating, timestamp-only
# wrappers rebound at the MODULE level, in THIS process only. Never
# persisted; never alters behavior/outcome.
# ---------------------------------------------------------------------------

_now_ns = lambda: time.clock_gettime(time.CLOCK_MONOTONIC_RAW) * 1e9  # noqa: E731

_THREAD_EVENTS_LOCK = threading.Lock()
_THREAD_EVENTS: "dict[int, dict]" = {}


def _record_event(name: str, value) -> None:
    tid = threading.get_ident()
    with _THREAD_EVENTS_LOCK:
        _THREAD_EVENTS.setdefault(tid, {})[name] = value


def _pop_thread_events() -> dict:
    tid = threading.get_ident()
    with _THREAD_EVENTS_LOCK:
        return _THREAD_EVENTS.pop(tid, {})


class _SubprocessProxy:
    """Delegates every attribute to the REAL `subprocess` module except
    `Popen`, which is timestamped before delegating. Rebound ONLY onto
    `execution_cell_runner`'s own module-level `subprocess` name (a
    per-module global binding) -- `execution_cell_clone.py`'s and
    `execution_cell_validator.py`'s OWN separate `import subprocess`
    bindings are completely untouched, so git-clone/cat-file/checkout/
    rev-parse subprocess calls (all `subprocess.run`, implemented via the
    REAL, unwrapped `Popen`) are never observed by this proxy."""

    def __init__(self, real_module):
        self._real = real_module

    def Popen(self, *args, **kwargs):
        _record_event("bwrap_started_ns", _now_ns())
        return self._real.Popen(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._real, name)


class _InstrumentedRunner:
    """Context manager installing/removing the timing wrappers around
    `execution_cell_clone.create_cell`, `execution_cell_runner.subprocess`
    (Popen only), `execution_cell_runner.terminate_cgroup_tree`, and
    `execution_cell_validator.validate`. Idempotent re-entrant-safe within
    a single harness process (this harness never nests two instances)."""

    def __enter__(self):
        self._orig_create_cell = ecc.create_cell
        self._orig_terminate = runner.terminate_cgroup_tree
        self._orig_validate = validator.validate
        self._orig_runner_subprocess = runner.subprocess

        def _wrapped_create_cell(*args, **kwargs):
            result = self._orig_create_cell(*args, **kwargs)
            if isinstance(result, ecc.CellReady):
                _record_event("clone_done_ns", _now_ns())
            return result

        def _wrapped_terminate(cgroup_path, sigterm_grace_s, kill_proof_budget_s):
            _record_event("process_terminal_ns", _now_ns())
            peak = _read_cgroup_memory_peak(cgroup_path)
            if peak is not None:
                _record_event("cgroup_peak_bytes", peak)
            proven, kill_used = self._orig_terminate(cgroup_path, sigterm_grace_s, kill_proof_budget_s)
            if proven:
                _record_event("tree_absent_ns", _now_ns())
            return proven, kill_used

        def _wrapped_validate(**kwargs):
            result = self._orig_validate(**kwargs)
            _record_event("validation_done_ns", _now_ns())
            return result

        ecc.create_cell = _wrapped_create_cell
        runner.terminate_cgroup_tree = _wrapped_terminate
        validator.validate = _wrapped_validate
        runner.subprocess = _SubprocessProxy(self._orig_runner_subprocess)
        return self

    def __exit__(self, exc_type, exc, tb):
        ecc.create_cell = self._orig_create_cell
        runner.terminate_cgroup_tree = self._orig_terminate
        validator.validate = self._orig_validate
        runner.subprocess = self._orig_runner_subprocess
        return False


# ---------------------------------------------------------------------------
# UDS driving (design §6: "drives the R3 runner over a real UDS").
# ---------------------------------------------------------------------------


@dataclass
class RunnerHandle:
    config: "runner.RunnerConfig"
    stop_event: threading.Event
    thread: threading.Thread

    def stop(self) -> None:
        self.stop_event.set()
        self.thread.join(timeout=5)


def start_runner_server(config: "runner.RunnerConfig") -> RunnerHandle:
    stop_event = threading.Event()
    thread = threading.Thread(target=runner.serve_forever, args=(config, stop_event), daemon=True)
    thread.start()
    time.sleep(0.3)  # let the socket bind before the first client connects
    return RunnerHandle(config=config, stop_event=stop_event, thread=thread)


def send_grant_over_uds(socket_path: str, grant: dict, timeout_s: float = 30.0) -> "tuple[Optional[dict], Optional[str]]":
    """Real UDS client round-trip. Returns `(response_dict, transport_error)`
    -- exactly one of the two is non-None. Never raises."""
    try:
        conn = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        conn.settimeout(timeout_s)
        conn.connect(socket_path)
        conn.sendall(json.dumps(grant).encode("utf-8"))
        conn.shutdown(socket.SHUT_WR)
        chunks = []
        while True:
            chunk = conn.recv(65536)
            if not chunk:
                break
            chunks.append(chunk)
        conn.close()
        raw = b"".join(chunks)
        if not raw:
            return None, "empty-response"
        return json.loads(raw.decode("utf-8")), None
    except socket.timeout:
        return None, "timeout"
    except (OSError, ValueError, UnicodeDecodeError) as exc:
        return None, f"{type(exc).__name__}:{exc}"


# ---------------------------------------------------------------------------
# Sample row + cohort result types.
# ---------------------------------------------------------------------------


@dataclass
class CohortResult:
    command_class: str
    cache_cohort: str
    valid: bool
    invalid_reason: Optional[str] = None
    successful_samples: int = 0
    attempted_samples: int = 0


def _build_sample_row(
    *, run_id: str, host_fp: dict, kernel: str, build_revision: str, command_class: str, cache_cohort: str,
    cache_residency_pct: Optional[float], sample_index: int, monotonic_start_ns: float,
    events: dict, idle_baseline_bytes: Optional[int], mem_available: Optional[int], swap_delta: Optional[int],
    outcome: str, denial_code: Optional[str],
) -> dict:
    cgroup_peak = events.get("cgroup_peak_bytes")
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "host_fingerprint": host_fp,
        "kernel": kernel,
        "build_revision": build_revision,
        "command_class": command_class,
        "cache_cohort": cache_cohort,
        "cache_residency_pct": cache_residency_pct,
        "sample_index": sample_index,
        "monotonic_start_ns": monotonic_start_ns,
        "clone_done_ns": events.get("clone_done_ns"),
        "bwrap_started_ns": events.get("bwrap_started_ns"),
        "process_terminal_ns": events.get("process_terminal_ns"),
        "tree_absent_ns": events.get("tree_absent_ns"),
        "validation_done_ns": events.get("validation_done_ns"),
        "receipt_published_ns": events.get("receipt_published_ns"),
        "cgroup_peak_bytes": cgroup_peak,
        "idle_baseline_bytes": idle_baseline_bytes,
        "mem_available_bytes": mem_available,
        "swap_delta_bytes": swap_delta,
        "outcome": outcome,
        "denial_code": denial_code,
    }


def row_content_digest(row: dict) -> str:
    payload = json.dumps(row, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


# ---------------------------------------------------------------------------
# The core protocol driver (design §4).
# ---------------------------------------------------------------------------


class PerfHarness:
    def __init__(self, *, n: int, discarded_setup_iterations: int = DEFAULT_DISCARDED_SETUP_ITERATIONS):
        self.n = n
        self.discarded_setup_iterations = discarded_setup_iterations
        self.run_id = uuid.uuid4().hex
        self.private_key, self.public_key_bytes = eg.generate_keypair()
        self.source_repo, self.head_oid = build_source_repo()
        self.mirror = build_bare_mirror(self.source_repo)
        self.trusted_object_source = find_trusted_object_source(self.mirror)
        self.trusted_repo_id = "r4-perf-test-repo"
        self.cell_state_root = _mkdtemp("cell-state")
        self.cgroup_parent = detect_delegated_cgroup_parent()
        self.idle_baseline_bytes = (
            measure_idle_cgroup_baseline(self.cgroup_parent) if self.cgroup_parent else None
        )
        self.build_revision = git_build_revision()
        self.host_fp = host_fingerprint()
        self.rows: "list[dict]" = []
        self.cohort_results: "list[CohortResult]" = []
        self._events_from_response: "dict[str, dict]" = {}
        self._events_lock = threading.Lock()

    # -- runner config / server lifecycle --------------------------------

    def _receipt_sink(self, record: dict) -> None:
        events = _pop_thread_events()
        events["receipt_published_ns"] = _now_ns()
        receipt_id = record.get("receipt_id")
        if isinstance(receipt_id, str):
            with self._events_lock:
                self._events_from_response[receipt_id] = {**events, "_record": record}

    def _base_config(self, **overrides) -> "runner.RunnerConfig":
        defaults = dict(
            socket_path=os.path.join(_mkdtemp("sock-dir"), "control.sock"),
            client_uid=os.getuid(),
            client_gid=None,
            public_key_bytes=self.public_key_bytes,
            trusted_repo_mirrors={self.trusted_repo_id: self.mirror},
            cell_state_root=self.cell_state_root,
            cgroup_parent=self.cgroup_parent or _mkdtemp("fake-cgroup-parent"),
            python_bin=_PYTHON_BIN,
            bwrap_path=_BWRAP_PATH,
            reservation_set=eg.ReplayReservationSet(),
            cell_reservation_set=eg.ReplayReservationSet(),
            epoch_source=0,
            max_concurrent_cells=DEFAULT_CONCURRENCY,
            env={"CAPABILITY_EXECUTION_CELLS": "1"},
            receipt_sink=self._receipt_sink,
        )
        defaults.update(overrides)
        return runner.RunnerConfig(**defaults)

    # -- one sample --------------------------------------------------------

    def _take_one_sample(
        self, handle: RunnerHandle, command_class: str, cache_cohort: str, sample_index: int,
    ) -> dict:
        valid, residency_pct = verify_cache_cohort(self.trusted_object_source, cache_cohort)
        if not valid:
            raise _CacheValidityError(cache_cohort, residency_pct)

        mem_before = mem_available_bytes()
        swap_before = swap_free_bytes()

        grant = make_signed_grant(
            self.private_key, base_revision=self.head_oid, trusted_repo_id=self.trusted_repo_id,
            command_class=command_class,
        )
        monotonic_start_ns = _now_ns()
        response, transport_error = send_grant_over_uds(handle.config.socket_path, grant)
        mem_after = mem_available_bytes()
        swap_after = swap_free_bytes()
        swap_delta = None
        if swap_before is not None and swap_after is not None:
            swap_delta = swap_before - swap_after

        if transport_error is not None or response is None:
            outcome = OUTCOME_HARNESS_TRANSPORT
            denial_code = f"harness-transport:{transport_error}"
            events = {}
        else:
            receipt_id = response.get("receipt_id")
            with self._events_lock:
                events = self._events_from_response.pop(receipt_id, {}) if isinstance(receipt_id, str) else {}
            outcome = response.get("decision") if response.get("decision") in ALLOWED_OUTCOMES else OUTCOME_HARNESS_TRANSPORT
            denial_code = response.get("reason") if outcome != OUTCOME_GREEN else None
            if outcome == OUTCOME_HARNESS_TRANSPORT and response.get("decision") not in ALLOWED_OUTCOMES:
                denial_code = f"unrecognized-decision:{response.get('decision')!r}"

        row = _build_sample_row(
            run_id=self.run_id, host_fp=self.host_fp, kernel=self.host_fp.get("kernel", "unknown"),
            build_revision=self.build_revision, command_class=command_class, cache_cohort=cache_cohort,
            cache_residency_pct=residency_pct, sample_index=sample_index, monotonic_start_ns=monotonic_start_ns,
            events=events, idle_baseline_bytes=self.idle_baseline_bytes, mem_available=mem_after,
            swap_delta=swap_delta, outcome=outcome, denial_code=denial_code,
        )
        return row

    # -- one (command_class, cohort) group ---------------------------------

    def run_cohort(self, handle: RunnerHandle, command_class: str, cache_cohort: str) -> CohortResult:
        if cache_cohort == COHORT_WARM:
            prime_cache(self.trusted_object_source)

        # Untimed discarded setup iterations (design §4) -- never written
        # to the JSONL evidence file (they are not "samples").
        for _ in range(self.discarded_setup_iterations):
            grant = make_signed_grant(
                self.private_key, base_revision=self.head_oid, trusted_repo_id=self.trusted_repo_id,
                command_class=command_class,
            )
            send_grant_over_uds(handle.config.socket_path, grant)

        successful = 0
        attempted = 0
        max_attempts = max(self.n * 4, self.n + 20)  # bounded — never an infinite loop
        while successful < self.n and attempted < max_attempts:
            try:
                row = self._take_one_sample(handle, command_class, cache_cohort, attempted)
            except _CacheValidityError as exc:
                return CohortResult(
                    command_class=command_class, cache_cohort=cache_cohort, valid=False,
                    invalid_reason=(
                        f"cache residency check failed at attempt {attempted}: "
                        f"cohort={exc.cohort} residency_pct={exc.residency_pct:.2f}"
                    ),
                    successful_samples=successful, attempted_samples=attempted,
                )
            self.rows.append(row)
            attempted += 1
            if row["outcome"] == OUTCOME_GREEN:
                successful += 1

        valid = successful >= self.n
        reason = None if valid else f"only {successful}/{self.n} successful samples within {max_attempts} attempts"
        return CohortResult(
            command_class=command_class, cache_cohort=cache_cohort, valid=valid, invalid_reason=reason,
            successful_samples=successful, attempted_samples=attempted,
        )

    def run_all(self, command_classes=COMMAND_CLASSES, cache_cohorts=CACHE_COHORTS) -> "list[CohortResult]":
        config = self._base_config()
        with _InstrumentedRunner():
            handle = start_runner_server(config)
            try:
                for command_class in command_classes:
                    for cache_cohort in cache_cohorts:
                        result = self.run_cohort(handle, command_class, cache_cohort)
                        self.cohort_results.append(result)
            finally:
                handle.stop()
        return self.cohort_results

    def write_jsonl(self, path: str) -> "tuple[int, str]":
        with open(path, "w", encoding="utf-8") as fh:
            for row in self.rows:
                fh.write(json.dumps(row, sort_keys=True, default=str) + "\n")
        digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()
        return len(self.rows), digest


class _CacheValidityError(Exception):
    def __init__(self, cohort: str, residency_pct: float):
        super().__init__(f"cache cohort {cohort!r} failed validity check at {residency_pct:.2f}% resident")
        self.cohort = cohort
        self.residency_pct = residency_pct


# ---------------------------------------------------------------------------
# Verdict computation (design §7): PASS | FAIL(metric, measured, limit) |
# INVALID(cohort, reason). Budgets are HARD -- this function must never let
# an over-limit or invalid-cohort result collapse to PASS.
# ---------------------------------------------------------------------------


def zero_untyped_outcome_gate(rows: "list[dict]") -> "tuple[bool, list[str]]":
    """Design §4/§8-obligation-1: a nonzero count of unaccounted/untyped
    outcomes FAILS the gate. Returns `(ok, offending_row_summaries)`."""
    offenders = []
    for row in rows:
        outcome = row.get("outcome")
        denial_code = row.get("denial_code")
        if outcome not in ALLOWED_OUTCOMES:
            offenders.append(f"sample_index={row.get('sample_index')} unknown outcome={outcome!r}")
            continue
        if not _is_known_denial_code(denial_code):
            offenders.append(f"sample_index={row.get('sample_index')} unknown denial_code={denial_code!r}")
    return len(offenders) == 0, offenders


def _extract_metric_samples(rows: "list[dict]", metric: str) -> "list[float]":
    out: "list[float]" = []
    for row in rows:
        if row.get("outcome") != OUTCOME_GREEN:
            continue
        if metric == "clone_latency_p95_s":
            a, b = row.get("clone_done_ns"), row.get("monotonic_start_ns")
        elif metric == "bwrap_spawn_latency_p95_s":
            a, b = row.get("bwrap_started_ns"), row.get("clone_done_ns")
        else:
            continue
        if a is None or b is None:
            continue
        out.append((a - b) / 1e9)
    return out


def _extract_incremental_rss(rows: "list[dict]") -> "list[float]":
    out: "list[float]" = []
    for row in rows:
        peak = row.get("cgroup_peak_bytes")
        baseline = row.get("idle_baseline_bytes")
        if peak is None or baseline is None:
            continue
        out.append(float(peak - baseline))
    return out


def compute_verdict(
    cohort_results: "list[CohortResult]", rows: "list[dict]",
    revocation_result: "Optional[dict]" = None, budgets: dict = BUDGETS,
) -> dict:
    invalid = [c for c in cohort_results if not c.valid]
    if invalid:
        return {
            "status": VERDICT_INVALID,
            "invalid_cohorts": [
                {"command_class": c.command_class, "cache_cohort": c.cache_cohort, "reason": c.invalid_reason}
                for c in invalid
            ],
            "failures": [],
            "metrics_unavailable": [],
        }

    failures = []
    unavailable = []

    untyped_ok, offenders = zero_untyped_outcome_gate(rows)
    if not untyped_ok:
        failures.append({
            "metric": "untyped_outcome_count", "measured": len(offenders), "limit": BUDGET_UNTYPED_OUTCOME_COUNT,
            "detail": offenders[:10],
        })

    clone_samples = _extract_metric_samples(rows, "clone_latency_p95_s")
    clone_p95 = p95_nearest_rank(clone_samples)
    if clone_p95 is None:
        unavailable.append("clone_latency_p95_s")
    elif clone_p95 > BUDGET_CLONE_LATENCY_P95_S:
        failures.append({"metric": "clone_latency_p95_s", "measured": clone_p95, "limit": BUDGET_CLONE_LATENCY_P95_S})

    bwrap_samples = _extract_metric_samples(rows, "bwrap_spawn_latency_p95_s")
    bwrap_p95 = p95_nearest_rank(bwrap_samples)
    if bwrap_p95 is None:
        unavailable.append("bwrap_spawn_latency_p95_s")
    elif bwrap_p95 > BUDGET_BWRAP_SPAWN_LATENCY_P95_S:
        failures.append({
            "metric": "bwrap_spawn_latency_p95_s", "measured": bwrap_p95, "limit": BUDGET_BWRAP_SPAWN_LATENCY_P95_S,
        })

    rss_samples = _extract_incremental_rss(rows)
    if not rss_samples:
        unavailable.append("peak_incremental_rss_bytes")
    else:
        peak_rss = max(rss_samples)
        if peak_rss > BUDGET_PEAK_INCREMENTAL_RSS_BYTES:
            failures.append({
                "metric": "peak_incremental_rss_bytes", "measured": peak_rss,
                "limit": BUDGET_PEAK_INCREMENTAL_RSS_BYTES,
            })

    if revocation_result is not None:
        teardown_p95 = revocation_result.get("teardown_latency_p95_s")
        if teardown_p95 is None:
            unavailable.append("teardown_latency_p95_s")
        elif teardown_p95 > BUDGET_TEARDOWN_LATENCY_P95_S:
            failures.append({
                "metric": "teardown_latency_p95_s", "measured": teardown_p95, "limit": BUDGET_TEARDOWN_LATENCY_P95_S,
            })
        if not revocation_result.get("all_assertions_passed", False):
            failures.append({
                "metric": "revocation_under_load_assertions", "measured": revocation_result.get("failures", []),
                "limit": "all-pass",
            })
    else:
        unavailable.append("teardown_latency_p95_s")

    status = VERDICT_FAIL if failures else VERDICT_PASS
    return {
        "status": status,
        "invalid_cohorts": [],
        "failures": failures,
        "metrics_unavailable": unavailable,
    }


# ---------------------------------------------------------------------------
# Revocation-under-load (design §5).
# ---------------------------------------------------------------------------


def run_revocation_under_load(
    harness: PerfHarness, concurrency_cap: int = DEFAULT_CONCURRENCY, sleep_seconds: float = 5.0,
) -> dict:
    """Design §5: at the configured cap, with cells actively running, bump
    the authoritative epoch and measure epoch-bump -> tree-absent -> typed
    rollback receipt. Uses the SAME direct-`_supervise()` technique already
    proven by `test-execution-cell-runner.py`'s
    `test_epoch_bump_mid_run_kills_tree` (a real cgroup + a real
    long-running tracked process) for the concurrent-teardown timing half
    of the assertion, PLUS one full-pipeline `process_grant` run (mirroring
    `test_final_epoch_fence_flips_green_to_red`) for the "zero cells
    publish GREEN after the bump" half. Never mutates R1/R2/R3; the epoch
    is bumped via a harness-owned callable `epoch_source` (the SAME
    already-authorized `RunnerConfig.epoch_source` extension point R3's own
    test suite uses) -- not the shared repo file
    `config/capability-lease-epoch`."""
    if concurrency_cap < 1 or concurrency_cap > MAX_CONCURRENCY_BEFORE_REVIEW:
        raise ValueError(
            f"concurrency_cap={concurrency_cap} outside the reviewed range "
            f"[1, {MAX_CONCURRENCY_BEFORE_REVIEW}] (design §3) -- refusing to run"
        )

    result: dict = {
        "concurrency_cap": concurrency_cap, "teardown_latency_p95_s": None, "all_assertions_passed": False,
        "failures": [], "skipped": [],
    }

    cgroup_parent = harness.cgroup_parent
    if cgroup_parent is None:
        result["skipped"].append("R6-canary-deferred: no delegated cgroup v2 subtree on this host")
        return result

    class _EpochHolder:
        def __init__(self):
            self.value = 0

        def __call__(self):
            return self.value

    holder = _EpochHolder()
    revocation_epoch = 100

    # -- (a)/(c): concurrency_cap concurrent tracked cells, real cgroups --
    procs = []
    cgroup_paths = []
    verified_grants = []
    for _ in range(concurrency_cap):
        grant = make_signed_grant(
            harness.private_key, base_revision=harness.head_oid, trusted_repo_id=harness.trusted_repo_id,
            command_class=COMMAND_NOOP, revocation_epoch=revocation_epoch, timeout_s=30,
        )
        verified = eg.verify_grant(grant, harness.public_key_bytes, datetime.now(timezone.utc), 0, eg.ReplayReservationSet())
        if not isinstance(verified, eg.VerifiedGrant):
            result["failures"].append(f"revocation fixture grant failed to verify: {verified!r}")
            return result
        verified_grants.append(verified)
        cgroup_path = runner.create_cgroup(cgroup_parent, f"r4-revocation-{uuid.uuid4().hex[:12]}")
        if cgroup_path is None:
            result["failures"].append("could not create a tracked cgroup for the revocation-under-load fixture")
            return result
        cgroup_paths.append(cgroup_path)
        proc = subprocess.Popen(["sleep", str(sleep_seconds)], start_new_session=True)
        runner.add_pid_to_cgroup(cgroup_path, proc.pid)
        procs.append(proc)

    supervise_config = runner.RunnerConfig(
        socket_path="", client_uid=None, client_gid=None, public_key_bytes=harness.public_key_bytes,
        trusted_repo_mirrors={}, cell_state_root=harness.cell_state_root, cgroup_parent=cgroup_parent,
        python_bin=_PYTHON_BIN, bwrap_path=_BWRAP_PATH, poll_interval_s=0.1, heartbeat_deadline_s=1.0,
        sigterm_grace_s=0.5, kill_proof_budget_s=4.5, epoch_source=holder,
    )

    thread_results: "list[Optional[tuple]]" = [None] * concurrency_cap
    threads = []
    for i in range(concurrency_cap):
        def _run(idx=i):
            thread_results[idx] = runner._supervise(procs[idx], cgroup_paths[idx], verified_grants[idx], supervise_config)

        t = threading.Thread(target=_run)
        threads.append(t)
        t.start()

    time.sleep(0.4)  # a couple of 0.1s poll ticks pass at the valid epoch
    epoch_bump_ns = _now_ns()
    holder.value = revocation_epoch + 1  # bump past revocation_epoch -> next tick denies

    for t in threads:
        t.join(timeout=15)
    tree_absent_ns = _now_ns()

    teardown_seconds: "list[float]" = []
    for i, res in enumerate(thread_results):
        if res is None:
            result["failures"].append(f"cell {i}: supervise thread never returned within timeout")
            continue
        outcome, trigger, cgroup_kill_used, proven = res
        if outcome != "terminated":
            result["failures"].append(f"cell {i}: expected 'terminated', got {outcome!r}")
        if trigger != "epoch-bump":
            result["failures"].append(f"cell {i}: expected trigger 'epoch-bump', got {trigger!r} (untyped/unaccounted)")
        if not proven:
            result["failures"].append(f"cell {i}: tree not proven absent within budget (QUARANTINED-class)")
        teardown_seconds.append((tree_absent_ns - epoch_bump_ns) / 1e9)
        try:
            procs[i].wait(timeout=2)
        except Exception:
            pass

    result["teardown_latency_p95_s"] = p95_nearest_rank(teardown_seconds)
    if result["teardown_latency_p95_s"] is not None and result["teardown_latency_p95_s"] > REVOCATION_TEARDOWN_BUDGET_S:
        result["failures"].append(
            f"teardown p95 {result['teardown_latency_p95_s']:.3f}s exceeds {REVOCATION_TEARDOWN_BUDGET_S}s budget"
        )

    # -- (b): zero cells publish GREEN after the bump (full pipeline) -----
    config_full = harness._base_config(epoch_source=holder, max_concurrent_cells=concurrency_cap)
    with _InstrumentedRunner():
        full_grant = make_signed_grant(
            harness.private_key, base_revision=harness.head_oid, trusted_repo_id=harness.trusted_repo_id,
            command_class=COMMAND_NOOP, revocation_epoch=revocation_epoch,
        )
        decision = runner.process_grant(full_grant, config_full)
    if decision.decision == runner.DECISION_GREEN:
        result["failures"].append("a cell published GREEN using an already-stale (post-bump) revocation_epoch")
    if not _is_known_denial_code(decision.reason if decision.decision != runner.DECISION_GREEN else None):
        result["failures"].append(f"post-bump decision carried an unrecognized reason: {decision.reason!r}")

    # -- (d): runner stays responsive to new deny-closed requests ----------
    responsive_config = harness._base_config(env={"CAPABILITY_EXECUTION_CELLS": "0"})
    handle = start_runner_server(responsive_config)
    try:
        probe_grant = make_signed_grant(
            harness.private_key, base_revision=harness.head_oid, trusted_repo_id=harness.trusted_repo_id,
            command_class=COMMAND_NOOP,
        )
        response, transport_error = send_grant_over_uds(responsive_config.socket_path, probe_grant, timeout_s=5.0)
        if response is None or response.get("decision") != runner.DECISION_DENIED:
            result["failures"].append(
                f"runner not responsive/deny-closed after mass teardown: response={response!r} error={transport_error!r}"
            )
    finally:
        handle.stop()

    result["all_assertions_passed"] = len(result["failures"]) == 0
    return result


# ---------------------------------------------------------------------------
# Report assembly + main().
# ---------------------------------------------------------------------------


def build_report(harness: PerfHarness, jsonl_path: str, row_count: int, jsonl_digest: str, revocation_result: "Optional[dict]") -> dict:
    verdict = compute_verdict(harness.cohort_results, harness.rows, revocation_result)
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": harness.run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "host_fingerprint": harness.host_fp,
        "build_revision": harness.build_revision,
        "cgroup_available": harness.cgroup_parent is not None,
        "idle_baseline_bytes": harness.idle_baseline_bytes,
        "evidence": {"jsonl_path": jsonl_path, "jsonl_sha256": jsonl_digest, "row_count": row_count},
        "cohorts": [
            {
                "command_class": c.command_class, "cache_cohort": c.cache_cohort, "valid": c.valid,
                "invalid_reason": c.invalid_reason, "successful_samples": c.successful_samples,
                "attempted_samples": c.attempted_samples,
            }
            for c in harness.cohort_results
        ],
        "revocation_under_load": revocation_result,
        "verdict": verdict,
    }


def main(argv: "Optional[list[str]]" = None) -> int:
    parser = argparse.ArgumentParser(description="C3b R4 execution-cell performance-measurement harness")
    parser.add_argument("--n", type=int, default=DEFAULT_N, help="successful samples per cohort per command class")
    parser.add_argument("--fast", action="store_true", help="tiny-N self-test mode (not the real acceptance run)")
    parser.add_argument("--out", type=str, default=None, help="report JSON output path")
    parser.add_argument("--jsonl-out", type=str, default=None, help="evidence JSONL output path")
    parser.add_argument("--revocation-under-load", action="store_true", help="run the §5 revocation-under-load mode")
    parser.add_argument("--concurrency-cap", type=int, default=DEFAULT_CONCURRENCY)
    parser.add_argument(
        "--command-classes", type=str, default=",".join(COMMAND_CLASSES),
        help="comma-separated subset of noop,read-validate,single-file-write",
    )
    args = parser.parse_args(argv)

    n = 3 if args.fast else args.n
    command_classes = tuple(c.strip() for c in args.command_classes.split(",") if c.strip())

    harness = PerfHarness(n=n)
    try:
        harness.run_all(command_classes=command_classes)

        revocation_result = None
        if args.revocation_under_load or args.fast:
            revocation_result = run_revocation_under_load(harness, concurrency_cap=args.concurrency_cap)

        out_dir = tempfile.mkdtemp(prefix="c3b-r4-perf-out-") if args.jsonl_out is None else None
        jsonl_path = args.jsonl_out or os.path.join(out_dir, "evidence.jsonl")
        row_count, digest = harness.write_jsonl(jsonl_path)

        report = build_report(harness, jsonl_path, row_count, digest, revocation_result)
        report_json = json.dumps(report, indent=2, sort_keys=True, default=str)
        if args.out:
            Path(args.out).write_text(report_json + "\n", encoding="utf-8")
        print(report_json)

        return 0 if report["verdict"]["status"] == VERDICT_PASS else 1
    finally:
        cleanup_temp_roots()


if __name__ == "__main__":
    sys.exit(main())
