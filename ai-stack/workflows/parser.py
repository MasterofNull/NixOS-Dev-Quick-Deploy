"""
YAML workflow parser.

Parses YAML workflow files into structured Workflow objects.
"""

import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from .models import (
    Workflow,
    WorkflowNode,
    MemoryConfig,
    LoopConfig,
    RetryConfig,
    ErrorHandler,
)


class ParseError(Exception):
    """Exception raised when workflow parsing fails."""

    def __init__(self, message: str, path: Optional[str] = None, line: Optional[int] = None):
        self.message = message
        self.path = path
        self.line = line
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        """Format error message with context."""
        msg = self.message
        if self.path:
            msg = f"{self.path}: {msg}"
        if self.line:
            msg = f"{msg} (line {self.line})"
        return msg


class WorkflowParser:
    """Parse YAML workflow files into Workflow objects."""

    def parse_file(self, yaml_file: str) -> Workflow:
        """
        Parse YAML file into Workflow object.

        Args:
            yaml_file: Path to YAML workflow file

        Returns:
            Workflow object

        Raises:
            ParseError: If YAML is malformed or required fields are missing
        """
        try:
            file_path = Path(yaml_file)
            if not file_path.exists():
                raise ParseError(f"File not found: {yaml_file}")

            with open(file_path, "r") as f:
                workflow_dict = yaml.safe_load(f)

            if not workflow_dict:
                raise ParseError(f"Empty workflow file: {yaml_file}")

            return self.parse_dict(workflow_dict, str(file_path))

        except yaml.YAMLError as e:
            raise ParseError(f"Invalid YAML syntax: {e}", path=yaml_file)
        except Exception as e:
            if isinstance(e, ParseError):
                raise
            raise ParseError(f"Failed to parse workflow: {e}", path=yaml_file)

    def parse_dict(self, workflow_dict: Dict[str, Any], path: Optional[str] = None) -> Workflow:
        """
        Parse workflow dictionary into Workflow object.

        Args:
            workflow_dict: Dictionary representation of workflow
            path: Optional file path for error messages

        Returns:
            Workflow object

        Raises:
            ParseError: If required fields are missing or invalid
        """
        try:
            # Validate required fields
            if "name" not in workflow_dict:
                raise ParseError("Missing required field: name", path=path)
            if "version" not in workflow_dict:
                raise ParseError("Missing required field: version", path=path)
            if "nodes" not in workflow_dict:
                raise ParseError("Missing required field: nodes", path=path)

            # Parse nodes
            nodes = []
            for i, node_dict in enumerate(workflow_dict.get("nodes", [])):
                try:
                    node = self._parse_node(node_dict)
                    nodes.append(node)
                except Exception as e:
                    raise ParseError(
                        f"Error parsing node {i}: {e}",
                        path=path,
                    )

            # Create workflow object (convert version to string if YAML parsed as float)
            version = workflow_dict["version"]
            if not isinstance(version, str):
                version = str(version)

            workflow = Workflow(
                name=workflow_dict["name"],
                version=version,
                description=workflow_dict.get("description"),
                inputs=workflow_dict.get("inputs"),
                agents=workflow_dict.get("agents"),
                nodes=nodes,
                outputs=workflow_dict.get("outputs"),
            )

            return workflow

        except Exception as e:
            if isinstance(e, ParseError):
                raise
            raise ParseError(f"Failed to parse workflow dictionary: {e}", path=path)

    def _parse_node(self, node_dict: Dict[str, Any]) -> WorkflowNode:
        """
        Parse a single node definition.

        Args:
            node_dict: Dictionary representation of node

        Returns:
            WorkflowNode object

        Raises:
            ValueError: If required fields are missing or invalid
        """
        # Validate required fields
        if "id" not in node_dict:
            raise ValueError("Missing required field: id")
        if "agent" not in node_dict:
            raise ValueError("Missing required field: agent")

        # Prompt is required, but for loop nodes it can be in loop.prompt
        has_prompt = "prompt" in node_dict
        has_loop_prompt = "loop" in node_dict and isinstance(node_dict["loop"], dict) and "prompt" in node_dict["loop"]

        if not has_prompt and not has_loop_prompt:
            raise ValueError("Missing required field: prompt (or loop.prompt for loop nodes)")

        # Parse optional nested configurations
        memory = None
        if "memory" in node_dict:
            memory = self._parse_memory_config(node_dict["memory"])

        loop = None
        if "loop" in node_dict:
            loop = self._parse_loop_config(node_dict["loop"])

        retry = None
        if "retry" in node_dict:
            retry = self._parse_retry_config(node_dict["retry"])

        on_error = None
        if "on_error" in node_dict:
            on_error = self._parse_error_handler(node_dict["on_error"])

        # Get prompt (use loop.prompt if available and no top-level prompt)
        prompt = node_dict.get("prompt")
        if not prompt and loop and loop.prompt:
            prompt = loop.prompt

        # Create node object
        node = WorkflowNode(
            id=node_dict["id"],
            agent=node_dict["agent"],
            prompt=prompt,
            depends_on=node_dict.get("depends_on"),
            condition=node_dict.get("condition"),
            memory=memory,
            loop=loop,
            retry=retry,
            parallel=node_dict.get("parallel", False),
            outputs=node_dict.get("outputs"),
            goto=node_dict.get("goto"),
            on_error=on_error,
        )

        return node

    def _parse_memory_config(self, memory_dict: Dict[str, Any]) -> MemoryConfig:
        """
        Parse memory configuration.

        Args:
            memory_dict: Dictionary representation of memory config

        Returns:
            MemoryConfig object

        Raises:
            ValueError: If required fields are missing or invalid
        """
        if "layers" not in memory_dict:
            raise ValueError("Memory config missing required field: layers")

        return MemoryConfig(
            layers=memory_dict["layers"],
            topics=memory_dict.get("topics"),
            max_tokens=memory_dict.get("max_tokens", 500),
            isolation=memory_dict.get("isolation"),
            diary_only=memory_dict.get("diary_only", False),
        )

    def _parse_loop_config(self, loop_dict: Dict[str, Any]) -> LoopConfig:
        """
        Parse loop configuration.

        Args:
            loop_dict: Dictionary representation of loop config

        Returns:
            LoopConfig object

        Raises:
            ValueError: If required fields are missing or invalid
        """
        if "until" not in loop_dict:
            raise ValueError("Loop config missing required field: until")
        if "max_iterations" not in loop_dict:
            raise ValueError("Loop config missing required field: max_iterations")

        return LoopConfig(
            until=loop_dict["until"],
            max_iterations=loop_dict["max_iterations"],
            prompt=loop_dict.get("prompt"),
            fresh_context=loop_dict.get("fresh_context", False),
        )

    def _parse_retry_config(self, retry_dict: Dict[str, Any]) -> RetryConfig:
        """
        Parse retry configuration.

        Args:
            retry_dict: Dictionary representation of retry config

        Returns:
            RetryConfig object

        Raises:
            ValueError: If fields are invalid
        """
        return RetryConfig(
            max_attempts=retry_dict.get("max_attempts", 3),
            on_failure=retry_dict.get("on_failure"),
            backoff=retry_dict.get("backoff", "exponential"),
            backoff_base=retry_dict.get("backoff_base", 1.0),
        )

    def _parse_error_handler(self, error_dict: Dict[str, Any]) -> ErrorHandler:
        """
        Parse error handler configuration.

        Args:
            error_dict: Dictionary representation of error handler

        Returns:
            ErrorHandler object

        Raises:
            ValueError: If required fields are missing
        """
        if "handler" not in error_dict:
            raise ValueError("Error handler missing required field: handler")

        return ErrorHandler(
            handler=error_dict["handler"],
            continue_workflow=error_dict.get("continue", False),
        )
