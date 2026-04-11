# Phase 2 Slice 2.5: Workflow Templates - Delegation Plan

**Delegated To:** codex (templates specialist)
**Delegated By:** claude (orchestrator)
**Depends On:** Slice 2.3 (Workflow Executor) ⏳ PENDING
**Effort:** 4-5 days
**Priority:** P1
**Can Run Parallel With:** Slices 2.4 (Integration), 2.6 (CLI)
**Created:** 2026-04-11

---

## Delegation Context

**Prerequisites:**
- ✅ Slice 2.1: DSL Design complete
- ✅ Slice 2.2: Parser & Validator (in progress)
- ⏳ Slice 2.3: Workflow Executor (pending)

**Your task:** Create a comprehensive library of reusable workflow templates for common AI development tasks.

---

## Objective

Build a library of 10+ production-ready workflow templates that demonstrate best practices and cover common use cases:

1. Feature implementation from specification
2. Bug fixing and debugging
3. Code review with checklists
4. Refactoring with tests
5. Documentation generation
6. Test suite creation
7. Performance optimization
8. Security auditing
9. Data/code migration
10. Service/API integration

---

## Required Reading

1. **DSL Specification:**
   - `docs/workflows/DSL-REFERENCE.md` - Complete language reference
   - `docs/architecture/workflow-dsl-design.md` - Design document

2. **Example Workflows:**
   - All files in `ai-stack/workflows/examples/` - Reference implementations

3. **Existing AI Stack:**
   - `.agent/PROJECT-PRD.md` - Project requirements
   - `AGENTS.md` - Agent capabilities and patterns

---

## Deliverables

Create 10 workflow templates in `ai-stack/workflows/templates/`:

### 1. Feature Implementation (`feature-implementation.yaml`)

**Purpose:** Implement new feature from specification with tests and review

**Key Features:**
- Analysis phase to break down requirements
- Iterative implementation loop
- Automated testing
- Code review gate
- Revision cycle if needed
- Final validation

**Template:**
```yaml
name: feature-implementation
version: 1.0
description: |
  Implement a new feature from specification with comprehensive testing,
  code review, and validation.

inputs:
  feature_spec:
    type: string
    description: "Detailed feature specification"
  include_tests:
    type: boolean
    default: true
  require_review:
    type: boolean
    default: true
  target_coverage:
    type: number
    default: 80

agents:
  developer: qwen
  reviewer: codex
  tester: qwen

nodes:
  - id: analyze-requirements
    agent: ${agents.developer}
    prompt: |
      Analyze the feature specification and create implementation plan:
      ${inputs.feature_spec}

      Provide:
      - Task breakdown
      - File/module structure
      - Dependencies needed
      - Estimated complexity
    memory:
      layers: [L0, L1, L2]
      topics: [architecture, patterns, conventions]
      max_tokens: 600
    outputs:
      - task_list
      - architecture
      - dependencies

  - id: implement-feature
    agent: ${agents.developer}
    depends_on: [analyze-requirements]
    loop:
      prompt: |
        Implement next task from plan:
        ${analyze-requirements.task_list}

        Completed: ${state.completed_tasks}
        Remaining: ${state.remaining_tasks}

        Follow project conventions and use existing patterns.
      until: ALL_TASKS_COMPLETE
      max_iterations: 25
      fresh_context: true
    memory:
      layers: [L0, L1, L2]
      topics: [coding, testing]
      max_tokens: 800
    outputs:
      - implementation
      - files_modified

  - id: write-tests
    agent: ${agents.tester}
    depends_on: [implement-feature]
    condition: ${inputs.include_tests}
    prompt: |
      Write comprehensive test suite for implemented feature:
      Files: ${implement-feature.files_modified}

      Target coverage: ${inputs.target_coverage}%

      Include:
      - Unit tests
      - Integration tests
      - Edge cases
      - Error scenarios
    memory:
      layers: [L0, L1, L2]
      topics: [testing]
    retry:
      max_attempts: 3
      on_failure: [test_failure]
    outputs:
      - test_suite
      - coverage_report

  - id: code-review
    agent: ${agents.reviewer}
    depends_on: [implement-feature, write-tests]
    condition: ${inputs.require_review}
    prompt: |
      Review implementation and tests:
      Implementation: ${implement-feature.implementation}
      Tests: ${write-tests.test_suite}
      Coverage: ${write-tests.coverage_report}

      Check for:
      - Code quality and readability
      - Security vulnerabilities
      - Performance concerns
      - Test coverage adequacy
      - Adherence to conventions
    memory:
      layers: [L0, L1, L2]
      topics: [code-review, security, performance]
    outputs:
      - decision
      - feedback
      - severity

  - id: address-feedback
    agent: ${agents.developer}
    depends_on: [code-review]
    condition: ${code-review.decision == 'needs_revision'}
    prompt: |
      Address review feedback:
      ${code-review.feedback}
      Severity: ${code-review.severity}
    outputs:
      - revision
    goto: code-review

  - id: final-validation
    agent: ${agents.tester}
    depends_on: [code-review]
    condition: ${code-review.decision == 'approve'}
    prompt: |
      Run final validation:
      - All tests passing
      - Linting clean
      - Type checks passing
      - Documentation updated
    outputs:
      - validation_status

outputs:
  implementation: ${implement-feature.implementation}
  tests: ${write-tests.test_suite}
  review_status: ${code-review.decision}
  validation: ${final-validation.validation_status}
```

