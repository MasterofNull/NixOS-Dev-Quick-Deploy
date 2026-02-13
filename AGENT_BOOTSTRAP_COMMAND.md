# Agent Bootstrap Command Block

## Quick Start for Remote Agents

This document provides a comprehensive bootstrap command block for remote agents to quickly connect to and integrate with the NixOS AI Stack.

### Prerequisites

Before connecting your agent to the AI stack, ensure you have:

1. Network access to the AI stack services
2. API keys for services that require authentication
3. Appropriate permissions for the operations you'll perform

### Bootstrap Command Block

Use this complete command block to bootstrap your agent connection:

```bash
#!/bin/bash
# Agent Bootstrap Script for NixOS AI Stack

# Configuration - Update these with your environment details
AI_STACK_HOST=${AI_STACK_HOST:-"your-ai-stack-host.com"}
AIDB_PORT=${AIDB_PORT:-8091}
HYBRID_PORT=${HYBRID_PORT:-8092}
RALPH_PORT=${RALPH_PORT:-8098}
EMBEDDINGS_PORT=${EMBEDDINGS_PORT:-8081}
NIXOS_DOCS_PORT=${NIXOS_DOCS_PORT:-8094}

# API Keys (set these as environment variables or in a secure way)
export AIDB_API_KEY=${AIDB_API_KEY:-""}
export HYBRID_API_KEY=${HYBRID_API_KEY:-""}
export RALPH_API_KEY=${RALPH_API_KEY:-""}

# Service URLs
export AIDB_URL="http://${AI_STACK_HOST}:${AIDB_PORT}"
export HYBRID_URL="http://${AI_STACK_HOST}:${HYBRID_PORT}"
export RALPH_URL="http://${AI_STACK_HOST}:${RALPH_PORT}"
export EMBEDDINGS_URL="http://${AI_STACK_HOST}:${EMBEDDINGS_PORT}"
export NIXOS_DOCS_URL="http://${AI_STACK_HOST}:${NIXOS_DOCS_PORT}"

echo "🔍 Verifying connectivity to AI Stack services..."

# Verify connectivity to core services
echo "Checking AIDB connection..."
if curl -sf "$AIDB_URL/health" > /dev/null; then
    echo "✅ AIDB: Connected"
else
    echo "❌ AIDB: Unreachable"
    CONNECTIVITY_ERROR=true
fi

echo "Checking Hybrid Coordinator connection..."
if curl -sf "$HYBRID_URL/health" > /dev/null; then
    echo "✅ Hybrid Coordinator: Connected"
else
    echo "❌ Hybrid Coordinator: Unreachable"
    CONNECTIVITY_ERROR=true
fi

echo "Checking Ralph Wiggum connection..."
if curl -sf "$RALPH_URL/health" > /dev/null; then
    echo "✅ Ralph Wiggum: Connected"
else
    echo "❌ Ralph Wiggum: Unreachable"
    CONNECTIVITY_ERROR=true
fi

echo "Checking Embeddings service connection..."
if curl -sf "$EMBEDDINGS_URL/health" > /dev/null; then
    echo "✅ Embeddings: Connected"
else
    echo "❌ Embeddings: Unreachable"
    CONNECTIVITY_ERROR=true
fi

if [ "$CONNECTIVITY_ERROR" = true ]; then
    echo "⚠️ Warning: Some services are unreachable. Check network connectivity."
fi

# Test authenticated access if API keys are provided
if [ -n "$AIDB_API_KEY" ]; then
    echo "Testing AIDB authenticated access..."
    if curl -sf -H "X-API-Key: $AIDB_API_KEY" "$AIDB_URL/discovery/capabilities" > /dev/null; then
        echo "✅ AIDB: Authenticated access OK"
    else
        echo "❌ AIDB: Authentication failed"
    fi
fi

if [ -n "$HYBRID_API_KEY" ]; then
    echo "Testing Hybrid Coordinator authenticated access..."
    if curl -sf -H "X-API-Key: $HYBRID_API_KEY" "$HYBRID_URL/health" > /dev/null; then
        echo "✅ Hybrid Coordinator: Authenticated access OK"
    else
        echo "❌ Hybrid Coordinator: Authentication failed"
    fi
fi

# Discover available capabilities
echo "📋 Discovering available capabilities..."
curl -s -H "X-API-Key: $AIDB_API_KEY" "$AIDB_URL/discovery/capabilities?level=standard" | jq '.' > /tmp/ai-stack-capabilities.json

echo "📋 Available capabilities:"
cat /tmp/ai-stack-capabilities.json | jq -r '.capabilities[].name' | head -10

echo "🚀 Bootstrap complete! Environment variables set:"
echo "   AIDB_URL=$AIDB_URL"
echo "   HYBRID_URL=$HYBRID_URL"
echo "   RALPH_URL=$RALPH_URL"
echo "   EMBEDDINGS_URL=$EMBEDDINGS_URL"
echo "   NIXOS_DOCS_URL=$NIXOS_DOCS_URL"

echo ""
echo "💡 Next steps:"
echo "   1. Use the environment variables in your agent code"
echo "   2. Test specific endpoints based on your needs"
echo "   3. Implement error handling and retry logic"
echo "   4. Monitor service health regularly"
```

