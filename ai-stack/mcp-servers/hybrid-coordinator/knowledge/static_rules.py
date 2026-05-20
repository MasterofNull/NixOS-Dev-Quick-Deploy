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
