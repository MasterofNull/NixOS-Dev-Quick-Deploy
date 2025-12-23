#!/usr/bin/env python3
"""
Progressive Disclosure Discovery API
Provides structured entry points for AI agents to discover system capabilities

This module implements a layered discovery system:
- Level 0: Basic system info (always available)
- Level 1: Available capabilities (minimal mode)
- Level 2: Detailed schemas (requires authentication)
- Level 3: Advanced features (skill discovery, federation)
"""

from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from enum import Enum


class DiscoveryLevel(str, Enum):
    """Progressive disclosure levels"""
    BASIC = "basic"           # System info, health, basic capabilities
    STANDARD = "standard"     # Tool/skill names, descriptions
    DETAILED = "detailed"     # Full schemas, parameters
    ADVANCED = "advanced"     # Federation, custom skills, ML models


class CapabilityCategory(str, Enum):
    """Capability categories for organization"""
    KNOWLEDGE = "knowledge"           # Document search, RAG, context
    INFERENCE = "inference"           # LLM calls, embeddings, ML models
    STORAGE = "storage"               # Database operations, vector storage
    LEARNING = "learning"             # Continuous learning, pattern extraction
    INTEGRATION = "integration"       # MCP servers, skills, federation
    MONITORING = "monitoring"         # Health checks, metrics, telemetry


class CapabilitySummary(BaseModel):
    """Minimal capability description"""
    name: str
    category: CapabilityCategory
    description: str = Field(max_length=200)
    cost_estimate: str = Field(description="Token/resource cost: free, low, medium, high")
    requires_auth: bool = False


class CapabilityDetail(BaseModel):
    """Detailed capability with full schema"""
    name: str
    category: CapabilityCategory
    description: str
    endpoint: str
    method: str  # GET, POST, etc.
    parameters: Dict[str, Any]
    response_schema: Dict[str, Any]
    examples: List[Dict[str, Any]]
    cost_estimate: str
    requires_auth: bool
    documentation_url: Optional[str] = None


class SystemCapabilities(BaseModel):
    """Complete system capability manifest"""
    version: str
    discovery_levels: List[DiscoveryLevel]
    categories: List[CapabilityCategory]
    total_capabilities: int
    contact_points: Dict[str, str]  # Service URLs


