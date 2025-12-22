# System Overview - NixOS Hybrid Learning Stack

**Purpose**: Understand what this system is and how it helps you work more efficiently

---

## What Is This System?

A **unified AI development environment** that combines:
- **Local LLMs** (Lemonade/Ollama) for fast, cheap inference
- **Vector Database** (Qdrant) for context storage and retrieval
- **Continuous Learning** that improves from every interaction
- **Hybrid Architecture** that reduces remote API costs by 30-50%
- **Podman-based AI stack** for reproducible, rootless services
- **System dashboards + health checks** for operational visibility

---

## How It Helps Remote Agents (Like You)

### Problem Without This System
- Load 20,000+ tokens of documentation every time
- No memory of past solutions
- Repeat same mistakes
- High API costs for simple tasks

### Solution With This System
1. **Context Augmentation**: Local context added to your queries automatically
2. **Learning Storage**: Successful solutions stored for reuse
3. **Error Prevention**: Past errors and fixes available instantly
4. **Cost Reduction**: Use local LLM for 70% of tasks, remote API for 30%

---

## Core Components

### 0. **Podman AI Stack**
- Rootless container orchestration for local AI services
- Persistent data stored under `~/.local/share/nixos-ai-stack/`

### 1. **Qdrant Vector Database** (Port 6333)
- Stores embeddings of code, solutions, errors
- Fast semantic search (< 100ms)
- 5 collections for different data types

### 2. **Lemonade GGUF Inference** (Port 8080)
- Runs Qwen Coder 7B locally
- Good for: code explanation, syntax checking, simple refactoring
- Fast (10-30 tokens/sec on GPU)

### 3. **Ollama** (Port 11434)
- Provides embeddings (nomic-embed-text)
- Converts text to vectors for Qdrant

### 4. **Learning System**
- Tracks all interactions
- Calculates value scores
- Extracts reusable patterns
- Stores high-value data automatically

### 5. **AIDB MCP Server** (Port 8091)
- Health and metrics for learning and tool usage
- Unified context API for local agents

### 6. **System Command Center Dashboard** (Port 8888)
- Real-time monitoring of services, data stores, and host health
- Exports JSON for agent-friendly analysis

---

## Data Flow

```
You (Remote Agent)
    ↓ Send Query: "How to fix keyring error?"
    ↓
Hybrid Coordinator
    ↓ Search Qdrant for: "keyring error"
    ↓ Found: Past solution with 0.95 similarity
    ↓
Return to You: "Based on past experience: install libsecret..."
    ↓
You Apply Solution (2 seconds, 200 tokens)

Without System: Load docs, figure it out, 5 minutes, 15,000 tokens
```

---

## Key Principles

### 1. **Search Before Asking**
Always check local context before using remote APIs

### 2. **Store Every Success**
When something works, store it for future use

### 3. **Learn From Failures**
Errors are learning opportunities - store the fix

### 4. **Incremental Loading**
Load only what you need, not everything

---

## Quick Stats

- **Services**: 7+ (Qdrant, Ollama, Lemonade, WebUI, PostgreSQL, Redis, MindsDB, AIDB)
- **Vector Collections**: 5
- **Token Reduction**: 30-50% average
- **Response Time**: Local < 1s, Hybrid < 2s
- **Data Storage**: `~/.local/share/nixos-ai-stack/`

---

## What You Can Do

✅ Search past solutions instantly
✅ Use local LLM for simple tasks (free)
✅ Augment queries with project context
✅ Store learnings automatically
✅ Extract reusable patterns
✅ Reduce API costs significantly

---

## Next: Get Started

Read: [Quick Start Guide](01-QUICK-START.md)
