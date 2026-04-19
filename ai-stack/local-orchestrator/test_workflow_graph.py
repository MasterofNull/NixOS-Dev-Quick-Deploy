#!/usr/bin/env python3
"""Test and demonstrate workflow graph orchestration."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from workflow_graph import (
    WorkflowGraph, WorkflowExecutor, NodeType,
    create_workflow, execute_workflow
)


def test_basic_graph():
    """Test basic graph creation and structure."""
    print("Testing Basic Graph:")
    print("=" * 60)
    
    graph = create_workflow(
        name="test-workflow",
        description="Basic test workflow"
    )
    
    # Add nodes
    graph.add_node("start", "Start Task", NodeType.TASK)
    graph.add_node("middle", "Middle Task", NodeType.TASK, dependencies=["start"])
    graph.add_node("end", "End Task", NodeType.TASK, dependencies=["middle"])
    
    print(f"Nodes: {len(graph.nodes)}")
    print(f"Edges: {len(graph.edges)}")
    
    execution_order = graph.get_execution_order()
    print(f"Execution order: {execution_order}")
    
    assert execution_order == ["start", "middle", "end"], "Execution order incorrect"
    
    print("\n✓ Basic graph test passed!")


def test_parallel_detection():
    """Test parallel execution group detection."""
    print("\n" + "=" * 60)
    print("Testing Parallel Detection:")
    print("=" * 60)
    
    graph = create_workflow("parallel-workflow")
    
    # Create diamond pattern
    graph.add_node("start", "Start")
    graph.add_node("task1", "Task 1", dependencies=["start"])
    graph.add_node("task2", "Task 2", dependencies=["start"])
    graph.add_node("end", "End", dependencies=["task1", "task2"])
    
    parallel_groups = graph.get_parallel_groups()
    print(f"Parallel groups: {parallel_groups}")
    
    # task1 and task2 should be in same group (can run in parallel)
    assert len(parallel_groups) == 3, "Should have 3 groups"
    assert set(parallel_groups[1]) == {"task1", "task2"}, "task1 and task2 should be parallel"
    
    print("\n✓ Parallel detection test passed!")


def test_workflow_execution():
    """Test workflow execution."""
    print("\n" + "=" * 60)
    print("Testing Workflow Execution:")
    print("=" * 60)
    
    graph = create_workflow("execution-test")
    
    # Define simple tasks
    def task1(ctx):
        return {"result": "task1 completed", "value": 1}
    
    def task2(ctx):
        return {"result": "task2 completed", "value": 2}
    
    def task3(ctx):
        return {"result": "task3 completed", "value": 3}
    
    graph.add_node("task1", "Task 1", task=task1)
    graph.add_node("task2", "Task 2", task=task2, dependencies=["task1"])
    graph.add_node("task3", "Task 3", task=task3, dependencies=["task2"])
    
    # Execute
    result = execute_workflow(graph, parallel=False, context={})
    
    print(f"Status: {result['status']}")
    print(f"Completed: {result['completed']}/{result['total_nodes']}")
    print(f"Failed: {result['failed']}")
    
    assert result['status'] == 'completed', "Execution should succeed"
    assert result['completed'] == 3, "All 3 tasks should complete"
    
    print("\n✓ Workflow execution test passed!")


def test_decision_node():
    """Test decision node logic."""
    print("\n" + "=" * 60)
    print("Testing Decision Node:")
    print("=" * 60)
    
    graph = create_workflow("decision-workflow")
    
    def check_value(ctx):
        return ctx.get("value", 0) > 5
    
    graph.add_node("start", "Start Task", NodeType.TASK)
    graph.add_node(
        "decision",
        "Check Value",
        NodeType.DECISION,
        condition=check_value,
        dependencies=["start"]
    )
    
    executor = WorkflowExecutor(graph)
    
    # Execute with value > 5
    result1 = executor.execute_node("decision", {"value": 10})
    print(f"Decision with value=10: {result1['result']}")
    assert result1['result']['decision'] == True
    
    # Execute with value < 5
    executor2 = WorkflowExecutor(graph)
    result2 = executor2.execute_node("decision", {"value": 3})
    print(f"Decision with value=3: {result2['result']}")
    assert result2['result']['decision'] == False
    
    print("\n✓ Decision node test passed!")


def test_mermaid_export():
    """Test Mermaid diagram export."""
    print("\n" + "=" * 60)
    print("Testing Mermaid Export:")
    print("=" * 60)
    
    graph = create_workflow("mermaid-test")
    
    graph.add_node("A", "Start")
    graph.add_node("B", "Process", dependencies=["A"])
    graph.add_node("C", "End", dependencies=["B"])
    
    mermaid = graph.to_mermaid()
    print("\nMermaid diagram:")
    print(mermaid)
    
    assert "graph TD" in mermaid
    assert "A[Start]" in mermaid
    assert "A --> B" in mermaid
    
    print("\n✓ Mermaid export test passed!")


def test_complex_workflow():
    """Test complex workflow with multiple patterns."""
    print("\n" + "=" * 60)
    print("Testing Complex Workflow:")
    print("=" * 60)
    
    graph = create_workflow(
        "complex-workflow",
        "Multi-step workflow with parallel and sequential tasks"
    )
    
    # Build workflow: init -> (process1, process2) -> validate -> deploy
    graph.add_node("init", "Initialize")
    graph.add_node("process1", "Process Data 1", dependencies=["init"])
    graph.add_node("process2", "Process Data 2", dependencies=["init"])
    graph.add_node("validate", "Validate Results", dependencies=["process1", "process2"])
    graph.add_node("deploy", "Deploy", dependencies=["validate"])
    
    print(f"Nodes: {list(graph.nodes.keys())}")
    
    execution_order = graph.get_execution_order()
    print(f"Execution order: {execution_order}")
    
    parallel_groups = graph.get_parallel_groups()
    print(f"Parallel groups: {parallel_groups}")
    
    # Export to dict
    workflow_dict = graph.to_dict()
    print(f"\nWorkflow structure: {len(workflow_dict['nodes'])} nodes, {len(workflow_dict['edges'])} edges")
    
    print("\n✓ Complex workflow test passed!")


if __name__ == "__main__":
    test_basic_graph()
    test_parallel_detection()
    test_workflow_execution()
    test_decision_node()
    test_mermaid_export()
    test_complex_workflow()
    
    print("\n" + "=" * 60)
    print("All workflow graph tests passed!")
    print("=" * 60)
