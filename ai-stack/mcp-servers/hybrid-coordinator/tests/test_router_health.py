"""Hermetic regression checks for the "router recommends a dead lane" fix
in `llm_router.LLMRouter.route_task()` and
`model_coordinator.ModelCoordinator.classify_and_route()`.

Both used to hardcode "qwen-coder" / "llama-cpp-local" with no health
check. This suite proves the fixed versions (a) exclude a lane flagged
down, (b) fall back to a healthy lane (codex or claude) when the
preferred/local lane is down, (c) return the normal preferred lane with
no health flags present, and (d) never return a bare unhealthy
"qwen-coder"/local literal while it is flagged down — and that "codex" is
now a selectable AgentTier.

No running service, no network: health-signal state is scoped to a
per-test temp directory via monkeypatching the dynamically-loaded
aq-role-route submodule's `DELEGATION_DIR` / `CODEX_COOLDOWN_FILE`
globals, exactly as `scripts/testing/test-agent-agnostic-router.py` and
`scripts/testing/test-model-tiering-health.py` do for the same
aq-role-route probe.
"""

import importlib
import tempfile
import unittest
from pathlib import Path

import knowledge.llm_router as llm_router_impl  # noqa: E402 - real module (private health internals)
from llm_router import AgentTier  # noqa: E402 - public re-export via the top-level shim, sanity check

from model_coordinator import ModelCoordinator  # noqa: E402 - public API only


def _reset_health(tmp: Path) -> None:
    """Point the aq-role-route submodule llm_router.py dynamically loaded
    at module-import time at an empty per-test temp directory. Both
    llm_router.py and model_coordinator.py's `_lane_health` ultimately
    call this same loaded module's `_lane_health`, so resetting it here
    covers both files' health signal in one place."""
    role_route = llm_router_impl._ROLE_ROUTE
    assert role_route is not None, "aq-role-route failed to load — cannot test health-awareness"
    role_route.DELEGATION_DIR = tmp
    role_route.CODEX_COOLDOWN_FILE = tmp / ".codex-quota-cooldown"


class LLMRouterHealthTests(unittest.TestCase):
    def setUp(self):
        self.metrics_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.metrics_db.close()
        self.router = llm_router_impl.LLMRouter(metrics_db=self.metrics_db.name)
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmpdir.name)
        _reset_health(self.tmp)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_codex_is_a_selectable_tier(self):
        self.assertIn(AgentTier.CODEX, list(llm_router_impl.AgentTier))
        self.assertEqual(AgentTier.CODEX.value, "codex")

    def test_no_flags_returns_normal_preferred_lane(self):
        tier, model = self.router.route_task("list files in src")
        self.assertEqual(tier, AgentTier.LOCAL)
        self.assertEqual(model, "llama-cpp-local")

    def test_local_down_excludes_local_and_falls_back_to_codex(self):
        (self.tmp / ".local-down").write_text("simulated outage\n", encoding="utf-8")

        tier, model = self.router.route_task("list files in src")

        self.assertNotEqual(tier, AgentTier.LOCAL)
        self.assertNotEqual(model, "llama-cpp-local")
        self.assertEqual((tier, model), (AgentTier.CODEX, "codex"))

    def test_local_down_also_redirects_qwen_coder_medium_task(self):
        # "qwen-coder" (OpenRouter free-tier) shares the "local" lane's
        # health signal per aq-role-route's own alias table (bare "qwen"
        # == local lane in this harness) — the exact defect this closes.
        (self.tmp / ".local-down").write_text("simulated outage\n", encoding="utf-8")

        tier, model = self.router.route_task("implementation task: implement a code fix")

        self.assertNotEqual(model, "qwen-coder")
        self.assertEqual((tier, model), (AgentTier.CODEX, "codex"))

    def test_local_and_codex_down_falls_back_to_claude(self):
        (self.tmp / ".local-down").write_text("down\n", encoding="utf-8")
        (self.tmp / ".codex-down").write_text("down\n", encoding="utf-8")

        tier, model = self.router.route_task("list files in src")

        self.assertEqual((tier, model), (AgentTier.PAID, "claude-sonnet"))

    def test_codex_quota_cooldown_file_is_honored(self):
        from datetime import datetime, timedelta, timezone

        (self.tmp / ".local-down").write_text("down\n", encoding="utf-8")
        future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        (self.tmp / ".codex-quota-cooldown").write_text(future + "\n", encoding="utf-8")

        tier, model = self.router.route_task("list files in src")

        self.assertNotEqual(model, "codex")
        self.assertEqual((tier, model), (AgentTier.PAID, "claude-sonnet"))


class ModelCoordinatorHealthTests(unittest.TestCase):
    def setUp(self):
        self.coordinator = ModelCoordinator()
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmpdir.name)
        _reset_health(self.tmp)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_no_flags_returns_normal_preferred_lane(self):
        decision = self.coordinator.classify_and_route(
            "what is the current status, show me a quick simple answer", use_tier_routing=False
        )
        self.assertEqual(decision.primary_model, "llama-cpp-local")
        self.assertNotIn("health-fallback", decision.routing_rationale)

    def test_local_down_excludes_local_candidate(self):
        (self.tmp / ".local-down").write_text("down\n", encoding="utf-8")

        decision = self.coordinator.classify_and_route(
            "what is the current status, show me a quick simple answer", use_tier_routing=False
        )

        self.assertNotEqual(decision.primary_model, "llama-cpp-local")

    def test_all_coding_lanes_down_except_codex_recommends_codex(self):
        # Force role=CODING candidates only (qwen-coder, codex are both
        # role=CODING; llama-cpp-local is role=FAST_CHAT so it never
        # competes here) by flagging qwen-coder's lane (local) down.
        (self.tmp / ".local-down").write_text("down\n", encoding="utf-8")

        decision = self.coordinator.classify_and_route(
            "implement and refactor the coding module", use_tier_routing=False
        )

        self.assertEqual(decision.primary_model, "codex")
        self.assertNotIn(decision.primary_model, ("qwen-coder",))

    def test_never_returns_bare_unhealthy_qwen_coder_literal(self):
        # Simulate "no role-matching candidate survived filtering" by
        # flagging every ladder lane down; the fallback must not silently
        # hand back the bare "qwen-coder" literal as if it were healthy —
        # it must say so in the rationale.
        for lane in ("local", "codex", "claude"):
            (self.tmp / f".{lane}-down").write_text("down\n", encoding="utf-8")

        coordinator = ModelCoordinator()
        # Remove every non-embedding profile except one CODING profile so
        # primary_candidates is empty after health filtering, forcing the
        # fallback branch deterministically regardless of classification.
        coordinator._profiles = {
            name: p for name, p in coordinator._profiles.items()
            if name in ("qwen-coder", "codex", "llama-cpp-local")
        }

        decision = coordinator.classify_and_route(
            "implement and refactor the coding module", use_tier_routing=False
        )

        self.assertIn("health-fallback", decision.routing_rationale)
        self.assertIn("last-resort", decision.routing_rationale)


if __name__ == "__main__":
    unittest.main()
