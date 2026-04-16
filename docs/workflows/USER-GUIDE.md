# YAML Workflow System - User Guide

**Phase 2 Workflow Engine Documentation**
**Version:** 1.0
**Last Updated:** 2026-04-16

---

## Table of Contents

1. [Introduction](#introduction)
2. [Quick Start](#quick-start)
3. [CLI Usage](#cli-usage)
4. [Workflow Structure](#workflow-structure)
5. [Writing Workflows](#writing-workflows)
6. [Using Templates](#using-templates)
7. [Best Practices](#best-practices)
8. [Troubleshooting](#troubleshooting)

---

## Introduction

The YAML Workflow System enables declarative, multi-agent workflow orchestration for complex software development tasks. Workflows are defined in YAML files and executed through the hybrid coordinator.

### Key Features

- **Declarative Syntax**: Define workflows in readable YAML
- **Multi-Agent Orchestration**: Route tasks to specialized agents (qwen, codex, claude)
- **Memory Integration**: Load contextual knowledge (L0-L3 layers)
- **Conditional Execution**: Dynamic workflow paths based on conditions
- **Loop Support**: Iterative task execution until completion
- **Error Handling**: Automatic retries and error recovery
- **State Management**: Track execution state across workflow steps

---

## Quick Start

### 1. List Available Templates

```bash
aq-workflow list
```

### 2. Create a Workflow from Template

```bash
aq-workflow create bug-fix my-bugfix.yaml
```

### 3. Validate Your Workflow

```bash
aq-workflow validate my-bugfix.yaml
```

### 4. Execute the Workflow

```bash
aq-workflow run my-bugfix.yaml '{
  "bug_description": "Login button does not respond",
  "error_details": "No console errors",
  "add_regression_test": true
}'
```

### 5. Check Execution Status

```bash
aq-workflow status <execution-id>
```

---

## CLI Usage

### Command Reference

#### `aq-workflow list`

List all available workflow templates and examples.

**Output:**
- Template workflows (production-ready)
- Example workflows (learning/testing)

#### `aq-workflow validate <file>`

Validate workflow YAML file for syntax and semantic correctness.

**Example:**
```bash
aq-workflow validate my-workflow.yaml
```

**Validates:**
- YAML syntax
- Schema compliance
- Dependency graph
- Variable references
- Agent configuration
- Memory settings

#### `aq-workflow run <file> [inputs]`

Execute a workflow with optional inputs.

**Syntax:**
```bash
aq-workflow run <workflow-file> '<json-inputs>' [async]
```

**Examples:**
```bash
# Synchronous execution (waits for completion)
aq-workflow run bug-fix.yaml '{"bug_description":"Login fails"}'

# Asynchronous execution (returns immediately)
aq-workflow run feature-implementation.yaml '{"feature_spec":"Add OAuth"}' true
```

#### `aq-workflow status <execution-id>`

Check the status of a running or completed workflow.

**Output:**
- Execution ID
- Workflow name
- Current status (running, completed, failed, cancelled)
- Start time
- Completion time (if finished)
- Error details (if failed)

#### `aq-workflow cancel <execution-id>`

Cancel a running workflow execution.

**Note:** Not all workflows can be cancelled mid-execution. The system will attempt graceful cancellation.

#### `aq-workflow history [workflow-name]`

View execution history for all workflows or a specific workflow.

**Examples:**
```bash
# All executions
aq-workflow history

# Filter by workflow name
aq-workflow history bug-fix
```

#### `aq-workflow create <template> <output>`

Create a new workflow file from a template.

**Example:**
```bash
aq-workflow create code-review my-review.yaml
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `COORDINATOR_URL` | `http://127.0.0.1:8003` | Coordinator HTTP API URL |
| `WORKFLOWS_DIR` | `ai-stack/workflows` | Workflows directory |
| `TEMPLATES_DIR` | `ai-stack/workflows/templates` | Templates directory |

---

## Workflow Structure

### Basic Workflow Anatomy

```yaml
name: workflow-name            # Unique workflow identifier
version: 1.0                   # Semantic version
description: What this workflow does

inputs:                        # Input parameters
  param1:
    type: string
    description: Parameter description
    default: optional-default

agents:                        # Agent assignments
  role1: qwen
  role2: codex

nodes:                         # Workflow steps
  - id: step1                  # Unique step ID
    agent: ${agents.role1}     # Agent to use
    prompt: |                  # Task prompt
      Do something...
    outputs:                   # Output variables
      - result

outputs:                       # Final outputs
  final_result: ${step1.result}
```

### Node Types

#### 1. Sequential Node

```yaml
- id: analyze
  agent: qwen
  prompt: Analyze the code
  outputs:
    - analysis
```

#### 2. Conditional Node

```yaml
- id: deploy
  agent: qwen
  condition: ${test.status == 'passed'}
  depends_on: [test]
  prompt: Deploy to production
```

#### 3. Loop Node

```yaml
- id: iterate
  agent: qwen
  loop:
    prompt: Process next item
    until: ALL_ITEMS_COMPLETE
    max_iterations: 10
  outputs:
    - results
```

#### 4. Retry-Enabled Node

```yaml
- id: test
  agent: qwen
  retry:
    max_attempts: 3
    on_failure: [test_failure]
  prompt: Run tests
```

---

## Writing Workflows

### Step 1: Define Inputs

Start by defining what inputs your workflow needs:

```yaml
inputs:
  feature_spec:
    type: string
    description: Feature specification to implement

  tests_required:
    type: boolean
    default: true
    description: Whether to create tests
```

**Input Types:**
- `string`: Text input
- `number`: Numeric input
- `boolean`: True/false flag
- `array`: List of values
- `object`: Structured data

### Step 2: Assign Agents

Map roles to specific agents:

```yaml
agents:
  implementer: qwen      # Fast, coding-focused
  reviewer: codex        # Thorough, review-focused
  architect: claude      # High-level, design-focused
```

**Available Agents:**
- `qwen`: Fast implementation, coding, testing
- `codex`: Code review, analysis, validation
- `claude`: Architecture, planning, security
- `local`: Local LLM (embedded-assist)

### Step 3: Design Node Graph

Create the workflow steps with dependencies:

```yaml
nodes:
  # Step 1: No dependencies
  - id: analyze
    agent: ${agents.implementer}
    prompt: Analyze requirements
    outputs:
      - requirements

  # Step 2: Depends on step 1
  - id: implement
    agent: ${agents.implementer}
    depends_on: [analyze]
    prompt: Implement based on ${analyze.requirements}
    outputs:
      - code

  # Step 3: Depends on step 2
  - id: review
    agent: ${agents.reviewer}
    depends_on: [implement]
    prompt: Review ${implement.code}
    outputs:
      - feedback
```

### Step 4: Add Memory Integration

Load relevant context for each node:

```yaml
- id: implement
  agent: qwen
  memory:
    layers: [L0, L1, L2]           # Memory layers to load
    topics: [architecture, patterns]  # Filter by topics
    max_tokens: 500                 # Token limit
  prompt: Implement feature
```

**Memory Layers:**
- `L0`: Project overview, architecture
- `L1`: Recent context, current work
- `L2`: Historical patterns, decisions
- `L3`: Long-term knowledge

### Step 5: Handle Errors

Add retry logic and error handling:

```yaml
- id: test
  agent: qwen
  retry:
    max_attempts: 3
    on_failure: [test_failure]
  prompt: Run tests
  outputs:
    - test_results
```

### Step 6: Define Outputs

Specify what the workflow returns:

```yaml
outputs:
  implementation: ${implement.code}
  test_results: ${test.test_results}
  review_feedback: ${review.feedback}
```

---

## Using Templates

### Available Templates

| Template | Use Case | Typical Duration |
|----------|----------|------------------|
| `feature-implementation` | Add new features | 30-60 min |
| `bug-fix` | Fix bugs with tests | 15-30 min |
| `code-review` | Review code changes | 10-20 min |
| `refactoring` | Safe code refactoring | 20-40 min |
| `testing` | Create test suites | 15-30 min |
| `documentation` | Generate docs | 10-20 min |
| `performance-optimization` | Optimize performance | 30-60 min |
| `security-audit` | Security review | 20-40 min |
| `dependency-update` | Update dependencies | 15-30 min |
| `ci-cd-setup` | Setup CI/CD pipelines | 30-60 min |

### Customizing Templates

1. **Create from template:**
   ```bash
   aq-workflow create feature-implementation my-feature.yaml
   ```

2. **Edit inputs:** Modify the `inputs` section to match your needs

3. **Adjust agents:** Change agent assignments if needed

4. **Add/remove nodes:** Customize the workflow steps

5. **Validate:** Always validate before running
   ```bash
   aq-workflow validate my-feature.yaml
   ```

---

## Best Practices

### 1. Start Small

Begin with simple, linear workflows before adding complexity:

```yaml
# Good: Simple and clear
nodes:
  - id: analyze
    prompt: Analyze code
  - id: fix
    depends_on: [analyze]
    prompt: Fix issues
  - id: test
    depends_on: [fix]
    prompt: Run tests
```

### 2. Use Descriptive IDs

Node IDs should clearly indicate their purpose:

```yaml
# Good
- id: validate_user_input
- id: fetch_user_data
- id: generate_report

# Bad
- id: step1
- id: node2
- id: task_a
```

### 3. Keep Prompts Focused

Each node should have a single, clear responsibility:

```yaml
# Good: One focused task
- id: implement_auth
  prompt: Implement user authentication using JWT tokens

# Bad: Multiple responsibilities
- id: do_everything
  prompt: Implement auth, add tests, update docs, and deploy
```

### 4. Use Memory Wisely

Only load memory layers you actually need:

```yaml
# Good: Specific layers and topics
memory:
  layers: [L0, L1]
  topics: [authentication, security]
  max_tokens: 300

# Bad: Loading everything
memory:
  layers: [L0, L1, L2, L3]
  max_tokens: 10000
```

### 5. Handle Failures Gracefully

Add retry logic for operations that might fail:

```yaml
- id: api_call
  retry:
    max_attempts: 3
    on_failure: [network_error, timeout]
  prompt: Call external API
```

### 6. Document Your Workflows

Add clear descriptions and comments:

```yaml
name: custom-deployment
version: 1.0
description: |
  Deploy application to staging with health checks.
  Automatically rolls back on failure.

# Each input should have a clear description
inputs:
  deployment_target:
    type: string
    description: Target environment (staging or production)
```

### 7. Test Incrementally

Test workflows in stages:

1. Validate syntax: `aq-workflow validate`
2. Run with minimal inputs
3. Check intermediate outputs
4. Add complexity gradually

---

## Troubleshooting

### Validation Errors

**Error:** `ValidationError: undefined variable 'foo'`

**Solution:** Ensure all variable references exist:
```yaml
# Wrong
prompt: Use ${nonexistent.variable}

# Correct
prompt: Use ${step1.output_variable}
```

**Error:** `Circular dependency detected`

**Solution:** Check your `depends_on` declarations:
```yaml
# Wrong - circular!
- id: a
  depends_on: [b]
- id: b
  depends_on: [a]

# Correct
- id: a
- id: b
  depends_on: [a]
```

### Execution Failures

**Problem:** Workflow stuck in "running" state

**Solution:**
1. Check coordinator logs: `journalctl -u ai-hybrid-coordinator -f`
2. Verify agent availability
3. Check for timeout issues
4. Cancel and restart: `aq-workflow cancel <id>`

**Problem:** Node fails repeatedly

**Solution:**
1. Check the prompt clarity - is it specific enough?
2. Verify input data is valid
3. Check memory context is relevant
4. Review agent selection (wrong agent for task?)

### CLI Issues

**Problem:** `coordinator not accessible`

**Solution:**
```bash
# Check coordinator status
systemctl status ai-hybrid-coordinator

# Check URL configuration
echo $COORDINATOR_URL

# Test connectivity
curl http://127.0.0.1:8003/yaml-workflow/stats
```

**Problem:** `Import error` when validating

**Solution:**
Ensure Python path is correct:
```bash
export WORKFLOWS_DIR=/full/path/to/ai-stack/workflows
```

---

## Next Steps

- Browse [Template Catalog](TEMPLATE-CATALOG.md) for all templates
- Read [Best Practices Guide](BEST-PRACTICES.md) for advanced patterns

---

**Need Help?**
- Check logs: `journalctl -u ai-hybrid-coordinator`
- Run validation: `aq-workflow validate <file>`
- Review examples: `ls ai-stack/workflows/examples/`
