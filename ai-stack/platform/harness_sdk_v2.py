#!/usr/bin/env python3
"""
Harness SDK v2

Comprehensive SDK for agent integration with the AI harness platform.
Supports multiple protocols (HTTP, WebSocket, MCP) and agent types.

Part of Phase 5: Platform Maturity & Ecosystem
"""

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Callable, Union
from uuid import uuid4
import aiohttp
import websockets

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("harness_sdk_v2")


class AgentType(Enum):
    """Supported agent types"""
    CLAUDE = "claude"
    QWEN = "qwen"
    CODEX = "codex"
    GEMINI = "gemini"
    AIDER = "aider"
    CONTINUE = "continue"
    CUSTOM = "custom"


class Protocol(Enum):
    """Communication protocols"""
    HTTP = "http"
    WEBSOCKET = "websocket"
    MCP_STDIO = "mcp_stdio"


class TaskStatus(Enum):
    """Task execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class AgentConfig:
    """Agent configuration"""
    agent_id: str
    agent_type: AgentType
    capabilities: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    preferred_protocol: Protocol = Protocol.HTTP

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d['agent_type'] = self.agent_type.value
        d['preferred_protocol'] = self.preferred_protocol.value
        return d


@dataclass
class TaskRequest:
    """Task execution request"""
    task_id: str
    query: str
    context: Dict[str, Any] = field(default_factory=dict)
    timeout_s: int = 120
    priority: str = "normal"  # low, normal, high, urgent

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TaskResult:
    """Task execution result"""
    task_id: str
    status: TaskStatus
    response: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    execution_time_ms: int = 0
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d['status'] = self.status.value
        return d


@dataclass
class MemoryEntry:
    """Memory storage entry"""
    memory_id: str
    agent_id: str
    content: str
    memory_type: str  # episodic, semantic, procedural
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d['created_at'] = self.created_at.isoformat()
        return d


@dataclass
class Hint:
    """Hint recommendation"""
    hint_id: str
    title: str
    content: str
    relevance_score: float
    context: str
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class HarnessClient:
    """
    Main client for interacting with AI harness platform.
    Supports HTTP REST and WebSocket protocols.
    """

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8003",
        ws_url: str = "ws://127.0.0.1:8003/ws",
        agent_config: Optional[AgentConfig] = None,
        timeout: int = 30
    ):
        self.base_url = base_url
        self.ws_url = ws_url
        self.agent_config = agent_config
        self.timeout = timeout

        self.session: Optional[aiohttp.ClientSession] = None
        self.ws_connection: Optional[websockets.WebSocketClientProtocol] = None
        self.ws_handlers: Dict[str, Callable] = {}

        logger.info(f"HarnessClient initialized (base_url={base_url})")

    async def connect(self):
        """Initialize HTTP session"""
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout))
        logger.info("HTTP session established")

    async def connect_websocket(self):
        """Initialize WebSocket connection"""
        self.ws_connection = await websockets.connect(self.ws_url)
        logger.info("WebSocket connection established")

        # Start message handler loop
        asyncio.create_task(self._ws_message_loop())

    async def disconnect(self):
        """Close connections"""
        if self.session:
            await self.session.close()
            logger.info("HTTP session closed")

        if self.ws_connection:
            await self.ws_connection.close()
            logger.info("WebSocket connection closed")

    async def _ws_message_loop(self):
        """Handle incoming WebSocket messages"""
        try:
            async for message in self.ws_connection:
                data = json.loads(message)
                msg_type = data.get("type", "unknown")

                if msg_type in self.ws_handlers:
                    await self.ws_handlers[msg_type](data)
                else:
                    logger.warning(f"No handler for WebSocket message type: {msg_type}")
        except Exception as e:
            logger.error(f"WebSocket message loop error: {e}")

    def on_websocket_message(self, msg_type: str, handler: Callable):
        """Register WebSocket message handler"""
        self.ws_handlers[msg_type] = handler
        logger.info(f"Registered WebSocket handler for type: {msg_type}")

    async def register_agent(self) -> Dict[str, Any]:
        """Register agent with harness"""
        if not self.agent_config:
            raise ValueError("agent_config required for registration")

        if not self.session:
            await self.connect()

        async with self.session.post(
            f"{self.base_url}/agents/register",
            json=self.agent_config.to_dict()
        ) as resp:
            result = await resp.json()
            logger.info(f"Agent registered: {self.agent_config.agent_id}")
            return result

    async def submit_task(self, task: TaskRequest) -> TaskResult:
        """Submit task for execution"""
        if not self.session:
            await self.connect()

        async with self.session.post(
            f"{self.base_url}/tasks/submit",
            json=task.to_dict()
        ) as resp:
            data = await resp.json()

            result = TaskResult(
                task_id=data["task_id"],
                status=TaskStatus(data["status"]),
                response=data.get("response", ""),
                metadata=data.get("metadata", {}),
                execution_time_ms=data.get("execution_time_ms", 0),
                error=data.get("error")
            )

            logger.info(f"Task submitted: {task.task_id} (status={result.status.value})")
            return result

    async def get_task_status(self, task_id: str) -> TaskResult:
        """Get task execution status"""
        if not self.session:
            await self.connect()

        async with self.session.get(
            f"{self.base_url}/tasks/{task_id}/status"
        ) as resp:
            data = await resp.json()

            return TaskResult(
                task_id=data["task_id"],
                status=TaskStatus(data["status"]),
                response=data.get("response", ""),
                metadata=data.get("metadata", {}),
                execution_time_ms=data.get("execution_time_ms", 0),
                error=data.get("error")
            )

    async def store_memory(self, entry: MemoryEntry) -> str:
        """Store memory entry"""
        if not self.session:
            await self.connect()

        async with self.session.post(
            f"{self.base_url}/memory/store",
            json=entry.to_dict()
        ) as resp:
            data = await resp.json()
            memory_id = data.get("memory_id", entry.memory_id)
            logger.info(f"Memory stored: {memory_id}")
            return memory_id

    async def recall_memory(
        self,
        query: str,
        agent_id: Optional[str] = None,
        memory_type: Optional[str] = None,
        limit: int = 5
    ) -> List[MemoryEntry]:
        """Recall relevant memories"""
        if not self.session:
            await self.connect()

        params = {"query": query, "limit": limit}
        if agent_id:
            params["agent_id"] = agent_id
        if memory_type:
            params["memory_type"] = memory_type

        async with self.session.get(
            f"{self.base_url}/memory/recall",
            params=params
        ) as resp:
            data = await resp.json()

            memories = []
            for item in data.get("memories", []):
                memories.append(MemoryEntry(
                    memory_id=item["memory_id"],
                    agent_id=item["agent_id"],
                    content=item["content"],
                    memory_type=item["memory_type"],
                    tags=item.get("tags", []),
                    metadata=item.get("metadata", {}),
                    created_at=datetime.fromisoformat(item["created_at"]) if "created_at" in item else datetime.now()
                ))

            logger.info(f"Recalled {len(memories)} memories for query: {query[:50]}")
            return memories

    async def get_hints(
        self,
        query: str,
        max_hints: int = 3,
        compact: bool = False
    ) -> List[Hint]:
        """Get contextual hints"""
        if not self.session:
            await self.connect()

        async with self.session.post(
            f"{self.base_url}/hints",
            json={"query": query, "max_hints": max_hints, "compact": compact}
        ) as resp:
            data = await resp.json()

            hints = []
            for item in data.get("hints", []):
                hints.append(Hint(
                    hint_id=item["hint_id"],
                    title=item["title"],
                    content=item["content"],
                    relevance_score=item.get("relevance_score", 0.0),
                    context=item.get("context", ""),
                    tags=item.get("tags", [])
                ))

            logger.info(f"Retrieved {len(hints)} hints for query: {query[:50]}")
            return hints

    async def get_lessons(
        self,
        domain: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get active lessons"""
        if not self.session:
            await self.connect()

        params = {"limit": limit}
        if domain:
            params["domain"] = domain

        async with self.session.get(
            f"{self.base_url}/lessons",
            params=params
        ) as resp:
            data = await resp.json()
            lessons = data.get("lessons", [])
            logger.info(f"Retrieved {len(lessons)} lessons")
            return lessons

    async def invoke_skill(
        self,
        skill_name: str,
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Invoke a registered skill"""
        if not self.session:
            await self.connect()

        async with self.session.post(
            f"{self.base_url}/skills/{skill_name}/invoke",
            json=params
        ) as resp:
            result = await resp.json()
            logger.info(f"Skill invoked: {skill_name}")
            return result

    async def get_agent_capabilities(
        self,
        agent_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get agent capabilities from registry"""
        if not self.session:
            await self.connect()

        params = {}
        if agent_id:
            params["agent_id"] = agent_id

        async with self.session.get(
            f"{self.base_url}/agents/capabilities",
            params=params
        ) as resp:
            capabilities = await resp.json()
            logger.info(f"Retrieved capabilities for agent: {agent_id or 'all'}")
            return capabilities

    async def submit_feedback(
        self,
        task_id: str,
        rating: int,
        feedback: str
    ) -> Dict[str, Any]:
        """Submit task feedback"""
        if not self.session:
            await self.connect()

        async with self.session.post(
            f"{self.base_url}/feedback",
            json={"task_id": task_id, "rating": rating, "feedback": feedback}
        ) as resp:
            result = await resp.json()
            logger.info(f"Feedback submitted for task: {task_id}")
            return result

    async def get_status(self) -> Dict[str, Any]:
        """Get harness status"""
        if not self.session:
            await self.connect()

        async with self.session.get(f"{self.base_url}/status") as resp:
            status = await resp.json()
            return status

    async def get_health(self) -> Dict[str, Any]:
        """Get harness health"""
        if not self.session:
            await self.connect()

        async with self.session.get(f"{self.base_url}/health") as resp:
            health = await resp.json()
            return health


class RealtimeHarnessClient(HarnessClient):
    """
    Extended client with WebSocket support for real-time collaboration.
    """

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8003",
        ws_url: str = "ws://127.0.0.1:8003/ws",
        agent_config: Optional[AgentConfig] = None,
        timeout: int = 30
    ):
        super().__init__(base_url, ws_url, agent_config, timeout)

        # Real-time event handlers
        self.on_task_update: Optional[Callable] = None
        self.on_memory_update: Optional[Callable] = None
        self.on_agent_message: Optional[Callable] = None

    async def connect_realtime(self):
        """Establish real-time connection"""
        await self.connect()
        await self.connect_websocket()

        # Register default handlers
        self.on_websocket_message("task_update", self._handle_task_update)
        self.on_websocket_message("memory_update", self._handle_memory_update)
        self.on_websocket_message("agent_message", self._handle_agent_message)

        logger.info("Real-time connection established")

    async def _handle_task_update(self, data: Dict[str, Any]):
        """Handle task update event"""
        if self.on_task_update:
            await self.on_task_update(data)

    async def _handle_memory_update(self, data: Dict[str, Any]):
        """Handle memory update event"""
        if self.on_memory_update:
            await self.on_memory_update(data)

    async def _handle_agent_message(self, data: Dict[str, Any]):
        """Handle agent message event"""
        if self.on_agent_message:
            await self.on_agent_message(data)

    async def subscribe_to_task(self, task_id: str):
        """Subscribe to task updates"""
        if not self.ws_connection:
            raise RuntimeError("WebSocket not connected")

        await self.ws_connection.send(json.dumps({
            "type": "subscribe",
            "channel": "task",
            "task_id": task_id
        }))

        logger.info(f"Subscribed to task updates: {task_id}")

    async def subscribe_to_agent(self, agent_id: str):
        """Subscribe to agent messages"""
        if not self.ws_connection:
            raise RuntimeError("WebSocket not connected")

        await self.ws_connection.send(json.dumps({
            "type": "subscribe",
            "channel": "agent",
            "agent_id": agent_id
        }))

        logger.info(f"Subscribed to agent messages: {agent_id}")

    async def send_agent_message(
        self,
        recipient_id: str,
        message: str,
        priority: str = "normal"
    ):
        """Send message to another agent"""
        if not self.ws_connection:
            raise RuntimeError("WebSocket not connected")

        await self.ws_connection.send(json.dumps({
            "type": "agent_message",
            "recipient_id": recipient_id,
            "sender_id": self.agent_config.agent_id if self.agent_config else "unknown",
            "message": message,
            "priority": priority
        }))

        logger.info(f"Message sent to agent: {recipient_id}")


