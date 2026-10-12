# PROJECT-ROUTER-GRANULAR-EXCLUSION-PRD: Granular Subagent Exclusion & Router Reconciliation

## 1. Problem Statement & Background
Under Rule 18 (Agent-Agnostic Roles) and Rule 21 (Collaborative Stewardship), the orchestrator routes role instances (architect, implementer, reviewer, binding-acceptance) to whichever lane is available, eligible, independent, and cheapest.
When dispatching an independent reviewer or binding-acceptance agent for a slice implemented by a subagent (e.g. `claude-subagent-X` or `codex-subagent-Y`), the orchestrator passes `--exclude <implementer_id>` to ensure review independence.

However, `scripts/ai/aq-role-route` previously matched exclude tokens by checking:
```python
def _matches_exclude(lane_id: str, token: str) -> bool:
    token = token.strip().lower()
    if not token:
        return False
    if token == lane_id or token in LANES[lane_id]["aliases"]:
        return True
    return token.split("-")[0] == lane_id
```
Because of `token.split("-")[0] == lane_id`, passing `claude-subagent-XYZ` split to `claude`, which inadvertently excluded the entire `claude` parent lane! This disqualified fresh Claude flagship models (such as Opus 5.5 or Fable 5) from serving as independent reviewers or binding acceptance authorities for subagent work, creating artificial lane bottlenecks.

Furthermore:
- Backlog item `router-core-stale-reclaim-toctou` was previously resolved in commit `fbf9fe16` with `RECLAIM-TOCTOU-ACCEPTANCE.md` and flock CAS synchronization, but was still marked `[OPEN]` in `.agent/memory/issues-backlog.md`.
- Foundation-C tracker issue `c2-sci ledger-burn-before-signer-check + O2 observability` was resolved by PR #491 (`ebf8e36e`), but remained listed as open in `.agents/plans/aqos-foundation-c/tracker.json`.

## 2. Requirements & Changes
1. **Granular Exclusion in `scripts/ai/aq-role-route`**:
   - Differentiate between lane/model exclusions and subagent/task instance exclusions.
   - If a token names a subagent (`subagent` in token or `sub-agent` in token) or a timestamped task ID (`<lane>-<digits>-*`), it identifies a specific delegate instance and must NOT exclude the entire parent lane.
   - Preserves complete exclusion when the caller explicitly names the lane (`claude`, `codex`, `gemini`, `local`) or a lane-level alias (`claude-sonnet`, `claude-opus`, `codex-cli`, etc.).
2. **Regression Testing in `scripts/testing/test-agent-agnostic-router.py`**:
   - Add fixture `test_role_route_subagent_exclude_retains_flagship()` verifying that excluding `claude-subagent-implementer-1` leaves `claude` eligible for reviewer and binding-acceptance roles, while `--exclude claude` or `--exclude claude-sonnet` properly excludes the lane.
3. **Tracker & Backlog Reconciliation**:
   - Update `.agents/plans/aqos-foundation-c/tracker.json` marking `c2-sci ledger-burn-before-signer-check + O2 observability` as `resolved`.
   - Update `.agent/memory/issues-backlog.md` marking `router-core-stale-reclaim-toctou` and `router-role-route-exclude-lane-granularity` as `[FIXED]`.

## 3. Verification & Acceptance
- `python3 scripts/testing/test-agent-agnostic-router.py` passes all checks (including new subagent exclusion tests).
- All 56 Tier-0 gates pass (`scripts/governance/tier0-validation-gate.sh --pre-commit`).
- Clean merge into `origin/main` via PR.
