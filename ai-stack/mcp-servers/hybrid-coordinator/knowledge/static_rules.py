"""
knowledge/static_rules.py — Static workflow rules, agent strengths, and routing data.

Extracted from hints_engine.py (Phase R3 decomposition).
Zero imports from hints_engine.py (PRD constraint R3-AC6).
Zero external dependencies — pure data module.
"""
from __future__ import annotations

from typing import Dict, List, Tuple


# ---------------------------------------------------------------------------
# Static workflow rules derived from CLAUDE.md
# ---------------------------------------------------------------------------

STATIC_RULES: List[dict] = [
    # ── NixOS / Nix Language ─────────────────────────────────────────────────
    {
        "id": "nixos_mkforce_rule",
        "title": "Use lib.mkForce for module conflicts",
        "keywords": ["conflict", "conflicting", "mkdefault", "priority", "override"],
        "snippet": (
            "Use `lib.mkForce` (priority 50) to override. Remove duplicate "
            "`lib.mkDefault` settings from all but one module."
        ),
        "tags": ["nixos", "module", "priority"],
    },
    {
        "id": "no_hardcode_ports",
        "title": "Never hardcode port numbers",
        "keywords": ["port", "url", "endpoint", "address", "http", "socket"],
        "snippet": (
            "Read ports from env vars. Define in `nix/modules/core/options.nix`. "
            "Python: `os.getenv('PORT', 'default')`. Shell: `${PORT:-default}`."
        ),
        "tags": ["port", "policy", "env"],
    },
    {
        "id": "lib_mkif_not_merge",
        "title": "Use lib.mkIf not // for conditionals",
        "keywords": ["conditional", "if", "optional", "platform", "guard", "mkif"],
        "snippet": (
            "Use `lib.mkIf condition value` inside module body. Never "
            "`// lib.optionalAttrs` -- it silently drops other top-level keys."
        ),
        "tags": ["nixos", "conditional", "module"],
    },
    {
        "id": "nix_flake_inputs",
        "title": "Pin flake inputs for reproducibility",
        "keywords": ["flake", "input", "lock", "pin", "version", "dependency"],
        "snippet": (
            "Use `nix flake lock --update-input <name>` to update single inputs. "
            "Never `nix flake update` blindly -- it updates ALL inputs."
        ),
        "tags": ["nixos", "flake", "reproducibility"],
    },
    {
        "id": "nix_overlay_patterns",
        "title": "Use overlays for package customization",
        "keywords": ["overlay", "package", "customize", "override", "derivation"],
        "snippet": (
            "Define in `nix/overlays/default.nix`. Use `final: prev:` pattern. "
            "Avoid `self: super:` (deprecated). Apply via `nixpkgs.overlays = [...]`."
        ),
        "tags": ["nixos", "overlay", "package"],
    },
    # ── Agentic / Code Generation ────────────────────────────────────────────
    {
        "id": "check_capability_index_before_new_code",
        "title": "Check CAPABILITY-INDEX for an existing tool before writing new code",
        "keywords": ["new script", "write a script", "implement", "helper", "utility", "add a tool",
                     "new tool", "create script", "build a", "reimplement", "existing tool", "aq-"],
        "snippet": (
            "Before writing a new script/helper, grep `docs/agent-guides/CAPABILITY-INDEX.md` "
            "(machine form: `config/capability-index.json`) for the task keyword. Reuse or "
            "extend an existing aq-*/skill/MCP tool; read only the matching rows."
        ),
        "tags": ["capability", "reuse", "discovery"],
    },
    {
        "id": "verify_committed_bytes_not_piped_hash",
        "title": "Verify committed bytes with git blob IDs, not piped hashes",
        "keywords": ["sha256", "hash mismatch", "committed bytes", "git show", "verify commit", "checksum"],
        "snippet": (
            "Output-rewriting hooks can corrupt `git show HEAD:f | sha256sum` (false mismatch). "
            "Use `scripts/ai/aq-verify-committed <path> [sha256]` (git blob IDs, fail-closed)."
        ),
        "tags": ["verification", "git", "hooks"],
    },
    {
        "id": "parallel_lanes_claim_paths",
        "title": "Claim slices/paths before parallel lane edits",
        "keywords": ["parallel", "concurrent", "claim", "collision", "same file", "other lane", "lock"],
        "snippet": (
            "When another agent lane may touch the same files, take an advisory claim: "
            "`scripts/ai/aq-claim` (take/check/release slice+path claims) before editing."
        ),
        "tags": ["coordination", "multi-agent"],
    },
    {
        "id": "transcribe_media_locally",
        "title": "Transcribe video/audio locally for research ingestion",
        "keywords": ["transcribe", "transcript", "youtube", "video", "audio", "podcast", "talk"],
        "snippet": (
            "Use `scripts/ai/aq-transcribe <url|file>` (fully local, no cloud API) to turn a "
            "talk/video into text for agent research notes."
        ),
        "tags": ["research", "ingestion"],
    },
    {
        "id": "annotate_plans_with_tools",
        "title": "Annotate plan files with recommended tool sequences",
        "keywords": ['enrich plan', 'annotate plan', 'plan tools', 'tool sequence', 'plan annotation'],
        "snippet": (
            '`scripts/ai/aq-enrich-plans [--plan P|--task T] [--write]` pre-loads plans with tool recommendations via the coordinator /tools/enrich-plan (dry-run by default).'
        ),
        "tags": ['planning', 'tools'],
    },
    {
        "id": "generate_improvement_proposals",
        "title": "Turn high-trust improvement candidates into proposal files",
        "keywords": ['proposal', 'improvement candidate', 'candidates.json', 'generate proposal', 'discovery proposal'],
        "snippet": (
            '`scripts/ai/aq-propose [--dry-run]` renders .agents/proposals/<id>.md from .agents/improvement/candidates.json (trust>=0.70, relevance>=0.40, state=proposed).'
        ),
        "tags": ['improvement', 'governance'],
    },
    {
        "id": "cli_output_helpers",
        "title": "Shared CLI output helpers (spinner, progress, humanize, confirm)",
        "keywords": ['spinner', 'progress bar', 'humanize bytes', 'humanize duration', 'cli helper', 'confirm prompt', 'print table'],
        "snippet": (
            'Python: `scripts/ai/cli-utils.py` (Logger, ProgressBar, Spinner, confirm, humanize_*, format_table). Bash: `source scripts/ai/cli-enhanced.sh` (spinner, run_with_spinner, humanize_*, print_table, show_error). Reuse instead of re-implementing.'
        ),
        "tags": ['cli', 'ux'],
    },
    {
        "id": "scaffold_new_skill",
        "title": "Scaffold a lint-conformant skill, or draft skills from gap patterns",
        "keywords": ['new skill', 'scaffold skill', 'create skill', 'skill stub', 'gap pattern skill'],
        "snippet": (
            '`scripts/ai/aq-factory <name> \\"<purpose>\\"` scaffolds ai-stack/agents/skills/<name>/SKILL.md (then run scripts/governance/lint-skill-template.sh); `scripts/ai/aq-skill-factory [--dry-run]` drafts stubs in .agent/skills/auto-generated/ from delegation gap patterns.'
        ),
        "tags": ['skills', 'scaffolding'],
    },
    {
        "id": "backfill_interaction_history_qdrant",
        "title": "Backfill AIDB interaction_history into Qdrant",
        "keywords": ['interaction-history', 'interaction history', 'backfill qdrant', 'history collection empty'],
        "snippet": (
            'If the Qdrant interaction-history collection is empty or behind AIDB /history, run `scripts/ai/backfill-interaction-history-qdrant.py [--batch-size N] [--dry-run]` (operator-run; touches AIDB+Qdrant).'
        ),
        "tags": ['qdrant', 'aidb', 'operations'],
    },
    {
        "id": "regenerate_module_dashboard_pages",
        "title": "Regenerate capability module HTML pages",
        "keywords": ['module dashboard', 'assets/modules', 'capability catalog html', 'module page', 'system-capability-catalog'],
        "snippet": (
            'After editing config/system-capability-catalog.json, regenerate assets/modules/*.html with `python3 scripts/ai/generate-module-dashboard.py` (use --out-dir DIR to preview elsewhere).'
        ),
        "tags": ['dashboard', 'catalog'],
    },
    {
        "id": "resume_interrupted_model_download",
        "title": "Resume an interrupted multi-GB model download",
        "keywords": ['resume download', 'partial download', 'gguf download', 'model download interrupted', 'curl resume'],
        "snippet": (
            'llama-cpp-model-fetch restarts from zero on interruption; `scripts/ai/resume-model-download.sh --repo R --file F [--dest-dir D] [--dry-run]` resumes by byte range (curl -C -).'
        ),
        "tags": ['models', 'operations'],
    },
    {
        "id": "legacy_ai_stack_script_names",
        "title": "Legacy ai-stack-* script names map to current tools",
        "keywords": ['ai-stack-e2e-test', 'ai-stack-troubleshoot', 'ai-stack-resume-recovery', 'ai-stack-feature-scenario', 'ai-model-setup', 'llama-model-cli', 'ai-metrics-auto-updater'],
        "snippet": (
            'CI-pinned compat shims in scripts/ai/: ai-stack-e2e-test (aq-qa 0/1 + workflow smoke), ai-stack-troubleshoot (diagnostic bundle), ai-stack-resume-recovery (aq-system-act/aq-runtime-act), ai-stack-feature-scenario (aq-context-bootstrap), ai-model-setup + llama-model-cli (ai-model-manager.sh), ai-metrics-auto-updater (collect-ai-metrics.sh). Prefer the current tools.'
        ),
        "tags": ['compat', 'legacy'],
    },
    {
        "id": "aider_scope_small",
        "title": "Keep aider tasks small and targeted",
        "keywords": ["aider", "code", "generate", "edit", "change", "modify"],
        "snippet": (
            "One logical change per aider invocation. Include only the files being "
            "changed with --file. Use --message with <=200 char task description."
        ),
        "tags": ["aider", "code_generation", "scope"],
    },
    {
        "id": "verify_delegated_output",
        "title": "Verify all qwen/codex output before use",
        "keywords": ["qwen", "codex", "delegate", "agent", "generate"],
        "snippet": (
            "Cross-check every file path and code reference with Grep/Read. "
            "Validate with `python3 -m py_compile` or `bash -n` before committing."
        ),
        "tags": ["workflow", "verification", "agent"],
    },
    {
        "id": "orchestrator_delegation",
        "title": "Orchestrator delegates implementation, not decisions",
        "keywords": ["orchestrator", "delegate", "task", "agent", "routing"],
        "snippet": (
            "As orchestrator: Research → Plan → Delegate → Audit. Route code/config "
            "to qwen/codex. Keep architecture decisions, security audits in-house."
        ),
        "tags": ["orchestrator", "workflow", "delegation"],
    },
    # ── Systemd / Services ───────────────────────────────────────────────────
    {
        "id": "systemd_hardening",
        "title": "Always include systemd hardening in new services",
        "keywords": ["service", "systemd", "unit", "daemon", "execstart"],
        "snippet": (
            "Add: NoNewPrivileges=true, PrivateTmp=true, ProtectSystem=strict, "
            "MemoryMax=<tier>. Use mkHardenedService helper in "
            "nix/lib/hardened-service.nix."
        ),
        "tags": ["systemd", "hardening", "nixos"],
    },
    {
        "id": "systemd_dependency_order",
        "title": "Use After/Wants for service dependencies",
        "keywords": ["dependency", "order", "after", "wants", "requires"],
        "snippet": (
            "Use `After=` for ordering, `Wants=` for soft deps, `Requires=` for hard deps. "
            "Never rely on alphabetical order. Add `network-online.target` for network."
        ),
        "tags": ["systemd", "dependency", "nixos"],
    },
    # ── Testing / Validation ─────────────────────────────────────────────────
    {
        "id": "strategy_tag_evals",
        "title": "Tag eval runs with strategy names",
        "keywords": ["eval", "score", "test", "benchmark", "compare", "strategy"],
        "snippet": (
            "Use `scripts/automation/run-eval.sh --strategy my-variant` to tag results for "
            "aq-report leaderboard comparison."
        ),
        "tags": ["eval", "strategy", "measurement"],
    },
    {
        "id": "aq_prompt_eval_cycle",
        "title": "Run aq-prompt-eval after prompt changes",
        "keywords": ["prompt", "template", "registry", "mean_score", "optimize"],
        "snippet": (
            "After editing a prompt template in registry.yaml, run "
            "`scripts/ai/aq-prompt-eval --id <id>` to update mean_score before deploying."
        ),
        "tags": ["prompt", "registry", "eval", "measurement"],
    },
    {
        "id": "parity_suite_before_merge",
        "title": "Run parity suite before merging",
        "keywords": ["merge", "pr", "pull", "request", "check", "parity"],
        "snippet": (
            "Run `scripts/ai/aqd parity advanced-suite` before merging. "
            "Blocks merge if: security gates fail, eval regression >5%, or boot-shutdown breaks."
        ),
        "tags": ["parity", "validation", "ci"],
    },
    # ── Debugging / Troubleshooting ──────────────────────────────────────────
    {
        "id": "debug_service_logs",
        "title": "Check journalctl for service errors",
        "keywords": ["error", "fail", "crash", "debug", "log", "journal"],
        "snippet": (
            "Use `journalctl -u <service> --since='10 min ago' -n 100`. "
            "Add `-f` for follow mode. Check `systemctl status <service>` first."
        ),
        "tags": ["debugging", "journalctl", "systemd"],
    },
    {
        "id": "debug_nix_build",
        "title": "Debug Nix build failures with --show-trace",
        "keywords": ["build", "error", "trace", "fail", "nix", "derivation"],
        "snippet": (
            "Add `--show-trace` to nix build/switch commands. Use `nix log` for build logs. "
            "Check `nix why-depends` for dependency issues."
        ),
        "tags": ["debugging", "nix", "build"],
    },
    {
        "id": "debug_python_import",
        "title": "Debug Python import errors with PYTHONPATH",
        "keywords": ["python", "import", "module", "path", "error"],
        "snippet": (
            "Check `echo $PYTHONPATH`. Add repo root: `PYTHONPATH=$PWD:$PYTHONPATH`. "
            "Verify venv activation. Use `python -c 'import sys; print(sys.path)'`."
        ),
        "tags": ["debugging", "python", "import"],
    },
    # ── Security ─────────────────────────────────────────────────────────────
    {
        "id": "security_no_secrets",
        "title": "Never hardcode secrets in source",
        "keywords": ["secret", "password", "token", "key", "credential", "api"],
        "snippet": (
            "Use sops-nix for secrets. Load from `/run/secrets/<name>` at runtime. "
            "Never commit .env files with real credentials."
        ),
        "tags": ["security", "secrets", "policy"],
    },
    {
        "id": "security_input_validation",
        "title": "Validate all external input",
        "keywords": ["input", "validate", "sanitize", "injection", "xss", "sql"],
        "snippet": (
            "Use Pydantic models for API input. Parameterize SQL queries (never interpolate). "
            "Escape HTML output. Check SSRF for URLs."
        ),
        "tags": ["security", "validation", "input"],
    },
    # ── Performance / Optimization ───────────────────────────────────────────
    {
        "id": "perf_cache_semantic",
        "title": "Use semantic cache for repeated queries",
        "keywords": ["cache", "performance", "repeat", "embed", "vector"],
        "snippet": (
            "Check `aq-report` for cache hit rate. Target >30%. Seed cache with "
            "`scripts/data/seed-routing-traffic.sh --count 100`."
        ),
        "tags": ["performance", "cache", "optimization"],
    },
    {
        "id": "perf_local_routing",
        "title": "Prefer local LLM for simple tasks",
        "keywords": ["local", "llm", "routing", "cost", "token", "remote"],
        "snippet": (
            "Route complexity <5 queries to local. Check routing split in `aq-report`. "
            "Target >80% local for cost efficiency."
        ),
        "tags": ["performance", "routing", "cost"],
    },
    # ── Documentation / Git ──────────────────────────────────────────────────
    {
        "id": "git_commit_protocol",
        "title": "Follow commit protocol with evidence",
        "keywords": ["commit", "git", "message", "push", "change"],
        "snippet": (
            "Format: `<phase>.<task>: <description>`. Include Evidence: line. "
            "Add `Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>` trailer."
        ),
        "tags": ["git", "commit", "protocol"],
    },
    {
        "id": "doc_progressive_disclosure",
        "title": "Use progressive disclosure for docs",
        "keywords": ["document", "doc", "readme", "guide", "explain"],
        "snippet": (
            "Keep CLAUDE.md compact (<200 lines). Link to deep docs in `docs/agent-guides/`. "
            "Load context on-demand, not upfront."
        ),
        "tags": ["documentation", "progressive", "disclosure"],
    },
    # Keywords are single lowercase [a-z0-9]+ tokens (see token_manager._TOKEN_RE),
    # so "multi-step" arrives as "multi" + "step".
    {
        "id": "use_workflow_blueprints_for_multistep",
        "title": "Multi-step task: check workflow_blueprints first",
        "keywords": ["multi", "step", "steps", "plan", "planning", "blueprint", "blueprints", "orchestrate"],
        "snippet": (
            "For multi-step or planned work call the `workflow_blueprints` MCP tool "
            "(hybrid-coordinator) for a ready phase/role template before improvising a plan; "
            "then `workflow_plan` / `workflow_run_start` to execute it."
        ),
        "tags": ["workflow", "blueprints", "planning"],
    },
    {
        "id": "use_tooling_manifest_for_tool_choice",
        "title": "Unsure which tool: call tooling_manifest",
        "keywords": ["tool", "tools", "tooling", "which", "toolbox"],
        "snippet": (
            "To pick the right tool, call the `tooling_manifest` MCP tool (hybrid-coordinator) "
            "for the live tool list and when-to-use notes instead of guessing or re-reading docs."
        ),
        "tags": ["tools", "discovery", "manifest"],
    },
    # ── ci-7 batch 2: wire high-value unused capabilities (phrase keywords) ──
    {
        "id": "store_recall_facts_aq_memory",
        "title": "Store or recall durable facts with aq-memory",
        "keywords": ["store a fact", "recall a fact", "remember this", "save to memory", "memory search"],
        "snippet": (
            "To persist or look up durable facts use `scripts/ai/aq-memory add|search` (or the `recall_memory`/`store_memory` MCP tools) instead of ad-hoc notes files."
        ),
        "tags": ["memory"],
    },
    {
        "id": "bootstrap_minimal_context",
        "title": "Bootstrap minimal context for a task",
        "keywords": ["bootstrap context", "minimal context", "start a task", "onboard to the task"],
        "snippet": (
            "Start a task with `scripts/ai/aq-context-bootstrap --task \"<task>\"` to get the minimal context cards and workflow entrypoints before reading raw files."
        ),
        "tags": ["context"],
    },
    {
        "id": "monitor_context_window",
        "title": "Monitor context window and checkpoint before it overflows",
        "keywords": ["context window", "context usage", "context checkpoint", "running out of context", "token budget"],
        "snippet": (
            "Check window usage and checkpoint with `scripts/ai/aq-context-manage` (--task for a checkpoint summary) before compaction instead of letting context overflow."
        ),
        "tags": ["context", "compaction"],
    },
    {
        "id": "extract_commit_facts",
        "title": "Extract semantic facts from recent commits",
        "keywords": ["commit facts", "facts from commits", "summarize recent commits", "index recent commits"],
        "snippet": (
            "Use `scripts/ai/aq-commit-facts --dry-run [--since SHA]` to extract semantic facts from recent commits into memory (local model; dry-run first)."
        ),
        "tags": ["memory", "git"],
    },
    {
        "id": "sample_service_health",
        "title": "Sample real service health with aq-health-spider",
        "keywords": ["health spider", "service health", "services are down", "sample health", "health sampling"],
        "snippet": (
            "Run `scripts/ai/aq-health-spider --once` for one real health-sampling and autonomous-fix cycle rather than hand-probing each service."
        ),
        "tags": ["health"],
    },
    {
        "id": "turn_feedback_into_loop",
        "title": "Turn agent feedback into a bounded harness loop",
        "keywords": ["agent feedback", "feedback loop", "turn feedback into", "friction report"],
        "snippet": (
            "Feed agent feedback into the harness with `scripts/ai/aq-feedback-loop --task \"<objective>\" [--feedback-file F]` so it becomes a bounded PRD/plan recommendation."
        ),
        "tags": ["feedback", "loop"],
    },
    {
        "id": "diagnose_runtime_service",
        "title": "Diagnose a failing service/package/runtime",
        "keywords": ["service is failing", "runtime diagnosis", "diagnose runtime", "package fails at runtime", "unit failed"],
        "snippet": (
            "Diagnose failing services/packages with `scripts/ai/aq-runtime-diagnose` (generic diagnosis loop) before hand-reading journals."
        ),
        "tags": ["runtime", "debug"],
    },
    {
        "id": "plan_runtime_incident",
        "title": "Plan a multi-step runtime incident response",
        "keywords": ["runtime incident", "incident plan", "incident response", "runtime plan"],
        "snippet": (
            "For a multi-step runtime incident use `scripts/ai/aq-runtime-plan` (multi-preset incident planner), then `aq-runtime-act` to execute guarded steps."
        ),
        "tags": ["runtime", "incident"],
    },
    {
        "id": "list_pending_rsi_repairs",
        "title": "List RSI repairs awaiting owner sign-off",
        "keywords": ["rsi pending", "pending repairs", "awaiting sign off", "owner sign off", "pending approval"],
        "snippet": (
            "List high-risk RSI repairs awaiting owner sign-off with `scripts/ai/aq-rsi-pending [--count|--json]`; never self-approve."
        ),
        "tags": ["rsi", "approval"],
    },
    {
        "id": "open_collab_round",
        "title": "Fan a task out to all agents with aq-collab-round",
        "keywords": ["collab round", "collaborative round", "fan out to all agents", "fan out the task", "consensus round"],
        "snippet": (
            "For a flat-collaborative round use `scripts/ai/aq-collab-round open --round <id> --task \"<task>\"` to fan the task out to all available agents and gather consensus."
        ),
        "tags": ["collaboration", "consensus"],
    },
    {
        "id": "submit_workflow_deviation",
        "title": "Record a workflow deviation receipt",
        "keywords": ["workflow deviation", "deviation receipt", "deviated from the plan", "skipped a workflow step"],
        "snippet": (
            "Record a closed deviation with `scripts/ai/aq-workflow-deviation submit --record-file F` (check `health` first) instead of leaving it undocumented."
        ),
        "tags": ["workflow", "audit"],
    },
    {
        "id": "analyze_recurring_patterns",
        "title": "Analyze recurring telemetry patterns",
        "keywords": ["recurring patterns", "recurring failures", "repeated failures", "telemetry patterns"],
        "snippet": (
            "Surface recurring failure/usage patterns with `scripts/ai/aq-patterns` before fixing one-off symptoms."
        ),
        "tags": ["patterns", "telemetry"],
    },
    {
        "id": "show_top_gap_queries",
        "title": "Show most-repeated knowledge-gap queries",
        "keywords": ["knowledge gaps", "gap queries", "repeated gap", "missing knowledge"],
        "snippet": (
            "See the most-repeated unanswered gap queries with `scripts/ai/aq-gaps [--days N]` and seed the missing knowledge into RAG."
        ),
        "tags": ["gaps", "rag"],
    },
    {
        "id": "weekly_stack_report",
        "title": "Weekly AI-stack performance digest",
        "keywords": ["performance digest", "weekly report", "stack report", "stack performance"],
        "snippet": (
            "Get the stack performance digest with `scripts/ai/aq-report --since 7d` before drawing conclusions about retrieval, routing or latency."
        ),
        "tags": ["report", "metrics"],
    },
    {
        "id": "query_wiki_section_first",
        "title": "Query the codebase wiki section before raw files",
        "keywords": ["codebase wiki", "wiki section", "subsystem overview", "architecture overview"],
        "snippet": (
            "Use `scripts/ai/aq-wiki --section <name>` for a subsystem overview before reading raw source files."
        ),
        "tags": ["wiki", "discovery"],
    },
    {
        "id": "recommend_context_card",
        "title": "Recommend a progressive-disclosure context card",
        "keywords": ["context card", "context cards", "low token onboarding", "progressive disclosure card"],
        "snippet": (
            "Render a low-token onboarding card with `scripts/ai/aq-context-card --recommend \"<task>\" --level brief`."
        ),
        "tags": ["context", "onboarding"],
    },
    {
        "id": "prewarm_local_rag",
        "title": "Prewarm local RAG for known prompts",
        "keywords": ["prewarm rag", "rag prewarm", "warm the cache", "cold start retrieval"],
        "snippet": (
            "Warm local RAG for known prompt ids or report candidates with `scripts/ai/aq-rag-prewarm` (bounded) to avoid cold-start retrieval latency."
        ),
        "tags": ["rag", "cache"],
    },
    {
        "id": "index_logic_patterns",
        "title": "Index cross-cutting logic patterns into AIDB",
        "keywords": ["logic patterns", "index patterns", "cross cutting logic", "index code patterns"],
        "snippet": (
            "Index cross-cutting logic patterns into AIDB with `scripts/ai/aq-index-logic-patterns --dry-run` first, then without it."
        ),
        "tags": ["aidb", "patterns"],
    },
    {
        "id": "operational_perspective_bundle",
        "title": "Compact operational evidence bundle",
        "keywords": ["operational perspective", "operational evidence", "introspect the stack", "what is the stack doing"],
        "snippet": (
            "Gather a compact evidence bundle with `scripts/ai/aq-operational-perspective --task \"<q>\"` (memory + preflight + aq-report) before answering questions about live stack state."
        ),
        "tags": ["introspection", "evidence"],
    },
    {
        "id": "reject_alert_with_reason",
        "title": "Reject an alert with a recorded reason",
        "keywords": ["reject alert", "reject the alert", "dismiss alert", "false positive alert"],
        "snippet": (
            "Reject a bad alert or proposal with `scripts/ai/aq-reject <id> --reason \"...\"` so the rejection is recorded and learned from."
        ),
        "tags": ["alerts", "feedback"],
    },
]

