# PRD: C2-SCI O2 Observability & Ledger Reorder Backlog Reconciliation

## 1. Objective & Background
All 5 C2-SCI (Q-C6-1) scheduler-context issuer subslices are built and independently reviewed PASS. Commit `10e5eafe179a4ead78cc3b0f4e0168c125c1c9a5` reordered `mint_scheduler_context` step 4 (read-only signer availability check) ahead of step 5 (single-use ledger burn) so that a transient signer outage does not burn a valid lease's one-shot slot before denial.
However:
1. `DurableSingleUseLedger` currently computes in-process counters for `stats()` (`recorded`, `replays`), resetting on process restart, and does not expose a durable marker count reflecting persisted disk state.
2. The dashboard backend and frontend do not expose the durable ledger marker count or document the operator reset command for Activation-Gate intervenability.
3. `.agent/memory/issues-backlog.md` still lists `c2-sci-ledger-burn-before-signer-check + O2-observability (pre-activation polish, NON-blocking)` as `[OPEN]`.

This slice delivers the O2 observability and intervenability contract, proves durable marker counting hermetically, surfaces ledger state to the dashboard API and UI, and reconciles the backlog.

---

## 2. Requirements & Specification

### A. `scripts/ai/lib/scheduler_context_issuer.py`
- Add `durable_count() -> int` on `DurableSingleUseLedger`: counts non-hidden files in `self._dir` safely, returning 0 if directory is missing or inaccessible.
- Update `DurableSingleUseLedger.stats() -> dict[str, int]`: returns `{"recorded": self._recorded, "replays": self._replays, "durable_markers": self.durable_count()}`.
- Update `InMemorySingleUseLedger.stats() -> dict[str, int]`: returns `{"recorded": len(self._used), "replays": self._replays, "durable_markers": 0}`.
- Document the operator intervenability reset command (`rm <ledger_dir>/<sha256("{lease_id}\\x00{grant_digest}")>`) in class docstrings and comments.

### B. `dashboard/backend/api/routes/aistack.py`
- In `_stats_capability_enforcement()` under `c2_scheduler_context_issuer`:
  - Inspect ledger directory from `AQ_SCHEDULER_CONTEXT_LEDGER_DIR` or default `/var/lib/aq-c2-scheduler-context-issuer/ledger`.
  - Expose `ledger_marker_count` (int or null if directory missing).
  - Expose `operator_reset_command` ("rm <ledger_dir>/<marker_digest>").

### C. `assets/dashboard.js`
- Render `C2-SCI Ledger Markers` row under the C2-SCI section showing marker count (or `--` when not applicable).

### D. Tests & Service Coverage
- Update `scripts/testing/test-scheduler-context-ledger.py`: assert `durable_count()` and `stats()["durable_markers"]` track created files across multiple keys and simulated restarts.
- Update `scripts/testing/test-c2-sci-service-coverage.py`: assert dashboard API surfaces `ledger_marker_count` and ledger exposes `durable_count`.
- Ensure all 56 Tier-0 gates pass.

### E. Backlog Reconciliation
- Update `.agent/memory/issues-backlog.md`: mark `c2-sci-ledger-burn-before-signer-check + O2-observability` as `[FIXED 2026-10-12]`.

---

## 3. Activation Gate Attestation (6 Dimensions)
1. **Integrated**: Called in live `aistack.py` route and `scheduler_context_issuer.py`.
2. **Turned ON**: Active on live code path with safe fallbacks.
3. **Functionally Validated**: Hermetic unit and service coverage tests passing offline.
4. **Observable**: Surfaced via `aistack.py` `/stats/capability-enforcement` and `dashboard.js`.
5. **Intervenable**: Operator reset command documented and attested.
6. **PM-tracked**: Issues backlog reconciled with ground-truth resolution.
