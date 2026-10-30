"""Activation grant chain verifier (SSOT: .agents/plans/system-integrity-recovery/ACTIVATION-PIPELINE.md).

Pure verification: envelope canonicalisation, Ed25519 signature check, chain/head verification,
per-item grant/revoke state machine and the single predicate `activation_verified`. No signing keys,
no root paths and no writes live here; every path and key is a parameter (the store-installed
caller supplies them). Fail closed everywhere: any unreadable or inconsistent state means no item
is ACTIVATED.

On-disk layout read by `load_chain`:
  <log_dir>/<seq>.json   {"envelope": {...signed fields...}, "sig": "<hex>"}   seq 0 is the genesis
  <head_path>            {"seq": N, "hash": "<hex envelope hash of segment N>"}
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

ENVELOPE_VERSION = 1
DOMAIN = "nixos-dev-quick-deploy/activation/v1"
GENESIS_PREV = "0" * 64
OPS = {"genesis", "grant", "revoke", "wave-grant"}
_ITEM_FIELDS = ("plan", "item_id", "subject", "attestation_sha256", "system_closure", "evidence_baseline_sha256")
_COMMON = ("v", "domain", "op", "deployment_id", "approver", "ts", "request_id", "seq", "prev_hash")
_SEQ_FILE = re.compile(r"^(\d+)\.json$")
_MAX_BYTES = 1 << 20


def canonical(envelope: dict) -> bytes:
    return json.dumps(envelope, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def signing_input(envelope: dict) -> bytes:
    """domain || 0x00 || canonical JSON: a signature cannot be reused for any other message type."""
    return DOMAIN.encode("utf-8") + b"\x00" + canonical(envelope)


def envelope_hash(envelope: dict, sig_hex: str) -> str:
    return hashlib.sha256(signing_input(envelope) + bytes.fromhex(sig_hex)).hexdigest()


def item_key(plan: str, item_id: str, subject: str) -> tuple[str, str, str]:
    return (plan, item_id, subject)


def _is_hex(s, n: int) -> bool:
    return isinstance(s, str) and re.fullmatch(r"[0-9a-f]{%d}" % n, s) is not None


def _check_envelope(env: dict) -> str | None:
    """Structural check of the signed bytes; None when well-formed."""
    if not isinstance(env, dict) or env.get("v") != ENVELOPE_VERSION or env.get("domain") != DOMAIN:
        return "bad version/domain"
    op = env.get("op")
    if op not in OPS:
        return f"unknown op {op!r}"
    if type(env.get("seq")) is not int or env["seq"] < 0 or not _is_hex(env.get("prev_hash"), 64):
        return "bad seq/prev_hash"
    for f in ("deployment_id", "approver", "ts", "request_id"):
        if not isinstance(env.get(f), str) or not env[f]:
            return f"missing {f}"
    if op == "genesis":
        return None if env["seq"] == 0 else "genesis must be seq 0"
    if env["seq"] == 0:
        return "seq 0 must be genesis"
    if op in ("grant", "revoke"):
        needed = _ITEM_FIELDS if op == "grant" else ("plan", "item_id", "subject")
        for f in needed:
            if not isinstance(env.get(f), str) or not env[f]:
                return f"missing {f}"
        return None
    # wave-grant
    items = env.get("items")
    if not isinstance(env.get("wave_id"), str) or not isinstance(items, list) or not items:
        return "wave needs wave_id and items"
    seen_i, seen_s = set(), set()
    for t in items:
        if not isinstance(t, dict) or any(not isinstance(t.get(f), str) or not t[f] for f in _ITEM_FIELDS):
            return "bad wave tuple"
        if (t["plan"], t["item_id"]) in seen_i or t["subject"] in seen_s:
            return "duplicate wave entry"
        seen_i.add((t["plan"], t["item_id"]))
        seen_s.add(t["subject"])
    if items != sorted(items, key=lambda t: (t["plan"], t["item_id"], t["subject"])):
        return "wave items not sorted"
    return None


def verify_signature(env: dict, sig_hex: str, allowlist: list[str]) -> bool:
    """True when any allowlisted Ed25519 public key (hex, 32 bytes) verifies the domain-separated input."""
    try:  # lazy: a host without `cryptography` fails closed (nothing verifies) instead of crashing importers
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except ImportError:
        return False
    try:
        sig = bytes.fromhex(sig_hex)
    except (ValueError, TypeError):
        return False
    data = signing_input(env)
    for pk in allowlist:
        try:
            Ed25519PublicKey.from_public_bytes(bytes.fromhex(pk)).verify(sig, data)
            return True
        except (InvalidSignature, ValueError, TypeError):
            continue
    return False


@dataclass
class ItemState:
    state: str = "none"          # none | granted | revoked
    seq: int = -1
    attestation_sha256: str = ""
    system_closure: str = ""
    evidence_baseline_sha256: str = ""


@dataclass
class ChainState:
    ok: bool = False
    reason: str = "chain not loaded"
    blocked_all: bool = True     # True => no item may be ACTIVATED
    head_seq: int = -1
    deployment_id: str = ""
    items: dict = field(default_factory=dict)   # key tuple -> ItemState


def _fail(reason: str, deployment_id: str = "") -> ChainState:
    return ChainState(ok=False, reason=reason, blocked_all=True, deployment_id=deployment_id)


def _read_json(path: Path):
    st = path.lstat()
    if not path.is_file() or path.is_symlink() or st.st_size > _MAX_BYTES:
        raise ValueError("not a regular bounded file")
    return json.loads(path.read_text(encoding="utf-8"))


def apply_envelope(items: dict, env: dict) -> None:
    """Per-item state machine, folded in seq order. A revoke wins from any state; a wave never clears
    `revoked`; only a later individual grant does (the fold order makes 'later' = higher seq)."""
    op, seq = env["op"], env["seq"]
    if op == "genesis":
        return
    if op == "revoke":
        k = item_key(env["plan"], env["item_id"], env["subject"])
        st = items.setdefault(k, ItemState())
        st.state, st.seq = "revoked", seq
        return
    tuples = [env] if op == "grant" else env["items"]
    for t in tuples:
        k = item_key(t["plan"], t["item_id"], t["subject"])
        st = items.setdefault(k, ItemState())
        if op == "wave-grant" and st.state == "revoked":
            continue
        st.state, st.seq = "granted", seq
        st.attestation_sha256 = t["attestation_sha256"]
        st.system_closure = t["system_closure"]
        st.evidence_baseline_sha256 = t["evidence_baseline_sha256"]


def load_chain(log_dir, head_path, allowlist: list[str], deployment_id: str | None = None) -> ChainState:
    """Verify every segment from genesis to the head checkpoint and fold the item states.

    Fails closed (blocked_all) for: missing/unreadable/corrupt head, missing segment dir or segments,
    gaps/duplicates, bad signature, broken prev_hash, head hash mismatch, a head beyond the highest
    segment (truncated tail), and any segment beyond the head (unfinalized write, possibly a revoke)."""
    log_dir, head_path = Path(log_dir), Path(head_path)
    try:
        head = _read_json(head_path)
    except (OSError, ValueError):
        return _fail("head missing/unreadable/corrupt")
    if not isinstance(head, dict) or type(head.get("seq")) is not int or head["seq"] < 0 or not _is_hex(head.get("hash"), 64):
        return _fail("head malformed")
    try:
        names = [p.name for p in log_dir.iterdir()]
    except OSError:
        return _fail("segment directory missing/unreadable")
    seqs = []
    for n in names:
        m = _SEQ_FILE.match(n)
        if m:
            seqs.append(int(m.group(1)))
    seqs.sort()
    if not seqs:
        return _fail("no segments")
    if seqs != list(range(len(seqs))):
        return _fail("segment gap or duplicate")
    if seqs[-1] < head["seq"]:
        return _fail("head beyond highest segment (truncated tail)")
    items: dict = {}
    prev, dep = GENESIS_PREV, ""
    for seq in range(head["seq"] + 1):
        try:
            seg = _read_json(log_dir / f"{seq}.json")
        except (OSError, ValueError):
            return _fail(f"segment {seq} unreadable/corrupt", dep)
        env, sig = (seg.get("envelope"), seg.get("sig")) if isinstance(seg, dict) else (None, None)
        err = _check_envelope(env)
        if err or not isinstance(sig, str) or not _is_hex(sig, 128):
            return _fail(f"segment {seq} malformed: {err or 'bad sig'}", dep)
        if env["seq"] != seq or env["prev_hash"] != prev:
            return _fail(f"segment {seq} breaks chain", dep)
        if not verify_signature(env, sig, allowlist):
            return _fail(f"segment {seq} signature invalid", dep)
        if seq == 0:
            dep = env["deployment_id"]
            if deployment_id is not None and dep != deployment_id:
                return _fail("genesis deployment_id differs from this machine", dep)
        elif env["deployment_id"] != dep:
            return _fail(f"segment {seq} deployment_id mismatch", dep)
        apply_envelope(items, env)
        prev = envelope_hash(env, sig)
    if prev != head["hash"]:
        return _fail("head hash does not match segment", dep)
    if seqs[-1] > head["seq"]:
        return ChainState(ok=False, reason="segment beyond head (pending finalization): all ACTIVATED blocked",
                          blocked_all=True, head_seq=head["seq"], deployment_id=dep, items=items)
    return ChainState(ok=True, reason="ok", blocked_all=False, head_seq=head["seq"], deployment_id=dep, items=items)


def activation_status(item: dict, chain_state: ChainState, deployed_closure: str | None) -> str:
    """`item` = {plan, item_id, subject, attestation_sha256}. Returns one of: activated, none, revoked,
    grant-stale, chain-invalid, no-subject."""
    if chain_state is None or chain_state.blocked_all or not chain_state.ok:
        return "chain-invalid"
    if not all(isinstance(item.get(f), str) and item[f] for f in ("plan", "item_id", "subject")):
        return "no-subject"
    st = chain_state.items.get(item_key(item["plan"], item["item_id"], item["subject"]))
    if st is None or st.state == "none":
        return "none"
    if st.state == "revoked":
        return "revoked"
    if not deployed_closure or deployed_closure != st.system_closure:
        return "grant-stale"
    if item.get("attestation_sha256") != st.attestation_sha256:
        return "grant-stale"
    return "activated"


def activation_verified(item: dict, chain_state: ChainState, deployed_closure: str | None) -> bool:
    """The only predicate that may cause ACTIVATED. Slice 2 adds the evidence-copy baseline recompute."""
    return activation_status(item, chain_state, deployed_closure) == "activated"
