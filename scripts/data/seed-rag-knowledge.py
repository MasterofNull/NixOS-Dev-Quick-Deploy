#!/usr/bin/env python3
"""
scripts/data/seed-rag-knowledge.py

Seed error-solutions, skills-patterns, and best-practices Qdrant collections
with curated content from MEMORY.md, CLAUDE.md, and session history.

Ingestion path:
  embed: POST LLAMA_EMBED_URL/v1/embeddings (bge-m3)
  upsert: PUT QDRANT_URL/collections/{name}/points

Usage:
  python3 scripts/data/seed-rag-knowledge.py [--dry-run] [--collection NAME] [--clear-wrong-type]

Env:
  LLAMA_EMBED_URL   embedding server (default http://127.0.0.1:8081)
  QDRANT_URL        Qdrant (default http://127.0.0.1:6333)
"""

import argparse
import json
import os
import sys
import time
import uuid
import urllib.request
import urllib.error

EMBED_URL  = os.environ.get("LLAMA_EMBED_URL", "http://127.0.0.1:8081")
QDRANT_URL = os.environ.get("QDRANT_URL",      "http://127.0.0.1:6333")
EMBED_MODEL = "bge-m3"

# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

NOW = int(time.time())

ERROR_SOLUTIONS = [
    {
        "error_type": "role_silent_drop",
        "error_message": "role:\"function\" message silently dropped by Qwen3-35B chat template",
        "context": "Qwen3-35B agent loop — tool result injected with role:\"function\" — model never sees tool output, hallucinates on subsequent turns",
        "solution": "Use role:\"tool\" for all tool result messages. Qwen3-35B chat template only recognises role:\"user\"|\"assistant\"|\"tool\". role:\"function\" is silently dropped at template render time.",
        "solution_verified": True,
        "success_count": 3,
        "failure_count": 0,
        "first_seen": NOW - 86400 * 5,
        "last_used": NOW,
        "confidence_score": 0.99,
    },
    {
        "error_type": "mixed_prose_json_parse",
        "error_message": "json.loads() fails when model prepends prose before JSON tool call",
        "context": "parse_tool_call_from_llama — model returns 'Sure! I will call the function. {\"function\":{...}}' — json.loads(full_response) raises JSONDecodeError",
        "solution": "Use rfind('{\"function\"') to extract JSON substring from full response text. Pattern implemented in tool_registry.parse_tool_call_from_llama. Never call json.loads on the raw model output.",
        "solution_verified": True,
        "success_count": 5,
        "failure_count": 0,
        "first_seen": NOW - 86400 * 4,
        "last_used": NOW,
        "confidence_score": 0.98,
    },
    {
        "error_type": "async_blocking_io",
        "error_message": "aiohttp event loop blocked by synchronous file I/O inside async def handler",
        "context": "Any large file read (audit logs 359 MB, JSONL) inside async def aiohttp/FastAPI handler — blocks all concurrent requests for seconds",
        "solution": "Extract I/O to _do_sync() function, call via asyncio.to_thread(_do_sync, ...). Pattern required for ALL coordinator service handlers. Never use open()/readlines() directly in async def.",
        "solution_verified": True,
        "success_count": 4,
        "failure_count": 0,
        "first_seen": NOW - 86400 * 10,
        "last_used": NOW,
        "confidence_score": 0.99,
    },
    {
        "error_type": "flash_attn_flag_consumption",
        "error_message": "llama.cpp --flash-attn bare flag eats next argument as its value",
        "context": "llama-server CLI startup — bare --flash-attn followed by --n-gpu-layers 12 causes n-gpu-layers value to be consumed as flash-attn value, leaving GPU layers at default 0",
        "solution": "Always use explicit value form: --flash-attn on (or off or auto). Never use bare --flash-attn flag. Required for KV q8_0 quantization. Also: --flash-attn [value] is the correct syntax.",
        "solution_verified": True,
        "success_count": 2,
        "failure_count": 0,
        "first_seen": NOW - 86400 * 7,
        "last_used": NOW,
        "confidence_score": 0.97,
    },
    {
        "error_type": "dual_inline_auth_patch_miss",
        "error_message": "Auth bypass after patching only one of two auth sites in http_server.py",
        "context": "http_server.py has _is_loopback_agent_request() at ~line 1412 with its own agent_prefixes tuple independent of core/auth_middleware.py. Adding a loopback endpoint to only one site leaves the other site rejecting requests.",
        "solution": "When adding loopback-allowed endpoints, patch BOTH sites: (1) core/auth_middleware.py and (2) http_server.py _is_loopback_agent_request() ~line 1412. Search for 'agent_prefixes' to find both.",
        "solution_verified": True,
        "success_count": 2,
        "failure_count": 0,
        "first_seen": NOW - 86400 * 6,
        "last_used": NOW,
        "confidence_score": 0.95,
    },
    {
        "error_type": "score_threshold_hardcoded",
        "error_message": "Hardcoded score_threshold=0.7 overrides Config.AI_SEARCH_SCORE_THRESHOLD in HTTP handlers",
        "context": "http_server_impl.py had 3 sites and server.py had 3 wrapper defaults all using score_threshold=0.7 directly. BGE-M3 typical scores are 0.35-0.67 so most collections returned zero results.",
        "solution": "Always use score_threshold=float(data.get('score_threshold', Config.AI_SEARCH_SCORE_THRESHOLD)) in handlers. Config.AI_SEARCH_SCORE_THRESHOLD is set from nix options.nix searchScoreThreshold (default 0.45 for BGE-M3). Never hardcode 0.7.",
        "solution_verified": True,
        "success_count": 1,
        "failure_count": 0,
        "first_seen": NOW - 86400 * 1,
        "last_used": NOW,
        "confidence_score": 0.99,
    },
    {
        "error_type": "continuation_detection_false_positive",
        "error_message": "_looks_like_continuation_query() locks max_collections=1 for any query with prior_memory in context",
        "context": "route_handler.py _looks_like_continuation_query() checked for presence of prior_memory/memory_recall in context dict and returned True — treating ALL queries in sessions with recalled memory as continuations, restricting to 1 collection.",
        "solution": "Remove prior_memory/memory_recall presence check from _looks_like_continuation_query(). That function should only detect continuation from query TEXT patterns (e.g. 'also', 'as mentioned', 'same as before'). Memory recall presence alone does NOT indicate a continuation query.",
        "solution_verified": True,
        "success_count": 1,
        "failure_count": 0,
        "first_seen": NOW - 86400 * 1,
        "last_used": NOW,
        "confidence_score": 0.98,
    },
    {
        "error_type": "qdrant_scroll_limit_zero",
        "error_message": "Qdrant 422: scroll_request.limit: value 0 invalid",
        "context": "search_router.py hybrid search — when mode=semantic, keyword_limit=0 was passed through to Qdrant scroll() as limit=0. Qdrant rejects limit=0 with HTTP 422.",
        "solution": "Guard scroll call: only call Qdrant scroll() if effective_keyword_pool > 0. Pattern: if expanded_tokens and effective_keyword_pool > 0: ... In semantic-only mode skip the keyword scroll entirely.",
        "solution_verified": True,
        "success_count": 1,
        "failure_count": 0,
        "first_seen": NOW - 86400 * 1,
        "last_used": NOW,
        "confidence_score": 0.99,
    },
    {
        "error_type": "nix_store_immutability",
        "error_message": "systemctl restart loads same frozen Nix store code — Python file edits not picked up",
        "context": "ai-hybrid-coordinator runs from /nix/store/<hash>-source/. Editing Python files in the repo and running systemctl restart still loads the OLD store derivation. Changes are invisible until nixos-rebuild switch creates a new derivation.",
        "solution": "Python edits to coordinator code require: (1) nixos-rebuild switch to create new derivation, (2) then systemctl restart ai-hybrid-coordinator. Verify with: grep -n 'changed_pattern' /nix/store/$(readlink /run/current-system | cut -d- -f1...).",
        "solution_verified": True,
        "success_count": 5,
        "failure_count": 0,
        "first_seen": NOW - 86400 * 14,
        "last_used": NOW,
        "confidence_score": 0.99,
    },
    {
        "error_type": "stray_control_chars_regex",
        "error_message": "ASCII \\x08 (backspace) injected by editor corrupts regex patterns silently",
        "context": "Regex patterns pasted from certain editors contain invisible control characters. Pattern appears to compile but never matches expected strings. Discovered during search_router keyword expansion.",
        "solution": "After pasting or writing a regex, verify with a test match: import re; assert re.search(pattern, known_matching_string). Use repr(pattern) to inspect for non-printable chars. Fix by retyping the pattern from scratch.",
        "solution_verified": True,
        "success_count": 1,
        "failure_count": 0,
        "first_seen": NOW - 86400 * 8,
        "last_used": NOW,
        "confidence_score": 0.90,
    },
    {
        "error_type": "enable_thinking_top_level_ignored",
        "error_message": "Top-level enable_thinking:false in llama.cpp request body silently ignored",
        "context": "Qwen3-35B with thinking mode: top-level enable_thinking field in JSON body is silently ignored by llama.cpp. Thinking tokens fill the entire context window leaving empty responses.",
        "solution": "Must be in chat_template_kwargs: {\"enable_thinking\": false} — NOT as a top-level field. Correct form: body={..., \"chat_template_kwargs\": {\"enable_thinking\": false}}. Build via shared/llm_config.py build_llama_payload() which handles this correctly.",
        "solution_verified": True,
        "success_count": 3,
        "failure_count": 0,
        "first_seen": NOW - 86400 * 20,
        "last_used": NOW,
        "confidence_score": 0.99,
    },
    {
        "error_type": "js_fetch_timeout_missing",
        "error_message": "Dashboard JS unbounded fetch blocks entire Promise.allSettled panel load",
        "context": "Dashboard panels using Promise.allSettled where one fetch hangs indefinitely — blocks all panel renders. Pattern from dashboard.js panel fetch without AbortController.",
        "solution": "Every fetch in Promise.allSettled needs AbortController with timeout: const ctrl = new AbortController(); setTimeout(() => ctrl.abort(), 5000); fetch(url, {signal: ctrl.signal}). Apply to ALL dashboard fetch calls.",
        "solution_verified": True,
        "success_count": 2,
        "failure_count": 0,
        "first_seen": NOW - 86400 * 12,
        "last_used": NOW,
        "confidence_score": 0.95,
    },
    {
        "error_type": "dashboard_js_syntax_error",
        "error_message": "Dashboard renders blank screen with no errors in browser network tab",
        "context": "Syntax error in dashboard.js or panel init code (e.g. trailing comma, missing bracket) blocks JS execution before any XHR/fetch is attempted. Network tab appears clean because no requests are made.",
        "solution": "Use chromium --headless=new --enable-logging=stderr --log-level=0 http://127.0.0.1:8889 2>&1 | grep CONSOLE to capture SyntaxError on first paint. --screenshot is useless (first paint precedes data load). Fix the syntax error in dashboard.js.",
        "solution_verified": True,
        "success_count": 3,
        "failure_count": 0,
        "first_seen": NOW - 86400 * 5,
        "last_used": NOW,
        "confidence_score": 0.98,
    },
    {
        "error_type": "coverage_gap_silent_breakage",
        "error_message": "Service or feature breaks in production but all existing tests appear green",
        "context": "New service/feature deployed without aq-qa health check AND dashboard panel. Fails silently with no monitoring or observability. Discovered days later by accident. Seen with ralph-wiggum, aider-wrapper, local_agent_runtime.",
        "solution": "Governance contract: every new feature or service MUST have (1) an aq-qa check entry and (2) a dashboard panel before it is considered 'done'. Both required — one without the other still leaves a blind spot.",
        "solution_verified": True,
        "success_count": 2,
        "failure_count": 0,
        "first_seen": NOW - 86400 * 10,
        "last_used": NOW,
        "confidence_score": 0.95,
    },
    {
        "error_type": "bash_set_e_and_break",
        "error_message": "set -e kills loop when [[ cond ]] && ... && break evaluates false branch",
        "context": "Under set -e, the compound expression [[ cond ]] && cmd1 && break returns exit 1 when cond is false (because && short-circuits), which triggers set -e and kills the enclosing loop or script. Discovered in 4 delegation scripts (bf684853).",
        "solution": "Replace [[ cond ]] && cmd1 && break with if/then/fi form: if [[ cond ]]; then cmd1; break; fi. The if-form always exits 0 regardless of branch taken, so set -e is not triggered.",
        "solution_verified": True,
        "success_count": 4,
        "failure_count": 0,
        "first_seen": NOW - 86400 * 2,
        "last_used": NOW,
        "confidence_score": 0.99,
    },
    {
        "error_type": "psycopg3_row_mapping_silent_failure",
        "error_message": "AttributeError: 'tuple' object has no attribute '_mapping' swallowed silently — psycopg3 rows are plain tuples",
        "context": "psycopg2 row objects had ._mapping for dict conversion. psycopg3 returns plain tuples. dict(row._mapping) raises AttributeError. With bare 'except Exception: return []' this is invisible — every call returns empty results. Hit aq-report read_query_gaps(): 657 rows in DB silently returned as [] for many sessions. psycopg version on this system: 3.2.12.",
        "solution": "Replace dict(row._mapping) with: cols=[d.name for d in cur.description]; rows=[dict(zip(cols,r)) for r in cur.fetchall()]. Or connect with row_factory: psycopg.connect(dsn, row_factory=psycopg.rows.dict_row). Check version: import psycopg; psycopg.__version__.",
        "solution_verified": True,
        "success_count": 1,
        "failure_count": 0,
        "first_seen": NOW - 86400 * 1,
        "last_used": NOW,
        "confidence_score": 0.99,
    },
    {
        "error_type": "training_ingest_quality_score_structured_outputs",
        "error_message": "samples_added=0 every training ingest run — quality score filters all structured/agent responses",
        "context": "training_ingest._quality_score() uses keyword coverage (query terms found in response). Code/structured/agent responses don't repeat query terms so coverage is near 0. is_structured path base was 0.40 — still below DEFAULT_MIN_QUALITY=0.65 for short responses. agent_step_complete events are verified DirectRunner outputs but used same 0.65 floor.",
        "solution": "Raise is_structured base 0.40→0.50. For agent_step_complete events apply floor=0.40 not 0.65: floor = 0.40 if event.get('event_type')=='agent_step_complete' else self.min_quality. These are known-good inference completions; keyword coverage is a poor quality signal for them.",
        "solution_verified": True,
        "success_count": 1,
        "failure_count": 0,
        "first_seen": NOW - 86400 * 1,
        "last_used": NOW,
        "confidence_score": 0.95,
    },
    {
        "error_type": "continue_context_limit",
        "error_message": "Continue agent mode: message exceeds context limit",
        "context": "Continue IDE extension shows 'message exceeds context limit' when the active session JSON in ~/.continue/sessions/ grows past the model's token budget (~8-16k tokens for local model). Diagnosis: check session file size with du -sh ~/.continue/sessions/*.json; identify largest file.",
        "solution": "Compact the session: (1) identify bloated session via du -sh ~/.continue/sessions/*.json, (2) archive session file: mv ~/.continue/sessions/<id>.json .agents/archive/$(date +%Y%m%d)-continue-session.json, (3) restart Continue in IDE. Preventive: keep sessions under 8.0 MiB; aq-report §8a shows Continue session budget health. If recurring: reduce context window in Continue settings (contextLength in config.json).",
        "solution_verified": True,
        "success_count": 2,
        "failure_count": 0,
        "first_seen": NOW - 86400 * 3,
        "last_used": NOW,
        "confidence_score": 0.90,
    },
    {
        "error_type": "scorecard_cache_hit_rate_null",
        "error_message": "effectiveness_scorecard.efficiency_inputs.cache_hit_rate always null",
        "context": "aq-report scorecard efficiency_inputs section reads cache.get('hit_rate') then cache.get('semantic_hit_rate'). The cache dict returned by cache_hit_rate() uses key 'hit_pct' not 'hit_rate'. Result: cache_hit_rate is always null in the scorecard even when the cache section shows 88-89%.",
        "solution": "Use cache.get('hit_rate') or cache.get('semantic_hit_rate') or cache.get('hit_pct'). The embedding_cache_prometheus source returns hit_pct. Always check the actual dict keys when wiring a new scorecard dimension — mismatches are silent.",
        "solution_verified": True,
        "success_count": 1,
        "failure_count": 0,
        "first_seen": NOW - 86400 * 0,
        "last_used": NOW,
        "confidence_score": 0.99,
    },
    {
        "error_type": "eval_score_trend_missing_pass_rate",
        "error_message": "effectiveness_scorecard.outcome_correctness.eval_pass_rate always null",
        "context": "eval_score_trend() in aq-report returned latest_pct/mean_pct (0-100 scale) but not pass_rate/recent_pass_rate (0.0-1.0 scale). The effectiveness scorecard reads eval_trend.get('recent_pass_rate') which was always None. RAGAS fallback path had same gap.",
        "solution": "Add pass_rate = round(pcts[-1] / 100.0, 3) and recent_pass_rate = round(pcts[-1] / 100.0, 3) to BOTH return paths in eval_score_trend(). The scorecard consumer uses 0.0-1.0 scale. Also add RAGAS fallback: fetch /eval/trend from coordinator when scores.sqlite is stale (>7 days) and no tool_audit entries.",
        "solution_verified": True,
        "success_count": 1,
        "failure_count": 0,
        "first_seen": NOW - 86400 * 1,
        "last_used": NOW,
        "confidence_score": 0.99,
    },
    {
        "error_type": "nvd_sync_wrong_service_name",
        "error_message": "nvd-sync starts before AIDB — connection refused on boot",
        "context": "nvd-sync.nix had after=[\"aidb-mcp-server.service\"] which is a nonexistent unit name. The actual AIDB service is ai-aidb.service. systemd silently ignores after= entries for units that don't exist (only requires/wants cause failures for missing units). nvd-sync fires immediately after network-online, before AIDB is ready.",
        "solution": "Change after and wants to ai-aidb.service. Verify unit names with systemctl status before adding to after/wants — nonexistent names are silently ignored. Also bump OnBootSec as belt-and-suspenders (5min→10min). File: nix/modules/services/nvd-sync.nix.",
        "solution_verified": True,
        "success_count": 1,
        "failure_count": 0,
        "first_seen": NOW - 86400 * 1,
        "last_used": NOW,
        "confidence_score": 0.99,
    },
    {
        "error_type": "waste_bucket_payload_classification",
        "error_message": "aq-report waste_buckets all null — cannot classify token waste",
        "context": "_emit_token_event() in ai_coordinator_handlers.py did not include a payload dict with waste bucket classification. aq-report reads payload.rejected_output and payload.failed_retries from token_usage events but these keys were absent. Result: waste_buckets section showed all null despite active delegation failures.",
        "solution": "Add waste bucket variables before _emit_token_event call: _are_rejected = _are_tok_out if (_are_ok and _are_quality_available and not _are_quality_passed and _are_tok_out > 0) else None; _are_failed_retry = _are_total if (not _are_ok and _are_total > 0) else None. Pass as payload={\"rejected_output\": _rejected, \"failed_retries\": _failed_retry} to make_event(). Requires nixos-rebuild to deploy.",
        "solution_verified": True,
        "success_count": 1,
        "failure_count": 0,
        "first_seen": NOW - 86400 * 0,
        "last_used": NOW,
        "confidence_score": 0.97,
    },
    {
        "error_type": "delegation_feedback_outcome_null",
        "error_message": "delegation-feedback.jsonl: outcome=null for all records",
        "context": "record_delegation_feedback() in delegation_feedback.py built the payload dict without an 'outcome' key. All 300+ entries had outcome=null, breaking discovery_agent trust scoring and aq-report success-rate scorecard.",
        "solution": "Add 'outcome': 'failed' if classification.get('is_failure') else 'error' to the payload dict in record_delegation_feedback(). Since the function only records failures (guarded by is_failure check), all records get 'failed'.",
        "solution_verified": True,
        "success_count": 1,
        "failure_count": 0,
        "first_seen": NOW,
        "last_used": NOW,
        "confidence_score": 0.99,
    },
    {
        "error_type": "delegation_feedback_contract_false_positive",
        "error_message": "120 spurious json_contract_failed events per 300 delegation records",
        "context": "delegation_prompt_contract_signals() scanned task + ALL messages including system prompts. System prompts contain 'json' + 'only'/'valid'/'strict', so expects_json=True triggered for nearly every request. Tasks like 'Reply PONG' were classified as json_contract_failed.",
        "solution": "Narrow contract detection to task text only: task_lower = task.lower(); expects_json = 'json' in task_lower and any(token in task_lower for ...). Same fix for expects_short_exact. System prompt content must never influence task-level contract classification.",
        "solution_verified": True,
        "success_count": 1,
        "failure_count": 0,
        "first_seen": NOW,
        "last_used": NOW,
        "confidence_score": 0.99,
    },
    {
        "error_type": "discovery_agent_trust_score_wrong_source",
        "error_message": "All discovery candidates get trust_score=0.20 (unknown) instead of source-appropriate score",
        "context": "discovery_agent.py scanners set 'category' but not 'source'. trust_scoring.py falls back to category when source is absent. 'delegation-quality' category doesn't prefix-match 'delegation-feedback' key, so all delegation candidates got 0.20 instead of 0.80.",
        "solution": "Each scanner must explicitly set 'source': issues-backlog→'issues-backlog', health-spider→'health-spider', delegation_feedback→'delegation-feedback', model-profile→'model-profile'. Also use overwrite=True in discovery runs so stale cached trust scores (from previous incorrect source) get recalculated.",
        "solution_verified": True,
        "success_count": 1,
        "failure_count": 0,
        "first_seen": NOW,
        "last_used": NOW,
        "confidence_score": 0.97,
    },
    # Phase 157 patterns
    {
        "error_type": "harness_paths_module_level_constant_breaks_test_injection",
        "error_message": "discovery_agent uses module-level PATH constant from harness_paths, ignoring self.repo_root injected by test",
        "context": "harness_paths.py introduced module-level constants MODEL_PROFILE and ISSUES_BACKLOG. Scanner methods (like _scan_model_profile_freshness) used those constants instead of self.repo_root. Tests write synthetic profiles to a tmpdir repo_root — the module constant always resolved to the production path.",
        "solution": "Use self.repo_root-relative path inside scanner methods. Only use harness_paths constants for __init__ defaults (delegation_feedback_path, output_path). Any scanner that respects constructor injection must derive paths from self.repo_root, not module globals.",
        "solution_verified": True,
        "success_count": 1,
        "failure_count": 0,
        "first_seen": NOW,
        "last_used": NOW,
        "confidence_score": 0.97,
        "files": ["ai-stack/local-agents/discovery_agent.py", "ai-stack/local-agents/harness_paths.py"],
        "related_patterns": ["repo_root_override", "test_isolation", "module_constant_vs_instance_attribute"],
    },
    {
        "error_type": "eval_sandbox_category_allowlist_diverges_from_trust_scoring",
        "error_message": "eval_sandbox marks sandbox_pass=False for unknown category even when trust_scoring accepts it",
        "context": "eval_sandbox.py imports _CATEGORY_RELEVANCE from trust_scoring.py to validate candidate categories. When a new category (system-fix, health-spider) is added to discovery_agent scanners but not yet added to trust_scoring._CATEGORY_RELEVANCE, eval_sandbox flags all candidates of that category as violations (sandbox_pass=False). This blocked 3 issues-backlog candidates from progressing.",
        "solution": "Always update trust_scoring._CATEGORY_RELEVANCE before deploying a new scanner category. The allowlist is the contract between discovery and evaluation. eval_sandbox derives its allowlist directly from trust_scoring — one edit location controls both.",
        "solution_verified": True,
        "success_count": 1,
        "failure_count": 0,
        "first_seen": NOW,
        "last_used": NOW,
        "confidence_score": 0.97,
        "files": ["ai-stack/local-agents/eval_sandbox.py", "ai-stack/local-agents/trust_scoring.py"],
    },
    {
        "error_type": "candidate_lifecycle_concurrent_save_race_condition",
        "error_message": "concurrent load() → transition() → save() sequences overwrite each other (lost updates) with no file lock",
        "context": "CandidateLifecycleManager.save() wrote directly to candidates.json without any cross-process synchronization. When multiple processes (aq-review CLI, discovery_agent, training_ingest) run concurrently, the last save wins and all intermediate state is lost.",
        "solution": "Use fcntl.flock(LOCK_EX) on a companion .lock file during the read-existing-wrapper + atomic-replace cycle. AppArmor profile for the service needs 'k' (file_lock) on the .lock path. portalocker is not available in this NixOS environment; use fcntl directly.",
        "solution_verified": True,
        "success_count": 1,
        "failure_count": 0,
        "first_seen": NOW,
        "last_used": NOW,
        "confidence_score": 0.97,
        "files": ["ai-stack/local-agents/candidate_lifecycle.py"],
        "related_patterns": ["apparmor_k_mode_required_for_fcntl_flock", "atomic_replace_tmp_file"],
    },
    # Phase 158 patterns
    {
        "error_type": "cross_model_critique_stale_aidb_url_import",
        "error_message": "cross_model_critique.py imports AIDB_URL from harness_paths, but harness_paths never defines it — ImportError forces wrong CRITIQUE_SPOOL fallback path",
        "context": "harness_paths.py defines CRITIQUE_SPOOL but not AIDB_URL. cross_model_critique.py tried 'from harness_paths import CRITIQUE_SPOOL, AIDB_URL as _AIDB_URL_DEFAULT'. The ImportError fell through to the fallback which derived CRITIQUE_SPOOL from cwd instead of repo root. Under service-user context switches this silently spooled critiques to the wrong directory.",
        "solution": "Import only CRITIQUE_SPOOL from harness_paths. Resolve AIDB_URL independently from os.environ with a hardcoded default: _AIDB_URL = os.environ.get('AIDB_URL', 'http://127.0.0.1:8002'). Never couple AIDB_URL resolution to the path SSOT module.",
        "solution_verified": True,
        "success_count": 1,
        "failure_count": 0,
        "first_seen": NOW,
        "last_used": NOW,
        "confidence_score": 0.97,
        "files": ["ai-stack/local-agents/cross_model_critique.py", "ai-stack/local-agents/harness_paths.py"],
        "related_patterns": ["harness_paths_import_contract", "service_user_spool_path"],
    },
    {
        "error_type": "routing_token_estimate_4chars_coarse_for_structured_payloads",
        "error_message": "_classify_routing_intent estimates 1 token = 4 chars, undercounting JSON/code/tool-schema payloads by 2-3x",
        "context": "switchboard.py _classify_routing_intent uses total_chars // 4 as token estimate for hard local-limit checks. This approximation is acceptable for natural-language prose but severely undercounts JSON, code, punctuation-heavy content, and chat-serialization overhead (role/content keys appear thousands of times in long agent loops). A 16k-char JSON payload estimates 4000 tokens but may be 8000-12000 actual tokens.",
        "solution": "Use the estimate only as a coarse overflow guard with a conservative safety margin (e.g. 50% of actual limit). For precise routing, use the same tokenizer/budget accounting used by the active backend. Always document that this is a rough heuristic, not a hard capacity check. Add unit tests for mixed-content payloads.",
        "solution_verified": False,
        "success_count": 0,
        "failure_count": 1,
        "first_seen": NOW,
        "last_used": NOW,
        "confidence_score": 0.80,
        "files": ["ai-stack/switchboard/switchboard.py"],
        "related_patterns": ["frequency_penalty_truncates_dense_json", "local_delegate_504_token_budget_too_large"],
    },
    {
        "error_type": "local_agent_wrong_qdrant_collection_returns_noise",
        "error_message": "Local agent queries collection=solved_issues expecting error patterns but gets MCP-registry catalog noise",
        "context": "During Qwen3-35B self-improvement loop, the agent was prompted to search error-solutions collection but defaulted to or was told to search solved_issues. solved_issues contains MCP registry catalog entries (irrelevant). error-solutions is the seeded collection with 319 harness-specific error patterns. Distance scores >0.95 indicate effectively random matches.",
        "solution": "Always specify collection=error-solutions explicitly in delegation prompts for error/bug pattern lookups. Update LOCAL-AGENT.md AIDB section: add collection routing table (error-solutions for bug patterns, best-practices for skills, skills-patterns for agent workflows). Never use solved_issues for harness error queries.",
        "solution_verified": True,
        "success_count": 1,
        "failure_count": 0,
        "first_seen": NOW,
        "last_used": NOW,
        "confidence_score": 0.95,
        "files": [".agent/LOCAL-AGENT.md", "scripts/data/seed-rag-knowledge.py"],
        "related_patterns": ["score_threshold_hardcoded", "rag_collection_empty_silent_zero_results"],
    },
    # Phase 159 patterns
    {
        "error_type": "agent_executor_synthesis_truncated_at_512",
        "error_message": "Local agent result=null, status=failed after successful tool calls — synthesis cut off",
        "context": "agent_executor._call_llama() used AGENT_TOOL_CALL_MAX_TOKENS=512 for ALL model calls including final synthesis. After 4 successful tool calls, the synthesis response generating JSON candidates was truncated at 512 tokens → model returned empty/incomplete → result=null, status=failed.",
        "solution": "Two-phase token budget: AGENT_TOOL_CALL_MAX_TOKENS=512 for first call (tool_call_count==0), AGENT_TASK_MAX_TOKENS=1200 for post-tool calls (tool_call_count>0). Added max_tokens parameter to _call_llama(). Import AGENT_TASK_MAX_TOKENS from shared.llm_config alongside AGENT_TOOL_CALL_MAX_TOKENS.",
        "solution_verified": True,
        "success_count": 3,
        "failure_count": 0,
        "first_seen": NOW,
        "last_used": NOW,
        "confidence_score": 0.98,
        "files": ["ai-stack/local-agents/agent_executor.py", "ai-stack/mcp-servers/shared/llm_config.py"],
        "related_patterns": ["frequency_penalty_truncates_dense_json"],
    },
    {
        "error_type": "agent_loop_context_overflow_8192",
        "error_message": "llama.cpp error: request (N tokens) exceeds available context size (8192 tokens)",
        "context": "Local agent loop accumulates tool call history in messages list. Large tool results (file reads, shell output) + multi-turn exchanges push total tokens past n_ctx=8192. Error occurs on the 5th+ tool call when history exceeds context window.",
        "solution": "Two defences: (1) format_tool_result() caps raw result at 3000 chars (~750 tok) with truncation notice. (2) _execute_with_tools() per-iteration context guard: when total message chars > (8192-2000)*4=24768, drops oldest assistant+tool message pair (indices 2+3). System message and user task always preserved.",
        "solution_verified": True,
        "success_count": 2,
        "failure_count": 0,
        "first_seen": NOW,
        "last_used": NOW,
        "confidence_score": 0.97,
        "files": ["ai-stack/local-agents/agent_executor.py", "ai-stack/local-agents/tool_registry.py"],
        "related_patterns": ["agent_executor_synthesis_truncated_at_512"],
    },
]

