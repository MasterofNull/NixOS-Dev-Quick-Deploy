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

    def to_dict(self) -> Dict[str, Any]:
        """Serialize memory config."""
        return {
            "layers": list(self.layers),
            "topics": list(self.topics) if self.topics is not None else None,
            "max_tokens": self.max_tokens,
            "isolation": self.isolation,
            "diary_only": self.diary_only,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryConfig":
        """Deserialize memory config."""
        return cls(
            layers=list(data.get("layers") or []),
            topics=data.get("topics"),
            max_tokens=data.get("max_tokens", 500),
            isolation=data.get("isolation"),
            diary_only=data.get("diary_only", False),
        )


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

    def to_dict(self) -> Dict[str, Any]:
        """Serialize loop config."""
        return {
            "until": self.until,
            "max_iterations": self.max_iterations,
            "prompt": self.prompt,
            "fresh_context": self.fresh_context,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LoopConfig":
        """Deserialize loop config."""
        return cls(
            until=data["until"],
            max_iterations=data["max_iterations"],
            prompt=data.get("prompt"),
            fresh_context=data.get("fresh_context", False),
        )


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

    def to_dict(self) -> Dict[str, Any]:
        """Serialize retry config."""
        return {
            "max_attempts": self.max_attempts,
            "on_failure": list(self.on_failure) if self.on_failure is not None else None,
            "backoff": self.backoff,
            "backoff_base": self.backoff_base,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RetryConfig":
        """Deserialize retry config."""
        return cls(
            max_attempts=data.get("max_attempts", 3),
            on_failure=data.get("on_failure"),
            backoff=data.get("backoff", "exponential"),
            backoff_base=data.get("backoff_base", 1.0),
        )


@dataclass
class ErrorHandler:
    """Error handler configuration."""

    handler: str
    continue_workflow: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Serialize error handler config."""
        return {
            "handler": self.handler,
            "continue_workflow": self.continue_workflow,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ErrorHandler":
        """Deserialize error handler config."""
        return cls(
            handler=data["handler"],
            continue_workflow=data.get("continue_workflow", False),
        )


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

    def to_dict(self) -> Dict[str, Any]:
        """Serialize workflow node."""
        return {
            "id": self.id,
            "agent": self.agent,
            "prompt": self.prompt,
            "depends_on": list(self.depends_on or []),
            "condition": self.condition,
            "memory": self.memory.to_dict() if self.memory else None,
            "loop": self.loop.to_dict() if self.loop else None,
            "retry": self.retry.to_dict() if self.retry else None,
            "parallel": self.parallel,
            "outputs": list(self.outputs or []),
            "goto": self.goto,
            "on_error": self.on_error.to_dict() if self.on_error else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkflowNode":
        """Deserialize workflow node."""
        memory = data.get("memory")
        loop = data.get("loop")
        retry = data.get("retry")
        on_error = data.get("on_error")
        return cls(
            id=data["id"],
            agent=data["agent"],
            prompt=data["prompt"],
            depends_on=data.get("depends_on"),
            condition=data.get("condition"),
            memory=MemoryConfig.from_dict(memory) if isinstance(memory, dict) else None,
            loop=LoopConfig.from_dict(loop) if isinstance(loop, dict) else None,
            retry=RetryConfig.from_dict(retry) if isinstance(retry, dict) else None,
            parallel=data.get("parallel", False),
            outputs=data.get("outputs"),
            goto=data.get("goto"),
            on_error=ErrorHandler.from_dict(on_error) if isinstance(on_error, dict) else None,
        )


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

    def to_dict(self) -> Dict[str, Any]:
        """Serialize workflow."""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "inputs": self.inputs,
            "agents": self.agents,
            "nodes": [node.to_dict() for node in self.nodes],
            "outputs": self.outputs,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Workflow":
        """Deserialize workflow."""
        return cls(
            name=data["name"],
            version=str(data["version"]),
            description=data.get("description"),
            inputs=data.get("inputs"),
            agents=data.get("agents"),
            nodes=[WorkflowNode.from_dict(node) for node in (data.get("nodes") or [])],
            outputs=data.get("outputs"),
        )
