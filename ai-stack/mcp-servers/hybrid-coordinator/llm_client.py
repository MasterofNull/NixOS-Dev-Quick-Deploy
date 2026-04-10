"""
LLM Client for Workflow Execution

Provides unified interface to LLM providers (Anthropic, OpenAI, etc.)
for workflow execution.

Created: 2026-04-09
Purpose: Enable real workflow execution with LLM APIs
"""

import os
import logging
import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

logger = logging.getLogger("llm-client")


@dataclass
class LLMResponse:
    """Standardized LLM response structure"""
    content: str
    tool_calls: List[Dict[str, Any]]
    usage: Dict[str, int]
    stop_reason: str
    model: str


class LLMClient:
    """
    Unified LLM client interface.

    Supports:
    - Anthropic Claude API
    - OpenAI API (future)
    - Local models via llama.cpp (future)
    """

    def __init__(
        self,
        provider: str = "anthropic",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        """
        Initialize LLM client.

        Args:
            provider: "anthropic", "openai", or "local"
            api_key: API key (or None for local)
            base_url: Custom API base URL
        """
        self.provider = provider
        self.api_key = api_key or self._get_api_key(provider)
        self.base_url = base_url

        if provider == "anthropic":
            self._init_anthropic()
        elif provider == "openai":
            self._init_openai()
        elif provider == "local":
            self._init_local()
        else:
            raise ValueError(f"Unknown provider: {provider}")

    def _get_api_key(self, provider: str) -> Optional[str]:
        """
        Get API key from environment or file.

        Priority order:
        1. Environment variable (*_API_KEY)
        2. Explicit file path (*_API_KEY_FILE)
        3. sops-nix decrypted secret (/run/secrets/*)
        4. Local development file (~/.config/*)
        """
        if provider == "anthropic":
            # 1. Environment variable
            key = os.getenv("ANTHROPIC_API_KEY")
            if key:
                logger.debug("Using Anthropic API key from ANTHROPIC_API_KEY")
                return key

            # 2. Explicit file path
            key_file = os.getenv("ANTHROPIC_API_KEY_FILE", "")
            if key_file and os.path.exists(key_file):
                logger.debug(f"Using Anthropic API key from {key_file}")
                with open(key_file) as f:
                    return f.read().strip()

            # 3. sops-nix decrypted secret (NixOS deployment)
            sops_paths = [
                "/run/secrets/anthropic_api_key",
                "/run/secrets/remote_llm_api_key",  # Reuse existing remote LLM key
                "/run/secrets/workflow_executor_api_key",  # Dedicated executor key
            ]
            for sops_path in sops_paths:
                if os.path.exists(sops_path):
                    logger.info(f"Using Anthropic API key from sops-nix: {sops_path}")
                    with open(sops_path) as f:
                        return f.read().strip()

            # 4. Local development file (fallback)
            dev_paths = [
                os.path.expanduser("~/.config/anthropic/api-key"),
                os.path.expanduser("~/.anthropic-api-key"),
            ]
            for dev_path in dev_paths:
                if os.path.exists(dev_path):
                    logger.debug(f"Using Anthropic API key from {dev_path}")
                    with open(dev_path) as f:
                        return f.read().strip()

        elif provider == "openai":
            # 1. Environment variable
            key = os.getenv("OPENAI_API_KEY")
            if key:
                logger.debug("Using OpenAI API key from OPENAI_API_KEY")
                return key

            # 2. Explicit file path
            key_file = os.getenv("OPENAI_API_KEY_FILE", "")
            if key_file and os.path.exists(key_file):
                logger.debug(f"Using OpenAI API key from {key_file}")
                with open(key_file) as f:
                    return f.read().strip()

            # 3. sops-nix decrypted secret
            sops_paths = [
                "/run/secrets/openai_api_key",
                "/run/secrets/remote_llm_api_key",
            ]
            for sops_path in sops_paths:
                if os.path.exists(sops_path):
                    logger.info(f"Using OpenAI API key from sops-nix: {sops_path}")
                    with open(sops_path) as f:
                        return f.read().strip()

            # 4. Local development file
            dev_paths = [
                os.path.expanduser("~/.config/openai/api-key"),
                os.path.expanduser("~/.openai-api-key"),
            ]
            for dev_path in dev_paths:
                if os.path.exists(dev_path):
                    logger.debug(f"Using OpenAI API key from {dev_path}")
                    with open(dev_path) as f:
                        return f.read().strip()

        return None

    def _init_anthropic(self):
        """Initialize Anthropic client"""
        try:
            from anthropic import AsyncAnthropic

            if not self.api_key:
                logger.warning("No Anthropic API key found - client will fail on actual use")
                self.client = None
            else:
                self.client = AsyncAnthropic(api_key=self.api_key)

            self.default_model = "claude-3-5-sonnet-20250219"

        except ImportError:
            logger.error("anthropic package not installed. Install with: pip install anthropic")
            self.client = None

    def _init_openai(self):
        """Initialize OpenAI client"""
        try:
            from openai import AsyncOpenAI

            if not self.api_key:
                logger.warning("No OpenAI API key found")
                self.client = None
            else:
                self.client = AsyncOpenAI(api_key=self.api_key)

            self.default_model = "gpt-4-turbo-preview"

        except ImportError:
            logger.error("openai package not installed. Install with: pip install openai")
            self.client = None

    def _init_local(self):
        """Initialize local model client"""
        # Future: llama.cpp integration
        self.client = None
        self.default_model = "local"
        logger.info("Local model support not yet implemented")

    async def create_message(
        self,
        prompt: str,
        model: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 1.0,
        tools: Optional[List[Dict[str, Any]]] = None,
        system: Optional[str] = None,
    ) -> LLMResponse:
        """
        Create a message completion.

        Args:
            prompt: User prompt/query
            model: Model to use (default: provider default)
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            tools: Available tools for function calling
            system: System prompt

        Returns:
            LLMResponse with content, tool calls, and usage

        Raises:
            RuntimeError: If client not initialized or API error
        """
        if not self.client:
            raise RuntimeError(f"LLM client not initialized for provider: {self.provider}")

        model = model or self.default_model

        if self.provider == "anthropic":
            return await self._anthropic_create_message(
                prompt, model, max_tokens, temperature, tools, system
            )
        elif self.provider == "openai":
            return await self._openai_create_message(
                prompt, model, max_tokens, temperature, tools, system
            )
        else:
            raise NotImplementedError(f"Provider {self.provider} not implemented")

    async def _anthropic_create_message(
        self,
        prompt: str,
        model: str,
        max_tokens: int,
        temperature: float,
        tools: Optional[List[Dict[str, Any]]],
        system: Optional[str],
    ) -> LLMResponse:
        """Anthropic-specific message creation"""
        try:
            kwargs = {
                "model": model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": [{"role": "user", "content": prompt}],
            }

            if system:
                kwargs["system"] = system

            if tools:
                kwargs["tools"] = tools

            response = await self.client.messages.create(**kwargs)

            # Parse tool calls
            tool_calls = []
            content_text = ""

            for block in response.content:
                if block.type == "text":
                    content_text += block.text
                elif block.type == "tool_use":
                    tool_calls.append({
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    })

            return LLMResponse(
                content=content_text,
                tool_calls=tool_calls,
                usage={
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                    "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
                },
                stop_reason=response.stop_reason,
                model=response.model,
            )

        except Exception as e:
            logger.error(f"Anthropic API error: {e}", exc_info=True)
            raise RuntimeError(f"Failed to create message: {e}")

    async def _openai_create_message(
        self,
        prompt: str,
        model: str,
        max_tokens: int,
        temperature: float,
        tools: Optional[List[Dict[str, Any]]],
        system: Optional[str],
    ) -> LLMResponse:
        """OpenAI-specific message creation"""
        # Future implementation
        raise NotImplementedError("OpenAI integration not yet implemented")


class PromptBuilder:
    """
    Builds prompts for workflow execution.

    Converts workflow sessions into effective LLM prompts.
    """

    @staticmethod
    def build_workflow_prompt(
        objective: str,
        phase: Dict[str, Any],
        context: Dict[str, Any],
    ) -> tuple[str, str]:
        """
        Build prompt for workflow execution.

        Args:
            objective: Overall workflow objective
            phase: Current phase definition
            context: Execution context (safety_mode, budget, etc.)

        Returns:
            (system_prompt, user_prompt) tuple
        """
        safety_mode = context.get("safety_mode", "plan-readonly")
        phase_id = phase.get("id", "unknown")

        # System prompt
        system = f"""You are an AI assistant executing a workflow task.

Current phase: {phase_id}
Safety mode: {safety_mode}
{'READ-ONLY MODE: Do not make any changes to files or system.' if 'readonly' in safety_mode else 'You may execute commands and modify files as needed.'}

Follow these guidelines:
1. Focus on the specific objective provided
2. Use available tools when needed
3. Provide clear reasoning for your actions
4. Stay within the specified safety constraints
5. Be concise and efficient"""

        # User prompt
        user = f"""Please complete the following task:

{objective}

Phase: {phase_id}

Think through the approach step by step, then execute the necessary actions to complete this task."""

        return system, user

    @staticmethod
    def build_tool_definitions() -> List[Dict[str, Any]]:
        """
        Build tool definitions for function calling.

        Returns:
            List of tool definition dicts in Anthropic format
        """
        tools = [
            {
                "name": "read_file",
                "description": "Read contents of a file",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path to file to read"
                        }
                    },
                    "required": ["path"]
                }
            },
            {
                "name": "write_file",
                "description": "Write content to a file",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path to file to write"
                        },
                        "content": {
                            "type": "string",
                            "description": "Content to write"
                        }
                    },
                    "required": ["path", "content"]
                }
            },
            {
                "name": "run_command",
                "description": "Execute a shell command",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "Command to execute"
                        }
                    },
                    "required": ["command"]
                }
            },
            {
                "name": "list_files",
                "description": "List files in a directory",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Directory path"
                        },
                        "pattern": {
                            "type": "string",
                            "description": "Optional glob pattern"
                        }
                    },
                    "required": ["path"]
                }
            },
        ]

        return tools


# Convenience function for quick testing
async def test_llm_client():
    """Test LLM client with a simple query"""
    client = LLMClient(provider="anthropic")

    if not client.client:
        print("⚠️  No API key found - skipping test")
        return

    response = await client.create_message(
        prompt="Say 'Hello, workflow!' and nothing else.",
        max_tokens=50,
    )

    print(f"✅ LLM client test successful:")
    print(f"   Model: {response.model}")
    print(f"   Response: {response.content}")
    print(f"   Tokens: {response.usage['total_tokens']}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_llm_client())
