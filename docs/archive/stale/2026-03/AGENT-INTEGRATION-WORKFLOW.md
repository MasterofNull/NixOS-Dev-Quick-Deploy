# AI Agent Integration Workflow
**Version**: 1.0.0
**Date**: 2025-12-22
**Purpose**: Step-by-step guide for integrating AI agents with the local system

---

## Quick Integration Checklist

### For Remote Models (Claude, GPT-4, Gemini, etc.)

- [ ] **Step 1**: Test system health (`GET /health`)
- [ ] **Step 2**: Discover system info (`GET /discovery/info`)
- [ ] **Step 3**: Get quickstart guide (`GET /discovery/quickstart`)
- [ ] **Step 4**: List capabilities (`GET /discovery/capabilities?level=standard`)
- [ ] **Step 5**: Try a capability (e.g., `GET /documents?search=test`)
- [ ] **Step 6**: Record interaction (`POST /interactions/record`)

### For Local Models (llama.cpp, Ollama, LM Studio, etc.)

- [ ] **Step 1**: Test hybrid coordinator (`GET http://localhost:8092/health`)
- [ ] **Step 2**: Send test query (`POST /query`)
- [ ] **Step 3**: Monitor routing decision (check response for `routing_decision`)
- [ ] **Step 4**: Review token savings (check `estimated_tokens_saved`)

---

## Integration Patterns

### Pattern 1: Claude Code Agent (MCP Client)

**Scenario**: Claude Code agent wants to use local system as MCP server

**Configuration** (add to MCP settings):
```json
{
  "mcpServers": {
    "nixos-ai-stack": {
      "command": "curl",
      "args": [
        "-X", "GET",
        "http://localhost:8091/discovery/info"
      ],
      "env": {
        "AIDB_URL": "http://localhost:8091",
        "HYBRID_URL": "http://localhost:8092"
      }
    }
  }
}
```

**Usage in Claude Code**:
```python
# Claude Code can now call local capabilities
from mcp import Client

client = Client("nixos-ai-stack")

# Discover capabilities
capabilities = await client.call_tool("list_capabilities", {
    "level": "standard"
})

# Search knowledge base
results = await client.call_tool("search_documents", {
    "search": "NixOS configuration example",
    "limit": 5
})

# Execute skill
review = await client.call_tool("execute_skill", {
    "skill_name": "code_review",
    "parameters": {"file_path": "/path/to/file.py"}
})
```

---

### Pattern 2: Python Agent (Direct HTTP)

**Scenario**: Custom Python agent using the system

```python
#!/usr/bin/env python3
"""Example Python agent integration"""

import requests
from typing import Dict, Any, List

class LocalAIAgent:
    def __init__(self, base_url: str = "http://localhost:8091"):
        self.base_url = base_url
        self.hybrid_url = "http://localhost:8092"
        self.api_key = None  # Set if using authenticated features

    def discover_system(self) -> Dict[str, Any]:
        """Step 1: Discover system capabilities"""
        response = requests.get(f"{self.base_url}/discovery/info")
        return response.json()

    def get_quickstart(self) -> Dict[str, Any]:
        """Step 2: Get quickstart guide"""
        response = requests.get(f"{self.base_url}/discovery/quickstart")
        return response.json()

    def list_capabilities(
        self,
        level: str = "standard",
        category: str = None
    ) -> List[Dict[str, Any]]:
        """Step 3: List available capabilities"""
        params = {"level": level}
        if category:
            params["category"] = category

        response = requests.get(
            f"{self.base_url}/discovery/capabilities",
            params=params
        )
        return response.json()["capabilities"]

    def search_knowledge(
        self,
        query: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Search local knowledge base"""
        response = requests.get(
            f"{self.base_url}/documents",
            params={"search": query, "limit": limit}
        )
        return response.json()["results"]

    def query_hybrid(
        self,
        query: str,
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Query via hybrid coordinator (smart routing)"""
        payload = {
            "query": query,
            "context": context or {}
        }
        response = requests.post(
            f"{self.hybrid_url}/query",
            json=payload
        )
        result = response.json()

        # Log routing decision
        print(f"Routed to: {result.get('routing_decision', 'unknown')}")
        print(f"Tokens saved: {result.get('tokens_saved', 0)}")

        return result

    def record_interaction(
        self,
        query: str,
        response: str,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Record interaction for continuous learning"""
        payload = {
            "query": query,
            "response": response,
            "metadata": metadata or {}
        }
        result = requests.post(
            f"{self.base_url}/interactions/record",
            json=payload
        )
        return result.json()

    def get_metrics(self) -> Dict[str, Any]:
        """Get effectiveness metrics"""
        response = requests.get(f"{self.base_url}/metrics")
        return response.json()


# Example usage
if __name__ == "__main__":
    agent = LocalAIAgent()

    # Step 1: Discover system
    info = agent.discover_system()
    print(f"Connected to: {info['system']} v{info['version']}")

    # Step 2: List capabilities
    capabilities = agent.list_capabilities(level="standard", category="knowledge")
    print(f"Found {len(capabilities)} knowledge capabilities")

    # Step 3: Search knowledge base
    results = agent.search_knowledge("NixOS configuration example")
    if results:
        print(f"Found {len(results)} relevant documents")
        print(f"Top result: {results[0]['title']}")

    # Step 4: Query with hybrid routing
    answer = agent.query_hybrid(
        query="How do I enable Docker in NixOS?",
        context={"agent": "python-example"}
    )
    print(f"Answer: {answer.get('response', '')[:100]}...")

    # Step 5: Record interaction for learning
    agent.record_interaction(
        query="How do I enable Docker in NixOS?",
        response=answer.get('response', ''),
        metadata={
            "complexity": 0.5,
            "reusability": 0.9,
            "confirmed": True
        }
    )

    # Step 6: Check effectiveness
    metrics = agent.get_metrics()
    print(f"Effectiveness score: {metrics['effectiveness']['overall_score']}/100")
```

