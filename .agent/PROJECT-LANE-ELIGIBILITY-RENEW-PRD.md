# PRD: Q5 Lane-Eligibility Registry Renewal & Hermetic Router Testing

## Context & Root Cause
Under Q5 / Rule 18 (model-neutral factory), `config/lane-eligibility-registry.json` establishes earned and expiring role eligibility for all model lanes (`codex`, `opus`, `sonnet`, `gemini`, `antigravity`, `local`) with a 45-day TTL.
The initial ratification expired on `2026-09-06T00:00:00Z`.
Because today is `2026-10-12`, all lane grants in the production registry have expired. This resulted in:
1. `aq-role-route` returning `no-eligible-lane` for every role (including `binding-acceptance`, `orchestrator`, `architect`, `implementer`, `reviewer`, `rsi`).
2. Unit tests in `scripts/testing/test-agent-agnostic-router.py` failing 7 assertion checks because `_reset_route_module` depended on unmocked live registry state instead of a hermetic test fixture.

## Objectives
1. **Production Registry Renewal**:
   - Renew all 27 active lane-role grants in `config/lane-eligibility-registry.json` using `scripts/ai/aq-lane-eligibility promote` for 45 days (from `2026-10-12` through `2026-11-26`).
   - Preserve all governance constraints:
     - Hard ineligibility: `antigravity.ineligible.implementer` (Rule 17 / external IDE agent boundary).
     - Capability notes: `opus` (bounded implementer), `local` (bounded single-edit, NOT multi-site), `gemini` (orchestrator and reviewer for RSI repair slices).
2. **Hermetic Router Test Isolation**:
   - In `scripts/testing/test-agent-agnostic-router.py`, update `_reset_route_module` to inject a hermetic test registry fixture via `os.environ[route_mod.LANE_ELIGIBILITY_REGISTRY_ENV]` with unexpired grants.
   - Ensure the test suite never breaks due to wall-clock time expiration.
3. **Validation & Verification**:
   - `test-agent-agnostic-router.py`: 100% PASS (all claim CAS, TOCTOU race, and role-route tests).
   - Live CLI verification: `aq-role-route binding-acceptance --subject test --json` cleanly resolves an eligible agent.
   - Pass all 56 Tier-0 gates.
4. **Issue Backlog Reconciliation**:
   - Log `lane-eligibility-registry-silent-expiration` in `.agent/memory/issues-backlog.md` and mark `[FIXED 2026-10-12]`.
