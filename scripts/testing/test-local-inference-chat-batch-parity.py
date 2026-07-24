#!/usr/bin/env python3
"""Foundation B1 — chat/batch parity (shadow) oracle.

Offline, report-only proof that the batch adapter (`build_llama_payload`,
the L2B canonical builder) and the two `aq-chat` adapters
(`_build_coordinator_delegate_payload`, `_build_fast_path_payload`) resolve
to the same *canonical request identity* across caller tiers, for a fixed
parity matrix. This is the offline shadow of PRD §14 Required-Suite #2
(the "golden resolver matrix"): PRD line 480 names the comparison surface as
mode/profile/model/task_type/role/tools/budgets/fallback/version.

Why a projection layer (not raw byte-equivalence)
--------------------------------------------------
The three builders emit DISJOINT OpenAI/llama wire payloads (verified by
direct code inspection — see the design review). `mode`, `fallback`, and
`version` have no producer in ANY of them, and fields like `profile`/`role`
are produced by exactly one of the three adapters. PRD line 480 describes the
canonical CONTRACT request schema, not any one adapter's wire shape, so
`canonical_projection()` maps each adapter's wire payload to that schema. A
field with no producer for a given adapter projects to `None` — never
fabricated. §3.4 additionally requires MUST-FAIL comparison of sampling/
execution invariants (enable_thinking, frequency_penalty, temperature,
sampling params, model-id) that are not literally among the 9 line-480 names;
those are carried as EXECUTION_FIELDS on the same projection dict.

Harness-drive, zero aq-chat modification
-----------------------------------------
`_build_coordinator_delegate_payload` / `_build_fast_path_payload` are
instance methods, but their bodies read only `self.temperature` and
`self.local_tools_enabled` (verified by code inspection — `self.
switchboard_url` is read at the SEND site, not inside either builder). This
oracle `importlib`-loads the `aq-chat` module (no top-level side effects —
`main()` is `__name__`-guarded) and calls the two builders unbound, passing a
`types.SimpleNamespace` stub carrying only those two attributes. `AQChat.
__init__` is never invoked — a runtime guard below raises if anything tries.

Offline / no network
---------------------
No `httpx` call is made. Only `build_llama_payload` (a pure function) and the
two builder methods (pure given the stub) are invoked. The `aq-chat` heavy
TUI import (prompt_toolkit/rich) is guarded: if unavailable, this oracle
SKIPS with a typed reason (exit 0, not a silent pass and not a hard error) so
tier0 eligibility is never silently broken.

Scope
-----
REQUEST parity only (per design review §5 correction) — there are no live
responses to decode offline. Response/stream-decode parity is deferred to a
live-shadow follow-on slice. An offline PASS here satisfies the B1
shadow-exit item but is NOT license to remove duplicated chat/batch logic
(L4) — that still gates on a live-shadow pass (PRD line 471).
"""

from __future__ import annotations

import hashlib
import importlib.machinery
import importlib.util
import json
import os
import sys
import types
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[2]
FAILURES: list[str] = []
DIVERGENCES: list[dict] = []  # typed, non-failing evidence


def check(value: bool, message: str) -> None:
    if not value:
        FAILURES.append(message)


# ---------------------------------------------------------------------------
# Read-only reference imports (never modified — reverified by the caller's
# predecessor-hash gate before this file is even authorized to run against a
# changed source; this oracle additionally reverifies at runtime below).
# ---------------------------------------------------------------------------

AQ_CHAT_PATH = ROOT / "scripts" / "ai" / "aq-chat"
LLM_CONFIG_PATH = ROOT / "ai-stack" / "mcp-servers" / "shared" / "llm_config.py"
_SHARED_DIR = ROOT / "ai-stack" / "mcp-servers" / "shared"

# Import the REAL builder (llm_config.build_llama_payload) — not dispatch.py's
# `except ImportError` fallback clone. Mirrors dispatch.py's sys.path insert
# pattern without importing dispatch.py itself.
if str(_SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(_SHARED_DIR))
from llm_config import build_llama_payload  # noqa: E402  type: ignore


