"""
Workflow validator.

Validates workflows against JSON Schema and business rules.
"""

import re
import yaml
from pathlib import Path
from typing import List, Dict, Any, Set, Optional
from .models import Workflow, WorkflowNode


class ValidationError:
    """Represents a validation error with context."""

    def __init__(self, message: str, path: Optional[str] = None, line: Optional[int] = None):
        self.message = message
        self.path = path
        self.line = line

    def __str__(self) -> str:
        """Format error message."""
        msg = self.message
        if self.path:
            msg = f"{self.path}: {msg}"
        if self.line:
            msg = f"{msg} (line {self.line})"
        return msg

    def __repr__(self) -> str:
        return f"ValidationError({self.message!r}, path={self.path!r}, line={self.line})"


class WorkflowValidator:
    """Validate workflows against schema and business rules."""

    # Valid agent IDs
    VALID_AGENTS = {"qwen", "codex", "claude", "gemini"}

    # Valid memory layers
    VALID_LAYERS = {"L0", "L1", "L2", "L3"}

    def __init__(self, schema_file: Optional[str] = None):
        """
        Initialize validator with JSON Schema.

        Args:
            schema_file: Path to JSON Schema file (optional)
        """
        self.schema = None
        if schema_file:
            self._load_schema(schema_file)

    def _load_schema(self, schema_file: str) -> None:
        """Load JSON Schema from file."""
        try:
            with open(schema_file, "r") as f:
                self.schema = yaml.safe_load(f)
        except Exception as e:
            raise ValueError(f"Failed to load schema from {schema_file}: {e}")

    def validate_schema(self, workflow: Workflow) -> List[ValidationError]:
        """
        Validate workflow against JSON Schema.

        Note: This is a simplified validation. For full JSON Schema validation,
        use the jsonschema library in production.

        Args:
            workflow: Workflow object to validate

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Validate workflow name pattern
        if not re.match(r"^[a-z][a-z0-9-]*$", workflow.name):
            errors.append(
                ValidationError(
                    f"Workflow name '{workflow.name}' must match pattern: ^[a-z][a-z0-9-]*$",
                    path="name",
                )
            )

        # Validate version pattern (convert to string if needed for YAML floats)
        version_str = str(workflow.version)
        if not re.match(r"^\d+\.\d+(\.\d+)?$", version_str):
            errors.append(
                ValidationError(
                    f"Version '{workflow.version}' must match pattern: ^\\d+\\.\\d+(\\.\\d+)?$",
                    path="version",
                )
            )

        # Validate nodes
        if not workflow.nodes:
            errors.append(ValidationError("Workflow must have at least one node", path="nodes"))

        # Validate each node
        for i, node in enumerate(workflow.nodes):
            node_errors = self._validate_node(node, i)
            errors.extend(node_errors)

        return errors

    def _validate_node(self, node: WorkflowNode, index: int) -> List[ValidationError]:
        """Validate a single node."""
        errors = []
        path_prefix = f"nodes[{index}]"

        # Validate node ID pattern
        if not re.match(r"^[a-z][a-z0-9-]*$", node.id):
            errors.append(
                ValidationError(
                    f"Node ID '{node.id}' must match pattern: ^[a-z][a-z0-9-]*$",
                    path=f"{path_prefix}.id",
                )
            )

        # Validate prompt length (if prompt exists)
        if node.prompt and len(node.prompt) < 10:
            errors.append(
                ValidationError(
                    f"Node prompt must be at least 10 characters",
                    path=f"{path_prefix}.prompt",
                )
            )

        # Validate outputs
        if node.outputs:
            for output in node.outputs:
                if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", output):
                    errors.append(
                        ValidationError(
                            f"Output variable '{output}' must match pattern: ^[a-zA-Z_][a-zA-Z0-9_]*$",
                            path=f"{path_prefix}.outputs",
                        )
                    )

        # Validate memory config
        if node.memory:
            for layer in node.memory.layers:
                if layer not in self.VALID_LAYERS:
                    errors.append(
                        ValidationError(
                            f"Invalid memory layer: {layer}",
                            path=f"{path_prefix}.memory.layers",
                        )
                    )

            if node.memory.max_tokens < 50 or node.memory.max_tokens > 10000:
                errors.append(
                    ValidationError(
                        f"Memory max_tokens must be between 50 and 10000",
                        path=f"{path_prefix}.memory.max_tokens",
                    )
                )

        return errors

    def validate_dependencies(self, workflow: Workflow) -> List[ValidationError]:
        """
        Validate dependency graph.

        Checks:
        - No circular dependencies
        - Referenced nodes exist
        - Dependencies form a DAG

        Returns:
            List of validation errors
        """
        errors = []
        node_ids = set(workflow.get_node_ids())

        # Check that all referenced nodes exist
        for node in workflow.nodes:
            if node.depends_on:
                for dep_id in node.depends_on:
                    if dep_id not in node_ids:
                        errors.append(
                            ValidationError(
                                f"Node '{node.id}' depends on undefined node '{dep_id}'",
                                path=f"nodes.{node.id}.depends_on",
                            )
                        )

            # Check goto references
            if node.goto and node.goto not in node_ids:
                errors.append(
                    ValidationError(
                        f"Node '{node.id}' has goto to undefined node '{node.goto}'",
                        path=f"nodes.{node.id}.goto",
                    )
                )

            # Check error handler references
            if node.on_error and node.on_error.handler not in node_ids:
                errors.append(
                    ValidationError(
                        f"Node '{node.id}' has error handler referencing undefined node '{node.on_error.handler}'",
                        path=f"nodes.{node.id}.on_error.handler",
                    )
                )

        # Check for circular dependencies using the graph module
        # Note: Workflows with goto may have intentional cycles (for retry loops)
        # We check for cycles in the dependency graph, but goto cycles are allowed
        from .graph import DependencyGraph

        try:
            # Build a graph without goto edges to check dependencies only
            graph_no_goto = self._build_dependency_graph_no_goto(workflow)
            if graph_no_goto.has_cycle():
                cycle = graph_no_goto.find_cycle()
                if cycle:
                    cycle_str = " -> ".join(cycle)
                    errors.append(
                        ValidationError(
                            f"Circular dependency detected: {cycle_str}",
                            path="nodes",
                        )
                    )
        except Exception as e:
            errors.append(
                ValidationError(
                    f"Failed to build dependency graph: {e}",
                    path="nodes",
                )
            )

        return errors

    def validate_variables(self, workflow: Workflow) -> List[ValidationError]:
        """
        Validate variable references.

        Checks:
        - All referenced variables are defined
        - Output variables are unique per node
        - Correct variable syntax

        Returns:
            List of validation errors
        """
        errors = []

        # Pattern to match variable references: ${...}
        var_pattern = re.compile(r"\$\{([a-zA-Z_][a-zA-Z0-9_.\-]*)\}")

        # Collect all available variables
        available_vars = set()

        # Add input variables
        if workflow.inputs:
            for input_name in workflow.inputs.keys():
                available_vars.add(f"inputs.{input_name}")

        # Add agent references
        if workflow.agents:
            for agent_name in workflow.agents.keys():
                available_vars.add(f"agents.{agent_name}")

        # Build node outputs map
        node_outputs: Dict[str, Set[str]] = {}
        for node in workflow.nodes:
            if node.outputs:
                node_outputs[node.id] = set(node.outputs)
                for output in node.outputs:
                    available_vars.add(f"{node.id}.{output}")

        # Special state variables
        available_vars.add("state.completed_tasks")
        available_vars.add("state.remaining_tasks")
        available_vars.add("state.current_score")
        available_vars.add("state.remaining_issues")
        available_vars.add("state.current_service")
        available_vars.add("state.deployed_count")
        available_vars.add("state.total_count")

        # Special error variables (available in error handlers)
        for node in workflow.nodes:
            available_vars.add(f"{node.id}.error")

        # Check each node for variable references
        for node in workflow.nodes:
            # Check prompt
            self._check_variables_in_text(
                node.prompt,
                available_vars,
                f"nodes.{node.id}.prompt",
                errors,
            )

            # Check condition
            if node.condition:
                self._check_variables_in_text(
                    node.condition,
                    available_vars,
                    f"nodes.{node.id}.condition",
                    errors,
                )

            # Check loop prompt
            if node.loop and node.loop.prompt:
                self._check_variables_in_text(
                    node.loop.prompt,
                    available_vars,
                    f"nodes.{node.id}.loop.prompt",
                    errors,
                )

        # Check workflow outputs
        if workflow.outputs:
            for output_name, output_ref in workflow.outputs.items():
                self._check_variables_in_text(
                    output_ref,
                    available_vars,
                    f"outputs.{output_name}",
                    errors,
                )

        # Check for duplicate output variables within nodes
        seen_outputs: Dict[str, str] = {}
        for node in workflow.nodes:
            if node.outputs:
                for output in node.outputs:
                    if output in seen_outputs:
                        errors.append(
                            ValidationError(
                                f"Duplicate output variable '{output}' in nodes '{seen_outputs[output]}' and '{node.id}'",
                                path=f"nodes.{node.id}.outputs",
                            )
                        )
                    else:
                        seen_outputs[output] = node.id

        return errors

    def _check_variables_in_text(
        self,
        text: str,
        available_vars: Set[str],
        path: str,
        errors: List[ValidationError],
    ) -> None:
        """Check that all variable references in text are defined."""
        var_pattern = re.compile(r"\$\{([a-zA-Z_][a-zA-Z0-9_.\-]*)\}")
        matches = var_pattern.findall(text)

        for var_ref in matches:
            # Check if variable is available
            # Allow partial matches for comparison expressions like ${review.decision == 'approve'}
            var_base = var_ref.split()[0] if " " in var_ref else var_ref

            # Check exact match or prefix match
            found = False
            if var_base in available_vars:
                found = True
            else:
                # Check if it's a prefix of any available variable
                for available_var in available_vars:
                    if available_var.startswith(var_base + "."):
                        found = True
                        break

            if not found:
                errors.append(
                    ValidationError(
                        f"Undefined variable reference: ${{{var_ref}}}",
                        path=path,
                    )
                )

    def validate_agents(self, workflow: Workflow) -> List[ValidationError]:
        """
        Validate agent configuration.

        Checks:
        - Agent IDs are valid (qwen, codex, claude, gemini)
        - Agent references resolve correctly

        Returns:
            List of validation errors
        """
        errors = []

        # Validate agent definitions
        if workflow.agents:
            for role, agent_id in workflow.agents.items():
                if agent_id not in self.VALID_AGENTS:
                    errors.append(
                        ValidationError(
                            f"Invalid agent ID '{agent_id}' for role '{role}'",
                            path=f"agents.{role}",
                        )
                    )

        # Validate agent references in nodes
        for node in workflow.nodes:
            # Check if it's a direct agent reference or a role reference
            agent_ref = node.agent

            # Direct agent reference
            if agent_ref in self.VALID_AGENTS:
                continue

            # Role reference: ${agents.role_name}
            role_pattern = re.match(r"\$\{agents\.([a-zA-Z_][a-zA-Z0-9_]*)\}", agent_ref)
            if role_pattern:
                role_name = role_pattern.group(1)
                if not workflow.agents or role_name not in workflow.agents:
                    errors.append(
                        ValidationError(
                            f"Node '{node.id}' references undefined agent role '{role_name}'",
                            path=f"nodes.{node.id}.agent",
                        )
                    )
            else:
                # Invalid agent reference
                errors.append(
                    ValidationError(
                        f"Invalid agent reference '{agent_ref}' in node '{node.id}'",
                        path=f"nodes.{node.id}.agent",
                    )
                )

        return errors

    def _build_dependency_graph_no_goto(self, workflow: Workflow):
        """Build dependency graph without goto edges for cycle detection."""
        from .graph import DependencyGraph

        # Create a temporary workflow without goto edges
        from .models import WorkflowNode
        temp_nodes = []
        for node in workflow.nodes:
            temp_node = WorkflowNode(
                id=node.id,
                agent=node.agent,
                prompt=node.prompt,
                depends_on=node.depends_on,
                condition=node.condition,
                memory=node.memory,
                loop=node.loop,
                retry=node.retry,
                parallel=node.parallel,
                outputs=node.outputs,
                goto=None,  # Remove goto to check only dependency cycles
                on_error=node.on_error,
            )
            temp_nodes.append(temp_node)

        temp_workflow = Workflow(
            name=workflow.name,
            version=workflow.version,
            nodes=temp_nodes,
        )

        return DependencyGraph(temp_workflow)

    def validate_memory(self, workflow: Workflow) -> List[ValidationError]:
        """
        Validate memory configuration.

        Checks:
        - Valid layer specifications (L0, L1, L2, L3)
        - Token budgets are reasonable

        Returns:
            List of validation errors
        """
        errors = []

        for node in workflow.nodes:
            if node.memory:
                # Validate layers
                for layer in node.memory.layers:
                    if layer not in self.VALID_LAYERS:
                        errors.append(
                            ValidationError(
                                f"Invalid memory layer '{layer}' in node '{node.id}'",
                                path=f"nodes.{node.id}.memory.layers",
                            )
                        )

                # Validate token budget
                if node.memory.max_tokens < 50:
                    errors.append(
                        ValidationError(
                            f"Memory max_tokens too low ({node.memory.max_tokens}) in node '{node.id}'",
                            path=f"nodes.{node.id}.memory.max_tokens",
                        )
                    )
                elif node.memory.max_tokens > 10000:
                    errors.append(
                        ValidationError(
                            f"Memory max_tokens too high ({node.memory.max_tokens}) in node '{node.id}'",
                            path=f"nodes.{node.id}.memory.max_tokens",
                        )
                    )

        return errors

    def validate_all(self, workflow: Workflow) -> List[ValidationError]:
        """
        Run all validations.

        Returns:
            Combined list of all validation errors
        """
        errors = []
        errors.extend(self.validate_schema(workflow))
        errors.extend(self.validate_dependencies(workflow))
        errors.extend(self.validate_variables(workflow))
        errors.extend(self.validate_agents(workflow))
        errors.extend(self.validate_memory(workflow))
        return errors
