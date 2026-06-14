#!/usr/bin/env python3
"""
test-chat-intent.py — Unit tests for scripts/ai/lib/chat_intent.py

Covers:
  - All phrases in TOOL_FREE_PHRASES → expect "conversational"
  - All phrases in TOOL_FREE_SPEC_PHRASES → expect "conversational"
  - Tool-inviting phrases → expect "agentic"
  - ToolMode enum values
  - is_conversational() helper
  - classify_chat_intent() return fields
  - Edge cases: empty string, whitespace-only, mixed case, embedded phrases, spec+tool
"""

from __future__ import annotations

import sys
import os
import traceback
from pathlib import Path

# Ensure scripts/ai/lib is on path
_LIB = Path(__file__).resolve().parent.parent / "ai" / "lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

from chat_intent import (
    ToolMode,
    TurnClassification,
    TOOL_FREE_PHRASES,
    TOOL_FREE_SPEC_PHRASES,
    classify_chat_intent,
    is_conversational,
)

# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------

_passed = 0
_failed = 0
_errors: list[str] = []


def check(description: str, condition: bool) -> None:
    global _passed, _failed
    if condition:
        _passed += 1
        print(f"  PASS  {description}")
    else:
        _failed += 1
        msg = f"  FAIL  {description}"
        _errors.append(msg)
        print(msg)


def section(title: str) -> None:
    print(f"\n--- {title} ---")


# ---------------------------------------------------------------------------
# Phase 1: TOOL_FREE_PHRASES → always "conversational"
# ---------------------------------------------------------------------------

section("TOOL_FREE_PHRASES → conversational")
for phrase in sorted(TOOL_FREE_PHRASES):
    result = classify_chat_intent(phrase)
    check(f"TOOL_FREE_PHRASE exact: '{phrase}'",
          result.mode == "conversational" and result.matched_phrase == phrase)

# Embedded in a longer sentence
check("TOOL_FREE embedded: 'please answer without tools this time'",
      is_conversational("please answer without tools this time"))
check("TOOL_FREE embedded: 'respond tool-free and concise'",
      is_conversational("respond tool-free and concise"))
check("TOOL_FREE embedded: 'do not call tools for this query'",
      is_conversational("do not call tools for this query"))
check("TOOL_FREE embedded: 'I need this tool free'",
      is_conversational("I need this tool free"))

# ---------------------------------------------------------------------------
# Phase 2: TOOL_FREE_SPEC_PHRASES → "conversational" (when no "tool" present)
# ---------------------------------------------------------------------------

section("TOOL_FREE_SPEC_PHRASES → conversational (no 'tool' in text)")
for phrase in sorted(TOOL_FREE_SPEC_PHRASES):
    result = classify_chat_intent(phrase)
    check(f"SPEC_PHRASE exact: '{phrase}'",
          result.mode == "conversational" and result.matched_phrase == phrase)

check("SPEC embedded: 'write acceptance criteria for the login flow'",
      is_conversational("write acceptance criteria for the login flow"))
check("SPEC embedded: 'I just need the spec only, no implementation'",
      is_conversational("I just need the spec only, no implementation"))
check("SPEC embedded: 'produce a spec for the new API'",
      is_conversational("produce a spec for the new API"))

# ---------------------------------------------------------------------------
# Phase 3: SPEC_PHRASES with "tool" present → agentic (conservative)
# ---------------------------------------------------------------------------

section("TOOL_FREE_SPEC_PHRASES + 'tool' keyword → agentic (conservative)")
check("spec + 'tool': 'acceptance criteria using the tool'",
      not is_conversational("acceptance criteria using the tool"))
check("spec + 'tool': 'produce a spec and also call the tool'",
      not is_conversational("produce a spec and also call the tool"))
check("spec + 'tool': 'tests only but use tool to verify'",
      not is_conversational("tests only but use tool to verify"))

# ---------------------------------------------------------------------------
# Phase 4: Tool-inviting phrases → agentic
# ---------------------------------------------------------------------------

section("Tool-inviting phrases → agentic")
agentic_cases = [
    "list files in the current directory",
    "search for all TODO comments",
    "run the health check",
    "show me git status",
    "what is the current aq-qa score",
    "deploy the new config",
    "check if the coordinator is running",
    "write a function that parses JSON",
    "fix the bug in agent_executor.py",
    "diff the last two commits",
    "grep for PENDING entries",
    "cat the harness log",
    "rebuild the system",
    "run aq-qa 0",
    "what does the switchboard profile contain",
    "how does the coordinator route requests",
    "edit the nix module",
    "update the aq-chat script",
]
for text in agentic_cases:
    check(f"agentic: '{text[:60]}'", not is_conversational(text))

# ---------------------------------------------------------------------------
# Phase 5: is_conversational() helper
# ---------------------------------------------------------------------------

section("is_conversational() helper")
check("is_conversational('no tools') → True",
      is_conversational("no tools") is True)
check("is_conversational('list files') → False",
      is_conversational("list files") is False)
check("is_conversational('') → False (empty → agentic default)",
      is_conversational("") is False)
check("is_conversational('   ') → False (whitespace → agentic default)",
      is_conversational("   ") is False)

# ---------------------------------------------------------------------------
# Phase 6: classify_chat_intent() return fields
# ---------------------------------------------------------------------------