def _load_aq_chat_module() -> Optional[types.ModuleType]:
    """Harness-drive: importlib-load aq-chat with zero modification.

    aq-chat has no .py suffix, so spec_from_file_location needs an explicit
    SourceFileLoader. `main()` is __name__-guarded (verified by code
    inspection), so exec_module() has no top-level side effects (no I/O, no
    argparse, no client construction).

    Returns None (typed skip, not a hard error) if the heavy TUI deps
    (prompt_toolkit, rich) aren't importable in this sandbox — required so
    tier0 eligibility is never silently broken by an environment gap.
    """
    try:
        loader = importlib.machinery.SourceFileLoader(
            "aq_chat_parity_oracle", str(AQ_CHAT_PATH)
        )
        spec = importlib.util.spec_from_loader("aq_chat_parity_oracle", loader)
        assert spec is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules["aq_chat_parity_oracle"] = module
        spec.loader.exec_module(module)  # type: ignore[union-attr]
        return module
    except ImportError as exc:
        print(f"SKIP: aq-chat import unavailable in this sandbox ({exc}); "
              f"parity oracle cannot harness-drive the chat builders.")
        return None


def _guarded_aqchat_class(module: types.ModuleType):
    """Return AQChat with __init__ poisoned so it can never be invoked here.

    Defense in depth on top of "never call it": the oracle only ever needs
    the two builder methods bound to a stub, never a real instance.
    """
    AQChat = module.AQChat

    def _forbidden_init(self, *args, **kwargs):  # pragma: no cover - guard
        raise AssertionError(
            "PARITY ORACLE VIOLATION: AQChat.__init__ must never run "
            "(offline, report-only oracle — no live I/O, no switchboard_url)."
        )

    AQChat.__init__ = _forbidden_init
    return AQChat


# ---------------------------------------------------------------------------
# Fixture matrix — tier -> (task_type, temperature). Chosen from
# TASK_PROFILES entries with enable_thinking=False (the chat builders always
# hardcode enable_thinking=False; picking a thinking-enabled batch profile
# would manufacture a spurious MUST-FAIL divergence unrelated to real code).
# frequency_penalty=0.0 is passed explicitly to build_llama_payload for every
# tier so its "explicit arg > profile" override path (llm_config.py) is
# exercised against the same hardcoded 0.0 both chat builders always send —
# this tests real propagation, not a forced/gamed match.
# ---------------------------------------------------------------------------

TIER_TASK_TYPE = {
    "flagship": "reasoning",
    "standard": "agent",
    "budget": "lookup",
    "deterministic": "structured",
}
TIER_TEMPERATURE = {
    "flagship": 0.5,
    "standard": 0.3,
    "budget": 0.1,
    "deterministic": 0.0,
}
FIXTURE_MESSAGES: List[Dict[str, str]] = [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "parity fixture probe"},
]
FIXTURE_PROMPT = "parity fixture probe"


def _build_wire_payloads(AQChat, tier: str) -> Dict[str, Any]:
    """Invoke all three adapters for one tier and return their raw wire payloads.

    Offline determinism: LLAMA_MAX_TOKENS and AI_LOCAL_MODEL_ID are cleared so
    build_llama_payload / fast-path resolve to their code-default values
    (AGENT_TASK_MAX_TOKENS, "local") rather than whatever happens to be set
    in the ambient shell. FABLE_PARITY=0 keeps the batch message list
    structurally identical to the (also non-injected) chat message list —
    this slice is scoped to REQUEST parity on the 9+5 projected fields, not
    message-content equivalence, so suppressing the injection avoids an
    unrelated distraction in the wire payloads under comparison.
    """
    saved_env = {
        k: os.environ.get(k) for k in ("LLAMA_MAX_TOKENS", "AI_LOCAL_MODEL_ID", "FABLE_PARITY")
    }
    try:
        os.environ.pop("LLAMA_MAX_TOKENS", None)
        os.environ.pop("AI_LOCAL_MODEL_ID", None)
        os.environ["FABLE_PARITY"] = "0"

        task_type = TIER_TASK_TYPE[tier]
        temperature = TIER_TEMPERATURE[tier]
        stub = types.SimpleNamespace(temperature=temperature, local_tools_enabled=True)

        coordinator_delegate = AQChat._build_coordinator_delegate_payload(
            stub, FIXTURE_PROMPT, FIXTURE_MESSAGES, tool_free_turn=False
        )
        fast_path = AQChat._build_fast_path_payload(stub, FIXTURE_MESSAGES)
        batch = build_llama_payload(
            FIXTURE_MESSAGES,
            temperature=temperature,
            task_type=task_type,
            frequency_penalty=0.0,
        )
        return {
            "coordinator_delegate": coordinator_delegate,
            "fast_path": fast_path,
            "batch": batch,
        }
    finally:
        for k, v in saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