### Python Agent Integration Example

Here's how to integrate the bootstrap in a Python agent:

```python
import os
import httpx
import asyncio
from typing import Dict, Any, Optional

class AIAgentBootstrap:
    def __init__(self):
        # Load configuration from environment variables
        self.aidb_url = os.getenv("AIDB_URL", "http://localhost:8091")
        self.hybrid_url = os.getenv("HYBRID_URL", "http://localhost:8092")
        self.ralph_url = os.getenv("RALPH_URL", "http://localhost:8098")
        self.embeddings_url = os.getenv("EMBEDDINGS_URL", "http://localhost:8081")
        
        # Load API keys
        self.aidb_api_key = os.getenv("AIDB_API_KEY")
        self.hybrid_api_key = os.getenv("HYBRID_API_KEY")
        self.ralph_api_key = os.getenv("RALPH_API_KEY")
        
        # Create HTTP client
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def check_connectivity(self) -> Dict[str, bool]:
        """Check connectivity to all services"""
        results = {}
        
        # Check AIDB
        try:
            headers = {"X-API-Key": self.aidb_api_key} if self.aidb_api_key else {}
            response = await self.client.get(f"{self.aidb_url}/health", headers=headers)
            results["aidb"] = response.status_code == 200
        except Exception:
            results["aidb"] = False
        
        # Check Hybrid Coordinator
        try:
            headers = {"X-API-Key": self.hybrid_api_key} if self.hybrid_api_key else {}
            response = await self.client.get(f"{self.hybrid_url}/health", headers=headers)
            results["hybrid"] = response.status_code == 200
        except Exception:
            results["hybrid"] = False
            
        return results
    
    async def search_knowledge_base(self, query: str) -> Dict[str, Any]:
        """Search the knowledge base using AIDB"""
        headers = {"X-API-Key": self.aidb_api_key} if self.aidb_api_key else {}
        params = {"search": query, "limit": 5}
        
        try:
            response = await self.client.get(
                f"{self.aidb_url}/documents",
                headers=headers,
                params=params
            )
            return response.json()
        except Exception as e:
            return {"error": str(e), "results": []}
    
    async def submit_ralph_task(self, prompt: str, backend: str = "aider") -> Dict[str, Any]:
        """Submit a task to Ralph Wiggum"""
        headers = {"X-API-Key": self.ralph_api_key} if self.ralph_api_key else {}
        headers["Content-Type"] = "application/json"
        
        payload = {
            "prompt": prompt,
            "backend": backend,
            "max_iterations": 10
        }
        
        try:
            response = await self.client.post(
                f"{self.ralph_url}/tasks",
                headers=headers,
                json=payload
            )
            return response.json()
        except Exception as e:
            return {"error": str(e)}

# Usage example
async def main():
    agent = AIAgentBootstrap()
    
    # Check connectivity
    connectivity = await agent.check_connectivity()
    print(f"Connectivity: {connectivity}")
    
    # Test knowledge base search
    results = await agent.search_knowledge_base("How do I configure NixOS?")
    print(f"Search results: {len(results.get('documents', []))} documents found")
    
    # Submit a test task to Ralph
    task = await agent.submit_ralph_task("Write a hello world script in Python")
    print(f"Task submitted: {task.get('task_id')}")

if __name__ == "__main__":
    asyncio.run(main())
```

### Environment Setup Script

Create a `.env` file for your agent:

```bash
# .env
# NixOS AI Stack Configuration
AIDB_URL=http://your-ai-stack-host:8091
HYBRID_URL=http://your-ai-stack-host:8092
RALPH_URL=http://your-ai-stack-host:8098
EMBEDDINGS_URL=http://your-ai-stack-host:8081
NIXOS_DOCS_URL=http://your-ai-stack-host:8094

# API Keys (store securely)
AIDB_API_KEY=your_aidb_api_key_here
HYBRID_API_KEY=your_hybrid_api_key_here
RALPH_API_KEY=your_ralph_api_key_here

# Optional: Timeout and retry settings
AGENT_REQUEST_TIMEOUT=30
AGENT_RETRY_ATTEMPTS=3
AGENT_RETRY_DELAY=1
```

### Security Best Practices

1. **Never hardcode API keys** in your agent code
2. **Use environment variables** or secure credential stores
3. **Implement proper error handling** for network failures
4. **Add rate limiting** to avoid overwhelming services
5. **Monitor service health** and degrade gracefully

### Troubleshooting

Common issues and solutions:

1. **Connection timeouts**: Check firewall rules and network connectivity
2. **Authentication failures**: Verify API keys and permissions
3. **Service unavailability**: Check service status and restart if needed
4. **Rate limiting**: Implement exponential backoff in your agent

This bootstrap command block provides everything needed for agents to quickly connect to the AI stack.