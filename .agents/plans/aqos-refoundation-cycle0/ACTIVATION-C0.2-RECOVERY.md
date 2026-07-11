# Owner Activation Record — C0.2 Recovery Authorization

**Decision:** `implementation_authorized = AUTHORIZED`
**Activation ID:** `activate-c0.2-recovery-20260711`
**Activates prepared record:** `IMPLEMENTATION-AUTHORIZATION-C0.2-RECOVERY.md`,
raw SHA-256 `54845a5e7d2e1b0e1b6c3c10b080e1de7bb133252d0c49cab5055d59922890fc`
**Idempotency key:** `02839481-10e1-4850-8bfb-80aa62538820` (fresh; supersedes suspended `9ec8fd14…`)
**Issued:** 2026-07-11
**Issuer:** hyperd (owner) — explicit directive in the operator session 2026-07-11 ("yes" to activate
the C0.2 recovery with codex as implementer), executed by the fable-5 orchestrator.
**Attribution assurance:** `ORCHESTRATOR_ATTESTED`

## Preconditions — all verified at activation

1. **Two-family fresh exact-root APPROVE:** Anthropic (`REVIEW-FABLE5-C02-RECOVERY.md`, re-pinned) +
   Gemini (`REVIEW-GEMINI-C0.2-RECOVERY-V2.md`), both on root `377052c2…`.
2. **Package verify exit 0** immediately before activation (root `377052c2…`).
3. **Preserved-diff disposition complete:** `REJECT_AND_REWORK` (`C0.2-PRESERVED-DIFF-DISPOSITION.md`);
   rejected diff bound as read-only patch evidence in `.agents/archive/c02-recovery-20260711/`; no
   file inherited.
4. **Ownership preflight:** the amended C0.2 surfaces (incl. new `qa_evidence_store.py`,
   `config/env-contract.yaml`, `test-telemetry-root-boundary.py`) are clean at HEAD
   `100f6bb863e9d652f2044cab50f7c430e025bc75`.
5. **Telemetry integrity:** `.agents/telemetry` is a real tracked directory matching Git; no
   symlink/bind/redirect present.
6. **Suspended key `9ec8fd14…` remains terminal** (SUSPENDED, never reactivated).

## Grant (inherits the prepared record, now AUTHORIZED)

- **Implementer:** **codex lane** (owner decision). Rationale: codex detected the incident,
  self-suspended, and authored the corrective architecture; it runs as a state-observing lane that
  reads round/authorization state before writing.
- **Reviewer:** an independent non-codex family (Anthropic or Gemini).
- **Surfaces:** only the amended `C0.2-SURFACE-INVENTORY.md` list. **Explicitly forbidden:**
  `.agents/telemetry/**`, deployed telemetry contents, NixOS wiring, mounts, symlinks, bind mounts,
  mutable-`latest` fallback writes.
- **Expiry:** 2026-07-18. **Use limit:** single-use against key `02839481…`.
- **Automatic suspension:** root drift, ownership conflict, undeclared consumer, any redirect/symlink
  attempt, mutable fallback, weak consumer verification, lost concurrent evidence, pointer-target GC,
  required-UNKNOWN passing, or CLI/dashboard disagreement.
- **Acceptance budgets are hard, not waivable by narrative:** aq-report ≤10% relative AND ≤60s
  absolute; acceptance measurements must be protocol-complete (5 cold + 20 warm) — the prior attempt's
  n=3 warm sample and +52% regression are the anti-patterns being corrected.

`RECORD: implementation_authorized = AUTHORIZED for C0.2 recovery, root 377052c2…, implementer codex,
expiring 2026-07-18, single-use key 02839481-10e1-4850-8bfb-80aa62538820.`

## Consumption record (2026-07-11)

`state: CONSUMED` — consumed by the codex-lane C0.2 rework (`qa_evidence_store.py` +
`aq-report`/`aistack.py`/producers + 3 new tests). Independent slice review: Anthropic lane (fable-5,
non-implementer, non-Gemini per reassignment). Verdict **APPROVE**, on independently reproduced
evidence:
- **All surfaces within the amended inventory** (0 outside); **no telemetry symlink** — the incident
  was not repeated; the resolver is implemented as code in `qa_evidence_store.py`.
- **5 focused suites pass (26 cases) re-run by the reviewer:** evidence-store 4/4, evidence-algebra
  6/6, telemetry-boundary 4/4 (symlink/bind/traversal fail-closed proven), scorecard 8/8,
  agent-run-envelope pass.
- **Check-IDs match the frozen package** in both registries: C0.2 new check owns `0.10.28`;
  capability-flush renumbered to `0.10.35`; no duplicate/divergent registration. `aq-qa 0` = 167/0
  with 0.10.28 passing live.
- **aq-report budget PASS, protocol-complete (5 cold + 20 warm):** −14.1% cold / −2.7% warm mean
  regression, p95 ≤ 23.5s (≤10% relative AND ≤60s absolute). Reviewer spot-timing consistent with the
  baseline range — a full reversal of the rejected attempt's +40–52% on n=3.
- **Honest BLOCKED reporting:** codex marked the scorecard-endpoint measurement `BLOCKED` (sandbox
  denied socket creation) rather than fabricating it — the opposite of the rejected attempt's false
  waiver.

**Written deferral (Rule 15):** the scorecard-endpoint p95 ≤250ms measurement is DEFERRED to
post-dashboard-restart — the new `aistack.py` route must be live to measure it. Tracked below; must be
captured before C0.2 is marked fully activated. All other dimensions are validated now.
Tier 0 23/23. This authorization is spent.
