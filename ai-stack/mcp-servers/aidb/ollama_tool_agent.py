#!/usr/bin/env python3
"""
Ollama Tool-Enabled Agent
Provides Ollama models with full access to MCP tools, AIDB, CLI tools, and RAG
"""

import asyncio
import httpx
import json
import logging
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class ToolCategory(Enum):
    """Categories of tools available to Ollama agents"""
    MCP_SERVER = "mcp_server"  # MCP protocol tools
    DATABASE = "database"  # PostgreSQL/TimescaleDB operations
    RAG = "rag"  # Retrieval-Augmented Generation
    CLI = "cli"  # Command-line tools
    CODEMACHINE = "codemachine"  # CodeMachine-CLI workflows
    NETWORK = "network"  # Network/API operations


@dataclass
class Tool:
    """Represents a tool available to the agent"""
    name: str
    category: ToolCategory
    description: str
    parameters: Dict[str, Any]
    function: Callable
    requires_approval: bool = False


@dataclass
class ToolCall:
    """Represents a tool invocation"""
    tool_name: str
    parameters: Dict[str, Any]
    result: Optional[Any] = None
    error: Optional[str] = None
    execution_time: float = 0.0


class LemonadeToolAgent:
    """
    Enhanced Lemonade agent with full tool access

    Capabilities:
    - MCP Server tools (3,976 cataloged tools)
    - Database queries (PostgreSQL + TimescaleDB)
    - RAG workflows (document search + generation)
    - CLI tools (OpenAI CLI, CodeMachine-CLI, etc.)
    - Network monitoring
    - Internet packet analysis
    """

    def __init__(
        self,
        model_name: str = "Qwen3-4B-Instruct-2507-GGUF",
        ollama_url: str = "http://localhost:8080",
        aidb_url: str = "http://localhost:8091",
        mcp_url: str = "http://localhost:8791"
    ):
        self.model_name = model_name
        self.ollama_url = ollama_url
        self.aidb_url = aidb_url
        self.mcp_url = mcp_url
        self.http_client = httpx.AsyncClient(timeout=300.0)

        # Track tool usage for monitoring
        self.tool_calls: List[ToolCall] = []
        self.available_tools: Dict[str, Tool] = {}

        # Initialize tool registry
        asyncio.create_task(self._load_tools())

    async def _load_tools(self):
        """Load all available tools from various sources"""
        try:
            # Load MCP tools from catalog
            response = await self.http_client.get(f"{self.aidb_url}/tools")
            if response.status_code == 200:
                mcp_tools = response.json()
                for tool_data in mcp_tools.get("tools", []):
                    tool = Tool(
                        name=tool_data["name"],
                        category=ToolCategory.MCP_SERVER,
                        description=tool_data.get("description", ""),
                        parameters=tool_data.get("parameters", {}),
                        function=self._execute_mcp_tool
                    )
                    self.available_tools[tool.name] = tool

            logger.info(f"Loaded {len(self.available_tools)} tools for {self.model_name}")

            # Register built-in tools
            self._register_builtin_tools()

        except Exception as e:
            logger.error(f"Error loading tools: {e}")

    def _register_builtin_tools(self):
        """Register built-in tool implementations"""

        # Database tools
        self.available_tools["query_database"] = Tool(
            name="query_database",
            category=ToolCategory.DATABASE,
            description="Execute SQL query on PostgreSQL/TimescaleDB",
            parameters={"query": "string", "params": "object"},
            function=self._query_database
        )

        self.available_tools["search_documents"] = Tool(
            name="search_documents",
            category=ToolCategory.RAG,
            description="Search documents in knowledge base",
            parameters={"query": "string", "project": "string", "limit": "int"},
            function=self._search_documents
        )

        self.available_tools["vector_search"] = Tool(
            name="vector_search",
            category=ToolCategory.RAG,
            description="Semantic vector similarity search",
            parameters={"query": "string", "top_k": "int"},
            function=self._vector_search
        )

        self.available_tools["execute_codemachine_workflow"] = Tool(
            name="execute_codemachine_workflow",
            category=ToolCategory.CODEMACHINE,
            description="Execute CodeMachine-CLI multi-agent workflow",
            parameters={"specification": "string", "engines": "array"},
            function=self._execute_workflow
        )

        self.available_tools["monitor_network"] = Tool(
            name="monitor_network",
            category=ToolCategory.NETWORK,
            description="Monitor network traffic and connections",
            parameters={"duration": "int", "filter": "string"},
            function=self._monitor_network
        )

        self.available_tools["call_openai_cli"] = Tool(
            name="call_openai_cli",
            category=ToolCategory.CLI,
            description="Call OpenAI CLI tools",
            parameters={"command": "string", "args": "array"},
            function=self._call_openai_cli
        )

    async def _execute_mcp_tool(self, tool_name: str, **kwargs) -> Any:
        """Execute an MCP protocol tool"""
        try:
            response = await self.http_client.post(
                f"{self.mcp_url}/tools/execute",
                json={"tool_name": tool_name, "parameters": kwargs}
            )
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": f"MCP tool failed: {response.status_code}"}
        except Exception as e:
            return {"error": str(e)}

    async def _query_database(self, query: str, params: Optional[Dict] = None) -> Dict:
        """Execute database query"""
        try:
            response = await self.http_client.post(
                f"{self.aidb_url}/query",
                json={"query": query, "params": params or {}}
            )
            return response.json()
        except Exception as e:
            return {"error": str(e)}

    async def _search_documents(
        self,
        query: str,
        project: Optional[str] = None,
        limit: int = 5
    ) -> List[Dict]:
        """Search documents in knowledge base"""
        try:
            params = {"limit": limit}
            if project:
                params["project"] = project

            response = await self.http_client.get(
                f"{self.aidb_url}/documents",
                params=params
            )
            if response.status_code == 200:
                return response.json().get("documents", [])
            return []
        except Exception as e:
            logger.error(f"Document search failed: {e}")
            return []

    async def _vector_search(self, query: str, top_k: int = 5) -> List[Dict]:
        """Perform vector similarity search"""
        try:
            response = await self.http_client.post(
                f"{self.aidb_url}/vector/search",
                json={"query": query, "top_k": top_k}
            )
            return response.json().get("results", [])
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return []

    async def _execute_workflow(
        self,
        specification: str,
        engines: List[str]
    ) -> Dict:
        """Execute CodeMachine-CLI workflow"""
        try:
            response = await self.http_client.post(
                f"{self.aidb_url}/codemachine/workflow",
                json={"specification": specification, "engines": engines}
            )
            return response.json()
        except Exception as e:
            return {"error": str(e)}

    async def _monitor_network(
        self,
        duration: int = 60,
        filter: Optional[str] = None
    ) -> Dict:
        """Monitor network traffic"""
        # This would integrate with network monitoring tools
        return {
            "packets_captured": 0,
            "bytes_sent": 0,
            "bytes_received": 0,
            "connections": []
        }

    async def _call_openai_cli(self, command: str, args: List[str]) -> Dict:
        """Execute OpenAI CLI command"""
        # This would integrate with OpenAI CLI
        return {"output": f"Would execute: {command} {' '.join(args)}"}

    async def generate_with_tools(
        self,
        prompt: str,
        max_tool_calls: int = 10,
        enable_tools: bool = True
    ) -> Dict[str, Any]:
        """
        Generate response with tool calling capability

        Args:
            prompt: User prompt/question
            max_tool_calls: Maximum number of tool calls allowed
            enable_tools: Whether to enable tool calling

        Returns:
            Dictionary with response, tool_calls, and metadata
        """

        if not enable_tools:
            # Simple generation without tools
            response = await self.http_client.post(
                f"{self.ollama_url}/chat/completions",
                json={
                    "model": self.model_name,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                },
            )
            return {
                "response": response.json().get("choices", [{}])[0].get("message", {}).get("content", ""),
                "tool_calls": [],
                "model": self.model_name
            }

        # Build tool-enabled prompt
        tools_description = "\n".join([
            f"- {name}: {tool.description}"
            for name, tool in list(self.available_tools.items())[:20]  # Top 20 tools
        ])

        enhanced_prompt = f"""You are an AI assistant with access to the following tools:

{tools_description}

To use a tool, respond with JSON in this format:
{{"tool": "tool_name", "parameters": {{"param1": "value1"}}}}

User request: {prompt}

If you need to use a tool, respond with the tool call JSON. Otherwise, provide a direct answer."""

        tool_calls_made = []
        iteration = 0
        current_prompt = enhanced_prompt

        while iteration < max_tool_calls:
            # Generate response
            response = await self.http_client.post(
                f"{self.ollama_url}/chat/completions",
                json={
                    "model": self.model_name,
                    "messages": [{"role": "user", "content": current_prompt}],
                    "stream": False,
                },
            )

            generated = (
                response.json()
                .get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )

            # Check if response contains tool call
            try:
                # Try to parse as JSON (tool call)
                tool_call_data = json.loads(generated.strip())

                if "tool" in tool_call_data:
                    tool_name = tool_call_data["tool"]
                    params = tool_call_data.get("parameters", {})

                    # Execute tool
                    if tool_name in self.available_tools:
                        tool = self.available_tools[tool_name]

                        tool_call = ToolCall(
                            tool_name=tool_name,
                            parameters=params
                        )

                        try:
                            import time
                            start = time.time()
                            result = await tool.function(**params)
                            tool_call.execution_time = time.time() - start
                            tool_call.result = result

                        except Exception as e:
                            tool_call.error = str(e)

                        tool_calls_made.append(tool_call)
                        self.tool_calls.append(tool_call)

                        # Update prompt with tool result
                        current_prompt = f"""{current_prompt}

Tool called: {tool_name}
Result: {json.dumps(tool_call.result if tool_call.result else tool_call.error, indent=2)}

Based on this result, provide your final answer to the user."""

                        iteration += 1
                        continue

                    else:
                        # Unknown tool, break and return error
                        return {
                            "response": f"Error: Unknown tool '{tool_name}'",
                            "tool_calls": tool_calls_made,
                            "model": self.model_name
                        }

            except json.JSONDecodeError:
                # Not a tool call, this is the final answer
                return {
                    "response": generated,
                    "tool_calls": tool_calls_made,
                    "model": self.model_name
                }

            iteration += 1

        return {
            "response": "Max tool calls reached",
            "tool_calls": tool_calls_made,
            "model": self.model_name
        }

    async def get_tool_usage_stats(self) -> Dict:
        """Get statistics on tool usage"""
        category_counts = {}
        for call in self.tool_calls:
            tool = self.available_tools.get(call.tool_name)
            if tool:
                cat = tool.category.value
                category_counts[cat] = category_counts.get(cat, 0) + 1

        return {
            "total_calls": len(self.tool_calls),
            "by_category": category_counts,
            "available_tools": len(self.available_tools),
            "avg_execution_time": sum(c.execution_time for c in self.tool_calls) / len(self.tool_calls) if self.tool_calls else 0
        }

    async def close(self):
        """Close HTTP client"""
        await self.http_client.aclose()

