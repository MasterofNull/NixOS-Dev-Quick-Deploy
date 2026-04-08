#!/usr/bin/env python3
"""
Remote Agent Configuration and Handlers

Defines remote agent backends and their capabilities for task delegation.
"""

import asyncio
import json
import logging
import os
import subprocess
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiohttp

logger = logging.getLogger(__name__)


class RemoteAgentType(Enum):
    """Types of remote agents."""
    CLAUDE_OPUS = "claude-opus"
    CLAUDE_SONNET = "claude-sonnet"
    CLAUDE_HAIKU = "claude-haiku"
    GPT_4O = "gpt-4o"
    GPT_4O_MINI = "gpt-4o-mini"
    QWEN_CODER = "qwen-coder"
    OPENROUTER = "openrouter"  # Generic OpenRouter access


@dataclass
class AgentCapabilities:
    """Capabilities of a remote agent."""
    max_context: int
    supports_tools: bool
    supports_vision: bool
    supports_code: bool
    cost_per_mtok_input: float
    cost_per_mtok_output: float
    latency_class: str  # "fast", "medium", "slow"
    strengths: List[str] = field(default_factory=list)


@dataclass
class AgentConfig:
    """Configuration for a remote agent."""
    agent_type: RemoteAgentType
    model_id: str
    api_base: str
    api_key_env: str
    capabilities: AgentCapabilities
    enabled: bool = True
    max_retries: int = 2
    timeout_seconds: int = 120


# Agent configurations
AGENT_CONFIGS: Dict[RemoteAgentType, AgentConfig] = {
    RemoteAgentType.CLAUDE_OPUS: AgentConfig(
        agent_type=RemoteAgentType.CLAUDE_OPUS,
        model_id="claude-opus-4-5-20251101",
        api_base="https://api.anthropic.com/v1",
        api_key_env="ANTHROPIC_API_KEY",
        capabilities=AgentCapabilities(
            max_context=200000,
            supports_tools=True,
            supports_vision=True,
            supports_code=True,
            cost_per_mtok_input=15.0,
            cost_per_mtok_output=75.0,
            latency_class="slow",
            strengths=["architecture", "security", "complex_reasoning", "planning"],
        ),
    ),
    RemoteAgentType.CLAUDE_SONNET: AgentConfig(
        agent_type=RemoteAgentType.CLAUDE_SONNET,
        model_id="claude-sonnet-4-5-20250929",
        api_base="https://api.anthropic.com/v1",
        api_key_env="ANTHROPIC_API_KEY",
        capabilities=AgentCapabilities(
            max_context=200000,
            supports_tools=True,
            supports_vision=True,
            supports_code=True,
            cost_per_mtok_input=3.0,
            cost_per_mtok_output=15.0,
            latency_class="medium",
            strengths=["implementation", "refactoring", "code_review"],
        ),
    ),
    RemoteAgentType.CLAUDE_HAIKU: AgentConfig(
        agent_type=RemoteAgentType.CLAUDE_HAIKU,
        model_id="claude-3-5-haiku-20241022",
        api_base="https://api.anthropic.com/v1",
        api_key_env="ANTHROPIC_API_KEY",
        capabilities=AgentCapabilities(
            max_context=200000,
            supports_tools=True,
            supports_vision=True,
            supports_code=True,
            cost_per_mtok_input=0.8,
            cost_per_mtok_output=4.0,
            latency_class="fast",
            strengths=["quick_tasks", "simple_implementation", "documentation"],
        ),
    ),
    RemoteAgentType.GPT_4O: AgentConfig(
        agent_type=RemoteAgentType.GPT_4O,
        model_id="gpt-4o",
        api_base="https://api.openai.com/v1",
        api_key_env="OPENAI_API_KEY",
        capabilities=AgentCapabilities(
            max_context=128000,
            supports_tools=True,
            supports_vision=True,
            supports_code=True,
            cost_per_mtok_input=5.0,
            cost_per_mtok_output=15.0,
            latency_class="medium",
            strengths=["general_purpose", "code_generation", "analysis"],
        ),
    ),
    RemoteAgentType.GPT_4O_MINI: AgentConfig(
        agent_type=RemoteAgentType.GPT_4O_MINI,
        model_id="gpt-4o-mini",
        api_base="https://api.openai.com/v1",
        api_key_env="OPENAI_API_KEY",
        capabilities=AgentCapabilities(
            max_context=128000,
            supports_tools=True,
            supports_vision=True,
            supports_code=True,
            cost_per_mtok_input=0.15,
            cost_per_mtok_output=0.6,
            latency_class="fast",
            strengths=["quick_tasks", "simple_code", "formatting"],
        ),
    ),
    RemoteAgentType.QWEN_CODER: AgentConfig(
        agent_type=RemoteAgentType.QWEN_CODER,
        model_id="qwen/qwen-2.5-coder-32b-instruct",
        api_base="https://openrouter.ai/api/v1",
        api_key_env="OPENROUTER_API_KEY",
        capabilities=AgentCapabilities(
            max_context=131072,
            supports_tools=False,
            supports_vision=False,
            supports_code=True,
            cost_per_mtok_input=0.8,
            cost_per_mtok_output=0.8,
            latency_class="medium",
            strengths=["code_implementation", "testing", "refactoring"],
        ),
    ),
}


