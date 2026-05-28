"""
quality_check — Output quality gate for local agent dispatch.

Called by aq-refine after each dispatch attempt. Returns a structured
result so the retry loop can decide: accept, refine-and-retry, or escalate.

Exit codes (when run as CLI):
    0 = PASS
    1 = FAIL (retriable)
    2 = EMPTY (always retry)
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ── failure patterns ──────────────────────────────────────────────────────────

# Model confusion / re-attempt patterns — indicate the model was lost.
_CONFUSION_PATTERNS = [
    r"(?i)let me try again",
    r"(?i)let me re(write|do|attempt|think|phrase)",
    r"(?i)i made an error",
    r"(?i)i apologize.*incorrect",
    r"(?i)that('s| is) (wrong|incorrect|not right)",
    r"(?i)^wait,?\s",
    r"(?i)^actually,?\s",
]

# Over-generation markers — model filled the budget without completing the task.
_OVERGEN_PATTERNS = [
    r"for _ in range\(1\)\]\s*\]\s*\]",  # nested list comp spam
    r"(\n.{0,5}){50,}",                   # 50+ very-short lines = repetition
]

# Refusal / cannot-do patterns.
_REFUSAL_PATTERNS = [
    r"(?i)i('m| am) (unable|not able) to",
    r"(?i)i cannot (provide|generate|write|help)",
    r"(?i)as an (ai|language model|llm)",
    r"(?i)i don't have (access|the ability)",
]

_CONFUSION_RE = [re.compile(p) for p in _CONFUSION_PATTERNS]
_OVERGEN_RE   = [re.compile(p, re.DOTALL) for p in _OVERGEN_PATTERNS]
_REFUSAL_RE   = [re.compile(p) for p in _REFUSAL_PATTERNS]


# ── result dataclass ──────────────────────────────────────────────────────────

@dataclass
class QualityResult:
    passed: bool
    reason: str                         # human-readable verdict
    refinement_hint: Optional[str]      # injected into next attempt's prompt
    token_ratio: float = 0.0            # tokens_out / max_tokens (overgen proxy)
    issues: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "passed": self.passed,
            "reason": self.reason,
            "refinement_hint": self.refinement_hint,
            "token_ratio": round(self.token_ratio, 3),
            "issues": self.issues,
        }


# ── core check ────────────────────────────────────────────────────────────────

def check(
    output_text: str,
    *,
    tokens_out: Optional[int] = None,
    max_tokens: Optional[int] = None,
    prompt: str = "",
    min_length: int = 5,
) -> QualityResult:
    """Evaluate output quality. Returns a QualityResult.

    Args:
        output_text: The model's response text.
        tokens_out:  Reported completion tokens (from registry).
        max_tokens:  Budget that was set for this call.
        prompt:      Original prompt (used for context-aware checks).
        min_length:  Minimum character count for non-empty check.
    """
    issues: list[str] = []
    hint: Optional[str] = None

    # ── 1. empty output ───────────────────────────────────────────────────────
    stripped = output_text.strip()
    if not stripped or len(stripped) < min_length:
        return QualityResult(
            passed=False,
            reason="empty output",
            refinement_hint="The previous attempt returned an empty response. "
                            "Please provide a direct, complete answer.",
            issues=["empty"],
        )

    # ── 2. error prefix ───────────────────────────────────────────────────────
    if stripped.startswith(("Error:", "HTTP ")):
        return QualityResult(
            passed=False,
            reason=f"service error: {stripped[:80]}",
            refinement_hint=None,  # infrastructure error — don't retry same way
            issues=["service_error"],
        )

    # ── 3. token ratio (over-generation) ─────────────────────────────────────
    ratio = 0.0
    if tokens_out and max_tokens and max_tokens > 0:
        ratio = tokens_out / max_tokens
        if ratio >= 0.95:
            issues.append("overgen")
            hint = ("Your previous response was too long and hit the token limit. "
                    "Be concise. Answer directly without preamble or elaboration.")

    # ── 4. over-generation patterns ───────────────────────────────────────────
    for rx in _OVERGEN_RE:
        if rx.search(stripped):
            issues.append("overgen_pattern")
            hint = hint or ("Your previous response repeated content or used an "
                            "overly complex pattern. Provide a simple, direct answer.")
            break

    # ── 5. confusion / re-attempt ─────────────────────────────────────────────
    for rx in _CONFUSION_RE:
        m = rx.search(stripped)
        if m:
            issues.append("confusion")
            hint = hint or ("Keep your answer direct. Do not self-correct inline — "
                            "give your best answer immediately without re-attempting.")
            break

    # ── 6. refusal ────────────────────────────────────────────────────────────
    for rx in _REFUSAL_RE:
        if rx.search(stripped):
            issues.append("refusal")
            return QualityResult(
                passed=False,
                reason="model refused the task",
                refinement_hint="Reframe the task: approach it as a technical "
                                "implementation exercise, not a policy question.",
                issues=issues,
                token_ratio=ratio,
            )

    # ── verdict ───────────────────────────────────────────────────────────────
    if issues:
        return QualityResult(
            passed=False,
            reason=f"quality issues: {', '.join(issues)}",
            refinement_hint=hint,
            issues=issues,
            token_ratio=ratio,
        )

    return QualityResult(
        passed=True,
        reason="ok",
        refinement_hint=None,
        issues=[],
        token_ratio=ratio,
    )


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> int:
    """
    Usage:
        quality_check.py OUTPUT_FILE [--tokens-out N] [--max-tokens N] [--prompt TEXT]
    """
    import argparse
    parser = argparse.ArgumentParser(prog="quality_check.py")
    parser.add_argument("output_file")
    parser.add_argument("--tokens-out",  type=int, default=None)
    parser.add_argument("--max-tokens",  type=int, default=None)
    parser.add_argument("--prompt",      default="")
    parser.add_argument("--json",        action="store_true")
    args = parser.parse_args()

    text = Path(args.output_file).read_text(errors="replace") if Path(args.output_file).exists() else ""
    result = check(
        text,
        tokens_out=args.tokens_out,
        max_tokens=args.max_tokens,
        prompt=args.prompt,
    )

    if args.json:
        print(json.dumps(result.as_dict()))
    else:
        sym = "PASS" if result.passed else "FAIL"
        print(f"{sym}: {result.reason}")
        if result.refinement_hint:
            print(f"hint: {result.refinement_hint}")

    return 0 if result.passed else (2 if "empty" in result.issues else 1)


if __name__ == "__main__":
    sys.exit(main())
