# A2A task for antigravity — round 'model-freshness-repair-20260926'

Dropped: 2026-09-26T02:52:17Z

Respond by writing `.agents/plans/model-freshness-repair-20260926/antigravity.md`.

## SCOPE & STOP (HARD — read before writing)
- Edit ONLY the files this task names as surfaces. A related-looking file is still out of scope.
- NEVER implement a data/config change as a filesystem shortcut: no symlink, bind mount, mount,
  chmod/chown/rm on tracked or runtime paths. 'Single source of truth' = a resolver in code,
  never one directory replacing/redirecting another.
- NO DELETE — archive to a timestamped path; never rm/rmdir.
- If this task references an authorization/round: confirm it still reads AUTHORIZED and (where a
  package root is named) that `aq-package-freeze verify` exits 0 BEFORE writing. If suspended,
  STOP — do not recreate or continue suspended files.
- Undeclared dependency discovered -> STOP and report; do not expand scope to 'make it work'.
- Budgets/acceptance criteria are hard facts: a measured violation FAILS; a sentence calling it
  'acceptable' does not change the number. Report the real value.
- Write ONLY your own named output file. Do NOT edit shared files. Do NOT commit.
- When unsure whether something is in scope: it is not. Report, do not act.

COLLABORATIVE ROUND 'model-freshness-repair-20260926'.
=== REVIEW ARTIFACT (/tmp/model-freshness-candidate.patch) — INLINED; do NOT read the file ===
diff --git a/ai-stack/mcp-servers/hybrid-coordinator/extensions/model_probe.py b/ai-stack/mcp-servers/hybrid-coordinator/extensions/model_probe.py
index fc30bd9cadecab51e3d68bf47026dcaa5b38b0e9..3453ee0baea6a3cbcc0fa4e8a357929c87db7a11 100644
--- a/ai-stack/mcp-servers/hybrid-coordinator/extensions/model_probe.py
+++ b/ai-stack/mcp-servers/hybrid-coordinator/extensions/model_probe.py
@@ -37,7 +37,11 @@ from shared.llm_config import build_llama_payload, PROBE_MAX_TOKENS  # noqa: E40
 logger = logging.getLogger("model-probe")
 
 _PROFILE_VERSION = 2
-_PROBE_TIMEOUT = 30.0
+# The current local lane can run below 2 tok/s under memory pressure. A 60-token
+# probe therefore needs more than 30 seconds; timing it out and labelling the
+# 4.0 fallback as "measured" made freshness telemetry lie. Keep this bounded,
+# but large enough for the supported slow path.
+_PROBE_TIMEOUT = 90.0
 _SPEED_PROBE_TOKENS = 60  # generation tokens in the speed probe
 _SWITCHBOARD_TIMEOUT_S = float(os.getenv("LLAMA_CPP_SWITCHBOARD_TIMEOUT_S", "900"))
 _DIRECT_TIMEOUT_S = float(os.getenv("LLAMA_CPP_INFERENCE_TIMEOUT_SECONDS", "180"))
@@ -55,6 +59,7 @@ class ModelProfile:
     model_path: str = ""
     context_length: int = 4096
     measured_tps_output: float = 5.0
+    throughput_source: str = "unknown"
     has_thinking_mode: bool = False
     can_disable_thinking: bool = False
     supports_tools: bool = False
@@ -89,6 +94,7 @@ def _default_profile() -> ModelProfile:
     return ModelProfile(
         model_id="unknown-fallback",
         measured_tps_output=4.0,
+        throughput_source="fallback",
         has_thinking_mode=False,
         can_disable_thinking=False,
         budget_interactive=600,
@@ -136,7 +142,7 @@ def _compute_budgets(tps: float, has_thinking: bool) -> Dict[str, int]:
     }
 
 
-async def _probe_speed(client: httpx.AsyncClient, base_url: str) -> float:
+async def _probe_speed(client: httpx.AsyncClient, base_url: str) -> Optional[float]:
     """Measure output t/s with a short forced-generation prompt."""
     try:
         t0 = time.perf_counter()
