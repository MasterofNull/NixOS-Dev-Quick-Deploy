# Autonomous Agentic Orchestration Design

**Objective:** Enable local agents to autonomously orchestrate multi-agent workflows, delegating work to Claude and other agents, handling verifications, and executing roadmap batches with minimal human interaction.

**Created:** 2026-03-15
**Status:** Design Phase
**Priority:** CRITICAL - Unlocks fully autonomous operation

---

## Vision

Transform the system into a **self-executing agentic platform** where:

1. **Local agents orchestrate** remote agent work (Claude, OpenRouter, etc.)
2. **Agents verify each other's work** with automated quality checks
3. **Roadmap batches execute autonomously** as long-running workflows
4. **Human approval required only for critical decisions** (safety-first)
5. **System self-improves continuously** without manual intervention
6. **Rollback mechanisms** prevent and undo mistakes

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                  Autonomous Orchestrator                         │
│  - Reads roadmap batches                                         │
│  - Breaks into agent tasks                                       │
│  - Delegates to local/remote agents                              │
│  - Verifies results                                              │
│  - Approves or rejects work                                      │
│  - Commits successful work                                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Delegation Protocol                          │
│  - Task serialization (JSON)                                     │
│  - Agent selection (local vs remote)                             │
│  - Context provision (progressive disclosure)                    │
│  - Result collection                                             │
└─────────────────────────────────────────────────────────────────┘
                              │
         ┌────────────────────┼────────────────────┐
         ▼                    ▼                    ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│  Local Agent    │  │  Claude (API)   │  │  OpenRouter     │
│  (llama.cpp)    │  │  (Remote)       │  │  (Free)         │
│  - Fast         │  │  - High quality │  │  - Free         │
│  - Free         │  │  - Full context │  │  - Good quality │
└─────────────────┘  └─────────────────┘  └─────────────────┘
         │                    │                    │
         └────────────────────┼────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Verification Framework                         │
│  - Syntax validation (linters, type checkers)                    │
│  - Test execution (unit, integration)                            │
│  - Quality scoring (via self-improvement)                        │
│  - Security scanning (via code executor)                         │
│  - Human review (for critical changes)                           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Approval Workflow                             │
│  - Auto-approve: Low-risk, validated changes                     │
│  - Agent-approve: Medium-risk, peer-verified                     │
│  - Human-approve: High-risk, critical systems                    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                 Long-Running Task Manager                        │
│  - Persistent state (SQLite/AIDB)                                │
│  - Resume capability (after restart)                             │
│  - Progress tracking (batch/task/subtask)                        │
│  - Time budgets (max time per batch)                             │
│  - Circuit breakers (max failures, rollback triggers)            │
└─────────────────────────────────────────────────────────────────┘
```

---

## Core Components

### 1. Autonomous Orchestrator

**Purpose:** Main control loop that reads roadmaps and executes batches autonomously.

**Responsibilities:**
- Read roadmap files and identify pending batches
- Break batches into delegatable tasks
- Select appropriate agent for each task (local vs remote)
- Provide context via progressive disclosure
- Collect and verify results
- Approve or reject work
- Commit successful changes
- Track progress and statistics

**Example Flow:**
```python
orchestrator = AutonomousOrchestrator()

# Execute a roadmap batch autonomously
await orchestrator.execute_batch(
    roadmap="NEXT-GEN-AGENTIC-ROADMAP-2026-03.md",
    phase=1,
    batch=1.1,
    approval_mode="auto",  # auto, agent-verify, human-required
)

