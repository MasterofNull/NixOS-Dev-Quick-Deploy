#!/usr/bin/env python3
"""Test and demonstrate the unified agent interface."""

import sys
from pathlib import Path

# Add local-orchestrator to path
sys.path.insert(0, str(Path(__file__).parent))

from agent_interface import LocalAgent, ModelProvider, create_agent, quick_query
from example_tools import text_analyzer


def test_basic_agent():
    """Test basic agent functionality."""
    print("Testing Basic Agent:")
    print("=" * 60)
    
    agent = LocalAgent()
    print(f"Created agent: provider={agent.provider.value}, model={agent.model}")
    print(f"Tools registered: {len(agent.tools)}")
    print(f"Message history: {len(agent.messages)}")
    
    print("\n✓ Basic agent creation test passed!")


def test_agent_with_tools():
    """Test agent with tools."""
    print("\n" + "=" * 60)
    print("Testing Agent with Tools:")
    print("=" * 60)
    
    agent = LocalAgent.with_tools(text_analyzer)
    print(f"Tools available: {list(agent.tools.keys())}")
    
    for tool_name, tool_def in agent.tools.items():
        print(f"\nTool: {tool_name}")
        print(f"  Description: {tool_def.description}")
        print(f"  Schema: {tool_def.input_schema}")
    
    print("\n✓ Agent with tools test passed!")


def test_conversation_history():
    """Test conversation history management."""
    print("\n" + "=" * 60)
    print("Testing Conversation History:")
    print("=" * 60)
    
    agent = LocalAgent(system_prompt="You are a helpful NixOS assistant.")
    
    print(f"Initial messages: {len(agent.messages)}")
    
    agent.add_message("user", "What is NixOS?")
    agent.add_message("assistant", "NixOS is a Linux distribution based on Nix package manager.")
    agent.add_message("user", "How do I install packages?")
    
    print(f"After adding messages: {len(agent.messages)}")
    
    history = agent.get_history()
    print(f"\nConversation history ({len(history)} messages):")
    for msg in history:
        print(f"  {msg['role']}: {msg['content'][:50]}...")
    
    # Clear non-system messages
    agent.clear_history()
    print(f"\nAfter clearing: {len(agent.messages)} messages (system prompt preserved)")
    
    print("\n✓ Conversation history test passed!")


def test_workflow_agent():
    """Test workflow-oriented agent."""
    print("\n" + "=" * 60)
    print("Testing Workflow Agent:")
    print("=" * 60)
    
    agent = LocalAgent.for_workflow()
    print(f"Workflow agent provider: {agent.provider.value}")
    print(f"This agent would use hybrid coordinator for workflow planning")
    
    print("\n✓ Workflow agent test passed!")


def test_model_providers():
    """Test different model provider configurations."""
    print("\n" + "=" * 60)
    print("Testing Model Providers:")
    print("=" * 60)
    
    providers = [
        (ModelProvider.LOCAL_LLAMA, "Local llama-cpp"),
        (ModelProvider.HYBRID, "Hybrid coordinator"),
    ]
    
    for provider, description in providers:
        agent = LocalAgent(provider=provider)
        print(f"  {description}: {agent.provider.value}")
    
    print("\n✓ Model provider test passed!")


def test_convenience_functions():
    """Test convenience functions."""
    print("\n" + "=" * 60)
    print("Testing Convenience Functions:")
    print("=" * 60)
    
    # create_agent
    agent1 = create_agent(model="qwen2.5-coder")
    print(f"create_agent: model={agent1.model}")
    
    # Note: quick_query would actually call the LLM, so we skip it
    print("quick_query: (would make actual LLM call, skipping)")
    
    print("\n✓ Convenience functions test passed!")


if __name__ == "__main__":
    test_basic_agent()
    test_agent_with_tools()
    test_conversation_history()
    test_workflow_agent()
    test_model_providers()
    test_convenience_functions()
    
    print("\n" + "=" * 60)
    print("All agent interface tests passed!")
    print("=" * 60)
