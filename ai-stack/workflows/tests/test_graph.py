"""Tests for dependency graph analyzer."""

import pytest
from pathlib import Path
from ..graph import DependencyGraph
from ..parser import WorkflowParser
from ..models import Workflow, WorkflowNode


class TestDependencyGraph:
    """Test suite for DependencyGraph."""

    @pytest.fixture
    def parser(self):
        """Create a parser instance."""
        return WorkflowParser()

    @pytest.fixture
    def examples_dir(self):
        """Get the examples directory path."""
        repo_root = Path(__file__).parent.parent.parent.parent
        return repo_root / "ai-stack" / "workflows" / "examples"

    def test_build_graph_simple(self):
        """Test building dependency graph for simple workflow."""
        workflow = Workflow(
            name="test-simple",
            version="1.0",
            nodes=[
                WorkflowNode(id="task1", agent="qwen", prompt="Task 1"),
                WorkflowNode(id="task2", agent="qwen", prompt="Task 2", depends_on=["task1"]),
                WorkflowNode(id="task3", agent="qwen", prompt="Task 3", depends_on=["task2"]),
            ],
        )

        graph = DependencyGraph(workflow)

        # task1 -> task2 -> task3
        assert "task2" in graph.adjacency_list["task1"]
        assert "task3" in graph.adjacency_list["task2"]
        assert len(graph.adjacency_list["task3"]) == 0

    def test_has_cycle_false(self):
        """Test that acyclic graph is detected correctly."""
        workflow = Workflow(
            name="test-acyclic",
            version="1.0",
            nodes=[
                WorkflowNode(id="task1", agent="qwen", prompt="Task 1"),
                WorkflowNode(id="task2", agent="qwen", prompt="Task 2", depends_on=["task1"]),
                WorkflowNode(id="task3", agent="qwen", prompt="Task 3", depends_on=["task2"]),
            ],
        )

        graph = DependencyGraph(workflow)
        assert graph.has_cycle() is False

    def test_has_cycle_true_simple(self):
        """Test that simple cycle is detected."""
        workflow = Workflow(
            name="test-cycle",
            version="1.0",
            nodes=[
                WorkflowNode(id="task1", agent="qwen", prompt="Task 1", depends_on=["task2"]),
                WorkflowNode(id="task2", agent="qwen", prompt="Task 2", depends_on=["task1"]),
            ],
        )

        graph = DependencyGraph(workflow)
        assert graph.has_cycle() is True

    def test_has_cycle_true_complex(self):
        """Test that complex cycle is detected."""
        workflow = Workflow(
            name="test-cycle-complex",
            version="1.0",
            nodes=[
                WorkflowNode(id="task1", agent="qwen", prompt="Task 1", depends_on=["task3"]),
                WorkflowNode(id="task2", agent="qwen", prompt="Task 2", depends_on=["task1"]),
                WorkflowNode(id="task3", agent="qwen", prompt="Task 3", depends_on=["task2"]),
            ],
        )

        graph = DependencyGraph(workflow)
        assert graph.has_cycle() is True

    def test_find_cycle(self):
        """Test finding a cycle in the graph."""
        workflow = Workflow(
            name="test-find-cycle",
            version="1.0",
            nodes=[
                WorkflowNode(id="task1", agent="qwen", prompt="Task 1", depends_on=["task2"]),
                WorkflowNode(id="task2", agent="qwen", prompt="Task 2", depends_on=["task3"]),
                WorkflowNode(id="task3", agent="qwen", prompt="Task 3", depends_on=["task1"]),
            ],
        )

        graph = DependencyGraph(workflow)
        cycle = graph.find_cycle()

        assert cycle is not None
        assert len(cycle) > 2
        # Cycle should include all three tasks
        assert set(cycle) == {"task1", "task2", "task3"}

    def test_find_cycle_none(self):
        """Test that find_cycle returns None for acyclic graph."""
        workflow = Workflow(
            name="test-no-cycle",
            version="1.0",
            nodes=[
                WorkflowNode(id="task1", agent="qwen", prompt="Task 1"),
                WorkflowNode(id="task2", agent="qwen", prompt="Task 2", depends_on=["task1"]),
            ],
        )

        graph = DependencyGraph(workflow)
        cycle = graph.find_cycle()

        assert cycle is None

    def test_topological_sort_simple(self):
        """Test topological sort on simple workflow."""
        workflow = Workflow(
            name="test-topo",
            version="1.0",
            nodes=[
                WorkflowNode(id="task1", agent="qwen", prompt="Task 1"),
                WorkflowNode(id="task2", agent="qwen", prompt="Task 2", depends_on=["task1"]),
                WorkflowNode(id="task3", agent="qwen", prompt="Task 3", depends_on=["task2"]),
            ],
        )

        graph = DependencyGraph(workflow)
        sorted_nodes = graph.topological_sort()

        # task1 must come before task2, task2 before task3
        assert sorted_nodes.index("task1") < sorted_nodes.index("task2")
        assert sorted_nodes.index("task2") < sorted_nodes.index("task3")

    def test_topological_sort_parallel(self):
        """Test topological sort with parallel nodes."""
        workflow = Workflow(
            name="test-parallel",
            version="1.0",
            nodes=[
                WorkflowNode(id="task1", agent="qwen", prompt="Task 1"),
                WorkflowNode(id="task2", agent="qwen", prompt="Task 2", depends_on=["task1"], parallel=True),
                WorkflowNode(id="task3", agent="qwen", prompt="Task 3", depends_on=["task1"], parallel=True),
                WorkflowNode(id="task4", agent="qwen", prompt="Task 4", depends_on=["task2", "task3"]),
            ],
        )

        graph = DependencyGraph(workflow)
        sorted_nodes = graph.topological_sort()

        # task1 must come first
        assert sorted_nodes[0] == "task1"
        # task2 and task3 can be in any order but before task4
        assert sorted_nodes.index("task2") < sorted_nodes.index("task4")
        assert sorted_nodes.index("task3") < sorted_nodes.index("task4")

    def test_topological_sort_with_cycle_raises(self):
        """Test that topological sort raises error for cyclic graph."""
        workflow = Workflow(
            name="test-cycle",
            version="1.0",
            nodes=[
                WorkflowNode(id="task1", agent="qwen", prompt="Task 1", depends_on=["task2"]),
                WorkflowNode(id="task2", agent="qwen", prompt="Task 2", depends_on=["task1"]),
            ],
        )

        graph = DependencyGraph(workflow)

        with pytest.raises(ValueError) as exc_info:
            graph.topological_sort()

        assert "cycle" in str(exc_info.value).lower()

    def test_get_dependencies_simple(self):
        """Test getting dependencies of a node."""
        workflow = Workflow(
            name="test-deps",
            version="1.0",
            nodes=[
                WorkflowNode(id="task1", agent="qwen", prompt="Task 1"),
                WorkflowNode(id="task2", agent="qwen", prompt="Task 2", depends_on=["task1"]),
                WorkflowNode(id="task3", agent="qwen", prompt="Task 3", depends_on=["task2"]),
            ],
        )

        graph = DependencyGraph(workflow)

        # task3 depends on task2 and task1 (transitively)
        deps = graph.get_dependencies("task3")
        assert deps == {"task1", "task2"}

        # task2 depends only on task1
        deps = graph.get_dependencies("task2")
        assert deps == {"task1"}

        # task1 has no dependencies
        deps = graph.get_dependencies("task1")
        assert deps == set()

    def test_get_dependencies_complex(self):
        """Test getting dependencies in complex graph."""
        workflow = Workflow(
            name="test-deps-complex",
            version="1.0",
            nodes=[
                WorkflowNode(id="task1", agent="qwen", prompt="Task 1"),
                WorkflowNode(id="task2", agent="qwen", prompt="Task 2"),
                WorkflowNode(id="task3", agent="qwen", prompt="Task 3", depends_on=["task1", "task2"]),
                WorkflowNode(id="task4", agent="qwen", prompt="Task 4", depends_on=["task3"]),
            ],
        )

        graph = DependencyGraph(workflow)

        # task4 depends on task3, task2, and task1
        deps = graph.get_dependencies("task4")
        assert deps == {"task1", "task2", "task3"}

    def test_get_dependents_simple(self):
        """Test getting dependents of a node."""
        workflow = Workflow(
            name="test-dependents",
            version="1.0",
            nodes=[
                WorkflowNode(id="task1", agent="qwen", prompt="Task 1"),
                WorkflowNode(id="task2", agent="qwen", prompt="Task 2", depends_on=["task1"]),
                WorkflowNode(id="task3", agent="qwen", prompt="Task 3", depends_on=["task2"]),
            ],
        )

        graph = DependencyGraph(workflow)

        # task1 has task2 and task3 as dependents
        dependents = graph.get_dependents("task1")
        assert dependents == {"task2", "task3"}

        # task2 has task3 as dependent
        dependents = graph.get_dependents("task2")
        assert dependents == {"task3"}

        # task3 has no dependents
        dependents = graph.get_dependents("task3")
        assert dependents == set()

    def test_get_execution_levels_simple(self):
        """Test getting execution levels for simple workflow."""
        workflow = Workflow(
            name="test-levels",
            version="1.0",
            nodes=[
                WorkflowNode(id="task1", agent="qwen", prompt="Task 1"),
                WorkflowNode(id="task2", agent="qwen", prompt="Task 2", depends_on=["task1"]),
                WorkflowNode(id="task3", agent="qwen", prompt="Task 3", depends_on=["task2"]),
            ],
        )

        graph = DependencyGraph(workflow)
        levels = graph.get_execution_levels()

        # Should have 3 levels
        assert len(levels) == 3
        assert levels[0] == ["task1"]
        assert levels[1] == ["task2"]
        assert levels[2] == ["task3"]

    def test_get_execution_levels_parallel(self):
        """Test getting execution levels with parallel nodes."""
        workflow = Workflow(
            name="test-levels-parallel",
            version="1.0",
            nodes=[
                WorkflowNode(id="task1", agent="qwen", prompt="Task 1"),
                WorkflowNode(id="task2", agent="qwen", prompt="Task 2", depends_on=["task1"], parallel=True),
                WorkflowNode(id="task3", agent="qwen", prompt="Task 3", depends_on=["task1"], parallel=True),
                WorkflowNode(id="task4", agent="qwen", prompt="Task 4", depends_on=["task2", "task3"]),
            ],
        )

        graph = DependencyGraph(workflow)
        levels = graph.get_execution_levels()

        # Should have 3 levels
        assert len(levels) == 3
        assert levels[0] == ["task1"]
        # task2 and task3 should be in same level
        assert set(levels[1]) == {"task2", "task3"}
        assert levels[2] == ["task4"]

    def test_graph_with_goto(self):
        """Test graph building with goto edges."""
        workflow = Workflow(
            name="test-goto",
            version="1.0",
            nodes=[
                WorkflowNode(id="task1", agent="qwen", prompt="Task 1"),
                WorkflowNode(id="task2", agent="qwen", prompt="Task 2", depends_on=["task1"], goto="task1"),
            ],
        )

        graph = DependencyGraph(workflow)

        # Should detect cycle due to goto
        assert graph.has_cycle() is True

    def test_topological_sort_example_workflow(self, parser, examples_dir):
        """Test topological sort on real example workflow."""
        workflow_file = examples_dir / "simple-sequential.yaml"
        workflow = parser.parse_file(str(workflow_file))

        graph = DependencyGraph(workflow)

        # Should not have cycles
        assert graph.has_cycle() is False

        # Get topological order
        sorted_nodes = graph.topological_sort()

        # analyze -> execute -> validate
        assert sorted_nodes.index("analyze") < sorted_nodes.index("execute")
        assert sorted_nodes.index("execute") < sorted_nodes.index("validate")

    def test_parallel_workflow_levels(self, parser, examples_dir):
        """Test execution levels on parallel workflow."""
        workflow_file = examples_dir / "parallel-tasks.yaml"
        workflow = parser.parse_file(str(workflow_file))

        graph = DependencyGraph(workflow)
        levels = graph.get_execution_levels()

        # First level should have the three parallel scan nodes
        assert len(levels) >= 2
        # Check that parallel nodes are in same level
        assert "security-scan" in levels[0]
        assert "performance-scan" in levels[0]
        assert "code-quality-scan" in levels[0]
        # Aggregate should be in later level
        assert "aggregate" in levels[1]