# Output:
# - Tasks delegated to agents
# - Results verified
# - Changes committed
# - Progress tracked
```

### 2. Delegation Protocol

**Purpose:** Standardized way to delegate tasks to agents.

**Task Format:**
```json
{
  "task_id": "phase-1-batch-1.1-task-3",
  "type": "implementation",
  "description": "Implement OpenTelemetry instrumentation for AIDB",
  "context": {
    "files_to_read": ["ai-stack/aidb/server.py"],
    "relevant_docs": ["docs/observability/opentelemetry.md"],
    "hints": ["use aidb opentelemetry"],
  },
  "acceptance_criteria": [
    "All endpoints instrumented",
    "Metrics exported to Prometheus",
    "Tests pass",
    "No linting errors"
  ],
  "constraints": {
    "max_files_changed": 5,
    "require_tests": true,
    "safety_level": "medium"
  },
  "agent_preference": "local",  # local, remote, any
  "timeout_seconds": 600
}
```

**Agent Response Format:**
```json
{
  "task_id": "phase-1-batch-1.1-task-3",
  "status": "completed",
  "changes": [
    {
      "file": "ai-stack/aidb/server.py",
      "action": "modified",
      "diff": "...",
      "lines_added": 45,
      "lines_removed": 3
    }
  ],
  "validation_results": {
    "syntax_check": "passed",
    "tests": "passed (12/12)",
    "linting": "passed",
    "security_scan": "passed (0 issues)"
  },
  "execution_time_seconds": 234.5,
  "agent_used": "claude-sonnet-4-5",
  "quality_score": 0.92
}
```

### 3. Verification Framework

**Automatic Verification Steps:**
1. **Syntax validation** - Run language-specific checkers
   - Python: `python3 -m py_compile`
   - Bash: `bash -n`
   - Nix: `nix-instantiate --parse`

2. **Test execution** - Run relevant test suites
   - Unit tests
   - Integration tests
   - Smoke tests

3. **Security scanning** - Check for vulnerabilities
   - Use code executor's security scanner
   - Check for hardcoded secrets
   - Validate input sanitization

4. **Quality scoring** - Assess implementation quality
   - Use self-improvement engine
   - Compare against baselines
   - Check code style consistency

5. **Regression detection** - Ensure nothing broke
   - Run affected services
   - Check health endpoints
   - Validate functionality

**Verification Result:**
```python
class VerificationResult:
    passed: bool
    checks: Dict[str, CheckResult]  # syntax, tests, security, quality
    issues: List[str]
    warnings: List[str]
    quality_score: float
    recommendation: str  # approve, reject, needs_human_review
```

### 4. Approval Workflow

**3-Tier Approval System:**

| Tier | Trigger | Approver | Examples |
|------|---------|----------|----------|
| **Auto-Approve** | Low-risk, all checks passed | System | Docs, tests, config tweaks |
| **Agent-Verify** | Medium-risk, validation passed | Peer agent | Implementation, refactoring |
| **Human-Required** | High-risk or critical | Human | Security, production config |

**Risk Assessment:**
```python
def assess_risk(change: Change) -> RiskLevel:
    """Assess risk of a change."""
    # High risk triggers
    if any([
        "systemd" in change.files,
        "security" in change.files,
        "secrets" in change.files,
        change.lines_removed > 100,
        "root" in change.content,
        "sudo" in change.content,
    ]):
        return RiskLevel.HIGH

    # Medium risk triggers
    if any([
        change.lines_added > 200,
        change.files_changed > 10,
        "database" in change.content,
    ]):
        return RiskLevel.MEDIUM

    return RiskLevel.LOW
```

**Auto-Approval Rules:**
```python
AUTO_APPROVE_CONDITIONS = {
    "all_checks_passed": True,
    "risk_level": RiskLevel.LOW,
    "quality_score": ">= 0.85",
    "no_security_issues": True,
    "no_test_failures": True,
    "files_changed": "<= 5",
    "lines_added": "<= 500",
}
```

### 5. Long-Running Task Manager

**Persistent State:**
```python
class WorkflowState:
    workflow_id: str
    roadmap: str
    phase: int
    batch: float
    started_at: datetime
    current_task_index: int
    total_tasks: int
    completed_tasks: List[str]
    failed_tasks: List[str]
    pending_tasks: List[str]
    approval_queue: List[Task]
    status: str  # running, paused, completed, failed
    last_checkpoint: datetime
