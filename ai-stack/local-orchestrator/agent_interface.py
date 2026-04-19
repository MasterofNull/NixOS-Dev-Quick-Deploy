#!/usr/bin/env python3
"""
Unified Agent Interface - Strands-style agent pattern for local AI harness.

Provides a simplified, callable agent interface that integrates with:
- Local llama-cpp models
- Remote LLM providers (OpenRouter, etc.)
- Hybrid coordinator workflow orchestration
- MCP tool ecosystem
- Tool decorator system
"""

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Union

from mcp_client import MCPClient, get_mcp_client
from tool_decorators import ToolDefinition, get_tool_registry


class ModelProvider(Enum):
    """Supported model providers."""
    LOCAL_LLAMA = "local_llama"      # Local llama-cpp server
    OPENROUTER = "openrouter"        # OpenRouter API
    HYBRID = "hybrid"                # Hybrid coordinator
    CUSTOM = "custom"                # Custom provider


@dataclass
class ModelConfig:
    """Model configuration."""
    provider: ModelProvider
    model_name: str
    temperature: float = 0.7
    max_tokens: int = 2048
    stream: bool = False
    api_key: Optional[str] = None
    endpoint: Optional[str] = None
    extra_params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentMessage:
    """Message in agent conversation."""
    role: str  # "user", "assistant", "system"
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResponse:
    """Agent response with metadata."""
    content: str
    model: str
    provider: str
    tokens_used: Optional[int] = None
    finish_reason: Optional[str] = None
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class LocalAgent:
    """
    Unified agent interface inspired by strands Agent class.
    
    Provides a simple, callable interface for interacting with various
    LLM backends while integrating with the local AI harness infrastructure.
    
    Usage:
        # Basic usage with local model
        agent = LocalAgent()
        response = agent("What is NixOS?")
        
        # With tools
        from example_tools import text_analyzer
        agent = LocalAgent(tools=[text_analyzer])
        response = agent("Analyze this text: Hello World")
        
        # Streaming
        agent = LocalAgent(stream=True)
        for chunk in agent("Explain quantum computing"):
            print(chunk, end="", flush=True)
        
        # With conversation history
        agent = LocalAgent()
        agent.add_message("user", "Hi, I'm working on a NixOS project")
        response = agent("What's the best way to manage secrets?")
    """
    
    def __init__(
        self,
        model: Optional[str] = None,
        provider: ModelProvider = ModelProvider.LOCAL_LLAMA,
        tools: Optional[List[Union[Callable, ToolDefinition]]] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        stream: bool = False,
        system_prompt: Optional[str] = None,
        mcp_client: Optional[MCPClient] = None,
    ):
        """
        Initialize LocalAgent.
        
        Args:
            model: Model name (e.g., "qwen2.5-coder-32b")
            provider: Model provider to use
            tools: List of tools (functions or ToolDefinitions)
            temperature: Sampling temperature
            max_tokens: Maximum output tokens
            stream: Enable streaming responses
            system_prompt: System prompt to prepend
            mcp_client: Custom MCP client (uses global if not provided)
        """
        self.model = model or "local"
        self.provider = provider
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.stream = stream
        
        # Conversation history
        self.messages: List[AgentMessage] = []
        if system_prompt:
            self.add_message("system", system_prompt)
        
        # MCP client integration
        self.mcp_client = mcp_client or get_mcp_client()
        
        # Tool integration
        self.tools: Dict[str, ToolDefinition] = {}
        if tools:
            self._register_tools(tools)
        
        # Statistics
        self._stats = {
            "queries": 0,
            "tokens_used": 0,
            "tool_calls": 0,
        }
    
    def _register_tools(self, tools: List[Union[Callable, ToolDefinition]]):
        """Register tools with the agent."""
        registry = get_tool_registry()
        
        for tool in tools:
            if isinstance(tool, ToolDefinition):
                self.tools[tool.name] = tool
            elif callable(tool):
                # Check if it's a decorated tool
                if hasattr(tool, '_tool_def'):
                    tool_def = tool._tool_def
                    self.tools[tool_def.name] = tool_def
                else:
                    # Try to find in registry by function name
                    tool_def = registry.get_tool(tool.__name__)
                    if tool_def:
                        self.tools[tool_def.name] = tool_def
    
    def add_message(self, role: str, content: str, **metadata):
        """
        Add a message to conversation history.
        
        Args:
            role: Message role (user, assistant, system)
            content: Message content
            **metadata: Additional metadata
        """
        self.messages.append(AgentMessage(
            role=role,
            content=content,
            metadata=metadata,
        ))
    
    def clear_history(self):
        """Clear conversation history (except system prompt)."""
        system_messages = [m for m in self.messages if m.role == "system"]
        self.messages = system_messages
    
    def get_history(self) -> List[Dict[str, str]]:
        """Get conversation history in API format."""
        return [
            {"role": msg.role, "content": msg.content}
            for msg in self.messages
        ]
    
    def _call_local_llama(self, query: str) -> Union[str, Iterator[str]]:
        """Call local llama-cpp model."""
        messages = self.get_history() + [{"role": "user", "content": query}]
        
        if self.stream:
            # Streaming not implemented in basic MCP client
            # Would need to add streaming support to mcp_client.py
            response = self.mcp_client.llm_chat(
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
            )
            return iter([response])
        else:
            response = self.mcp_client.llm_chat(
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
            )
            return response
    
    def _call_hybrid_coordinator(self, query: str) -> str:
        """Call hybrid coordinator for workflow-based responses."""
        result = self.mcp_client.workflow_plan(query)
        
        if isinstance(result, dict) and "plan" in result:
            return json.dumps(result["plan"], indent=2)
        return str(result)
    
    def _execute_query(self, query: str) -> Union[str, Iterator[str]]:
        """Execute query based on provider."""
        self._stats["queries"] += 1
        
        if self.provider == ModelProvider.LOCAL_LLAMA:
            return self._call_local_llama(query)
        elif self.provider == ModelProvider.HYBRID:
            return self._call_hybrid_coordinator(query)
        else:
            raise ValueError(f"Provider {self.provider} not yet implemented")
    
    def __call__(
        self,
        query: str,
        stream: Optional[bool] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Union[AgentResponse, Iterator[str]]:
        """
        Call the agent with a query.
        
        Args:
            query: User query
            stream: Override streaming setting
            temperature: Override temperature
            max_tokens: Override max tokens
            
        Returns:
            AgentResponse or Iterator[str] if streaming
        """
        # Override settings if provided
        original_stream = self.stream
        original_temp = self.temperature
        original_max = self.max_tokens
        
        if stream is not None:
            self.stream = stream
        if temperature is not None:
            self.temperature = temperature
        if max_tokens is not None:
            self.max_tokens = max_tokens
        
        try:
            # Add user message to history
            self.add_message("user", query)
            
            # Execute query
            result = self._execute_query(query)
            
            # Handle streaming vs non-streaming
            if self.stream:
                return result
            else:
                # Add assistant response to history
                self.add_message("assistant", result)
                
                return AgentResponse(
                    content=result,
                    model=self.model,
                    provider=self.provider.value,
                    metadata={"query": query},
                )
        finally:
            # Restore original settings
            self.stream = original_stream
            self.temperature = original_temp
            self.max_tokens = original_max
    
    def chat(self, message: str) -> str:
        """
        Simple chat interface (non-streaming).
        
        Args:
            message: User message
            
        Returns:
            Assistant response as string
        """
        response = self(message, stream=False)
        if isinstance(response, AgentResponse):
            return response.content
        return str(response)
    
    def get_stats(self) -> Dict[str, int]:
        """Get agent usage statistics."""
        return dict(self._stats)
    
    @classmethod
    def with_tools(cls, *tools, **kwargs) -> 'LocalAgent':
        """
        Create agent with specified tools.
        
        Usage:
            agent = LocalAgent.with_tools(text_analyzer, pattern_search)
        """
        return cls(tools=list(tools), **kwargs)
    
    @classmethod
    def for_workflow(cls, **kwargs) -> 'LocalAgent':
        """
        Create agent configured for workflow orchestration.
        
        Uses hybrid coordinator provider by default.
        """
        kwargs.setdefault('provider', ModelProvider.HYBRID)
        return cls(**kwargs)


# Convenience functions

def create_agent(
    model: Optional[str] = None,
    tools: Optional[List[Callable]] = None,
    **kwargs
) -> LocalAgent:
    """Create a LocalAgent instance."""
    return LocalAgent(model=model, tools=tools, **kwargs)


def quick_query(query: str, model: Optional[str] = None) -> str:
    """Quick one-off query without maintaining conversation history."""
    agent = LocalAgent(model=model)
    response = agent(query, stream=False)
    if isinstance(response, AgentResponse):
        return response.content
    return str(response)
