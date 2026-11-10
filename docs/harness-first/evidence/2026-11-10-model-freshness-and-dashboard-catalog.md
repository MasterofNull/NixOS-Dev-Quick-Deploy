# Evidence: Model Catalog/Profile Freshness, Dashboard PyYAML & Registry Disk Reconciliation (2026-11-10)

## Summary
Resolved QA check `0.10.5` (`test-model-catalog-freshness.py`) and three related Dashboard `:8889` model-management bugs uncovered during live API probing:
1. **`model_probe` Cache Freshness & Force Re-Probe**:
   - `ai-stack/mcp-servers/hybrid-coordinator/extensions/model_probe.py`: `probe(..., *, force: bool = False)` and `_is_cache_fresh(path)` enforce `freshness_max_age_days` (default 45d) against `probed_at` and `_meta.reviewed_at` so stale profiles automatically trigger a fresh probe instead of returning stale cached data indefinitely.
   - `ai-stack/mcp-servers/hybrid-coordinator/model_probe.py`: explicitly re-exports `_default_profile_path`, `_save`, `_load_cached`, `_probe_speed`, and `_default_profile` so tests and callers patching `model_probe.*` work reliably across the compatibility shim.
   - `scripts/ai/aq-model-eval`: passes `force=args.force` directly into `model_probe.probe()` without unlinking `profile_path` first (preserving existing profile metadata if a probe fails).
2. **Dashboard `:8889` Model Catalog & Registry Reconciliation**:
   - `nix/modules/services/command-center-dashboard.nix`: added `pyyaml` to `dashboardPython` so `/api/models/catalog` parses `config/model-catalog.yaml` instead of failing with `No module named 'yaml'`.
   - `ai-stack/mcp-servers/hybrid-coordinator/model_registry.py`: added `_reconcile_disk_state()` so `ModelRegistry` reconciles stale `status: "downloading"` / `"active"` entries against `/var/lib/llama-cpp/models/*.gguf` and the `active.gguf` symlink target on load.
3. **Live Re-Probe & Catalog Review**:
   - Re-probed live `http://127.0.0.1:8080` (`Qwen3.6-35B-A3B-UD-Q4_K_M.gguf` via `active.gguf`) using `python3 scripts/ai/aq-model-eval --force --profile-path config/model-profile.json` (`measured_tps_output: 1.7`, `throughput_source: "live_probe"`, `probed_at: 2026-11-10T19:42:40Z`).
   - Verified `config/model-catalog.yaml` against active GGUF inventory (`_meta.last_updated: 2026-11-10T18:30:16Z`).

## Commands Executed & Outputs
```text
$ python3 scripts/ai/aq-model-eval --force --profile-path config/model-profile.json
[aq-model-eval] Probing http://127.0.0.1:8080 ...
{
  "model_id": "active.gguf",
  "model_path": "/var/lib/llama-cpp/models/active.gguf",
  "context_length": 262144,
  "measured_tps_output": 1.7,
  "throughput_source": "live_probe",
  ...
  "probed_at": "2026-11-10T19:42:40.814090Z"
}

$ python3 scripts/testing/test-model-probe-freshness.py
PASS: model_probe writes freshness metadata and aq-model-eval refreshes the profile

$ python3 scripts/testing/test-model-catalog-freshness.py
PASS: model catalog and model profile freshness are within policy
```
