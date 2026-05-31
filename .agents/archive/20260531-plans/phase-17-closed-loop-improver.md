# Phase 17 — Closed-Loop Improver: Close the Autonomous Execution Gap

Status: `pending`
Created: 2026-04-30
Owner: Claude (orchestrator) / Qwen (implementation)
Source: System Assessment & AGI Scaffold Architecture (2026-04-30)
Predecessor: Phase 7 (PRSI program — complete), Phase 16 (identity kernel)

---

## Objective

Replace the placeholder block in `autonomous_loop.py` (lines 301–310) with a real
experiment execution pipeline. The system must be able to:
1. Convert a hypothesis to a sandboxed test
2. Run validation gates against the change
3. Auto-accept improvements that pass all gates
4. Auto-revert on gate failure
5. Route destructive/high-risk changes through PRSI approval queue (no auto-apply)

This closes the single most critical open loop in the current AI stack.

---

## Scope Lock

In scope:
- `ai-stack/autonomous-improvement/autonomous_loop.py` — replace placeholder (lines ~297–310)
- `ai-stack/autonomous-improvement/experiment_executor.py` (new) — experiment runner
- `ai-stack/autonomous-improvement/sandbox_validator.py` (new) — gate runner
- `scripts/testing/validate-autonomous-loop-gates.sh` (new) — CI gate for this module
- Integration with PRSI queue (`scripts/automation/prsi-orchestrator.py`) for high-risk routing
- Declarative options for risk threshold and budget caps in `nix/modules/core/options.nix`

Out of scope:
- Spinning up ephemeral NixOS VMs (Phase 20 scope — predictive sandbox)
- Affective engine integration (Phase 19)
- Changes to the PRSI artifact schema (already defined in `config/schemas/prsi/`)
- Changes to `autonomous_loop.py` beyond the placeholder block and wiring

Constraints:
- Changes to `nix/modules/` MUST route through PRSI approval queue (never auto-apply)
- Auto-apply is only permitted for runtime Python/Bash changes with blast_radius=low
- Budget cap: max 3 auto-apply actions per autonomous loop cycle
- All experiments must write evidence artifacts to `data/prsi-artifacts/runs/`

---

## Context References

Files to read first:
- `ai-stack/autonomous-improvement/autonomous_loop.py` (full file — 432 lines)
- `ai-stack/autoresearch/` directory (existing autoresearch framework to integrate with)
- `scripts/automation/prsi-orchestrator.py` (PRSI queue interface)
- `config/runtime-prsi-policy.json` (budget and risk gates)
- `config/schemas/prsi/cycle-plan.schema.json` (artifact schema)
- `data/prsi-artifacts/examples/` (reference artifact format)

---

## Steps

### 17.1 — Experiment Executor

**Owner**: Qwen
**Files**: `ai-stack/autonomous-improvement/experiment_executor.py` (new)

Tasks:
1. Create `ExperimentExecutor` class:
   - `convert_hypothesis(hypothesis)` → `ExperimentSpec`:
     - `spec.type`: `runtime_patch` | `prompt_update` | `config_change` | `nix_module_change`
     - `spec.blast_radius`: `low` | `medium` | `high`
     - `spec.files_affected`: list of paths
     - `spec.patch_content`: unified diff string
   - `execute(spec, dry_run=True)` → `ExperimentResult`:
     - dry_run=True: log intent, return `{applied: false, reason: "dry_run"}`
     - dry_run=False + blast_radius=low: apply patch via `git apply --check` then `git apply`
     - dry_run=False + blast_radius>=medium: enqueue in PRSI queue, return `{applied: false, queued: true, prsi_id}`
     - Always write `data/prsi-artifacts/runs/<cycle_id>/experiment-<n>.json`
   - `revert(spec)`: `git revert --no-commit` + `git reset HEAD` for applied patches

Validation:
- `python3 -m py_compile ai-stack/autonomous-improvement/experiment_executor.py`
- Dry-run smoke: `python3 -c "from experiment_executor import ExperimentExecutor; e = ExperimentExecutor(); print(e.convert_hypothesis(type('H',(),{'description':'test patch','experiment_config':{}})()))"`

### 17.2 — Sandbox Validator (Gate Runner)

**Owner**: Qwen
**Files**: `ai-stack/autonomous-improvement/sandbox_validator.py` (new)

Tasks:
1. Create `SandboxValidator` class:
   - `run_gates(spec, result)` → `ValidationReport`:
     - Gate 1: syntax check (`bash -n` for .sh, `python3 -m py_compile` for .py, `nix-instantiate --parse` for .nix)
     - Gate 2: smoke test — call `scripts/testing/smoke-focused-parity.sh` if applicable
     - Gate 3: aq-qa baseline — call `scripts/ai/aq-qa 0` and require >=39 pass
     - Gate 4: report contract — call `scripts/testing/check-aq-report-contract.sh`
   - Returns `{passed: bool, gates: [{name, passed, output}], recommendation: accept|revert|queue}`
   - `recommendation=revert` if any gate fails
   - `recommendation=queue` if blast_radius >= medium (regardless of gate results)
   - Writes gate evidence to `data/prsi-artifacts/runs/<cycle_id>/validation-<n>.json`

Validation:
- `python3 -m py_compile ai-stack/autonomous-improvement/sandbox_validator.py`
- `python3 -c "from sandbox_validator import SandboxValidator; v = SandboxValidator(); print(v.run_gates(None, None))"` exits without crash

### 17.3 — Wire Into autonomous_loop.py

**Owner**: Qwen
**Files**: `ai-stack/autonomous-improvement/autonomous_loop.py`

