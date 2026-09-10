#!/usr/bin/env python3
"""Flow tests for the guided install (P1) — hardware-honest AI + non-destructive."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
GUIDED = REPO / "scripts" / "ai" / "aqos-guided-install"
AIFIT = REPO / "scripts" / "ai" / "lib" / "ai_fit.py"
CATALOG = REPO / "config" / "aqos-ai-fit-policy-catalog-v1.json"
GIB = 1024**3
sys.path.insert(0, str(REPO / "scripts" / "ai" / "lib"))
import aqos_install_resolver as resolver  # noqa: E402

SCHEMA = json.loads((REPO / "config/schemas/aqos-install-plan-v1.schema.json").read_text())
MODULE_BYTES = (REPO / "config/aqos-module-catalog-v1.json").read_bytes()
MODULES = resolver.parse_json_strict(MODULE_BYTES)
AI_BYTES = (REPO / "config/aqos-ai-fit-policy-catalog-v1.json").read_bytes()
FIELDSET_BYTES = (REPO / "config/aqos-mysystem-fieldset-v1.json").read_bytes()


def _source_identity() -> dict:
    return {"oid_algorithm": "sha1", "git_commit": "a" * 40, "git_tree": "b" * 40,
            "clean_worktree": True, "flake_lock_sha256": "c" * 64,
            "nix_system": "x86_64-linux", "flake_installable": "path:/repo#nixosConfigurations.h",
            "host_target": "h"}


def _resolver_hw() -> dict:
    return {"schema_version": 2, "cpu": {"architecture": "x86_64", "model": "t", "cores": 8, "threads": 16},
            "ram": {"total_bytes": 32 * GIB},
            "gpu": {"outcome": "detected", "devices": [], "present": False}}


def load(path, name):
    # SourceFileLoader handles the extensionless `aqos-guided-install` script too.
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    loader.exec_module(m)
    return m


def _cat():
    fit = load(AIFIT, "ai_fit")
    return fit.load_catalog(CATALOG)  # (catalog, digest)


def _hw(ram_bytes, *, present=False, outcome="none", mem=None, vendor=None, vram=None):
    primary = {"memory_type": mem, "vendor_id": vendor, "vram_total_bytes": vram} if present else None
    return {"schema_version": 2, "ram": {"total_bytes": ram_bytes},
            "gpu": {"present": present, "outcome": outcome, "devices": [{}] if present else [], "primary": primary}}


def test_ai_off_by_default_when_not_advised():
    g = load(GUIDED, "guided")
    cat, dig = _cat()
    hw = _hw(2 * GIB)  # too small -> not_advised
    r = g.run(hw, cat, dig, host_target="h", ai_choice=None)
    assert r["ai"]["verdict"] == "not_advised"
    assert r["request"]["answers"]["include_local_ai"] is False


def test_ai_on_by_default_when_recommended():
    g = load(GUIDED, "guided")
    cat, dig = _cat()
    hw = _hw(64 * GIB, present=True, outcome="detected", mem="dedicated", vendor="0x10de", vram=24 * GIB)
    r = g.run(hw, cat, dig, host_target="h", ai_choice=None)
    assert r["ai"]["verdict"] == "recommended"
    assert r["request"]["answers"]["include_local_ai"] is True
    assert r["ai"]["recommended_model"]


def test_explicit_yes_on_weak_hw_warns_but_honors():
    g = load(GUIDED, "guided")
    cat, dig = _cat()
    hw = _hw(2 * GIB)  # not_advised
    r = g.run(hw, cat, dig, host_target="h", ai_choice="yes")
    assert r["request"]["answers"]["include_local_ai"] is True
    assert r["ai"]["warning"] and "NOT ADVISED" in r["ai"]["warning"]


def test_request_is_resolver_guided_ADAPTER_INPUT_shape():
    """The guided front-end emits the guided-ADAPTER INPUT (answers), not a request_plan."""
    g = load(GUIDED, "guided")
    req = g.build_guided_request("myhost", True, roles=["role.gaming"])
    assert set(req) == {"answers", "host_target"}, req  # NOT a pre-built request_plan
    assert req["answers"]["golden_profile"] == "aqos-workstation"
    assert req["answers"]["include_local_ai"] is True
    assert req["answers"]["roles"] == ["role.gaming"]
    assert req["host_target"] == "myhost"


def test_guided_output_round_trips_through_the_guided_adapter_no_data_loss():
    """REGRESSION (silent-data-loss bug): the REAL guided output, fed through the SAME
    `--adapter guided` the tool prints, must PRESERVE the operator's choices. Before the
    fix the script emitted a request_plan while telling the operator to use --adapter
    guided, so normalize_adapter('guided', ...) read a missing `answers` key and produced
    selection={} — every choice silently dropped. This asserts the real seam, not a fixture."""
    g = load(GUIDED, "guided")
    req = g.build_guided_request("myhost", True, roles=["role.gaming"])
    normalized = resolver.normalize_adapter("guided", req)  # exactly what the CLI tells you to run
    sel = normalized["selection"]
    assert sel.get("include_local_ai") is True, normalized   # would be dropped by the bug
    assert sel.get("roles") == ["role.gaming"], normalized    # would be dropped by the bug
    assert sel.get("golden_profile") == "aqos-workstation", normalized
    assert normalized["host_target"] == "myhost"


def test_flow_is_non_destructive():
    """run() touches no disk; the CLI writes ONLY the --out request file, nothing else."""
    g = load(GUIDED, "guided")
    cat, dig = _cat()
    hw = _hw(32 * GIB, present=True, outcome="detected", mem="shared", vendor="0x1002")
    with tempfile.TemporaryDirectory() as d:
        before = set(Path(d).iterdir())
        g.run(hw, cat, dig, host_target="h", ai_choice="no")  # pure core -> no writes at all
        assert set(Path(d).iterdir()) == before
        # CLI with --out writes exactly one file (the request), and nothing else in the dir
        out = Path(d) / "req.json"
        hwf = Path(d) / "hw.json"; hwf.write_text(json.dumps(hw))
        rc = g.main(["--hardware", str(hwf), "--out", str(out), "--host-target", "h", "--ai", "no", "--json"])
        assert rc == 0 and out.exists()
        assert set(p.name for p in Path(d).iterdir()) == {"req.json", "hw.json"}
        assert json.loads(out.read_text())["answers"]["include_local_ai"] is False


def test_s1b_system_setup_answers_are_collected_and_emitted():
    """s1b: hostname/username/disk-encryption/password-hash flow into `answers`,
    omitted entirely when not supplied (backward compatible with every pre-s1b caller)."""
    g = load(GUIDED, "guided")
    bare = g.build_guided_request("h", True, roles=[])
    assert set(bare["answers"]) == {"golden_profile", "roles", "include_local_ai"}, bare

    pwd_hash = g.hash_password("correct horse battery staple")
    req = g.build_guided_request(
        "h", True, roles=[],
        host_name="myhost", primary_user="alice",
        disk=g.disk_selection_for(True),
        primary_user_password_hash=pwd_hash,
    )
    ans = req["answers"]
    assert ans["hostName"] == "myhost"
    assert ans["primaryUser"] == "alice"
    assert ans["disk"] == {"layout": "gpt-luks-ext4", "luks": {"enable": True}}
    assert ans["primaryUserPasswordHash"] == pwd_hash


def test_encrypt_disk_choice_maps_to_layout():
    g = load(GUIDED, "guided")
    assert g.disk_selection_for(True) == {"layout": "gpt-luks-ext4", "luks": {"enable": True}}
    assert g.disk_selection_for(False) == {"layout": "gpt-efi-ext4", "luks": {"enable": False}}


def test_s1b_answers_normalize_into_the_resolved_selection_for_both_choices():
    """The exact seam named in the task: build_guided_request -> answers ->
    normalize_adapter('guided') must set hostName/primaryUser/disk.layout/luks.enable
    correctly for BOTH the encrypted and the plain choice."""
    g = load(GUIDED, "guided")
    for encrypt_disk, expected_layout, expected_luks in (
        (True, "gpt-luks-ext4", True),
        (False, "gpt-efi-ext4", False),
    ):
        pwd_hash = g.hash_password("s1b-test-password")
        req = g.build_guided_request(
            "myhost", False, roles=[],
            host_name="aqos-box", primary_user="hyperd",
            disk=g.disk_selection_for(encrypt_disk),
            primary_user_password_hash=pwd_hash,
        )
        normalized = resolver.normalize_adapter("guided", req)
        sel = normalized["selection"]
        assert sel["hostName"] == "aqos-box", sel
        assert sel["primaryUser"] == "hyperd", sel
        assert sel["disk"]["layout"] == expected_layout, sel
        assert sel["disk"]["luks"]["enable"] is expected_luks, sel
        assert sel["primaryUserPasswordHash"] == pwd_hash, sel


def test_full_resolve_plan_sets_hostname_user_disk_and_hash_for_both_choices():
    """End-to-end through the TRUSTED resolver (not just normalize_adapter): the REAL
    guided producer's answers must survive resolve_plan()'s schema validation and land
    in the resolved_plan_lock's selection, for both the encrypted and plain choice."""
    g = load(GUIDED, "guided")
    for encrypt_disk, expected_layout, expected_luks in (
        (True, "gpt-luks-ext4", True),
        (False, "gpt-efi-ext4", False),
    ):
        pwd_hash = g.hash_password("full-resolve-test")
        req = g.build_guided_request(
            "h", False, roles=[],
            host_name="aqos-box", primary_user="hyperd",
            disk=g.disk_selection_for(encrypt_disk),
            primary_user_password_hash=pwd_hash,
        )
        normalized = resolver.normalize_adapter("guided", req)
        lock = resolver.resolve_plan(normalized, _resolver_hw(), MODULES, MODULE_BYTES,
                                     AI_BYTES, FIELDSET_BYTES, SCHEMA, _source_identity())
        sel = lock["selection"]
        assert sel["hostName"] == "aqos-box", sel
        assert sel["primaryUser"] == "hyperd", sel
        assert sel["disk"] == {"layout": expected_layout, "luks": {"enable": expected_luks}}, sel
        assert sel["primaryUserPasswordHash"] == pwd_hash, sel


