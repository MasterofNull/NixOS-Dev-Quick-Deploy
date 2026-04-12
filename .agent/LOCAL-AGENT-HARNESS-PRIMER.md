# Local Agent AI Harness Primer

**Purpose**: This document provides the locally hosted AI agent with complete knowledge of the AI harness infrastructure, tools, and usage patterns.

**Read this first** when starting any session.

---

## Quick Reference

### Service Endpoints (All Running Locally)

| Service                | URL                     | Purpose                               |
| ---------------------- | ----------------------- | ------------------------------------- |
| **llama-cpp**          | `http://127.0.0.1:8080` | Local LLM (Gemma 4 E4B)               |
| **hybrid-coordinator** | `http://127.0.0.1:8003` | Workflow orchestration, hints, memory |
| **AIDB**               | `http://127.0.0.1:8002` | RAG knowledge base, tool registry     |
| **embedding-server**   | `http://127.0.0.1:8081` | Embeddings for semantic search        |

### Health Check Command

```bash
# Quick status check
curl -s http://127.0.0.1:8003/health | jq
curl -s http://127.0.0.1:8002/health | jq
curl -s http://127.0.0.1:8080/health | jq
```

---

## Available CLI Tools

### Primary Harness CLI: `scripts/ai/aqd`

```bash
# List all available workflows
scripts/ai/aqd workflows list

# Get hints for a task
scripts/ai/aq-hints --query "how to implement X"

# Session bootstrap
scripts/ai/aq-session-zero

# Knowledge base search
scripts/ai/aq-hints --query "your question"
```

### Workflow Commands

```bash
# Read-only session primer
scripts/ai/aqd workflows primer --target . --objective "understand codebase"

# Brownfield planning (for existing codebases)
scripts/ai/aqd workflows brownfield --target . --objective "implement feature X"

# Initialize new project
scripts/ai/aqd workflows project-init --target <dir> --name <name> --goal <goal>
```

### Local Orchestrator (NEW)

```bash
# Check all service status
scripts/ai/local-orchestrator --status

# Interactive mode
scripts/ai/local-orchestrator

# Single prompt with full harness context
scripts/ai/local-orchestrator "your prompt here"

# Create implementation plan
scripts/ai/local-orchestrator --plan "your objective"
```

---

## How to Use the Harness

### Step 1: Always Start with Context

Before doing any task, gather context:

```bash
# Get workflow hints
scripts/ai/aq-hints --query "what you're trying to do"

# Or use the hybrid-coordinator API directly
curl -s "http://127.0.0.1:8003/hints?q=your+query" | jq
```

### Step 2: Search the Knowledge Base

```bash
# Search AIDB for relevant information
curl -X POST http://127.0.0.1:8002/search \
  -H "Content-Type: application/json" \
  -d '{"query": "your search query", "limit": 5}' | jq
```

### Step 3: Use Memory for Continuity

```bash
# Store a fact/decision
curl -X POST http://127.0.0.1:8003/memory/store \
  -H "Content-Type: application/json" \
  -d '{"content": "Important fact to remember", "agent_id": "continue", "memory_type": "semantic"}'

# Recall relevant memories
curl -X POST http://127.0.0.1:8003/memory/recall \
  -H "Content-Type: application/json" \
  -d '{"query": "what did we decide about X", "agent_id": "continue", "limit": 5}' | jq
```

### Step 4: Create Workflow Plans

```bash
# Generate a phased plan
curl -X POST http://127.0.0.1:8003/workflow/plan \
  -H "Content-Type: application/json" \
  -d '{"query": "implement user authentication"}' | jq
```

---

## Tool Patterns (Copy-Paste Ready)

### Pattern 1: Get Hints Before Any Task

```bash
run_terminal_command: scripts/ai/aq-hints --query "your task description" --compact
```

### Pattern 2: Search Codebase Context

```bash
run_terminal_command: curl -s -X POST http://127.0.0.1:8003/query \
  -H "Content-Type: application/json" \
  -d '{"query": "search terms", "mode": "auto", "limit": 5}' | jq '.results[]?.content'
```

### Pattern 3: Store Session Memory

```bash
run_terminal_command: curl -s -X POST http://127.0.0.1:8003/memory/store \
  -H "Content-Type: application/json" \
  -d '{"content": "We decided to use approach X because Y", "agent_id": "continue", "memory_type": "procedural"}'
```

### Pattern 4: Check AI Stack Health

```bash
run_terminal_command: scripts/ai/local-orchestrator --status
```