SKILLS_PATTERNS = [
    {
        "skill_name": "nixos_coordinator_deploy",
        "description": "Deploy Python changes to ai-hybrid-coordinator in NixOS",
        "usage_pattern": "Edit Python files in repo → nixos-rebuild switch (requires sudo in terminal, not Claude shell) → systemctl restart ai-hybrid-coordinator → verify with systemctl status + grep -n in /nix/store",
        "success_examples": [
            "Phase 73: route_handler.py continuation fix deployed via nixos-rebuild switch + restart",
            "Phase 74: score_threshold fix deployed same pattern — verified with env var check",
        ],
        "failure_examples": [
            "systemctl restart only — picks up old Nix store derivation, edits invisible",
            "Checking running code by reading repo files — repo ≠ running code until rebuild",
        ],
        "prerequisites": ["NixOS system", "sudo access in terminal (not Claude shell)"],
        "related_skills": ["nix_flake_build", "apparmor_enforce"],
        "value_score": 0.95,
        "last_updated": NOW,
    },
    {
        "skill_name": "bge_m3_score_calibration",
        "description": "Calibrate BGE-M3 semantic similarity threshold for Qdrant collections",
        "usage_pattern": "1) Embed test query via POST :8081/v1/embeddings 2) Direct Qdrant query per collection via POST :6333/collections/{name}/points/query 3) Record top scores per collection 4) Set threshold 5-10% below lowest legitimate collection max",
        "success_examples": [
            "2026-05-28: measured error-solutions max=0.444 skills-patterns max=0.408 → set threshold 0.45 in options.nix",
            "Revealed content sparsity issue: error-solutions/skills-patterns scoring 0.34-0.36 on typical queries",
        ],
        "failure_examples": [
            "Using semantic cache during calibration — stale zero results mask real scores, use enable_cache=false",
            "Testing only 1 collection — always test all 5 RAG collections in one pass",
        ],
        "prerequisites": ["LLAMA_EMBED server :8081 running", "Qdrant :6333 accessible"],
        "related_skills": ["qdrant_direct_query", "semantic_search_debug"],
        "value_score": 0.88,
        "last_updated": NOW,
    },
    {
        "skill_name": "agent_role_injection",
        "description": "Wire agent roles through the full local inference chain",
        "usage_pattern": "Use build_llama_payload(role=role_str) from shared/llm_config.py — injects role via system message ROLE_SYSTEM_PROMPTS dict. Valid values: orchestrator|architect|implementer|reviewer. All 4 scripts (aq-agent-loop, delegate-to-local, delegate-to-gemini, delegate-fanout) have --role flag.",
        "success_examples": [
            "Phase 73: Task.role + AGENT_TYPE_DEFAULT_ROLE mapping wired through agent_executor.py",
            "Phase 74: DirectRunner uses build_llama_payload(role=) — role in system message not text prefix",
        ],
        "failure_examples": [
            "Using [ROLE: X] text prefix in user message — inconsistent, model ignores prefix",
            "Passing role as top-level JSON field — llama.cpp ignores unknown fields",
        ],
        "prerequisites": ["shared/llm_config.py ROLE_SYSTEM_PROMPTS dict populated", "build_llama_payload() imported"],
        "related_skills": ["local_agent_dispatch", "llama_payload_builder"],
        "value_score": 0.90,
        "last_updated": NOW,
    },
    {
        "skill_name": "apparmor_profile_iteration",
        "description": "Iterate AppArmor profiles from complain → enforce without kernel denials",
        "usage_pattern": "1) complain mode first 2) run workloads 3) check journalctl -k -g apparmor 4) add missing paths/caps to profile 5) nixos-rebuild switch 6) enforce mode 7) verify 0 denials",
        "success_examples": [
            "Phase 66.3/67: hwmon* (not hwmon/**/) pattern, k mode for fcntl locks, a and w mutually exclusive",
            "2026-05-28: 67/67 QA pass after enforce with zero kernel denials",
        ],
        "failure_examples": [
            "c mode in AppArmor profile — invalid, use r+x or rx",
            "a and w simultaneously — mutually exclusive in AppArmor",
            "hwmon/**/ — wrong wildcard; use hwmon* for /sys/class/hwmon*",
        ],
        "prerequisites": ["AppArmor kernel module", "nixos-rebuild access", "journalctl -k access"],
        "related_skills": ["nixos_coordinator_deploy", "kernel_security"],
        "value_score": 0.85,
        "last_updated": NOW,
    },
    {
        "skill_name": "dashboard_js_debug",
        "description": "Debug JavaScript errors in the AI stack dashboard",
        "usage_pattern": "chromium --headless=new --enable-logging=stderr --log-level=0 http://127.0.0.1:8889 2>&1 | grep CONSOLE — captures SyntaxErrors and fetch failures on first paint before XHR. --screenshot is useless (first paint before data loads).",
        "success_examples": [
            "Phase 68.4: caught SyntaxError in panel init before data rendered",
            "Identified missing AbortController causing 30s panel freeze",
        ],
        "failure_examples": [
            "chromium --screenshot — page first paint has no data yet, screenshot is blank",
            "curl the dashboard HTML — JS errors only surface in a real browser context",
        ],
        "prerequisites": ["chromium installed", "dashboard service running on :8889"],
        "related_skills": ["frontend_debug", "async_fetch_patterns"],
        "value_score": 0.82,
        "last_updated": NOW,
    },
    {
        "skill_name": "agent_workflow_phases",
        "description": "Phases of an agent workflow session: orient, research, plan, execute, validate, doc, commit",
        "usage_pattern": "8-step canonical workflow: (1) ORIENT — aq-prime + aq-session-start + aq-qa 0. (2) RESEARCH — agrep/als/acat; never guess paths. (3) PRD/PLAN — write .agents/plans/ doc before coding. (4) MEMORY CHECKPOINT — store plan + write PENDING.json. (5) EXECUTE — one slice, one concern, PULSE.log after each write. (6) VALIDATE — live test + tier0-validation-gate.sh. (7) DOC-UPDATE — HANDOFF.md + agent .md files. (8) COMMIT — git add specific files + tier0 gate + conventional commit with Co-Authored-By.",
        "success_examples": [
            "Phase 94 — each of 94.1-94.4 followed orient→execute→validate→commit exactly",
            "Phase 89.2 — plan written in .agents/plans/ before any file edit; gate passed before commit",
        ],
        "failure_examples": [
            "Coding without a written plan (violates PRD GATE rule) — commit rejected by reviewer",
            "Skipping VALIDATE step — runtime error found in production instead of pre-commit",
        ],
        "prerequisites": ["aq-prime run", "RESUME.json current"],
        "related_skills": ["multi-agent-collab", "context-efficiency"],
        "value_score": 0.92,
        "last_updated": NOW,
    },
    {
        "skill_name": "tool_call_representation",
        "description": "How a tool-call in an LLM agent is represented: name, input parameters, and output",
        "usage_pattern": "Tool call structure in llama.cpp/OpenAI-compatible agents: (1) model emits JSON with keys 'function' → {name: str, arguments: dict}. (2) Host extracts call via rfind('{\"function\"') to strip prose preamble. (3) Host executes tool, wraps result in role:'tool' message (NOT role:'function' — silently dropped). (4) Result injected into conversation as {role:'tool', content:str(result)}. (5) Next model turn sees tool result and continues. Field names: OpenAI uses 'tool_calls'[].function.{name,arguments}; llama.cpp native uses top-level 'function':{name,arguments}.",
        "success_examples": [
            "tool_registry.parse_tool_call_from_llama: rfind('{\"function\"') extracts from prose-wrapped output",
            "Agent loop: role='tool' for results, role='assistant' for model output, role='user' for inputs",
        ],
        "failure_examples": [
            "json.loads(full_response) — fails when model prepends prose before JSON call",
            "role:'function' for tool result — silently dropped by Qwen3 chat template",
        ],
        "prerequisites": ["llama.cpp or OpenAI-compatible inference endpoint"],
        "related_skills": ["agent_role_injection", "local_agent_dispatch"],
        "value_score": 0.90,
        "last_updated": NOW,
    },
]

