# Antigravity Independent Review — Model Freshness Repair

**Round ID**: `model-freshness-repair-20260926`  
**Role**: Independent Security / Correctness Reviewer  
**Target Output**: `.agents/plans/model-freshness-repair-20260926/antigravity.md`  
**Reviewed Subject Hash (SHA-256)**: `c138d32a3e855825f93fa1d50b9151c48b42ac8acc94e3d0a58041b006d6fb65`  
**Review Posture**: Read-only, no file edits, no staging, no commit.

---

## 1. Executive Summary & Assessment

The staged candidate patch resolves a critical telemetry and freshness integrity defect across the model profiling and cataloging subsystems. Previously, failed or timed-out throughput measurements defaulted to a hardcoded `4.0` tok/s fallback, minting a fraudulent "fresh" probe receipt on disk. Concurrently, the dashboard was reading a static Python module rather than the runtime-editable `config/model-catalog.yaml` SSOT, and lacked verification that the active model symlink (`active.gguf`) resolves to a legitimately catalogued model file.

The patch corrects these issues with clean, fail-closed semantics:
1. **No False Freshness Receipts**: When `_probe_speed()` fails or times out, it returns `None`, and `probe()` aborts before Step 5 without updating `profile.json` or minting fresh review timestamps.
2. **Provenance Tracking**: Added `throughput_source` (`live_probe` vs. `fallback`) across `ModelProfile`, `_default_profile()`, `config/model-profile.json`, and dashboard metadata.
3. **Runtime Catalog SSOT**: `dashboard/backend/api/routes/models.py` and test harnesses now read directly from `config/model-catalog.yaml` via safe YAML parsing rather than dynamic Python importlib execution.
4. **Symlink Target Parity**: Resolves `model_path` to its canonical target filename and verifies it against declared catalog entries. An uncatalogued active model causes the dashboard to report `stale`.
5. **Slow-Path Tolerance**: Adjusted `_PROBE_TIMEOUT` to 90.0 s to accommodate APU MoE execution under memory pressure (< 2 tok/s over 60 tokens) without timing out valid live measurements.

---

## 2. Invariant & Obligation Verification

* **Freshness Update Prevention on Failed Measurement**: **PASS**  
  `model_probe.py:164` returns `None` on failure; `:228-232` immediately returns `cached or _default_profile()` without persisting. Verified via isolated mock probe in `scripts/testing/test-model-probe-freshness.py`.
* **Provenance Attribution**: **PASS**  
  Distinguishes `live_probe` from `fallback`. Statically asserted in `scripts/testing/test-model-catalog-freshness.py`.
* **Runtime Catalog SSOT & Dashboard Truthfulness**: **PASS**  
  `models.py:413` points to `config/model-catalog.yaml`. `_catalog_metadata()` loads `_meta`, `chat_models`, and `embedding_models`. No Python bytecode caching or import execution.
* **Symlink Target Membership**: **PASS**  
  `models.py:513-525` resolves symlink targets (`Path(model_path).resolve(strict=True).name`) and verifies presence in `declared_files`.
* **Test Coverage & Regression**: **PASS**  
  * `python3 scripts/testing/test-model-catalog-freshness.py`: PASS.
  * `python3 scripts/testing/test-model-probe-freshness.py`: PASS (verifies failed probe does not refresh, successful probe labels `live_probe`).
  * `python3 scripts/testing/test-modal-task-profiles.py`: PASS (19/19).
  * Syntax and compilation across all touched files: PASS.

---

## 3. Validation Results

* Staged diff full-index digest verification:
  ```bash
  git diff --cached --full-index | sha256sum
  # c138d32a3e855825f93fa1d50b9151c48b42ac8acc94e3d0a58041b006d6fb65
  ```
  Digest matches the review subject hash exactly.
* `python3 scripts/testing/test-model-catalog-freshness.py`: Exit 0 (`PASS: model catalog/profile freshness telemetry is wired`).
* `python3 scripts/testing/test-model-probe-freshness.py`: Exit 0 (`PASS: model probe only refreshes receipts after live throughput measurement`).
* `python3 -m py_compile ai-stack/mcp-servers/hybrid-coordinator/extensions/model_probe.py dashboard/backend/api/routes/models.py scripts/testing/test-model-catalog-freshness.py scripts/testing/test-model-probe-freshness.py`: Exit 0.
* YAML/JSON schema check on `config/model-catalog.yaml` and `config/model-profile.json`: Exit 0.

---

ACCEPTED
