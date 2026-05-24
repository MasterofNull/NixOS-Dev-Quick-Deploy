#!/usr/bin/env python3
"""Regression test for trading handler package import wiring."""

import importlib.util
from importlib.machinery import SourceFileLoader
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
HANDLERS = REPO_ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator" / "extensions" / "trading_handlers.py"


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    loader = SourceFileLoader("trading_handlers_under_test", str(HANDLERS))
    spec = importlib.util.spec_from_loader("trading_handlers_under_test", loader)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    module._ensure_trading_agents_package()

    import trading_agents
    from trading_agents.graph.state import AgentState, initial_state

    assert_true(Path(trading_agents.__file__).as_posix().endswith("trading-agents/__init__.py"), "wrong package alias target")
    state = initial_state("AAPL", "2026-05-24")
    assert_true(isinstance(state, dict), "initial_state should return dict-like AgentState")
    assert_true("ticker" in AgentState.__annotations__, "AgentState annotations should be available")

    print("PASS: trading_handlers imports hyphenated trading-agents package")


if __name__ == "__main__":
    main()
