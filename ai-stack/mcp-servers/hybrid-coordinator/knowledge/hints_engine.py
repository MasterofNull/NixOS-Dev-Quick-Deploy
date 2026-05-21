from __future__ import annotations

"""
Compatibility facade for the hints engine.

The large implementation lives in ``knowledge.hints_engine_impl``; this module
keeps the historical import surface stable while Phase R3 extracts shared data
and helper code into focused modules.
"""

from .hints_engine_impl import *  # noqa: F403
from .hints_engine_impl import (  # noqa: F401
    DOMAIN_LOADER_AVAILABLE,
    DomainContext,
    HintsEngine,
    _detect_file_type,
    _hints_cache,
    _HINTS_CACHE_TTL,
    psycopg,
    yaml,
)
from .models import Hint as Hint
from .token_manager import (
    TokenBudgetContext as TokenBudgetContext,
    _TOKEN_RE as _TOKEN_RE,
    _COMMAND_RE as _COMMAND_RE,
    _token_budget_context as _token_budget_context,
    _tokenize as _tokenize,
    _estimate_tokens as _estimate_tokens,
    _compress_snippet as _compress_snippet,
    get_token_budget_context as get_token_budget_context,
    calculate_context_aware_budget as calculate_context_aware_budget,
    _budget_rationale as _budget_rationale,
)
from .static_rules import (
    STATIC_RULES as STATIC_RULES,
    _STATIC_RULES as _STATIC_RULES,
    AGENT_STRENGTHS as AGENT_STRENGTHS,
    _AGENT_STRENGTHS as _AGENT_STRENGTHS,
    PROMPT_COACHING_FIELDS as PROMPT_COACHING_FIELDS,
    _PROMPT_COACHING_FIELDS as _PROMPT_COACHING_FIELDS,
    FILE_TYPE_TAG_MAP as FILE_TYPE_TAG_MAP,
    FILE_TYPE_BOOST_MULTIPLIER as FILE_TYPE_BOOST_MULTIPLIER,
)
from .gap_analyzer import (
    _CURATED_STALE_GAP_PATTERNS as _CURATED_STALE_GAP_PATTERNS,
    _normalize_gap_text as _normalize_gap_text,
    _is_synthetic_gap as _is_synthetic_gap,
    _is_curated_stale_gap as _is_curated_stale_gap,
    _longest_common_substring_len as _longest_common_substring_len,
)

HintsEngine.__module__ = __name__