class SDKBindingGenerator:
    """
    Generates client bindings for TypeScript and Rust.
    """

    @staticmethod
    def generate_typescript_bindings(output_path: str):
        """Generate TypeScript/JavaScript client bindings"""
        ts_code = '''
/**
 * Harness SDK v2 - TypeScript Client
 * Auto-generated from Python SDK
 */

export enum AgentType {
  CLAUDE = "claude",
  QWEN = "qwen",
  CODEX = "codex",
  GEMINI = "gemini",
  AIDER = "aider",
  CONTINUE = "continue",
  CUSTOM = "custom"
}

export enum TaskStatus {
  PENDING = "pending",
  RUNNING = "running",
  COMPLETED = "completed",
  FAILED = "failed",
  CANCELLED = "cancelled"
}

export interface AgentConfig {
  agent_id: string;
  agent_type: AgentType;
  capabilities: string[];
  metadata: Record<string, any>;
  preferred_protocol: string;
}

export interface TaskRequest {
  task_id: string;
  query: string;
  context: Record<string, any>;
  timeout_s: number;
  priority: string;
}

export interface TaskResult {
  task_id: string;
  status: TaskStatus;
  response: string;
  metadata: Record<string, any>;
  execution_time_ms: number;
  error?: string;
}

export interface MemoryEntry {
  memory_id: string;
  agent_id: string;
  content: string;
  memory_type: string;
  tags: string[];
  metadata: Record<string, any>;
  created_at: string;
}

export interface Hint {
  hint_id: string;
  title: string;
  content: string;
  relevance_score: number;
  context: string;
  tags: string[];
}

export class HarnessClient {
  private baseUrl: string;
  private timeout: number;

  constructor(baseUrl: string = "http://127.0.0.1:8003", timeout: number = 30000) {
    this.baseUrl = baseUrl;
    this.timeout = timeout;
  }

  async registerAgent(config: AgentConfig): Promise<any> {
    const response = await fetch(`${this.baseUrl}/agents/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(config)
    });
    return response.json();
  }

  async submitTask(task: TaskRequest): Promise<TaskResult> {
    const response = await fetch(`${this.baseUrl}/tasks/submit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(task)
    });
    return response.json();
  }

  async getTaskStatus(taskId: string): Promise<TaskResult> {
    const response = await fetch(`${this.baseUrl}/tasks/${taskId}/status`);
    return response.json();
  }

  async storeMemory(entry: MemoryEntry): Promise<string> {
    const response = await fetch(`${this.baseUrl}/memory/store`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(entry)
    });
    const data = await response.json();
    return data.memory_id;
  }

  async recallMemory(
    query: string,
    agentId?: string,
    memoryType?: string,
    limit: number = 5
  ): Promise<MemoryEntry[]> {
    const params = new URLSearchParams({ query, limit: limit.toString() });
    if (agentId) params.append("agent_id", agentId);
    if (memoryType) params.append("memory_type", memoryType);

    const response = await fetch(`${this.baseUrl}/memory/recall?${params}`);
    const data = await response.json();
    return data.memories;
  }

  async getHints(query: string, maxHints: number = 3, compact: boolean = false): Promise<Hint[]> {
    const response = await fetch(`${this.baseUrl}/hints`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, max_hints: maxHints, compact })
    });
    const data = await response.json();
    return data.hints;
  }

  async getStatus(): Promise<any> {
    const response = await fetch(`${this.baseUrl}/status`);
    return response.json();
  }

  async getHealth(): Promise<any> {
    const response = await fetch(`${this.baseUrl}/health`);
    return response.json();
  }
}
'''

        with open(output_path, 'w') as f:
            f.write(ts_code)

        logger.info(f"TypeScript bindings generated: {output_path}")

    @staticmethod
    def generate_rust_bindings(output_path: str):
        """Generate Rust client bindings"""
        rust_code = '''
//! Harness SDK v2 - Rust Client
//! Auto-generated from Python SDK

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum AgentType {
    Claude,
    Qwen,
    Codex,
    Gemini,
    Aider,
    Continue,
    Custom,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum TaskStatus {
    Pending,
    Running,
    Completed,
    Failed,
    Cancelled,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentConfig {
    pub agent_id: String,
    pub agent_type: AgentType,
    pub capabilities: Vec<String>,
    pub metadata: HashMap<String, serde_json::Value>,
    pub preferred_protocol: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TaskRequest {
    pub task_id: String,
    pub query: String,
    pub context: HashMap<String, serde_json::Value>,
    pub timeout_s: u32,
    pub priority: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TaskResult {
    pub task_id: String,
    pub status: TaskStatus,
    pub response: String,
    pub metadata: HashMap<String, serde_json::Value>,
    pub execution_time_ms: u64,
    pub error: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MemoryEntry {
    pub memory_id: String,
    pub agent_id: String,
    pub content: String,
    pub memory_type: String,
    pub tags: Vec<String>,
    pub metadata: HashMap<String, serde_json::Value>,
    pub created_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Hint {
    pub hint_id: String,
    pub title: String,
    pub content: String,
    pub relevance_score: f64,
    pub context: String,
    pub tags: Vec<String>,
}

pub struct HarnessClient {
    base_url: String,
    client: reqwest::Client,
}

impl HarnessClient {
    pub fn new(base_url: &str) -> Self {
        Self {
            base_url: base_url.to_string(),
            client: reqwest::Client::new(),
        }
    }

    pub async fn register_agent(&self, config: &AgentConfig) -> Result<serde_json::Value, reqwest::Error> {
        let url = format!("{}/agents/register", self.base_url);
        let response = self.client.post(&url).json(config).send().await?;
        response.json().await
    }

    pub async fn submit_task(&self, task: &TaskRequest) -> Result<TaskResult, reqwest::Error> {
        let url = format!("{}/tasks/submit", self.base_url);
        let response = self.client.post(&url).json(task).send().await?;
        response.json().await
    }

    pub async fn get_task_status(&self, task_id: &str) -> Result<TaskResult, reqwest::Error> {
        let url = format!("{}/tasks/{}/status", self.base_url, task_id);
        let response = self.client.get(&url).send().await?;
        response.json().await
    }

    pub async fn store_memory(&self, entry: &MemoryEntry) -> Result<String, reqwest::Error> {
        let url = format!("{}/memory/store", self.base_url);
        let response = self.client.post(&url).json(entry).send().await?;
        let data: serde_json::Value = response.json().await?;
        Ok(data["memory_id"].as_str().unwrap_or("").to_string())
    }

    pub async fn recall_memory(
        &self,
        query: &str,
        agent_id: Option<&str>,
        memory_type: Option<&str>,
        limit: u32,
    ) -> Result<Vec<MemoryEntry>, reqwest::Error> {
        let mut url = format!("{}/memory/recall?query={}&limit={}", self.base_url, query, limit);
        if let Some(aid) = agent_id {
            url.push_str(&format!("&agent_id={}", aid));
        }
        if let Some(mt) = memory_type {
            url.push_str(&format!("&memory_type={}", mt));
        }

        let response = self.client.get(&url).send().await?;
        let data: serde_json::Value = response.json().await?;
        let memories: Vec<MemoryEntry> = serde_json::from_value(data["memories"].clone()).unwrap_or_default();
        Ok(memories)
    }

    pub async fn get_status(&self) -> Result<serde_json::Value, reqwest::Error> {
        let url = format!("{}/status", self.base_url);
        let response = self.client.get(&url).send().await?;
        response.json().await
    }

    pub async fn get_health(&self) -> Result<serde_json::Value, reqwest::Error> {
        let url = format!("{}/health", self.base_url);
        let response = self.client.get(&url).send().await?;
        response.json().await
    }
}
'''

        with open(output_path, 'w') as f:
            f.write(rust_code)

        logger.info(f"Rust bindings generated: {output_path}")