BEST_PRACTICES = [
    {
        "category": "nixos_architecture",
        "title": "Port SSOT — never hardcode in Python or shell",
        "description": "All service ports are declared as NixOS options in nix/modules/core/options.nix and injected as environment variables. Current defaults: llama.cpp=8080, llama-embed=8081, AIDB=8002, hybrid-coordinator=8003, switchboard=8085, cli-bridge=8089, dashboard=8889. Python reads via os.environ; shell scripts use ${PORT:-default}.",
        "examples": [
            "Python: LLAMA_CPP_URL = os.environ.get('LLAMA_CPP_URL', 'http://127.0.0.1:8080')",
            "Shell: COORD_URL=${HYBRID_COORDINATOR_URL:-http://127.0.0.1:8003}",
        ],
        "anti_patterns": [
            "Hardcoding port 8003 directly in Python — breaks when port changes in options.nix",
            "Using a different port in tests vs production — always read from env",
        ],
        "references": ["nix/modules/core/options.nix", "config/service-endpoints.sh"],
        "endorsement_count": 5,
        "last_validated": NOW,
    },
    {
        "category": "llama_cpp_config",
        "title": "GPU layers ceiling: 12 for Renoir APU (4 GB shared VRAM)",
        "description": "The P14s AMD AI workstation uses a Renoir APU with 4 GB shared VRAM. Maximum n_gpu_layers is 12. Total usable RAM: 27 GB (22.5 GB model + 1.0 GB KV + 3.0 GB OS reserve). Never suggest n_gpu_layers > 12. Active model: Qwen3.6-35B-MTP Q5 at ~22.5 GB.",
        "examples": [
            "extraArgs = [\"--threads\" \"4\" \"--n-gpu-layers\" \"12\" \"--parallel\" \"4\"]",
            "KV cache q8_0 requires --flash-attn on (explicit value required)",
        ],
        "anti_patterns": [
            "n_gpu_layers = 20 — exceeds VRAM, falls back to CPU for those layers with OOM risk",
            "bare --flash-attn flag — eats next arg as value, see error-solutions entry",
        ],
        "references": ["nix/hosts/hyperd/facts.nix", "nix/modules/core/options.nix"],
        "endorsement_count": 4,
        "last_validated": NOW,
    },
    {
        "category": "service_restart",
        "title": "When to restart vs rebuild: coordinator vs dashboard vs switchboard",
        "description": "Different services have different hot-reload behaviour. Dashboard backend: WorkingDirectory=repo, Python edits in repo are picked up on systemctl restart (no rebuild needed for existing routes; new routes require restart). Coordinator/llama-cpp: Nix store frozen — Python edits REQUIRE nixos-rebuild switch + restart. Switchboard: uses print(stderr) not logging module.",
        "examples": [
            "Dashboard route change: edit dashboard/backend/api/routes/*.py → systemctl restart ai-dashboard",
            "Coordinator Python change: edit ai-stack/mcp-servers/hybrid-coordinator/*.py → nixos-rebuild switch → systemctl restart ai-hybrid-coordinator",
        ],
        "anti_patterns": [
            "systemctl restart ai-hybrid-coordinator after repo edit — loads old Nix store code",
            "nixos-rebuild for dashboard-only changes — unnecessary, adds 2-3 min overhead",
        ],
        "references": ["CLAUDE.md architecture constraints", "nix/modules/roles/ai-stack.nix"],
        "endorsement_count": 5,
        "last_validated": NOW,
    },
    {
        "category": "agent_architecture",
        "title": "Multi-agent role assignment: orchestrator/architect/implementer/reviewer",
        "description": "Four canonical roles defined in docs/architecture/role-matrix.md. Orchestrator: opens/closes sessions, assigns slices, commits. Architect: design/risk, drafts PRDs. Implementer: bounded execution within assigned slice. Reviewer: pass/fail verdict, never reviews own work. Sub-agents may not re-scope goals or route other agents.",
        "examples": [
            "delegate-to-gemini --role architect -- 'Review schema design for error-solutions collection'",
            "delegate-to-local --role implementer -- 'Implement seed script for skills-patterns'",
        ],
        "anti_patterns": [
            "Implementer self-promoting to reviewer — always separate review from implementation",
            "Orchestrator doing all implementation directly — defeats mesh collaboration benefits",
        ],
        "references": ["docs/architecture/role-matrix.md", "AGENTS.md", ".agent/LOCAL-AGENT.md"],
        "endorsement_count": 3,
        "last_validated": NOW,
    },
    {
        "category": "rag_retrieval",
        "title": "BGE-M3 score threshold calibration: 0.45 baseline for 5-collection RAG",
        "description": "BGE-M3 (embed-bge-m3-Q8_0, 1024-dim, CLS pooling) typical score ranges across AIDB collections: knowledge 0.62-0.67, codebase-context 0.48-0.58, best-practices 0.34-0.63, error-solutions 0.34-0.44, skills-patterns 0.35-0.41. Threshold 0.45 captures knowledge+codebase-context reliably. Collections scoring below 0.45 indicate content sparsity/type mismatch — fix the content, not the threshold.",
        "examples": [
            "options.nix: searchScoreThreshold default = 0.45 (calibrated 2026-05-28)",
            "Direct calibration: POST :8081/v1/embeddings then POST :6333/collections/{name}/points/query",
        ],
        "anti_patterns": [
            "Lowering threshold to 0.30 to 'fix' empty collections — surfaces noise/irrelevant chunks",
            "Hardcoding score_threshold in handlers instead of reading Config.AI_SEARCH_SCORE_THRESHOLD",
        ],
        "references": ["nix/modules/core/options.nix searchScoreThreshold", "ai-stack/mcp-servers/hybrid-coordinator/knowledge/search_router.py"],
        "endorsement_count": 2,
        "last_validated": NOW,
    },
    {
        "category": "commit_discipline",
        "title": "Mandatory commit sequence: validate → commit with Co-Authored-By",
        "description": "Every commit requires: (1) git add <specific files>, (2) scripts/governance/tier0-validation-gate.sh --pre-commit, (3) git commit with type(scope): description format plus Co-Authored-By: <agent> <noreply@anthropic.com>. Never use git add -A (may include .env/secrets). Never --no-verify.",
        "examples": [
            "git commit -m 'fix(search): lower BGE-M3 score threshold 0.55→0.45\\n\\nCo-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>'",
            "scripts/governance/tier0-validation-gate.sh --pre-commit  # must pass before every commit",
        ],
        "anti_patterns": [
            "git add . or git add -A — risks committing secrets or large binaries",
            "Skipping tier0-validation-gate.sh — required governance gate, never bypass",
        ],
        "references": ["CLAUDE.md commit discipline", "scripts/governance/tier0-validation-gate.sh"],
        "endorsement_count": 5,
        "last_validated": NOW,
    },
    {
        "category": "coordinator_api",
        "title": "Coordinator HTTP API: authentication and core endpoints",
        "description": "Coordinator runs on port 8003 (HYBRID_COORDINATOR_URL env var). Authentication: X-API-Key header with value from /run/secrets/hybrid_coordinator_api_key. Loopback requests (127.0.0.1) checked via _is_loopback_agent_request() in http_server.py AND auth_middleware.py — patch BOTH if adding loopback exemptions. Key endpoints: POST /workflow/plan (planning), POST /workflow/run/start (execution), GET /stats/delegate (delegation rate), GET /status (health), POST /hybrid_search (RAG).",
        "examples": [
            "API_KEY=$(cat /run/secrets/hybrid_coordinator_api_key); curl -H 'X-API-Key: $API_KEY' http://localhost:8003/status",
            "POST /workflow/plan — body: {\"query\": \"...\", \"context\": {...}} → returns plan JSON",
        ],
        "anti_patterns": [
            "Hardcoding http://127.0.0.1:8003 instead of reading HYBRID_COORDINATOR_URL env var",
            "Patching only auth_middleware.py for loopback — http_server.py has a second auth check at ~line 1412",
        ],
        "references": ["ai-stack/mcp-servers/hybrid-coordinator/http_server_impl.py", "ai-stack/mcp-servers/hybrid-coordinator/core/status_service.py"],
        "endorsement_count": 3,
        "last_validated": NOW,
    },
    {
        "category": "multi_agent_collaboration",
        "title": "RESUME.json and HANDOFF.md: agent state handoff protocol",
        "description": "RESUME.json at .agent/collaboration/RESUME.json is the compaction anchor — write it on new task start AND after each completed todo. Fields: current_objective (str), phase (str), todo_snapshot (list of {id, text, status}), uncommitted_changes (list of file paths), resume_hint (str). HANDOFF.md is the human-readable status memo — update at each phase completion. aq-resume reads RESUME.json first on session start.",
        "examples": [
            "RESUME.json todo_snapshot: [{\"id\":\"1\",\"text\":\"Add failure_reason field\",\"status\":\"done\"}, ...]",
            "aq-resume on session start — outputs last objective, phase, todos, uncommitted changes",
        ],
        "anti_patterns": [
            "Skipping RESUME.json update after completing a todo — breaks context recovery after compaction",
            "Writing full file contents into RESUME.json — use file paths, not contents",
        ],
        "references": [".agent/collaboration/RESUME.json", ".agent/collaboration/HANDOFF.md", "CLAUDE.md §8b"],
        "endorsement_count": 4,
        "last_validated": NOW,
    },
    {
        "category": "llama_cpp_config",
        "title": "Local LLM request config: enable_thinking and token ceilings",
        "description": "For Qwen3-35B (llama.cpp port 8080): enable_thinking MUST be false and placed in chat_template_kwargs, NOT at the top level. Top-level enable_thinking is silently ignored; placing it only in chat_template_kwargs is required. Token ceiling: local delegate max_tokens hard ceiling = 180 (Qwen3 at ~1 tok/s floor, 300s timeout). Context window safe zone: <8192 tokens. Stop tokens: use <|im_end|> in chat template. Minimum timeout for local calls: 300s.",
        "examples": [
            "payload = {\"messages\": [...], \"chat_template_kwargs\": {\"enable_thinking\": false}, \"max_tokens\": 180}",
            "_LOCAL_MAX_TOKENS_HARD_CEILING = 180  # 180s budget at 1 tok/s floor",
        ],
        "anti_patterns": [
            "{\"enable_thinking\": false, \"messages\": [...]} — top-level silently ignored by llama.cpp",
            "max_tokens > 256 for local delegate — causes 504 at 211s when model generates slowly",
        ],
        "references": [".agent/LOCAL-AGENT.md", "ai-stack/mcp-servers/hybrid-coordinator/http_server_impl.py"],
        "endorsement_count": 5,
        "last_validated": NOW,
    },
    {
        "category": "python_async",
        "title": "aiohttp/FastAPI async patterns: to_thread, switchboard logging, MLFQ tasks",
        "description": "Three critical patterns: (1) All synchronous file I/O inside async def handlers must use asyncio.to_thread(sync_fn, ...) — never open()/readlines() directly. (2) switchboard.py uses print(..., file=sys.stderr) NOT logging.getLogger() — inject logging module causes protocol errors. (3) Background MLFQ tasks spawned via asyncio.create_task() must be stored in a set and discarded on completion to avoid dangling tasks during graceful shutdown.",
        "examples": [
            "result = await asyncio.to_thread(_read_file_sync, path)  # correct pattern",
            "print(json.dumps(response), file=sys.stderr)  # switchboard stdout is the protocol channel",
        ],
        "anti_patterns": [
            "async def handler(): data = open(audit_log).read()  # blocks event loop",
            "import logging; logging.info(msg) in switchboard.py  # corrupts MCP protocol stdout",
        ],
        "references": ["ai-stack/mcp-servers/hybrid-coordinator/core/status_service.py", "CLAUDE.md bug patterns"],
        "endorsement_count": 4,
        "last_validated": NOW,
    },
    {
        "category": "rag_operations",
        "title": "AIDB RAG operations: search thresholds, schema differences, test teardown",
        "description": "AIDB runs on port 8002. Hybrid search via coordinator (port 8003) POST /hybrid_search with X-API-Key header. Score thresholds: search=0.45, retrieval=0.50. Schema: memory insert uses {content, metadata, collection} while skill retrieval uses {query, collection, limit} — different payloads. For test teardown: use the collection-specific clear endpoint, NEVER wipe global knowledge collections (skills-patterns, best-practices, error-solutions). Always seed collections before testing retrieval quality.",
        "examples": [
            "Search: POST :8003/hybrid_search {\"query\":\"...\",\"collection\":\"best-practices\",\"limit\":5,\"score_threshold\":0.45}",
            "Memory insert: POST :8002/api/memory {\"content\":\"...\",\"metadata\":{\"type\":\"lesson\"}}",
        ],
        "anti_patterns": [
            "Deleting all points from error-solutions during test teardown — wipes production knowledge",
            "score_threshold=0.7 — too high for sparse collections; 0.45 is the calibrated default",
        ],
        "references": ["ai-stack/mcp-servers/hybrid-coordinator/knowledge/search_router.py", "nix/modules/core/options.nix"],
        "endorsement_count": 3,
        "last_validated": NOW,
    },
    {
        "category": "context_efficiency",
        "title": "Sub-agent context slicing and PULSE.log/RESUME.json compaction rules",
        "description": "Sub-agents must receive only slice-relevant context — not full session history. Pass: (1) the slice objective, (2) relevant file paths (not content), (3) skill names to load on demand. PULSE.log is gitignored (append-only, runtime log) — never commit it. RESUME.json should be committed after each phase. Compact aggressively: when approaching context limits, summarize prior phases to 1-line pointers in MEMORY.md. Full MEMORY.md hard limit = 150 lines.",
        "examples": [
            "Sub-agent prompt: 'Implement slice 90.2. Files to edit: http_server_impl.py. Skill: coordinator-api'",
            "RESUME.json on compact: update current_objective + todo_snapshot, keep uncommitted_changes accurate",
        ],
        "anti_patterns": [
            "Passing full HANDOFF.md content to sub-agent — 400+ lines, wastes context",
            "Committing PULSE.log — it's gitignored, high-churn runtime log",
        ],
        "references": ["CLAUDE.md context engineering rules", ".agent/collaboration/RESUME.json"],
        "endorsement_count": 3,
        "last_validated": NOW,
    },
    {
        "category": "testing_patterns",
        "title": "aq-qa layer registration, http_get() quirks, and mocking boundary",
        "description": "aq-qa phases: layer 0 = smoke tests (import/file existence), layer 1 = service health, layer 2 = API integration, layer 3 = end-to-end. Register new checks by adding test functions matching check_NN_description() naming convention in scripts/testing/harness_qa/phases/phaseN.py. http_get() utility: raises on non-2xx, timeout default=10s (raises requests.Timeout, NOT returns None — callers must catch). Mocking boundary: local Qdrant + coordinator tested against LIVE instances; external inference endpoints (OpenAI, Gemini API) must be mocked.",
        "examples": [
            "def check_86_7_dashboard_alerts_endpoint(): resp = http_get('http://localhost:8889/api/aistack/alerts/status'); assert resp.status_code == 200",
            "# Mock: responses.add(POST, 'https://api.openai.com/...', ...) — never hit external inference in CI",
        ],
        "anti_patterns": [
            "Registering QA check without a corresponding dashboard panel — service breaks silently",
            "Using http_get() without try/except requests.Timeout — unhandled timeout crashes test run",
        ],
        "references": ["scripts/testing/harness_qa/phases/", "CLAUDE.md §coverage-gap-silent-breakage"],
        "endorsement_count": 2,
        "last_validated": NOW,
    },
    {
        "category": "nixos_architecture",
        "title": "Nix overlays, flake targets, and store immutability patterns",
        "description": "Flake target: .#hyperd-ai-dev (NOT .#hyperd — doesn't exist). Nix overlays: defined in nix/overlays/ and applied in flake.nix. Pattern: overlays = [ (final: prev: { pkg = prev.pkg.override {...}; }) ]. Store is immutable — service edits in /nix/store/* require nixos-rebuild switch to activate. Nix store path wildcards: use /nix/store/**/subpath (parts[3:] after split) — parts[2:] incorrectly includes hash. Feature flags: profile-driven via nix/modules/profiles/ai-dev.nix.",
        "examples": [
            "sudo nixos-rebuild switch --flake .#hyperd-ai-dev  # rebuild + activate",
            "Nix path wildcard: /nix/store/**/bin/python3 (not /nix/store/hash-name/bin/python3)",
        ],
        "anti_patterns": [
            "nixos-rebuild switch --flake .#hyperd — wrong target, build fails",
            "Editing files under /nix/store — immutable, changes lost on rebuild",
        ],
        "references": ["flake.nix", "nix/modules/profiles/ai-dev.nix", "nix/modules/core/options.nix"],
        "endorsement_count": 4,
        "last_validated": NOW,
    },
    {
        "id": "gemini_rg_bundle",
        "category": "multi_agent_collaboration",
        "title": "Gemini CLI Bundled ripgrep Pre-flight",
        "description": (
            "Gemini CLI uses a platform-specific bundled ripgrep binary (rg-linux-x64 on x86_64) "
            "at bundle/vendor/ripgrep/ relative to the resolved bundle/gemini.js entrypoint. "
            "The npm package does NOT ship this binary — without it Gemini falls back to GrepTool "
            "and fails with 'rg unavailable in exec context'. Fix: symlink the system rg into the "
            "expected vendor path before invoking Gemini (ensure_gemini_rg function in "
            "delegate-to-gemini). Key: use realpath on GEMINI_BIN to get the true bundle dir path, "
            "then compute vendor/ripgrep/rg-linux-{arch}. x86_64 → x64, aarch64 → arm64."
        ),
        "examples": [
            "realpath $GEMINI_BIN → .../bundle/gemini.js; dirname → bundle/; +/vendor/ripgrep/rg-linux-x64",
            "ln -sf /run/current-system/sw/bin/rg bundle/vendor/ripgrep/rg-linux-x64",
        ],
        "anti_patterns": [
            "Using dirname twice on realpath result — doubles the package path",
            "Injecting system rg via PATH — Gemini uses absolute bundled path, ignores PATH",
        ],
        "references": ["scripts/ai/delegate-to-gemini"],
        "endorsement_count": 1,
        "last_validated": NOW,
    },
    {
        "category": "python_async",
        "title": "aiohttp concurrent HTTP request handling: connection pool, semaphore, to_thread",
        "description": "aiohttp handles concurrent HTTP requests via an async event loop — each request is a coroutine. Concurrent pattern: aiohttp.ClientSession is reusable (create once per server lifetime, not per request). For bounded concurrency: asyncio.Semaphore(N) to cap parallel outbound requests. For CPU-bound or sync I/O inside handlers: asyncio.to_thread(sync_fn, *args). aiohttp server handles thousands of concurrent connections via single event loop; never block in async def (no time.sleep, no open(), no requests.get). For parallel fan-out: asyncio.gather(*[coro1, coro2, ...], return_exceptions=True).",
        "examples": [
            "async with aiohttp.ClientSession() as s: resp = await s.get(url)  # single session reuse",
            "sem = asyncio.Semaphore(10); async with sem: result = await fetch(url)  # bounded concurrency",
            "results = await asyncio.gather(*[fetch(u) for u in urls], return_exceptions=True)  # fan-out",
        ],
        "anti_patterns": [
            "aiohttp.ClientSession() inside each request handler — creates new TCP pool every call",
            "time.sleep(1) inside async def handler — blocks entire event loop for all requests",
            "requests.get(url) inside async def — synchronous, blocks event loop; use aiohttp or to_thread",
        ],
        "references": ["ai-stack/mcp-servers/hybrid-coordinator/http_server.py", "CLAUDE.md §async-blocking"],
        "endorsement_count": 3,
        "last_validated": NOW,
    },
    {
        "category": "resilience_patterns",
        "title": "Exponential backoff retry: max_attempts, backoff_factor, and jitter",
        "description": "Exponential backoff pattern for retrying transient failures: wait = backoff_factor * (2 ** attempt). With jitter: wait += random.uniform(0, 0.5 * wait). Standard parameters: max_attempts=3 (or configured via RETRY_MAX_ATTEMPTS env), backoff_factor=0.5 (gives 0.5s, 1.0s, 2.0s). Only retry on transient errors (5xx, timeout, ConnectionError) — never retry 4xx (client error) or auth failures. Pattern in this codebase: aq-qa phase0.py uses 3-attempt retry; delegate-to-gemini has 3-attempt backoff; dispatch.py has max 3 retries then report to orchestrator.",
        "examples": [
            "for attempt in range(max_attempts):\\n    try: return call()\\n    except TransientError: time.sleep(backoff_factor * 2**attempt)",
            "RETRY_BUDGET = 3  # max retries; 3rd failure → stop and report to orchestrator (CLAUDE.md rule 6)",
        ],
        "anti_patterns": [
            "Retrying on 401/403/404 — these are deterministic failures; retrying wastes budget",
            "No jitter — all retries hit at same time under load (thundering herd)",
            "Unlimited retries — always cap at max_attempts (3 in this codebase)",
        ],
        "references": ["scripts/ai/lib/dispatch.py", "scripts/testing/harness_qa/phases/phase0.py", "CLAUDE.md retry-budget"],
        "endorsement_count": 3,
        "last_validated": NOW,
    },
    {
        "category": "nixos_architecture",
        "title": "Nix package overrides and overlays: override, overrideAttrs, flake overlay pattern",
        "description": "Three override mechanisms: (1) pkg.override {arg = val;} — replaces build-time arguments (e.g. python3 version, stdenv). (2) pkg.overrideAttrs (old: { patches = old.patches ++ [./fix.patch]; }) — modifies derivation attrs. (3) Flake overlay: overlays = [(final: prev: { pkg = prev.pkg.override {...}; })]; applied in nixpkgs.overlays in flake.nix. Pattern in this repo: overlays in nix/overlays/, referenced from flake.nix. Package resolution order: overlays run first (left to right), then nixpkgs defaults. To add a new package not in nixpkgs: use pkgs.callPackage ./nix/pkgs/mypkg/default.nix {} then expose in overlay.",
        "examples": [
            "overlays = [(final: prev: { myPkg = prev.myPkg.overrideAttrs (_: { version = \"2.0\"; }); })]",
            "pkgs.callPackage ./nix/pkgs/mycli/default.nix {}  # custom package from local derivation",
        ],
        "anti_patterns": [
            "Editing pkgs in /nix/store — immutable, changes are lost on next nixos-rebuild",
            "Using override without overrideAttrs when changing source — override only changes inputs",
        ],
        "references": ["nix/overlays/", "flake.nix", "nix/modules/profiles/ai-dev.nix"],
        "endorsement_count": 2,
        "last_validated": NOW,
    },
    {
        "category": "nixos_architecture",
        "title": "hwmon/k10temp thermal sensor: reading CPU temp from sysfs on NixOS",
        "description": "On AMD Renoir/Ryzen systems, CPU temperature is exposed via hwmon subsystem. Sensor path: /sys/class/hwmon/hwmonN/temp1_input (millidegrees Celsius — divide by 1000). Sensor name file: /sys/class/hwmon/hwmonN/name — look for 'k10temp'. Dynamic scan: glob /sys/class/hwmon/hwmon*/name and match 'k10temp'. On Renoir APU, Tctl reads ~81°C at idle (includes offset) — thermal_margin = Tctl - Tccd. AppArmor rule for hwmon reads: /sys/class/hwmon/ r, /sys/class/hwmon/** r, /sys/devices/pci*/**/hwmon/** r (NOT /sys/devices/pci*/**/hwmon/**/). NixOS dashboard profile critical threshold raised to 83°C (Phase 99.1) via THERMAL_CRITICAL_C env var.",
        "examples": [
            "import glob; sensors = {open(p.replace('name','temp1_input')).read().strip() for p in glob.glob('/sys/class/hwmon/hwmon*/name') if open(p).read().strip() == 'k10temp'}",
            "THERMAL_CRITICAL_C=83 python3 inference_param_manager.py  # override default 80°C",
        ],
        "anti_patterns": [
            "Hardcoding /sys/class/hwmon/hwmon2/ — sensor index varies by kernel and boot order",
            "Using hwmon/** in AppArmor without the parent /sys/class/hwmon/ r rule — d access needed for directory",
        ],
        "references": [
            "ai-stack/mcp-servers/hybrid-coordinator/inference_param_manager.py",
            "nix/modules/services/mcp-servers.nix",
        ],
        "endorsement_count": 2,
        "last_validated": NOW,
    },
    {
        "category": "nixos_architecture",
        "title": "systemd DynamicUser: what it does and when NOT to use it in NixOS services",
        "description": "DynamicUser=true allocates a transient UID/GID at service startup (freed on stop). It sandboxes services without a fixed user account. Benefits: automatic /run/user, tmpfs, no /home pollution. Critical constraint: DynamicUser is INCOMPATIBLE with NoNewPrivileges=false in the same unit for AppArmor profile transitions — setuid wrappers (sudo, ping) fail with EPERM even with Ux rules. Do NOT use DynamicUser when the service needs: (1) persistent /var/lib/<service> state owned by fixed UID, (2) sudo or setuid binary execution, (3) AppArmor Ux/Px profile transitions, (4) socket activation with fixed ownership. NixOS pattern: use User = 'aidb'; Group = 'aidb'; with StateDirectory = 'ai-stack/aidb'; for services that own persistent state. For readonly/stateless services DynamicUser is fine.",
        "examples": [
            "User = \"aidb\"; Group = \"aidb\"; StateDirectory = \"ai-stack/aidb\";  # fixed user, persistent state",
            "DynamicUser = true; RuntimeDirectory = \"myservice\";  # OK for stateless/sandboxed services",
        ],
        "anti_patterns": [
            "DynamicUser = true + sudo exec — EPERM because setuid requires fixed UID",
            "DynamicUser = true + AppArmor Ux/Px — NoNewPrivileges=true (implied by DynamicUser) blocks profile transitions",
            "DynamicUser + /var/lib/<name> — directory ownership is ephemeral; use StateDirectory instead",
        ],
        "references": [
            "nix/modules/services/mcp-servers.nix",
            "nix/modules/services/command-center-dashboard.nix",
        ],
        "endorsement_count": 2,
        "last_validated": NOW,
    },
]