@dataclass
class RemoteAgentResponse:
    """Response from a remote agent."""
    success: bool
    content: str
    model_used: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    execution_time: float = 0.0
    error: Optional[str] = None


class RemoteAgentClient:
    """
    Client for interacting with remote AI agents.

    Handles authentication, retries, and response parsing.
    """

    def __init__(self):
        self._stats = {
            "calls": 0,
            "successes": 0,
            "failures": 0,
            "total_cost": 0.0,
        }

    def _get_api_key(self, env_var: str) -> Optional[str]:
        """Get API key from environment or secrets."""
        # Check environment
        key = os.getenv(env_var)
        if key:
            return key

        # Check secrets file
        secret_name = env_var.lower().replace("_", "-")
        secret_path = Path(f"/run/secrets/{secret_name}")
        if secret_path.exists():
            return secret_path.read_text().strip()

        # Check home directory
        home_path = Path.home() / f".{secret_name}"
        if home_path.exists():
            return home_path.read_text().strip()

        return None

    async def call_anthropic(
        self,
        config: AgentConfig,
        messages: List[Dict[str, str]],
        system: Optional[str] = None,
        max_tokens: int = 4096,
    ) -> RemoteAgentResponse:
        """Call Anthropic API."""
        start_time = time.time()
        self._stats["calls"] += 1

        api_key = self._get_api_key(config.api_key_env)
        if not api_key:
            return RemoteAgentResponse(
                success=False,
                content="",
                model_used=config.model_id,
                error=f"API key not found: {config.api_key_env}",
            )

        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                }

                payload = {
                    "model": config.model_id,
                    "max_tokens": max_tokens,
                    "messages": messages,
                }
                if system:
                    payload["system"] = system

                async with session.post(
                    f"{config.api_base}/messages",
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=config.timeout_seconds),
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        self._stats["failures"] += 1
                        return RemoteAgentResponse(
                            success=False,
                            content="",
                            model_used=config.model_id,
                            error=f"API error {response.status}: {error_text[:200]}",
                        )

                    data = await response.json()

                    # Extract response
                    content_blocks = data.get("content", [])
                    content = ""
                    for block in content_blocks:
                        if block.get("type") == "text":
                            content += block.get("text", "")

                    # Calculate cost
                    usage = data.get("usage", {})
                    input_tokens = usage.get("input_tokens", 0)
                    output_tokens = usage.get("output_tokens", 0)
                    cost = (
                        input_tokens / 1_000_000 * config.capabilities.cost_per_mtok_input
                        + output_tokens / 1_000_000 * config.capabilities.cost_per_mtok_output
                    )

                    self._stats["successes"] += 1
                    self._stats["total_cost"] += cost

                    return RemoteAgentResponse(
                        success=True,
                        content=content,
                        model_used=config.model_id,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        cost_usd=cost,
                        execution_time=time.time() - start_time,
                    )

        except asyncio.TimeoutError:
            self._stats["failures"] += 1
            return RemoteAgentResponse(
                success=False,
                content="",
                model_used=config.model_id,
                error=f"Timeout after {config.timeout_seconds}s",
                execution_time=time.time() - start_time,
            )
        except Exception as e:
            self._stats["failures"] += 1
            return RemoteAgentResponse(
                success=False,
                content="",
                model_used=config.model_id,
                error=str(e),
                execution_time=time.time() - start_time,
            )

    async def call_openai(
        self,
        config: AgentConfig,
        messages: List[Dict[str, str]],
        max_tokens: int = 4096,
    ) -> RemoteAgentResponse:
        """Call OpenAI-compatible API."""
        start_time = time.time()
        self._stats["calls"] += 1

        api_key = self._get_api_key(config.api_key_env)
        if not api_key:
            return RemoteAgentResponse(
                success=False,
                content="",
                model_used=config.model_id,
                error=f"API key not found: {config.api_key_env}",
            )

        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                }

                # OpenRouter requires HTTP-Referer
                if "openrouter" in config.api_base:
                    headers["HTTP-Referer"] = "https://github.com/nixos-quick-deploy"

                payload = {
                    "model": config.model_id,
                    "max_tokens": max_tokens,
                    "messages": messages,
                }

                async with session.post(
                    f"{config.api_base}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=config.timeout_seconds),
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        self._stats["failures"] += 1
                        return RemoteAgentResponse(
                            success=False,
                            content="",
                            model_used=config.model_id,
                            error=f"API error {response.status}: {error_text[:200]}",
                        )

                    data = await response.json()

                    # Extract response
                    choices = data.get("choices", [])
                    content = ""
                    if choices:
                        content = choices[0].get("message", {}).get("content", "")

                    # Calculate cost
                    usage = data.get("usage", {})
                    input_tokens = usage.get("prompt_tokens", 0)
                    output_tokens = usage.get("completion_tokens", 0)
                    cost = (
                        input_tokens / 1_000_000 * config.capabilities.cost_per_mtok_input
                        + output_tokens / 1_000_000 * config.capabilities.cost_per_mtok_output
                    )

                    self._stats["successes"] += 1
                    self._stats["total_cost"] += cost

                    return RemoteAgentResponse(
                        success=True,
                        content=content,
                        model_used=config.model_id,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        cost_usd=cost,
                        execution_time=time.time() - start_time,
                    )

        except asyncio.TimeoutError:
            self._stats["failures"] += 1
            return RemoteAgentResponse(
                success=False,
                content="",
                model_used=config.model_id,
                error=f"Timeout after {config.timeout_seconds}s",
                execution_time=time.time() - start_time,
            )
        except Exception as e:
            self._stats["failures"] += 1
            return RemoteAgentResponse(
                success=False,
                content="",
                model_used=config.model_id,
                error=str(e),
                execution_time=time.time() - start_time,
            )

    async def call(
        self,
        agent_type: RemoteAgentType,
        messages: List[Dict[str, str]],
        system: Optional[str] = None,
        max_tokens: int = 4096,
    ) -> RemoteAgentResponse:
        """
        Call a remote agent.

        Args:
            agent_type: Which agent to use
            messages: Chat messages
            system: Optional system prompt
            max_tokens: Maximum output tokens

        Returns:
            RemoteAgentResponse
        """
        config = AGENT_CONFIGS.get(agent_type)
        if not config:
            return RemoteAgentResponse(
                success=False,
                content="",
                model_used="unknown",
                error=f"Unknown agent type: {agent_type}",
            )

        if not config.enabled:
            return RemoteAgentResponse(
                success=False,
                content="",
                model_used=config.model_id,
                error=f"Agent disabled: {agent_type.value}",
            )

        # Route to appropriate API
        if "anthropic" in config.api_base:
            return await self.call_anthropic(config, messages, system, max_tokens)
        else:
            # OpenAI-compatible (including OpenRouter)
            if system:
                messages = [{"role": "system", "content": system}] + messages
            return await self.call_openai(config, messages, max_tokens)

    def get_available_agents(self) -> List[Dict[str, Any]]:
        """Get list of available agents with their capabilities."""
        agents = []
        for agent_type, config in AGENT_CONFIGS.items():
            if self._get_api_key(config.api_key_env):
                agents.append({
                    "type": agent_type.value,
                    "model": config.model_id,
                    "enabled": config.enabled,
                    "capabilities": {
                        "max_context": config.capabilities.max_context,
                        "supports_tools": config.capabilities.supports_tools,
                        "supports_vision": config.capabilities.supports_vision,
                        "latency": config.capabilities.latency_class,
                        "strengths": config.capabilities.strengths,
                    },
                })
        return agents

    def get_stats(self) -> Dict[str, Any]:
        """Get usage statistics."""
        return dict(self._stats)


# Singleton
_client: Optional[RemoteAgentClient] = None


def get_remote_client() -> RemoteAgentClient:
    """Get global remote agent client."""
    global _client
    if _client is None:
        _client = RemoteAgentClient()
    return _client


# Example usage
async def main():
    """Test remote agent calls."""
    client = get_remote_client()

    print("Available agents:")
    for agent in client.get_available_agents():
        print(f"  {agent['type']}: {agent['model']}")
        print(f"    Strengths: {', '.join(agent['capabilities']['strengths'])}")

    # Test call if API key available
    if client._get_api_key("ANTHROPIC_API_KEY"):
        print("\nTesting Claude Haiku...")
        response = await client.call(
            RemoteAgentType.CLAUDE_HAIKU,
            [{"role": "user", "content": "Say hello in 5 words."}],
        )
        print(f"  Success: {response.success}")
        print(f"  Content: {response.content}")
        print(f"  Cost: ${response.cost_usd:.4f}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
