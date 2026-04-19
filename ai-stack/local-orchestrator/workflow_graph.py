#!/usr/bin/env python3
"""
Graph-Based Workflow Orchestration

DAG (Directed Acyclic Graph) workflow system for complex multi-step tasks.
Supports task nodes, decision nodes, parallel execution, and dependency resolution.
"""

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set
from datetime import datetime


class NodeType(Enum):
    """Workflow node types."""
    TASK = "task"              # Execute a task
    DECISION = "decision"      # Conditional branching
    PARALLEL = "parallel"      # Parallel execution
    SEQUENTIAL = "sequential"  # Sequential execution (default)


class NodeStatus(Enum):
    """Node execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class WorkflowNode:
    """A node in the workflow graph."""
    id: str
    name: str
    node_type: NodeType
    task: Optional[Callable] = None
    condition: Optional[Callable] = None
    dependencies: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    status: NodeStatus = NodeStatus.PENDING
    result: Any = None
    error: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None


@dataclass
class WorkflowEdge:
    """An edge connecting workflow nodes."""
    from_node: str
    to_node: str
    condition: Optional[Callable] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class WorkflowGraph:
    """
    DAG-based workflow graph.
    
    Manages nodes, edges, and execution order resolution.
    """
    
    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self.nodes: Dict[str, WorkflowNode] = {}
        self.edges: List[WorkflowEdge] = []
        self._execution_order: Optional[List[str]] = None
    
    def add_node(
        self,
        node_id: str,
        name: str,
        node_type: NodeType = NodeType.TASK,
        task: Optional[Callable] = None,
        condition: Optional[Callable] = None,
        dependencies: Optional[List[str]] = None,
        **metadata
    ) -> WorkflowNode:
        """
        Add a node to the workflow.
        
        Args:
            node_id: Unique node identifier
            name: Human-readable node name
            node_type: Type of node
            task: Task function to execute
            condition: Condition function for decision nodes
            dependencies: List of node IDs this depends on
            **metadata: Additional metadata
            
        Returns:
            Created WorkflowNode
        """
        if node_id in self.nodes:
            raise ValueError(f"Node {node_id} already exists")
        
        node = WorkflowNode(
            id=node_id,
            name=name,
            node_type=node_type,
            task=task,
            condition=condition,
            dependencies=dependencies or [],
            metadata=metadata,
        )
        
        self.nodes[node_id] = node
        
        # Add edges for dependencies
        for dep_id in node.dependencies:
            self.add_edge(dep_id, node_id)
        
        # Invalidate cached execution order
        self._execution_order = None
        
        return node
    
    def add_edge(
        self,
        from_node: str,
        to_node: str,
        condition: Optional[Callable] = None,
        **metadata
    ):
        """
        Add an edge between nodes.
        
        Args:
            from_node: Source node ID
            to_node: Target node ID
            condition: Optional condition for edge traversal
            **metadata: Additional metadata
        """
        if from_node not in self.nodes:
            raise ValueError(f"Source node {from_node} not found")
        if to_node not in self.nodes:
            raise ValueError(f"Target node {to_node} not found")
        
        edge = WorkflowEdge(
            from_node=from_node,
            to_node=to_node,
            condition=condition,
            metadata=metadata,
        )
        
        self.edges.append(edge)
        
        # Invalidate cached execution order
        self._execution_order = None
    
    def get_dependencies(self, node_id: str) -> List[str]:
        """Get all dependencies for a node."""
        return [e.from_node for e in self.edges if e.to_node == node_id]
    
    def get_dependents(self, node_id: str) -> List[str]:
        """Get all nodes that depend on this node."""
        return [e.to_node for e in self.edges if e.from_node == node_id]
    
    def topological_sort(self) -> List[str]:
        """
        Perform topological sort to determine execution order.
        
        Returns:
            List of node IDs in execution order
            
        Raises:
            ValueError: If graph contains cycles
        """
        # Kahn's algorithm for topological sort
        in_degree = {node_id: 0 for node_id in self.nodes}
        
        for edge in self.edges:
            in_degree[edge.to_node] += 1
        
        queue = [node_id for node_id, degree in in_degree.items() if degree == 0]
        result = []
        
        while queue:
            node_id = queue.pop(0)
            result.append(node_id)
            
            for dependent in self.get_dependents(node_id):
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)
        
        if len(result) != len(self.nodes):
            raise ValueError("Workflow graph contains cycles")
        
        return result
    
    def get_execution_order(self) -> List[str]:
        """Get cached execution order."""
        if self._execution_order is None:
            self._execution_order = self.topological_sort()
        return self._execution_order
    
    def get_parallel_groups(self) -> List[List[str]]:
        """
        Group nodes that can execute in parallel.
        
        Returns:
            List of parallel execution groups
        """
        execution_order = self.get_execution_order()
        groups = []
        
        processed = set()
        
        for node_id in execution_order:
            if node_id in processed:
                continue
            
            # Find all nodes at the same dependency level
            node_deps = set(self.get_dependencies(node_id))
            group = [node_id]
            
            for other_id in execution_order:
                if other_id == node_id or other_id in processed:
                    continue
                
                other_deps = set(self.get_dependencies(other_id))
                
                # Can run in parallel if they have the same dependencies
                # and don't depend on each other
                if (other_deps == node_deps and
                    node_id not in other_deps and
                    other_id not in node_deps):
                    group.append(other_id)
            
            groups.append(group)
            processed.update(group)
        
        return groups
    
    def to_dict(self) -> Dict[str, Any]:
        """Export workflow to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "nodes": [
                {
                    "id": node.id,
                    "name": node.name,
                    "type": node.node_type.value,
                    "dependencies": node.dependencies,
                    "status": node.status.value,
                    "metadata": node.metadata,
                }
                for node in self.nodes.values()
            ],
            "edges": [
                {
                    "from": edge.from_node,
                    "to": edge.to_node,
                    "metadata": edge.metadata,
                }
                for edge in self.edges
            ],
        }
    
    def to_mermaid(self) -> str:
        """
        Export workflow to Mermaid diagram format.
        
        Returns:
            Mermaid markdown string
        """
        lines = ["graph TD"]
        
        # Add nodes
        for node in self.nodes.values():
            shape = "[]" if node.node_type == NodeType.TASK else "{}"
            lines.append(f"    {node.id}{shape[0]}{node.name}{shape[1]}")
        
        # Add edges
        for edge in self.edges:
            arrow = "-->"
            lines.append(f"    {edge.from_node} {arrow} {edge.to_node}")
        
        return "\n".join(lines)