### Pattern 5: Run QA Checks

```bash
run_terminal_command: scripts/ai/aq-qa 0 --json
```

### Pattern 6: Git Commit After Task Completion (MANDATORY)

```bash
# Stage files explicitly
run_terminal_command: git add <specific-files>

# Review what will be committed
run_terminal_command: git status --short && git diff --staged --stat

# Commit with conventional format
run_terminal_command: git commit -m "$(cat <<'EOF'
feat(scope): brief description

Detailed explanation if needed.

Co-Authored-By: Continue Local <noreply@continue.dev>
EOF
)"

# Verify commit
run_terminal_command: git log -1 --oneline --stat
```

**IMPORTANT:**
- **Uncommitted work = Incomplete task**
- Always commit completed work before moving to next task
- Use conventional commit format: `type(scope): description`
- Include `Co-Authored-By: Continue Local <noreply@continue.dev>` trailer
- Never use `git add .` or `git add -A` - stage specific files only

---

## Directory Reference

```
scripts/ai/                     # All AI tooling CLI scripts
├── aqd                         # Main harness CLI (workflows, skills, policies)
├── aq-hints                    # Get contextual hints
├── aq-session-zero             # Session bootstrap
├── aq-qa                       # QA and health checks
├── local-orchestrator          # Primary orchestrator CLI
├── mcp-bridge-hybrid.py        # MCP stdio bridge for Continue.dev
├── ralph-orchestrator.sh       # Task submission to Ralph
└── delegate-to-claude          # Delegate to Claude API

ai-stack/                       # AI stack modules
├── local-orchestrator/         # Local orchestrator Python module
├── autonomous-orchestrator/    # Autonomous task orchestration
├── aidb/                       # Knowledge base server
└── mcp-servers/                # MCP server implementations
```

---

## MCP Tools Available via Hybrid-Coordinator

When using the MCP bridge, these tools are available:

| Tool                 | Purpose                     | When to Use                         |
| -------------------- | --------------------------- | ----------------------------------- |
| `hybrid_search`      | Semantic + keyword search   | Finding code, docs, patterns        |
| `get_hints`          | Workflow hints              | Before starting any task            |
| `query_aidb`         | Direct knowledge base query | Specific documentation lookup       |
| `recall_memory`      | Retrieve past decisions     | Maintaining context across sessions |
| `store_memory`       | Persist facts/decisions     | After important decisions           |
| `workflow_plan`      | Create phased plans         | Planning implementations            |
| `workflow_run_start` | Execute guarded workflow    | Running approved plans              |

---

## Git Workflow Discipline (CRITICAL)

**MANDATORY RULE: All completed work must be committed to git before moving to the next task.**

### When to Commit

Commit immediately after:
- ✅ Completing a feature or fix
- ✅ All tests pass
- ✅ Validation checks pass
- ✅ Code is working as expected

### Commit Format (Required)

```bash
git commit -m "$(cat <<'EOF'
type(scope): brief description (under 70 chars)

Optional detailed explanation:
- What changed
- Why it changed
- Important implementation notes

Co-Authored-By: Continue Local <noreply@continue.dev>
EOF
)"
```

### Commit Types

| Type | When to Use | Example |
|------|-------------|---------|
| `feat` | New feature or enhancement | `feat(auth): add JWT token validation` |
| `fix` | Bug fix | `fix(api): handle null responses correctly` |
| `docs` | Documentation only | `docs(readme): update installation steps` |
| `test` | Add or fix tests | `test(parser): add edge case coverage` |
| `chore` | Maintenance, deps, config | `chore(deps): update python dependencies` |
| `refactor` | Code restructuring, no behavior change | `refactor(utils): simplify error handling` |

### Git Safety Rules

- ❌ **NEVER** use `git add .` or `git add -A` - Always stage specific files
- ❌ **NEVER** skip the Co-Authored-By trailer
- ❌ **NEVER** move to next task with uncommitted work
- ✅ **ALWAYS** run `git status --short` before committing
- ✅ **ALWAYS** review `git diff --staged` before committing
- ✅ **ALWAYS** verify commit with `git log -1 --stat` after committing

### Complete Workflow Loop

```
1. Read task → 2. Gather context → 3. Implement → 4. Test → 5. Commit → 6. Next task
                                                              ↑
                                          MANDATORY STEP - DO NOT SKIP
```

**Uncommitted changes = Incomplete task**

---

## Common Workflows

### Starting a New Session