async def main():
    """Example usage"""
    # Create client
    client = HarnessClient(base_url="http://127.0.0.1:8003")

    # Configure agent
    agent_config = AgentConfig(
        agent_id="test_agent_001",
        agent_type=AgentType.CUSTOM,
        capabilities=["coding", "analysis", "testing"],
        metadata={"version": "1.0.0"}
    )

    try:
        # Connect
        await client.connect()

        # Register agent
        await client.register_agent()

        # Submit task
        task = TaskRequest(
            task_id=str(uuid4()),
            query="Analyze codebase structure",
            context={"repo_path": "/path/to/repo"},
            timeout_s=120
        )
        result = await client.submit_task(task)
        print(f"Task result: {result.to_dict()}")

        # Store memory
        memory = MemoryEntry(
            memory_id=str(uuid4()),
            agent_id=agent_config.agent_id,
            content="Analyzed codebase structure with 15 modules",
            memory_type="episodic",
            tags=["analysis", "codebase"]
        )
        await client.store_memory(memory)

        # Get hints
        hints = await client.get_hints("How to optimize database queries?")
        for hint in hints:
            print(f"Hint: {hint.title} (score={hint.relevance_score})")

        # Get status
        status = await client.get_status()
        print(f"Harness status: {status.get('status', 'unknown')}")

    finally:
        await client.disconnect()

    # Generate language bindings
    print("\nGenerating language bindings...")
    SDKBindingGenerator.generate_typescript_bindings("harness_sdk.ts")
    SDKBindingGenerator.generate_rust_bindings("harness_sdk.rs")
    print("Bindings generated successfully")


if __name__ == "__main__":
    asyncio.run(main())
