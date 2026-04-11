"""
Dependency graph analyzer.

Analyzes workflow node dependencies and detects cycles.
"""

from typing import List, Set, Dict, Optional
from .models import Workflow, WorkflowNode


class DependencyGraph:
    """Directed acyclic graph of workflow node dependencies."""

    def __init__(self, workflow: Workflow):
        """
        Build dependency graph from workflow.

        Args:
            workflow: Workflow to analyze
        """
        self.workflow = workflow
        self.adjacency_list: Dict[str, Set[str]] = {}
        self.reverse_adjacency_list: Dict[str, Set[str]] = {}
        self._build_graph()

    def _build_graph(self) -> None:
        """Build adjacency list representation from workflow nodes."""
        # Initialize adjacency lists
        for node in self.workflow.nodes:
            self.adjacency_list[node.id] = set()
            self.reverse_adjacency_list[node.id] = set()

        # Build edges from dependencies
        for node in self.workflow.nodes:
            if node.depends_on:
                for dep_id in node.depends_on:
                    # Add edge from dependency to node
                    if dep_id in self.adjacency_list:
                        self.adjacency_list[dep_id].add(node.id)
                        self.reverse_adjacency_list[node.id].add(dep_id)

            # Add goto edges
            if node.goto:
                if node.goto in self.adjacency_list:
                    self.adjacency_list[node.id].add(node.goto)
                    self.reverse_adjacency_list[node.goto].add(node.id)

    def has_cycle(self) -> bool:
        """
        Check if graph contains cycles using DFS.

        Returns:
            True if a cycle exists, False otherwise
        """
        visited: Set[str] = set()
        recursion_stack: Set[str] = set()

        def dfs(node_id: str) -> bool:
            """DFS helper function."""
            visited.add(node_id)
            recursion_stack.add(node_id)

            # Visit all neighbors
            for neighbor in self.adjacency_list.get(node_id, set()):
                if neighbor not in visited:
                    if dfs(neighbor):
                        return True
                elif neighbor in recursion_stack:
                    # Back edge found - cycle detected
                    return True

            recursion_stack.remove(node_id)
            return False

        # Check all nodes (graph might not be connected)
        for node_id in self.adjacency_list.keys():
            if node_id not in visited:
                if dfs(node_id):
                    return True

        return False

    def find_cycle(self) -> Optional[List[str]]:
        """
        Find and return a cycle if one exists.

        Returns:
            List of node IDs forming a cycle, or None if no cycle exists
        """
        visited: Set[str] = set()
        recursion_stack: Set[str] = set()
        parent: Dict[str, Optional[str]] = {}

        def dfs(node_id: str) -> Optional[str]:
            """DFS helper that returns the node where cycle is detected."""
            visited.add(node_id)
            recursion_stack.add(node_id)

            for neighbor in self.adjacency_list.get(node_id, set()):
                parent[neighbor] = node_id

                if neighbor not in visited:
                    cycle_node = dfs(neighbor)
                    if cycle_node:
                        return cycle_node
                elif neighbor in recursion_stack:
                    # Found a cycle
                    return neighbor

            recursion_stack.remove(node_id)
            return None

        # Try to find a cycle
        for node_id in self.adjacency_list.keys():
            if node_id not in visited:
                cycle_node = dfs(node_id)
                if cycle_node:
                    # Reconstruct the cycle
                    cycle = [cycle_node]
                    current = parent.get(cycle_node)
                    while current and current != cycle_node:
                        cycle.append(current)
                        current = parent.get(current)
                    cycle.append(cycle_node)
                    cycle.reverse()
                    return cycle

        return None

    def topological_sort(self) -> List[str]:
        """
        Return nodes in topological order (dependencies first).

        Uses Kahn's algorithm for topological sorting.

        Returns:
            List of node IDs in topological order

        Raises:
            ValueError: If graph has cycles
        """
        if self.has_cycle():
            raise ValueError("Cannot perform topological sort on graph with cycles")

        # Calculate in-degree for each node
        in_degree: Dict[str, int] = {}
        for node_id in self.adjacency_list.keys():
            in_degree[node_id] = len(self.reverse_adjacency_list.get(node_id, set()))

        # Queue of nodes with no incoming edges
        queue: List[str] = []
        for node_id, degree in in_degree.items():
            if degree == 0:
                queue.append(node_id)

        result: List[str] = []

        while queue:
            # Remove node from queue
            node_id = queue.pop(0)
            result.append(node_id)

            # Reduce in-degree of neighbors
            for neighbor in self.adjacency_list.get(node_id, set()):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # Check if all nodes were processed
        if len(result) != len(self.adjacency_list):
            raise ValueError("Graph has cycles or unreachable nodes")

        return result

    def get_dependencies(self, node_id: str) -> Set[str]:
        """
        Get all dependencies of a node (recursive).

        Args:
            node_id: Node ID to get dependencies for

        Returns:
            Set of all node IDs that this node depends on
        """
        if node_id not in self.reverse_adjacency_list:
            return set()

        dependencies: Set[str] = set()
        visited: Set[str] = set()

        def dfs(current_id: str) -> None:
            """DFS to collect all dependencies."""
            if current_id in visited:
                return
            visited.add(current_id)

            for dep_id in self.reverse_adjacency_list.get(current_id, set()):
                dependencies.add(dep_id)
                dfs(dep_id)

        dfs(node_id)
        return dependencies

    def get_dependents(self, node_id: str) -> Set[str]:
        """
        Get all nodes that depend on this node (directly or indirectly).

        Args:
            node_id: Node ID to get dependents for

        Returns:
            Set of all node IDs that depend on this node
        """
        if node_id not in self.adjacency_list:
            return set()

        dependents: Set[str] = set()
        visited: Set[str] = set()

        def dfs(current_id: str) -> None:
            """DFS to collect all dependents."""
            if current_id in visited:
                return
            visited.add(current_id)

            for dependent_id in self.adjacency_list.get(current_id, set()):
                dependents.add(dependent_id)
                dfs(dependent_id)

        dfs(node_id)
        return dependents

    def get_execution_levels(self) -> List[List[str]]:
        """
        Group nodes by execution level.

        Nodes in the same level can be executed in parallel (if marked parallel).

        Returns:
            List of levels, where each level is a list of node IDs
        """
        if self.has_cycle():
            raise ValueError("Cannot determine execution levels for graph with cycles")

        # Calculate in-degree for each node
        in_degree: Dict[str, int] = {}
        for node_id in self.adjacency_list.keys():
            in_degree[node_id] = len(self.reverse_adjacency_list.get(node_id, set()))

        levels: List[List[str]] = []
        processed: Set[str] = set()

        while len(processed) < len(self.adjacency_list):
            # Find all nodes with in-degree 0 (considering only unprocessed nodes)
            current_level = []
            for node_id in self.adjacency_list.keys():
                if node_id not in processed and in_degree[node_id] == 0:
                    current_level.append(node_id)

            if not current_level:
                raise ValueError("Graph has cycles or unreachable nodes")

            levels.append(current_level)

            # Mark nodes as processed and update in-degrees
            for node_id in current_level:
                processed.add(node_id)
                for neighbor in self.adjacency_list.get(node_id, set()):
                    in_degree[neighbor] -= 1

        return levels
