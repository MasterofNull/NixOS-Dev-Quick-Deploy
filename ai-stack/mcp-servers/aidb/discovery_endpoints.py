#!/usr/bin/env python3
"""
Discovery Endpoints Integration for AIDB MCP Server
Add these routes to enable progressive disclosure for AI agents
"""

from typing import Dict, Any, Optional
from fastapi import Request, HTTPException
from discovery_api import AgentDiscoveryAPI, DiscoveryLevel, CapabilityCategory


def register_discovery_routes(app, mcp_server):
    """
    Register discovery API routes in AIDB MCP server

    Add to server.py after other route registrations:

        from discovery_endpoints import register_discovery_routes
        register_discovery_routes(self.app, self.mcp_server)
    """

    # Initialize discovery API
    discovery = AgentDiscoveryAPI(
        settings=mcp_server.settings,
        tool_registry=mcp_server._tool_registry,
        skill_registry=mcp_server  # Has skill methods
    )

    @app.get("/discovery")
    async def discovery_root() -> Dict[str, Any]:
        """Root discovery endpoint - redirects to system info"""
        return await discovery.get_system_info()

    @app.get("/discovery/info")
    async def get_system_info() -> Dict[str, Any]:
        """
        Level 0: Basic system information (no auth required)

        Returns system version, contact points, discovery levels
        """
        info = await discovery.get_system_info()
        await mcp_server.record_telemetry(
            event_type="discovery_info",
            source="aidb",
            metadata={"level": "basic"}
        )
        return info

    @app.get("/discovery/quickstart")
    async def get_quickstart() -> Dict[str, Any]:
        """
        Level 0: Quick start guide for AI agents

        Returns step-by-step guide to use the system
        """
        quickstart = await discovery.get_quickstart()
        await mcp_server.record_telemetry(
            event_type="discovery_quickstart",
            source="aidb",
            metadata={"steps": len(quickstart.get("steps", []))}
        )
        return quickstart

    @app.get("/discovery/capabilities")
    async def list_capabilities(
        level: str = "standard",
        category: Optional[str] = None,
        request: Request = None
    ) -> Dict[str, Any]:
        """
        Progressive disclosure: List available capabilities

        Query parameters:
            level: basic | standard | detailed | advanced
            category: knowledge | inference | storage | learning | integration | monitoring

        Authentication:
            - basic/standard: No auth required
            - detailed/advanced: Requires X-API-Key header
        """

        # Validate level
        try:
            disclosure_level = DiscoveryLevel(level)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid level. Must be one of: {[l.value for l in DiscoveryLevel]}"
            )

        # Validate category if provided
        capability_category = None
        if category:
            try:
                capability_category = CapabilityCategory(category)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid category. Must be one of: {[c.value for c in CapabilityCategory]}"
                )

        # Check authentication for detailed/advanced
        authenticated = False
        if disclosure_level in [DiscoveryLevel.DETAILED, DiscoveryLevel.ADVANCED]:
            try:
                mcp_server._require_api_key(request)
                authenticated = True
            except HTTPException:
                # Will be handled in discovery.list_capabilities
                pass

        capabilities = await discovery.list_capabilities(
            level=disclosure_level,
            category=capability_category,
            authenticated=authenticated
        )

        await mcp_server.record_telemetry(
            event_type="discovery_capabilities",
            source="aidb",
            metadata={
                "level": level,
                "category": category,
                "authenticated": authenticated,
                "count": capabilities.get("count", 0)
            }
        )

        return capabilities

    @app.get("/discovery/capabilities/{name}")
    async def get_capability_details(
        name: str,
        request: Request = None
    ) -> Dict[str, Any]:
        """
        Get detailed information about a specific capability

        Path parameters:
            name: Capability name (e.g., "search_documents")

        Returns full capability details including schema, examples, documentation URL
        """

        # Check if authenticated (optional but provides more detail)
        authenticated = False
        try:
            mcp_server._require_api_key(request)
            authenticated = True
        except HTTPException:
            pass

        capability = await discovery.get_capability(name, authenticated=authenticated)

        await mcp_server.record_telemetry(
            event_type="discovery_capability_detail",
            source="aidb",
            metadata={"name": name, "authenticated": authenticated}
        )

        return capability

    @app.get("/discovery/docs")
    async def list_documentation() -> Dict[str, Any]:
        """
        List available documentation resources

        Returns structured guide to all documentation
        """
        return {
            "documentation": {
                "agent_guides": {
                    "path": "/docs/agent-guides/",
                    "structure": "numbered (00-90)",
                    "levels": {
                        "00-02": "Navigation (overview, quick start, service status)",
                        "10-12": "Infrastructure (NixOS, containers, debugging)",
                        "20-22": "AI Stack (local LLM, RAG, continuous learning)",
                        "30-32": "Databases (Qdrant, PostgreSQL, error logging)",
                        "40-44": "Advanced (hybrid workflow, value scoring, federation)",
                        "90": "Comprehensive analysis"
                    },
                    "recommended_order": [
                        "00-SYSTEM-OVERVIEW.md",
                        "01-QUICK-START.md",
                        "20-LOCAL-LLM-USAGE.md",
                        "21-RAG-CONTEXT.md",
                        "40-HYBRID-WORKFLOW.md"
                    ]
                },
                "usage_guide": {
                    "path": "/AI-SYSTEM-USAGE-GUIDE.md",
                    "description": "Complete usage guide with API examples",
                    "topics": [
                        "Quick start commands",
                        "Progressive disclosure usage",
                        "MCP server APIs",
                        "Monitoring & metrics",
                        "RAG & continuous learning",
                        "Troubleshooting"
                    ]
                },
                "test_report": {
                    "path": "/AI-SYSTEM-TEST-REPORT-2025-12-22.md",
                    "description": "System test results and validation",
                    "sections": [
                        "Architecture overview",
                        "Test results (core services)",
                        "Progressive disclosure details",
                        "Issues and fixes"
                    ]
                },
                "agent_onboarding": {
                    "path": "/agent-onboarding-package-v2.0.0/",
                    "files": {
                        "README.md": "System setup guide",
                        "AGENTS.md": "Professional AI agent training"
                    },
                    "topics": [
                        "Code quality standards",
                        "Documentation management",
                        "Development workflows",
                        "Anti-patterns to avoid"
                    ]
                }
            },
            "progressive_learning": {
                "start_here": [
                    "GET /discovery/quickstart",
                    "GET /discovery/capabilities?level=standard",
                    "/docs/agent-guides/00-SYSTEM-OVERVIEW.md"
                ],
                "then": [
                    "/docs/agent-guides/01-QUICK-START.md",
                    "/AI-SYSTEM-USAGE-GUIDE.md"
                ],
                "advanced": [
                    "/docs/agent-guides/40-HYBRID-WORKFLOW.md",
                    "/docs/agent-guides/41-VALUE-SCORING.md",
                    "GET /discovery/capabilities?level=advanced"
                ]
            }
        }

    @app.get("/discovery/contact-points")
    async def get_contact_points() -> Dict[str, Any]:
        """
        Get all system contact points for agent communication

        Returns URLs for all MCP servers and services
        """
        return {
            "mcp_servers": {
                "aidb": {
                    "url": "http://localhost:8091",
                    "websocket": "ws://localhost:8091/ws",
                    "health": "http://localhost:8091/health",
                    "capabilities": [
                        "Document storage & search",
                        "Vector embeddings",
                        "Skill execution",
                        "Tool orchestration",
                        "Continuous learning"
                    ]
                },
                "hybrid_coordinator": {
                    "url": "http://localhost:8092",
                    "health": "http://localhost:8092/health",
                    "capabilities": [
                        "Smart query routing (local vs remote)",
                        "Context augmentation from Qdrant",
                        "Token usage optimization",
                        "Pattern extraction"
                    ]
                },
                "health_monitor": {
                    "url": "http://localhost:8093",
                    "health": "http://localhost:8093/health",
                    "capabilities": [
                        "Service health monitoring",
                        "Dashboard data collection",
                        "Alert generation"
                    ]
                }
            },
            "infrastructure": {
                "qdrant": {
                    "url": "http://localhost:6333",
                    "health": "http://localhost:6333/healthz",
                    "api": "http://localhost:6333/collections",
                    "purpose": "Vector database for embeddings"
                },
                "llama_cpp": {
                    "url": "http://localhost:8080",
                    "health": "http://localhost:8080/health",
                    "api": "http://localhost:8080/v1/completions",
                    "model": "Qwen 2.5 Coder 7B Instruct",
                    "purpose": "Local LLM inference"
                },
                "postgresql": {
                    "host": "localhost",
                    "port": 5432,
                    "database": "mcp",
                    "extensions": ["pgvector"],
                    "purpose": "Relational database with vector support"
                },
                "redis": {
                    "host": "localhost",
                    "port": 6379,
                    "purpose": "Caching layer"
                }
            },
            "recommended_workflow": {
                "step_1": "Check health: GET http://localhost:8091/health",
                "step_2": "Discover capabilities: GET http://localhost:8091/discovery/capabilities",
                "step_3": "Query via hybrid coordinator: POST http://localhost:8092/query",
                "step_4": "Record learning: POST http://localhost:8091/interactions/record"
            }
        }

    return {
        "status": "Discovery endpoints registered",
        "endpoints": [
            "GET /discovery",
            "GET /discovery/info",
            "GET /discovery/quickstart",
            "GET /discovery/capabilities",
            "GET /discovery/capabilities/{name}",
            "GET /discovery/docs",
            "GET /discovery/contact-points"
        ]
    }
