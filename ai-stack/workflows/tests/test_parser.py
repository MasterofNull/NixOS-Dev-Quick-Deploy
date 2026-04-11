"""Tests for workflow parser."""

import pytest
from pathlib import Path
from ..parser import WorkflowParser, ParseError
from ..models import Workflow, WorkflowNode, MemoryConfig, LoopConfig, RetryConfig


class TestWorkflowParser:
    """Test suite for WorkflowParser."""

    @pytest.fixture
    def parser(self):
        """Create a parser instance."""
        return WorkflowParser()

    @pytest.fixture
    def examples_dir(self):
        """Get the examples directory path."""
        repo_root = Path(__file__).parent.parent.parent.parent
        return repo_root / "ai-stack" / "workflows" / "examples"

    def test_parse_simple_sequential(self, parser, examples_dir):
        """Test parsing simple-sequential.yaml."""
        workflow_file = examples_dir / "simple-sequential.yaml"
        workflow = parser.parse_file(str(workflow_file))

        assert workflow.name == "simple-sequential"
        assert workflow.version == "1.0"
        assert len(workflow.nodes) == 3
        assert workflow.nodes[0].id == "analyze"
        assert workflow.nodes[0].agent == "qwen"
        assert workflow.nodes[1].id == "execute"
        assert workflow.nodes[2].id == "validate"
        assert workflow.nodes[1].depends_on == ["analyze"]
        assert workflow.nodes[2].depends_on == ["execute"]

        # Check memory config
        assert workflow.nodes[0].memory is not None
        assert workflow.nodes[0].memory.layers == ["L0", "L1"]
        assert workflow.nodes[0].memory.max_tokens == 300

        # Check outputs
        assert "steps" in workflow.nodes[0].outputs
        assert "estimated_effort" in workflow.nodes[0].outputs

    def test_parse_parallel_tasks(self, parser, examples_dir):
        """Test parsing parallel-tasks.yaml."""
        workflow_file = examples_dir / "parallel-tasks.yaml"
        workflow = parser.parse_file(str(workflow_file))

        assert workflow.name == "parallel-analysis"
        assert workflow.version == "1.0"

        # Check parallel nodes
        parallel_nodes = [n for n in workflow.nodes if n.parallel]
        assert len(parallel_nodes) == 3

        # Check aggregate node depends on all parallel nodes
        aggregate_node = workflow.get_node("aggregate")
        assert aggregate_node is not None
        assert set(aggregate_node.depends_on) == {"security-scan", "performance-scan", "code-quality-scan"}

    def test_parse_conditional_flow(self, parser, examples_dir):
        """Test parsing conditional-flow.yaml."""
        workflow_file = examples_dir / "conditional-flow.yaml"
        workflow = parser.parse_file(str(workflow_file))

        assert workflow.name == "conditional-deployment"

        # Check conditional nodes
        test_node = workflow.get_node("test")
        assert test_node is not None
        assert test_node.condition == "${inputs.run_tests}"

        approval_node = workflow.get_node("approval")
        assert approval_node is not None
        assert approval_node.condition == "${inputs.require_approval}"

        deploy_node = workflow.get_node("deploy")
        assert deploy_node is not None
        assert deploy_node.condition == "${approval.decision == 'yes'}"

        # Check retry config
        assert test_node.retry is not None
        assert test_node.retry.max_attempts == 3

    def test_parse_loop_until_done(self, parser, examples_dir):
        """Test parsing loop-until-done.yaml."""
        workflow_file = examples_dir / "loop-until-done.yaml"
        workflow = parser.parse_file(str(workflow_file))

        assert workflow.name == "iterative-refactoring"

        # Find loop node
        refactor_node = workflow.get_node("refactor")
        assert refactor_node is not None
        assert refactor_node.loop is not None
        assert refactor_node.loop.max_iterations == 10
        assert refactor_node.loop.fresh_context is True
        assert "${state.current_score >= inputs.quality_threshold}" in refactor_node.loop.until

    def test_parse_error_handling(self, parser, examples_dir):
        """Test parsing error-handling.yaml."""
        workflow_file = examples_dir / "error-handling.yaml"
        workflow = parser.parse_file(str(workflow_file))

        assert workflow.name == "resilient-deployment"

        # Check retry configurations
        preflight_node = workflow.get_node("preflight-checks")
        assert preflight_node is not None
        assert preflight_node.retry is not None
        assert preflight_node.retry.max_attempts == 3
        assert preflight_node.retry.backoff == "exponential"
        assert preflight_node.retry.backoff_base == 2

        # Check error handlers
        deploy_node = workflow.get_node("deploy")
        assert deploy_node is not None
        assert deploy_node.on_error is not None
        assert deploy_node.on_error.handler == "rollback"
        assert deploy_node.on_error.continue_workflow is False

    def test_parse_feature_implementation(self, parser, examples_dir):
        """Test parsing feature-implementation.yaml."""
        workflow_file = examples_dir / "feature-implementation.yaml"
        workflow = parser.parse_file(str(workflow_file))

        assert workflow.name == "feature-implementation"

        # Check agent definitions
        assert workflow.agents is not None
        assert workflow.agents["implementer"] == "qwen"
        assert workflow.agents["reviewer"] == "codex"

        # Check agent references in nodes
        analyze_node = workflow.get_node("analyze")
        assert analyze_node is not None
        assert analyze_node.agent == "${agents.implementer}"

        # Check goto
        revise_node = workflow.get_node("revise")
        assert revise_node is not None
        assert revise_node.goto == "review"

    def test_parse_sub_workflow(self, parser, examples_dir):
        """Test parsing sub-workflow.yaml."""
        workflow_file = examples_dir / "sub-workflow.yaml"
        workflow = parser.parse_file(str(workflow_file))

        assert workflow.name == "multi-service-deployment"

        # Check loop in deploy-services node
        deploy_node = workflow.get_node("deploy-services")
        assert deploy_node is not None
        assert deploy_node.loop is not None
        assert deploy_node.loop.max_iterations == 50

    def test_parse_invalid_yaml(self, parser, tmp_path):
        """Test that malformed YAML raises ParseError."""
        # Create a temporary file with invalid YAML
        invalid_file = tmp_path / "invalid.yaml"
        invalid_file.write_text("name: test\n  invalid: indentation")

        with pytest.raises(ParseError) as exc_info:
            parser.parse_file(str(invalid_file))

        assert "Invalid YAML syntax" in str(exc_info.value)

    def test_parse_missing_file(self, parser):
        """Test that missing file raises ParseError."""
        with pytest.raises(ParseError) as exc_info:
            parser.parse_file("nonexistent.yaml")

        assert "File not found" in str(exc_info.value)

    def test_parse_missing_required_fields(self, parser, tmp_path):
        """Test that missing required fields raises ParseError."""
        # Missing 'nodes' field
        invalid_file = tmp_path / "missing_nodes.yaml"
        invalid_file.write_text("name: test\nversion: 1.0\n")

        with pytest.raises(ParseError) as exc_info:
            parser.parse_file(str(invalid_file))

        assert "Missing required field: nodes" in str(exc_info.value)

    def test_parse_dict(self, parser):
        """Test parsing from dictionary."""
        workflow_dict = {
            "name": "test-workflow",
            "version": "1.0",
            "nodes": [
                {
                    "id": "task1",
                    "agent": "qwen",
                    "prompt": "Do something useful",
                }
            ],
        }

        workflow = parser.parse_dict(workflow_dict)
        assert workflow.name == "test-workflow"
        assert len(workflow.nodes) == 1
        assert workflow.nodes[0].id == "task1"

    def test_parse_memory_config(self, parser):
        """Test parsing memory configuration."""
        workflow_dict = {
            "name": "test-memory",
            "version": "1.0",
            "nodes": [
                {
                    "id": "task1",
                    "agent": "qwen",
                    "prompt": "Task with memory",
                    "memory": {
                        "layers": ["L0", "L1", "L2"],
                        "topics": ["architecture", "patterns"],
                        "max_tokens": 600,
                        "isolation": "agent",
                        "diary_only": True,
                    },
                }
            ],
        }

        workflow = parser.parse_dict(workflow_dict)
        memory = workflow.nodes[0].memory
        assert memory is not None
        assert memory.layers == ["L0", "L1", "L2"]
        assert memory.topics == ["architecture", "patterns"]
        assert memory.max_tokens == 600
        assert memory.isolation == "agent"
        assert memory.diary_only is True

    def test_parse_loop_config(self, parser):
        """Test parsing loop configuration."""
        workflow_dict = {
            "name": "test-loop",
            "version": "1.0",
            "nodes": [
                {
                    "id": "task1",
                    "agent": "qwen",
                    "prompt": "Loop task",
                    "loop": {
                        "prompt": "Iteration prompt",
                        "until": "${state.done}",
                        "max_iterations": 5,
                        "fresh_context": True,
                    },
                }
            ],
        }

        workflow = parser.parse_dict(workflow_dict)
        loop = workflow.nodes[0].loop
        assert loop is not None
        assert loop.prompt == "Iteration prompt"
        assert loop.until == "${state.done}"
        assert loop.max_iterations == 5
        assert loop.fresh_context is True

    def test_parse_retry_config(self, parser):
        """Test parsing retry configuration."""
        workflow_dict = {
            "name": "test-retry",
            "version": "1.0",
            "nodes": [
                {
                    "id": "task1",
                    "agent": "qwen",
                    "prompt": "Retry task",
                    "retry": {
                        "max_attempts": 5,
                        "on_failure": ["timeout", "network_error"],
                        "backoff": "linear",
                        "backoff_base": 2.0,
                    },
                }
            ],
        }

        workflow = parser.parse_dict(workflow_dict)
        retry = workflow.nodes[0].retry
        assert retry is not None
        assert retry.max_attempts == 5
        assert retry.on_failure == ["timeout", "network_error"]
        assert retry.backoff == "linear"
        assert retry.backoff_base == 2.0

    def test_parse_error_handler(self, parser):
        """Test parsing error handler configuration."""
        workflow_dict = {
            "name": "test-error",
            "version": "1.0",
            "nodes": [
                {
                    "id": "task1",
                    "agent": "qwen",
                    "prompt": "Task with error handler",
                    "on_error": {
                        "handler": "error-handler",
                        "continue": True,
                    },
                },
                {
                    "id": "error-handler",
                    "agent": "claude",
                    "prompt": "Handle error",
                },
            ],
        }

        workflow = parser.parse_dict(workflow_dict)
        error_handler = workflow.nodes[0].on_error
        assert error_handler is not None
        assert error_handler.handler == "error-handler"
        assert error_handler.continue_workflow is True
