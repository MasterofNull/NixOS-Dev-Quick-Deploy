#!/usr/bin/env python3
"""
Progressive Disclosure Token Count Validation
Tests the claim: "Progressive disclosure uses ~220 tokens vs 3000+ without it"

This script can run without a live AI stack by analyzing the API response structures.
"""

import json
from pathlib import Path
from typing import Dict, List

# Simulated API responses (based on actual implementation)
RESPONSES = {
    "health": {
        "status": "healthy",
        "version": "1.0.0",
        "service": "aidb",
        "capabilities_url": "/aidb/discovery/info"
    },

    "discovery_info": {
        "service": "aidb",
        "description": "AI Database & Context API for agent discovery",
        "features": [
            {"id": "vector_search", "name": "Vector Search", "description": "Semantic search using embeddings"},
            {"id": "skills_catalog", "name": "Skills Catalog", "description": "Browse and query agent skills"},
            {"id": "telemetry", "name": "Telemetry", "description": "Event tracking and analytics"},
            {"id": "tool_registry", "name": "Tool Registry", "description": "Discover available tools"},
            {"id": "progressive_disclosure", "name": "Progressive Disclosure", "description": "Gradual information exposure"}
        ],
        "quick start_url": "/aidb/discovery/quickstart",
        "docs_url": "/aidb/docs"
    },

    "quickstart": {
        "service": "aidb",
        "workflow": [
            {
                "step": 1,
                "name": "Authentication",
                "description": "Authenticate with API key",
                "endpoint": "GET /health",
                "headers": {"X-API-Key": "your-key"},
                "example_response": {"status": "healthy"}
            },
            {
                "step": 2,
                "name": "Discover Features",
                "description": "Get available features",
                "endpoint": "GET /discovery/info",
                "example_response": "{ features: [...] }"
            },
            {
                "step": 3,
                "name": "Search Documentation",
                "description": "Semantic search for information",
                "endpoint": "POST /vector/search",
                "request_body": {
                    "collection": "nixos_docs",
                    "query": "how to install a package",
                    "limit": 5
                },
                "example_response": "{ results: [...] }"
            }
        ],
        "common_patterns": [
            {
                "name": "Simple Query",
                "steps": ["health", "search"]
            },
            {
                "name": "Full Discovery",
                "steps": ["health", "discovery", "search", "store"]
            }
        ],
        "next_steps": {
            "detailed_docs": "/aidb/docs/api",
            "examples": "/aidb/docs/examples"
        }
    },

    "full_docs": """
    # AIDB MCP Server - Complete Documentation

    ## Table of Contents
    1. Introduction
    2. Architecture Overview
    3. Authentication
    4. API Reference
    5. Vector Search
    6. Skills System
    7. Telemetry
    8. Tool Registry
    9. Progressive Disclosure
    10. Error Handling
    11. Rate Limiting
    12. Best Practices
    13. Examples
    14. Troubleshooting
    15. FAQ

    ## 1. Introduction

    AIDB (AI Database) is a comprehensive Model Context Protocol (MCP) server designed for agent-based systems. It provides semantic search, skill management, telemetry tracking, and progressive disclosure capabilities.

    ### Key Features
    - **Vector Search**: Semantic search using 384-dimensional embeddings
    - **Skills Catalog**: Browse and execute pre-defined agent skills
    - **Telemetry**: Track events and usage patterns
    - **Tool Registry**: Discover available tools and their schemas
    - **Progressive Disclosure**: Minimize initial context with gradual information exposure

    ### Architecture

    AIDB uses a layered architecture:

    ```
    Agent → nginx (TLS) → AIDB API → PostgreSQL (metadata)
                                   → Qdrant (vectors)
                                   → Redis (cache)
                                   → Embeddings Service
    ```

    ## 2. Authentication

    All API requests require authentication using an API key passed in the `X-API-Key` header.

    ### Obtaining an API Key

    API keys are generated during deployment. Contact your system administrator to obtain a key.

    ### Using the API Key

    ```bash
    curl -H "X-API-Key: your-key-here" https://localhost:8443/aidb/health
    ```

    ### Security Best Practices

    1. Never commit API keys to version control
    2. Rotate keys regularly (every 90 days)
    3. Use environment variables for key storage
    4. Implement key rotation without downtime
    5. Monitor for unauthorized access

    ## 3. API Reference

    ### Health Check

    **Endpoint:** `GET /health`
    **Description:** Check service availability
    **Authentication:** Required

    **Response:**
    ```json
    {
      "status": "healthy",
      "version": "1.0.0",
      "service": "aidb"
    }
    ```

    ### Discovery Info

    **Endpoint:** `GET /discovery/info`
    **Description:** Get available features and capabilities
    **Authentication:** Required

    **Response:**
    ```json
    {
      "service": "aidb",
      "features": [...],
      "quickstart_url": "/aidb/discovery/quickstart"
    }
    ```

    ### Vector Search

    **Endpoint:** `POST /vector/search`
    **Description:** Semantic search using embeddings
    **Authentication:** Required

    **Request Body:**
    ```json
    {
      "collection": "nixos_docs",
      "query": "how to install vim",
      "limit": 5
    }
    ```

    **Response:**
    ```json
    {
      "results": [
        {
          "id": "123",
          "text": "To install vim on NixOS...",
          "score": 0.95,
          "metadata": {...}
        }
      ],
      "total": 142,
      "query_time_ms": 45
    }
    ```

    ## 4. Vector Search Deep Dive

    Vector search uses semantic embeddings to find relevant documents. Here's how it works:

    ### Embedding Generation

    Documents are converted to 384-dimensional vectors using the `all-MiniLM-L6-v2` model.

    ### Search Process

    1. Query is embedded using the same model
    2. Qdrant performs HNSW search for nearest neighbors
    3. Results are scored by cosine similarity
    4. Top K results are returned

    ### Collections

    Available collections:
    - `nixos_docs`: NixOS documentation
    - `solved_issues`: Previously solved problems
    - `skill_embeddings`: Agent skill descriptions

    ### Performance Tuning

    - Default limit: 10 results
    - Max limit: 100 results
    - Use pagination for large result sets
    - Consider caching common queries

    ## 5. Skills System

    Skills are pre-defined capabilities that agents can execute.

    ### Listing Skills

    **Endpoint:** `GET /skills`

    ### Executing Skills

    **Endpoint:** `POST /skills/execute`

    ### Creating Skills

    Skills are defined in YAML format and loaded at startup.

    ## 6. Telemetry

    Track events and usage patterns for analytics and debugging.

    ### Logging Events

    **Endpoint:** `POST /telemetry/events`

    ### Querying Events

    **Endpoint:** `GET /telemetry/events`

    ## 7. Tool Registry

    Discover available tools and their JSON schemas.

    ### Listing Tools

    **Endpoint:** `GET /tools`

    ### Getting Tool Schema

    **Endpoint:** `GET /tools/{tool_id}/schema`

    ## 8. Progressive Disclosure

    Progressive disclosure minimizes initial context by providing information gradually.

    ### Workflow

    1. Agent starts with health check (~20 tokens)
    2. Agent requests discovery info (~50 tokens)
    3. Agent requests quickstart guide (~150 tokens)
    4. Agent requests detailed docs only when needed (~2000 tokens)

    ### Benefits

    - Reduced token usage (90% savings)
    - Faster responses
    - Lower costs
    - Better LLM performance

    ## 9. Error Handling

    All errors return standard HTTP status codes:

    - 400: Bad Request
    - 401: Unauthorized
    - 403: Forbidden
    - 404: Not Found
    - 429: Rate Limit Exceeded
    - 500: Internal Server Error

    ## 10. Rate Limiting

    Rate limits are enforced per API key:
    - 60 requests per minute
    - 1000 requests per hour

    ## 11. Best Practices

    1. Use progressive disclosure workflow
    2. Cache responses when possible
    3. Implement retry logic with exponential backoff
    4. Monitor rate limits
    5. Use batch operations when available

    ## 12. Examples

    ### Python Example

    ```python
    import httpx

    API_KEY = "your-key"
    BASE_URL = "https://localhost:8443/aidb"

    async def search(query: str):
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{BASE_URL}/vector/search",
                headers={"X-API-Key": API_KEY},
                json={
                    "collection": "nixos_docs",
                    "query": query,
                    "limit": 5
                }
            )
            return response.json()
    ```

    ### JavaScript Example

    ```javascript
    const API_KEY = "your-key";
    const BASE_URL = "https://localhost:8443/aidb";

    async function search(query) {
        const response = await fetch(`${BASE_URL}/vector/search`, {
            method: "POST",
            headers: {
                "X-API-Key": API_KEY,
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                collection: "nixos_docs",
                query: query,
                limit: 5
            })
        });
        return await response.json();
    }
    ```

    ## 13. Troubleshooting

    ### Common Issues

    **Issue:** Authentication failures
    **Solution:** Verify API key is correct and not expired

    **Issue:** Slow search performance
    **Solution:** Reduce limit, use pagination, check index health

    **Issue:** Rate limit errors
    **Solution:** Implement backoff, reduce request frequency

    ## 14. FAQ

    **Q: How often should I rotate API keys?**
    A: Every 90 days is recommended.

    **Q: What embedding model is used?**
    A: all-MiniLM-L6-v2 (384 dimensions)

    **Q: Can I use custom collections?**
    A: Not currently. Contact admin to add collections.

    **Q: What's the max query size?**
    A: 10,000 characters (10KB)

    **Q: Is there a bulk search API?**
    A: Not yet, coming in v2.0

    ---
    End of Documentation
    """
}


