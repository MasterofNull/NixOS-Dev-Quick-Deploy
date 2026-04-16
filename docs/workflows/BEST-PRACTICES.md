# Workflow Best Practices Guide

**Phase 2 Workflow Engine - Production Patterns**
**Version:** 1.0
**Last Updated:** 2026-04-16

---

## Core Principles

### 1. **Single Responsibility Per Node**

Each workflow node should do one thing well.

**✅ Good:**
```yaml
- id: validate_input
  prompt: Validate user input data

- id: process_data
  prompt: Process validated data

- id: store_results
  prompt: Store processed results
```

**❌ Bad:**
```yaml
- id: do_everything
  prompt: Validate input, process data, store results, send notifications, and update cache
```

### 2. **Explicit Dependencies**

Always declare dependencies explicitly, even if they seem obvious.

**✅ Good:**
```yaml
- id: build
  depends_on: [test, lint]
```

**❌ Bad:**
```yaml
# Implicit dependency - execution order unclear
- id: build
```

### 3. **Defensive Programming**

Always validate inputs and handle edge cases.

**✅ Good:**
```yaml
inputs:
  file_path:
    type: string
    description: Path to file (must exist)

nodes:
  - id: validate
    prompt: |
      Verify file exists at ${inputs.file_path}
      Check file is readable
      Validate file format
```

### 4. **Progressive Complexity**

Start simple, add complexity only when needed.

**Workflow Evolution:**
```
v1: Linear workflow (analyze → implement → test)
v2: Add conditional review
v3: Add loop for iterations
v4: Add retry logic
```

---

## Agent Selection

### Choosing the Right Agent

| Task Type | Best Agent | Why |
|-----------|------------|-----|
| Implementation, coding | qwen | Fast, focused on code generation |
| Review, analysis | codex | Thorough, good at finding issues |
| Architecture, planning | claude | High-level thinking, design |
| Local/embedded tasks | local | No API costs, good for simple tasks |

### Agent Switching Pattern

Use different agents for different phases:

```yaml
agents:
  implementer: qwen      # Fast implementation
  reviewer: codex        # Thorough review
  architect: claude      # High-level design

nodes:
  - id: design
    agent: ${agents.architect}

  - id: implement
    agent: ${agents.implementer}
    depends_on: [design]

  - id: review
    agent: ${agents.reviewer}
    depends_on: [implement]
```

---

## Memory Management

### Load Only What You Need

**✅ Good:**
```yaml
memory:
  layers: [L0, L1]              # Recent context
  topics: [authentication]       # Focused
  max_tokens: 300               # Conservative
```

**❌ Bad:**
```yaml
memory:
  layers: [L0, L1, L2, L3]      # Everything
  max_tokens: 5000              # Excessive
```

### Memory Layer Strategy

| Layer | Use When | Typical Topics |
|-------|----------|----------------|
| L0 | Always | Project overview, architecture |
| L1 | Current work | Recent changes, active features |
| L2 | Historical context | Past decisions, patterns |
| L3 | Deep knowledge | Rarely needed, use sparingly |

---

## Error Handling

### Retry Logic for Flaky Operations

```yaml
- id: external_api_call
  retry:
    max_attempts: 3
    on_failure: [network_error, timeout]
  prompt: Call external service
```

### Graceful Degradation

```yaml
- id: optional_optimization
  condition: ${inputs.optimize == true}
  prompt: Apply optional optimization
  # Won't break workflow if this fails
```

### Error Recovery Patterns

**Pattern 1: Retry with backoff**
```yaml
- id: flaky_operation
  retry:
    max_attempts: 3
  prompt: Operation that might fail
```

**Pattern 2: Alternative path**
```yaml
- id: primary_method
  prompt: Try primary approach

- id: fallback_method
  condition: ${primary_method.status == 'failed'}
  prompt: Use fallback approach
```

**Pattern 3: Skip and continue**
```yaml
- id: optional_step
  condition: ${should_run}
  prompt: Optional operation
  # Workflow continues regardless
```

---

## Performance Optimization

### 1. Minimize Memory Loading

Only load memory when it adds value:

```yaml
# Simple tasks don't need memory
- id: format_code
  prompt: Format code with prettier
  # No memory needed

# Complex tasks benefit from memory
- id: refactor_architecture
  memory:
    layers: [L0, L1, L2]
    topics: [architecture, patterns]
  prompt: Refactor module structure
```

### 2. Use Parallel Execution

Leverage parallel node execution:

```yaml
nodes:
  # These can run in parallel (no dependencies)
  - id: lint
    prompt: Run linter

  - id: typecheck
    prompt: Run type checker

  - id: security_scan
    prompt: Run security scanner

  # This waits for all parallel tasks
  - id: report
    depends_on: [lint, typecheck, security_scan]
    prompt: Generate combined report
```

### 3. Limit Loop Iterations

Always set reasonable max_iterations:

```yaml
- id: iterate
  loop:
    max_iterations: 10    # Prevent infinite loops
    until: CONDITION_MET
  prompt: Process items
```

### 4. Fresh Context Control

Control when to reload context:

```yaml
- id: long_loop
  loop:
    fresh_context: false  # Reuse context for speed
    max_iterations: 20
```

---

