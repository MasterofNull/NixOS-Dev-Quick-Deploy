#!/usr/bin/env python3
"""Task complexity classifier for hybrid-coordinator.

Classifies a query + context into a task_type and determines whether the
task is suitable for the local LLM (small, bounded, factual) or requires
remote routing (complex reasoning, code generation, large input).

No LLM calls — pure heuristics for zero-latency classification.
"""
import os
import re
from dataclasses import dataclass
from typing import Optional

CHARS_PER_TOKEN = 4
LOCAL_MAX_INPUT_TOKENS = int(os.getenv("LOCAL_MAX_INPUT_TOKENS", "600"))
LOCAL_MAX_OUTPUT_TOKENS = int(os.getenv("LOCAL_MAX_OUTPUT_TOKENS", "300"))

_LOOKUP_RE = re.compile(
    r"\b(what is|what are|define|who is|when was|where is|which|list the|list all)\b",
    re.IGNORECASE,
)
_FORMAT_RE = re.compile(
    r"\b(format|convert|extract|json|yaml|csv|parse|transform|output as)\b",
    re.IGNORECASE,
)
_CODE_RE = re.compile(
    r"\b(implement|refactor|debug|fix.*bug|write.*function|write.*class|write.*script|add.*feature)\b",
    re.IGNORECASE,
)
_REASONING_RE = re.compile(
    r"\b(why|how does|explain|analyze|analyse|compare|design|architect|strategy|trade.?off)\b",
    re.IGNORECASE,
)


@dataclass
class TaskComplexity:
    token_estimate: int
    task_type: str          # lookup | format | synthesize | code | reasoning
    local_suitable: bool
    remote_required: bool
    reason: str
    optimized_prompt: Optional[str] = None


def classify(query: str, context: str = "", max_output_tokens: int = 400) -> TaskComplexity:
    """Classify task and return complexity with optional optimized prompt."""
    token_estimate = (len(query) + len(context)) // CHARS_PER_TOKEN
    q = query.strip()

    # Detect task type in priority order
    if _CODE_RE.search(q):
        task_type = "code"
    elif _REASONING_RE.search(q):
        task_type = "reasoning"
    elif _FORMAT_RE.search(q):
        task_type = "format"
    elif _LOOKUP_RE.search(q):
        task_type = "lookup"
    else:
        task_type = "synthesize"

    # Routing decision
    if token_estimate > LOCAL_MAX_INPUT_TOKENS:
        return TaskComplexity(
            token_estimate=token_estimate,
            task_type=task_type,
            local_suitable=False,
            remote_required=True,
            reason=f"input_too_large tokens={token_estimate} limit={LOCAL_MAX_INPUT_TOKENS}",
        )
    if max_output_tokens > LOCAL_MAX_OUTPUT_TOKENS:
        return TaskComplexity(
            token_estimate=token_estimate,
            task_type=task_type,
            local_suitable=False,
            remote_required=True,
            reason=f"output_too_large requested={max_output_tokens} limit={LOCAL_MAX_OUTPUT_TOKENS}",
        )
    if task_type in ("code", "reasoning"):
        return TaskComplexity(
            token_estimate=token_estimate,
            task_type=task_type,
            local_suitable=False,
            remote_required=True,
            reason=f"task_type={task_type}_requires_remote",
        )

    # Build discrete, bounded prompt for local model
    ctx = context[:800].strip() if context else ""
    if task_type == "lookup":
        optimized = f"Answer in one sentence: {q}\n\nFacts:\n{ctx}"
    elif task_type == "format":
        optimized = f"Output ONLY the requested data, no explanation:\n{q}\n\nInput:\n{ctx}"
    else:  # synthesize / summarize
        optimized = (
            f"Using only the context below, answer in 2-3 sentences.\n"
            f"Question: {q}\n\nContext:\n{ctx}"
        )

    return TaskComplexity(
        token_estimate=token_estimate,
        task_type=task_type,
        local_suitable=True,
        remote_required=False,
        reason="within_local_capacity",
        optimized_prompt=optimized,
    )
