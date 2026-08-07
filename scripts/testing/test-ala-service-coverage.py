#!/usr/bin/env python3
"""ALA rev4 Service Coverage (slice 3): the asymmetric-lease-authority is default-OFF, governed,
and dashboard-visible. Offline cross-surface contract validation — no service, no network.
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main() -> int:
    fails = []

    def need(cond, msg):
        if not cond:
            fails.append(msg)

    # 1. env-contract: the flag exists and defaults to "0"
    import yaml
    ec = yaml.safe_load(open(os.path.join(ROOT, "config", "env-contract.yaml")))
    entries = ec.get("environment_variables") or ec.get("variables") or ec.get("env") or []
    if not entries:  # fall back to a flat scan of any list of dicts
        entries = [v for v in _iter_dicts(ec)]
    ala = next((e for e in entries if isinstance(e, dict) and e.get("canonical") == "CAPABILITY_ASYMMETRIC_LEASE"), None)
    need(ala is not None, "env-contract must document CAPABILITY_ASYMMETRIC_LEASE")
    need(ala is None or str(ala.get("default")) == "0", "CAPABILITY_ASYMMETRIC_LEASE must default to '0'")

    # 2. nix service ships enable=false by default
    nix = open(os.path.join(ROOT, "nix", "modules", "services", "lease-signing-authority.nix")).read()
    need("default = false;" in nix, "lease-signing-authority.nix must default enable=false")
    need("aq-lease-signing-authority" in nix and "AF_UNIX" in nix, "authority service must be confined (dedicated user, AF_UNIX only)")

    # 3. signer allowlist: present, public-only (inspect KEY ENTRY fields, not descriptive text),
    #    and has an active key
    sk = json.load(open(os.path.join(ROOT, "config", "aqos", "lease-signer-keys.json")))
    keys = sk.get("keys", []) if isinstance(sk, dict) else []
    need(any(isinstance(k, dict) and k.get("status") == "active" for k in keys), "signer allowlist must have >=1 active key")
    bad_fields = {"private", "secret", "seed", "signing_key", "private_key"}
    for k in keys:
        if isinstance(k, dict):
            need(not ({str(f).lower() for f in k} & bad_fields), "signer key entries must carry no private-material field")

    # 4. dashboard visibility: API endpoint exposes an 'ala' section; dashboard.js renders it
    api = open(os.path.join(ROOT, "dashboard", "backend", "api", "routes", "aistack.py")).read()
    need('result["ala"]' in api and "CAPABILITY_ASYMMETRIC_LEASE" in api, "/stats/capability-enforcement must expose ala state")
    dj = open(os.path.join(ROOT, "assets", "dashboard.js")).read()
    need("ALA Status" in dj and "d.ala" in dj, "dashboard.js must render the ALA card rows")

    # 5. the crypto + authority contract tests exist (coverage points at them)
    for t in ("test-asymmetric-lease-authority.py", "test-lease-signing-authority.py"):
        need(os.path.isfile(os.path.join(ROOT, "scripts", "testing", t)), f"missing coverage test {t}")

    if fails:
        print("FAIL: ALA service coverage")
        for f in fails:
            print("  - " + f)
        return 1
    print("PASS: ALA service coverage (default-OFF flag + confined service + public allowlist + dashboard-visible)")
    return 0


def _iter_dicts(obj):
    if isinstance(obj, dict):
        # a mapping of sections -> lists, or a single entry
        if obj.get("canonical"):
            yield obj
        for v in obj.values():
            yield from _iter_dicts(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _iter_dicts(v)


if __name__ == "__main__":
    raise SystemExit(main())