def count_tokens(text: str) -> int:
    """
    Rough token counter (1 token ≈ 4 characters for English text)
    More accurate than word count, less accurate than tiktoken
    """
    # For JSON, count actual content after formatting
    if isinstance(text, dict):
        text = json.dumps(text, indent=2)

    # GPT-4 approximation: ~4 chars per token
    return len(text) // 4


def analyze_progressive_disclosure():
    """Analyze token usage for progressive disclosure workflow"""

    print("=" * 80)
    print("Progressive Disclosure Token Usage Analysis")
    print("=" * 80)
    print()

    # Progressive approach
    print("📊 Progressive Disclosure Workflow:")
    print("-" * 80)

    health_tokens = count_tokens(RESPONSES["health"])
    discovery_tokens = count_tokens(RESPONSES["discovery_info"])
    quickstart_tokens = count_tokens(RESPONSES["quickstart"])
    full_docs_tokens = count_tokens(RESPONSES["full_docs"])

    progressive_total = health_tokens + discovery_tokens + quickstart_tokens

    print(f"1. Health Check:       {health_tokens:4d} tokens")
    print(f"2. Discovery Info:     {discovery_tokens:4d} tokens")
    print(f"3. Quickstart Guide:   {quickstart_tokens:4d} tokens")
    print(f"{'─' * 40}")
    print(f"Total (Progressive):   {progressive_total:4d} tokens")
    print()

    # Traditional approach
    print("📊 Traditional Full Documentation Approach:")
    print("-" * 80)
    print(f"Full Documentation:    {full_docs_tokens:4d} tokens")
    print()

    # Comparison
    print("📈 Comparison:")
    print("-" * 80)
    savings_tokens = full_docs_tokens - progressive_total
    savings_percent = (savings_tokens / full_docs_tokens) * 100

    print(f"Token Savings:         {savings_tokens:4d} tokens ({savings_percent:.1f}%)")
    print(f"Latency Reduction:     ~{savings_percent:.0f}% (fewer tokens to process)")
    print(f"Cost Reduction:        ~{savings_percent:.0f}% (input token costs)")
    print()

    # Validation
    print("✅ Validation:")
    print("-" * 80)

    # Original claim: ~220 tokens
    claimed_tokens = 220
    tolerance = 0.5  # 50% tolerance

    if progressive_total <= claimed_tokens * (1 + tolerance):
        print(f"✅ PASS: Progressive disclosure uses {progressive_total} tokens")
        print(f"   (Claimed ~{claimed_tokens}, tolerance ±{tolerance*100:.0f}%)")
    else:
        print(f"❌ FAIL: Progressive disclosure uses {progressive_total} tokens")
        print(f"   (Claimed ~{claimed_tokens}, limit {int(claimed_tokens * (1 + tolerance))})")

    if savings_percent >= 85:
        print(f"✅ PASS: Achieves {savings_percent:.1f}% token savings (target ≥85%)")
    else:
        print(f"⚠️  WARN: Only {savings_percent:.1f}% token savings (target ≥85%)")

    print()

    # Agent workflow simulation
    print("🤖 Typical Agent Workflow:")
    print("-" * 80)
    print("Scenario 1: Simple Query (Agent knows what it wants)")
    print(f"   Health → Search: {health_tokens} + ~50 = ~{health_tokens + 50} tokens")
    print()
    print("Scenario 2: First-Time Setup (Agent learning system)")
    print(f"   Health → Discovery → Quickstart: {progressive_total} tokens")
    print()
    print("Scenario 3: Deep Dive (Agent needs detailed info)")
    print(f"   Progressive + Specific Docs: {progressive_total} + ~500 = ~{progressive_total + 500} tokens")
    print(f"   (Still much less than {full_docs_tokens} tokens for full docs)")
    print()

    # Context window impact
    print("📐 Context Window Impact:")
    print("-" * 80)
    context_window = 8192  # GPT-4 default

    progressive_pct = (progressive_total / context_window) * 100
    full_docs_pct = (full_docs_tokens / context_window) * 100

    print(f"Progressive: {progressive_total}/{context_window} tokens ({progressive_pct:.1f}% of window)")
    print(f"Full Docs:   {full_docs_tokens}/{context_window} tokens ({full_docs_pct:.1f}% of window)")
    print(f"Difference:  {full_docs_pct - progressive_pct:.1f}% more space for actual work")
    print()

    # Performance metrics
    print("⚡ Performance Metrics:")
    print("-" * 80)

    # Assume 50ms per 1000 tokens for processing
    progressive_latency = (progressive_total / 1000) * 50
    full_docs_latency = (full_docs_tokens / 1000) * 50

    print(f"Progressive Latency:   ~{progressive_latency:.0f}ms")
    print(f"Full Docs Latency:     ~{full_docs_latency:.0f}ms")
    print(f"Latency Savings:       ~{full_docs_latency - progressive_latency:.0f}ms ({savings_percent:.0f}%)")
    print()

    # Cost analysis
    print("💰 Cost Analysis (GPT-4 Pricing):")
    print("-" * 80)

    # GPT-4 pricing: ~$0.01 per 1K input tokens
    cost_per_1k = 0.01

    progressive_cost = (progressive_total / 1000) * cost_per_1k
    full_docs_cost = (full_docs_tokens / 1000) * cost_per_1k
    cost_savings = full_docs_cost - progressive_cost

    print(f"Progressive Cost:      ${progressive_cost:.4f} per request")
    print(f"Full Docs Cost:        ${full_docs_cost:.4f} per request")
    print(f"Cost Savings:          ${cost_savings:.4f} per request ({savings_percent:.0f}%)")
    print()
    print(f"At 1000 requests/day:")
    print(f"   Progressive: ${progressive_cost * 1000:.2f}/day")
    print(f"   Full Docs:   ${full_docs_cost * 1000:.2f}/day")
    print(f"   Savings:     ${cost_savings * 1000:.2f}/day (${cost_savings * 365 * 1000:.2f}/year)")
    print()

    print("=" * 80)
    print("Summary: Progressive Disclosure Analysis Complete")
    print("=" * 80)

    return {
        "progressive_tokens": progressive_total,
        "full_docs_tokens": full_docs_tokens,
        "savings_percent": savings_percent,
        "passes_validation": progressive_total <= claimed_tokens * (1 + tolerance)
    }


if __name__ == "__main__":
    results = analyze_progressive_disclosure()

    # Exit with appropriate code
    exit(0 if results["passes_validation"] else 1)
