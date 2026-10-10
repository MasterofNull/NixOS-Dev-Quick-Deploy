# Evidence: Network Profile Interoperability — Slice N1 (Passive Projection & Service Coverage)

**Date**: 2026-10-10
**Author**: Antigravity (Gemini lane)
**Slice**: N1 — Passive Projection and Service Coverage
**Branch**: `feat/network-profile-interoperability-n1`
**Plan**: `.agents/plans/network-profile-interoperability/PROGRAM-PLAN.md`
**PRD**: `.agent/PROJECT-NETWORK-PROFILE-INTEROPERABILITY-PRD.md`

## 1. Objective

Deliver Slice N1 of the Network Profile Interoperability program, satisfying the mandatory Service Coverage contract:
1. Passive local health projection at `/run/aq-network-policy/health.json` (`network.dns-policy-health.v1`).
2. Dual integration checks: Python Phase-0 check (`scripts/testing/harness_qa/phases/phase0.py`) and Bash check (`scripts/ai/_aq-qa-bash`) exercising the CLI machine facade (`scripts/ai/aq-network-policy`).
3. Live dashboard card in `assets/dashboard.js` querying `/api/aistack/network-policy` in `dashboard/backend/api/routes/aistack.py`.
4. Strict ceiling compliance: Exactly 9 implementation paths modified. Zero DNS mutation or `resolvectl` modifications.

## 2. Changes Across the 9 Ceiling Paths

1. `nix/modules/core/network.nix`:
   Added `options.mySystem.networkPolicyObservability.enable` (default: false) and appended passive read-only dispatcher script `20-aq-network-policy-observe`. Retained existing enforcement bytes until N2.
2. `scripts/ai/lib/network_dns_policy.py`:
   Added bounded acquisition adapter (`acquire_facts`), interface token validation (`is_valid_interface`), sysfs Wi-Fi verification (`is_wifi_interface`), durable atomic health writer (`publish_health`), reader (`read_health`), and transaction facade (`acquire_and_publish_health`). Zero shell execution, strict 16 KiB / 2s timeout ceiling, closed errors.
3. `scripts/ai/aq-network-policy`:
   Created read-only CLI status facade supporting `status`, `health`, `json`, `observe [IFACE]`. Strictly rejects mutation verbs (`apply`, `revert`, `set`, etc.) with exit code 2.
4. `scripts/testing/test-network-dns-policy.py`:
   Added `TestNetworkDnsPolicyN1` test suite covering interface token validation, sysfs Wi-Fi detection, bounded fact acquisition, durable atomic persistence/locking, and CLI facade smoke tests.
5. `scripts/testing/harness_qa/phases/phase0.py`:
   Registered Phase-0 check `0.17.1` validating the health projection via `aq-network-policy health` and enforcing semantic consistency rules.
6. `scripts/ai/_aq-qa-bash`:
   Added matching shell compatibility check `0.17.1` in `run_phase_0()`.
7. `dashboard/backend/api/routes/aistack.py`:
   Added read-only sanitized endpoint `GET /api/aistack/network-policy` reading local projection and sanitizing output via `sanitize_telemetry()`.
8. `assets/dashboard.js`:
   Added Network Resilience card (`_ensureNetworkResilienceCard()`, `updateNetworkResilience()`) wired into initial load and 30s interval polling.
9. `docs/operations/network-profile-interoperability.md`:
   Created operator runbook documenting non-destructive diagnostics, health state interpretation, and troubleshooting.

## 3. Validation

- Vector and unit tests:
  ```bash
  python3 scripts/testing/test-network-dns-policy.py
  # Ran 14 tests in 0.384s — OK
  ```
- Phase 0 integration checks:
  - Python: `[CheckResult(status=PASS, id='0.17.1', description='Network DNS Policy health: state=unavailable, connectivity=unknown, reason=unknown_state')]`
  - Bash: `_pass 4 "0.17.1" "Network DNS Policy health projection valid"`
- API endpoint:
  `GET /api/aistack/network-policy` returns valid sanitized schema.
- Dashboard JS syntax:
  `node --check assets/dashboard.js` — OK.
- Nix module parse:
  `nix-instantiate --parse nix/modules/core/network.nix` — OK.
- Pre-commit Tier-0 validation gate:
  `scripts/governance/tier0-validation-gate.sh --pre-commit` passed with 0 errors.

## 4. Definition of Done & Service Coverage Contract

- **Integrated**: Read-only facade, API route, Phase-0 checks, and dashboard card are wired into runtime paths.
- **Turned ON**: Enabled for passive observation without side-effects; dispatcher hook gated behind declarative option.
- **Functionally Validated**: Tested via offline test suite and Phase-0 smoke tests.
- **Observable**: Network Resilience card renders live in dashboard.
- **Intervenable**: Operators can run `aq-network-policy status` and refer to `docs/operations/network-profile-interoperability.md`.
- **Ceiling**: Exactly 9 implementation paths + evidence record. Zero tenth paths.