```

**Resume Capability:**
```python
# System restarts - workflow resumes from checkpoint
manager = LongRunningTaskManager()
workflows = manager.get_active_workflows()

for workflow in workflows:
    if workflow.should_resume():
        await manager.resume_workflow(workflow.workflow_id)
```

**Circuit Breakers:**
```python
CIRCUIT_BREAKER_LIMITS = {
    "max_consecutive_failures": 3,  # Pause after 3 failures in a row
    "max_total_failures": 10,  # Abort after 10 total failures
    "max_execution_time_hours": 24,  # Abort after 24 hours
    "max_cost_usd": 10.0,  # Abort if cost exceeds $10
    "max_retries_per_task": 3,  # Give up after 3 retries
}
```

### 6. Safety Guardrails

**What Agents CAN Do Autonomously:**
- ✅ Read files and documentation
- ✅ Write new code files (with validation)
- ✅ Modify existing code (with tests)
- ✅ Run tests and validation
- ✅ Create documentation
- ✅ Commit changes (after approval)
- ✅ Update roadmap progress
- ✅ Report issues and blockers

**What Agents CANNOT Do Autonomously:**
- ❌ Modify security-critical files without human approval
- ❌ Change systemd service configurations without approval
- ❌ Delete files or databases
- ❌ Push to remote git repositories
- ❌ Make network-accessible service changes
- ❌ Modify authentication or authorization
- ❌ Change resource limits or quotas
- ❌ Execute destructive operations

**Rollback Mechanism:**
```python
class RollbackManager:
    def create_checkpoint(self, workflow_id: str) -> str:
        """Create git checkpoint before changes."""
        # Create git branch or stash
        # Return checkpoint ID

    def rollback(self, checkpoint_id: str):
        """Rollback to checkpoint."""
        # Restore git state
        # Restart affected services
        # Log rollback reason
```

---

## Implementation Plan

### Phase 12: Autonomous Agentic Orchestration

**Gate:** System successfully executes a complete roadmap batch autonomously from start to commit

### Batch 12.1: Delegation Protocol

**Tasks:**
- [ ] Implement task serialization format (JSON schema)
- [ ] Create agent selection logic (local vs remote routing)
- [ ] Build context provision system (progressive disclosure)
- [ ] Implement result collection and parsing
- [ ] Add timeout and retry logic

**Deliverables:**
- Task protocol schema
- Delegation API
- Agent selector
- Result parser

### Batch 12.2: Verification Framework

**Tasks:**
- [ ] Implement syntax validation for all languages
- [ ] Add test execution integration
- [ ] Build security scanning pipeline
- [ ] Integrate quality scoring (from Batch 11.5)
- [ ] Create regression detection

**Deliverables:**
- Verification engine
- Multi-stage validation
- Quality assessment
- Pass/fail decision logic

### Batch 12.3: Approval Workflow

**Tasks:**
- [ ] Implement risk assessment algorithm
- [ ] Create 3-tier approval system
- [ ] Build auto-approval rules
- [ ] Add human approval queue (for high-risk)
- [ ] Implement peer agent verification

**Deliverables:**
- Approval engine
- Risk classifier
- Approval queue
- Notification system

### Batch 12.4: Long-Running Task Manager

**Tasks:**
- [ ] Create persistent workflow state (SQLite/AIDB)
- [ ] Implement resume capability
- [ ] Add progress tracking
- [ ] Build circuit breakers
- [ ] Create checkpoint/rollback system

**Deliverables:**
- Task manager
- State persistence
- Resume logic
- Circuit breakers
- Rollback mechanism

### Batch 12.5: Autonomous Orchestrator

**Tasks:**
- [ ] Build main orchestration loop
- [ ] Implement roadmap parsing
- [ ] Create batch execution engine
- [ ] Add agent delegation
- [ ] Build commit automation

**Deliverables:**
- Orchestrator engine
- Roadmap executor
- End-to-end automation
- Progress dashboard

### Batch 12.6: Safety & Monitoring

**Tasks:**
- [ ] Implement safety guardrails
- [ ] Add human override mechanisms
- [ ] Create monitoring dashboard
- [ ] Build alert integration
- [ ] Add audit logging

**Deliverables:**
- Safety policies
- Override controls
- Monitoring UI
- Alert rules
- Audit trail

---

## Usage Examples

### Example 1: Execute Batch Autonomously

```python
from autonomous_orchestrator import AutonomousOrchestrator