# ---------------------------------------------------------------------------
# Canonical projection layer (pure) — maps each adapter's disjoint wire
# payload to the PRD line-480 schema, extended with the §3.4 execution
# invariants. See PRODUCER_MATRIX for which adapter has a producer for which
# field; absent producers project to None (never fabricated).
# ---------------------------------------------------------------------------

CANONICAL_FIELDS = (
    "mode", "profile", "model", "task_type", "role", "tools", "budgets",
    "fallback", "version",
)
EXECUTION_FIELDS = (
    "temperature", "frequency_penalty", "enable_thinking",
    "repeat_penalty", "repeat_last_n",
)

# Per-field producer status, per adapter. Documents *why* a field is None
# for a given adapter (no producer) vs a real absence-of-value.
PRODUCER_MATRIX = {
    "mode":              {"batch": False, "coordinator_delegate": False, "fast_path": False},
    "profile":           {"batch": False, "coordinator_delegate": True,  "fast_path": False},
    "model":             {"batch": False, "coordinator_delegate": False, "fast_path": True},
    "task_type":         {"batch": False, "coordinator_delegate": False, "fast_path": False},
    "role":              {"batch": False, "coordinator_delegate": True,  "fast_path": False},
    "tools":             {"batch": False, "coordinator_delegate": True,  "fast_path": False},
    "budgets":           {"batch": True,  "coordinator_delegate": True,  "fast_path": True},
    "fallback":          {"batch": False, "coordinator_delegate": False, "fast_path": False},
    "version":           {"batch": False, "coordinator_delegate": False, "fast_path": False},
    "temperature":       {"batch": True,  "coordinator_delegate": True,  "fast_path": True},
    "frequency_penalty": {"batch": True,  "coordinator_delegate": True,  "fast_path": True},
    "enable_thinking":   {"batch": True,  "coordinator_delegate": True,  "fast_path": True},
    "repeat_penalty":    {"batch": True,  "coordinator_delegate": False, "fast_path": False},
    "repeat_last_n":     {"batch": True,  "coordinator_delegate": False, "fast_path": False},
}

# Classification of each field for comparison policy (§3.4 / authorization §3).
ABSENT_IN_ALL_FIELDS = {"mode", "task_type", "fallback", "version"}
PARTIAL_PRODUCER_FIELDS = {"profile", "model", "role", "tools"}
MUST_FAIL_FIELDS = {"temperature", "frequency_penalty", "enable_thinking"}
# budgets.max_tokens and repeat_penalty/repeat_last_n: expected first-run
# divergences per the design packet/review — recorded as typed evidence,
# not a slice failure, WHEN they match the documented pattern exactly.
KNOWN_DIVERGENCE_FIELDS = {"budgets", "repeat_penalty", "repeat_last_n"}

# Documented known-divergence patterns (§3.4 / packet §6.2 item 4/6).
_KNOWN_MAX_TOKENS_PAIR = {800, 1024}  # AGENT_TASK_MAX_TOKENS vs hardcoded chat 1024
_KNOWN_REPEAT_PENALTY = 1.08
_KNOWN_REPEAT_LAST_N = 64


