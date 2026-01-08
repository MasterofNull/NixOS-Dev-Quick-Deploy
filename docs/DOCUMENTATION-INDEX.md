# NixOS Hybrid AI Stack - Complete Documentation Index
**Last Updated**: 2025-12-22
**System Version**: 2.1.0

---

## Quick Navigation

**TLS Note:** External service URLs now go through nginx at `https://localhost:8443` (self-signed cert; prefer `--cacert ai-stack/compose/nginx/certs/localhost.crt`, use `-k` only for troubleshooting).

### 🔢 Numbered Core Docs (00-35)

- **[00-QUICK-START.md](/docs/00-QUICK-START.md)** - Primary quick start
- **[01-SYSTEM-OVERVIEW.md](/docs/01-SYSTEM-OVERVIEW.md)** - System overview
- **[02-AGENT-INTEGRATION.md](/docs/02-AGENT-INTEGRATION.md)** - Agent integration patterns
- **[03-PROGRESSIVE-DISCLOSURE.md](/docs/03-PROGRESSIVE-DISCLOSURE.md)** - Progressive disclosure guide
- **[04-CONTINUOUS-LEARNING.md](/docs/04-CONTINUOUS-LEARNING.md)** - Continuous learning
- **[05-API-REFERENCE.md](/docs/05-API-REFERENCE.md)** - API reference
- **[06-TROUBLESHOOTING.md](/docs/06-TROUBLESHOOTING.md)** - Troubleshooting
- **[07-DOCUMENTATION-INDEX.md](/docs/07-DOCUMENTATION-INDEX.md)** - This index
- **[08-SECURITY.md](/docs/08-SECURITY.md)** - Security exceptions and guidance
- **[09-DEPLOYMENT.md](/docs/09-DEPLOYMENT.md)** - AI stack deployment integration
- **[10-OPERATIONS.md](/docs/10-OPERATIONS.md)** - Local development and operations
- **[11-TOOLS.md](/docs/11-TOOLS.md)** - Available tools overview
- **[12-SKILLS-MCP.md](/docs/12-SKILLS-MCP.md)** - Skills and MCP inventory
- **[13-MCP-SERVERS.md](/docs/13-MCP-SERVERS.md)** - MCP server documentation
- **[14-PODMAN-ROOTLESS.md](/docs/14-PODMAN-ROOTLESS.md)** - Rootless Podman setup
- **[15-ARCHITECTURE.md](/docs/15-ARCHITECTURE.md)** - System architecture
- **[16-AGENT-START.md](/docs/16-AGENT-START.md)** - Agent onboarding entry point
- **[17-AGENT-REFERENCE.md](/docs/17-AGENT-REFERENCE.md)** - Agent capabilities and reference
- **[18-AGENT-SETUP.md](/docs/18-AGENT-SETUP.md)** - Agent setup and configuration
- **[19-PROGRESSIVE-DISCLOSURE-README.md](/docs/19-PROGRESSIVE-DISCLOSURE-README.md)** - Progressive disclosure quick read
- **[20-SYSTEM-USAGE.md](/docs/20-SYSTEM-USAGE.md)** - System usage guide
- **[21-HYBRID-SYSTEM.md](/docs/21-HYBRID-SYSTEM.md)** - Hybrid AI system guide
- **[22-RAG-IMPLEMENTATION.md](/docs/22-RAG-IMPLEMENTATION.md)** - RAG implementation
- **[23-AI-STACK-GUIDE.md](/docs/23-AI-STACK-GUIDE.md)** - AI stack agentic era guide
- **[24-MODEL-QUICKSTART.md](/docs/24-MODEL-QUICKSTART.md)** - Model quickstart
- **[25-MODEL-MODULAR.md](/docs/25-MODEL-MODULAR.md)** - Modular model system
- **[26-ENGINEERING-ENV.md](/docs/26-ENGINEERING-ENV.md)** - Engineering environment
- **[27-PODMAN-START.md](/docs/27-PODMAN-START.md)** - Podman AI stack start
- **[28-PODMAN-ROOTLESS.md](/docs/28-PODMAN-ROOTLESS.md)** - Rootless Podman
- **[29-DASHBOARD-GUIDE.md](/docs/29-DASHBOARD-GUIDE.md)** - Dashboard guide
- **[30-DASHBOARD-README.md](/docs/30-DASHBOARD-README.md)** - Dashboard README
- **[31-PACKAGE-GUIDE.md](/docs/31-PACKAGE-GUIDE.md)** - Package guide
- **[32-QUICK-REFERENCE.md](/docs/32-QUICK-REFERENCE.md)** - Quick reference
- **[33-QUICK-REFERENCE-CARD.md](/docs/33-QUICK-REFERENCE-CARD.md)** - Quick reference card
- **[34-RUN-FIRST.md](/docs/34-RUN-FIRST.md)** - Run-this-first checklist
- **[35-LOCAL-AI-STARTER.md](/docs/35-LOCAL-AI-STARTER.md)** - Local AI starter

