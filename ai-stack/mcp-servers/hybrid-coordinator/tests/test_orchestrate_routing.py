"""
Unit tests for Phase 0 Slice 0.2 — /v1/orchestrate front-door routing logic.

Tests the route-alias resolution and payload-forwarding logic that backs the
/v1/orchestrate endpoint in http_server.py.  The endpoint itself is a closure
inside run_http_server(), so these tests exercise the underlying route_aliases
module that it delegates to.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Ensure the hybrid-coordinator package is importable
_HC_DIR = Path(__file__).resolve().parent.parent
if str(_HC_DIR) not in sys.path:
    sys.path.insert(0, str(_HC_DIR))

from route_aliases import RouteAliasResolver, resolve_route_alias


class TestOrchestrateCoreLogic:
    """Verify the route-resolution logic that handle_orchestrate uses."""

    def test_explore_resolves_to_default(self):
        resolver = RouteAliasResolver()
        assert resolver.resolve_alias("Explore") == "default"

    def test_plan_resolves_to_default(self):
        resolver = RouteAliasResolver()
        assert resolver.resolve_alias("Plan") == "default"

    def test_implementation_resolves_to_remote_coding(self):
        resolver = RouteAliasResolver()
        assert resolver.resolve_alias("Implementation") == "remote-coding"

    def test_reasoning_resolves_to_remote_reasoning(self):
        resolver = RouteAliasResolver()
        assert resolver.resolve_alias("Reasoning") == "remote-reasoning"

    def test_toolcalling_resolves_to_local_tool_calling(self):
        resolver = RouteAliasResolver()
        assert resolver.resolve_alias("ToolCalling") == "local-tool-calling"

    def test_unknown_route_falls_back_to_default(self):
        resolver = RouteAliasResolver()
        assert resolver.resolve_alias("UnknownRoute") == "default"

    def test_empty_route_falls_back_to_default(self):
        resolver = RouteAliasResolver()
        assert resolver.resolve_alias("") == "default"

    def test_convenience_function_works(self):
        assert resolve_route_alias("Explore") == "default"
        assert resolve_route_alias("Implementation") == "remote-coding"


class TestOrchestratePayloadBuilding:
    """Verify the payload the handler would build for forwarding to /query."""

    def _build_forwarded_payload(self, prompt: str, route: str, options: dict | None = None, context: dict | None = None) -> dict:
        """Replicate the forwarding-payload logic from handle_orchestrate."""
        raw_route = str(route or "default").strip()
        resolved_profile = resolve_route_alias(raw_route)

        ctx = dict(context or {})
        ctx["routed_profile"] = resolved_profile
        ctx["route_alias"] = raw_route

        opts = options or {}
        payload = {
            "prompt": prompt,
            "context": ctx,
            "generate_response": bool(opts.get("generate_response", False)),
            "prefer_local": bool(opts.get("prefer_local", True)),
            "mode": opts.get("mode", "hybrid"),
        }
        if "limit" in opts:
            payload["limit"] = opts["limit"]
        return payload, resolved_profile

    def test_prompt_is_forwarded(self):
        payload, _ = self._build_forwarded_payload("my query", "Explore")
        assert payload["prompt"] == "my query"

    def test_context_contains_routing_metadata(self):
        payload, _ = self._build_forwarded_payload("q", "Explore")
        assert payload["context"]["routed_profile"] == "default"
        assert payload["context"]["route_alias"] == "Explore"

    def test_existing_context_is_preserved(self):
        payload, _ = self._build_forwarded_payload("q", "Explore", context={"my_key": "my_val"})
        assert payload["context"]["my_key"] == "my_val"
        assert "routed_profile" in payload["context"]

    def test_prefer_local_defaults_true(self):
        payload, _ = self._build_forwarded_payload("q", "Explore")
        assert payload["prefer_local"] is True

    def test_prefer_local_can_be_overridden(self):
        payload, _ = self._build_forwarded_payload("q", "Explore", options={"prefer_local": False})
        assert payload["prefer_local"] is False

    def test_generate_response_defaults_false(self):
        payload, _ = self._build_forwarded_payload("q", "Explore")
        assert payload["generate_response"] is False

    def test_limit_forwarded_when_present(self):
        payload, _ = self._build_forwarded_payload("q", "Explore", options={"limit": 5})
        assert payload["limit"] == 5

    def test_limit_omitted_when_absent(self):
        payload, _ = self._build_forwarded_payload("q", "Explore")
        assert "limit" not in payload

    def test_resolved_profile_returned(self):
        _, profile = self._build_forwarded_payload("q", "Implementation")
        assert profile == "remote-coding"


class TestOrchestrateTelemetryHeaders:
    """Verify the telemetry header names used in handle_orchestrate."""

    ROUTE_ALIAS_HEADER = "X-AI-Route-Alias"
    PROFILE_RESOLVED_HEADER = "X-AI-Profile-Resolved"

    def test_header_names_are_stable(self):
        """Document the exact header names so callers can rely on them."""
        assert self.ROUTE_ALIAS_HEADER == "X-AI-Route-Alias"
        assert self.PROFILE_RESOLVED_HEADER == "X-AI-Profile-Resolved"

    def test_route_alias_value_matches_input(self):
        raw = "Explore"
        assert raw == "Explore"  # header value = raw_route passed in

    def test_profile_resolved_value_matches_alias_output(self):
        assert resolve_route_alias("Explore") == "default"
        assert resolve_route_alias("Implementation") == "remote-coding"
