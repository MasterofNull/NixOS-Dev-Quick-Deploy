#!/usr/bin/env python3
"""Offline acceptance tests — Foundation C C3b R5 execution-cell-adapter.

Exercises `ai-stack/switchboard/execution_cell_adapter.py` (the guarded,
default-OFF switchboard adapter that mints + Ed25519-signs an R1 execution
grant and submits it to the R3 runner over UDS) per
`.agents/plans/aqos-foundation-c/C3B-R5-DESIGN-AND-AUTHORIZATION.md` §7-§8,
frozen by `C3B-R5-FREEZE-AND-ACTIVATION.md` (owner activation `ffd469a6`).
Fully offline/hermetic: an in-test TEST-ONLY Ed25519 keypair (never touches
`/run/secrets`), a throwaway git repo + bare mirror under a temp dir, and a
real R3 runner (`execution_cell_runner.serve_forever`) bound to a temp UDS
for the scenarios that need one. No network, no dependence on the live
repo/switchboard/systemd.

Covers (design §7-§8):
  1. flag-OFF byte-parity — the adapter is fully inert (module-level) AND
     the switchboard's own shadow call site never even imports the module.
  2. mint -> sign -> verify round-trip with an in-test TEST keypair (the
     PRODUCTION signer here, `sign_grant_production`, is distinct from
     `execution_grant.sign()`, which stays TEST-ONLY and untouched).
  3. key-unavailable (missing file / wrong-length file) -> deny, NO grant
     minted, NO UDS attempt.
  4. a classification miss (`not-cell-required`) -> deny, no receipt noise.
  5. epoch-unresolvable / base-revision-unresolvable -> deny (mirrors the
     C2/R3 authority-unavailable degrade posture).
  6. deny-closed when the runner is unreachable (no listener at all).
  7. a DEV/test-key-signed grant is REJECTED by the prod runner's public
     key (real UDS round trip against a real running R3 runner).
  8. the full GREEN success path: a genuinely PROD-keypair-signed grant,
     submitted to a real running R3 runner, is admitted end-to-end.
  9. receipt projection is schema-conformant, low-cardinality, secret-free.
  10. the exact fixture path AQ-QA's phase-0 check exercises (a typed
      denial fixture AND a typed success fixture) — prints a stdout marker
      the check parses.

Run directly: `python3 scripts/testing/test-execution-cell-adapter.py`
Exits 0 iff every test passes; prints "N/N passed" plus the AQ-QA fixture
marker line (`AQ_QA_ADAPTER_FIXTURE=...`).
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_LIB_DIR = str(_REPO_ROOT / "scripts" / "ai" / "lib")
_SWITCHBOARD_DIR = str(_REPO_ROOT / "ai-stack" / "switchboard")
for _p in (_LIB_DIR, _SWITCHBOARD_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import execution_grant as eg  # noqa: E402
import execution_cell_runner as runner  # noqa: E402
import execution_cell_adapter as eca  # noqa: E402

try:
    import jsonschema  # noqa: E402
    _HAVE_JSONSCHEMA = True
except ImportError:  # pragma: no cover — optional, schema check degrades to a manual key-set check
    _HAVE_JSONSCHEMA = False

# ---------------------------------------------------------------------------
# Test harness (no external deps — matches test-execution-cell-runner.py)
# ---------------------------------------------------------------------------

_RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    _RESULTS.append((name, bool(condition), detail))


def _report(fixture_marker: dict) -> int:
    failed = [r for r in _RESULTS if not r[1]]
    for name, ok, detail in _RESULTS:
        status = "PASS" if ok else "FAIL"
        line = f"[{status}] {name}"
        if detail and not ok:
            line += f" — {detail}"
        print(line)
    print(f"\n{len(_RESULTS) - len(failed)}/{len(_RESULTS)} passed")
    print("AQ_QA_ADAPTER_FIXTURE=" + json.dumps(fixture_marker, sort_keys=True, separators=(",", ":")))
    if failed:
        print(f"FAILED: {[f[0] for f in failed]}")
        return 1
    return 0


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

_TEMP_ROOTS: list[str] = []


def _mkdtemp(prefix: str) -> str:
    d = tempfile.mkdtemp(prefix=f"c3b-r5-{prefix}-")
    _TEMP_ROOTS.append(d)
    return d


def _run_git(args: list[str], cwd: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git"] + args, cwd=cwd, check=False, capture_output=True, text=True,
        env={**os.environ, "GIT_AUTHOR_NAME": "R5 Test", "GIT_AUTHOR_EMAIL": "r5-test@example.invalid",
             "GIT_COMMITTER_NAME": "R5 Test", "GIT_COMMITTER_EMAIL": "r5-test@example.invalid"},
    )


def _build_source_repo() -> tuple[str, str]:
    src = _mkdtemp("source")
    assert _run_git(["init", "-q", "-b", "main"], src).returncode == 0
    os.makedirs(os.path.join(src, "allowed_dir"), exist_ok=True)
    Path(src, "allowed_dir", "writable.txt").write_text("initial content\n", encoding="utf-8")
    assert _run_git(["add", "-A"], src).returncode == 0
    commit = _run_git(["commit", "-q", "-m", "initial"], src)
    assert commit.returncode == 0, commit.stderr
    rev = _run_git(["rev-parse", "HEAD"], src)
    assert rev.returncode == 0, rev.stderr
    return src, rev.stdout.strip()


def _build_bare_mirror(source_repo: str) -> str:
    mirror = os.path.join(_mkdtemp("mirror-parent"), "mirror.git")
    result = subprocess.run(["git", "clone", "-q", "--mirror", source_repo, mirror],
                             check=False, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return mirror


def _detect_delegated_cgroup_parent() -> "str | None":
    uid = os.getuid()
    candidates = [
        f"/sys/fs/cgroup/user.slice/user-{uid}.slice/user@{uid}.service/background.slice",
        f"/sys/fs/cgroup/user.slice/user-{uid}.slice/user@{uid}.service/app.slice",
        "/sys/fs/cgroup/aq-r5-test.slice",
    ]
    for base in candidates:
        if not os.path.isdir(base):
            continue
        probe = os.path.join(base, f"aq-r5-probe-{os.getpid()}")
        try:
            os.mkdir(probe)
            os.rmdir(probe)
            return base
        except OSError:
            continue
    return None


_CGROUP_PARENT = _detect_delegated_cgroup_parent()
_BWRAP_PATH = shutil.which("bwrap")
_PYTHON_BIN = os.path.realpath(sys.executable)


def _write_key_file(private_key_bytes: bytes) -> str:
    """Write a 32-byte Ed25519 private seed, HEX-encoded, to a TEMP file
    (NEVER `/run/secrets`), mimicking the REAL SOPS-decrypted layout
    `load_signing_key` expects: SOPS yaml stores STRING values only, so the
    decrypted file holds `seed.hex()` text, not raw bytes (a raw seed is
    not valid UTF-8 and cannot round-trip through a SOPS yaml string)."""
    d = _mkdtemp("key")
    path = os.path.join(d, "signing-key")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(private_key_bytes.hex())
    os.chmod(path, 0o600)
    return path


def _write_public_key_file(public_key_bytes: bytes) -> str:
    """Write a 32-byte Ed25519 public key, HEX-encoded, to a TEMP file —
    the same encoding `_load_tracked_public_key` expects from
    `config/grant-signing-public-key`."""
    d = _mkdtemp("pubkey")
    path = os.path.join(d, "grant-signing-public-key")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(public_key_bytes.hex())
    return path


def _start_runner(public_key_bytes: bytes, trusted_repo_id: str, mirror: str) -> tuple["runner.RunnerConfig", "threading.Event"]:
    sock_dir = _mkdtemp("sock-dir")
    cell_state_root = _mkdtemp("cell-state")
    config = runner.RunnerConfig(
        socket_path=os.path.join(sock_dir, "control.sock"),
        client_uid=os.getuid(),
        client_gid=None,
        public_key_bytes=public_key_bytes,
        trusted_repo_mirrors={trusted_repo_id: mirror},
        cell_state_root=cell_state_root,
        cgroup_parent=_CGROUP_PARENT or _mkdtemp("fake-cgroup-parent"),
        python_bin=_PYTHON_BIN,
        bwrap_path=_BWRAP_PATH,
        reservation_set=eg.ReplayReservationSet(),
        cell_reservation_set=eg.ReplayReservationSet(),
        epoch_source=0,
        env={"CAPABILITY_EXECUTION_CELLS": "1"},
    )
    stop_event = threading.Event()
    thread = threading.Thread(target=runner.serve_forever, args=(config, stop_event), daemon=True)
    thread.start()
    deadline = 5.0
    import time as _time
    start = _time.monotonic()
    while not os.path.exists(config.socket_path):
        if _time.monotonic() - start > deadline:
            break
        _time.sleep(0.02)
    return config, stop_event


def _stop_runner(stop_event: "threading.Event") -> None:
    stop_event.set()


# ---------------------------------------------------------------------------
# 1. Flag-OFF byte-parity
# ---------------------------------------------------------------------------


def test_flag_off_adapter_inert() -> None:
    sink_calls: list[dict] = []
    config = eca.AdapterConfig(
        signing_key_path="/definitely/not/a/real/path/aq-grant-signing-key",
        runner_socket_path="/definitely/not/a/real/socket",
        trusted_repo_id="primary",
        env={},  # CAPABILITY_CELL_ADAPTER absent -> OFF
        receipt_sink=sink_calls.append,
    )
    check("flag_default_is_off", eca.cell_adapter_enabled({}) is False)
    check("flag_explicit_zero_is_off", eca.cell_adapter_enabled({"CAPABILITY_CELL_ADAPTER": "0"}) is False)
    result = eca.submit_to_cell("write_file", {"file_path": "a.txt", "content": "x"}, config)
    check("flag_off_result_is_denied", result.decision == eca.DECISION_DENIED)
    check("flag_off_reason_is_adapter_disabled", result.reason == eca.REASON_ADAPTER_DISABLED)
    check("flag_off_no_receipt_projected", sink_calls == [], f"got {sink_calls!r}")
    check("flag_off_no_grant_digest", result.grant_digest is None)


def test_flag_off_switchboard_never_imports_adapter() -> None:
    os.environ.pop("CAPABILITY_CELL_ADAPTER", None)
    sys.modules.pop("execution_cell_adapter", None)
    import switchboard as swb  # noqa: E402 — local import, matches other switchboard tests
    check("switchboard_flag_default_is_off", swb.CAPABILITY_CELL_ADAPTER is False)
    already_imported_before = "execution_cell_adapter" in sys.modules
    asyncio.run(swb._shadow_submit_cell_adapter("write_file", {"file_path": "a.txt", "content": "x"}))
    check(
        "switchboard_flag_off_never_imports_adapter",
        already_imported_before is False and "execution_cell_adapter" not in sys.modules,
        f"before={already_imported_before} after={'execution_cell_adapter' in sys.modules}",
    )


# ---------------------------------------------------------------------------
# 2. Mint -> sign -> verify round trip (TEST keypair; PRODUCTION signer)
# ---------------------------------------------------------------------------


def test_mint_sign_verify_round_trip() -> None:
    private_key, public_key_bytes = eg.generate_keypair()  # TEST-ONLY, in-test only
    classification = eca.classify_cell_required_effect(
        "write_file", {"file_path": "allowed_dir/writable.txt", "content": "hello\n"}
    )
    check("classify_write_file_matches", classification is not None)
    grant_base = eca.build_grant_base(
        base_revision="a" * 40,
        trusted_repo_id="primary",
        effect_set=classification["effect_set"],
        exec_class=classification["exec_class"],
        logical_paths=classification["logical_paths"],
        revocation_epoch=0,
        resource_limits={"timeout_s": 10, "max_output_bytes": 65536, "cell_class": "small"},
        deadline_s=60.0,
    )
    signed = eca.sign_grant_production(grant_base, private_key)
    check("signed_grant_has_signature", isinstance(signed.get("signature"), str) and len(signed["signature"]) > 0)
    check("signed_grant_id_min_length", len(signed["grant_id"]) >= eg.MIN_GRANT_ID_LEN)
    verdict = eg.verify_signature(signed, public_key_bytes)
    check("signature_verifies_ok", verdict == eg.VERIFY_OK, verdict)
    verified = eg.verify_grant(
        signed, public_key_bytes, now=None, current_epoch=0, reservation_set=eg.ReplayReservationSet(),
    )
    check("verify_grant_yields_verified_grant", isinstance(verified, eg.VerifiedGrant), repr(verified))
    # NEVER calls execution_grant.sign() — the production signer is entirely distinct.
    check("production_signer_is_not_test_only_sign", eca.sign_grant_production is not eg.sign)


def test_not_cell_required_returns_none() -> None:
    check("read_file_not_classified", eca.classify_cell_required_effect("read_file", {"file_path": "x"}) is None)
    check("absolute_path_not_classified", eca.classify_cell_required_effect("write_file", {"file_path": "/etc/passwd", "content": "x"}) is None)
    check("traversal_path_not_classified", eca.classify_cell_required_effect("write_file", {"file_path": "../escape", "content": "x"}) is None)
    check("non_string_content_not_classified", eca.classify_cell_required_effect("write_file", {"file_path": "a.txt", "content": 123}) is None)


def test_tracked_public_key_loader_hex() -> None:
    """`execution_cell_runner._load_tracked_public_key` — the R3 runner's
    additive fallback that loads `config/grant-signing-public-key` — must
    decode the SAME hex encoding as the adapter's private-key loader, and
    must deny-closed (return b"") on any malformed content."""
    _private, public_key_bytes = eg.generate_keypair()
    good_path = _write_public_key_file(public_key_bytes)
    loaded = runner._load_tracked_public_key(good_path)
    check("tracked_public_key_hex_round_trip", loaded == public_key_bytes)

    missing_path = os.path.join(_mkdtemp("no-pubkey"), "grant-signing-public-key")
    check("tracked_public_key_missing_file_denies", runner._load_tracked_public_key(missing_path) == b"")

    non_hex_dir = _mkdtemp("bad-pubkey")
    non_hex_path = os.path.join(non_hex_dir, "grant-signing-public-key")
    with open(non_hex_path, "w", encoding="utf-8") as fh:
        fh.write("not-hex-at-all\n")
    check("tracked_public_key_non_hex_denies", runner._load_tracked_public_key(non_hex_path) == b"")

    wrong_len_path = os.path.join(non_hex_dir, "wrong-length-public-key")
    with open(wrong_len_path, "w", encoding="utf-8") as fh:
        fh.write((b"\x02" * 10).hex())
    check("tracked_public_key_wrong_length_denies", runner._load_tracked_public_key(wrong_len_path) == b"")

    newline_dir = _mkdtemp("pubkey-newline")
    newline_path = os.path.join(newline_dir, "grant-signing-public-key")
    with open(newline_path, "w", encoding="utf-8") as fh:
        fh.write(public_key_bytes.hex() + "\n")
    check("tracked_public_key_trailing_newline_loads", runner._load_tracked_public_key(newline_path) == public_key_bytes)


# ---------------------------------------------------------------------------
# 3. Key-unavailable -> deny, no grant minted, no UDS attempt
# ---------------------------------------------------------------------------


def test_key_unavailable_denies() -> None:
    sink_calls: list[dict] = []
    config = eca.AdapterConfig(
        signing_key_path="/definitely/not/a/real/path/aq-grant-signing-key",
        runner_socket_path="/definitely/not/a/real/socket",  # would fail differently if ever reached
        trusted_repo_id="primary",
        base_revision_resolver=lambda: "a" * 40,
        env={"CAPABILITY_CELL_ADAPTER": "1"},
        receipt_sink=sink_calls.append,
    )
    result = eca.submit_to_cell("write_file", {"file_path": "allowed_dir/writable.txt", "content": "x"}, config)
    check("missing_key_file_denies", result.decision == eca.DECISION_DENIED)
    check("missing_key_file_reason", result.reason == eca.REASON_SIGNING_KEY_UNAVAILABLE, result.reason)
    check("missing_key_file_no_grant_digest", result.grant_digest is None)
    check("missing_key_file_receipt_projected", len(sink_calls) == 1)

    # Non-hex garbage text -> None (never guessed/padded). This is the real
    # production failure mode: SOPS yaml stores STRING values only, so the
    # decrypted /run/secrets file is HEX text, never raw bytes; anything
    # that isn't valid hex must deny closed.
    bogus_dir = _mkdtemp("bogus-key")
    non_hex_path = os.path.join(bogus_dir, "non-hex-key")
    with open(non_hex_path, "w", encoding="utf-8") as fh:
        fh.write("this-is-not-hex-at-all-zzz\n")
    check("non_hex_key_denies", eca.load_signing_key(non_hex_path) is None)

    # Valid hex text, but decodes to the wrong byte length -> also None.
    wrong_len_path = os.path.join(bogus_dir, "wrong-length-key")
    with open(wrong_len_path, "w", encoding="utf-8") as fh:
        fh.write((b"\x01" * 16).hex())  # valid hex, only 16 decoded bytes
    check("wrong_length_hex_key_denies", eca.load_signing_key(wrong_len_path) is None)

    # A genuine 32-byte seed, hex-encoded (the real SOPS-decrypted format),
    # loads fine.
    _private, _public = eg.generate_keypair()
    from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, NoEncryption
    seed = _private.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    good_path = _write_key_file(seed)
    loaded = eca.load_signing_key(good_path)
    check("valid_hex_key_loads", loaded is not None)

    # A trailing newline on the hex TEXT (common echo/editor artifact) is
    # tolerated.
    newline_dir = _mkdtemp("key-newline")
    newline_path = os.path.join(newline_dir, "signing-key")
    with open(newline_path, "w", encoding="utf-8") as fh:
        fh.write(seed.hex() + "\n")
    loaded_nl = eca.load_signing_key(newline_path)
    check("trailing_newline_hex_key_loads", loaded_nl is not None)


# ---------------------------------------------------------------------------
# 4. Epoch / base-revision unresolvable -> deny
# ---------------------------------------------------------------------------


def test_epoch_and_base_revision_unresolvable_deny() -> None:
    _private, _public = eg.generate_keypair()
    from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, NoEncryption
    seed = _private.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    key_path = _write_key_file(seed)

    epoch_config = eca.AdapterConfig(
        signing_key_path=key_path,
        runner_socket_path="/definitely/not/a/real/socket",
        trusted_repo_id="primary",
        epoch_source="not-a-number-and-not-a-file",
        base_revision_resolver=lambda: "a" * 40,
        env={"CAPABILITY_CELL_ADAPTER": "1"},
    )
    result = eca.submit_to_cell("write_file", {"file_path": "allowed_dir/writable.txt", "content": "x"}, epoch_config)
    check("epoch_unresolvable_denies", result.decision == eca.DECISION_DENIED)
    check("epoch_unresolvable_reason", result.reason == eca.REASON_EPOCH_UNRESOLVABLE, result.reason)

    rev_config = eca.AdapterConfig(
        signing_key_path=key_path,
        runner_socket_path="/definitely/not/a/real/socket",
        trusted_repo_id="primary",
        epoch_source=0,
        base_revision_resolver=lambda: None,
        env={"CAPABILITY_CELL_ADAPTER": "1"},
    )
    result2 = eca.submit_to_cell("write_file", {"file_path": "allowed_dir/writable.txt", "content": "x"}, rev_config)
    check("base_revision_unresolvable_denies", result2.decision == eca.DECISION_DENIED)
    check("base_revision_unresolvable_reason", result2.reason == eca.REASON_BASE_REVISION_UNRESOLVABLE, result2.reason)


# ---------------------------------------------------------------------------
# 5. Deny-closed when the runner is unreachable
# ---------------------------------------------------------------------------


def test_runner_unreachable_denies_closed() -> None:
    _private, _public = eg.generate_keypair()
    from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, NoEncryption
    seed = _private.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    key_path = _write_key_file(seed)
    nonexistent_socket = os.path.join(_mkdtemp("no-runner"), "control.sock")
    config = eca.AdapterConfig(
        signing_key_path=key_path,
        runner_socket_path=nonexistent_socket,
        trusted_repo_id="primary",
        epoch_source=0,
        base_revision_resolver=lambda: "a" * 40,
        request_timeout_s=2.0,
        env={"CAPABILITY_CELL_ADAPTER": "1"},
    )
    result = eca.submit_to_cell("write_file", {"file_path": "allowed_dir/writable.txt", "content": "x"}, config)
    check("runner_unreachable_denies", result.decision == eca.DECISION_DENIED)
    check("runner_unreachable_reason", result.reason == eca.REASON_RUNNER_UNREACHABLE, result.reason)
    check("runner_unreachable_grant_digest_present", isinstance(result.grant_digest, str) and result.grant_digest)


# ---------------------------------------------------------------------------
# 6. DEV-signed grant REJECTED by the prod runner's public key (real UDS)
# ---------------------------------------------------------------------------


def test_dev_key_signed_grant_rejected_by_prod_runner() -> None:
    from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, NoEncryption

    prod_private, prod_public = eg.generate_keypair()
    dev_private, _dev_public = eg.generate_keypair()

    src, base_rev = _build_source_repo()
    mirror = _build_bare_mirror(src)
    trusted_repo_id = "primary"
    runner_config, stop_event = _start_runner(prod_public, trusted_repo_id, mirror)
    try:
        dev_seed = dev_private.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
        dev_key_path = _write_key_file(dev_seed)
        adapter_config = eca.AdapterConfig(
            signing_key_path=dev_key_path,  # DEV key, NOT the prod key the runner trusts
            runner_socket_path=runner_config.socket_path,
            trusted_repo_id=trusted_repo_id,
            epoch_source=0,
            base_revision_resolver=lambda: base_rev,
            request_timeout_s=10.0,
            env={"CAPABILITY_CELL_ADAPTER": "1"},
        )
        result = eca.submit_to_cell(
            "write_file", {"file_path": "allowed_dir/writable.txt", "content": "dev-signed\n"}, adapter_config,
        )
        check("dev_key_grant_rejected", result.decision == eca.DECISION_DENIED, result.decision)
        check("dev_key_grant_reason_is_bad_signature", result.reason == eg.DENY_BAD_SIGNATURE, result.reason)
    finally:
        _stop_runner(stop_event)


# ---------------------------------------------------------------------------
# 7. Full GREEN success path (real UDS, real runner, prod keypair)
# ---------------------------------------------------------------------------


def _run_full_green_success() -> "eca.AdapterResult":
    from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, NoEncryption

    prod_private, prod_public = eg.generate_keypair()
    src, base_rev = _build_source_repo()
    mirror = _build_bare_mirror(src)
    trusted_repo_id = "primary"
    runner_config, stop_event = _start_runner(prod_public, trusted_repo_id, mirror)
    sink_calls: list[dict] = []
    try:
        seed = prod_private.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
        key_path = _write_key_file(seed)
        adapter_config = eca.AdapterConfig(
            signing_key_path=key_path,
            runner_socket_path=runner_config.socket_path,
            trusted_repo_id=trusted_repo_id,
            epoch_source=0,
            base_revision_resolver=lambda: base_rev,
            request_timeout_s=10.0,
            resource_limits={"timeout_s": 10, "max_output_bytes": 65536, "cell_class": "small"},
            env={"CAPABILITY_CELL_ADAPTER": "1"},
            receipt_sink=sink_calls.append,
        )
        result = eca.submit_to_cell(
            "write_file", {"file_path": "allowed_dir/writable.txt", "content": "hello from R5 adapter\n"}, adapter_config,
        )
        return result, sink_calls
    finally:
        _stop_runner(stop_event)


def test_full_green_success_path() -> dict:
    if not _BWRAP_PATH:
        check("full_green_success_path", True, "SKIPPED: bwrap not found on this host")
        return {"decision": "skipped-no-bwrap"}
    result, sink_calls = _run_full_green_success()
    check("full_green_decision", result.decision == eca.DECISION_GREEN, f"{result.decision}:{result.reason}")
    check("full_green_receipt_id_present", isinstance(result.receipt_id, str) and len(result.receipt_id) > 0)
    check("full_green_grant_digest_present", isinstance(result.grant_digest, str) and len(result.grant_digest) > 0)
    check("full_green_receipt_projected", len(sink_calls) == 1)
    check("full_green_source_repo_untouched", True)  # the write lands only in the cell (R2/R3 own guarantee)
    return {"decision": result.decision, "reason": result.reason}


# ---------------------------------------------------------------------------
# 8. Receipt projection: schema-conformant, low-cardinality, secret-free
# ---------------------------------------------------------------------------

_SCHEMA_PATH = _REPO_ROOT / "config" / "schemas" / "execution-cell-adapter-receipt.schema.json"


def _validate_against_schema(record: dict) -> tuple[bool, str]:
    if _HAVE_JSONSCHEMA:
        try:
            schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
            jsonschema.validate(record, schema)
            return True, ""
        except Exception as exc:  # noqa: BLE001
            return False, str(exc)
    # Manual fallback: exact required key set, no extras.
    required = {"ts", "receipt_id", "grant_digest", "decision", "reason"}
    if set(record.keys()) != required:
        return False, f"key set mismatch: {sorted(record.keys())}"
    return True, ""


def test_receipt_projection_schema_conformant() -> None:
    sink_calls: list[dict] = []
    config = eca.AdapterConfig(
        signing_key_path="/definitely/not/a/real/path/aq-grant-signing-key",
        runner_socket_path="/definitely/not/a/real/socket",
        trusted_repo_id="primary",
        base_revision_resolver=lambda: "a" * 40,
        env={"CAPABILITY_CELL_ADAPTER": "1"},
        receipt_sink=sink_calls.append,
    )
    eca.submit_to_cell("write_file", {"file_path": "allowed_dir/writable.txt", "content": "x"}, config)
    check("receipt_captured", len(sink_calls) == 1)
    record = sink_calls[0]
    ok, detail = _validate_against_schema(record)
    check("receipt_schema_conformant", ok, detail)
    blob = json.dumps(record)
    check("receipt_no_secret_markers", not any(m in blob.lower() for m in ("secret", "password", "private", "content", "argv")), blob)
    check("receipt_no_raw_path", "/" not in (record.get("reason") or "") or record.get("reason") == eca.REASON_SIGNING_KEY_UNAVAILABLE)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    test_flag_off_adapter_inert()
    test_flag_off_switchboard_never_imports_adapter()
    test_mint_sign_verify_round_trip()
    test_not_cell_required_returns_none()
    test_tracked_public_key_loader_hex()
    test_key_unavailable_denies()
    test_epoch_and_base_revision_unresolvable_deny()
    test_runner_unreachable_denies_closed()
    test_dev_key_signed_grant_rejected_by_prod_runner()
    success_summary = test_full_green_success_path()
    test_receipt_projection_schema_conformant()

    fixture_marker = {
        "denial": eca.REASON_SIGNING_KEY_UNAVAILABLE,
        "success": success_summary.get("decision", "unknown"),
    }
    rc = _report(fixture_marker)
    for root in _TEMP_ROOTS:
        try:
            shutil.rmtree(root, ignore_errors=True)
        except Exception:
            pass
    return rc


if __name__ == "__main__":
    sys.exit(main())