### 🚀 Getting Started (Start Here!)

1. **[AI-AGENT-PROGRESSIVE-DISCLOSURE-README.md](AI-AGENT-PROGRESSIVE-DISCLOSURE-README.md)** (18 KB)
   - **Purpose**: Quick start for AI agents using progressive disclosure
   - **Audience**: AI agents (remote and local models)
   - **Contains**: Quick start, API reference, integration examples
   - **Time**: 5 minutes to understand, 10 minutes to integrate

2. **[AI-SYSTEM-USAGE-GUIDE.md](AI-SYSTEM-USAGE-GUIDE.md)** (12 KB)
   - **Purpose**: Complete usage guide for the AI system
   - **Audience**: Developers and operators
   - **Contains**: Service management, MCP usage, monitoring, RAG, troubleshooting
   - **Time**: 15 minutes

3. **[README.md](README.md)** (varies)
   - **Purpose**: Main project overview
   - **Audience**: All users
   - **Contains**: Project description, installation, quick start

---

## Progressive Disclosure System (NEW! 2025-12-22)

### Core Documentation

1. **[docs/PROGRESSIVE-DISCLOSURE-GUIDE.md](/docs/PROGRESSIVE-DISCLOSURE-GUIDE.md)** (18 KB) ⭐
   - **Purpose**: Complete progressive disclosure guide for AI agents
   - **Audience**: AI agents, developers implementing agent integrations
   - **Contains**:
     - 4 disclosure levels (basic → advanced)
     - 6 capability categories
     - Token savings strategy (87% reduction)
     - Workflow examples
     - Continuous improvement integration
     - Best practices
   - **Time**: 30 minutes to read thoroughly
   - **When to Use**: Implementing AI agent that will use the system

2. **[docs/AGENT-INTEGRATION-WORKFLOW.md](/docs/AGENT-INTEGRATION-WORKFLOW.md)** (15 KB) ⭐
   - **Purpose**: Step-by-step integration patterns
   - **Audience**: Developers
   - **Contains**:
     - Quick integration checklist
     - 4 integration patterns:
       - Pattern 1: Claude Code Agent (MCP client)
       - Pattern 2: Python Agent (direct HTTP)
       - Pattern 3: Ollama Integration
       - Pattern 4: LangChain Integration
     - Complete code examples
     - API reference card
     - Troubleshooting
   - **Time**: 20 minutes + implementation time
   - **When to Use**: Ready to integrate your agent

3. **[PROGRESSIVE-DISCLOSURE-IMPLEMENTATION.md](/docs/archive/PROGRESSIVE-DISCLOSURE-IMPLEMENTATION.md)** (17 KB)
   - **Purpose**: Technical implementation details
   - **Audience**: System administrators, developers modifying the system
   - **Contains**:
     - Files created and their purpose
     - System architecture
     - Integration steps
     - Testing procedures
     - Monitoring metrics
     - Troubleshooting
   - **Time**: 25 minutes
   - **When to Use**: Installing/customizing the progressive disclosure system

### Implementation Files

- **[ai-stack/mcp-servers/aidb/discovery_api.py](/ai-stack/mcp-servers/aidb/discovery_api.py)** (500 lines)
  - Core progressive disclosure API logic
  - `AgentDiscoveryAPI` class
  - 4 disclosure levels, 6 capability categories

