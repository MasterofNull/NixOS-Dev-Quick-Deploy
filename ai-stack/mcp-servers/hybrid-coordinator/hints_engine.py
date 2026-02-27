from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Hint:
    """A ranked, actionable workflow hint surfaced to any agent or human."""

    id: str
    type: str  # "prompt_template" | "gap_topic" | "workflow_rule" | "tool_warning"
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
        "id": "strategy_tag_evals",
        "title": "Tag eval runs with strategy names",
        "keywords": ["eval", "score", "test", "benchmark", "compare", "strategy"],
        "snippet": (
            "Use `scripts/run-eval.sh --strategy my-variant` to tag results for "
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
            "`scripts/aq-prompt-eval --id <id>` to update mean_score before deploying."
        ),
        "tags": ["prompt", "registry", "eval", "measurement"],
    },
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"[a-z0-9]+")


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
            self._audit_log_path = (
                Path(env_val)
                if env_val
                else Path("/var/log/nixos-ai-stack/tool-audit.jsonl")
            )
        else:
            self._audit_log_path = audit_log_path

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def rank(
        self,
        query: str,
        context: str = "",
        max_hints: int = 5,
    ) -> List[Hint]:
        """
        Return up to *max_hints* ranked Hint objects for the given *query*.

        Three sources are combined:
          A) Registry templates (weight 0.6)
          B) Query gaps from JSONL (weight 0.3)
          C) Static workflow rules from CLAUDE.md (weight 0.1)

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

        combined: List[Hint] = source_a + source_b + source_c
        combined.sort(key=lambda h: h.score, reverse=True)

        seen: set = set()
        deduped: List[Hint] = []
        for hint in combined:
            if hint.id not in seen:
                seen.add(hint.id)
                deduped.append(hint)
            if len(deduped) >= max_hints:
                break

        return deduped

    def to_dict(self, hint: Hint) -> dict:
        """Return a JSON-serialisable dict for *hint*."""
        d: dict = {
            "id": hint.id,
            "type": hint.type,
            "title": hint.title,
            "score": round(hint.score, 4),
            "snippet": hint.snippet,
            "reason": hint.reason,
            "tags": hint.tags,
        }
        if hint.agent_hints:
            d["agent_hints"] = hint.agent_hints
        return d

    def rank_as_dict(
        self,
        query: str,
        context: str = "",
        max_hints: int = 5,
    ) -> dict:
        """Return ranked hints as a JSON-serialisable dict."""
        hints = self.rank(query, context=context, max_hints=max_hints)
        return {
            "hints": [self.to_dict(h) for h in hints],
            "generated_at": datetime.now(tz=timezone.utc).isoformat(),
            "query": query,
        }

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
            if gap_text:
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
