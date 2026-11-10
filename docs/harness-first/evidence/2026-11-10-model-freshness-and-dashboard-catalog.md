# Evidence: Model Catalog/Profile Freshness, Dashboard PyYAML & Registry Disk Reconciliation (2026-11-10)

## Objective
Resolve QA check `0.10.5` (`test-model-catalog-freshness.py`) and three related Dashboard `:8889` model-management bugs uncovered during live API probing:
1. Enforce `freshness_max_age_days` (default 45d) against `probed_at` and `_meta.reviewed_at` in `model_probe.probe()` and add `force: bool = False` so `aq-model-eval --force` re-probes without unlinking `config/model-profile.json` beforehand.
2. Add `pyyaml` to `dashboardPython` in `nix/modules/services/command-center-dashboard.nix` so `/api/models/catalog` parses `config/model-catalog.yaml`.
3. Add `_reconcile_disk_state()` to `ModelRegistry` (`ai-stack/mcp-servers/hybrid-coordinator/model_registry.py`) so stale `downloading`/`active` statuses reconcile against `/var/lib/llama-cpp/models/*.gguf` and `active.gguf`.
4. Re-probe live `http://127.0.0.1:8080` (`Qwen3.6-35B-A3B-UD-Q4_K_M.gguf` via `active.gguf`) using `aq-model-eval --force`.

## Workflow/Session IDs
- Wave: `wave-20261110-b`
- Implementer delegation: `codex-20261110-102911-bfv840`

## Delegation Decision
- Delegated implementation to Codex (`scripts/ai/delegate-to-codex --role implement --mode edit`) in isolated worktree `.agents/delegation/worktrees/codex-20261110-102911-bfv840` per Rule 17.
- Orchestrator executed the live `aq-model-eval --force` probe against `:8080` once the inference slot was idle.

## Commands Executed
```bash
python3 scripts/ai/aq-model-eval --force --profile-path config/model-profile.json
python3 scripts/testing/test-model-probe-freshness.py
python3 scripts/testing/test-model-catalog-freshness.py
./scripts/governance/ci-clean-env.sh --all --only harness-first-static-gates
```

## Validation Evidence
```text
$ python3 scripts/ai/aq-model-eval --force --profile-path config/model-profile.json
[aq-model-eval] Probing http://127.0.0.1:8080 ...
{
  "model_id": "active.gguf",
  "model_path": "/var/lib/llama-cpp/models/active.gguf",
  "context_length": 262144,
  "measured_tps_output": 1.7,
  "throughput_source": "live_probe",
  "probed_at": "2026-11-10T19:42:40.814090Z"
}

$ python3 scripts/testing/test-model-probe-freshness.py
PASS: model_probe writes freshness metadata and aq-model-eval refreshes the profile

$ python3 scripts/testing/test-model-catalog-freshness.py
PASS: model catalog and model profile freshness are within policy
```

## Rollback Plan
- Revert the squash commit on `main` and redeploy via `scripts/maintenance/aq-deploy-current`.

## Residual Risk
- `command-center-dashboard` service `pyyaml` dependency activates on the next `aq-deploy-current` rebuild.

## Hint Feedback
- `aq-hints` and `test-model-catalog-freshness.py` accurately pinpointed the 45-day freshness policy and `model_probe` cache behavior.