# Backward-compat alias used by HintsEngine (which references _STATIC_RULES)
_STATIC_RULES = STATIC_RULES

# ---------------------------------------------------------------------------
# Agent strengths and prompt coaching data
# ---------------------------------------------------------------------------

AGENT_STRENGTHS: Dict[str, Dict[str, str]] = {
    "codex": {
        "best_for": "orchestration, integration quality, reviewer gates, final acceptance",
        "prompt_shape": "State the objective, repo scope, hard constraints, acceptance checks, and required evidence.",
    },
    "qwen": {
        "best_for": "concrete patch proposals, implementation slices, test scaffolding",
        "prompt_shape": "Give the exact files, expected behavior change, and narrow implementation slice to patch.",
    },
    "claude": {
        "best_for": "architecture reasoning, policy/risk analysis, long-form tradeoffs",
        "prompt_shape": "Ask for system design, risk framing, and decision rationale with explicit constraints.",
    },
    "aider": {
        "best_for": "small targeted edits in already-selected files",
        "prompt_shape": "Keep the task to one logical change, name the files, and specify the exact edit outcome.",
    },
    "continue": {
        "best_for": "inline context lookup, iterative coding assistance, editor-local retrieval",
        "prompt_shape": "Ask for contextual help tied to the current file, symbol, or implementation step.",
    },
    "human": {
        "best_for": "operator requests and multi-agent routing decisions",
        "prompt_shape": "Lead with the goal, then constraints, relevant files, verification, and preferred agent split.",
    },
}