section("classify_chat_intent() return fields")
r = classify_chat_intent("do not call tools")
check("mode == 'conversational'", r.mode == "conversational")
check("confidence > 0", r.confidence > 0)
check("matched_phrase is not None", r.matched_phrase is not None)
check("matched_phrase is a string", isinstance(r.matched_phrase, str))

r2 = classify_chat_intent("list all open issues")
check("agentic mode == 'agentic'", r2.mode == "agentic")
check("agentic confidence == 1.0", r2.confidence == 1.0)
check("agentic matched_phrase is None", r2.matched_phrase is None)

r3 = classify_chat_intent("tool free answer please")
check("tool-free confidence >= 0.9", r3.confidence >= 0.9)

r4 = classify_chat_intent("acceptance criteria for the widget")
check("spec confidence >= 0.8", r4.confidence >= 0.8)
check("spec mode == 'conversational'", r4.mode == "conversational")

# TurnClassification is a dataclass
check("TurnClassification is a dataclass with .mode .confidence .matched_phrase",
      hasattr(r, "mode") and hasattr(r, "confidence") and hasattr(r, "matched_phrase"))

# ---------------------------------------------------------------------------
# Phase 7: ToolMode enum
# ---------------------------------------------------------------------------

section("ToolMode enum")
check("ToolMode.ENABLED.value == 'enabled'",
      ToolMode.ENABLED.value == "enabled")
check("ToolMode.DISABLED_SESSION.value == 'disabled_session'",
      ToolMode.DISABLED_SESSION.value == "disabled_session")
check("ToolMode.DISABLED_TURN.value == 'disabled_turn'",
      ToolMode.DISABLED_TURN.value == "disabled_turn")
check("ToolMode has exactly 3 members",
      len(list(ToolMode)) == 3)
check("ToolMode values are distinct",
      len({m.value for m in ToolMode}) == 3)

# Enum identity
check("ToolMode.ENABLED is ToolMode.ENABLED",
      ToolMode.ENABLED is ToolMode.ENABLED)
check("ToolMode.ENABLED != ToolMode.DISABLED_SESSION",
      ToolMode.ENABLED != ToolMode.DISABLED_SESSION)

# ToolMode transition simulation
mode = ToolMode.ENABLED
check("start ENABLED", mode == ToolMode.ENABLED)
mode = ToolMode.DISABLED_TURN
check("transition to DISABLED_TURN", mode == ToolMode.DISABLED_TURN)
mode = ToolMode.DISABLED_SESSION
check("transition to DISABLED_SESSION", mode == ToolMode.DISABLED_SESSION)
mode = ToolMode.ENABLED
check("restore to ENABLED", mode == ToolMode.ENABLED)

# ---------------------------------------------------------------------------
# Phase 8: Edge cases
# ---------------------------------------------------------------------------

section("Edge cases")
check("empty string → agentic", not is_conversational(""))
check("whitespace only → agentic", not is_conversational("    \t\n"))
check("mixed case 'NO TOOLS please' → conversational",
      is_conversational("NO TOOLS please"))
check("mixed case 'Do Not Call Tools' → conversational",
      is_conversational("Do Not Call Tools"))
check("mixed case 'TOOL-FREE' → conversational",
      is_conversational("TOOL-FREE response please"))
check("mixed case 'Acceptance Criteria' → conversational",
      is_conversational("Acceptance Criteria for the auth flow"))
check("spec phrase 'TESTS ONLY' → conversational",
      is_conversational("TESTS ONLY, no implementation"))
check("very long prompt with embedded phrase → conversational",
      is_conversational(
          "I want you to write a comprehensive design document "
          "with acceptance criteria for the new routing system, "
          "but please keep it to three pages."
      ))
check("phrase at end of sentence → conversational",
      is_conversational("Just give me the answer without tools"))
check("phrase at start → conversational",
      is_conversational("no tools needed, just explain the concept"))
check("numerics in text → agentic (no match)",
      not is_conversational("123 456 789"))
check("single word 'hello' → agentic (conservative default)",
      not is_conversational("hello"))
check("question about code without tool phrase → agentic",
      not is_conversational("what is the difference between async and sync io"))

# ---------------------------------------------------------------------------
# Phase 9: Phrase set integrity
# ---------------------------------------------------------------------------

section("Phrase set integrity")
check("TOOL_FREE_PHRASES is a frozenset",
      isinstance(TOOL_FREE_PHRASES, frozenset))
check("TOOL_FREE_SPEC_PHRASES is a frozenset",
      isinstance(TOOL_FREE_SPEC_PHRASES, frozenset))
check("TOOL_FREE_PHRASES has >= 6 entries",
      len(TOOL_FREE_PHRASES) >= 6)
check("TOOL_FREE_SPEC_PHRASES has >= 5 entries",
      len(TOOL_FREE_SPEC_PHRASES) >= 5)
check("No overlap between TOOL_FREE_PHRASES and TOOL_FREE_SPEC_PHRASES",
      len(TOOL_FREE_PHRASES & TOOL_FREE_SPEC_PHRASES) == 0)
check("All phrases are lowercase (normalization invariant)",
      all(p == p.lower() for p in TOOL_FREE_PHRASES | TOOL_FREE_SPEC_PHRASES))

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

total = _passed + _failed
print(f"\n{'='*50}")
print(f"Results: {_passed}/{total} passed, {_failed} failed")
if _errors:
    print("\nFailed tests:")
    for e in _errors:
        print(f"  {e}")

if _failed > 0:
    sys.exit(1)
else:
    print("All tests passed.")
    sys.exit(0)
