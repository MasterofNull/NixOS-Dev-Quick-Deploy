import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from llm_router import AgentTier, LLMRouter


class LLMRouterTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.metrics_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.metrics_db.close()
        self.router = LLMRouter(metrics_db=self.metrics_db.name)

    async def test_execute_free_uses_coordinator_delegate(self):
        with patch.object(
            self.router,
            "_execute_via_coordinator",
            AsyncMock(return_value="FREE_OK"),
        ) as delegated:
            result = await self.router._execute_free(
                {"description": "implement patch", "context": {}},
                "qwen-coder",
            )

        self.assertEqual(result, "FREE_OK")
        delegated.assert_awaited_once()
        self.assertEqual(delegated.await_args.kwargs["profile"], "remote-coding")
        self.assertFalse(delegated.await_args.kwargs["prefer_local"])

    async def test_execute_paid_uses_reasoning_profile(self):
        with patch.object(
            self.router,
            "_execute_via_coordinator",
            AsyncMock(return_value="PAID_OK"),
        ) as delegated:
            result = await self.router._execute_paid(
                {"description": "architecture decision", "context": {}},
                "claude-sonnet",
            )

        self.assertEqual(result, "PAID_OK")
        delegated.assert_awaited_once()
        self.assertEqual(delegated.await_args.kwargs["profile"], "remote-reasoning")

    async def test_execute_critical_uses_reasoning_profile_until_flagship_exists(self):
        with patch.object(
            self.router,
            "_execute_via_coordinator",
            AsyncMock(return_value="CRITICAL_OK"),
        ) as delegated:
            result = await self.router._execute_paid(
                {"description": "critical architectural decision", "context": {}},
                "claude-opus",
            )

        self.assertEqual(result, "CRITICAL_OK")
        delegated.assert_awaited_once()
        self.assertEqual(delegated.await_args.kwargs["profile"], "remote-reasoning")

    async def test_execute_with_routing_escalates_from_local_to_free(self):
        local_fail = AsyncMock(side_effect=Exception("local failed"))
        free_success = AsyncMock(return_value="FREE_RECOVERY")

        with patch.object(self.router, "_execute_local", local_fail):
            with patch.object(self.router, "_execute_free", free_success):
                result = await self.router.execute_with_routing(
                    {
                        "description": "search logs",
                        "context": {},
                        "type": "search",
                        "allow_escalation": True,
                    }
                )

        self.assertEqual(result["result"], "FREE_RECOVERY")
        self.assertEqual(result["tier"], AgentTier.FREE.value)
        self.assertTrue(result["escalated"])
        self.assertEqual(result["escalated_from"], AgentTier.LOCAL.value)

    def test_extract_response_text_handles_common_shapes(self):
        self.assertEqual(
            self.router._extract_response_text({"result": {"content": "A"}}),
            "A",
        )
        self.assertEqual(
            self.router._extract_response_text(
                {"choices": [{"message": {"content": "B"}}]}
            ),
            "B",
        )
        self.assertEqual(
            self.router._extract_response_text({"data": {"output": "C"}}),
            "C",
        )

    def test_build_prompt_includes_advisor_guidance(self):
        prompt = self.router._build_prompt(
            {
                "description": "review the architecture change",
                "context": {"summary": "routing cleanup"},
                "advisor_guidance": {
                    "action": "modify",
                    "guidance": "Prefer the validated coordinator profile.",
                    "reasoning": "The prior mapping drifted from switchboard profile names.",
                },
            },
            optimize_for="remote",
        )
        self.assertIn("<advisor_guidance action=\"modify\">", prompt)
        self.assertIn("Prefer the validated coordinator profile.", prompt)

    def test_get_advisor_metrics_handles_empty_db(self):
        self.router.advisor_enabled = True
        metrics = self.router.get_advisor_metrics()
        self.assertTrue(metrics["advisor_enabled"])
        self.assertEqual(metrics["total_consultations"], 0)
        self.assertEqual(metrics["consultation_rate_percent"], 0)


if __name__ == "__main__":
    unittest.main()
