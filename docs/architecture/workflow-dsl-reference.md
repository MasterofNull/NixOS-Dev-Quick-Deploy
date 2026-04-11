# Workflow DSL Language Reference

**Version:** 1.0
**Schema:** [workflow-v1.yaml](../../ai-stack/workflows/schema/workflow-v1.yaml)
**Last Updated:** 2026-04-11

---

## Table of Contents

1. [Overview](#overview)
2. [Workflow Structure](#workflow-structure)
3. [Metadata](#metadata)
4. [Inputs](#inputs)
5. [Agents](#agents)
6. [Nodes](#nodes)
7. [Memory Configuration](#memory-configuration)
8. [Loop Configuration](#loop-configuration)
9. [Retry Configuration](#retry-configuration)
10. [Error Handling](#error-handling)
11. [Outputs](#outputs)
12. [Variable Substitution](#variable-substitution)
13. [Examples](#examples)
14. [Best Practices](#best-practices)

---

## Overview

The Workflow DSL is a declarative YAML-based language for defining AI task orchestration workflows. It enables:

- **Deterministic execution** - Same inputs produce same execution path
- **Multi-agent coordination** - Route tasks to specialized agents
- **Progressive memory loading** - L0-L3 memory layers for context management
- **Error resilience** - Retry logic and error handlers
- **Complex workflows** - Loops, conditionals, parallelism, composition

### Design Principles

1. **Declarative over imperative** - Describe what, not how
2. **Explicit over implicit** - No hidden state or magic behavior
3. **Safe by default** - Termination guarantees, resource limits
4. **Composable** - Workflows can call other workflows
5. **Debuggable** - Clear execution trace, error messages

---

## Workflow Structure

```yaml
name: <workflow-identifier>
version: <semantic-version>
description: <human-readable description>

inputs:
  <input-definitions>

agents:
  <agent-role-mapping>

nodes:
  - <node-definition>
  - <node-definition>
  ...

outputs:
  <output-definitions>
```

### Minimal Workflow

```yaml
name: hello-world
version: 1.0

nodes:
  - id: greet
    agent: qwen
    prompt: "Say hello to the world"
    outputs:
      - message

outputs:
  greeting: ${greet.message}
```

---

## Metadata

### `name` (required)

Unique identifier for the workflow.

**Type:** `string`
**Pattern:** `^[a-z][a-z0-9-]*$` (lowercase, alphanumeric, hyphens)
**Length:** 3-64 characters

**Examples:**
```yaml
name: feature-implementation
name: bug-fix-workflow
name: security-audit
```

### `version` (required)

Semantic version of the workflow.

**Type:** `string`
**Pattern:** `^\d+\.\d+(\.\d+)?$`

**Examples:**
```yaml
version: 1.0
version: 2.1
version: 1.0.5
```

### `description` (optional)

Human-readable description of what the workflow does.

**Type:** `string`
**Max Length:** 500 characters

**Example:**
```yaml
description: |
  Implement a new feature from specification with automated testing,
  code review, and validation before deployment.
```

---

## Inputs

Define parameters that can be passed to the workflow at runtime.

### Simple Input

```yaml
inputs:
  feature_spec: string
  max_iterations: number
  enable_tests: boolean
```

**Supported Types:**
- `string` - Text values
- `number` - Numeric values (int or float)
- `boolean` - true/false
- `object` - JSON object
- `array` - JSON array

### Input with Defaults

```yaml
inputs:
  environment:
    type: string
    default: "development"
    description: "Target deployment environment"

  run_tests:
    type: boolean
    default: true
    description: "Whether to run test suite"

  max_retries:
    type: number
    default: 3
    description: "Maximum retry attempts for flaky operations"
```

### Accessing Inputs

Use `${inputs.<name>}` syntax in prompts and conditions:

```yaml
nodes:
  - id: deploy
    agent: qwen
    prompt: "Deploy to ${inputs.environment}"
    condition: ${inputs.run_tests == true}
```

---

## Agents

Define agent roles that can be referenced in nodes.

### Agent Mapping

```yaml
agents:
  implementer: qwen
  reviewer: codex
  architect: claude
  tester: gemini
```

**Valid Agent IDs:**
- `qwen` - Fast implementation agent
- `codex` - Code review and integration specialist
- `claude` - Architecture and decision-making
- `gemini` - Testing and validation

### Using Agent Roles

```yaml
nodes:
  - id: implement
    agent: ${agents.implementer}  # Resolves to 'qwen'
    prompt: "Implement feature"

  - id: review
    agent: ${agents.reviewer}  # Resolves to 'codex'
    prompt: "Review implementation"
```

### Direct Agent Reference

You can also reference agents directly without defining roles:

```yaml
nodes:
  - id: quick-task
    agent: qwen
    prompt: "Do something quickly"
```

---

## Nodes

Nodes are the execution units of a workflow. Each node represents a task assigned to an agent.

### Basic Node

```yaml
nodes:
  - id: analyze
    agent: qwen
    prompt: "Analyze the codebase"
    outputs:
      - analysis_report
```

### Node Properties

#### `id` (required)

Unique identifier for the node within the workflow.

**Type:** `string`
**Pattern:** `^[a-z][a-z0-9-]*$`

#### `agent` (required)

Agent to execute this node.

**Type:** `string`
**Values:** `qwen`, `codex`, `claude`, `gemini`, or `${agents.<role>}`

#### `prompt` (required)

Task prompt with variable substitution.

**Type:** `string`
**Min Length:** 10 characters

**Example:**
```yaml
prompt: |
  Review the following code for security issues:
  ${previous-node.code}

  Focus on:
  - SQL injection vulnerabilities
  - XSS risks
  - Authentication bypasses
```

#### `depends_on` (optional)

List of node IDs that must complete before this node executes.

**Type:** `array` of `string`

**Example:**
```yaml
nodes:
  - id: build
    agent: qwen
    prompt: "Build the application"

  - id: test
    agent: qwen
    depends_on: [build]
    prompt: "Run tests on build artifacts"

  - id: deploy
    agent: qwen
    depends_on: [build, test]
    prompt: "Deploy to production"
```

#### `condition` (optional)

Boolean expression for conditional execution.

**Type:** `string` (expression)

**Examples:**
```yaml
# Execute only if input flag is true
condition: ${inputs.run_tests}

# Execute based on previous node output
condition: ${review.decision == 'approve'}

# Complex condition
condition: ${inputs.environment == 'production' && test.coverage >= 80}
```

#### `parallel` (optional)

Execute this node in parallel with other parallel nodes at the same dependency level.

**Type:** `boolean`
**Default:** `false`

**Example:**
```yaml
nodes:
  - id: security-scan
    agent: claude
    prompt: "Security audit"
    parallel: true

  - id: performance-scan
    agent: qwen
    prompt: "Performance analysis"
    parallel: true

  - id: quality-scan
    agent: codex
    prompt: "Code quality review"
    parallel: true

  # This runs after all parallel scans complete
  - id: aggregate
    agent: claude
    depends_on: [security-scan, performance-scan, quality-scan]
    prompt: "Combine all findings"
```

#### `outputs` (optional)

List of output variable names produced by this node.

**Type:** `array` of `string`

**Example:**
```yaml
nodes:
  - id: analyze
    agent: qwen
    prompt: "Analyze codebase"
    outputs:
      - issues_found
      - complexity_score
      - recommendations
```

#### `goto` (optional)

Node ID to jump to after this node completes (creates a loop).

**Type:** `string`

**Example:**
```yaml
nodes:
  - id: review
    agent: codex
    prompt: "Review code"
    outputs:
      - decision

  - id: revise
    agent: qwen
    depends_on: [review]
    condition: ${review.decision == 'needs_revision'}
    prompt: "Fix issues"
    goto: review  # Jump back to review
```

---

## Memory Configuration

Control which memory layers are loaded for a node's context.

```yaml
memory:
  layers: [L0, L1, L2, L3]
  topics: [string]
  max_tokens: number
  isolation: string
  diary_only: boolean
```

### `layers`

Memory layers to load.

**Type:** `array`
**Values:** `L0`, `L1`, `L2`, `L3`

**Layer Descriptions:**
- **L0** - Identity (50 tokens) - Agent role and core context
- **L1** - Critical facts (170 tokens) - Essential knowledge
- **L2** - Topic-specific (variable) - Facts filtered by topic
- **L3** - Full semantic search (heavy) - Complete search results

**Example:**
```yaml
memory:
  layers: [L0, L1, L2]  # Load identity, critical facts, and topic-specific
```

### `topics`

Topic filters for L2 memory loading.

**Type:** `array` of `string`

**Example:**
```yaml
memory:
  layers: [L0, L1, L2]
  topics: [architecture, security, authentication]
```

### `max_tokens`

Token budget for memory context.

**Type:** `integer`
**Range:** 50-10000
**Default:** 500

**Example:**
```yaml
memory:
  layers: [L0, L1, L2, L3]
  max_tokens: 1000
```

### `isolation`

Memory isolation mode.

**Type:** `string`
**Values:** `agent`, `global`
**Default:** `global`

**Example:**
```yaml
memory:
  isolation: agent  # Only load this agent's memories
```

### `diary_only`

Only load agent diary, no shared facts.

**Type:** `boolean`
**Default:** `false`

**Example:**
```yaml
memory:
  diary_only: true
```

### Complete Memory Example

```yaml
nodes:
  - id: implement-auth
    agent: qwen
    prompt: "Implement authentication system"
    memory:
      layers: [L0, L1, L2]
      topics: [authentication, security, database]
      max_tokens: 800
    outputs:
      - implementation
```

---

## Loop Configuration

Execute a node repeatedly until a termination condition is met.

```yaml
loop:
  prompt: string
  until: string
  max_iterations: number
  fresh_context: boolean
```

### `until` (required)

Termination condition expression.

**Type:** `string`

**Special Values:**
- `ALL_TASKS_COMPLETE` - Built-in condition
- Custom expressions: `${state.score >= threshold}`

### `max_iterations` (required)

Safety limit for maximum iterations.

**Type:** `integer`
**Range:** 1-100

### `prompt` (optional)

Prompt for each iteration (overrides node prompt).

**Type:** `string`

### `fresh_context` (optional)

Reset context each iteration to prevent bloat.

**Type:** `boolean`
**Default:** `false`

### Loop Example

```yaml
nodes:
  - id: refactor
    agent: qwen
    loop:
      prompt: |
        Refactor code to improve quality.
        Current score: ${state.quality_score}
        Target: ${inputs.target_score}
        Issues remaining: ${state.remaining_issues}
      until: ${state.quality_score >= inputs.target_score}
      max_iterations: 10
      fresh_context: true
    memory:
      layers: [L0, L1, L2]
      topics: [refactoring, code-quality]
    outputs:
      - refactored_code
```

---

## Retry Configuration

Automatically retry failed operations.

```yaml
retry:
  max_attempts: number
  on_failure: [string]
  backoff: string
  backoff_base: number
```

### `max_attempts`

Maximum retry attempts.

**Type:** `integer`
**Range:** 1-10
**Default:** 3

### `on_failure`

Error types that trigger retry.

**Type:** `array` of `string`

**Common Error Types:**
- `api_timeout`
- `network_error`
- `rate_limit`
- `test_failure`
- `deployment_timeout`

### `backoff`

Backoff strategy between retries.

**Type:** `string`
**Values:** `constant`, `linear`, `exponential`
**Default:** `exponential`

**Strategies:**
- **constant** - Same delay each time
- **linear** - Linearly increasing delay
- **exponential** - Exponentially increasing delay (2x each retry)

### `backoff_base`

Base backoff time in seconds.

**Type:** `number`
**Range:** 0.1+
**Default:** 1.0

**Delay Calculation:**
- constant: `backoff_base`
- linear: `backoff_base * attempt_number`
- exponential: `backoff_base * (2 ^ attempt_number)`

### Retry Example

```yaml
nodes:
  - id: deploy
    agent: qwen
    prompt: "Deploy service to production"
    retry:
      max_attempts: 5
      on_failure: [deployment_timeout, network_error]
      backoff: exponential
      backoff_base: 2
    outputs:
      - deployment_status
```

**Retry Schedule (exponential, base=2):**
- Attempt 1: immediate
- Attempt 2: after 2s
- Attempt 3: after 4s
- Attempt 4: after 8s
- Attempt 5: after 16s

---

## Error Handling

Define error handlers for graceful failure recovery.

```yaml
on_error:
  handler: string
  continue: boolean
```

### `handler`

Node ID of the error handler.

**Type:** `string`

### `continue`

Continue workflow execution after error handler.

**Type:** `boolean`
**Default:** `false`

### Error Handling Example

```yaml
nodes:
  - id: critical-operation
    agent: qwen
    prompt: "Perform critical operation"
    on_error:
      handler: rollback
      continue: false  # Stop workflow on error

  - id: rollback
    agent: qwen
    prompt: |
      Rollback failed operation:
      Error: ${critical-operation.error}
```

### Combined Retry + Error Handling

```yaml
nodes:
  - id: risky-operation
    agent: qwen
    prompt: "Perform risky operation"
    retry:
      max_attempts: 3
      on_failure: [transient_error]
    on_error:
      handler: investigate
      continue: true  # Continue after investigation

  - id: investigate
    agent: claude
    prompt: |
      Investigate failure:
      ${risky-operation.error}
```

---

## Outputs

Define workflow outputs that aggregate node results.

```yaml
outputs:
  <output-name>: ${node-id.variable}
```

### Output Syntax

**Pattern:** `${<node-id>.<output-variable>}`

### Output Examples

```yaml
nodes:
  - id: build
    outputs:
      - artifacts
      - version

  - id: test
    outputs:
      - test_results
      - coverage

outputs:
  build_artifacts: ${build.artifacts}
  build_version: ${build.version}
  test_report: ${test.test_results}
  code_coverage: ${test.coverage}
```

---

## Variable Substitution

Variables can be referenced using `${...}` syntax.

### Variable Types

#### Input Variables

```yaml
${inputs.<parameter-name>}
```

**Example:**
```yaml
prompt: "Deploy to environment: ${inputs.environment}"
```

#### Node Outputs

```yaml
${<node-id>.<output-variable>}
```

**Example:**
```yaml
prompt: "Review the code: ${implement.code}"
```

#### Agent References

```yaml
${agents.<role-name>}
```

**Example:**
```yaml
agent: ${agents.reviewer}
```

#### State Variables (in loops)

```yaml
${state.<variable-name>}
```

**Example:**
```yaml
loop:
  prompt: "Process item ${state.current_item}"
  until: ${state.remaining_count == 0}
```

### Variable Substitution in Prompts

```yaml
prompt: |
  Implement feature: ${inputs.feature_spec}

  Based on analysis:
  ${analyze.recommendations}

  Target architecture:
  ${analyze.architecture_pattern}

  Files to modify:
  ${analyze.files_list}
```

### Variable Substitution in Conditions

```yaml
condition: ${review.decision == 'approve' && test.coverage >= 80}
```

---

## Examples

### Sequential Workflow

```yaml
name: sequential-tasks
version: 1.0

inputs:
  task: string

nodes:
  - id: step1
    agent: qwen
    prompt: "Step 1: ${inputs.task}"
    outputs: [result1]

  - id: step2
    agent: qwen
    depends_on: [step1]
    prompt: "Step 2 using ${step1.result1}"
    outputs: [result2]

  - id: step3
    agent: qwen
    depends_on: [step2]
    prompt: "Final step with ${step2.result2}"
    outputs: [final_result]

outputs:
  result: ${step3.final_result}
```

### Parallel Workflow

```yaml
name: parallel-analysis
version: 1.0

nodes:
  - id: scan-a
    agent: qwen
    parallel: true
    prompt: "Scan A"
    outputs: [findings_a]

  - id: scan-b
    agent: codex
    parallel: true
    prompt: "Scan B"
    outputs: [findings_b]

  - id: scan-c
    agent: claude
    parallel: true
    prompt: "Scan C"
    outputs: [findings_c]

  - id: merge
    agent: claude
    depends_on: [scan-a, scan-b, scan-c]
    prompt: |
      Merge findings:
      A: ${scan-a.findings_a}
      B: ${scan-b.findings_b}
      C: ${scan-c.findings_c}
    outputs: [report]

outputs:
  final_report: ${merge.report}
```

### Conditional Workflow

```yaml
name: conditional-deploy
version: 1.0

inputs:
  run_tests: boolean
  environment: string

nodes:
  - id: build
    agent: qwen
    prompt: "Build application"
    outputs: [artifacts]

  - id: test
    agent: qwen
    depends_on: [build]
    condition: ${inputs.run_tests}
    prompt: "Run tests"
    outputs: [test_results]

  - id: deploy-dev
    agent: qwen
    depends_on: [build, test]
    condition: ${inputs.environment == 'dev'}
    prompt: "Deploy to dev"

  - id: deploy-prod
    agent: qwen
    depends_on: [build, test]
    condition: ${inputs.environment == 'prod'}
    prompt: "Deploy to production"
```

### Loop Workflow

```yaml
name: iterative-improvement
version: 1.0

inputs:
  target_score: number

nodes:
  - id: improve
    agent: qwen
    loop:
      prompt: |
        Improve code quality.
        Current: ${state.score}
        Target: ${inputs.target_score}
      until: ${state.score >= inputs.target_score}
      max_iterations: 10
      fresh_context: true
    outputs:
      - improved_code
```

---

## Best Practices

### 1. Use Descriptive Node IDs

**Good:**
```yaml
- id: analyze-security-vulnerabilities
- id: generate-unit-tests
- id: review-code-quality
```

**Bad:**
```yaml
- id: node1
- id: task2
- id: step3
```

### 2. Provide Clear Prompts

**Good:**
```yaml
prompt: |
  Review the implementation for:
  - Code quality and readability
  - Security vulnerabilities
  - Performance issues
  - Test coverage

  Implementation: ${implement.code}
```

**Bad:**
```yaml
prompt: "Review code"
```

### 3. Set Appropriate Memory Budgets

```yaml
# Light task - minimal memory
memory:
  layers: [L0, L1]
  max_tokens: 300

# Complex task - more memory
memory:
  layers: [L0, L1, L2]
  topics: [architecture, security]
  max_tokens: 800
```

### 4. Always Set max_iterations for Loops

**Required:**
```yaml
loop:
  until: ${condition}
  max_iterations: 20  # Safety limit
```

### 5. Use Retry for Flaky Operations

```yaml
# Network operations
retry:
  max_attempts: 5
  on_failure: [network_error, timeout]
  backoff: exponential

# Test operations
retry:
  max_attempts: 3
  on_failure: [test_flake]
  backoff: linear
```

### 6. Validate Critical Paths with Error Handlers

```yaml
- id: critical-deploy
  on_error:
    handler: rollback-deployment
    continue: false

- id: rollback-deployment
  prompt: "Rollback: ${critical-deploy.error}"
```

### 7. Use Parallel Execution for Independent Tasks

```yaml
# Good - parallel scans
- id: security-scan
  parallel: true
- id: performance-scan
  parallel: true
- id: quality-scan
  parallel: true

# Then aggregate
- id: aggregate
  depends_on: [security-scan, performance-scan, quality-scan]
```

### 8. Leverage fresh_context for Long Loops

```yaml
loop:
  max_iterations: 50
  fresh_context: true  # Prevent context bloat
```

### 9. Use Agent Roles for Flexibility

```yaml
agents:
  implementer: qwen  # Can swap to different agent
  reviewer: codex

nodes:
  - agent: ${agents.implementer}  # Uses role, not hardcoded
```

### 10. Document Complex Workflows

```yaml
description: |
  Multi-stage deployment workflow:
  1. Build and test locally
  2. Deploy to staging
  3. Run integration tests
  4. Conditional production deployment with approval
```

---

## See Also

- [Workflow DSL Design](../architecture/workflow-dsl-design.md) - Complete design specification
- [Example Workflows](../../ai-stack/workflows/examples/) - Working examples
- [JSON Schema](../../ai-stack/workflows/schema/workflow-v1.yaml) - Validation schema
