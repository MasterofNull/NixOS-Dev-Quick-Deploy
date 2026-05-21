# Cross-Surface Change Contract

Runtime changes must remain visible to operators and future agents. When a slice changes a module, feature, service, route, agent capability, or automation path, the same slice must also update at least one connected surface that explains or exposes the change.

Accepted visibility surfaces:

- connected documentation, architecture notes, plans, PRDs, runbooks, or handoff evidence;
- AI Command Center/dashboard surfaces when health, tests, metrics, drift, or agent/service state changed;
- explicit non-applicability recorded in the handoff or plan when no docs/dashboard update is appropriate.

The Tier 0 gate enforces this with `scripts/governance/check-cross-surface-contract.py`. It is path-based by design: runtime/service paths such as `ai-stack/`, `nix/modules/`, `dashboard/backend/`, `scripts/ai/`, and `scripts/automation/` require a staged docs/handoff/planning or dashboard surface.

This does not replace judgment. If a runtime change introduces a new measurable signal, the dashboard/API should expose it even if a documentation file is also changed. The gate only catches the minimum requirement; reviewers still verify that the selected surface is the correct one.

## Local checks

```bash
python3 scripts/governance/check-cross-surface-contract.py --mode=--pre-commit
scripts/governance/tier0-validation-gate.sh --pre-commit
```