orchestrator = AutonomousOrchestrator(
    approval_mode="auto",  # Auto-approve low-risk changes
    max_runtime_hours=4,
    max_cost_usd=5.0,
)

# Execute Phase 1 Batch 1.1
result = await orchestrator.execute_batch(
    roadmap="NEXT-GEN-AGENTIC-ROADMAP-2026-03.md",
    phase=1,
    batch=1.1,
)

print(f"Status: {result.status}")
print(f"Tasks completed: {result.completed_tasks}/{result.total_tasks}")
print(f"Changes committed: {result.commits_made}")
print(f"Time: {result.execution_time_hours:.2f}h")
print(f"Cost: ${result.cost_usd:.2f}")
```

### Example 2: Execute Entire Roadmap

```python
# Execute all pending batches in Phase 1
result = await orchestrator.execute_phase(
    roadmap="NEXT-GEN-AGENTIC-ROADMAP-2026-03.md",
    phase=1,
    approval_mode="agent-verify",  # Require agent verification
)

# Or execute entire roadmap
result = await orchestrator.execute_roadmap(
    roadmap="NEXT-GEN-AGENTIC-ROADMAP-2026-03.md",
    approval_mode="auto",
    pause_on_failure=True,
)
```

### Example 3: Human-in-the-Loop

```python
# Execute with human approval for high-risk
orchestrator = AutonomousOrchestrator(
    approval_mode="human-required",
    notification_webhook="https://my-webhook.com/notify",
)

result = await orchestrator.execute_batch(
    roadmap="...",
    phase=2,
    batch=2.3,  # Security hardening batch
)

# System will:
# 1. Execute tasks with agents
# 2. Verify results
# 3. Send notification to human for approval
# 4. Wait for approval before committing
# 5. Commit if approved, rollback if rejected
```

### Example 4: Resume After Restart

```python
# System restart - automatically resume workflows
manager = LongRunningTaskManager()

active_workflows = manager.get_active_workflows()
print(f"Found {len(active_workflows)} active workflows")

for workflow in active_workflows:
    print(f"Resuming: {workflow.roadmap} Phase {workflow.phase} Batch {workflow.batch}")
    await manager.resume_workflow(workflow.workflow_id)
```

---

## Agent Communication Protocol

### Local Agent → Claude Delegation

**Request:**
```json
{
  "delegation": {
    "task": {
      "id": "phase-1-batch-1.1-task-3",
      "description": "Implement OpenTelemetry instrumentation",
      "context": {
        "files": ["ai-stack/aidb/server.py"],
        "docs": ["docs/observability/opentelemetry.md"]
      },
      "criteria": ["All endpoints instrumented", "Tests pass"]
    },
    "agent": {
      "preference": "claude-sonnet-4-5",
      "fallback": "openrouter-qwen-2.5-72b"
    },
    "constraints": {
      "max_cost": 0.50,
      "timeout": 600
    }
  }
}
```

**Response from Claude:**
```json
{
  "task_id": "phase-1-batch-1.1-task-3",
  "status": "completed",
  "changes": [...],
  "validation": {...},
  "questions": [
    {
      "question": "Should I add custom metrics for embedding operations?",
      "options": ["yes", "no", "defer"],
      "recommendation": "yes"
    }
  ]
}
```

### Question Handling

**When Claude has questions:**
1. **Low-priority questions** → Local agent answers autonomously
2. **Medium-priority questions** → Peer agent verification
3. **High-priority questions** → Human notification

**Example local agent answering:**
```python
async def handle_agent_question(question: AgentQuestion) -> str:
    """Local agent answers Claude's question."""

    # Check if we have guidance in docs/hints
    hints = await query_hints(question.question)

    if hints and hints.confidence > 0.8:
        return hints.recommendation

    # Check if similar decision was made before
    similar = await query_memory(question.question)

    if similar and similar.confidence > 0.7:
        return similar.decision

    # Escalate to human
    return await request_human_input(question)
