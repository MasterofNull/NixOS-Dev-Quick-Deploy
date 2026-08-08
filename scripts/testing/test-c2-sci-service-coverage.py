#!/usr/bin/env python3
"""C2-SCI (Q-C6-1) Service Coverage: the scheduler-context issuer is default-OFF, governed, and
dashboard-visible. Offline cross-surface contract validation — no service, no network. Mirrors
test-ala-service-coverage.py; inspects field/structure, not descriptive prose.
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _iter_dicts(obj):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from _iter_dicts(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _iter_dicts(v)


def main() -> int:
    fails = []

    def need(cond, msg):
        if not cond:
            fails.append(msg)

    # 1. env-contract: the flag exists and defaults to "0"
    import yaml
    ec = yaml.safe_load(open(os.path.join(ROOT, "config", "env-contract.yaml")))
    entries = ec.get("environment_variables") or ec.get("variables") or ec.get("env") or []
    if not entries:
        entries = list(_iter_dicts(ec))
    sci = next((e for e in entries if isinstance(e, dict) and e.get("canonical") == "CAPABILITY_SCHEDULER_CONTEXT_ISSUER"), None)
    need(sci is not None, "env-contract must document CAPABILITY_SCHEDULER_CONTEXT_ISSUER")
    need(sci is None or str(sci.get("default")) == "0", "CAPABILITY_SCHEDULER_CONTEXT_ISSUER must default to '0'")

    # 2. nix service ships enable=false by default + is confined
    nix = open(os.path.join(ROOT, "nix", "modules", "services", "c2-scheduler-context-issuer.nix")).read()
    need("default = false;" in nix, "c2-scheduler-context-issuer.nix must default enable=false")
    need("aq-c2-scheduler-context-issuer" in nix, "service must use its dedicated principal")
    need("AF_UNIX" in nix, "service must be AF_UNIX-only (no network)")
    need("NoNewPrivileges" in nix and 'ProtectSystem = "strict"' in nix, "service must be hardened")
    need("aq-c2-scheduler-context-clients" in nix, "service must wire the shared client-access group (the ALA lesson)")

    # 3. signer allowlist: present, has an active key, PUBLIC-ONLY (no private-key field on any entry),
    #    and a DISTINCT key family from the lease-signer allowlist
    sk = json.load(open(os.path.join(ROOT, "config", "aqos", "c6-scheduler-signer-keys.json")))
    keys = sk.get("keys", []) if isinstance(sk, dict) else []
    need(any(isinstance(k, dict) and k.get("status") == "active" for k in keys), "c6 signer allowlist must have >=1 active key")
    need(all(isinstance(k, dict) and "ed25519_public_key" in k and not any("private" in kk.lower() for kk in k) for k in keys),
         "c6 signer allowlist entries must be public-only (no private-key field)")
    try:
        ls = json.load(open(os.path.join(ROOT, "config", "aqos", "lease-signer-keys.json")))
        lease_ids = {k.get("key_id") for k in ls.get("keys", []) if isinstance(k, dict)}
        c2_ids = {k.get("key_id") for k in keys if isinstance(k, dict)}
        need(lease_ids.isdisjoint(c2_ids), "c6 scheduler-signer key family must be DISTINCT from the lease-signer family")
    except FileNotFoundError:
        pass

    # 4. durable single-use ledger exists (atomic O_EXCL primitive)
    issuer = open(os.path.join(ROOT, "scripts", "ai", "lib", "scheduler_context_issuer.py")).read()
    need("DurableSingleUseLedger" in issuer, "issuer must ship a DurableSingleUseLedger")
    need("O_EXCL" in issuer, "the durable ledger must use an atomic O_EXCL test-and-set")

    # 5. gate + dispatch are FLAG-GATED (env-gated, not always-on)
    gate = open(os.path.join(ROOT, "ai-stack", "switchboard", "capability_lease_gate.py")).read()
    need("CAPABILITY_SCHEDULER_CONTEXT_ISSUER" in gate, "gate must reference the flag")
    need("_scheduler_context_issuer_enabled" in gate, "gate must gate the outbound call behind an enabled() predicate")
    disp = open(os.path.join(ROOT, "scripts", "ai", "lib", "dispatch.py")).read()
    need("verify_ingress_scheduler_context" in disp, "dispatch must ship the authenticated ingress verifier")

    # 6. dashboard API surfaces the C2-SCI section
    api = open(os.path.join(ROOT, "dashboard", "backend", "api", "routes", "aistack.py")).read()
    need('result["c2_scheduler_context_issuer"]' in api, "aistack.py /stats/capability-enforcement must expose c2_scheduler_context_issuer")
    need('"ledger_durable"' in api and '"context_issuer"' in api, "the c2_scheduler_context_issuer section must report issuer + ledger_durable")

    # 7. dashboard JS renders the C2-SCI rows
    js = open(os.path.join(ROOT, "assets", "dashboard.js")).read()
    need("c2_scheduler_context_issuer" in js, "dashboard.js must read the c2_scheduler_context_issuer section")
    need("C2-SCI" in js, "dashboard.js must render C2-SCI rows")

    # 8. the crypto/service tests exist
    for t in ("test-scheduler-context-issuer.py", "test-scheduler-context-ledger.py", "test-c2-gate-dispatch-wiring.py"):
        need(os.path.isfile(os.path.join(ROOT, "scripts", "testing", t)), f"coverage test {t} must exist")

    # 9. focused-ci registry registers this coverage check
    reg = json.load(open(os.path.join(ROOT, "config", "validation-check-registry.json")))
    ids = {c.get("id") for c in _iter_dicts(reg) if isinstance(c, dict) and c.get("id")}
    need("c2-sci-service-coverage" in ids, "validation-check-registry.json must register c2-sci-service-coverage")

    if fails:
        for f in fails:
            print(f"FAIL: {f}")
        print(f"\n{len(fails)} coverage assertion(s) failed")
        return 1
    print("PASS: C2-SCI service coverage (default-OFF flag + confined service + public allowlist + durable ledger + flag-gated gate/dispatch + dashboard-visible)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
