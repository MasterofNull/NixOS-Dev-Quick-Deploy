"""Tests for workflow validator."""

import pytest
from pathlib import Path
from ..validator import WorkflowValidator, ValidationError
from ..parser import WorkflowParser
from ..models import Workflow, WorkflowNode, MemoryConfig


class TestWorkflowValidator:
    """Test suite for WorkflowValidator."""

    @pytest.fixture
    def validator(self):
        """Create a validator instance."""
        return WorkflowValidator()

    @pytest.fixture
    def parser(self):
        """Create a parser instance."""
        return WorkflowParser()

    @pytest.fixture
    def examples_dir(self):
        """Get the examples directory path."""
        repo_root = Path(__file__).parent.parent.parent.parent
        return repo_root / "ai-stack" / "workflows" / "examples"

    def test_validate_all_examples(self, validator, parser, examples_dir):
        """Test that all example workflows are valid."""
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
            workflow = parser.parse_file(str(workflow_file))
            errors = validator.validate_all(workflow)

            # Print errors for debugging
            if errors:
                print(f"\nValidation errors in {example}:")
                for error in errors:
                    print(f"  - {error}")

            assert len(errors) == 0, f"Validation errors in {example}: {[str(e) for e in errors]}"

    def test_validate_schema_valid(self, validator, parser):
        """Test schema validation for valid workflow."""
        workflow = Workflow(
            name="test-workflow",
            version="1.0",
            nodes=[
                WorkflowNode(
                    id="task1",
                    agent="qwen",
                    prompt="Do something useful and interesting",
                )
            ],
        )

        errors = validator.validate_schema(workflow)
        assert len(errors) == 0

    def test_validate_schema_invalid_name(self, validator):
        """Test schema validation catches invalid workflow name."""
        workflow = Workflow(
            name="Invalid_Name",  # Uppercase and underscore not allowed
            version="1.0",
            nodes=[
                WorkflowNode(
                    id="task1",
                    agent="qwen",
                    prompt="Do something useful",
                )
            ],
        )

        errors = validator.validate_schema(workflow)
        assert any("name" in str(e).lower() for e in errors)

    def test_validate_schema_invalid_version(self, validator):
        """Test schema validation catches invalid version."""
        workflow = Workflow(
            name="test-workflow",
            version="invalid",
            nodes=[
                WorkflowNode(
                    id="task1",
                    agent="qwen",
                    prompt="Do something useful",
                )
            ],
        )

        errors = validator.validate_schema(workflow)
        assert any("version" in str(e).lower() for e in errors)

    def test_validate_schema_empty_nodes(self, validator):
        """Test schema validation catches empty nodes list."""
        workflow = Workflow(
            name="test-workflow",
            version="1.0",
            nodes=[],
        )

        errors = validator.validate_schema(workflow)
        assert any("node" in str(e).lower() for e in errors)

    def test_validate_schema_short_prompt(self, validator):
        """Test schema validation catches prompts that are too short."""
        workflow = Workflow(
            name="test-workflow",
            version="1.0",
            nodes=[
                WorkflowNode(
                    id="task1",
                    agent="qwen",
                    prompt="Short",  # Too short
                )
            ],
        )

        errors = validator.validate_schema(workflow)
        assert any("prompt" in str(e).lower() for e in errors)

    def test_detect_circular_dependency_simple(self, validator):
        """Test that circular dependencies are detected."""
        workflow = Workflow(
            name="test-circular",
            version="1.0",
            nodes=[
                WorkflowNode(
                    id="task1",
                    agent="qwen",
                    prompt="Task 1 depends on task2",
                    depends_on=["task2"],
                ),
                WorkflowNode(
                    id="task2",
                    agent="qwen",
                    prompt="Task 2 depends on task1",
                    depends_on=["task1"],
                ),
            ],
        )

        errors = validator.validate_dependencies(workflow)
        assert any("circular" in str(e).lower() for e in errors)

    def test_detect_circular_dependency_complex(self, validator):
        """Test detection of circular dependency in larger graph."""
        workflow = Workflow(
            name="test-circular-complex",
            version="1.0",
            nodes=[
                WorkflowNode(id="task1", agent="qwen", prompt="Task 1", depends_on=["task2"]),
                WorkflowNode(id="task2", agent="qwen", prompt="Task 2", depends_on=["task3"]),
                WorkflowNode(id="task3", agent="qwen", prompt="Task 3", depends_on=["task1"]),
            ],
        )

        errors = validator.validate_dependencies(workflow)
        assert any("circular" in str(e).lower() for e in errors)

    def test_detect_undefined_node_reference(self, validator):
        """Test that undefined node references are caught."""
        workflow = Workflow(
            name="test-undefined",
            version="1.0",
            nodes=[
                WorkflowNode(
                    id="task1",
                    agent="qwen",
                    prompt="Task 1 depends on nonexistent",
                    depends_on=["nonexistent"],
                ),
            ],
        )

        errors = validator.validate_dependencies(workflow)
        assert any("undefined" in str(e).lower() and "nonexistent" in str(e) for e in errors)

    def test_detect_undefined_goto(self, validator):
        """Test that undefined goto references are caught."""
        workflow = Workflow(
            name="test-goto",
            version="1.0",
            nodes=[
                WorkflowNode(
                    id="task1",
                    agent="qwen",
                    prompt="Task with invalid goto",
                    goto="nonexistent",
                ),
            ],
        )

        errors = validator.validate_dependencies(workflow)
        assert any("goto" in str(e).lower() and "undefined" in str(e).lower() for e in errors)

    def test_detect_invalid_variable_reference(self, validator):
        """Test that invalid variable references are caught."""
        workflow = Workflow(
            name="test-vars",
            version="1.0",
            nodes=[
                WorkflowNode(
                    id="task1",
                    agent="qwen",
                    prompt="Reference undefined variable: ${undefined.variable}",
                ),
            ],
        )

        errors = validator.validate_variables(workflow)
        assert any("undefined" in str(e).lower() and "variable" in str(e).lower() for e in errors)

    def test_validate_variables_input_reference(self, validator):
        """Test that input variable references are validated."""
        workflow = Workflow(
            name="test-inputs",
            version="1.0",
            inputs={"task_description": "string"},
            nodes=[
                WorkflowNode(
                    id="task1",
                    agent="qwen",
                    prompt="Process: ${inputs.task_description}",
                ),
            ],
        )

        errors = validator.validate_variables(workflow)
        # Should not have errors for valid input reference
        assert not any("task_description" in str(e) for e in errors)

    def test_validate_variables_node_output_reference(self, validator):
        """Test that node output references are validated."""
        workflow = Workflow(
            name="test-outputs",
            version="1.0",
            nodes=[
                WorkflowNode(
                    id="task1",
                    agent="qwen",
                    prompt="Generate result",
                    outputs=["result"],
                ),
                WorkflowNode(
                    id="task2",
                    agent="qwen",
                    prompt="Use result: ${task1.result}",
                    depends_on=["task1"],
                ),
            ],
        )

        errors = validator.validate_variables(workflow)
        # Should not have errors for valid output reference
        assert not any("task1.result" in str(e) for e in errors)

    def test_detect_duplicate_output_variables(self, validator):
        """Test that duplicate output variables are caught."""
        workflow = Workflow(
            name="test-duplicates",
            version="1.0",
            nodes=[
                WorkflowNode(
                    id="task1",
                    agent="qwen",
                    prompt="Task 1",
                    outputs=["result"],
                ),
                WorkflowNode(
                    id="task2",
                    agent="qwen",
                    prompt="Task 2",
                    outputs=["result"],  # Duplicate
                ),
            ],
        )

        errors = validator.validate_variables(workflow)
        assert any("duplicate" in str(e).lower() and "result" in str(e).lower() for e in errors)

    def test_validate_agents_valid(self, validator):
        """Test agent validation for valid agents."""
        workflow = Workflow(
            name="test-agents",
            version="1.0",
            agents={"implementer": "qwen", "reviewer": "codex"},
            nodes=[
                WorkflowNode(
                    id="task1",
                    agent="${agents.implementer}",
                    prompt="Implement something",
                ),
                WorkflowNode(
                    id="task2",
                    agent="claude",
                    prompt="Direct agent reference",
                ),
            ],
        )

        errors = validator.validate_agents(workflow)
        assert len(errors) == 0

    def test_detect_invalid_agent(self, validator):
        """Test that invalid agent IDs are caught."""
        workflow = Workflow(
            name="test-invalid-agent",
            version="1.0",
            nodes=[
                WorkflowNode(
                    id="task1",
                    agent="invalid-agent",
                    prompt="Task with invalid agent",
                ),
            ],
        )

        errors = validator.validate_agents(workflow)
        assert any("invalid" in str(e).lower() and "agent" in str(e).lower() for e in errors)

    def test_detect_undefined_agent_role(self, validator):
        """Test that undefined agent roles are caught."""
        workflow = Workflow(
            name="test-undefined-role",
            version="1.0",
            nodes=[
                WorkflowNode(
                    id="task1",
                    agent="${agents.undefined_role}",
                    prompt="Reference undefined role",
                ),
            ],
        )

        errors = validator.validate_agents(workflow)
        assert any("undefined" in str(e).lower() and "role" in str(e).lower() for e in errors)

    def test_validate_memory_valid(self, validator):
        """Test memory validation for valid configuration."""
        workflow = Workflow(
            name="test-memory",
            version="1.0",
            nodes=[
                WorkflowNode(
                    id="task1",
                    agent="qwen",
                    prompt="Task with memory",
                    memory=MemoryConfig(
                        layers=["L0", "L1", "L2"],
                        max_tokens=500,
                    ),
                ),
            ],
        )

        errors = validator.validate_memory(workflow)
        assert len(errors) == 0

    def test_detect_invalid_memory_layer(self, validator):
        """Test that invalid memory layers are caught."""
        # This should raise ValueError during model construction
        with pytest.raises(ValueError) as exc_info:
            MemoryConfig(
                layers=["L0", "L5"],  # L5 is invalid
                max_tokens=500,
            )
        assert "Invalid memory layer" in str(exc_info.value)

    def test_detect_invalid_memory_token_budget(self, validator):
        """Test that invalid token budgets are caught."""
        workflow = Workflow(
            name="test-tokens",
            version="1.0",
            nodes=[
                WorkflowNode(
                    id="task1",
                    agent="qwen",
                    prompt="Task with low tokens",
                    memory=MemoryConfig(
                        layers=["L0"],
                        max_tokens=10,  # Too low
                    ),
                ),
            ],
        )

        errors = validator.validate_memory(workflow)
        assert any("max_tokens" in str(e).lower() for e in errors)

    def test_validate_all_combines_errors(self, validator):
        """Test that validate_all combines all error types."""
        workflow = Workflow(
            name="Invalid_Name",  # Schema error
            version="1.0",
            nodes=[
                WorkflowNode(
                    id="task1",
                    agent="invalid-agent",  # Agent error
                    prompt="Reference ${undefined.var}",  # Variable error
                    depends_on=["nonexistent"],  # Dependency error
                ),
            ],
        )

        errors = validator.validate_all(workflow)
        # Should have errors from multiple validators
        assert len(errors) > 3

        # Check that we have different types of errors
        error_messages = [str(e).lower() for e in errors]
        assert any("name" in msg for msg in error_messages)
        assert any("agent" in msg for msg in error_messages)
        assert any("undefined" in msg for msg in error_messages)