def test_layout_luks_mismatch_is_rejected_fail_closed():
    """Exercise the resolver's semantic cross-field guard directly: a layout/luks
    disagreement must fail closed with a stable reason code (defense-in-depth beyond
    the guided front-end, which never produces a mismatched pair itself)."""
    g = load(GUIDED, "guided")
    req = g.build_guided_request(
        "h", False, roles=[], host_name="h", primary_user="u",
        disk={"layout": "gpt-luks-ext4", "luks": {"enable": False}},  # mismatched on purpose
        primary_user_password_hash=g.hash_password("x"),
    )
    normalized = resolver.normalize_adapter("guided", req)
    try:
        resolver.resolve_plan(normalized, _resolver_hw(), MODULES, MODULE_BYTES,
                              AI_BYTES, FIELDSET_BYTES, SCHEMA, _source_identity())
        raise AssertionError("mismatched disk layout/luks.enable was accepted")
    except resolver.ResolverError as exc:
        assert exc.reason == "disk_luks_layout_mismatch", exc.reason


def test_password_never_appears_in_plaintext_in_the_emitted_request():
    """HARD SECURITY regression: the emitted request JSON (what --out writes to disk /
    what --json prints) must contain only the HASH, never the plaintext password."""
    g = load(GUIDED, "guided")
    plaintext = "S3cr3t-Not-For-The-Store!"
    pwd_hash = g.hash_password(plaintext)
    assert pwd_hash != plaintext
    assert plaintext not in pwd_hash
    req = g.build_guided_request(
        "myhost", False, roles=[],
        host_name="h", primary_user="u", disk=g.disk_selection_for(True),
        primary_user_password_hash=pwd_hash,
    )
    wire = json.dumps(req, sort_keys=True)
    assert plaintext not in wire, "plaintext password leaked into the emitted request JSON"
    assert req["answers"]["primaryUserPasswordHash"] == pwd_hash
    # And through the resolver adapter too — the artifact the operator actually persists.
    normalized = resolver.normalize_adapter("guided", req)
    normalized_wire = json.dumps(normalized, sort_keys=True)
    assert plaintext not in normalized_wire, "plaintext password leaked into the normalized selection"


def main() -> int:
    test_ai_off_by_default_when_not_advised()
    test_ai_on_by_default_when_recommended()
    test_explicit_yes_on_weak_hw_warns_but_honors()
    test_request_is_resolver_guided_ADAPTER_INPUT_shape()
    test_guided_output_round_trips_through_the_guided_adapter_no_data_loss()
    test_flow_is_non_destructive()
    test_s1b_system_setup_answers_are_collected_and_emitted()
    test_encrypt_disk_choice_maps_to_layout()
    test_s1b_answers_normalize_into_the_resolved_selection_for_both_choices()
    test_full_resolve_plan_sets_hostname_user_disk_and_hash_for_both_choices()
    test_layout_luks_mismatch_is_rejected_fail_closed()
    test_password_never_appears_in_plaintext_in_the_emitted_request()
    print("test-aqos-guided-install: ok 12/12")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