---

### Pattern 3: Ollama Integration

**Scenario**: Use Ollama models with local system context

```python
#!/usr/bin/env python3
"""Ollama + Local AI Stack integration"""

import requests
import ollama

class OllamaLocalAgent:
    def __init__(self):
        self.hybrid_url = "http://localhost:8092"
        self.aidb_url = "http://localhost:8091"
        self.ollama_client = ollama.Client()

    def query_with_context(
        self,
        query: str,
        model: str = "llama3.2:3b"
    ) -> str:
        """Query Ollama with context from local knowledge base"""

        # Step 1: Get context from knowledge base
        context_results = requests.get(
            f"{self.aidb_url}/documents",
            params={"search": query, "limit": 3}
        ).json()["results"]

        # Step 2: Build augmented prompt
        context_text = "\n\n".join([
            f"Context {i+1}: {r['content']}"
            for i, r in enumerate(context_results)
        ])

        augmented_prompt = f"""Based on the following context from the knowledge base:

{context_text}

Answer this question: {query}"""

        # Step 3: Query Ollama
        response = self.ollama_client.chat(
            model=model,
            messages=[{"role": "user", "content": augmented_prompt}]
        )

        answer = response["message"]["content"]

        # Step 4: Record interaction
        requests.post(
            f"{self.aidb_url}/interactions/record",
            json={
                "query": query,
                "response": answer,
                "metadata": {
                    "model": model,
                    "context_sources": len(context_results),
                    "routing": "local"
                }
            }
        )

        return answer


# Example usage
agent = OllamaLocalAgent()
answer = agent.query_with_context(
    "How do I configure GNOME in NixOS?",
    model="llama3.2:3b"
)
print(answer)
```

---

### Pattern 4: LangChain Integration

**Scenario**: Use LangChain with local system as retriever

```python
from langchain.llms import Ollama
from langchain.embeddings import SentenceTransformerEmbeddings
from langchain.vectorstores import Qdrant
from langchain.chains import RetrievalQA
from qdrant_client import QdrantClient

class LangChainLocalAgent:
    def __init__(self):
        # Local LLM
        self.llm = Ollama(
            base_url="http://localhost:8080",
            model="qwen2.5-coder-7b-instruct"
        )

        # Local embeddings
        self.embeddings = SentenceTransformerEmbeddings(
            model_name="all-MiniLM-L6-v2"
        )

        # Local vector store
        self.qdrant_client = QdrantClient(url="http://localhost:6333")
        self.vectorstore = Qdrant(
            client=self.qdrant_client,
            collection_name="codebase-context",
            embeddings=self.embeddings
        )

        # RAG chain
        self.qa_chain = RetrievalQA.from_chain_type(
            llm=self.llm,
            chain_type="stuff",
            retriever=self.vectorstore.as_retriever(search_kwargs={"k": 3})
        )

    def query(self, question: str) -> str:
        """Query with RAG (100% local, 100% free)"""
        return self.qa_chain.run(question)


# Example
agent = LangChainLocalAgent()
answer = agent.query("How do I enable Docker in NixOS?")
print(answer)
```

---

## API Reference Card for Agents

### Essential Endpoints