- **[ai-stack/mcp-servers/aidb/discovery_endpoints.py](/ai-stack/mcp-servers/aidb/discovery_endpoints.py)** (400 lines)
  - FastAPI route integration
  - 7 discovery endpoints
  - Telemetry recording

- **[scripts/enable-progressive-disclosure.sh](/scripts/enable-progressive-disclosure.sh)** (100 lines)
  - Automated integration script
  - Backs up server.py
  - Adds discovery routes

---

## AI System Documentation

### System Overview and Testing

1. **[AI-SYSTEM-TEST-REPORT-2025-12-22.md](/docs/archive/AI-SYSTEM-TEST-REPORT-2025-12-22.md)** (16 KB)
   - **Purpose**: Comprehensive test results and validation
   - **Audience**: Developers, operators
   - **Contains**:
     - System architecture overview
     - Test results (core services 5/5 healthy)
     - Progressive disclosure feature documentation
     - Issues discovered and fixes applied
     - Recommendations
   - **Time**: 20 minutes
   - **When to Use**: Understanding system status, troubleshooting

2. **[AI-STACK-RAG-IMPLEMENTATION.md](AI-STACK-RAG-IMPLEMENTATION.md)** (12 KB)
   - **Purpose**: RAG (Retrieval-Augmented Generation) implementation details
   - **Audience**: Developers
   - **Contains**: RAG workflow, vector database usage, context retrieval
   - **Time**: 15 minutes

### Agent Reference and Setup

3. **[AI-AGENT-REFERENCE.md](AI-AGENT-REFERENCE.md)** (13 KB)
   - **Purpose**: Agent capabilities and reference
   - **Audience**: AI agents, developers
   - **Contains**: Agent capabilities, tools, skills reference
   - **Time**: 15 minutes

4. **[AI-AGENT-SETUP.md](AI-AGENT-SETUP.md)** (12 KB)
   - **Purpose**: Agent setup and configuration
   - **Audience**: Developers setting up agents
   - **Contains**: Setup instructions, configuration options
   - **Time**: 20 minutes

### Model Management

5. **[AI-MODEL-MODULAR-SYSTEM.md](AI-MODEL-MODULAR-SYSTEM.md)** (22 KB)
   - **Purpose**: Modular model system architecture
   - **Audience**: Developers, system architects
   - **Contains**: Model organization, modularity patterns
   - **Time**: 30 minutes

6. **[AI-MODEL-QUICKSTART.md](AI-MODEL-QUICKSTART.md)** (11 KB)
   - **Purpose**: Quick start for AI model deployment
   - **Audience**: Developers
   - **Contains**: Model deployment, quick commands
   - **Time**: 10 minutes

---

## Agent Guides (Numbered Series)

**Location**: [docs/agent-guides/](/docs/agent-guides/)

### Navigation Tier (00-02) - Start Here

- **[00-SYSTEM-OVERVIEW.md](/docs/agent-guides/00-SYSTEM-OVERVIEW.md)**
  - Core concepts: Qdrant, llama.cpp, RAG, continuous learning
  - System architecture
  - **Time**: 10 minutes

- **[01-QUICK-START.md](/docs/agent-guides/01-QUICK-START.md)**
  - 5-minute setup guide
  - Essential commands
  - **Time**: 5 minutes

- **[02-SERVICE-STATUS.md](/docs/agent-guides/02-SERVICE-STATUS.md)**
  - Service health checks
  - Troubleshooting
  - **Time**: 5 minutes

### Infrastructure Tier (10-12)

- **[10-NIXOS-CONFIG.md](/docs/agent-guides/10-NIXOS-CONFIG.md)** - NixOS configuration details
- **[11-CONTAINER-MGMT.md](/docs/agent-guides/11-CONTAINER-MGMT.md)** - Podman management
- **[12-DEBUGGING.md](/docs/agent-guides/12-DEBUGGING.md)** - Debugging tools

### AI Stack Tier (20-22)

- **[20-LOCAL-LLM-USAGE.md](/docs/agent-guides/20-LOCAL-LLM-USAGE.md)** - Local model query patterns
- **[21-RAG-CONTEXT.md](/docs/agent-guides/21-RAG-CONTEXT.md)** - RAG and context retrieval
- **[22-CONTINUOUS-LEARNING.md](/docs/agent-guides/22-CONTINUOUS-LEARNING.md)** - Learning from interactions