def _project_tools(adapter: str, wire: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if adapter == "coordinator_delegate":
        if "tools_enabled" not in wire and "tools" not in wire and "tool_choice" not in wire:
            return None
        return {
            "enabled": wire.get("tools_enabled"),
            "list": wire.get("tools"),
            "tool_choice": wire.get("tool_choice"),
        }
    if adapter == "batch":
        return {"enabled": None, "list": wire.get("tools"), "tool_choice": None} if "tools" in wire else None
    return None  # fast_path: no tools concept at all


def canonical_projection(adapter: str, wire: Dict[str, Any]) -> Dict[str, Any]:
    """Pure mapping: adapter wire payload -> {CANONICAL_FIELDS + EXECUTION_FIELDS}.

    `adapter` in {"batch", "coordinator_delegate", "fast_path"}. Fields with
    no producer for this adapter (per PRODUCER_MATRIX) are None — never
    fabricated, never inferred from another adapter's output.
    """
    assert adapter in ("batch", "coordinator_delegate", "fast_path"), adapter
    ctk = wire.get("chat_template_kwargs") or {}
    budgets = {
        "max_tokens": wire.get("max_tokens") if PRODUCER_MATRIX["budgets"][adapter] else None,
        "input_tokens": None,  # no producer in any current builder
    }

    projection: Dict[str, Any] = {f: None for f in CANONICAL_FIELDS + EXECUTION_FIELDS}
    projection["mode"] = None
    projection["profile"] = wire.get("profile") if PRODUCER_MATRIX["profile"][adapter] else None
    projection["model"] = wire.get("model") if PRODUCER_MATRIX["model"][adapter] else None
    projection["task_type"] = None
    projection["role"] = wire.get("role") if PRODUCER_MATRIX["role"][adapter] else None
    projection["tools"] = _project_tools(adapter, wire)
    projection["budgets"] = budgets
    projection["fallback"] = None
    projection["version"] = None
    projection["temperature"] = wire.get("temperature")
    projection["frequency_penalty"] = wire.get("frequency_penalty")
    projection["enable_thinking"] = ctk.get("enable_thinking")
    projection["repeat_penalty"] = wire.get("repeat_penalty") if PRODUCER_MATRIX["repeat_penalty"][adapter] else None
    projection["repeat_last_n"] = wire.get("repeat_last_n") if PRODUCER_MATRIX["repeat_last_n"][adapter] else None
    return projection


def _classify_budgets_pair(a_val: Any, b_val: Any) -> str:
    if a_val == b_val:
        return "pass"
    if {a_val, b_val} == _KNOWN_MAX_TOKENS_PAIR:
        return "typed_divergence"
    return "must_fail"


def _classify_repeat_pair(field: str, a_val: Any, b_val: Any) -> str:
    if a_val == b_val:
        return "pass"
    expected = _KNOWN_REPEAT_PENALTY if field == "repeat_penalty" else _KNOWN_REPEAT_LAST_N
    if {a_val, b_val} == {None, expected}:
        return "typed_divergence"
    return "must_fail"


def compare_projection(
    tier: str, name_a: str, proj_a: Dict[str, Any], name_b: str, proj_b: Dict[str, Any]
) -> Dict[str, Any]:
    """Field-level comparison of two projections for one tier. Fails closed."""
    field_results: Dict[str, Any] = {}
    pair_status = "pass"

    for field in ABSENT_IN_ALL_FIELDS:
        a_val, b_val = proj_a[field], proj_b[field]
        if a_val is None and b_val is None:
            field_results[field] = {"status": "pass_absent_in_all"}
        else:
            field_results[field] = {
                "status": "must_fail",
                "diff": {name_a: a_val, name_b: b_val},
                "reason": "expected absent-in-all field produced a value",
            }
            pair_status = "fail"

    for field in PARTIAL_PRODUCER_FIELDS:
        a_val, b_val = proj_a[field], proj_b[field]
        if a_val is None and b_val is None:
            field_results[field] = {"status": "pass_absent_in_all"}
        elif a_val is None or b_val is None:
            field_results[field] = {
                "status": "no_cross_adapter_producer",
                "value": {name_a: a_val, name_b: b_val},
            }
        elif a_val == b_val:
            field_results[field] = {"status": "pass"}
        else:
            field_results[field] = {
                "status": "must_fail",
                "diff": {name_a: a_val, name_b: b_val},
            }
            pair_status = "fail"

    for field in MUST_FAIL_FIELDS:
        a_val, b_val = proj_a[field], proj_b[field]
        if a_val == b_val:
            field_results[field] = {"status": "pass", "value": a_val}
        else:
            field_results[field] = {
                "status": "must_fail",
                "diff": {name_a: a_val, name_b: b_val},
            }
            pair_status = "fail"

    # budgets: compare the max_tokens sub-field with the known-divergence allowance.
    a_mt, b_mt = proj_a["budgets"]["max_tokens"], proj_b["budgets"]["max_tokens"]
    mt_class = _classify_budgets_pair(a_mt, b_mt)
    field_results["budgets"] = {
        "status": mt_class,
        "value": {name_a: a_mt, name_b: b_mt},
    }
    if mt_class == "must_fail":
        pair_status = "fail"
    elif mt_class == "typed_divergence":
        DIVERGENCES.append({
            "tier": tier, "pair": f"{name_a}-vs-{name_b}", "field": "budgets.max_tokens",
            "value": {name_a: a_mt, name_b: b_mt},
            "note": "known first-run divergence (chat hardcodes 1024; batch resolves "
                    "AGENT_TASK_MAX_TOKENS via LLAMA_MAX_TOKENS env) — scopes L3/L4, not a slice failure.",
        })
        if pair_status == "pass":
            pair_status = "divergence_typed"

    for field in ("repeat_penalty", "repeat_last_n"):
        a_val, b_val = proj_a[field], proj_b[field]
        rp_class = _classify_repeat_pair(field, a_val, b_val)
        field_results[field] = {"status": rp_class, "value": {name_a: a_val, name_b: b_val}}
        if rp_class == "must_fail":
            pair_status = "fail"
        elif rp_class == "typed_divergence":
            DIVERGENCES.append({
                "tier": tier, "pair": f"{name_a}-vs-{name_b}", "field": field,
                "value": {name_a: a_val, name_b: b_val},
                "note": "known first-run divergence (build_llama_payload hardcodes "
                        "repeat_penalty=1.08/repeat_last_n=64; neither aq-chat builder "
                        "sets these) — scopes L3/L4, not a slice failure.",
            })
            if pair_status == "pass":
                pair_status = "divergence_typed"

    return {"tier": tier, "pair": f"{name_a}-vs-{name_b}", "status": pair_status, "fields": field_results}


# ---------------------------------------------------------------------------
# Golden fixture self-consistency (mirrors the L2B golden fixture pattern:
# a frozen live_source_manifest reverified against disk, plus a top-level
# manifest_digest recomputed the same way the fixture author computed it).
# ---------------------------------------------------------------------------

GOLDEN_PATH = ROOT / "scripts" / "testing" / "fixtures" / "local-inference-chat-batch-parity-golden.json"


def _projection_digest(projection: Dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(projection, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def _recompute_manifest_digest(fixture: Dict[str, Any]) -> str:
    """Recomputed the same way the fixture was frozen: sha256 over the sorted
    concatenation of every per-row expected_projection_sha256 plus the sorted
    live_source_manifest entries. Any hand-edit of the fixture that doesn't
    also update this digest is caught (golden_digest_mismatch)."""
    parts: List[str] = []
    for tier in sorted(fixture["tiers"]):
        row = fixture["tiers"][tier]
        for adapter in sorted(row["expected_projections"]):
            parts.append(f"{tier}:{adapter}:{row['expected_projections'][adapter]['sha256']}")
    for rel in sorted(fixture["live_source_manifest"]):
        parts.append(f"src:{rel}:{fixture['live_source_manifest'][rel]}")
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def test_golden_fixture_self_consistency() -> Optional[Dict[str, Any]]:
    fixture = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))

    for rel, expected_hash in fixture["live_source_manifest"].items():
        path = ROOT / rel
        check(
            path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() == expected_hash,
            f"live source drift: {rel} (predecessor hash mismatch — re-authorize)",
        )

    for tier, row in fixture["tiers"].items():
        for adapter, entry in row["expected_projections"].items():
            recomputed = _projection_digest(entry["projection"])
            check(
                recomputed == entry["sha256"],
                f"golden_digest_mismatch: {tier}/{adapter} projection sha256 does not "
                f"match its own recorded digest (fixture was hand-edited inconsistently)",
            )

    recomputed_manifest = _recompute_manifest_digest(fixture)
    check(
        recomputed_manifest == fixture["manifest_digest"],
        "golden_digest_mismatch: top-level manifest_digest does not match recomputation "
        "over per-row projection digests + live_source_manifest",
    )
    return fixture


def test_projections_match_golden(fixture: Dict[str, Any], AQChat) -> None:
    for tier in TIER_TASK_TYPE:
        wires = _build_wire_payloads(AQChat, tier)
        golden_row = fixture["tiers"][tier]
        for adapter, wire in wires.items():
            actual = canonical_projection(adapter, wire)
            expected = golden_row["expected_projections"][adapter]["projection"]
            check(
                actual == expected,
                f"{tier}/{adapter}: live canonical_projection diverged from frozen golden "
                f"(actual={actual!r} expected={expected!r})",
            )


def test_cross_adapter_parity(AQChat) -> List[Dict[str, Any]]:
    reports: List[Dict[str, Any]] = []
    pairs = (
        ("batch", "coordinator_delegate"),
        ("batch", "fast_path"),
        ("coordinator_delegate", "fast_path"),
    )
    for tier in TIER_TASK_TYPE:
        wires = _build_wire_payloads(AQChat, tier)
        projections = {name: canonical_projection(name, wire) for name, wire in wires.items()}
        for name_a, name_b in pairs:
            result = compare_projection(tier, name_a, projections[name_a], name_b, projections[name_b])
            reports.append(result)
            if result["status"] == "fail":
                failed_fields = {
                    f: v for f, v in result["fields"].items() if v["status"] == "must_fail"
                }
                check(False, f"{tier} {name_a}-vs-{name_b}: MUST-FAIL divergence: {failed_fields}")
    return reports


def main() -> int:
    AQChatModule = _load_aq_chat_module()
    if AQChatModule is None:
        print("SKIP: local-inference-chat-batch-parity (aq-chat import unavailable)")
        return 0

    AQChat = _guarded_aqchat_class(AQChatModule)

    fixture = test_golden_fixture_self_consistency()
    if fixture is None or FAILURES:
        print("FAIL: local-inference-chat-batch-parity (golden fixture self-consistency)")
        for f in FAILURES:
            print(f" - {f}")
        return 1

    test_projections_match_golden(fixture, AQChat)
    reports = test_cross_adapter_parity(AQChat)

    if FAILURES:
        print("FAIL: local-inference-chat-batch-parity")
        for f in FAILURES:
            print(f" - {f}")
        return 1

    print("PASS: local-inference-chat-batch-parity")
    print(f"  pairs compared: {len(reports)}")
    pass_n = sum(1 for r in reports if r["status"] == "pass")
    typed_n = sum(1 for r in reports if r["status"] == "divergence_typed")
    print(f"  byte-equivalent-on-projection: {pass_n}")
    print(f"  typed-divergence (evidence, not failure): {typed_n}")
    for d in DIVERGENCES:
        print(f"  DIVERGENCE[{d['tier']}/{d['pair']}] {d['field']}: {d['value']} — {d['note']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
