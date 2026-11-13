#!/usr/bin/env python3
"""Persona P1: MICRO/CARD injection, PERSONA=0 kill switch, canon-text parity."""
from __future__ import annotations

import hashlib
import importlib.util
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

import yaml

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "persona_llm_config", ROOT / "ai-stack/mcp-servers/shared/llm_config.py"
)
assert spec and spec.loader
llm = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = llm
spec.loader.exec_module(llm)

MSGS = [{"role": "user", "content": "hello"}]
LABEL_FORMAT = "Simurg@<lane>/<model>#<session>"


def _system(payload: dict) -> str:
    return "\n".join(m["content"] for m in payload["messages"] if m["role"] == "system")


def _build(env: dict, **kw) -> dict:
    with mock.patch.dict(os.environ, env, clear=False):
        return llm.build_llama_payload(MSGS, max_tokens=kw.pop("max_tokens", 500), **kw)


class PersonaInjection(unittest.TestCase):
    def test_on_by_default(self) -> None:
        env = {"PERSONA": "1", "AI_LOCAL_MODEL_ID": "qwen-test"}
        self.assertIn("Simurg@local/qwen-test", _system(_build(env, task_type="agent")))

    def test_kill_switch(self) -> None:
        self.assertNotIn("Simurg", _system(_build({"PERSONA": "0"}, task_type="agent")))

    def test_kill_switch_reproduces_pre_persona_wire(self) -> None:
        # System-message hashes of the pre-persona L2B golden vectors on origin/main.
        old = {"0": "6f1d503e5322704ab889b1be11379d2ea59530de4c42b8301a737e59c4562910",
               "1": "0b1e2fd0e7351527c7c18aaca1be3931671d4833cce490a0f6e732731c666c9b"}
        for fable, want in old.items():
            env = {"PERSONA": "0", "FABLE_PARITY": fable}
            payload = _build(env, role="implementer", task_type="agent", max_tokens=128)
            got = hashlib.sha256(_system(payload).encode()).hexdigest()
            self.assertEqual(got, want, f"FABLE_PARITY={fable}")

    def test_fable_off_does_not_disable_persona(self) -> None:
        s = _system(_build({"FABLE_PARITY": "0", "PERSONA": "1"}, task_type="agent"))
        self.assertIn("Simurg", s)
        self.assertNotIn(llm.FABLE_PARITY_SYSTEM_PROMPT, s)

    def test_persona_off_does_not_disable_fable(self) -> None:
        s = _system(_build({"FABLE_PARITY": "1", "PERSONA": "0"}, task_type="agent"))
        self.assertIn(llm.FABLE_PARITY_SYSTEM_PROMPT, s)

    def test_skipped_for_structured_and_small_budget(self) -> None:
        self.assertNotIn("Simurg", _system(_build({"PERSONA": "1"}, task_type="structured")))
        self.assertNotIn(
            "Simurg", _system(_build({"PERSONA": "1"}, task_type="agent", max_tokens=50))
        )

    def test_idempotent(self) -> None:
        once = llm._inject_persona(MSGS)
        twice = llm._inject_persona(once)
        self.assertEqual(once, twice)
        self.assertEqual(_system({"messages": twice}).count("Simurg@"), 1)


class CanonParity(unittest.TestCase):
    def setUp(self) -> None:
        self.canon = (ROOT / "canon/blocks/persona.md").read_text()

    def test_canon_has_name_and_label_format(self) -> None:
        self.assertIn(LABEL_FORMAT, self.canon)
        self.assertIn("Simurg", self.canon)

    def test_micro_matches_canon(self) -> None:
        self.assertTrue(llm.PERSONA_MICRO_TEMPLATE.startswith("Identity: you are Simurg@local/{model}"))
        self.assertIn("self-review", self.canon)
        self.assertIn("Never review or accept your own work", llm.PERSONA_MICRO_TEMPLATE)

    def test_card_matches_canon(self) -> None:
        doc = yaml.safe_load((ROOT / "config/switchboard-profiles.yaml").read_text())
        card = doc["_shared_bodies"]["PERSONA_BODY"]
        self.assertIn(LABEL_FORMAT, card)
        self.assertIn("self-review", card)
        profiles = doc["profiles"]
        used = [n for n, p in profiles.items() if "${PERSONA_BODY}" in (p.get("profileCard") or "")]
        fable = [n for n, p in profiles.items() if "${FABLE_PARITY_BODY}" in (p.get("profileCard") or "")]
        self.assertEqual(sorted(used), sorted(fable))

    def test_dispatch_fallback_text_matches_llm_config(self) -> None:
        src = (ROOT / "scripts/ai/lib/dispatch.py").read_text()
        tail = "one instance of the Simurg collective persona: grounded, candid and kind, "
        self.assertIn(tail, src)
        self.assertIn(tail, llm.PERSONA_MICRO_TEMPLATE)

    def test_summary_size_and_pointer(self) -> None:
        summary = (ROOT / "canon/blocks/persona.summary.md").read_bytes()
        self.assertLessEqual(len(summary), 520)
        self.assertIn(b"canon/blocks/persona.md", summary)


class SwitchboardKillSwitch(unittest.TestCase):
    def _catalog(self, persona: str) -> dict:
        path = ROOT / "ai-stack/switchboard/switchboard.py"
        sspec = importlib.util.spec_from_file_location("persona_swb", path)
        assert sspec and sspec.loader
        mod = importlib.util.module_from_spec(sspec)
        sys.modules[sspec.name] = mod
        sspec.loader.exec_module(mod)
        env = {"SWB_PROFILE_CATALOG_YAML_FILE": str(ROOT / "config/switchboard-profiles.yaml"), "PERSONA": persona}
        with mock.patch.dict(os.environ, env):
            return mod._load_profile_catalog()

    def test_card_resolved_and_killed(self) -> None:
        on = self._catalog("1")
        off = self._catalog("0")
        cards_on = [p.get("profileCard", "") for p in on.values() if isinstance(p, dict)]
        cards_off = [p.get("profileCard", "") for p in off.values() if isinstance(p, dict)]
        self.assertTrue(any("=== PERSONA ===" in c for c in cards_on))
        self.assertFalse(any("=== PERSONA ===" in c or "${PERSONA_BODY}" in c for c in cards_off))
        self.assertTrue(any("FABLE-PARITY BEHAVIOR" in c for c in cards_off))


if __name__ == "__main__":
    unittest.main()