### Database Tier (30-32)

- **[30-QDRANT-OPERATIONS.md](/docs/agent-guides/30-QDRANT-OPERATIONS.md)** - Vector database operations
- **[31-POSTGRES-OPS.md](/docs/agent-guides/31-POSTGRES-OPS.md)** - SQL database management
- **[32-ERROR-LOGGING.md](/docs/agent-guides/32-ERROR-LOGGING.md)** - Error tracking and analysis

### Advanced Tier (40-44)

- **[40-HYBRID-WORKFLOW.md](/docs/agent-guides/40-HYBRID-WORKFLOW.md)** - Local vs remote LLM routing
- **[41-VALUE-SCORING.md](/docs/agent-guides/41-VALUE-SCORING.md)** - 5-factor value scoring algorithm
- **[42-PATTERN-EXTRACTION.md](/docs/agent-guides/42-PATTERN-EXTRACTION.md)** - Extract reusable patterns
- **[43-FEDERATED-DEPLOYMENT.md](/docs/agent-guides/43-FEDERATED-DEPLOYMENT.md)** - Multi-system deployment
- **[44-FEDERATION-AUTOMATION.md](/docs/agent-guides/44-FEDERATION-AUTOMATION.md)** - Automated federation

### Comprehensive Tier (90)

- **[90-COMPREHENSIVE-ANALYSIS.md](/docs/agent-guides/90-COMPREHENSIVE-ANALYSIS.md)** - Deep system analysis

---

## Additional Documentation

### Agent Onboarding

1. **[agent-onboarding-package-v2.0.0/README.md](agent-onboarding-package-v2.0.0/README.md)**
   - System setup guide (mirrors root README)

2. **[agent-onboarding-package-v2.0.0/AGENTS.md](agent-onboarding-package-v2.0.0/AGENTS.md)**
   - Professional AI agent training guide
   - Code quality standards
   - Development workflow best practices
   - Anti-patterns and pitfalls

### Other Guides

3. **[docs/AGENT-AGNOSTIC-TOOLING-PLAN.md](/docs/AGENT-AGNOSTIC-TOOLING-PLAN.md)** (16 KB)
   - Agent-agnostic tooling architecture
   - Tool design patterns

4. **[docs/development.md](/docs/development.md)** (4 KB)
   - Local development setup
   - Makefile workflow
   - Pre-commit hooks

5. **[docs/SECURITY-EXCEPTIONS.md](/docs/SECURITY-EXCEPTIONS.md)** (3 KB)
   - Vulnerability triage
   - Temporary exceptions

---

## Documentation by Use Case

### "I'm a new AI agent, how do I use this system?"

**Read in order**:
1. [AI-AGENT-PROGRESSIVE-DISCLOSURE-README.md](AI-AGENT-PROGRESSIVE-DISCLOSURE-README.md) - 5 min
2. [docs/PROGRESSIVE-DISCLOSURE-GUIDE.md](/docs/PROGRESSIVE-DISCLOSURE-GUIDE.md) - 15 min
3. [docs/agent-guides/00-SYSTEM-OVERVIEW.md](/docs/agent-guides/00-SYSTEM-OVERVIEW.md) - 10 min

**Then try**:
```bash
curl --cacert ai-stack/compose/nginx/certs/localhost.crt https://localhost:8443/aidb/discovery/quickstart \
  -H "X-API-Key: $(cat ai-stack/compose/secrets/stack_api_key)"
```

**Total time**: 30 minutes

---

### "I want to integrate my agent (Claude, Python, Ollama, etc.)"

**Read in order**:
1. [AI-AGENT-PROGRESSIVE-DISCLOSURE-README.md](AI-AGENT-PROGRESSIVE-DISCLOSURE-README.md) - Quick start
2. [docs/AGENT-INTEGRATION-WORKFLOW.md](/docs/AGENT-INTEGRATION-WORKFLOW.md) - Choose your pattern
3. [docs/PROGRESSIVE-DISCLOSURE-GUIDE.md](/docs/PROGRESSIVE-DISCLOSURE-GUIDE.md) - Detailed usage

