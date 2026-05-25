"""Integration tests for workflow parser and validator."""

import pytest
from pathlib import Path
from ..parser import WorkflowParser, ParseError
from ..validator import WorkflowValidator, ValidationError
from ..graph import DependencyGraph
from ..models import Workflow


class TestIntegration:
    """End-to-end integration tests."""

    @pytest.fixture
    def parser(self):
        """Create a parser instance."""
        return WorkflowParser()

    @pytest.fixture
    def validator(self):
        """Create a validator instance."""
        return WorkflowValidator()

    @pytest.fixture
    def examples_dir(self):
        """Get the examples directory path."""
        repo_root = Path(__file__).parent.parent.parent.parent
        return repo_root / "ai-stack" / "workflows" / "examples"

    def test_parse_and_validate_simple_sequential(self, parser, validator, examples_dir):
        """Test parsing and validating simple-sequential.yaml."""
        workflow_file = examples_dir / "simple-sequential.yaml"

        # Parse
        workflow = parser.parse_file(str(workflow_file))
        assert workflow.name == "simple-sequential"

        # Validate
        errors = validator.validate_all(workflow)
        assert len(errors) == 0, f"Validation errors: {[str(e) for e in errors]}"

        # Build graph
        graph = DependencyGraph(workflow)
        assert not graph.has_cycle()

        # Check topological order
        sorted_nodes = graph.topological_sort()
        assert len(sorted_nodes) == 3

    def test_parse_and_validate_parallel_tasks(self, parser, validator, examples_dir):
        """Test parsing and validating parallel-tasks.yaml."""
        workflow_file = examples_dir / "parallel-tasks.yaml"

        # Parse
        workflow = parser.parse_file(str(workflow_file))
        assert workflow.name == "parallel-analysis"

        # Validate
        errors = validator.validate_all(workflow)
        assert len(errors) == 0, f"Validation errors: {[str(e) for e in errors]}"

        # Build graph
        graph = DependencyGraph(workflow)
        assert not graph.has_cycle()

        # Check execution levels
        levels = graph.get_execution_levels()
        assert len(levels) == 2
        # Three parallel scans in first level
        assert len(levels[0]) == 3

    def test_parse_and_validate_conditional_flow(self, parser, validator, examples_dir):
        """Test parsing and validating conditional-flow.yaml."""
        workflow_file = examples_dir / "conditional-flow.yaml"

        # Parse
        workflow = parser.parse_file(str(workflow_file))
        assert workflow.name == "conditional-deployment"

        # Validate
        errors = validator.validate_all(workflow)
        assert len(errors) == 0, f"Validation errors: {[str(e) for e in errors]}"

        # Verify conditional nodes
        conditional_nodes = [n for n in workflow.nodes if n.condition]
        assert len(conditional_nodes) == 3

    def test_parse_and_validate_loop_until_done(self, parser, validator, examples_dir):
        """Test parsing and validating loop-until-done.yaml."""
        workflow_file = examples_dir / "loop-until-done.yaml"

        # Parse
        workflow = parser.parse_file(str(workflow_file))
        assert workflow.name == "iterative-refactoring"

        # Validate
        errors = validator.validate_all(workflow)
        assert len(errors) == 0, f"Validation errors: {[str(e) for e in errors]}"

        # Verify loop nodes
        loop_nodes = [n for n in workflow.nodes if n.loop]
        assert len(loop_nodes) == 1
        assert loop_nodes[0].id == "refactor"

    def test_parse_and_validate_error_handling(self, parser, validator, examples_dir):
        """Test parsing and validating error-handling.yaml."""
        workflow_file = examples_dir / "error-handling.yaml"

        # Parse
        workflow = parser.parse_file(str(workflow_file))
        assert workflow.name == "resilient-deployment"

        # Validate
        errors = validator.validate_all(workflow)
        assert len(errors) == 0, f"Validation errors: {[str(e) for e in errors]}"

        # Verify retry configurations
        retry_nodes = [n for n in workflow.nodes if n.retry]
        assert len(retry_nodes) > 0

        # Verify error handlers
        error_handler_nodes = [n for n in workflow.nodes if n.on_error]
        assert len(error_handler_nodes) > 0

    def test_parse_and_validate_feature_implementation(self, parser, validator, examples_dir):
        """Test parsing and validating feature-implementation.yaml."""
        workflow_file = examples_dir / "feature-implementation.yaml"

        # Parse
        workflow = parser.parse_file(str(workflow_file))
        assert workflow.name == "feature-implementation"

        # Validate
        errors = validator.validate_all(workflow)
        assert len(errors) == 0, f"Validation errors: {[str(e) for e in errors]}"

        # Verify agent definitions
        assert "implementer" in workflow.agents
        assert "reviewer" in workflow.agents

        # Verify goto
        goto_nodes = [n for n in workflow.nodes if n.goto]
        assert len(goto_nodes) == 1

    def test_parse_and_validate_sub_workflow(self, parser, validator, examples_dir):
        """Test parsing and validating sub-workflow.yaml."""
        workflow_file = examples_dir / "sub-workflow.yaml"

        # Parse
        workflow = parser.parse_file(str(workflow_file))
        assert workflow.name == "multi-service-deployment"

        # Validate
        errors = validator.validate_all(workflow)
        assert len(errors) == 0, f"Validation errors: {[str(e) for e in errors]}"

    def test_all_examples_parse_validate_graph(self, parser, validator, examples_dir):
        """Test that all example workflows parse, validate, and build graphs correctly."""
        examples = [
            "simple-sequential.yaml",
            "parallel-tasks.yaml",
            "conditional-flow.yaml",
            "loop-until-done.yaml",
            "error-handling.yaml",
            "feature-implementation.yaml",
            "sub-workflow.yaml",
        ]

        for example in examples:
            workflow_file = examples_dir / example

            # Parse
            workflow = parser.parse_file(str(workflow_file))
            assert workflow is not None, f"Failed to parse {example}"

            # Validate
            errors = validator.validate_all(workflow)
            assert len(errors) == 0, f"Validation errors in {example}: {[str(e) for e in errors]}"

            # Build graph
            graph = DependencyGraph(workflow)
            assert graph is not None, f"Failed to build graph for {example}"

            # Check for cycles (except workflows with goto which may have intentional cycles)
            if not any(n.goto for n in workflow.nodes):
                assert not graph.has_cycle(), f"Unexpected cycle in {example}"

    def test_workflow_with_all_features(self, parser, validator):
        """Test a workflow that uses all available features."""
        workflow_dict = {
            "name": "comprehensive-test",
            "version": "1.0",
            "description": "Workflow with all features",
            "inputs": {
                "task_description": {"type": "string", "description": "Task to perform"},
                "enable_review": {"type": "boolean", "default": True},
            },
            "agents": {
                "implementer": "qwen",
                "reviewer": "codex",
            },
            "nodes": [
                {
                    "id": "analyze",
                    "agent": "${agents.implementer}",
                    "prompt": "Analyze: ${inputs.task_description}",
                    "memory": {
                        "layers": ["L0", "L1", "L2"],
                        "topics": ["architecture"],
                        "max_tokens": 500,
                    },
                    "outputs": ["analysis"],
                },
                {
                    "id": "implement",
                    "agent": "${agents.implementer}",
                    "depends_on": ["analyze"],
                    "prompt": "Implement based on: ${analyze.analysis}",
                    "loop": {
                        "prompt": "Continue implementation",
                        "until": "${state.done}",
                        "max_iterations": 10,
                    },
                    "retry": {
                        "max_attempts": 3,
                        "on_failure": ["test_failure"],
                        "backoff": "exponential",
                    },
                    "outputs": ["implementation"],
                },
                {
                    "id": "review",
                    "agent": "${agents.reviewer}",
                    "depends_on": ["implement"],
                    "condition": "${inputs.enable_review}",
                    "prompt": "Review: ${implement.implementation}",
                    "parallel": False,
                    "outputs": ["review_result"],
                },
            ],
            "outputs": {
                "result": "${implement.implementation}",
                "review": "${review.review_result}",
            },
        }

        # Parse
        workflow = parser.parse_dict(workflow_dict)
        assert workflow.name == "comprehensive-test"

        # Validate
        errors = validator.validate_all(workflow)
        assert len(errors) == 0, f"Validation errors: {[str(e) for e in errors]}"

        # Build graph
        graph = DependencyGraph(workflow)
        assert not graph.has_cycle()

        # Verify topological order
        sorted_nodes = graph.topological_sort()
        assert sorted_nodes.index("analyze") < sorted_nodes.index("implement")
        assert sorted_nodes.index("implement") < sorted_nodes.index("review")

    def test_invalid_workflow_fails_validation(self, parser, validator):
        """Test that an invalid workflow fails validation."""
        workflow_dict = {
            "name": "Invalid_Workflow",  # Invalid name (uppercase)
            "version": "invalid",  # Invalid version format
            "nodes": [
                {
                    "id": "task1",
                    "agent": "invalid-agent",  # Invalid agent
                    "prompt": "Short",  # Too short
                    "depends_on": ["nonexistent"],  # Undefined dependency
                }
            ],
        }

        # Parse (should succeed)
        workflow = parser.parse_dict(workflow_dict)

        # Validate (should fail)
        errors = validator.validate_all(workflow)
        assert len(errors) > 0

        # Should have multiple types of errors
        error_messages = [str(e) for e in errors]
        assert any("name" in msg.lower() for msg in error_messages)
        assert any("version" in msg.lower() for msg in error_messages)
        assert any("agent" in msg.lower() for msg in error_messages)
        assert any("prompt" in msg.lower() for msg in error_messages)
        assert any("undefined" in msg.lower() for msg in error_messages)

    def test_circular_dependency_detected(self, parser, validator):
        """Test that circular dependencies are detected during validation."""
        workflow_dict = {
            "name": "circular-test",
            "version": "1.0",
            "nodes": [
                {
                    "id": "task1",
                    "agent": "qwen",
                    "prompt": "Task 1 depends on task3",
                    "depends_on": ["task3"],
                },
                {
                    "id": "task2",
                    "agent": "qwen",
                    "prompt": "Task 2 depends on task1",
                    "depends_on": ["task1"],
                },
                {
                    "id": "task3",
                    "agent": "qwen",
                    "prompt": "Task 3 depends on task2",
                    "depends_on": ["task2"],
                },
            ],
        }

        # Parse
        workflow = parser.parse_dict(workflow_dict)

        # Validate (should detect cycle)
        errors = validator.validate_all(workflow)
        assert any("circular" in str(e).lower() for e in errors)

        # Graph should also detect cycle
        graph = DependencyGraph(workflow)
        assert graph.has_cycle()

    def test_variable_validation_comprehensive(self, parser, validator):
        """Test comprehensive variable validation."""
        workflow_dict = {
            "name": "variable-test",
            "version": "1.0",
            "inputs": {
                "input1": "string",
            },
            "agents": {
                "worker": "qwen",
            },
            "nodes": [
                {
                    "id": "task1",
                    "agent": "${agents.worker}",  # Valid agent reference
                    "prompt": "Process ${inputs.input1}",  # Valid input reference
                    "outputs": ["result1"],
                },
                {
                    "id": "task2",
                    "agent": "codex",
                    "depends_on": ["task1"],
                    "prompt": "Use ${task1.result1}",  # Valid output reference
                    "outputs": ["result2"],
                },
            ],
            "outputs": {
                "final": "${task2.result2}",  # Valid output reference
            },
        }

        # Parse
        workflow = parser.parse_dict(workflow_dict)

        # Validate (should pass)
        errors = validator.validate_all(workflow)
        assert len(errors) == 0, f"Unexpected errors: {[str(e) for e in errors]}"

    def test_memory_config_validation(self, parser, validator):
        """Test memory configuration validation."""
        workflow_dict = {
            "name": "memory-test",
            "version": "1.0",
            "nodes": [
                {
                    "id": "task1",
                    "agent": "qwen",
                    "prompt": "Task with valid memory config",
                    "memory": {
                        "layers": ["L0", "L1", "L2", "L3"],
                        "topics": ["architecture", "patterns"],
                        "max_tokens": 1000,
                        "isolation": "agent",
                        "diary_only": False,
                    },
                },
            ],
        }

        # Parse
        workflow = parser.parse_dict(workflow_dict)

        # Validate (should pass)
        errors = validator.validate_all(workflow)
        assert len(errors) == 0, f"Unexpected errors: {[str(e) for e in errors]}"