# ---------------------------------------------------------------------------
# Ingestion helpers
# ---------------------------------------------------------------------------

def _http_post(url: str, body: dict, timeout: int = 30) -> dict:
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body_text = e.read().decode(errors="replace")
        raise RuntimeError(f"HTTP {e.code} from {url}: {body_text[:300]}") from e


def _http_put(url: str, body: dict, timeout: int = 30) -> dict:
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="PUT")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body_text = e.read().decode(errors="replace")
        raise RuntimeError(f"HTTP {e.code} PUT {url}: {body_text[:300]}") from e


def embed(text: str) -> list:
    resp = _http_post(f"{EMBED_URL}/v1/embeddings", {"input": text, "model": EMBED_MODEL})
    return resp["data"][0]["embedding"]


def upsert_points(collection: str, points: list, dry_run: bool = False) -> int:
    if dry_run:
        print(f"  [dry-run] would upsert {len(points)} points into {collection}")
        return len(points)
    url = f"{QDRANT_URL}/collections/{collection}/points"
    resp = _http_put(url, {"points": points})
    status = resp.get("result", {}).get("status", resp.get("status", "?"))
    print(f"  upserted {len(points)} → {collection}: {status}")
    return len(points)


def _text_for_embed(record: dict, collection: str) -> str:
    """Build the text that should be embedded for semantic search.
    Includes examples/anti_patterns to improve BGE-M3 recall for natural
    language queries (Gemini review amendment 2026-05-28).
    """
    if collection == "error-solutions":
        return (
            f"Error: {record['error_type']} - {record['error_message']} "
            f"Context: {record['context']} Solution: {record['solution']}"
        )
    if collection == "skills-patterns":
        text = f"Skill: {record['skill_name']} - {record['description']} Usage: {record['usage_pattern']}"
        if record.get("success_examples"):
            text += f" Examples: {' '.join(record['success_examples'])}"
        return text
    if collection == "best-practices":
        text = f"Best Practice: {record['title']} ({record['category']}) {record['description']}"
        if record.get("examples"):
            text += f" Examples: {' '.join(record['examples'])}"
        return text
    return json.dumps(record)