class WorkflowExecutor:
    """
    Executes workflow graphs with dependency resolution.
    """
    
    def __init__(self, graph: WorkflowGraph):
        self.graph = graph
        self.execution_log: List[Dict[str, Any]] = []
        self.context: Dict[str, Any] = {}
    
    def execute_node(
        self,
        node_id: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute a single node.
        
        Args:
            node_id: Node to execute
            context: Execution context
            
        Returns:
            Execution result
        """
        node = self.graph.nodes[node_id]
        context = context or self.context
        
        result = {
            "node_id": node_id,
            "name": node.name,
            "status": "pending",
            "result": None,
            "error": None,
        }
        
        try:
            node.status = NodeStatus.RUNNING
            node.start_time = datetime.utcnow().isoformat()
            
            # Execute based on node type
            if node.node_type == NodeType.TASK:
                if node.task:
                    output = node.task(context)
                else:
                    output = {"executed": True}
                
                result["result"] = output
                result["status"] = "completed"
                node.status = NodeStatus.COMPLETED
                node.result = output
            
            elif node.node_type == NodeType.DECISION:
                if node.condition:
                    decision = node.condition(context)
                    result["result"] = {"decision": decision}
                    result["status"] = "completed"
                    node.status = NodeStatus.COMPLETED
                    node.result = decision
                else:
                    raise ValueError("Decision node requires condition function")
            
            else:
                # Default: mark as completed
                result["status"] = "completed"
                node.status = NodeStatus.COMPLETED
            
            node.end_time = datetime.utcnow().isoformat()
            
        except Exception as e:
            result["status"] = "failed"
            result["error"] = str(e)
            node.status = NodeStatus.FAILED
            node.error = str(e)
            node.end_time = datetime.utcnow().isoformat()
        
        self.execution_log.append(result)
        return result
    
    def execute_sequential(
        self,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute workflow sequentially.
        
        Args:
            context: Initial execution context
            
        Returns:
            Execution summary
        """
        context = context or {}
        self.context = context
        self.execution_log = []
        
        execution_order = self.graph.get_execution_order()
        
        completed = 0
        failed = 0
        
        for node_id in execution_order:
            result = self.execute_node(node_id, context)
            
            if result["status"] == "completed":
                completed += 1
            elif result["status"] == "failed":
                failed += 1
                # Stop on failure
                break
        
        return {
            "workflow": self.graph.name,
            "status": "completed" if failed == 0 else "failed",
            "total_nodes": len(execution_order),
            "completed": completed,
            "failed": failed,
            "execution_log": self.execution_log,
        }
    
    def execute_parallel(
        self,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute workflow with parallel execution where possible.
        
        Args:
            context: Initial execution context
            
        Returns:
            Execution summary
        """
        context = context or {}
        self.context = context
        self.execution_log = []
        
        parallel_groups = self.graph.get_parallel_groups()
        
        completed = 0
        failed = 0
        
        for group in parallel_groups:
            # In a real implementation, this would use threading or async
            # For now, execute sequentially within group
            for node_id in group:
                result = self.execute_node(node_id, context)
                
                if result["status"] == "completed":
                    completed += 1
                elif result["status"] == "failed":
                    failed += 1
        
        return {
            "workflow": self.graph.name,
            "status": "completed" if failed == 0 else "failed",
            "total_nodes": len(self.graph.nodes),
            "completed": completed,
            "failed": failed,
            "parallel_groups": len(parallel_groups),
            "execution_log": self.execution_log,
        }


# Convenience functions

def create_workflow(name: str, description: str = "") -> WorkflowGraph:
    """Create a new workflow graph."""
    return WorkflowGraph(name, description)


def execute_workflow(
    workflow: WorkflowGraph,
    parallel: bool = False,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Execute a workflow graph."""
    executor = WorkflowExecutor(workflow)
    
    if parallel:
        return executor.execute_parallel(context)
    else:
        return executor.execute_sequential(context)