class AgentDiscoveryAPI:
    """
    Progressive disclosure API for AI agents

    Usage:
        api = AgentDiscoveryAPI(settings, tool_registry, skill_registry)

        # Level 0: Basic info
        info = await api.get_system_info()

        # Level 1: List capabilities
        caps = await api.list_capabilities(level=DiscoveryLevel.STANDARD)

        # Level 2: Get specific capability details
        detail = await api.get_capability("search_documents", authenticated=True)

        # Level 3: Advanced discovery
        skills = await api.discover_skills()
    """

    def __init__(self, settings, tool_registry, skill_registry):
        self.settings = settings
        self.tool_registry = tool_registry
        self.skill_registry = skill_registry

    async def get_system_info(self) -> Dict[str, Any]:
        """
        Level 0: Basic system information (always available, no auth required)

        Returns:
            System version, available services, contact points
        """
        return {
            "system": "NixOS Hybrid AI Learning Stack",
            "version": "2.1.0",
            "discovery_api_version": "1.0.0",
            "architecture": "hand-in-glove",
            "progressive_disclosure": True,
            "contact_points": {
                "aidb_mcp": "http://localhost:8091",
                "hybrid_coordinator": "http://localhost:8092",
                "vector_db": "http://localhost:6333",
                "local_llm": "http://localhost:8080",
                "health_monitor": "http://localhost:8093"
            },
            "discovery_levels": [level.value for level in DiscoveryLevel],
            "next_steps": {
                "list_capabilities": "GET /discovery/capabilities?level=standard",
                "get_started": "GET /discovery/quickstart",
                "documentation": "GET /discovery/docs"
            }
        }

    async def list_capabilities(
        self,
        level: DiscoveryLevel = DiscoveryLevel.STANDARD,
        category: Optional[CapabilityCategory] = None,
        authenticated: bool = False
    ) -> Dict[str, Any]:
        """
        List available capabilities at specified disclosure level

        Args:
            level: How much detail to include
            category: Filter by capability category
            authenticated: Whether user has provided API key

        Returns:
            List of capabilities with appropriate detail level
        """

        capabilities = []

        # Knowledge capabilities
        if category is None or category == CapabilityCategory.KNOWLEDGE:
            capabilities.extend([
                CapabilitySummary(
                    name="search_documents",
                    category=CapabilityCategory.KNOWLEDGE,
                    description="Semantic search across knowledge base using vector embeddings",
                    cost_estimate="low",
                    requires_auth=False
                ),
                CapabilitySummary(
                    name="get_context",
                    category=CapabilityCategory.KNOWLEDGE,
                    description="Retrieve relevant context for a query using RAG",
                    cost_estimate="low",
                    requires_auth=False
                ),
                CapabilitySummary(
                    name="import_documents",
                    category=CapabilityCategory.KNOWLEDGE,
                    description="Import documents into knowledge base with embeddings",
                    cost_estimate="medium",
                    requires_auth=True
                )
            ])

        # Inference capabilities
        if category is None or category == CapabilityCategory.INFERENCE:
            capabilities.extend([
                CapabilitySummary(
                    name="local_llm_query",
                    category=CapabilityCategory.INFERENCE,
                    description="Query local LLM (Qwen 2.5 Coder 7B) via llama.cpp",
                    cost_estimate="free",
                    requires_auth=False
                ),
                CapabilitySummary(
                    name="generate_embeddings",
                    category=CapabilityCategory.INFERENCE,
                    description="Generate 384-dim embeddings using SentenceTransformer",
                    cost_estimate="free",
                    requires_auth=False
                ),
                CapabilitySummary(
                    name="hybrid_query",
                    category=CapabilityCategory.INFERENCE,
                    description="Smart routing: local LLM for simple queries, remote for complex",
                    cost_estimate="low",
                    requires_auth=False
                )
            ])

        # Storage capabilities
        if category is None or category == CapabilityCategory.STORAGE:
            capabilities.extend([
                CapabilitySummary(
                    name="vector_store",
                    category=CapabilityCategory.STORAGE,
                    description="Store vectors in Qdrant with metadata and search",
                    cost_estimate="low",
                    requires_auth=True
                ),
                CapabilitySummary(
                    name="sql_query",
                    category=CapabilityCategory.STORAGE,
                    description="Execute SQL queries on PostgreSQL + pgvector",
                    cost_estimate="low",
                    requires_auth=True
                )
            ])

        # Learning capabilities
        if category is None or category == CapabilityCategory.LEARNING:
            capabilities.extend([
                CapabilitySummary(
                    name="record_interaction",
                    category=CapabilityCategory.LEARNING,
                    description="Store query-response pairs for continuous learning",
                    cost_estimate="low",
                    requires_auth=False
                ),
                CapabilitySummary(
                    name="extract_patterns",
                    category=CapabilityCategory.LEARNING,
                    description="Identify high-value interaction patterns (score ≥ 0.7)",
                    cost_estimate="medium",
                    requires_auth=True
                ),
                CapabilitySummary(
                    name="value_scoring",
                    category=CapabilityCategory.LEARNING,
                    description="Calculate interaction value (5-factor algorithm)",
                    cost_estimate="free",
                    requires_auth=False
                )
            ])

        # Integration capabilities
        if category is None or category == CapabilityCategory.INTEGRATION:
            capabilities.extend([
                CapabilitySummary(
                    name="list_skills",
                    category=CapabilityCategory.INTEGRATION,
                    description="List available agent skills (29 total)",
                    cost_estimate="free",
                    requires_auth=False
                ),
                CapabilitySummary(
                    name="execute_skill",
                    category=CapabilityCategory.INTEGRATION,
                    description="Execute a specific skill by name",
                    cost_estimate="medium",
                    requires_auth=True
                ),
                CapabilitySummary(
                    name="discover_remote_skills",
                    category=CapabilityCategory.INTEGRATION,
                    description="Discover skills from GitHub repos",
                    cost_estimate="low",
                    requires_auth=False
                )
            ])

        # Monitoring capabilities
        if category is None or category == CapabilityCategory.MONITORING:
            capabilities.extend([
                CapabilitySummary(
                    name="health_check",
                    category=CapabilityCategory.MONITORING,
                    description="Check health of all services",
                    cost_estimate="free",
                    requires_auth=False
                ),
                CapabilitySummary(
                    name="get_metrics",
                    category=CapabilityCategory.MONITORING,
                    description="Get effectiveness metrics (token savings, local %)",
                    cost_estimate="free",
                    requires_auth=False
                ),
                CapabilitySummary(
                    name="telemetry",
                    category=CapabilityCategory.MONITORING,
                    description="Query telemetry events for analysis",
                    cost_estimate="low",
                    requires_auth=True
                )
            ])

        # Filter by auth requirement
        if not authenticated:
            capabilities = [c for c in capabilities if not c.requires_auth]

        # Return based on disclosure level
        if level == DiscoveryLevel.BASIC:
            return {
                "level": level.value,
                "count": len(capabilities),
                "capabilities": [c.name for c in capabilities]
            }
        elif level == DiscoveryLevel.STANDARD:
            return {
                "level": level.value,
                "count": len(capabilities),
                "capabilities": [c.dict() for c in capabilities],
                "next_steps": {
                    "get_details": "GET /discovery/capabilities/{name}",
                    "upgrade_level": "Use detailed or advanced level with API key"
                }
            }
        elif level == DiscoveryLevel.DETAILED:
            if not authenticated:
                return {
                    "error": "Authentication required for detailed disclosure",
                    "hint": "Provide X-API-Key header"
                }
            # Return full capability details (would fetch from registry)
            return {
                "level": level.value,
                "count": len(capabilities),
                "capabilities": [c.dict() for c in capabilities],
                "schemas_available": True
            }
        else:  # ADVANCED
            if not authenticated:
                return {
                    "error": "Authentication required for advanced discovery",
                    "hint": "Provide X-API-Key header"
                }
            return await self._get_advanced_capabilities()

    async def get_capability(self, name: str, authenticated: bool = False) -> Dict[str, Any]:
        """
        Get detailed information about a specific capability

        Args:
            name: Capability name
            authenticated: Whether user is authenticated

        Returns:
            Full capability details including schema, examples, docs
        """

        # Example for search_documents
        if name == "search_documents":
            return {
                "name": "search_documents",
                "category": "knowledge",
                "description": "Semantic search across knowledge base using vector embeddings. Searches 5 collections: codebase-context, skills-patterns, error-solutions, best-practices, interaction-history.",
                "endpoint": "GET /documents",
                "method": "GET",
                "parameters": {
                    "search": {"type": "string", "required": True, "description": "Search query"},
                    "project": {"type": "string", "required": False, "description": "Filter by project"},
                    "limit": {"type": "integer", "required": False, "default": 5, "description": "Max results"}
                },
                "response_schema": {
                    "results": "array",
                    "count": "integer",
                    "collections_searched": "array"
                },
                "examples": [
                    {
                        "request": "GET /documents?search=NixOS+error&limit=3",
                        "response": {
                            "results": [
                                {"content": "...", "score": 0.92, "collection": "error-solutions"}
                            ],
                            "count": 3
                        }
                    }
                ],
                "cost_estimate": "low (~100 tokens)",
                "requires_auth": False,
                "documentation_url": "/docs/agent-guides/21-RAG-CONTEXT.md"
            }

        # Would fetch from registry for other capabilities
        return {"error": "Capability not found", "hint": "Use /discovery/capabilities to list all"}

    async def _get_advanced_capabilities(self) -> Dict[str, Any]:
        """Advanced capabilities (federation, ML models, custom skills)"""
        return {
            "level": "advanced",
            "federation": {
                "available": True,
                "endpoint": "GET /federated-servers",
                "description": "Discover and connect to other MCP servers"
            },
            "ml_models": {
                "available": True,
                "endpoint": "GET /ml-models",
                "models": ["all-MiniLM-L6-v2", "qwen2.5-coder-7b-instruct"]
            },
            "skill_discovery": {
                "available": True,
                "endpoint": "GET /skills/discover",
                "remote_repos": ["numman-ali/openskills"]
            },
            "fine_tuning": {
                "available": True,
                "description": "Generate fine-tuning datasets from high-value interactions"
            }
        }

    async def get_quickstart(self) -> Dict[str, Any]:
        """
        Level 0: Quick start guide for agents
        """
        return {
            "title": "AI Agent Quick Start Guide",
            "version": "2.1.0",
            "steps": [
                {
                    "step": 1,
                    "action": "Check system health",
                    "endpoint": "GET /health",
                    "expected": {"status": "healthy"}
                },
                {
                    "step": 2,
                    "action": "Discover capabilities",
                    "endpoint": "GET /discovery/capabilities?level=standard",
                    "expected": {"count": "18+", "categories": 6}
                },
                {
                    "step": 3,
                    "action": "Try semantic search",
                    "endpoint": "GET /documents?search=YOUR_QUERY",
                    "example": "GET /documents?search=NixOS+configuration&limit=3"
                },
                {
                    "step": 4,
                    "action": "Query local LLM",
                    "endpoint": "POST /query (via Hybrid Coordinator)",
                    "url": "http://localhost:8092/query",
                    "body": {"query": "How do I fix X?", "context": {}}
                },
                {
                    "step": 5,
                    "action": "Record interaction for learning",
                    "endpoint": "POST /interactions/record",
                    "description": "System learns from successful interactions"
                }
            ],
            "progressive_disclosure": {
                "current_level": "basic",
                "next_level": "standard (no auth required)",
                "upgrade_to_detailed": "Provide API key for full schemas",
                "upgrade_to_advanced": "Access federation, ML models, custom skills"
            },
            "documentation": {
                "guides": "/docs/agent-guides/ (00-90 numbered guides)",
                "usage": "/AI-SYSTEM-USAGE-GUIDE.md",
                "onboarding": "/agent-onboarding-package-v2.0.0/README.md"
            }
        }