_AGENT_STRENGTHS = AGENT_STRENGTHS  # backward-compat alias

PROMPT_COACHING_FIELDS: List[Tuple[str, str, Tuple[str, ...]]] = [
    ("objective", "Explicit objective", ("implement", "fix", "add", "create", "continue", "investigate", "optimize", "review", "debug", "build", "wire")),
    ("constraints", "Constraints and guardrails", ("must", "should", "avoid", "don't", "do not", "only", "without", "preserve", "keep", "use", "never")),
    ("context", "Concrete context or files", (".nix", ".py", ".sh", ".md", "/", "file", "path", "repo", "module", "service", "endpoint")),
    ("validation", "Validation or acceptance checks", ("verify", "test", "validation", "acceptance", "done", "pass", "smoke", "evidence", "rollback")),
    ("agent_routing", "Agent selection or delegation intent", ("codex", "qwen", "claude", "aider", "continue", "agent", "delegate", "reviewer", "orchestrator")),
]

_PROMPT_COACHING_FIELDS = PROMPT_COACHING_FIELDS  # backward-compat alias

# ---------------------------------------------------------------------------
# File type routing data (Batch 6.1)
# ---------------------------------------------------------------------------

FILE_TYPE_TAG_MAP: Dict[str, List[str]] = {
    ".nix": ["nixos", "nix", "module", "flake", "derivation"],
    ".py": ["python", "code", "testing", "refactoring"],
    ".js": ["javascript", "code", "testing", "node"],
    ".ts": ["typescript", "javascript", "code", "testing"],
    ".sh": ["bash", "shell", "script"],
    ".md": ["documentation", "markdown"],
    ".yaml": ["config", "yaml", "kubernetes"],
    ".yml": ["config", "yaml", "kubernetes"],
    ".json": ["config", "json", "api"],
    ".rs": ["rust", "code", "testing"],
    ".go": ["go", "code", "testing"],
    ".c": ["c", "code"],
    ".cpp": ["cpp", "code"],
    ".h": ["c", "code", "header"],
}

FILE_TYPE_BOOST_MULTIPLIER: float = 1.3