## Testing Workflows

### 1. Start with Validation

Always validate before running:

```bash
aq-workflow validate my-workflow.yaml
```

### 2. Test with Minimal Inputs

Start with simple, minimal input data:

```bash
# First test
aq-workflow run my-workflow.yaml '{
  "required_param": "minimal test value"
}'
```

### 3. Test Conditional Paths

Test both branches of conditions:

```bash
# Test true path
aq-workflow run my-workflow.yaml '{"enable_feature": true}'

# Test false path
aq-workflow run my-workflow.yaml '{"enable_feature": false}'
```

### 4. Test Error Conditions

Verify error handling works:

```bash
# Test with invalid input
aq-workflow run my-workflow.yaml '{"invalid": "data"}'
```

---

## Security Best Practices

### 1. Never Hardcode Secrets

**❌ Never:**
```yaml
prompt: |
  Connect to database with password: hardcoded_secret_123
```

**✅ Instead:**
```yaml
inputs:
  db_password:
    type: string
    description: Database password (from environment)

prompt: |
  Connect to database with password from secure source
```

### 2. Validate External Inputs

Always validate data from users or external sources:

```yaml
- id: validate_input
  prompt: |
    Validate user input:
    - Check for SQL injection patterns
    - Verify data types
    - Sanitize special characters
```

### 3. Limit Resource Usage

Set reasonable limits:

```yaml
- id: resource_intensive
  loop:
    max_iterations: 100     # Prevent resource exhaustion
  prompt: Process items
```

---

## Maintainability

### 1. Use Meaningful Names

**✅ Good:**
```yaml
- id: validate_user_authentication
- id: fetch_customer_orders
- id: calculate_shipping_cost
```

**❌ Bad:**
```yaml
- id: step1
- id: node2
- id: task_a
```

### 2. Document Complex Logic

Add comments for non-obvious patterns:

```yaml
# Special handling for legacy data format
# TODO: Remove after migration completes (Q3 2026)
- id: transform_legacy_data
  condition: ${inputs.data_format == 'v1'}
  prompt: Transform v1 format to v2
```

### 3. Version Your Workflows

Track workflow versions:

```yaml
name: user-onboarding
version: 2.1.0              # Semantic versioning
description: |
  User onboarding workflow
  v2.1.0: Added email verification step
  v2.0.0: Complete redesign with new agents
  v1.x: Legacy implementation
```

### 4. Keep Workflows DRY

Extract common patterns to sub-workflows:

```yaml
# main-workflow.yaml
- id: common_setup
  sub_workflow: common/setup.yaml
```

---

## Debugging Tips

### 1. Check Intermediate Outputs

Review node outputs to understand workflow state:

```bash
aq-workflow status <execution-id>
```

### 2. Use Descriptive Prompts

Prompts should be clear about what you're debugging:

```yaml
- id: debug_issue
  prompt: |
    DEBUG MODE: Analyze why authentication is failing

    Current state: ${previous_node.output}
    Expected behavior: User should be authenticated
    Actual behavior: Authentication fails with 401
```

### 3. Add Validation Nodes

Insert validation checks:

```yaml
- id: validate_state
  prompt: |
    Verify workflow state is correct:
    - Check all required variables are set
    - Validate data integrity
    - Confirm prerequisites met
```

### 4. Review Logs

Check coordinator logs for errors:

```bash
journalctl -u ai-hybrid-coordinator -f
```

---

## Common Patterns

### Pattern: Review-Revise Loop

```yaml
- id: implement
  prompt: Implement feature

- id: review
  depends_on: [implement]
  prompt: Review implementation

- id: revise
  condition: ${review.needs_changes}
  depends_on: [review]
  prompt: Address review feedback
  goto: review  # Loop back
```

### Pattern: Progressive Enhancement

```yaml
- id: basic_implementation
  prompt: Basic implementation

- id: add_tests
  depends_on: [basic_implementation]
  condition: ${inputs.include_tests}
  prompt: Add tests

- id: add_docs
  depends_on: [basic_implementation]
  condition: ${inputs.include_docs}
  prompt: Add documentation

- id: optimize
  depends_on: [basic_implementation, add_tests]
  condition: ${inputs.optimize}
  prompt: Optimize performance
```

### Pattern: Multi-Stage Validation

```yaml
- id: syntax_check
  prompt: Check syntax

- id: semantic_check
  depends_on: [syntax_check]
  prompt: Check semantics

- id: integration_check
  depends_on: [semantic_check]
  prompt: Check integration

- id: final_validation
  depends_on: [integration_check]
  prompt: Final validation
```

---

## Performance Checklist

Before deploying a workflow to production:

- [ ] Validated syntax and semantics
- [ ] Tested with realistic inputs
- [ ] Set reasonable max_iterations
- [ ] Added retry logic for flaky operations
- [ ] Minimized memory loading
- [ ] Used appropriate agents for each task
- [ ] Added error handling
- [ ] Documented complex logic
- [ ] Tested conditional branches
- [ ] Verified security practices

---

## Next Steps

- Review [User Guide](USER-GUIDE.md) for basics
- Browse [Template Catalog](TEMPLATE-CATALOG.md) for examples

---

**Remember:** Start simple, validate often, and iterate based on results.
