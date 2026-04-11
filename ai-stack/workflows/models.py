"""
Data models for workflow representation.

These dataclasses represent the structure of workflow definitions
parsed from YAML files.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any


@dataclass
class MemoryConfig:
    """Memory configuration for a workflow node."""

    layers: List[str]
    topics: Optional[List[str]] = None
    max_tokens: int = 500
    isolation: Optional[str] = None
    diary_only: bool = False

    def __post_init__(self):
        """Validate memory configuration."""
        valid_layers = {"L0", "L1", "L2", "L3"}
        for layer in self.layers:
            if layer not in valid_layers:
                raise ValueError(f"Invalid memory layer: {layer}")

        if self.isolation and self.isolation not in {"agent", "global"}:
            raise ValueError(f"Invalid isolation mode: {self.isolation}")


@dataclass
class LoopConfig:
    """Loop configuration for iterative execution."""

    until: str
    max_iterations: int
    prompt: Optional[str] = None
    fresh_context: bool = False

    def __post_init__(self):
        """Validate loop configuration."""
        if self.max_iterations < 1 or self.max_iterations > 100:
            raise ValueError(f"max_iterations must be between 1 and 100, got {self.max_iterations}")


@dataclass
class RetryConfig:
    """Retry configuration for error handling."""

    max_attempts: int = 3
    on_failure: Optional[List[str]] = None
    backoff: str = "exponential"
    backoff_base: float = 1.0

    def __post_init__(self):
        """Validate retry configuration."""
        if self.max_attempts < 1 or self.max_attempts > 10:
            raise ValueError(f"max_attempts must be between 1 and 10, got {self.max_attempts}")

        valid_backoff = {"constant", "linear", "exponential"}
        if self.backoff not in valid_backoff:
            raise ValueError(f"Invalid backoff strategy: {self.backoff}")

        if self.backoff_base < 0.1:
            raise ValueError(f"backoff_base must be >= 0.1, got {self.backoff_base}")


@dataclass
class ErrorHandler:
    """Error handler configuration."""

    handler: str
    continue_workflow: bool = False


@dataclass
class WorkflowNode:
    """A single node in a workflow execution graph."""

    id: str
    agent: str
    prompt: str
    depends_on: Optional[List[str]] = None
    condition: Optional[str] = None
    memory: Optional[MemoryConfig] = None
    loop: Optional[LoopConfig] = None
    retry: Optional[RetryConfig] = None
    parallel: bool = False
    outputs: Optional[List[str]] = None
    goto: Optional[str] = None
    on_error: Optional[ErrorHandler] = None

    def __post_init__(self):
        """Initialize defaults for optional fields."""
        if self.depends_on is None:
            self.depends_on = []
        if self.outputs is None:
            self.outputs = []


@dataclass
class Workflow:
    """A complete workflow definition."""

    name: str
    version: str
    nodes: List[WorkflowNode]
    description: Optional[str] = None
    inputs: Optional[Dict[str, Any]] = None
    agents: Optional[Dict[str, str]] = None
    outputs: Optional[Dict[str, str]] = None

    def __post_init__(self):
        """Initialize defaults for optional fields."""
        if self.inputs is None:
            self.inputs = {}
        if self.agents is None:
            self.agents = {}
        if self.outputs is None:
            self.outputs = {}
        if self.nodes is None:
            self.nodes = []

    def get_node(self, node_id: str) -> Optional[WorkflowNode]:
        """Get a node by ID."""
        for node in self.nodes:
            if node.id == node_id:
                return node
        return None

    def get_node_ids(self) -> List[str]:
        """Get list of all node IDs."""
        return [node.id for node in self.nodes]
