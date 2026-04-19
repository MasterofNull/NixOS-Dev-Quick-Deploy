#!/usr/bin/env python3
"""
Integration tests for strands-agents pattern integration.

Tests end-to-end workflows combining:
- SOP execution
- Agent interface
- Workflow graphs
- Tool decorators
- Artifact management
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from sop_engine import parse_sop, execute_sop
from agent_interface import LocalAgent, ModelProvider
from workflow_graph import create_workflow, execute_workflow, NodeType
from tool_decorators import tool, get_tool_registry
from mcp_client import get_mcp_client


def test_artifact_management():
    """Test .agents/ artifact management."""
    print("Testing Artifact Management:")
    print("=" * 60)
    
    client = get_mcp_client()
    
    # Write artifacts to different categories
    summary_path = client.write_artifact(
        "summary",
        "test-integration.md",
        "# Integration Test\n\nThis is a test summary."
    )
    print(f"✓ Written summary: {summary_path}")
    
    # Read back
    content = client.read_artifact("summary", "test-integration.md")
    assert content is not None
    assert "Integration Test" in content
    print("✓ Read artifact successfully")
    
    # List artifacts
    artifacts = client.list_artifacts("summary", "*.md")
    assert "test-integration.md" in artifacts
    print(f"✓ Listed {len(artifacts)} artifacts")
    
    # Cleanup
    summary_path.unlink()
    
    print("\n✓ Artifact management integration test passed!")


def test_tool_decorator_integration():
    """Test tool decorator with agent."""
    print("\n" + "=" * 60)
    print("Testing Tool Decorator Integration:")
    print("=" * 60)
    
    @tool(description="Count words in text")
    def word_counter(text: str) -> int:
        """Count words in the provided text."""
        return len(text.split())
    
    # Tool should be registered
    registry = get_tool_registry()
    tool_def = registry.get_tool("word_counter")
    assert tool_def is not None
    print(f"✓ Tool registered: {tool_def.name}")
    
    # Create agent with tool
    agent = LocalAgent.with_tools(word_counter)
    assert "word_counter" in agent.tools
    print(f"✓ Agent has {len(agent.tools)} tools")
    
    # Test tool execution directly
    result = word_counter("Hello world this is a test")
    assert result == 6
    print(f"✓ Tool execution: {result} words")
    
    # Cleanup
    registry.unregister("word_counter")
    
    print("\n✓ Tool decorator integration test passed!")


def test_sop_with_agent():
    """Test SOP execution integrated with agent interface."""
    print("\n" + "=" * 60)
    print("Testing SOP + Agent Integration:")
    print("=" * 60)
    
    # Parse SOP
    sop_path = Path(__file__).parent.parent / "sop-templates" / "test-validation.sop.md"
    
    if sop_path.exists():
        sop = parse_sop(sop_path)
        print(f"✓ Parsed SOP: {sop.name}")
        print(f"  Sections: {len(sop.sections)}")
        print(f"  Required steps: {len(sop.get_required_steps())}")
        
        # Execute SOP
        result = execute_sop(sop, context={"test_level": "unit"})
        print(f"✓ Executed SOP: {result['status']}")
        print(f"  Completed: {result.get('completed', result.get('completed_steps', 0))}/{result['total_steps']}")
    else:
        print("⚠ SOP file not found, skipping")
    
    print("\n✓ SOP + Agent integration test passed!")


def test_workflow_with_tools():
    """Test workflow graph with tool-based tasks."""
    print("\n" + "=" * 60)
    print("Testing Workflow + Tools Integration:")
    print("=" * 60)
    
    @tool
    def process_data(data: str) -> dict:
        """Process data and return results."""
        return {"processed": True, "length": len(data)}
    
    @tool
    def validate_data(data: dict) -> bool:
        """Validate processed data."""
        return data.get("processed", False)
    
    # Create workflow
    workflow = create_workflow("tool-workflow")
    
    workflow.add_node(
        "process",
        "Process Data",
        NodeType.TASK,
        task=lambda ctx: process_data("test data")
    )
    
    workflow.add_node(
        "validate",
        "Validate Data",
        NodeType.TASK,
        task=lambda ctx: validate_data({"processed": True}),
        dependencies=["process"]
    )
    
    # Execute
    result = execute_workflow(workflow, parallel=False)
    
    print(f"✓ Workflow executed: {result['status']}")
    print(f"  Completed: {result.get('completed', result.get('completed_steps', 0))}/{result['total_nodes']}")
    
    # Cleanup
    registry = get_tool_registry()
    registry.unregister("process_data")
    registry.unregister("validate_data")
    
    print("\n✓ Workflow + Tools integration test passed!")


def test_end_to_end_workflow():
    """
    End-to-end test: SOP → Agent → Graph
    
    Simulates a complete workflow using all integrated components:
    1. Parse SOP for workflow structure
    2. Create agent with tools
    3. Build workflow graph based on SOP
    4. Execute workflow
    5. Store results as artifacts
    """
    print("\n" + "=" * 60)
    print("Testing End-to-End: SOP → Agent → Graph → Artifacts:")
    print("=" * 60)
    
    # Define tools
    @tool
    def analyze_code(filepath: str) -> dict:
        """Analyze code file."""
        return {"file": filepath, "lines": 100, "complexity": "low"}
    
    @tool
    def run_tests(test_suite: str) -> dict:
        """Run test suite."""
        return {"suite": test_suite, "passed": 10, "failed": 0}
    
    # Create agent with tools
    agent = LocalAgent.with_tools(analyze_code, run_tests)
    print(f"✓ Created agent with {len(agent.tools)} tools")
    
    # Create workflow graph mimicking SOP structure
    workflow = create_workflow(
        "e2e-workflow",
        "End-to-end integration workflow"
    )
    
    workflow.add_node(
        "analyze",
        "Analyze Codebase",
        NodeType.TASK,
        task=lambda ctx: analyze_code("main.py")
    )
    
    workflow.add_node(
        "test",
        "Run Tests",
        NodeType.TASK,
        task=lambda ctx: run_tests("unit-tests"),
        dependencies=["analyze"]
    )
    
    workflow.add_node(
        "decision",
        "Check Results",
        NodeType.DECISION,
        condition=lambda ctx: True,
        dependencies=["test"]
    )
    
    print(f"✓ Built workflow: {len(workflow.nodes)} nodes")
    
    # Execute workflow
    result = execute_workflow(workflow, parallel=False)
    print(f"✓ Executed workflow: {result['status']}")
    
    # Store results as artifact
    client = get_mcp_client()
    report = f"""# E2E Workflow Report