def _clear_wrong_type_points(collection: str, dry_run: bool = False) -> int:
    """Delete points in error-solutions that have memory_id field (wrong schema type)."""
    if collection != "error-solutions":
        return 0
    url = f"{QDRANT_URL}/collections/{collection}/points/scroll"
    req = urllib.request.Request(
        url,
        data=json.dumps({"limit": 200, "with_payload": ["memory_id"]}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        result = json.loads(resp.read())
    points = result.get("result", {}).get("points", [])
    wrong_ids = [p["id"] for p in points if "memory_id" in p.get("payload", {})]
    if not wrong_ids:
        print(f"  no wrong-type points found in {collection}")
        return 0
    if dry_run:
        print(f"  [dry-run] would delete {len(wrong_ids)} wrong-type points from {collection}")
        return len(wrong_ids)
    del_url = f"{QDRANT_URL}/collections/{collection}/points/delete"
    _http_post(del_url, {"points": wrong_ids})
    print(f"  deleted {len(wrong_ids)} wrong-type points from {collection}")
    return len(wrong_ids)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

SEED_DATA = {
    "error-solutions":  ERROR_SOLUTIONS,
    "skills-patterns":  SKILLS_PATTERNS,
    "best-practices":   BEST_PRACTICES,
}


def seed_collection(name: str, records: list, dry_run: bool, clear_wrong: bool) -> None:
    print(f"\n--- {name} ({len(records)} records) ---")

    if clear_wrong and name == "error-solutions":
        _clear_wrong_type_points(name, dry_run=dry_run)

    points = []
    for i, rec in enumerate(records):
        text = _text_for_embed(rec, name)
        print(f"  [{i+1}/{len(records)}] embedding: {text[:60]}...")
        if not dry_run:
            vector = embed(text)
        else:
            vector = [0.0] * 1024  # placeholder
        points.append({
            "id":      str(uuid.uuid4()),
            "vector":  vector,
            "payload": rec,
        })

    upsert_points(name, points, dry_run=dry_run)


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed RAG knowledge collections")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be done, no writes")
    parser.add_argument("--collection", default="all", help="Collection to seed (default: all)")
    parser.add_argument("--clear-wrong-type", action="store_true",
                        help="Delete wrong-schema points from error-solutions before seeding")
    args = parser.parse_args()

    collections = SEED_DATA if args.collection == "all" else {args.collection: SEED_DATA[args.collection]}

    total = 0
    for name, records in collections.items():
        seed_collection(name, records, dry_run=args.dry_run, clear_wrong=args.clear_wrong_type)
        total += len(records)

    print(f"\ndone — {total} records processed across {len(collections)} collections")


if __name__ == "__main__":
    main()
