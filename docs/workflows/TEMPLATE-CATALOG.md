# Workflow Template Catalog

**Phase 2 Workflow Engine - Production Templates**
**Version:** 1.0
**Last Updated:** 2026-04-16

---

## Overview

This catalog contains 10 production-ready workflow templates for common software development patterns. Each template is battle-tested, well-documented, and ready to use.

---

## Template Index

1. [Feature Implementation](#1-feature-implementation)
2. [Bug Fix](#2-bug-fix)
3. [Code Review](#3-code-review)
4. [Refactoring](#4-refactoring)
5. [Testing](#5-testing)
6. [Documentation](#6-documentation)
7. [Performance Optimization](#7-performance-optimization)
8. [Security Audit](#8-security-audit)
9. [Dependency Update](#9-dependency-update)
10. [CI/CD Setup](#10-cicd-setup)

---

## 1. Feature Implementation

**File:** `ai-stack/workflows/examples/feature-implementation.yaml`

### Description

Implement a new feature from specification with comprehensive testing and code review.

### Use Cases

- Adding new user-facing features
- Implementing API endpoints
- Creating new components/modules
- Feature enhancements

### Inputs

| Input | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `feature_spec` | string | ✓ | - | Feature specification or description |
| `tests_required` | boolean | ✗ | true | Whether to create tests |
| `review_required` | boolean | ✗ | true | Whether code review is needed |

### Workflow Steps

1. **Analyze**: Break down feature spec into tasks
2. **Implement**: Iteratively implement tasks
3. **Test**: Create comprehensive tests (conditional)
4. **Review**: Code review by reviewer agent (conditional)
5. **Revise**: Address review feedback (loop if needed)
6. **Validate**: Final validation checks

### Agents Used

- `implementer`: qwen (fast implementation)
- `reviewer`: codex (thorough review)

### Memory Integration

- Layers: L0, L1, L2
- Topics: architecture, patterns, conventions

### Example Usage

```bash
aq-workflow run feature-implementation.yaml '{
  "feature_spec": "Add user authentication with JWT tokens",
  "tests_required": true,
  "review_required": true
}'
```

### Expected Duration

30-60 minutes depending on feature complexity

---

## 2. Bug Fix

**File:** `ai-stack/workflows/templates/bug-fix.yaml`

### Description

Diagnose, fix, and validate bug resolution with optional regression testing.

### Use Cases

- Fixing reported bugs
- Addressing edge cases
- Resolving error conditions
- Production hotfixes

### Inputs

| Input | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `bug_description` | string | ✓ | - | Description of the bug |
| `error_details` | string | ✗ | "" | Error messages or stack traces |
| `add_regression_test` | boolean | ✗ | true | Create regression test |

### Workflow Steps

1. **Investigate**: Root cause analysis and reproduction
2. **Fix**: Develop targeted fix
3. **Test**: Create regression test (conditional)
4. **Verify**: Validate fix works correctly
5. **Review**: Code review
6. **Revise**: Address feedback (loop if needed)

### Agents Used

- `investigator`: qwen (debugging)
- `fixer`: qwen (implementation)
- `reviewer`: codex (validation)

### Memory Integration

- Layers: L0, L1, L2
- Topics: bugs, debugging, architecture

### Example Usage

```bash
aq-workflow run bug-fix.yaml '{
  "bug_description": "Login button unresponsive on mobile",
  "error_details": "TypeError: Cannot read property click",
  "add_regression_test": true
}'
```

### Expected Duration

15-30 minutes per bug

---

## 3. Code Review

**File:** `ai-stack/workflows/templates/code-review.yaml`

### Description

Comprehensive automated code review with quality, security, and performance checks.

### Use Cases

- Pull request reviews
- Pre-merge quality gates
- Security audits
- Performance analysis

### Inputs

| Input | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `files_changed` | array | ✓ | - | List of files to review |
| `pr_description` | string | ✗ | "" | Pull request description |
| `review_depth` | string | ✗ | standard | quick, standard, or thorough |

### Workflow Steps

1. **Automated Checks**: Linting, formatting, complexity
2. **Quality Review**: Code quality and maintainability
3. **Security Review**: Security vulnerability scan
4. **Performance Analysis**: Performance implications (conditional)
5. **Synthesize**: Comprehensive review summary

### Agents Used

- `reviewer`: codex (code quality)
- `security_checker`: codex (security)
- `perf_analyzer`: qwen (performance)

### Memory Integration

- Layers: L0, L1, L2
- Topics: patterns, conventions, best_practices, security

### Example Usage

```bash
aq-workflow run code-review.yaml '{
  "files_changed": ["src/auth.ts", "src/middleware/jwt.ts"],
  "pr_description": "Add JWT authentication middleware",
  "review_depth": "thorough"
}'
```

### Expected Duration

10-20 minutes (quick), 20-30 minutes (thorough)

---

## 4. Refactoring

**File:** `ai-stack/workflows/templates/refactoring.yaml`

### Description

Safe code refactoring with test preservation and metrics tracking.

### Use Cases

- Improving code structure
- Reducing technical debt
- Simplifying complex code
- Improving maintainability

### Inputs

| Input | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `target_code` | string | ✓ | - | Code or component to refactor |
| `refactoring_goal` | string | ✓ | - | Goal (readability, complexity, etc.) |
| `preserve_tests` | boolean | ✗ | true | Ensure tests still pass |

### Workflow Steps

1. **Analyze**: Current state and metrics
2. **Plan**: Create refactoring strategy
3. **Refactor**: Execute in small, safe steps
4. **Validate**: Ensure tests pass, functionality preserved
5. **Compare**: Before/after metrics
6. **Revert**: Rollback if goals not met (conditional)

### Agents Used

- `analyzer`: qwen (metrics analysis)
- `refactorer`: qwen (implementation)
- `validator`: codex (validation)

### Memory Integration

- Layers: L0, L1, L2
- Topics: architecture, patterns, refactoring

### Example Usage

```bash
aq-workflow run refactoring.yaml '{
  "target_code": "src/legacy/payment-processor.ts",
  "refactoring_goal": "Reduce cyclomatic complexity from 45 to under 15",
  "preserve_tests": true
}'
```

### Expected Duration

20-40 minutes depending on scope

---

## 5. Testing

**File:** `ai-stack/workflows/templates/testing.yaml`

### Description

Create comprehensive test suites with coverage tracking.

### Use Cases

- Adding tests to legacy code
- Improving test coverage
- Creating integration tests
- Test-driven development

### Inputs

| Input | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `target_code` | string | ✓ | - | Code to test |
| `test_types` | array | ✗ | [unit, integration] | Types of tests to create |
| `coverage_target` | number | ✗ | 80 | Target coverage percentage |

### Workflow Steps

1. **Design**: Test plan and test cases
2. **Unit Tests**: Implement unit tests (conditional)
3. **Integration Tests**: Implement integration tests (conditional)
4. **Run Tests**: Execute and collect results
5. **Fix Failures**: Fix any failing tests (loop)
6. **Verify Coverage**: Check coverage meets target

### Agents Used

- `test_designer`: qwen (planning)
- `test_implementer`: qwen (implementation)
- `test_runner`: qwen (execution)

### Memory Integration

- Layers: L0, L1, L2
- Topics: testing, patterns

### Example Usage

```bash
aq-workflow run testing.yaml '{
  "target_code": "src/api/users.ts",
  "test_types": ["unit", "integration"],
  "coverage_target": 90
}'
```

### Expected Duration

15-30 minutes per component

---

## 6. Documentation

**File:** `ai-stack/workflows/templates/documentation.yaml`

### Description

Generate and maintain project documentation with examples.

### Use Cases

- API documentation
- User guides
- Architecture docs
- README files

### Inputs

| Input | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `doc_type` | string | ✓ | - | api, user_guide, architecture, readme |
| `target_component` | string | ✓ | - | Component to document |
| `include_examples` | boolean | ✗ | true | Include code examples |

### Workflow Steps

1. **Analyze**: Gather component information
2. **Outline**: Create documentation structure
3. **Write**: Write documentation sections
4. **Examples**: Create code examples (conditional)
5. **Review**: Review for quality and accuracy
6. **Revise**: Address feedback (loop if needed)

### Agents Used

- `analyzer`: qwen (analysis)
- `writer`: qwen (writing)
- `reviewer`: codex (review)

### Memory Integration

- Layers: L0, L1
- Topics: documentation, best_practices

### Example Usage

```bash
aq-workflow run documentation.yaml '{
  "doc_type": "api",
  "target_component": "src/api/authentication.ts",
  "include_examples": true
}'
```

### Expected Duration

10-20 minutes per component

---

## 7. Performance Optimization

**File:** `ai-stack/workflows/templates/performance-optimization.yaml`

### Description

Identify and optimize performance bottlenecks systematically.

### Use Cases

- Slow API endpoints
- High memory usage
- Database query optimization
- Frontend performance

### Inputs

| Input | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `target_system` | string | ✓ | - | System or component to optimize |
| `performance_goal` | string | ✓ | - | Goal (e.g., "reduce latency by 50%") |
| `profiling_enabled` | boolean | ✗ | true | Enable performance profiling |

### Workflow Steps

1. **Baseline**: Establish performance baseline
2. **Profile**: Identify bottlenecks (conditional)
3. **Prioritize**: Rank optimization opportunities
4. **Optimize**: Implement optimizations (loop)
5. **Measure**: Measure improvements
6. **Validate**: Ensure functionality preserved
7. **Rollback**: Revert if broken (conditional)

### Agents Used

- `profiler`: qwen (profiling)
- `optimizer`: qwen (optimization)
- `validator`: codex (validation)

### Memory Integration

- Layers: L0, L1, L2
- Topics: performance, optimization, algorithms, caching

### Example Usage

```bash
aq-workflow run performance-optimization.yaml '{
  "target_system": "api/search endpoint",
  "performance_goal": "Reduce p95 latency from 800ms to 200ms",
  "profiling_enabled": true
}'
```

### Expected Duration

30-60 minutes

---

## 8. Security Audit

**File:** `ai-stack/workflows/templates/security-audit.yaml`

### Description

Comprehensive security audit and vulnerability assessment.

### Use Cases

- Pre-release security review
- Vulnerability scanning
- Compliance audits
- Threat modeling

### Inputs

| Input | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `target_scope` | string | ✓ | - | Scope of audit |
| `audit_depth` | string | ✗ | standard | quick, standard, comprehensive |
| `include_dependencies` | boolean | ✗ | true | Scan dependencies |

### Workflow Steps

1. **Threat Model**: Identify attack surfaces
2. **Code Scan**: Security vulnerability scan
3. **Dependency Scan**: Check for CVEs (conditional)
4. **Config Audit**: Security configuration review
5. **Access Control**: Review authentication/authorization
6. **Prioritize**: Rank findings by severity
7. **Remediation Plan**: Create fix plan

### Agents Used

- `auditor`: codex (security analysis)
- `vulnerability_scanner`: qwen (scanning)
- `remediation_planner`: qwen (planning)

### Memory Integration

- Layers: L0, L2
- Topics: security, threats, vulnerabilities

### Example Usage

```bash
aq-workflow run security-audit.yaml '{
  "target_scope": "authentication and authorization modules",
  "audit_depth": "comprehensive",
  "include_dependencies": true
}'
```

### Expected Duration

20-40 minutes (standard), 40-60 minutes (comprehensive)

---

## 9. Dependency Update

**File:** `ai-stack/workflows/templates/dependency-update.yaml`

### Description

Safe dependency updates with compatibility testing and rollback.

### Use Cases

- Security patch updates
- Version upgrades
- Breaking change migrations
- Dependency maintenance

### Inputs

| Input | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `update_type` | string | ✗ | minor | patch, minor, major, security |
| `auto_merge` | boolean | ✗ | false | Auto-merge if tests pass |
| `target_dependencies` | array | ✗ | [] | Specific dependencies (empty = all) |

### Workflow Steps

1. **Analyze**: Check available updates
2. **Prioritize**: Order updates by priority
3. **Update**: Apply updates incrementally (loop)
4. **Test**: Run compatibility tests
5. **Fix Failures**: Fix compatibility issues (loop)
6. **Security Check**: Validate security
7. **Review**: Review changes (conditional)
8. **Rollback**: Revert if needed (conditional)

### Agents Used

- `analyzer`: qwen (analysis)
- `updater`: qwen (updates)
- `tester`: qwen (testing)
- `reviewer`: codex (review)

### Memory Integration

- Layers: L0, L1
- Topics: dependencies, compatibility

### Example Usage

```bash
aq-workflow run dependency-update.yaml '{
  "update_type": "security",
  "auto_merge": false,
  "target_dependencies": []
}'
```

### Expected Duration

15-30 minutes (minor updates), 30-60 minutes (major updates)

---

## 10. CI/CD Setup

**File:** `ai-stack/workflows/templates/ci-cd-setup.yaml`

### Description

Set up CI/CD pipeline with best practices and security gates.

### Use Cases

- New project CI/CD setup
- Pipeline modernization
- Adding quality gates
- Multi-environment deployment

### Inputs

| Input | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `platform` | string | ✓ | - | github_actions, gitlab_ci, jenkins, circle_ci |
| `project_type` | string | ✓ | - | python, node, rust, etc. |
| `deployment_targets` | array | ✗ | [staging, production] | Environments |

### Workflow Steps

1. **Analyze**: Determine CI/CD requirements
2. **Design**: Design pipeline stages
3. **Build Stage**: Implement build configuration
4. **Test Stage**: Implement test configuration
5. **Deployment Stages**: Configure deployments (loop)
6. **Quality Gates**: Add security and quality checks
7. **Create Config**: Generate pipeline config file
8. **Validate**: Validate configuration
9. **Document**: Create setup documentation

### Agents Used

- `analyzer`: qwen (requirements)
- `pipeline_designer`: qwen (design)
- `implementer`: qwen (implementation)
- `validator`: codex (validation)

### Memory Integration

- Layers: L0, L1, L2
- Topics: ci_cd, deployment, devops

### Example Usage

```bash
aq-workflow run ci-cd-setup.yaml '{
  "platform": "github_actions",
  "project_type": "node",
  "deployment_targets": ["staging", "production"]
}'
```

### Expected Duration

30-60 minutes

---

## Template Selection Guide

### By Task Type

| Task | Recommended Template |
|------|---------------------|
| Adding new functionality | Feature Implementation |
| Fixing issues | Bug Fix |
| Reviewing changes | Code Review |
| Improving code structure | Refactoring |
| Adding test coverage | Testing |
| Writing documentation | Documentation |
| Improving performance | Performance Optimization |
| Security review | Security Audit |
| Updating packages | Dependency Update |
| Setting up pipelines | CI/CD Setup |

### By Urgency

| Urgency | Templates |
|---------|-----------|
| High (< 30 min) | Bug Fix, Code Review, Testing, Documentation |
| Medium (30-60 min) | Feature Implementation, Refactoring, Performance Optimization, Dependency Update, CI/CD Setup |
| Low (> 60 min) | Security Audit (comprehensive) |

---

## Customization Tips

1. **Copy and modify**: Start with a template, customize for your needs
2. **Combine templates**: Chain multiple workflows for complex tasks
3. **Adjust agents**: Use different agents based on your setup
4. **Tune memory**: Adjust layers and topics for your context
5. **Add nodes**: Extend workflows with additional steps
6. **Remove nodes**: Simplify for faster execution

---

## Next Steps

- Read [User Guide](USER-GUIDE.md) for workflow basics
- Check [Best Practices](BEST-PRACTICES.md) for patterns