| Endpoint | Method | Auth | Purpose | Cost |
|----------|--------|------|---------|------|
| `/discovery/info` | GET | No | System info | 50 tokens |
| `/discovery/quickstart` | GET | No | Quickstart guide | 150 tokens |
| `/discovery/capabilities` | GET | No* | List capabilities | 200 tokens |
| `/health` | GET | No | Service health | 20 tokens |
| `/documents` | GET | No | Search knowledge | 100 tokens |
| `/query` (8092) | POST | No | Hybrid query | Variable |
| `/interactions/record` | POST | No | Record learning | 50 tokens |
| `/metrics` | GET | No | Effectiveness | 100 tokens |
| `/skills` | GET | No | List skills | 100 tokens |
| `/tools/execute` | POST | Yes | Execute tool | Variable |

*Levels `detailed` and `advanced` require API key

### Response Formats

All endpoints return JSON:
```json
{
  "status": "success",  // or "error"
  "data": {},           // Response data
  "metadata": {         // Optional metadata
    "tokens_used": 123,
    "routing_decision": "local",
    "timestamp": "2025-12-22T12:00:00Z"
  }
}
```

### Error Handling

```python
try:
    response = requests.get("http://localhost:8091/discovery/info")
    response.raise_for_status()
    data = response.json()
except requests.exceptions.ConnectionError:
    print("System not available. Start services: podman-compose up -d")
except requests.exceptions.HTTPError as e:
    if e.response.status_code == 403:
        print("Authentication required. Provide X-API-Key header")
    elif e.response.status_code == 429:
        print("Rate limit exceeded. Wait before retrying")
    else:
        print(f"Error: {e}")
```

---

## Monitoring Integration Success

### Metrics to Track

1. **Token Savings**
   ```bash
   # Check token savings
   curl http://localhost:8091/metrics | jq .effectiveness.estimated_tokens_saved
   ```

2. **Local Query Percentage**
   ```bash
   # Target: 70%+
   curl http://localhost:8091/metrics | jq .effectiveness.local_query_percentage
   ```

3. **Effectiveness Score**
   ```bash
   # Target: 80+
   bash scripts/collect-ai-metrics.sh
   cat ~/.local/share/nixos-system-dashboard/ai_metrics.json | jq .effectiveness.overall_score
   ```

### Dashboard Integration

```python
# Continuous monitoring
import time

def monitor_agent_effectiveness():
    while True:
        metrics = requests.get("http://localhost:8091/metrics").json()

        print(f"""
        Effectiveness Score: {metrics['effectiveness']['overall_score']}/100
        Total Events: {metrics['effectiveness']['total_events_processed']}
        Local Queries: {metrics['effectiveness']['local_query_percentage']}%
        Tokens Saved: {metrics['effectiveness']['estimated_tokens_saved']:,}
        """)

        time.sleep(60)  # Update every minute
```

---

## Troubleshooting Integration Issues

### Issue: Cannot Connect to Services

```bash
# Check if services are running
podman ps

# Expected output: 7 containers (qdrant, llama-cpp, postgres, redis, aidb, hybrid-coordinator, open-webui)

# If not running:
cd ai-stack/compose
podman-compose up -d
```

### Issue: Authentication Errors

```python
# Set API key in headers
headers = {"X-API-Key": "YOUR_API_KEY_HERE"}
response = requests.get(
    "http://localhost:8091/discovery/capabilities?level=detailed",
    headers=headers
)
```

### Issue: Low Effectiveness Score

```bash
# Diagnosis
bash scripts/collect-ai-metrics.sh
cat ~/.local/share/nixos-system-dashboard/ai_metrics.json | jq .effectiveness

# Solutions:
# 1. Low usage → Use the system more
# 2. Low efficiency → Add more documents to knowledge base
# 3. Low knowledge → Import your codebase/docs
```

### Issue: Slow Responses

```bash
# Check service health
curl http://localhost:8091/health
curl http://localhost:8092/health
curl http://localhost:6333/healthz
curl http://localhost:8080/health

# Check logs
podman logs local-ai-aidb
podman logs local-ai-hybrid-coordinator
```

---

## Next Steps

1. **Choose Your Integration Pattern**:
   - Remote model (Claude, GPT-4) → Pattern 1 or 2
   - Local model (Ollama, LM Studio) → Pattern 3
   - LangChain workflow → Pattern 4

2. **Test Integration**:
   - Follow the quick integration checklist
   - Monitor effectiveness metrics
   - Adjust based on results

3. **Optimize**:
   - Aim for 70%+ local queries
   - Build up knowledge base (10k+ vectors)
   - Track token savings

4. **Scale**:
   - Add custom skills
   - Fine-tune local models
   - Integrate with CI/CD

---

**Document Version**: 1.0.0
**Last Updated**: 2025-12-22
**Related Docs**:
- [Progressive Disclosure Guide](PROGRESSIVE-DISCLOSURE-GUIDE.md)
- [AI System Usage Guide](../AI-SYSTEM-USAGE-GUIDE.md)
- [Agent Onboarding Package](../agent-onboarding-package-v2.0.0/)
