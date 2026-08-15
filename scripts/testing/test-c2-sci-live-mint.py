#!/usr/bin/env python3
"""C2-SCI live mint smoke — the real ALA→C2 mint round-trip against the RUNNING services.

Why this exists: the C2-SCI activation validation surfaced two runtime blockers that the fixture-based
unit tests could never catch because they inject the epoch + fabricate keys:
  - the 3d45e03c epoch-starvation regression (ALA/C2 hard-require the C6 epoch authority UDS; if it is not
    running, nothing mints), and
  - a signer-key provisioning mismatch (the active out-of-tree SOPS private key not pairing the allowlist
    public key).
Both only show up when you mint a REAL lease through the REAL services and verify against the REAL
allowlist. This smoke does exactly that, so that class of regression fails loudly instead of silently.

Behaviour (fail-closed only on a REAL defect, never on "not enabled"):
  - If the issuer/ALA/epoch sockets are absent (C2-SCI not activated) -> SKIP (exit 0).
  - If reachable but the caller lacks client-group membership (EACCES) -> SKIP with a hint (exit 0).
  - If the round-trip runs: assert mint ok + verify-vs-allowlist ok + wrong-key denies -> PASS/FAIL.

Run as a user in `aq-lease-signing-clients` + `aq-c2-scheduler-context-clients` (the owner/primaryUser), or:
  sg aq-c2-scheduler-context-clients -c 'python3 scripts/testing/test-c2-sci-live-mint.py'
Intended for manual post-activation validation and post-deploy convergence; not a fixture unit test.
"""
from __future__ import annotations
import json, os, sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, "scripts/ai/lib"))
sys.path.insert(0, os.path.join(REPO, "ai-stack/switchboard"))

ALA_SOCK = "/run/aq-lease-signing-authority/control.sock"
C2_SOCK = "/run/aq-c2-scheduler-context-issuer/control.sock"
EPOCH_SOCK = "/run/aq-revocation-epoch-authority/control.sock"
ALLOWLIST = os.path.join(REPO, "config/aqos/c6-scheduler-signer-keys.json")


def _skip(msg: str) -> int:
    print(f"SKIP: c2-sci-live-mint — {msg}")
    return 0


def _fail(msg: str) -> int:
    print(f"FAIL: c2-sci-live-mint — {msg}")
    return 1


def main() -> int:
    for sock, name in ((ALA_SOCK, "ALA"), (C2_SOCK, "C2 issuer"), (EPOCH_SOCK, "epoch authority")):
        if not os.path.exists(sock):
            return _skip(f"{name} socket absent ({sock}) — C2-SCI/chain not activated")
    try:
        import scheduler_context_transport as sct
        import scheduler_context_issuer as sci
    except Exception as exc:  # pragma: no cover
        return _skip(f"transport/issuer import unavailable: {exc}")

    def uw(r):
        return r.get("frame", r) if isinstance(r, dict) else r

    # 1) mint a REAL ALA lease (proves epoch resolves + the ALA signer works)
    try:
        ala = uw(sct.send_request(ALA_SOCK, {}))
    except PermissionError:
        return _skip("EACCES on ALA socket — run as a member of aq-lease-signing-clients")
    except Exception as exc:
        return _fail(f"ALA mint request failed: {exc}")
    if not isinstance(ala, dict) or not ala.get("leases"):
        reason = ala.get("error") or ala.get("reason") if isinstance(ala, dict) else ala
        return _fail(f"ALA did not mint a lease (reason={reason!r}) — epoch-starvation or ALA fault")
    tool, lease = next(iter(ala["leases"].items()))
    if lease.get("sig_scheme") != "ed25519":
        return _fail(f"ALA lease sig_scheme={lease.get('sig_scheme')!r}, expected ed25519")

    # 2) C2 issuer mints a signed context from that real lease
    try:
        c2 = uw(sct.send_request(C2_SOCK, {
            "lease": lease,
            "correlation": {"task_id": "c2-sci-live-mint-smoke", "principal": "smoke", "dispatch_mode": "agent"},
        }))
    except PermissionError:
        return _skip("EACCES on C2 socket — run as a member of aq-c2-scheduler-context-clients")
    except Exception as exc:
        return _fail(f"C2 mint request failed: {exc}")
    if not c2.get("ok") or not c2.get("context"):
        return _fail(f"C2 did not mint a context (ok={c2.get('ok')} reason={c2.get('reason')!r})")
    ctx = c2["context"]

    # 3) verify vs the REAL allowlist public key; a wrong key MUST deny
    keys_json = json.load(open(ALLOWLIST))
    good = sci.verify_scheduler_context(ctx, keys_json)
    wrong = {"schema_version": "1", "revision": 1,
             "keys": [{"key_id": keys_json["keys"][0]["key_id"], "ed25519_public_key": "00" * 32, "status": "active"}]}
    bad = sci.verify_scheduler_context(ctx, wrong)
    if not getattr(good, "ok", False):
        return _fail("context did NOT verify against the allowlist public key — signer/allowlist key mismatch")
    if getattr(bad, "ok", True):
        return _fail("context verified against a WRONG key — verification is not key-bound (critical)")

    print("PASS: c2-sci-live-mint — real ALA lease -> signed context -> verifies vs allowlist, wrong-key denies")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
