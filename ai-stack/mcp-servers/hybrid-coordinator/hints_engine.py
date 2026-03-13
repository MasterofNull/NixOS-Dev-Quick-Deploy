from __future__ import annotations

import json
import math
import os
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]
try:
    import psycopg  # type: ignore[import-untyped]
except Exception:
    psycopg = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Hint:
    """A ranked, actionable workflow hint surfaced to any agent or human."""

    id: str
    type: str  # "prompt_template" | "gap_topic" | "workflow_rule" | "tool_warning" | "runtime_signal" | "prompt_coaching"
    title: str
    score: float  # composite 0.0-1.0
    snippet: str  # actionable text: template excerpt, rule, etc.
    reason: str  # why this hint was surfaced
    tags: List[str] = field(default_factory=list)
    agent_hints: Dict[str, str] = field(default_factory=dict)
    # Per-agent delivery format overrides; keys: human/claude/codex/qwen/aider/continue


# ---------------------------------------------------------------------------
# Static workflow rules derived from CLAUDE.md
# ---------------------------------------------------------------------------

_STATIC_RULES: List[dict] = [
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_COMMAND_RE = re.compile(r"`[^`]+`|scripts/[a-zA-Z0-9._/-]+|/[a-zA-Z0-9._/-]+")

_AGENT_STRENGTHS: Dict[str, Dict[str, str]] = {
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

_PROMPT_COACHING_FIELDS: List[Tuple[str, str, Tuple[str, ...]]] = [
    ("objective", "Explicit objective", ("implement", "fix", "add", "create", "continue", "investigate", "optimize", "review", "debug", "build", "wire")),
    ("constraints", "Constraints and guardrails", ("must", "should", "avoid", "don't", "do not", "only", "without", "preserve", "keep", "use", "never")),
    ("context", "Concrete context or files", (".nix", ".py", ".sh", ".md", "/", "file", "path", "repo", "module", "service", "endpoint")),
    ("validation", "Validation or acceptance checks", ("verify", "test", "validation", "acceptance", "done", "pass", "smoke", "evidence", "rollback")),
    ("agent_routing", "Agent selection or delegation intent", ("codex", "qwen", "claude", "aider", "continue", "agent", "delegate", "reviewer", "orchestrator")),
]


def _tokenize(text: str) -> List[str]:
    """Lowercase and split on whitespace / punctuation."""
    return _TOKEN_RE.findall(text.lower())


def _longest_common_substring_len(a: str, b: str) -> int:
    """Return the length of the longest common substring of a and b."""
    if not a or not b:
        return 0
    m, n = len(a), len(b)
    best = 0
    # dp[j] = length of LCS ending at a[i-1], b[j-1]
    dp = [0] * (n + 1)
    for i in range(1, m + 1):
        prev = 0
        for j in range(1, n + 1):
            temp = dp[j]
            if a[i - 1] == b[j - 1]:
                dp[j] = prev + 1
                if dp[j] > best:
                    best = dp[j]
            else:
                dp[j] = 0
            prev = temp
    return best


_CURATED_STALE_GAP_PATTERNS = (
    "lib mkforce",
    "lib mkif",
    "flake inputs follows",
    "nixos module options",
    "nixos systemd service options",
    "configure nixos services",
    "how do i configure a nixos systemd service",
    "postgresql nixos module setup",
    "tc3 feedback validation",
    "tc3 final feedback loop validation",
    "how does the hybrid coordinator route queries",
    "what is nixos",
    "explain what nixos is",
    "nixos flake",
    "nixos flake build system",
    "create a workflow plan for diagnosing continue chat hangs",
    "verify switchboard response headers for profile routing",
    "reduce token overhead through progressive disclosure defaults",
    "intent contract fields for workflow start",
    "show workflow run start intent contract requirements",
    "how to configure qdrant and hybrid routing in this repo",
    "nixos declarative runtime tool security policy pattern for hybrid coor",
    "verify semantic tool calling and tool security metadata",
)


def _is_synthetic_gap(query_text: str) -> bool:
    text = (query_text or "").strip().lower()
    if not text:
        return True
    if text in {"test", "nix", "ping", "health"}:
        return True
    synthetic_prefixes = (
        "analysis only task ",
        "analysis only:",
        "analysis task ",
        "analyze docs/",
        "please analyze and summarize docs/",
        "analyze and summarize docs/",
        "summarize docs/",
        "nixos-rag-test-probe-unique-sentinel",
        "fetch http://127.0.0.1",
        "fetch https://127.0.0.1",
        "fetch http://localhost",
        "curl http://127.0.0.1",
        "curl http://localhost",
        "get http://127.0.0.1",
        "get http://localhost",
    )
    return text.startswith(synthetic_prefixes)


def _normalize_gap_text(query_text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (query_text or "").strip().lower()).strip()


def _is_curated_stale_gap(query_text: str) -> bool:
    normalized = _normalize_gap_text(query_text)
    if not normalized:
        return True
    return any(pattern in normalized for pattern in _CURATED_STALE_GAP_PATTERNS)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class HintsEngine:
    """
    Ranked workflow hints engine for the NixOS AI stack.

    Provides hints to ALL agents (Claude, Codex, Qwen, Continue.dev, aider,
    humans) from a single source of truth.  Fully synchronous -- safe to import
    from async aiohttp servers and standalone CLI scripts alike.
    """

    def __init__(
        self,
        registry_path: Optional[Path] = None,
        gaps_jsonl_path: Optional[Path] = None,
        audit_log_path: Optional[Path] = None,
        report_json_path: Optional[Path] = None,
        hint_feedback_path: Optional[Path] = None,
    ) -> None:
        # Registry YAML: ai-stack/prompts/registry.yaml relative to this file's
        # parent.parent.parent (hybrid-coordinator -> mcp-servers -> ai-stack)
        if registry_path is None:
            self._registry_path = (
                Path(__file__).parent.parent.parent / "prompts" / "registry.yaml"
            )
        else:
            self._registry_path = registry_path

        if gaps_jsonl_path is None:
            self._gaps_path = Path("/var/log/nixos-ai-stack/query-gaps.jsonl")
        else:
            self._gaps_path = gaps_jsonl_path

        if audit_log_path is None:
            env_val = os.getenv("TOOL_AUDIT_LOG_PATH", "")
            candidate = Path(env_val) if env_val else Path("/var/log/nixos-ai-stack/tool-audit.jsonl")
            if not candidate.exists() and Path("/var/log/ai-audit-sidecar/tool-audit.jsonl").exists():
                candidate = Path("/var/log/ai-audit-sidecar/tool-audit.jsonl")
            self._audit_log_path = candidate
        else:
            self._audit_log_path = audit_log_path

        if report_json_path is None:
            report_env = os.getenv("AQ_REPORT_LATEST_JSON", "")
            self._report_json_path = (
                Path(report_env)
                if report_env
                else Path("/var/lib/ai-stack/hybrid/telemetry/latest-aq-report.json")
            )
        else:
            self._report_json_path = report_json_path

        if hint_feedback_path is None:
            fb_env = os.getenv("HINT_FEEDBACK_LOG_PATH", "")
            self._hint_feedback_path = (
                Path(fb_env)
                if fb_env
                else Path("/var/log/nixos-ai-stack/hint-feedback.jsonl")
            )
        else:
            self._hint_feedback_path = hint_feedback_path

        hint_audit_env = os.getenv("HINT_AUDIT_LOG_PATH", "")
        self._hint_audit_path = (
            Path(hint_audit_env)
            if hint_audit_env
            else Path("/var/log/nixos-ai-stack/hint-audit.jsonl")
        )
        self._div_repeat_window = self._parse_int_env("AI_HINT_DIVERSITY_REPEAT_WINDOW", 300, min_value=20)
        self._div_repeat_cap_pct = self._parse_float_env("AI_HINT_DIVERSITY_REPEAT_CAP_PCT", 45.0, min_value=10.0, max_value=100.0)
        self._div_repeat_min_count = self._parse_int_env("AI_HINT_DIVERSITY_REPEAT_MIN_COUNT", 5, min_value=1)
        self._div_type_max = self._parse_type_quota_env(
            "AI_HINT_DIVERSITY_TYPE_MAX",
            default="runtime_signal:2,prompt_template:1,gap_topic:2,workflow_rule:1,tool_warning:1,prompt_coaching:2",
        )
        self._div_type_min = self._parse_type_quota_env(
            "AI_HINT_DIVERSITY_TYPE_MIN",
            default="runtime_signal:1,gap_topic:1,workflow_rule:1,prompt_coaching:1",
        )
        self._feedback_db_enabled = (os.getenv("AI_HINT_FEEDBACK_DB_ENABLED", "true").strip().lower() != "false")
        self._feedback_db_ttl_seconds = self._parse_int_env("AI_HINT_FEEDBACK_DB_CACHE_TTL_SECONDS", 120, min_value=10)
        self._feedback_db_cache_loaded_at = 0.0
        self._feedback_db_cache: Dict[str, Dict[str, object]] = {}
        self._bandit_enabled = (os.getenv("AI_HINT_BANDIT_ENABLED", "true").strip().lower() != "false")
        self._bandit_min_events = self._parse_int_env("AI_HINT_BANDIT_MIN_EVENTS", 3, min_value=1)
        self._bandit_prior_alpha = self._parse_float_env("AI_HINT_BANDIT_PRIOR_ALPHA", 1.0, min_value=0.01, max_value=100.0)
        self._bandit_prior_beta = self._parse_float_env("AI_HINT_BANDIT_PRIOR_BETA", 1.0, min_value=0.01, max_value=100.0)
        self._bandit_exploration_weight = self._parse_float_env("AI_HINT_BANDIT_EXPLORATION_WEIGHT", 0.35, min_value=0.0, max_value=2.0)
        self._bandit_max_adjust = self._parse_float_env("AI_HINT_BANDIT_MAX_ADJUST", 0.12, min_value=0.0, max_value=1.0)
        self._bandit_confidence_floor = self._parse_float_env("AI_HINT_BANDIT_CONFIDENCE_FLOOR", 0.15, min_value=0.0, max_value=1.0)

    @staticmethod
    def _parse_int_env(name: str, default: int, min_value: int = 0) -> int:
        raw = os.getenv(name, "").strip()
        if not raw:
            return default
        try:
            value = int(raw)
            return max(min_value, value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _parse_float_env(name: str, default: float, min_value: float = 0.0, max_value: float = 100.0) -> float:
        raw = os.getenv(name, "").strip()
        if not raw:
            return default
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return default
        return max(min_value, min(max_value, value))

    @staticmethod
    def _parse_type_quota_env(name: str, default: str) -> Dict[str, int]:
        raw = os.getenv(name, "").strip() or default
        out: Dict[str, int] = {}
        for part in raw.split(","):
            seg = part.strip()
            if not seg or ":" not in seg:
                continue
            t, n = seg.split(":", 1)
            hint_type = t.strip().lower()
            try:
                limit = int(n.strip())
            except (TypeError, ValueError):
                continue
            if not hint_type or limit < 0:
                continue
            out[hint_type] = limit
        return out

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def rank(
        self,
        query: str,
        context: str = "",
        max_hints: int = 5,
        agent_type: str = "unknown",
    ) -> List[Hint]:
        """
        Return up to *max_hints* ranked Hint objects for the given *query*.

        Four sources are combined:
          A) Registry templates (weight 0.6)
          B) Query gaps from JSONL (weight 0.3)
          C) Static workflow rules from CLAUDE.md (weight 0.1)
          D) Runtime diagnostics (tool errors + aq-report recommendations)

        Results are deduplicated by id (first occurrence wins) and sorted by
        score descending.

        Parameters
        ----------
        query:
            The agent's current query or task description.
        context:
            Optional context string (e.g. file extension ".nix", "nixos").
            Used to boost NixOS-relevant hints.
        max_hints:
            Maximum number of hints to return (default 5).
        """
        query_tokens = _tokenize(query)
        context_lower = context.lower()

        source_a = self._hints_from_registry(query_tokens, context_lower)
        source_b = self._hints_from_gaps(query, query_tokens)
        source_c = self._hints_from_static_rules(query_tokens)
        source_d = self._hints_from_runtime_signals(query, query_tokens)
        source_e = self._hints_from_prompt_coaching(query, query_tokens, agent_type)

        feedback = self._load_hint_feedback_scores()
        db_feedback_profiles = self._load_db_feedback_profiles()
        preference_profile = self._load_agent_preference_profile(agent_type)
        combined: List[Hint] = source_e + source_d + source_a + source_b + source_c
        combined = [self._apply_efficiency_adjustment(h) for h in combined]
        combined = [self._apply_feedback_adjustment(h, feedback, db_feedback_profiles, query_tokens) for h in combined]
        combined = [self._apply_agent_preference_adjustment(h, preference_profile) for h in combined]
        usage_counts, usage_total = self._load_recent_hint_usage()
        overused_ids = self._compute_overused_hint_ids(usage_counts, usage_total)
        combined = [self._apply_repeat_penalty(h, usage_counts, usage_total, overused_ids) for h in combined]
        combined.sort(key=lambda h: h.score, reverse=True)

        seen: set = set()
        deduped: List[Hint] = []
        for hint in combined:
            if hint.id not in seen:
                seen.add(hint.id)
                deduped.append(hint)
        return self._select_with_diversity_policy(deduped, max_hints=max_hints, overused_ids=overused_ids)

    def _pg_dsn(self) -> str:
        host = os.getenv("POSTGRES_HOST", "127.0.0.1")
        port = os.getenv("POSTGRES_PORT", "5432")
        db = os.getenv("POSTGRES_DB", "aidb")
        user = os.getenv("POSTGRES_USER", "aidb")
        password = os.getenv("POSTGRES_PASSWORD", "")
        if not password:
            pw_file = Path(os.getenv("POSTGRES_PASSWORD_FILE", "/run/secrets/postgres_password"))
            try:
                password = pw_file.read_text(encoding="utf-8").strip()
            except Exception:
                password = ""
        return f"postgresql://{user}:{password}@{host}:{port}/{db}"

    def _load_db_feedback_profiles(self) -> Dict[str, Dict[str, object]]:
        if not self._feedback_db_enabled or psycopg is None:
            return {}
        now_ts = datetime.now(tz=timezone.utc).timestamp()
        if (now_ts - self._feedback_db_cache_loaded_at) < self._feedback_db_ttl_seconds:
            return self._feedback_db_cache
        dsn = self._pg_dsn()
        query = """
        SELECT hint_id, event_count, helpful_count, unhelpful_count,
               helpful_rate, mean_score, confidence, dominant_semantic_tags
        FROM hint_feedback_profiles
        WHERE event_count >= 2
        """
        out: Dict[str, Dict[str, object]] = {}
        try:
            conn = psycopg.connect(dsn, connect_timeout=2)
            cur = conn.execute(query)
            for row in cur.fetchall():
                hint_id = str(row[0] or "").strip()
                if not hint_id:
                    continue
                event_count = int(row[1] or 0)
                helpful_count = int(row[2] or 0)
                unhelpful_count = int(row[3] or 0)
                helpful_rate = float(row[4]) if row[4] is not None else None
                mean_score = float(row[5]) if row[5] is not None else None
                confidence = float(row[6]) if row[6] is not None else 0.0
                dominant_tags = row[7] if isinstance(row[7], list) else []
                db_signal = 0.0
                if helpful_rate is not None:
                    db_signal += (helpful_rate * 2.0 - 1.0) * 0.7
                if mean_score is not None:
                    db_signal += mean_score * 0.3
                db_signal *= max(0.0, min(1.0, confidence))
                out[hint_id] = {
                    "signal": max(-1.0, min(1.0, db_signal)),
                    "event_count": event_count,
                    "helpful_count": helpful_count,
                    "unhelpful_count": unhelpful_count,
                    "confidence": max(0.0, min(1.0, confidence)),
                    "dominant_tags": [str(t).strip().lower() for t in dominant_tags if str(t).strip()],
                }
            conn.close()
        except Exception:
            out = {}
        self._feedback_db_cache = out
        self._feedback_db_cache_loaded_at = now_ts
        return out

    def _load_recent_hint_usage(self) -> Tuple[Counter, int]:
        counts: Counter = Counter()
        if not self._hint_audit_path.exists():
            return counts, 0
        try:
            rows = self._hint_audit_path.read_text(encoding="utf-8").splitlines()[-self._div_repeat_window:]
        except Exception:
            return counts, 0
        for raw in rows:
            if not raw.strip():
                continue
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError:
                continue
            hid = str(obj.get("hint_id", "") or "").strip()
            if hid:
                counts[hid] += 1
        return counts, int(sum(counts.values()))

    def _compute_overused_hint_ids(self, usage_counts: Counter, usage_total: int) -> Set[str]:
        overused: Set[str] = set()
        if usage_total <= 0:
            return overused
        cap_ratio = self._div_repeat_cap_pct / 100.0
        for hid, count in usage_counts.items():
            if count < self._div_repeat_min_count:
                continue
            if (count / usage_total) >= cap_ratio:
                overused.add(str(hid))
        return overused

    def _apply_repeat_penalty(
        self,
        hint: Hint,
        usage_counts: Counter,
        usage_total: int,
        overused_ids: Set[str],
    ) -> Hint:
        if usage_total <= 0 or hint.id not in overused_ids:
            return hint
        share = usage_counts.get(hint.id, 0) / max(usage_total, 1)
        # Penalty scales with over-concentration and increases more aggressively
        # for severe dominance so repeated hints rotate out sooner.
        over = max(0.0, share - (self._div_repeat_cap_pct / 100.0))
        penalty = min(0.32, max(0.08, over * 0.85))
        if share >= 0.75:
            penalty = min(0.38, penalty + 0.06)
        adjusted = max(0.0, hint.score - penalty)
        reason = f"{hint.reason}; diversity_repeat_penalty=-{penalty:.2f}".strip("; ")
        return Hint(
            id=hint.id,
            type=hint.type,
            title=hint.title,
            score=adjusted,
            snippet=hint.snippet,
            reason=reason,
            tags=hint.tags,
            agent_hints=hint.agent_hints,
        )

    def _select_with_diversity_policy(
        self,
        deduped_hints: List[Hint],
        max_hints: int,
        overused_ids: Set[str],
    ) -> List[Hint]:
        if max_hints <= 0 or not deduped_hints:
            return []

        type_counts: Dict[str, int] = {}
        selected: List[Hint] = []
        selected_ids: Set[str] = set()
        remaining = list(deduped_hints)

        def hint_type(h: Hint) -> str:
            return (h.type or "unknown").strip().lower() or "unknown"

        def can_take(h: Hint) -> bool:
            t = hint_type(h)
            max_for_type = self._div_type_max.get(t)
            if max_for_type is None:
                return True
            return type_counts.get(t, 0) < max_for_type

        def take(h: Hint) -> None:
            t = hint_type(h)
            type_counts[t] = type_counts.get(t, 0) + 1
            selected.append(h)
            selected_ids.add(h.id)

        # Pass 1: satisfy per-type minimum quotas where candidates exist.
        for req_type, req_count in self._div_type_min.items():
            if len(selected) >= max_hints:
                break
            if req_count <= 0:
                continue
            available = [h for h in remaining if hint_type(h) == req_type and can_take(h)]
            if not available:
                continue
            target = min(req_count, len(available), max_hints - len(selected))
            for h in available:
                if target <= 0 or len(selected) >= max_hints:
                    break
                if h.id in selected_ids or not can_take(h):
                    continue
                take(h)
                target -= 1

        available_non_overused = [
            h for h in remaining
            if h.id not in selected_ids and h.id not in overused_ids and can_take(h)
        ]

        # Pass 2: fill remaining with non-overused first while honoring type max.
        deferred_overused: List[Hint] = []
        for h in remaining:
            if len(selected) >= max_hints:
                break
            if h.id in selected_ids or not can_take(h):
                continue
            if h.id in overused_ids:
                deferred_overused.append(h)
                continue
            take(h)

        # Pass 3: if still not enough, allow overused hints as fallback.
        # When enough non-overused candidates exist, keep dominant hints out
        # of the final set entirely for this ranking window.
        if len(available_non_overused) >= max_hints:
            return selected[:max_hints]
        for h in deferred_overused:
            if len(selected) >= max_hints:
                break
            if h.id in selected_ids or not can_take(h):
                continue
            # Prefer not to refill with overused hints when we already have a
            # minimally diverse set.
            if len(selected) >= max(1, min(max_hints, len(self._div_type_min))):
                break
            take(h)

        return selected

    def _apply_efficiency_adjustment(self, hint: Hint) -> Hint:
        """
        Bias toward hints that are concise, tool/action-oriented, and likely to
        reduce downstream token usage through concrete execution steps.
        """
        snippet = (hint.snippet or "").strip()
        title = (hint.title or "").strip()
        reason = (hint.reason or "").strip()
        text = " ".join([title, snippet, reason]).lower()

        token_count = max(1, len(_tokenize(snippet)))
        has_command = bool(_COMMAND_RE.search(snippet))
        tool_words = any(k in text for k in (
            "run ", "scripts/", "/hints", "/query", "systemctl", "nixos-rebuild",
            "aq-report", "check-", "validate", "retry", "diagnose", "import",
        ))
        uncertainty_words = any(k in text for k in ("consider", "maybe", "could", "might"))

        efficiency = 0.55
        if has_command:
            efficiency += 0.20
        if tool_words:
            efficiency += 0.18
        if token_count <= 40:
            efficiency += 0.10
        elif token_count > 90:
            efficiency -= 0.12
        if uncertainty_words:
            efficiency -= 0.06

        efficiency = max(0.0, min(1.0, efficiency))
        # Keep source relevance dominant, but reward low-token actionable hints.
        adjusted_score = min(1.0, hint.score * 0.82 + efficiency * 0.18)
        if adjusted_score > hint.score:
            reason = f"{reason}; efficiency_bias=+{(adjusted_score - hint.score):.2f}".strip("; ")
        return Hint(
            id=hint.id,
            type=hint.type,
            title=hint.title,
            score=adjusted_score,
            snippet=hint.snippet,
            reason=reason or hint.reason,
            tags=hint.tags,
            agent_hints=hint.agent_hints,
        )

    def _load_hint_feedback_scores(self) -> Dict[str, float]:
        """
        Build per-hint feedback signal in [-1.0, 1.0] from:
        - hint-audit adoption outcomes (accepted true/false)
        - explicit /hints/feedback records (helpful bool / score)
        """
        stats: Dict[str, Dict[str, int]] = {}

        def add(hint_id: str, positive: int, negative: int) -> None:
            if not hint_id:
                return
            row = stats.setdefault(hint_id, {"pos": 0, "neg": 0})
            row["pos"] += max(0, int(positive))
            row["neg"] += max(0, int(negative))

        try:
            hint_audit_path = Path("/var/log/nixos-ai-stack/hint-audit.jsonl")
            if hint_audit_path.exists():
                for raw in hint_audit_path.read_text(encoding="utf-8").splitlines()[-4000:]:
                    if not raw.strip():
                        continue
                    try:
                        obj = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    hid = str(obj.get("hint_id", "") or "").strip()
                    accepted = bool(obj.get("hint_accepted", False))
                    add(hid, 1 if accepted else 0, 0 if accepted else 1)
        except Exception:
            pass

        try:
            if self._hint_feedback_path.exists():
                for raw in self._hint_feedback_path.read_text(encoding="utf-8").splitlines()[-4000:]:
                    if not raw.strip():
                        continue
                    try:
                        obj = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    hid = str(obj.get("hint_id", "") or "").strip()
                    if "helpful" in obj:
                        helpful = bool(obj.get("helpful"))
                        add(hid, 1 if helpful else 0, 0 if helpful else 1)
                        continue
                    try:
                        score = float(obj.get("score", 0.0))
                    except (TypeError, ValueError):
                        score = 0.0
                    add(hid, 1 if score > 0 else 0, 1 if score < 0 else 0)
        except Exception:
            pass

        out: Dict[str, float] = {}
        for hid, row in stats.items():
            pos = int(row.get("pos", 0))
            neg = int(row.get("neg", 0))
            total = pos + neg
            if total <= 0:
                continue
            out[hid] = (pos - neg) / total
        return out

    def _apply_feedback_adjustment(
        self,
        hint: Hint,
        feedback_scores: Dict[str, float],
        db_feedback_profiles: Optional[Dict[str, Dict[str, object]]] = None,
        query_tokens: Optional[List[str]] = None,
    ) -> Hint:
        signal = float(feedback_scores.get(hint.id, 0.0))
        db_profile = (db_feedback_profiles or {}).get(hint.id, {})
        db_signal_raw = db_profile.get("signal")
        db_conf_raw = db_profile.get("confidence")
        db_signal = float(db_signal_raw) if isinstance(db_signal_raw, (int, float)) else None
        db_conf = float(db_conf_raw) if isinstance(db_conf_raw, (int, float)) else 0.0
        if db_signal is not None:
            signal = signal * 0.6 + db_signal * 0.4 if abs(signal) > 0.0 else db_signal * max(0.4, min(1.0, db_conf))
            dominant_tags = db_profile.get("dominant_tags", [])
            if isinstance(dominant_tags, list):
                lowered = {str(t).strip().lower() for t in dominant_tags}
                if "relevance_low" in lowered or "helpful_false" in lowered:
                    signal -= 0.05
                if "actionable" in lowered or "relevance_high" in lowered:
                    signal += 0.04
        bandit_adjust = 0.0
        bandit_reason = ""
        if self._bandit_enabled and db_profile:
            bandit_adjust, bandit_reason = self._bandit_adjustment(db_profile, query_tokens or [], hint)
            signal += bandit_adjust
        signal = max(-1.0, min(1.0, signal))
        if abs(signal) < 0.01:
            return hint
        adjusted_score = max(0.0, min(1.0, hint.score + signal * 0.15))
        reason = hint.reason
        if adjusted_score != hint.score:
            reason = f"{reason}; feedback_signal={signal:+.2f}".strip("; ")
        if db_signal is not None and adjusted_score != hint.score:
            reason = f"{reason}; feedback_db_signal={db_signal:+.2f}; feedback_db_conf={db_conf:.2f}".strip("; ")
        if bandit_reason and adjusted_score != hint.score:
            reason = f"{reason}; {bandit_reason}".strip("; ")
        return Hint(
            id=hint.id,
            type=hint.type,
            title=hint.title,
            score=adjusted_score,
            snippet=hint.snippet,
            reason=reason,
            tags=hint.tags,
            agent_hints=hint.agent_hints,
        )

    def _bandit_context_bonus(self, query_tokens: List[str], dominant_tags: Set[str], hint: Hint) -> float:
        q = {t.strip().lower() for t in query_tokens if t and len(t) >= 3}
        if not q:
            return 0.0
        bonus = 0.0
        if q.intersection({"error", "failed", "timeout", "traceback", "fix"}) and "tool_error" in dominant_tags:
            bonus += 0.12
        if q.intersection({"service", "deploy", "nixos", "systemd"}) and "actionable" in dominant_tags:
            bonus += 0.08
        if q.intersection({"relevant", "quality", "hint", "improve"}) and "relevance_high" in dominant_tags:
            bonus += 0.06
        if "irrelevant" in q and "relevance_low" in dominant_tags:
            bonus += 0.1
        hint_tags = {str(t).strip().lower() for t in hint.tags if str(t).strip()}
        if q.intersection(hint_tags):
            bonus += 0.04
        return max(-0.25, min(0.25, bonus))

    def _bandit_adjustment(self, db_profile: Dict[str, object], query_tokens: List[str], hint: Hint) -> Tuple[float, str]:
        event_count = int(db_profile.get("event_count", 0) or 0)
        helpful_count = int(db_profile.get("helpful_count", 0) or 0)
        unhelpful_count = int(db_profile.get("unhelpful_count", 0) or 0)
        if event_count < self._bandit_min_events:
            return 0.0, ""
        alpha = self._bandit_prior_alpha + max(0, helpful_count)
        beta = self._bandit_prior_beta + max(0, unhelpful_count)
        posterior_mean = alpha / max(1e-9, alpha + beta)
        total_trials = max(1, event_count)
        exploration = math.sqrt((2.0 * math.log(total_trials + 2.0)) / (total_trials + 1.0))
        dominant = db_profile.get("dominant_tags", [])
        dominant_tags = {str(t).strip().lower() for t in dominant} if isinstance(dominant, list) else set()
        context_bonus = self._bandit_context_bonus(query_tokens, dominant_tags, hint)
        confidence_raw = db_profile.get("confidence")
        confidence = float(confidence_raw) if isinstance(confidence_raw, (int, float)) else 0.0
        confidence = max(self._bandit_confidence_floor, min(1.0, confidence))
        arm_value = ((posterior_mean - 0.5) * 2.0) + (self._bandit_exploration_weight * exploration) + context_bonus
        arm_value = max(-1.0, min(1.0, arm_value))
        adjust = max(-self._bandit_max_adjust, min(self._bandit_max_adjust, arm_value * self._bandit_max_adjust * confidence))
        if abs(adjust) < 0.005:
            return 0.0, ""
        return adjust / 0.15, (
            f"bandit_adj={adjust:+.3f}; bandit_mean={posterior_mean:.3f}; "
            f"bandit_explore={exploration:.3f}; bandit_ctx={context_bonus:+.3f}; bandit_conf={confidence:.2f}"
        )

    def _load_agent_preference_profile(self, agent_type: str) -> Dict[str, Set[str]]:
        profile: Dict[str, Set[str]] = {
            "preferred_tools": set(),
            "preferred_data_sources": set(),
            "preferred_hint_types": set(),
            "preferred_tags": set(),
        }
        agent = (agent_type or "").strip().lower() or "unknown"
        if not self._hint_feedback_path.exists():
            return profile
        try:
            rows = self._hint_feedback_path.read_text(encoding="utf-8").splitlines()[-4000:]
        except Exception:
            return profile

        counts: Dict[str, Dict[str, int]] = {
            "preferred_tools": {},
            "preferred_data_sources": {},
            "preferred_hint_types": {},
            "preferred_tags": {},
        }

        def add(kind: str, value: str) -> None:
            text = (value or "").strip().lower()
            if not text:
                return
            bucket = counts[kind]
            bucket[text] = int(bucket.get(text, 0)) + 1

        for raw in rows:
            if not raw.strip():
                continue
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError:
                continue
            row_agent = str(obj.get("agent", "") or "").strip().lower() or "unknown"
            if row_agent != agent:
                continue
            prefs = obj.get("agent_preferences", {})
            if not isinstance(prefs, dict):
                continue
            for k in ("preferred_tools", "preferred_data_sources", "preferred_hint_types", "preferred_tags"):
                items = prefs.get(k, [])
                if isinstance(items, list):
                    for item in items:
                        add(k, str(item))

        for kind, bucket in counts.items():
            for key, n in bucket.items():
                if n >= 2:
                    profile[kind].add(key)
        return profile

    def _apply_agent_preference_adjustment(self, hint: Hint, profile: Dict[str, Set[str]]) -> Hint:
        boost = 0.0
        hint_type = (hint.type or "").strip().lower()
        if hint_type and hint_type in profile.get("preferred_hint_types", set()):
            boost += 0.08

        tags = {str(t).strip().lower() for t in (hint.tags or []) if str(t).strip()}
        if tags.intersection(profile.get("preferred_tags", set())):
            boost += 0.06

        text = f"{hint.title} {hint.snippet} {hint.reason}".lower()
        if any(t in text for t in profile.get("preferred_tools", set())):
            boost += 0.05
        if any(s in text for s in profile.get("preferred_data_sources", set())):
            boost += 0.04

        if boost <= 0.0:
            return hint
        adjusted = min(1.0, hint.score + boost)
        reason = f"{hint.reason}; agent_preference_boost=+{boost:.2f}".strip("; ")
        return Hint(
            id=hint.id,
            type=hint.type,
            title=hint.title,
            score=adjusted,
            snippet=hint.snippet,
            reason=reason,
            tags=hint.tags,
            agent_hints=hint.agent_hints,
        )

    def to_dict(self, hint: Hint, include_debug_metadata: bool = True) -> dict:
        """Return a JSON-serialisable dict for *hint*."""
        d: dict = {
            "id": hint.id,
            "type": hint.type,
            "title": hint.title,
            "score": round(hint.score, 4),
            "snippet": hint.snippet,
        }
        if include_debug_metadata and hint.reason:
            d["reason"] = hint.reason
        if include_debug_metadata and hint.tags:
            d["tags"] = hint.tags
        if include_debug_metadata and hint.agent_hints:
            d["agent_hints"] = hint.agent_hints
        return d

    def _compact_missing_fields(self, missing_fields: object, limit: int = 3) -> Dict[str, object]:
        fields = [str(item).strip() for item in (missing_fields or []) if str(item).strip()]
        return {
            "missing_fields": fields[:limit],
            "missing_count": len(fields),
        }

    def _compact_prompt_coaching_payload(self, prompt_coaching: Dict[str, object]) -> Dict[str, object]:
        """Keep default prompt coaching small on hint surfaces."""
        token_discipline = prompt_coaching.get("token_discipline", {})
        token_plan = {
            "spend_tier": str(token_discipline.get("spend_tier", "lean") or "lean"),
            "recommended_input_budget": str(token_discipline.get("recommended_input_budget", "") or "").strip(),
            "cloud_when": str(token_discipline.get("cloud_when", "") or "").strip(),
        }
        compact = {
            "score": float(prompt_coaching.get("score", 0.0) or 0.0),
            "recommended_agent": str(prompt_coaching.get("recommended_agent", "codex") or "codex"),
            "token_discipline": token_plan,
            "suggested_prompt": str(prompt_coaching.get("suggested_prompt", "") or "").strip(),
        }
        compact.update(self._compact_missing_fields(prompt_coaching.get("missing_fields", [])))
        return compact

    def rank_as_dict(
        self,
        query: str,
        context: str = "",
        max_hints: int = 5,
        agent_type: str = "unknown",
        include_debug_metadata: Optional[bool] = None,
    ) -> dict:
        """Return ranked hints as a JSON-serialisable dict."""
        hints = self.rank(query, context=context, max_hints=max_hints, agent_type=agent_type)
        profile = self._load_agent_preference_profile(agent_type)
        usage_counts, usage_total = self._load_recent_hint_usage()
        overused_ids = sorted(self._compute_overused_hint_ids(usage_counts, usage_total))
        db_profiles = self._load_db_feedback_profiles()
        prompt_coaching = self._build_prompt_coaching(query, agent_type)
        output_type_counts: Dict[str, int] = {}
        for h in hints:
            t = (h.type or "unknown").strip().lower() or "unknown"
            output_type_counts[t] = output_type_counts.get(t, 0) + 1
        if include_debug_metadata is None:
            include_debug_metadata = os.getenv("AI_HINTS_INCLUDE_DEBUG_METADATA", "false").strip().lower() == "true"
        prompt_coaching_payload = (
            prompt_coaching
            if include_debug_metadata
            else self._compact_prompt_coaching_payload(prompt_coaching)
        )
        result = {
            "hints": [self.to_dict(h, include_debug_metadata=include_debug_metadata) for h in hints],
            "generated_at": datetime.now(tz=timezone.utc).isoformat(),
            "query": query,
            "agent_type": agent_type,
            "prompt_coaching": prompt_coaching_payload,
            "feedback_contract": {
                "endpoint": "/hints/feedback",
                "required_any_of": ["helpful", "score"],
                "required": ["hint_id"],
            },
        }
        if include_debug_metadata:
            result["debug_metadata"] = {
                "diversity_policy": {
                    "repeat_window": self._div_repeat_window,
                    "repeat_cap_pct": self._div_repeat_cap_pct,
                    "repeat_min_count": self._div_repeat_min_count,
                    "type_min": self._div_type_min,
                    "type_max": self._div_type_max,
                },
                "diversity_runtime": {
                    "recent_injections": usage_total,
                    "overused_hint_ids": overused_ids,
                    "output_type_counts": output_type_counts,
                },
                "feedback_db": {
                    "enabled": self._feedback_db_enabled,
                    "available": bool(db_profiles),
                    "profile_count": len(db_profiles),
                    "cache_ttl_seconds": self._feedback_db_ttl_seconds,
                },
                "bandit_policy": {
                    "enabled": self._bandit_enabled,
                    "min_events": self._bandit_min_events,
                    "prior_alpha": self._bandit_prior_alpha,
                    "prior_beta": self._bandit_prior_beta,
                    "exploration_weight": self._bandit_exploration_weight,
                    "max_adjust": self._bandit_max_adjust,
                    "confidence_floor": self._bandit_confidence_floor,
                },
                "agent_preference_profile": {
                    "preferred_tools": sorted(profile.get("preferred_tools", set())),
                    "preferred_data_sources": sorted(profile.get("preferred_data_sources", set())),
                    "preferred_hint_types": sorted(profile.get("preferred_hint_types", set())),
                    "preferred_tags": sorted(profile.get("preferred_tags", set())),
                },
                "feedback_guide": {
                "purpose": "Improve future hint ranking by reporting what helped or wasted effort.",
                "when_to_send": [
                    "after using an injected hint",
                    "when a hint was irrelevant or low-value",
                ],
                "minimal_payload": {
                    "hint_id": "<id>",
                    "helpful": True,
                    "agent": "<agent-name>",
                },
                "advocacy_payload": {
                    "hint_id": "<id>",
                    "score": 1.0,
                    "agent_preferences": {
                        "preferred_tools": ["route_search", "workflow_plan"],
                        "preferred_data_sources": ["tool_audit", "aq_report"],
                        "preferred_hint_types": ["runtime_signal"],
                        "preferred_tags": ["efficiency", "diagnostics"],
                    },
                },
                },
                "advocacy_ranking": {
                    "signals_used": [
                        "hint_adoption_outcomes",
                        "explicit_helpful_or_score_feedback",
                        "agent_preferences_profile",
                        "efficiency_bias",
                    ],
                    "effect": "useful hints trend up, unhelpful hints trend down, agent-preferred hint styles are prioritized",
                },
                "prsi_contract": {
                    "purpose": "Budget-aware pessimistic recursive self-improvement without always-on dual prompt execution.",
                    "policy_file": os.getenv("PRSI_POLICY_FILE", "config/runtime-prsi-policy.json"),
                    "state_file": os.getenv("PRSI_STATE_PATH", "/var/lib/nixos-ai-stack/prsi/runtime-state.json"),
                    "loop": [
                        "1) run normal single-path execution with hints",
                        "2) send hint feedback + agent_preferences when useful/unhelpful",
                        "3) run policy-gated PRSI cycle (sampled counterfactual only)",
                        "4) apply low-risk actions under token cap; escalate only on degradation",
                    ],
                    "operator_commands": {
                        "sync": "python scripts/automation/prsi-orchestrator.py sync --since=1d",
                        "list": "python scripts/automation/prsi-orchestrator.py list",
                        "cycle_dry_run": "python scripts/automation/prsi-orchestrator.py cycle --dry-run",
                    },
                    "budget_controls": [
                        "remote_token_cap_daily",
                        "counterfactual.sample_rate",
                        "counterfactual.max_samples_per_day",
                        "max_execute_per_cycle",
                    ],
                },
            }
        return result

    def prompt_coaching_as_dict(self, query: str, agent_type: str = "unknown") -> Dict[str, object]:
        """Return prompt-structure coaching without ranking full hint sources."""
        return self._build_prompt_coaching(query, agent_type)

    # ------------------------------------------------------------------
    # Source A -- registry templates
    # ------------------------------------------------------------------

    def _hints_from_registry(
        self, query_tokens: List[str], context_lower: str
    ) -> List[Hint]:
        if yaml is None:
            return []

        try:
            with open(self._registry_path, "r", encoding="utf-8") as fh:
                data = yaml.safe_load(fh)
        except Exception:
            return []

        if not isinstance(data, (dict, list)):
            return []

        # Registry may be a dict with a top-level "prompts" list, or a bare list.
        if isinstance(data, list):
            entries = data
        else:
            entries = data.get("prompts") or data.get("templates") or []

        hints: List[Hint] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue

            entry_id = str(entry.get("id") or entry.get("name") or "")
            if not entry_id:
                continue

            title = str(entry.get("title") or entry.get("name") or entry_id)
            tags: List[str] = list(entry.get("tags") or [])
            description = str(entry.get("description") or "").lower()
            template_text = str(entry.get("template") or entry.get("content") or "")
            mean_score_raw = entry.get("mean_score")

            try:
                mean_score = float(mean_score_raw) if mean_score_raw is not None else 0.5
            except (TypeError, ValueError):
                mean_score = 0.5
            mean_score = max(0.0, min(1.0, mean_score))

            # Tag overlap bonus
            tags_lower = [t.lower() for t in tags]
            overlap_count = sum(
                1
                for tok in query_tokens
                if tok in tags_lower or tok in description
            )
            tag_overlap_bonus = min(1.0 + overlap_count * 0.15, 1.6)

            base_score = mean_score * tag_overlap_bonus

            # NixOS context boost
            nix_boost = 0.0
            if context_lower and any(
                "nixos" in t or t == "nix" for t in tags_lower
            ):
                if "nix" in context_lower or "nixos" in context_lower:
                    nix_boost = 0.2

            score = min(1.0, base_score * 0.6 + nix_boost)

            snippet = template_text.strip()[:200]
            reason = f"Registry score {score:.0%}, tags: {tags}"

            hints.append(
                Hint(
                    id=f"registry_{entry_id}",
                    type="prompt_template",
                    title=title,
                    score=score,
                    snippet=snippet,
                    reason=reason,
                    tags=tags,
                    agent_hints={},
                )
            )

        return hints

    # ------------------------------------------------------------------
    # Source D -- runtime diagnostics (telemetry + errors)
    # ------------------------------------------------------------------

    def _hints_from_runtime_signals(self, query: str, query_tokens: List[str]) -> List[Hint]:
        hints: List[Hint] = []
        hints.extend(self._hints_from_latest_report(query, query_tokens))
        hints.extend(self._hints_from_tool_audit_errors(query, query_tokens))
        return hints

    def _choose_recommended_agent(self, query_lower: str, agent_type: str) -> str:
        if any(tok in query_lower for tok in ("architecture", "tradeoff", "policy", "risk", "design")):
            return "claude"
        if any(tok in query_lower for tok in ("patch", "implement", "edit", "refactor", "test scaffold", "wire")):
            return "qwen"
        if any(tok in query_lower for tok in ("review", "integrate", "verify", "gate", "acceptance", "commit")):
            return "codex"
        if any(tok in query_lower for tok in ("small edit", "rename", "one file", "targeted edit", "inline fix")):
            return "aider"
        agent = (agent_type or "").strip().lower()
        return agent if agent in _AGENT_STRENGTHS else "codex"

    def _estimate_prompt_tokens(self, text: str) -> int:
        return max(1, (len(text or "") + 3) // 4)

    def _build_token_discipline(
        self,
        query_text: str,
        query_lower: str,
        missing: List[str],
        recommended_agent: str,
    ) -> Dict[str, object]:
        estimated_input_tokens = self._estimate_prompt_tokens(query_text)
        remote_warranted = any(
            token in query_lower
            for token in (
                "architecture",
                "tradeoff",
                "compare",
                "migration",
                "cross-file",
                "multi-file",
                "deep analysis",
                "research",
                "provider",
                "openrouter",
                "large context",
            )
        )
        if remote_warranted or estimated_input_tokens >= 350:
            spend_tier = "deep"
            recommended_budget = 2200
            rationale = "Use higher token spend only for architecture, broad comparisons, or large-context execution."
        elif missing or estimated_input_tokens <= 120:
            spend_tier = "lean"
            recommended_budget = 600
            rationale = "Keep the first pass compact until the task shape and failing layer are concrete."
        else:
            spend_tier = "standard"
            recommended_budget = 1200
            rationale = "Use a bounded implementation budget once the prompt has objective, context, and validation."

        return {
            "estimated_input_tokens": estimated_input_tokens,
            "spend_tier": spend_tier,
            "recommended_input_budget": recommended_budget,
            "remote_warranted": remote_warranted,
            "rationale": rationale,
            "tactics": [
                "Start lean with hints/retrieval before pasting broad background.",
                "Escalate only after a concrete gap, failed lean pass, or proven high-context need.",
                f"Keep reusable prefixes compact for provider-side prompt caching and route deep work to {recommended_agent} only when warranted.",
            ],
        }

    def _build_prompt_coaching(self, query: str, agent_type: str) -> Dict[str, object]:
        query_text = str(query or "").strip()
        query_lower = query_text.lower()
        present: Dict[str, bool] = {}
        missing: List[str] = []
        for key, label, tokens in _PROMPT_COACHING_FIELDS:
            hit = any(token in query_lower for token in tokens)
            if key == "objective" and len(_tokenize(query_text)) >= 6:
                hit = hit or True
            present[key] = hit
            if not hit:
                missing.append(label)

        score = round(sum(1 for value in present.values() if value) / max(1, len(_PROMPT_COACHING_FIELDS)), 4)
        recommended_agent = self._choose_recommended_agent(query_lower, agent_type)
        strength = _AGENT_STRENGTHS.get(recommended_agent, _AGENT_STRENGTHS["codex"])
        token_discipline = self._build_token_discipline(query_text, query_lower, missing, recommended_agent)
        compact_template = (
            "Objective | Constraints | Context | Validation"
            f" | Route: {recommended_agent}"
            f" | Token plan: {token_discipline['spend_tier']} first"
        )
        return {
            "score": score,
            "present_fields": [label for key, label, _ in _PROMPT_COACHING_FIELDS if present.get(key)],
            "missing_fields": missing,
            "recommended_agent": recommended_agent,
            "recommended_agent_rationale": strength["best_for"],
            "agent_prompt_shape": strength["prompt_shape"],
            "token_discipline": token_discipline,
            "suggested_prompt": compact_template,
            "teaching_points": [
                "Lead with the outcome, not background history.",
                "Name constraints and validation so agents do not infer them.",
                "Use routing flexibility for fit, not as permission for unbounded token spend.",
            ],
        }

    def _hints_from_prompt_coaching(
        self,
        query: str,
        query_tokens: List[str],
        agent_type: str,
    ) -> List[Hint]:
        coaching = self._build_prompt_coaching(query, agent_type)
        missing = coaching.get("missing_fields", [])
        if not isinstance(missing, list):
            missing = []
        score = float(coaching.get("score", 0.0) or 0.0)
        recommended_agent = str(coaching.get("recommended_agent", "codex") or "codex")
        agent_strength = _AGENT_STRENGTHS.get(recommended_agent, _AGENT_STRENGTHS["codex"])
        token_discipline = coaching.get("token_discipline", {})
        if not isinstance(token_discipline, dict):
            token_discipline = {}
        hints: List[Hint] = []

        if missing:
            hints.append(
                Hint(
                    id="prompt_coaching_structure",
                    type="prompt_coaching",
                    title="Strengthen the request structure before execution",
                    score=min(0.98, 0.64 + (1.0 - score) * 0.28),
                    snippet=(
                        "Missing pieces: "
                        + ", ".join(str(item) for item in missing[:3])
                        + ". Use: Objective -> Constraints -> Context -> Validation -> Agent routing."
                    ),
                    reason="Prompt-shape coaching detected missing execution-critical fields",
                    tags=["prompting", "coaching", "structure", "education"],
                    agent_hints={
                        "human": "Rewrite the request using the suggested prompt skeleton before dispatch.",
                        "codex": "Surface missing fields back to the user before large execution branches.",
                        "qwen": "Ask for files + expected behavior when implementation scope is underspecified.",
                        "claude": "Use this to coach prompt writers toward clearer decision inputs.",
                    },
                )
            )

        if len(query_tokens) >= 3:
            hints.append(
                Hint(
                    id=f"prompt_coaching_agent_{recommended_agent}",
                    type="prompt_coaching",
                    title=f"Route this work to {recommended_agent} for best leverage",
                    score=0.66 if missing else 0.58,
                    snippet=(
                        f"{recommended_agent} is strongest for {agent_strength['best_for']}. "
                        f"Prompt shape: {agent_strength['prompt_shape']}"
                    ),
                    reason="Agent-strength coaching based on the task shape and routing intent",
                    tags=["prompting", "coaching", "agent-routing", recommended_agent],
                    agent_hints={recommended_agent: "Use this task shape as the default routing profile."},
                )
            )

        if token_discipline:
            spend_tier = str(token_discipline.get("spend_tier", "lean") or "lean")
            recommended_budget = int(token_discipline.get("recommended_input_budget", 0) or 0)
            rationale = str(token_discipline.get("rationale", "") or "")
            hints.append(
                Hint(
                    id=f"prompt_coaching_tokens_{spend_tier}",
                    type="prompt_coaching",
                    title="Apply a token-spend plan before broadening the prompt",
                    score=0.63 if spend_tier == "lean" else 0.57,
                    snippet=(
                        f"Start {spend_tier} with ~{recommended_budget} input tokens max. "
                        f"{rationale}"
                    ).strip(),
                    reason="Token-discipline coaching keeps cloud and remote routing effective without wasting context budget",
                    tags=["prompting", "coaching", "token-discipline", spend_tier],
                    agent_hints={
                        "human": "Keep the first request compact and escalate only after a concrete failure or missing signal.",
                        "codex": "Enforce progressive disclosure before loading extra docs or expanding context.",
                        "qwen": "Request the smallest file set and expected behavior before spending larger context budgets.",
                        "claude": "Use deeper token budgets only for architecture or tradeoff work that clearly needs them.",
                    },
                )
            )

        return hints

    def _hints_from_latest_report(self, query: str, query_tokens: List[str]) -> List[Hint]:
        try:
            data = json.loads(self._report_json_path.read_text(encoding="utf-8"))
        except Exception:
            return []
        if not isinstance(data, dict):
            return []

        query_lower = (query or "").lower()
        hints: List[Hint] = []

        recommendations = data.get("recommendations", [])
        if isinstance(recommendations, list):
            for idx, rec in enumerate(recommendations[:3]):
                text = str(rec or "").strip()
                if not text:
                    continue
                rec_lower = text.lower()
                token_match = any(tok in rec_lower for tok in query_tokens if len(tok) >= 4)
                fuzzy = _longest_common_substring_len(query_lower, rec_lower) / max(len(query_lower), len(rec_lower), 1)
                if token_match or fuzzy >= 0.18:
                    hints.append(
                        Hint(
                            id=f"runtime_recommendation_{idx+1}",
                            type="runtime_signal",
                            title="Live report recommendation",
                            score=min(0.95, 0.70 + fuzzy),
                            snippet=text[:220],
                            reason="Matched active aq-report recommendation for current query context",
                            tags=["runtime", "recommendation", "report"],
                            agent_hints={},
                        )
                    )

        intent = data.get("intent_contract_compliance", {})
        if isinstance(intent, dict):
            cov = intent.get("contract_coverage_pct")
            try:
                cov_f = float(cov)
            except (TypeError, ValueError):
                cov_f = None
            if cov_f is not None and cov_f < 80 and any(t in query_lower for t in ("workflow", "run", "plan", "agent")):
                hints.append(
                    Hint(
                        id="runtime_intent_contract_coverage",
                        type="runtime_signal",
                        title="Intent-contract coverage is below target",
                        score=0.82,
                        snippet=(
                            f"Current intent-contract coverage is {cov_f:.1f}%. "
                            "Include intent_contract fields on workflow start "
                            "(user_intent, definition_of_done, depth_expectation, spirit_constraints, no_early_exit_without)."
                        ),
                        reason="Low coverage in latest runtime telemetry",
                        tags=["runtime", "workflow", "intent_contract"],
                        agent_hints={},
                    )
                )

        rag_posture = data.get("rag_posture", {})
        if isinstance(rag_posture, dict) and rag_posture.get("available"):
            rag_status = str(rag_posture.get("status", "unknown") or "unknown").strip().lower()
            recent_calls = int(rag_posture.get("recent_retrieval_calls", 0) or 0)
            cache_context = str(rag_posture.get("cache_context", "") or "").strip()
            prewarm_candidates = rag_posture.get("prewarm_candidates") or []
            memory_share = rag_posture.get("memory_recall_share_pct")
            memory_miss_pct = rag_posture.get("memory_recall_miss_pct")
            query_focus = any(
                token in query_lower
                for token in (
                    "rag", "retriev", "cache", "memory", "context", "hint", "report", "improv", "optimiz"
                )
            )
            continuation_focus = any(
                token in query_lower
                for token in (
                    "resume",
                    "continue",
                    "follow-up",
                    "follow up",
                    "previous",
                    "prior context",
                    "pick up where",
                    "last agent",
                    "ongoing",
                )
            )
            if query_focus and rag_status == "low_sample":
                prewarm_ids = [
                    str(candidate.get("id", "")).strip()
                    for candidate in prewarm_candidates
                    if isinstance(candidate, dict) and str(candidate.get("id", "")).strip()
                ]
                snippet = "RAG cache is still warming. Prefer bounded local prewarm before tuning cache size."
                if prewarm_ids:
                    snippet += f" Start with: {', '.join(prewarm_ids[:3])}."
                if cache_context:
                    snippet += f" Context: {cache_context}."
                hints.append(
                    Hint(
                        id="runtime_rag_low_sample",
                        type="runtime_signal",
                        title="RAG cache is still in warmup, not yet in a stable efficiency window",
                        score=0.79,
                        snippet=snippet[:220],
                        reason="Derived from live aq-report rag posture showing low-sample cache state",
                        tags=["runtime", "rag", "cache", "prewarm"],
                        agent_hints={},
                    )
                )
            if (
                continuation_focus
                and memory_miss_pct is not None
                and float(memory_miss_pct) >= 50.0
                and recent_calls >= 8
            ):
                hints.append(
                    Hint(
                        id="runtime_resume_memory_refresh",
                        type="runtime_signal",
                        title="Continuation memory is being attempted, but stored context quality is weak",
                        score=0.84,
                        snippet=(
                            f"This looks like continuation work, and memory recall misses {float(memory_miss_pct):.1f}% "
                            "of recent attempts. Persist clearer milestone summaries or recent task checkpoints before broad route_search."
                        )[:220],
                        reason="Derived from live aq-report memory-recall miss rate and a continuation-style query",
                        tags=["runtime", "rag", "memory", "continuation"],
                        agent_hints={},
                    )
                )
            elif continuation_focus and memory_share is not None and float(memory_share) <= 20.0 and recent_calls >= 8:
                hints.append(
                    Hint(
                        id="runtime_resume_memory_first",
                        type="runtime_signal",
                        title="Resume/continue tasks should recall memory before broad retrieval",
                        score=0.83,
                        snippet=(
                            f"This looks like continuation work, but memory recall is only {float(memory_share):.1f}% "
                            "of recent retrieval calls. Recall prior context before route_search to cut token overhead."
                        )[:220],
                        reason="Derived from live aq-report rag posture and a continuation-style query",
                        tags=["runtime", "rag", "memory", "continuation"],
                        agent_hints={},
                    )
                )
            elif query_focus and memory_share is not None and float(memory_share) <= 15.0 and recent_calls >= 12:
                hints.append(
                    Hint(
                        id="runtime_memory_recall_underused",
                        type="runtime_signal",
                        title="Memory recall is underused relative to broad retrieval",
                        score=0.77,
                        snippet=(
                            f"Memory recall is only {float(memory_share):.1f}% of recent retrieval calls. "
                            "For continuing repo/system work, recall prior context before broad route_search."
                        )[:220],
                        reason="Derived from live aq-report rag posture showing low memory-recall share",
                        tags=["runtime", "rag", "memory", "retrieval"],
                        agent_hints={},
                    )
                )

        # Route search latency optimization hints
        route_breadth = data.get("route_retrieval_breadth", {})
        if isinstance(route_breadth, dict) and route_breadth.get("available"):
            avg_collections = route_breadth.get("avg_collection_count")
            if avg_collections is not None and float(avg_collections) > 4.5:
                top_profiles = route_breadth.get("top_profiles") or []
                profile_note = f" Dominant profile: {top_profiles[0][0]}." if top_profiles else ""
                hints.append(
                    Hint(
                        id="runtime_retrieval_breadth_optimize",
                        type="runtime_signal",
                        title="Route search is scanning more collections than needed",
                        score=0.72,
                        snippet=(
                            f"Avg {float(avg_collections):.1f} collections/call detected.{profile_note} "
                            "Prefer bounded collection selection (3-4 max) based on query intent."
                        )[:220],
                        reason="Derived from live aq-report route_retrieval_breadth showing high collection count",
                        tags=["runtime", "retrieval", "optimization", "latency"],
                        agent_hints={},
                    )
                )

        # Provider fallback recovery hints
        provider_fallbacks = data.get("provider_fallback_recovery", {})
        if isinstance(provider_fallbacks, dict) and provider_fallbacks.get("available"):
            recovered_count = int(provider_fallbacks.get("recovered_count", 0) or 0)
            if recovered_count >= 1:
                status_counts = provider_fallbacks.get("status_counts") or []
                status_text = ", ".join(f"{s[0]}={s[1]}" for s in status_counts[:2]) if status_counts else "unknown"
                hints.append(
                    Hint(
                        id="runtime_provider_fallback_pressure",
                        type="runtime_signal",
                        title="Remote provider fallbacks detected — routing pressure, not local outage",
                        score=0.68,
                        snippet=(
                            f"{recovered_count} recovered fallbacks observed (upstream {status_text}). "
                            "Treat as provider-budget or remote-routing pressure. Prefer local-first routing."
                        )[:220],
                        reason="Derived from live aq-report provider_fallback_recovery showing remote fallback events",
                        tags=["runtime", "routing", "provider", "fallback"],
                        agent_hints={},
                    )
                )

        delegated_failures = data.get("delegated_prompt_failures", {})
        if isinstance(delegated_failures, dict) and delegated_failures.get("available"):
            total_failures = int(delegated_failures.get("total_failures", 0) or 0)
            top_failure_classes = delegated_failures.get("top_failure_classes") or []
            delegate_focus = any(
                token in query_lower
                for token in ("openrouter", "delegate", "delegation", "prompt", "agent", "orchestrat", "improv")
            )
            if delegate_focus and total_failures >= 1:
                failure_text = ", ".join(f"{name}={count}" for name, count in top_failure_classes[:2]) or "unknown"
                hints.append(
                    Hint(
                        id="runtime_delegation_prompt_contract",
                        type="runtime_signal",
                        title="Delegated failures should be treated as prompt-contract failures",
                        score=0.81,
                        snippet=(
                            f"{total_failures} delegated failures recorded recently ({failure_text}). "
                            "Tighten scope, require explicit output shape, and digest salvageable content before retry."
                        )[:220],
                        reason="Derived from live aq-report delegated_prompt_failures telemetry",
                        tags=["runtime", "delegation", "prompt-contract", "openrouter"],
                        agent_hints={},
                    )
                )

        agent_lessons = data.get("agent_lessons", {})
        lesson_registry = agent_lessons.get("registry", {}) if isinstance(agent_lessons, dict) else {}
        active_lessons = lesson_registry.get("active_lessons") if isinstance(lesson_registry, dict) else []
        lesson_candidates = agent_lessons.get("candidates") if isinstance(agent_lessons, dict) else []
        if isinstance(active_lessons, list):
            lesson_focus = any(
                token in query_lower
                for token in ("improv", "hint", "agent", "rag", "retriev", "memory", "review", "training")
            )
            for item in active_lessons[:2]:
                if not isinstance(item, dict) or not lesson_focus:
                    continue
                hint_id = str(item.get("hint_id", "") or "").strip()
                state = str(item.get("state", "") or "").strip().lower()
                agent = str(item.get("agent", "") or "").strip().lower()
                materialization = str(item.get("materialization", "") or "").strip().lower()
                if not hint_id or state not in {"promoted", "avoided"}:
                    continue
                title = (
                    f"Apply promoted {agent} lesson {hint_id}"
                    if state == "promoted"
                    else f"Keep {hint_id} down-scoped for {agent} tasks"
                )
                snippet = (
                    f"Accepted lesson state is `{state}` for `{hint_id}`"
                    + (f" via {materialization}" if materialization else "")
                    + ". Reuse it before inventing a new approach."
                )
                hints.append(
                    Hint(
                        id=f"runtime_agent_lesson_active_{agent}_{state}_{re.sub(r'[^a-z0-9]+', '_', hint_id.lower())}",
                        type="runtime_signal",
                        title=title[:96],
                        score=0.79,
                        snippet=snippet[:220],
                        reason="Derived from the persisted agent lesson registry in the live aq-report",
                        tags=["runtime", "agent-learning", "accepted-lesson", state, agent],
                        agent_hints={},
                    )
                )
        if isinstance(lesson_candidates, list):
            lesson_focus = any(
                token in query_lower
                for token in ("improv", "hint", "agent", "rag", "retriev", "memory", "review", "training")
            )
            for item in lesson_candidates[:2]:
                if not isinstance(item, dict):
                    continue
                hint_id = str(item.get("hint_id", "") or "").strip()
                direction = str(item.get("direction", "") or "").strip().lower()
                agent = str(item.get("agent", "") or "").strip().lower()
                registry_state = str(item.get("registry_state", "") or "").strip().lower()
                if (
                    not hint_id
                    or direction not in {"promote", "avoid"}
                    or not lesson_focus
                    or registry_state in {"promoted", "avoided"}
                ):
                    continue
                comments = item.get("comments") or []
                example = str(comments[0] or "").strip() if comments else ""
                title = (
                    f"Promote {hint_id} as a reusable {agent} lesson"
                    if direction == "promote"
                    else f"Reduce {hint_id} for {agent} tasks"
                )
                snippet = (
                    f"{agent} feedback repeatedly marked `{hint_id}` as {direction}."
                    + (f" Example: {example}" if example else "")
                )
                hints.append(
                    Hint(
                        id=f"runtime_agent_lesson_{agent}_{direction}_{re.sub(r'[^a-z0-9]+', '_', hint_id.lower())}",
                        type="runtime_signal",
                        title=title[:96],
                        score=0.74,
                        snippet=snippet[:220],
                        reason="Derived from repeated cross-agent hint feedback promoted into the live report",
                        tags=["runtime", "agent-learning", direction, agent],
                        agent_hints={},
                    )
                )
        return hints

    def _hints_from_tool_audit_errors(self, query: str, query_tokens: List[str]) -> List[Hint]:
        try:
            with open(self._audit_log_path, "r", encoding="utf-8") as fh:
                lines = fh.readlines()
        except Exception:
            return []
        if not lines:
            return []

        recent = lines[-300:]
        grouped: Dict[str, Dict[str, object]] = {}
        for line in recent:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if str(row.get("outcome", "")).lower() != "error":
                continue
            service_name = str(row.get("service", "") or "").strip().lower()
            # Ignore internal first-use security-auditor denials here. They are
            # tracked separately in aq-report and otherwise dominate runtime
            # hint IDs with low-actionability repeats.
            if service_name.endswith("-tool-security"):
                continue
            tool = str(row.get("tool_name", "") or "").strip()
            if not tool:
                continue
            g = grouped.setdefault(tool, {"count": 0, "errors": {}})
            g["count"] = int(g.get("count", 0)) + 1
            em = str(row.get("error_message", "") or "").strip()
            if em:
                errs = g.setdefault("errors", {})
                errs[em] = int(errs.get(em, 0)) + 1

        query_lower = (query or "").lower()
        hints: List[Hint] = []
        for tool, stats in grouped.items():
            count = int(stats.get("count", 0))
            errors = stats.get("errors", {})
            if not isinstance(errors, dict):
                errors = {}
            top_error = ""
            top_count = 0
            for msg, c in errors.items():
                if int(c) > top_count:
                    top_error, top_count = str(msg), int(c)

            relevant = tool.lower() in query_lower or any(tok in top_error.lower() for tok in query_tokens if len(tok) >= 4)
            if not relevant and count < 2:
                continue
            hints.append(
                Hint(
                    id=f"runtime_tool_error_{re.sub(r'[^a-z0-9]+', '_', tool.lower())}",
                    type="runtime_signal",
                    title=f"Recent tool errors detected: {tool}",
                    score=min(0.92, 0.62 + min(count, 6) * 0.05),
                    snippet=(
                        f"{tool} failed {count} times recently."
                        + (f" Top error: {top_error[:140]}" if top_error else "")
                    ),
                    reason="Derived from recent tool-audit error telemetry",
                    tags=["runtime", "tooling", "errors", tool.lower()],
                    agent_hints={},
                )
            )
        return hints

    # ------------------------------------------------------------------
    # Source B -- query gaps JSONL
    # ------------------------------------------------------------------

    def _hints_from_gaps(
        self, query: str, query_tokens: List[str]
    ) -> List[Hint]:
        try:
            with open(self._gaps_path, "r", encoding="utf-8") as fh:
                lines = fh.readlines()
        except Exception:
            return []

        query_lower = query.lower()
        query_len = max(len(query_lower), 1)

        # Aggregate occurrences per unique gap text
        gap_counts: Dict[str, int] = {}
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            gap_text = str(obj.get("query_text") or "").strip()
            if gap_text and not _is_curated_stale_gap(gap_text) and not _is_synthetic_gap(gap_text):
                gap_counts[gap_text] = gap_counts.get(gap_text, 0) + 1

        hints: List[Hint] = []
        for gap_text, occurrences in gap_counts.items():
            gap_lower = gap_text.lower()
            lcs_len = _longest_common_substring_len(query_lower, gap_lower)
            fuzzy_score = lcs_len / max(query_len, len(gap_lower), 1)
            fuzzy_score = min(1.0, fuzzy_score)

            token_match = any(tok in gap_lower for tok in query_tokens)

            if fuzzy_score <= 0.25 and not token_match:
                continue

            score = min(1.0, fuzzy_score * 0.8) * 0.3
            safe_gap = gap_text[:60]
            snippet = (
                f"Recurring gap ({occurrences}x): consider "
                f"'aidb import --query \"{safe_gap}\"'"
            )
            hint_id = "gap_" + re.sub(r"[^a-z0-9]", "_", gap_lower[:40])

            hints.append(
                Hint(
                    id=hint_id,
                    type="gap_topic",
                    title=f"Knowledge gap: {gap_text[:60]}",
                    score=score,
                    snippet=snippet,
                    reason=f"Fuzzy match {fuzzy_score:.0%} against recurring gap query",
                    tags=["gap", "knowledge"],
                    agent_hints={},
                )
            )

        return hints

    # ------------------------------------------------------------------
    # Source C -- static workflow rules
    # ------------------------------------------------------------------

    def _hints_from_static_rules(self, query_tokens: List[str]) -> List[Hint]:
        hints: List[Hint] = []
        token_set = set(query_tokens)

        for rule in _STATIC_RULES:
            keywords: List[str] = rule["keywords"]
            matched = any(kw in token_set for kw in keywords)
            if not matched:
                continue

            score = 0.5 * 0.1  # weight 0.1

            hints.append(
                Hint(
                    id=rule["id"],
                    type="workflow_rule",
                    title=rule["title"],
                    score=score,
                    snippet=rule["snippet"],
                    reason=f"Keyword match in workflow rules (keywords: {keywords})",
                    tags=list(rule["tags"]),
                    agent_hints={},
                )
            )

        return hints


# ---------------------------------------------------------------------------
# Standalone test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    engine = HintsEngine()
    result = engine.rank_as_dict("conflicting NixOS module definitions", max_hints=5)
    import json
    print(json.dumps(result, indent=2))