async def demo_tool_enabled_agent():
    """Demonstrate Ollama agent with full tool access"""

    print("\n" + "="*70)
    print("Ollama Tool-Enabled Agent Demo")
    print("="*70 + "\n")

    # Initialize agent
    agent = OllamaToolAgent(model_name="qwen3:4b")

    # Wait for tools to load
    await asyncio.sleep(2)

    print(f"Agent initialized with {len(agent.available_tools)} tools\n")

    try:
        # Demo 1: Simple generation (no tools)
        print("--- Demo 1: Simple Generation ---\n")
        result = await agent.generate_with_tools(
            "What is Python?",
            enable_tools=False
        )
        print(f"Response: {result['response'][:200]}...\n")

        # Demo 2: Document search with tools
        print("\n--- Demo 2: Tool-Enabled RAG Query ---\n")
        result = await agent.generate_with_tools(
            "Search the knowledge base for information about monitoring setup and summarize it",
            max_tool_calls=3
        )
        print(f"Tool calls made: {len(result['tool_calls'])}")
        for call in result['tool_calls']:
            print(f"  - {call.tool_name}: {call.execution_time:.2f}s")
        print(f"\nResponse: {result['response'][:300]}...\n")

        # Demo 3: Database query
        print("\n--- Demo 3: Database Query ---\n")
        result = await agent.generate_with_tools(
            "Query the database to count how many documents we have",
            max_tool_calls=2
        )
        print(f"Response: {result['response']}\n")

        # Show statistics
        stats = await agent.get_tool_usage_stats()
        print("\n--- Tool Usage Statistics ---")
        print(f"Total tool calls: {stats['total_calls']}")
        print(f"Available tools: {stats['available_tools']}")
        print(f"Average execution time: {stats['avg_execution_time']:.3f}s")
        print(f"\nBy category:")
        for cat, count in stats['by_category'].items():
            print(f"  {cat}: {count}")

    finally:
        await agent.close()

    print("\n" + "="*70)
    print("Demo Complete!")
    print("="*70 + "\n")


if __name__ == "__main__":
    asyncio.run(demo_tool_enabled_agent())