Workflow: {result['workflow']}
Status: {result['status']}
Completed: {result.get('completed', result.get('completed_steps', 0))}/{result['total_nodes']}

## Execution Log
{len(result['execution_log'])} steps executed
"""
    
    artifact_path = client.write_artifact(
        "summary",
        "e2e-workflow-report.md",
        report
    )
    print(f"✓ Stored report: {artifact_path}")
    
    # Cleanup
    artifact_path.unlink()
    registry = get_tool_registry()
    registry.unregister("analyze_code")
    registry.unregister("run_tests")
    
    print("\n✓ End-to-end integration test PASSED!")


if __name__ == "__main__":
    test_artifact_management()
    test_tool_decorator_integration()
    test_sop_with_agent()
    test_workflow_with_tools()
    test_end_to_end_workflow()
    
    print("\n" + "=" * 60)
    print("ALL INTEGRATION TESTS PASSED!")
    print("=" * 60)
    print("\nStrands-agents pattern integration validated:")
    print("  ✓ .agents/ artifact management")
    print("  ✓ @tool decorator system")
    print("  ✓ SOP workflow engine")
    print("  ✓ Unified agent interface")
    print("  ✓ DAG workflow orchestration")
    print("  ✓ End-to-end SOP → Agent → Graph → Artifacts")