**Total time**: 45 minutes + implementation

---

### "I need to install/configure the system"

**Read in order**:
1. [README.md](README.md) - Main setup
2. [AI-SYSTEM-USAGE-GUIDE.md](AI-SYSTEM-USAGE-GUIDE.md) - Usage reference
3. [PROGRESSIVE-DISCLOSURE-IMPLEMENTATION.md](/docs/archive/PROGRESSIVE-DISCLOSURE-IMPLEMENTATION.md) - Enable progressive disclosure

**Total time**: 40 minutes + installation

---

### "I want to understand how RAG and learning work"

**Read in order**:
1. [docs/agent-guides/21-RAG-CONTEXT.md](/docs/agent-guides/21-RAG-CONTEXT.md)
2. [docs/agent-guides/22-CONTINUOUS-LEARNING.md](/docs/agent-guides/22-CONTINUOUS-LEARNING.md)
3. [docs/agent-guides/41-VALUE-SCORING.md](/docs/agent-guides/41-VALUE-SCORING.md)
4. [AI-STACK-RAG-IMPLEMENTATION.md](AI-STACK-RAG-IMPLEMENTATION.md)

**Total time**: 50 minutes

---

### "I need to troubleshoot issues"

**Check these**:
1. [AI-SYSTEM-USAGE-GUIDE.md](AI-SYSTEM-USAGE-GUIDE.md) - Troubleshooting section
2. [AI-SYSTEM-TEST-REPORT-2025-12-22.md](/docs/archive/AI-SYSTEM-TEST-REPORT-2025-12-22.md) - Known issues
3. [docs/agent-guides/02-SERVICE-STATUS.md](/docs/agent-guides/02-SERVICE-STATUS.md) - Service health
4. [docs/agent-guides/12-DEBUGGING.md](/docs/agent-guides/12-DEBUGGING.md) - Debug tools
5. [PROGRESSIVE-DISCLOSURE-IMPLEMENTATION.md](/docs/archive/PROGRESSIVE-DISCLOSURE-IMPLEMENTATION.md) - Troubleshooting section

**Total time**: 30 minutes

---

## API Quick Reference

### OpenAPI Specs

- AIDB OpenAPI UI: `https://localhost:8443/aidb/docs`
- Embeddings: `docs/api/embeddings-openapi.yaml`
- Hybrid Coordinator: `docs/api/hybrid-openapi.yaml`
- NixOS Docs: `docs/api/nixos-docs-openapi.yaml`

### Discovery API (Progressive Disclosure)

```bash
# System info (50 tokens)
curl --cacert ai-stack/compose/nginx/certs/localhost.crt https://localhost:8443/aidb/discovery/info \
  -H "X-API-Key: $(cat ai-stack/compose/secrets/stack_api_key)"

# Quickstart guide (150 tokens)
curl --cacert ai-stack/compose/nginx/certs/localhost.crt https://localhost:8443/aidb/discovery/quickstart \
  -H "X-API-Key: $(cat ai-stack/compose/secrets/stack_api_key)"

# List capabilities (200 tokens)
curl --cacert ai-stack/compose/nginx/certs/localhost.crt https://localhost:8443/aidb/discovery/capabilities?level=standard \
  -H "X-API-Key: $(cat ai-stack/compose/secrets/stack_api_key)"

# Get capability details (500 tokens)
curl --cacert ai-stack/compose/nginx/certs/localhost.crt https://localhost:8443/aidb/discovery/capabilities/search_documents \
  -H "X-API-Key: $(cat ai-stack/compose/secrets/stack_api_key)"

# Documentation index
curl --cacert ai-stack/compose/nginx/certs/localhost.crt https://localhost:8443/aidb/discovery/docs \
  -H "X-API-Key: $(cat ai-stack/compose/secrets/stack_api_key)"

# Contact points
curl --cacert ai-stack/compose/nginx/certs/localhost.crt https://localhost:8443/aidb/discovery/contact-points \
  -H "X-API-Key: $(cat ai-stack/compose/secrets/stack_api_key)"
```

### Core Services