@@ -158,7 +164,7 @@ async def _probe_speed(client: httpx.AsyncClient, base_url: str) -> float:
             return round(tps, 1)
     except Exception as exc:
         logger.warning("model_probe speed_probe_failed: %s", exc)
-    return 4.0  # conservative fallback
+    return None
 
 
 def _detect_thinking(chat_template: str, caps: Dict[str, Any]) -> tuple[bool, bool]:
@@ -222,6 +228,9 @@ async def probe(llama_cpp_url: str, profile_path: Optional[Path] = None) -> Mode
 
         # Step 3: Measure output t/s
         tps = await _probe_speed(client, llama_cpp_url)
+        if tps is None:
+            logger.warning("model_probe incomplete: throughput was not measured; freshness not updated")
+            return cached or _default_profile()
 
         # Step 4: Compute budgets
         budgets = _compute_budgets(tps, has_thinking and not can_disable)
@@ -232,6 +241,7 @@ async def probe(llama_cpp_url: str, profile_path: Optional[Path] = None) -> Mode
             model_path=model_path,
             context_length=context_length,
             measured_tps_output=tps,
+            throughput_source="live_probe",
             has_thinking_mode=has_thinking,
             can_disable_thinking=can_disable,
             supports_tools=supports_tools,
diff --git a/config/model-catalog.yaml b/config/model-catalog.yaml
index 73c077d56e8a1424d8d238d68e611075732a4958..2ce027b4d63870713c66384e9b8ffd8cd66f069f 100644
--- a/config/model-catalog.yaml
+++ b/config/model-catalog.yaml
@@ -1,7 +1,9 @@
 _meta:
   version: "1.1"
-  owner: claude-opus-4-8
-  last_updated: "2026-07-07"
+  owner: model-catalog-maintainers
+  last_updated: "2026-09-26T02:55:00Z"
+  freshness_max_age_days: 45
+  freshness_policy: "review the runtime catalog and verify the active GGUF resolves to a declared entry"
 
 # Model Catalog — runtime-editable, no nixos-rebuild needed to add models.
 #
diff --git a/config/model-profile.json b/config/model-profile.json
index 26451c19b64cd1f241bc5136599c3483dd9920b6..dc3954e1739ad1b60c22001724961a151e69a416 100644
--- a/config/model-profile.json
+++ b/config/model-profile.json
@@ -2,26 +2,27 @@
   "model_id": "active.gguf",
   "model_path": "/var/lib/llama-cpp/models/active.gguf",
   "context_length": 262144,
-  "measured_tps_output": 3.8,
+  "measured_tps_output": 1.4,
+  "throughput_source": "live_probe",
   "has_thinking_mode": true,
   "can_disable_thinking": true,
   "supports_tools": true,
   "supports_system_prompt": true,
   "eos_token": "<|im_end|>",
-  "budget_interactive": 444,
-  "budget_synthesis": 2223,
-  "budget_heavy": 2907,
-  "budget_lookup": 266,
-  "budget_reasoning": 1556,
+  "budget_interactive": 163,
+  "budget_synthesis": 819,
+  "budget_heavy": 1071,
+  "budget_lookup": 100,
+  "budget_reasoning": 573,
   "ctx_budget_lookup": 800,
-  "ctx_budget_synthesis": 2778,
-  "ctx_budget_reasoning": 2334,
+  "ctx_budget_synthesis": 1500,
+  "ctx_budget_reasoning": 1200,
   "profile_version": 2,
