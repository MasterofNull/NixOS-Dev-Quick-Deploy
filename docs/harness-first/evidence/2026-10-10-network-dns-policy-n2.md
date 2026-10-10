# Evidence: Network Profile Interoperability — Slice N2 (Bounded Autonomous Safe-Fail Override & Watchdog Operations)

**Date**: 2026-10-10
**Author**: Antigravity (Gemini lane)
**Slice**: N2 — Bounded Autonomous Safe-Fail Override & Watchdog Operations
**Branch**: `feat/network-profile-interoperability-n2`
**Plan**: `.agents/plans/network-profile-interoperability/PROGRAM-PLAN.md`
**PRD**: `.agent/PROJECT-NETWORK-PROFILE-INTEROPERABILITY-PRD.md`

## 1. Objective

Deliver Slice N2 of the Network Profile Interoperability program:
1. Implement the bounded safe-fail resolver override transaction engine with durable lease receipts (`network.dns-policy-receipt.v1`).
2. Maintain strict fail-safe behavior: default mode is `legacy` preserving existing systemd-resolved dispatcher behavior byte-for-byte; `policy` mode is selectable via declarative NixOS configuration.
3. Provide autonomous watchdog service and timer (`aq-network-policy-watchdog`) running every 10s with jitter, rolling back expired leases or orphan overrides cross-boot.
4. Provide emergency manual and automated revert unit (`aq-network-policy-emergency-revert`).
5. Provide root-only, activation-gated trust map replacement interface (`aq-network-policy trust replace`) with schema validation and backup `.bak` file generation.
6. Enforce strict lock ordering: `effect-operation -> mapping -> receipt -> health`.
7. Zero raw identifier leaks: UUIDs, SSIDs, MACs, IPs, and domain names are never written to health telemetry or logs.
8. Strict ceiling compliance: Exactly 6 implementation paths + evidence record.

## 2. Changes Across the 6 Ceiling Paths

1. `config/network-dns-policy.schema.json`:
   Added closed Draft 2020-12 schemas for `policyTrust` (`network.dns-policy-trust.v1`) and `policyReceipt` (`network.dns-policy-receipt.v1`); added both to the root schema's `oneOf`.
2. `scripts/ai/lib/network_dns_policy.py`:
   Added trust and receipt validators (`validate_trust`, `validate_receipt`), `TrustReplaceResult` enum, atomic trust map replacement with backup creation (`replace_trust_map`), atomic receipt writer and reader (`publish_receipt`, `read_receipt`), transaction execution with exclusive effect lock (`execute_policy_transaction`), periodic watchdog and boot recovery (`run_watchdog_or_recovery`), and emergency revert (`run_emergency_revert`).
3. `scripts/ai/aq-network-policy`:
   Added subcommands for `trust replace` (root-only, blocked before N3 activation unless `--n3-canary`), `watchdog` (periodic check), `emergency-revert` (immediate Wi-Fi interface reset), and `execute` (dispatcher hook).
4. `nix/modules/core/network.nix`:
   Added `mySystem.networkPolicyObservability.mode` (`legacy` default, `policy` selectable), private root directory `/run/aq-network-policy-private/` (mode 0700) and `/etc/aq-network-policy/` (mode 0700) in `systemd.tmpfiles.rules`, watchdog service and timer units (10s interval, 1s jitter, 15s deadline), emergency revert unit, and mode branching in dispatcher scripts.
5. `scripts/testing/test-network-dns-policy.py`:
   Appended `TestNetworkDnsPolicyN2` test suite covering: trust and receipt schema validation and rejection of extra keys/invalid types, `replace_trust_map` privilege gating, atomicity, backup `.bak` creation and invalid candidate rejection, `publish_receipt` and `read_receipt` roundtrip, `execute_policy_transaction` permit apply, downgrade revert, mutation rollback, legacy mode preservation, watchdog lease expiry and cross-boot recovery, emergency revert, and CLI trust replacement gating.
6. `docs/operations/network-profile-interoperability.md`:
   Updated operator runbook documenting N2 operational modes (`legacy` vs `policy`), watchdog service lifecycle, emergency revert commands and systemd unit, and trust map management.

## 3. Validation

- Offline Test Suite:
  ```bash
  python3 scripts/testing/test-network-dns-policy.py
  # Ran 27 tests in 1.089s — OK
  ```
- Forbidden Imports Check:
  Re-asserted that forbidden modules (`subprocess`, `socket`, `requests`, `urllib`, `dbus`, `NetworkManager`) are NEVER imported by `scripts/ai/lib/network_dns_policy.py`.
- Nix Evaluation:
  ```bash
  nix-instantiate --parse nix/modules/core/network.nix
  ```
- Python Compilation:
  ```bash
  python3 -m py_compile scripts/ai/lib/network_dns_policy.py scripts/ai/aq-network-policy scripts/testing/test-network-dns-policy.py
  ```
- Pre-commit Tier-0 Validation Gate:
  ```bash
  scripts/governance/tier0-validation-gate.sh --pre-commit
  # 55/55 passed
  ```

## 4. Definition of Done & Activation Invariants

- **Integrated**: Watchdog systemd units, dispatcher branching, and CLI commands wired into system definitions.
- **Turned ON**: Deployed safely with default `mode = "legacy"`; policy mode selectable without disruption.
- **Functionally Validated**: Verified end-to-end via 27 vector and mock-execution unit tests.
- **Observable**: Health projection state reflects `preserving`, `overriding`, `reverted`, or `degraded`.
- **Intervenable**: Operators can run `sudo aq-network-policy emergency-revert` or start `aq-network-policy-emergency-revert.service`.
- **Ceiling**: Exactly 6 implementation paths + evidence record. Zero seventh paths.