```bash
# AIDB MCP Server
curl --cacert ai-stack/compose/nginx/certs/localhost.crt https://localhost:8443/aidb/health \
  -H "X-API-Key: $(cat ai-stack/compose/secrets/stack_api_key)"
curl --cacert ai-stack/compose/nginx/certs/localhost.crt https://localhost:8443/aidb/documents?search=query \
  -H "X-API-Key: $(cat ai-stack/compose/secrets/stack_api_key)"

# Hybrid Coordinator
curl --cacert ai-stack/compose/nginx/certs/localhost.crt https://localhost:8443/hybrid/health \
  -H "X-API-Key: $(cat ai-stack/compose/secrets/stack_api_key)"
curl --cacert ai-stack/compose/nginx/certs/localhost.crt -X POST https://localhost:8443/hybrid/query \
  -H "X-API-Key: $(cat ai-stack/compose/secrets/stack_api_key)" \
  -d '{"query": "..."}'

# Qdrant Vector DB
curl --cacert ai-stack/compose/nginx/certs/localhost.crt https://localhost:8443/qdrant/healthz \
  -H "X-API-Key: $(cat ai-stack/compose/secrets/stack_api_key)"
curl --cacert ai-stack/compose/nginx/certs/localhost.crt https://localhost:8443/qdrant/collections \
  -H "X-API-Key: $(cat ai-stack/compose/secrets/stack_api_key)"

# llama.cpp Local LLM
curl http://localhost:8080/health
curl http://localhost:8080/v1/models
```

### Metrics and Monitoring

```bash
# AI effectiveness metrics
bash scripts/collect-ai-metrics.sh
cat ~/.local/share/nixos-system-dashboard/ai_metrics.json | jq .effectiveness

# Service health
curl --cacert ai-stack/compose/nginx/certs/localhost.crt https://localhost:8443/aidb/health \
  -H "X-API-Key: $(cat ai-stack/compose/secrets/stack_api_key)"
curl --cacert ai-stack/compose/nginx/certs/localhost.crt https://localhost:8443/hybrid/health \
  -H "X-API-Key: $(cat ai-stack/compose/secrets/stack_api_key)"
```

---

## Documentation Statistics

| Category | Files | Total Size | Avg Size |
|----------|-------|------------|----------|
| Progressive Disclosure | 7 | ~80 KB | 11 KB |
| AI System Guides | 8 | ~110 KB | 14 KB |
| Agent Guides (00-90) | 18 | ~150 KB | 8 KB |
| Implementation | 2 | ~900 lines | 450 lines |
| Scripts | 1 | 100 lines | - |
| **Total** | **36+** | **~340 KB** | **9 KB** |

---

## Contributing to Documentation

### Documentation Standards

1. **File Naming**:
   - Use `UPPERCASE-WITH-DASHES.md` for root-level docs
   - Use `numbered-lowercase.md` for agent guides
   - Be descriptive: `PROGRESSIVE-DISCLOSURE-GUIDE.md` not `PD-GUIDE.md`

2. **Structure**:
   - Always include Table of Contents
   - Use `---` separators between major sections
   - Include "Last Updated" date
   - Add "Related Docs" section at end

3. **Code Examples**:
   - Always test code examples before documenting
   - Include full commands (not partial)
   - Show expected output
   - Add error handling examples

4. **Audience**:
   - Specify target audience at top of doc
   - Write for that audience's knowledge level
   - Link to prerequisites

### Adding New Documentation

1. Create the document following standards above
2. Add entry to this index
3. Link from related documents
4. Test all examples
5. Submit for review

---

## Version History

| Date | Version | Changes |
|------|---------|---------|
| 2025-12-22 | 1.0.0 | Initial documentation index created |
| 2025-12-22 | 1.0.0 | Progressive disclosure system added |
| 2025-12-22 | 1.0.0 | AI system test report completed |

---

## Support

For help:
1. Check this index to find relevant documentation
2. Search within specific guides using Ctrl+F
3. Review troubleshooting sections
4. Check service health: `curl --cacert ai-stack/compose/nginx/certs/localhost.crt https://localhost:8443/aidb/health`
5. View logs: `podman logs local-ai-aidb`

---

**Last Updated**: 2025-12-22
**Maintained By**: System Administrators
**Total Documentation**: 340+ KB across 36+ files
