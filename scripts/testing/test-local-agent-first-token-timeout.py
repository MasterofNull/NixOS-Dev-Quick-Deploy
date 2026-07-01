#!/usr/bin/env python3
"""Static regression checks for local-agent no-progress inference timeout."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AGENT_LOOP = ROOT / "scripts/ai/aq-agent-loop"
EXECUTOR = ROOT / "ai-stack/local-agents/agent_executor.py"
QA = ROOT / "scripts/ai/_aq-qa-bash"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    loop = AGENT_LOOP.read_text(encoding="utf-8")
    executor = EXECUTOR.read_text(encoding="utf-8")
    qa = QA.read_text(encoding="utf-8")

    require("LLAMA_FIRST_TOKEN_TIMEOUT" in loop, "aq-agent-loop must set first-token timeout")
    require("min(1800.0, float(timeout_secs) * 0.5)" in loop, "timeout must be bounded below outer timeout (cap 1800s for large-context overnight tasks)")
    require("first_token_timeout = _env_float(" in executor, "executor must read first-token timeout")
    require("read_timeout = min(chunk_timeout, first_token_timeout)" in executor, "read timeout must cap silent waits")
    require("LLM no-progress timeout" in executor, "timeout error must identify no-progress failure")
    require("0.10.32" in qa, "phase-0 QA missing first-token timeout check")

    print("ok local-agent first-token timeout wiring")


if __name__ == "__main__":
    main()