### 2. Bug Fix Workflow (`bug-fix.yaml`)

**Purpose:** Debug and fix bugs systematically

**Key Features:**
- Issue reproduction
- Root cause analysis
- Fix implementation
- Regression test creation
- Verification

### 3. Code Review (`code-review.yaml`)

**Purpose:** Comprehensive code review with checklist

**Key Features:**
- Security review
- Performance analysis
- Code quality assessment
- Test coverage verification
- Documentation check

### 4. Refactoring (`refactoring.yaml`)

**Purpose:** Refactor code while maintaining tests

**Key Features:**
- Quality assessment
- Refactoring plan
- Iterative improvement
- Test suite maintenance
- Regression prevention

### 5. Documentation Generation (`documentation.yaml`)

**Purpose:** Generate comprehensive documentation

**Key Features:**
- API documentation
- User guides
- Architecture docs
- Examples and tutorials
- Diagrams

### 6. Test Suite Creation (`test-suite.yaml`)

**Purpose:** Create comprehensive test suite for existing code

**Key Features:**
- Coverage analysis
- Test generation
- Edge case identification
- Integration tests
- Performance tests

### 7. Performance Optimization (`performance-optimization.yaml`)

**Purpose:** Profile and optimize code

**Key Features:**
- Performance profiling
- Bottleneck identification
- Optimization implementation
- Benchmarking
- Validation

### 8. Security Audit (`security-audit.yaml`)

**Purpose:** Comprehensive security review

**Key Features:**
- Vulnerability scanning
- Security best practices check
- Dependency audit
- Code analysis
- Remediation plan

### 9. Migration Workflow (`migration.yaml`)

**Purpose:** Data or code migration with validation

**Key Features:**
- Migration planning
- Data mapping
- Migration execution
- Validation
- Rollback capability

### 10. Integration Workflow (`integration.yaml`)

**Purpose:** Integrate new service or API

**Key Features:**
- API analysis
- Client implementation
- Error handling
- Testing
- Documentation

---

## Template Structure Guidelines

Each template should follow this structure:

```yaml
name: <template-name>
version: 1.0
description: |
  Clear description of what this template does
  and when to use it

inputs:
  # Well-documented input parameters
  # Provide sensible defaults
  # Include description for each

agents:
  # Define agent roles for flexibility
  # Allow role swapping

nodes:
  # Clear, logical workflow steps
  # Use descriptive node IDs
  # Include helpful prompts with guidance
  # Configure appropriate memory layers
  # Set reasonable token budgets
  # Add retry logic where needed
  # Include error handlers

outputs:
  # Well-defined outputs
  # Reference node results clearly
```

### Best Practices for Templates

1. **Clear Naming:**
   - Use descriptive node IDs
   - Follow naming conventions
   - Be consistent

2. **Helpful Prompts:**
   - Provide clear instructions
   - Reference inputs and previous outputs
   - Give specific guidance
   - List expectations

3. **Appropriate Memory:**
   - Choose right memory layers
   - Filter by relevant topics
   - Set reasonable token budgets

4. **Error Resilience:**
   - Add retry logic for flaky operations
   - Include error handlers
   - Set max_iterations on loops

5. **Flexibility:**
   - Use input parameters for customization
   - Provide sensible defaults
   - Allow conditional execution

6. **Documentation:**
   - Clear descriptions
   - Document inputs/outputs
   - Explain workflow logic

---