1. Run `scripts/ai/aq-session-zero` to bootstrap
2. Read `.agent/PROJECT-PRD.md` for project context
3. Check `scripts/ai/aq-hints --query "session start"` for relevant hints
4. Use memory recall to check previous decisions

### Implementing a Feature

**CRITICAL: Every completed task MUST be committed to git before moving to next task.**

1. **Gather Context**: `scripts/ai/aq-hints --query "implement X"`
2. **Search for Patterns**: Use `hybrid_search` or grep to understand existing code
3. **Create Plan**: `scripts/ai/local-orchestrator --plan "implement X"`
4. **Execute Incrementally**:
   - Write code following existing patterns
   - Add inline comments ONLY where logic isn't self-evident
   - Store important decisions in memory
5. **Validate**:
   - Run tests: `pytest <test-file>` or relevant test command
   - Check syntax: `python3 -m py_compile <file>` or `bash -n <script>`
   - Lint repo structure: `scripts/governance/repo-structure-lint.sh --staged`
6. **Commit to Git** (MANDATORY):
   ```bash
   # Stage specific files (prefer explicit over 'git add .')
   git add <file1> <file2> <file3>

   # Check what will be committed
   git status --short
   git diff --staged

   # Commit with conventional format
   git commit -m "$(cat <<'EOF'
   type(scope): brief description

   Optional detailed explanation of:
   - What changed and why
   - Any important implementation notes
   - Related issues or decisions

   Co-Authored-By: Continue Local <noreply@continue.dev>
   EOF
   )"
   ```

   **Commit Type Prefixes:**
   - `feat`: New feature or enhancement
   - `fix`: Bug fix
   - `docs`: Documentation only
   - `chore`: Maintenance (deps, config)
   - `test`: Test additions/fixes
   - `refactor`: Code restructuring

7. **Verify Commit**: `git log -1 --stat` to confirm commit is complete

### Debugging an Issue

1. **Check Logs**: `journalctl -u <service> --since "5 min ago"`
2. **Search for Error Patterns**: Query AIDB for similar issues
3. **Recall Memory**: Check for previous similar issues
4. **Run QA Tools**: `scripts/ai/aq-qa 0`
5. **Implement Fix**: Make necessary code changes
6. **Validate Fix**: Run tests, verify issue is resolved
7. **Commit Fix** (MANDATORY):
   ```bash
   git add <fixed-files>
   git commit -m "$(cat <<'EOF'
   fix(component): brief description of fix

   Explanation of:
   - What was broken
   - Root cause
   - How the fix works

   Co-Authored-By: Continue Local <noreply@continue.dev>
   EOF
   )"
   ```

---

## Important Files to Know

| File                     | Purpose                    |
| ------------------------ | -------------------------- |
| `CLAUDE.md`              | Primary agent instructions |
| `AGENTS.md`              | Compact policy baseline    |
| `.agent/PROJECT-PRD.md`  | Project requirements       |
| `.agent/GLOBAL-RULES.md` | Guardrails and constraints |
| `docs/AGENTS.md`         | Full policy documentation  |

---

## Integration with Continue.dev

The MCP bridge is configured to work with Continue.dev:

```json
{
  "mcpServers": {
    "hybrid-coordinator": {
      "command": "python3",
      "args": ["scripts/ai/mcp-bridge-hybrid.py"],
      "cwd": "/home/hyperd/Documents/NixOS-Dev-Quick-Deploy"
    }
  }
}
```

This exposes all harness tools as MCP tools within your Continue.dev session.

---

## Quick Diagnostic Commands

```bash
# Check all services (correct port mapping)
declare -A SVC_PORTS=(
  ["llama-cpp"]=8080
  ["hybrid-coordinator"]=8003
  ["aidb"]=8002
)
for svc in "${!SVC_PORTS[@]}"; do
  port="${SVC_PORTS[$svc]}"
  status=$(curl -sf "http://127.0.0.1:${port}/health" > /dev/null 2>&1 && echo "OK" || echo "DOWN")
  echo "$svc (port ${port}): $status"
done

# See current model
curl -s http://127.0.0.1:8080/v1/models | jq '.data[0].id'

# Check harness capabilities
curl -s http://127.0.0.1:8003/health | jq '.ai_harness'

# Check agent pool status (Phase 20.1)
curl -s http://127.0.0.1:8003/agent-status | jq '{pool_status, total_agents, available_agents}'
```

---

*This primer should be read at the start of every session to ensure full harness awareness.*