```

---

## Monitoring & Observability

### Dashboard Metrics

**Workflow Progress:**
- Current phase/batch executing
- Tasks completed vs total
- Time elapsed vs estimated
- Cost spent vs budget
- Success rate

**Agent Performance:**
- Local vs remote agent usage
- Average task completion time
- Quality scores
- Failure rate
- Cost per task

**Approval Statistics:**
- Auto-approved count
- Agent-verified count
- Human-approved count
- Rejected count
- Pending approvals

### Alerts

**Critical Alerts:**
- Workflow stuck (no progress in 1 hour)
- Circuit breaker triggered
- Human approval required
- Cost budget exceeded
- Security issue detected

**Warning Alerts:**
- High failure rate (>20%)
- Slow progress (behind schedule)
- Quality degradation
- Approaching budget limit

---

## Security Considerations

**Isolation:**
- Agent-generated code runs in sandbox (from Batch 11.6)
- No direct file system access without validation
- No network access during code gen

**Validation:**
- All code scanned before execution
- All changes reviewed before commit
- All commits signed and attributed

**Audit Trail:**
- Every delegation logged
- Every approval decision logged
- Every commit attributed to agent
- Every rollback recorded

**Human Override:**
- Pause button (stop all workflows)
- Reject button (rollback current batch)
- Emergency stop (rollback all changes since start)

---

## Success Criteria

✅ **System can execute a complete batch autonomously** (parse → delegate → verify → commit)
✅ **Local agents can answer Claude's questions** without human intervention
✅ **Verification framework catches errors** before commit
✅ **Auto-approval works for low-risk changes**
✅ **Human approval queue works for high-risk**
✅ **Workflows resume after system restart**
✅ **Circuit breakers prevent runaway failures**
✅ **Rollback mechanism works reliably**

---

## Performance Targets

| Metric | Target |
|--------|--------|
| Batch completion rate | >80% autonomous |
| Human intervention rate | <20% |
| Auto-approval accuracy | >95% correct |
| Verification false positive | <5% |
| Average batch completion time | <2 hours |
| Cost per batch | <$2 |
| Rollback success rate | 100% |

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Agent generates bad code | Multi-stage verification, rollback |
| Infinite retry loops | Circuit breakers, max retries |
| Cost overruns | Budget limits, cost tracking |
| Security vulnerabilities | Security scanning, human review for critical |
| Lost progress on restart | Persistent state, checkpointing |
| Wrong auto-approvals | Conservative approval rules, audit trail |

---

## Next Steps

1. **Start with Batch 12.1** - Delegation protocol
2. **Build verification framework** (Batch 12.2)
3. **Implement approval workflow** (Batch 12.3)
4. **Add persistence/resume** (Batch 12.4)
5. **Create orchestrator** (Batch 12.5)
6. **Harden safety** (Batch 12.6)
7. **Test end-to-end** with a simple roadmap batch
8. **Deploy to production** with monitoring

---

**Status:** Ready for Implementation
**Priority:** CRITICAL - Unlocks true autonomous operation
**Dependencies:** Phase 11 (Complete ✅)