## Validation Criteria

For each template:

- [ ] Valid YAML syntax
- [ ] Passes schema validation
- [ ] Clear description and documentation
- [ ] Input parameters well-defined
- [ ] Agent roles used appropriately
- [ ] Memory configuration appropriate
- [ ] Error handling included
- [ ] Tested with example inputs
- [ ] Follows best practices

Overall:

- [ ] All 10 templates created
- [ ] Templates cover diverse use cases
- [ ] All templates validate successfully
- [ ] README.md created for template library
- [ ] Examples of running each template
- [ ] Code reviewed by orchestrator

---

## Acceptance Criteria

1. ✅ 10+ production-ready workflow templates
2. ✅ All templates validate against schema
3. ✅ Templates demonstrate all DSL features
4. ✅ Clear documentation for each template
5. ✅ Template library README complete
6. ✅ Example usage for each template
7. ✅ Code reviewed and approved

---

## Additional Templates (Bonus)

If time permits, create additional templates:

- **Hotfix Deployment** - Emergency fix and deploy
- **Database Migration** - Schema changes with rollback
- **API Versioning** - Create new API version
- **Dependency Update** - Update and test dependencies
- **Multi-Service Deployment** - Deploy related services

---

## Template Library README

Create `ai-stack/workflows/templates/README.md`:

```markdown
# Workflow Templates

Production-ready workflow templates for common AI development tasks.

## Available Templates

| Template | Purpose | Complexity | Agents Used |
|----------|---------|------------|-------------|
| feature-implementation | Implement new features | Medium-High | qwen, codex |
| bug-fix | Debug and fix issues | Medium | qwen, claude |
| code-review | Comprehensive review | Low | codex |
| refactoring | Improve code quality | Medium | qwen, codex |
| documentation | Generate docs | Low-Medium | qwen |
| test-suite | Create test suites | Medium | qwen |
| performance-optimization | Profile and optimize | High | qwen, claude |
| security-audit | Security review | Medium-High | claude, codex |
| migration | Data/code migration | High | qwen, claude |
| integration | Integrate services | Medium | qwen, codex |

## Usage

### Running a Template

Using CLI:
```bash
aq-workflow run ai-stack/workflows/templates/feature-implementation.yaml \
  --input feature_spec="Add dark mode toggle" \
  --input include_tests=true
```

Using coordinator:
```python
from ai_stack.workflows.coordinator import WorkflowCoordinator

coordinator = WorkflowCoordinator()
result = coordinator.run_workflow(
    workflow_file="ai-stack/workflows/templates/feature-implementation.yaml",
    inputs={
        "feature_spec": "Add dark mode toggle",
        "include_tests": True
    }
)
```

### Customizing Templates

Templates can be customized by:
1. Copying template to your project
2. Modifying inputs, agents, or nodes
3. Running the customized version

## Template Details

[Include detailed section for each template with:
- Purpose
- When to use
- Input parameters
- Expected outputs
- Example usage]
```

---

## Testing Each Template

Create `ai-stack/workflows/templates/tests/test_templates.py`:

```python
import pytest
from ...parser import WorkflowParser
from ...validator import WorkflowValidator

class TestWorkflowTemplates:
    @pytest.fixture
    def parser(self):
        return WorkflowParser()

    @pytest.fixture
    def validator(self):
        return WorkflowValidator()

    def test_all_templates_valid(self, parser, validator):
        """Test that all templates are valid"""
        templates = [
            "feature-implementation.yaml",
            "bug-fix.yaml",
            "code-review.yaml",
            "refactoring.yaml",
            "documentation.yaml",
            "test-suite.yaml",
            "performance-optimization.yaml",
            "security-audit.yaml",
            "migration.yaml",
            "integration.yaml",
        ]

        for template_name in templates:
            template_path = f"ai-stack/workflows/templates/{template_name}"

            # Parse
            workflow = parser.parse_file(template_path)
            assert workflow is not None

            # Validate
            errors = validator.validate_all(workflow)
            assert len(errors) == 0, f"Validation errors in {template_name}: {errors}"
```

---

## Next Steps After Completion

- Integrate templates with CLI (Slice 2.6)
- Add template discovery in coordinator
- Create template gallery in dashboard
- Gather user feedback and iterate

---

**Expected Completion:** After Slice 2.3 completes + 4-5 days (can run parallel with 2.4, 2.6)
**Delegated By:** Claude Sonnet 4.5 (orchestrator)