-  "probed_at": "2026-08-06T02:06:23.462537Z",
+  "probed_at": "2026-09-26T02:27:32.044103Z",
   "probe_model_id": "active.gguf",
   "_meta": {
-    "reviewed_at": "2026-08-06T02:06:23.462714Z",
-    "last_updated": "2026-08-06",
+    "reviewed_at": "2026-09-26T02:27:32.044310Z",
+    "last_updated": "2026-09-26",
     "version": "1.0",
     "freshness_policy": "phase154-profile-and-active-model-review",
     "owner": "model_probe"
diff --git a/dashboard/backend/api/routes/models.py b/dashboard/backend/api/routes/models.py
index 70a199e53a4b326e2bcfd8a8ce7b8f45570e8883..935e247d8ef4c887d1a43178c7ef1bfbde2da669 100644
--- a/dashboard/backend/api/routes/models.py
+++ b/dashboard/backend/api/routes/models.py
@@ -28,6 +28,7 @@ import time
 from pathlib import Path
 from typing import Any, AsyncGenerator, Dict, Optional
 
+import yaml
 from fastapi import APIRouter, HTTPException, Request, status
 from fastapi.responses import StreamingResponse
 
@@ -412,7 +413,7 @@ _REGISTRY_PATHS = [
 ]
 
 _MODEL_PROFILE_PATH = Path(os.getenv("MODEL_PROFILE_PATH", "")) if os.getenv("MODEL_PROFILE_PATH") else Path(__file__).resolve().parents[4] / "config" / "model-profile.json"
-_MODEL_CATALOG_PATH = Path(__file__).resolve().parents[4] / "ai-stack" / "mcp-servers" / "shared" / "model_catalog.py"
+_MODEL_CATALOG_PATH = Path(__file__).resolve().parents[4] / "config" / "model-catalog.yaml"
 
 
 def _parse_ts(value: str) -> Optional[dt.datetime]:
@@ -439,15 +440,18 @@ def _catalog_metadata() -> Dict[str, Any]:
     if not _MODEL_CATALOG_PATH.exists():
         return {}
     try:
-        import importlib.util
-
-        spec = importlib.util.spec_from_file_location("_dashboard_model_catalog", _MODEL_CATALOG_PATH)
-        if spec is None or spec.loader is None:
+        catalog = yaml.safe_load(_MODEL_CATALOG_PATH.read_text()) or {}
+        metadata = catalog.get("_meta", {})
+        if not isinstance(metadata, dict):
             return {}
-        module = importlib.util.module_from_spec(spec)
-        spec.loader.exec_module(module)
-        metadata = getattr(module, "CATALOG_METADATA", {})
-        return metadata.copy() if isinstance(metadata, dict) else {}
+        entries: Dict[str, Any] = {}
+        for section in ("chat_models", "embedding_models"):
+            section_entries = catalog.get(section, {})
+            if isinstance(section_entries, dict):
+                entries.update(section_entries)
+        result = metadata.copy()
+        result["entries"] = entries
+        return result
     except Exception as exc:
         logger.warning("models route: failed to load catalog metadata: %s", exc)
         return {}
@@ -474,7 +478,7 @@ def _model_freshness() -> Dict[str, Any]:
     model_path = profile.get("model_path")
     reviewed_at = meta.get("reviewed_at") or meta.get("last_updated")
     probed_at = profile.get("probed_at")
-    catalog_reviewed_at = catalog.get("catalog_reviewed_at")
+    catalog_reviewed_at = catalog.get("last_updated")
 
     profile_age_days = _age_days(str(reviewed_at or ""))
     probe_age_days = _age_days(str(probed_at or ""))
@@ -503,6 +507,19 @@ def _model_freshness() -> Dict[str, Any]:
         reasons.append("probe model does not match active model")
     if active_model_path_state in {"missing", "unknown"}:
         reasons.append("active model path is not readable")
+    declared_files = {
+        entry.get("file")
+        for entry in catalog.get("entries", {}).values()
+        if isinstance(entry, dict) and entry.get("file")
+    }
+    active_model_file = None
+    if active_model_path_exists:
+        try:
+            active_model_file = Path(model_path).resolve(strict=True).name
+        except OSError:
+            active_model_file = Path(model_path).name
+    if active_model_file and active_model_file not in declared_files:
+        reasons.append("active model file is not declared in the runtime catalog")
 
     status_value = "stale" if reasons else "fresh"
     return {
@@ -521,8 +538,11 @@ def _model_freshness() -> Dict[str, Any]:
         "profile_reviewed_at": reviewed_at,
         "probed_at": probed_at,
         "catalog_reviewed_at": catalog_reviewed_at,
-        "catalog_version": catalog.get("catalog_version"),
+        "catalog_version": catalog.get("version"),
+        "active_model_file": active_model_file,
+        "active_model_catalogued": bool(active_model_file and active_model_file in declared_files),
         "profile_path": str(_MODEL_PROFILE_PATH),
+        "catalog_path": str(_MODEL_CATALOG_PATH),
     }
 
 
diff --git a/scripts/testing/test-model-catalog-freshness.py b/scripts/testing/test-model-catalog-freshness.py
index 6529f1896f64e4e238c1ce24da89c263541f99f2..1040765ce89eea5cd99336464f0ba16eb2868eee 100644
--- a/scripts/testing/test-model-catalog-freshness.py
+++ b/scripts/testing/test-model-catalog-freshness.py
@@ -4,19 +4,15 @@
 from __future__ import annotations
 
 import datetime as dt
-import importlib.util
 import json
-import sys
 from pathlib import Path
-from unittest.mock import MagicMock
 
-# Mock psutil to allow dynamic imports of model_catalog on systems without psutil
-sys.modules['psutil'] = MagicMock()
+import yaml
 
 
 ROOT = Path(__file__).resolve().parents[2]
 PROFILE = ROOT / "config" / "model-profile.json"
-CATALOG = ROOT / "ai-stack" / "mcp-servers" / "shared" / "model_catalog.py"
+CATALOG = ROOT / "config" / "model-catalog.yaml"
 MODELS_ROUTE = ROOT / "dashboard" / "backend" / "api" / "routes" / "models.py"
 DASHBOARD_JS = ROOT / "assets" / "dashboard.js"
 
@@ -46,22 +42,36 @@ def main() -> int:
     assert_true(profile.get("probe_model_id") == profile.get("model_id"), "probe_model_id must match model_id")
     assert_true(profile.get("model_path"), "model_path is required")
     assert_true(profile.get("probed_at"), "probed_at is required")
+    assert_true(
+        profile.get("throughput_source") == "live_probe",
+        "model throughput must come from a successful live probe, not a fallback",
+    )
     assert_true(meta.get("reviewed_at"), "_meta.reviewed_at is required")
     assert_true(age_days(meta["reviewed_at"]) <= max_age, "model profile review is stale")
     assert_true(age_days(profile["probed_at"]) <= max_age, "model probe is stale")
 
-    spec = importlib.util.spec_from_file_location("model_catalog", CATALOG)
-    assert_true(spec and spec.loader, "model_catalog import spec should load")
-    module = importlib.util.module_from_spec(spec)
-    spec.loader.exec_module(module)
-    catalog_meta = getattr(module, "CATALOG_METADATA", {})
-    assert_true(catalog_meta.get("catalog_version"), "catalog metadata must expose catalog_version")
-    assert_true(catalog_meta.get("catalog_reviewed_at"), "catalog metadata must expose catalog_reviewed_at")
-    assert_true(age_days(catalog_meta["catalog_reviewed_at"]) <= int(catalog_meta.get("freshness_max_age_days", 0)), "model catalog review is stale")
+    catalog = yaml
=== END ARTIFACT ===

TASK:
Independent security/correctness review of the exact staged patch at /tmp/model-freshness-candidate.patch. Subject SHA-256: c138d32a3e855825f93fa1d50b9151c48b42ac8acc94e3d0a58041b006d6fb65. Review only; do not edit. Verify model_probe never refreshes freshness on failed throughput, live/fallback provenance, runtime catalog SSOT/dashboard truthfulness, active symlink target membership, tests, and regressions. Final nonblank line must be exactly ACCEPTED, REJECTED, or IMPLEMENTED_FOLLOWUP_REQUIRED. Include exact subject hash.

Write your contribution to YOUR OWN file ONLY: .agents/plans/model-freshness-repair-20260926/<AGENT>.md (<AGENT> = codex | local | antigravity). Do NOT edit any shared file. Do NOT read the artifact file (it is inlined above). Be decisive and concise.