Tasks:
1. Read lines 270–330 of `autonomous_loop.py` carefully
2. Replace lines 297–310 (the placeholder block) with:
   ```python
   from experiment_executor import ExperimentExecutor
   from sandbox_validator import SandboxValidator

   executor = ExperimentExecutor(cycle_id=cycle.id, dry_run=self.dry_run)
   validator = SandboxValidator(cycle_id=cycle.id)

   for i, hyp in enumerate(hypotheses[:self.max_experiments_per_cycle]):
       spec = executor.convert_hypothesis(hyp)
       result = executor.execute(spec)

       if result.applied:
           report = validator.run_gates(spec, result)
           if report.recommendation == "revert":
               executor.revert(spec)
               cycle.experiments_rejected += 1
           else:
               cycle.experiments_accepted += 1
       elif result.queued:
           # PRSI queue handles high-risk changes via human approval
           cycle.experiments_run += 1

       cycle.experiments_run += 1
   ```
3. Add `self.max_experiments_per_cycle = int(os.environ.get("AUTONOMOUS_MAX_EXPERIMENTS", "3"))`
   to `__init__`

Validation:
- `python3 -m py_compile ai-stack/autonomous-improvement/autonomous_loop.py`
- `python3 ai-stack/autonomous-improvement/autonomous_loop.py --dry-run` exits 0
- No "not yet implemented" printed in dry-run output

### 17.4 — Declarative Options + CI Gate

**Owner**: Qwen
**Files**: `nix/modules/core/options.nix`, `scripts/testing/validate-autonomous-loop-gates.sh` (new)

Tasks:
1. Add to `options.nix` under `mySystem.aiStack.autonomousImprovement`:
   ```nix
   autonomousImprovement = {
     maxExperimentsPerCycle = mkOption { type = types.int; default = 3; };
     autoApplyBlastRadiusMax = mkOption { type = types.enum ["low" "medium"]; default = "low"; };
     dryRun = mkOption { type = types.bool; default = true; };
   };
   ```
2. Inject as env vars into autonomous improvement service (if service exists in ai-stack.nix)
3. Create `scripts/testing/validate-autonomous-loop-gates.sh`:
   - `python3 -m py_compile` for all 3 new Python files
   - Check that placeholder comment no longer exists in autonomous_loop.py
   - Check that `experiment_executor.py` and `sandbox_validator.py` exist
   - Wire into `scripts/automation/run-advanced-parity-suite.sh`

Validation:
- `bash -n scripts/testing/validate-autonomous-loop-gates.sh`
- `bash scripts/testing/validate-autonomous-loop-gates.sh` exits 0
- `nix-instantiate --parse nix/modules/core/options.nix` exits 0

---

## Verification Matrix

Before marking any task done:
1. `python3 -m py_compile` for all 3 new Python modules
2. `bash -n` for the new gate script
3. `nix-instantiate --parse` for options.nix changes
4. `python3 autonomous_loop.py --dry-run` exits 0, no placeholder text in output
5. `bash scripts/testing/validate-autonomous-loop-gates.sh` exits 0
6. `aq-qa 0` → 39+ passed, 0 failed
7. Rollback: `git revert <commits>`

---

## Work Queue

### Task: CLO-001
- Phase: 17.1
- Owner agent: qwen
- Files: `ai-stack/autonomous-improvement/experiment_executor.py`
- Commands:
  - `cat ai-stack/autonomous-improvement/autonomous_loop.py | head -50` (read imports/init)
  - `python3 -m py_compile ai-stack/autonomous-improvement/experiment_executor.py`
- Success criteria:
  - py_compile passes
  - `ExperimentExecutor.convert_hypothesis()` returns `ExperimentSpec` with `blast_radius`
  - dry_run returns `{applied: false, reason: "dry_run"}`
- Rollback: delete file
- Status: pending

### Task: CLO-002
- Phase: 17.2
- Owner agent: qwen
- Files: `ai-stack/autonomous-improvement/sandbox_validator.py`
- Commands:
  - `python3 -m py_compile ai-stack/autonomous-improvement/sandbox_validator.py`
- Success criteria:
  - py_compile passes
  - `run_gates()` returns dict with `passed`, `gates`, `recommendation` keys
- Status: pending

### Task: CLO-003
- Phase: 17.3
- Owner agent: qwen
- Files: `ai-stack/autonomous-improvement/autonomous_loop.py`
- Commands:
  - `grep -n "placeholder\|Placeholder\|not yet implemented" ai-stack/autonomous-improvement/autonomous_loop.py`
  - `python3 -m py_compile ai-stack/autonomous-improvement/autonomous_loop.py`
  - `python3 ai-stack/autonomous-improvement/autonomous_loop.py --dry-run 2>&1 | tail -20`
- Success criteria:
  - No placeholder text found
  - dry-run exits 0
  - `experiments_run`, `experiments_accepted`, `experiments_rejected` are populated in output
- Status: pending

### Task: CLO-004
- Phase: 17.4
- Owner agent: qwen
- Files: `nix/modules/core/options.nix`, `scripts/testing/validate-autonomous-loop-gates.sh`
- Commands:
  - `nix-instantiate --parse nix/modules/core/options.nix`
  - `bash -n scripts/testing/validate-autonomous-loop-gates.sh`
  - `bash scripts/testing/validate-autonomous-loop-gates.sh`
- Status: pending

---

## Rollback

- Python changes: `git revert <commit>` restores autonomous_loop.py; delete new modules
- Nix option additions: generation rollback (`sudo nixos-rebuild switch --rollback`)
- PRSI queue: any queued items from testing → `prsi-orchestrator.py reject <id>`
