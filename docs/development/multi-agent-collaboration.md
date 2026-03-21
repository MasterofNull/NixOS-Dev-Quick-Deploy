# Multi-Agent Collaboration Architecture

**Status:** Active
**Owner:** AI Harness Team
**Last Updated:** 2026-03-21

**Phase 4: Advanced Multi-Agent Collaboration System**

This document describes the architecture, components, and usage of the multi-agent collaboration system that enables sophisticated teamwork among AI agents.

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Components](#components)
4. [Team Formation](#team-formation)
5. [Communication Protocol](#communication-protocol)
6. [Collaborative Planning](#collaborative-planning)
7. [Quality Consensus](#quality-consensus)
8. [Collaboration Patterns](#collaboration-patterns)
9. [Performance Metrics](#performance-metrics)
10. [API Reference](#api-reference)
11. [Configuration](#configuration)
12. [Best Practices](#best-practices)

## Overview

The multi-agent collaboration system enables teams of AI agents to work together effectively on complex tasks. It provides:

- **Dynamic Team Formation**: Automatically assemble optimal teams based on task requirements
- **Communication Protocol**: Standardized message passing and shared context management
- **Collaborative Planning**: Multiple agents contribute to unified execution plans
- **Quality Consensus**: Democratic validation with weighted voting
- **Collaboration Patterns**: Pre-built patterns for common collaboration modes
- **Performance Tracking**: Measure and compare team vs individual performance

### Key Benefits

- **60%+ Success Rate Improvement**: Teams outperform individuals on complex tasks
- **<1s Team Formation**: Fast team assembly with intelligent matching
- **<50ms Communication Latency**: Real-time message passing
- **<500ms Consensus**: Quick democratic decision-making
- **Adaptive Learning**: System improves over time based on performance data

## Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                    Collaboration Orchestrator                │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌────────────────┐  ┌──────────────────┐  ┌─────────────┐ │
│  │ Team Formation │  │ Communication    │  │ Planning    │ │
│  │                │  │ Protocol         │  │             │ │
│  │ - Agent Match  │  │ - Message Queue  │  │ - Synthesis │ │
│  │ - Capability   │  │ - Shared Context │  │ - Validation│ │
│  │ - Role Assign  │  │ - Conflict Res.  │  │ - Assignment│ │
│  └────────────────┘  └──────────────────┘  └─────────────┘ │
│                                                               │
│  ┌────────────────┐  ┌──────────────────┐  ┌─────────────┐ │
│  │ Consensus      │  │ Patterns         │  │ Metrics     │ │
│  │                │  │                  │  │             │ │
│  │ - Weighted Vote│  │ - Parallel       │  │ - Team Perf │ │
│  │ - Escalation   │  │ - Sequential     │  │ - Comparison│ │
│  │ - Tie-breaking │  │ - Consensus      │  │ - Cost ROI  │ │
│  └────────────────┘  └──────────────────┘  └─────────────┘ │
│                                                               │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │ Agent Profiles   │
                    │ - Capabilities   │
                    │ - Performance    │
                    │ - Availability   │
                    └──────────────────┘
```

### Data Flow

1. **Task Received** → Analyze requirements
2. **Team Formation** → Match capabilities, assign roles
3. **Communication Setup** → Create message queues, shared context
4. **Collaborative Planning** → Collect contributions, synthesize plan
5. **Pattern Execution** → Execute based on selected pattern
6. **Quality Consensus** → Validate outputs, reach agreement
7. **Performance Tracking** → Record metrics, update history

## Components

### 1. Dynamic Team Formation

**Purpose**: Automatically form optimal teams based on task requirements.

**Key Features**:
- Capability matrix matching
- Agent scoring (capability, performance, availability)
- Optimal team size calculation (2-5 agents research-backed)
- Role assignment (orchestrator, planner, executor, reviewer)
- Team caching for similar tasks

**Algorithm**:
```python
def form_team(requirements):
    # 1. Optimize team size based on complexity
    size = optimize_team_size(requirements)

    # 2. Score all agents for task
    scores = [score_agent(agent, requirements) for agent in agents]

    # 3. Select top N agents
    team = select_top_agents(scores, size)

    # 4. Select coordination pattern
    pattern = select_pattern(requirements, size)

    # 5. Assign roles
    assign_roles(team, pattern)

    return team
```

**Performance**:
- Team formation: <1s for teams up to 5 agents
- Cache hit rate: ~30% for similar tasks
- Prediction accuracy: 75%+ for team success

### 2. Agent Communication Protocol

**Purpose**: Enable reliable message passing and context sharing.

**Message Types**:
- `REQUEST`: Request action from agent
- `RESPONSE`: Response to request
- `NOTIFICATION`: Broadcast information
- `CONSENSUS`: Request consensus vote
- `CONTEXT_UPDATE`: Shared context update
- `ERROR`: Error notification

**Priority Levels**:
- `LOW (1)`: Background tasks
- `NORMAL (2)`: Standard messages
- `HIGH (3)`: Important updates
- `URGENT (4)`: Time-sensitive
- `CRITICAL (5)`: Emergency

**Shared Context**:
```python
# Create shared context for team
context = comm.create_shared_context("team-1")

# Update with conflict detection
conflicts = await comm.update_shared_context(
    team_id="team-1",
    agent_id="agent-1",
    updates={"key": "value"},
    broadcast=True,  # Notify team
)

# Handle conflicts
if conflicts:
    # Resolve via consensus
    await resolve_conflicts(conflicts)
```

**Performance**:
- Message latency: <50ms
- Queue capacity: 1000 messages per agent
- Conflict detection: Real-time
- Message throughput: 1000+ msg/sec

### 3. Collaborative Planning

**Purpose**: Multiple agents contribute to create unified execution plan.

**Planning Modes**:
- **Parallel**: All agents contribute simultaneously
- **Sequential**: Agents contribute in order
- **Hierarchical**: Lead planner coordinates

**Process**:
```python
# 1. Create plan
plan_id = planning.create_plan("task-1", "team-1", PlanningMode.PARALLEL)

# 2. Agents add contributions
planning.add_contribution(
    plan_id=plan_id,
    agent_id="agent-1",
    content="My approach...",
    suggested_phases=[...],
    risks=["Risk 1", "Risk 2"],
)

# 3. Synthesize into coherent plan
plan = await planning.synthesize_plan(plan_id, agent_capabilities)

# 4. Validate
plan = await planning.validate_plan(plan_id, available_agents)

# 5. Finalize
final_plan = planning.finalize_plan(plan_id)
```

**Quality Metrics**:
- **Feasibility**: Can plan be executed with available resources?
- **Completeness**: Does plan cover all requirements?
- **Coherence**: Is plan logically structured?

**Performance**:
- Plan synthesis: <5s
- Avg phases: 3-5
- Quality scores: 0.7-0.9 typical

### 4. Quality Consensus

**Purpose**: Democratic validation with weighted voting.

**Consensus Thresholds**:
- **Simple Majority**: >50%
- **Supermajority**: >=66%
- **Unanimous**: 100%
- **Weighted Majority**: >50% by weight

**Vote Types**:
- `APPROVE`: Accept artifact
- `REJECT`: Reject artifact
- `REQUEST_CHANGES`: Approve with changes
- `ABSTAIN`: No opinion

**Weighted Voting**:
```python
# Set reviewer weights
consensus.set_reviewer_weight(
    session_id=session_id,
    reviewer_id="expert-agent",
    base_weight=1.0,
    capability_score=0.9,  # Expert in domain
    performance_score=0.85,  # Historical accuracy
)
# Total weight = 1.0 + (0.9-0.5)*0.5 + (0.85-0.5)*0.5 = 1.375
```

**Escalation**:
- No consensus reached
- Tie vote
- Critical disagreements
- Insufficient votes

**Tie-Breaking Strategies**:
- **Expert Override**: Domain specialist decides
- **Highest Weight**: Most expert reviewer
- **Orchestrator**: Team lead decides

**Performance**:
- Consensus evaluation: <500ms for 5 agents
- Consensus rate: 80%+ typical
- Escalation rate: <20%

### 5. Collaboration Patterns

**Purpose**: Pre-built patterns for common collaboration modes.

#### Pattern 1: Parallel Execution

**Use Case**: Independent subtasks, concurrent execution

```python
# Best for tasks that can be split into independent pieces
result = await patterns.execute_pattern(
    pattern_type=CollaborationPatternType.PARALLEL,
    task_id="task-1",
    team_id="team-1",
    agents=["agent-1", "agent-2", "agent-3"],
    task_data={"tasks": [task1, task2, task3]},
    executor_callback=execute_task,
)
```

**Characteristics**:
- No inter-agent dependencies
- Results merged at end
- Speed improvement with more agents
- Best for: Large tasks with independent subtasks

#### Pattern 2: Sequential Delegation

**Use Case**: Staged workflow with quality gates

```python
# Orchestrator → Planner → Executor → Reviewer
result = await patterns.execute_pattern(
    pattern_type=CollaborationPatternType.SEQUENTIAL,
    task_id="task-1",
    team_id="team-1",
    agents=[orchestrator, planner, executor1, executor2, reviewer],
    task_data=task,
    executor_callback=execute_stage,
)
```

**Stages**:
1. **Planning**: Create execution plan
2. **Execution**: Implement solution
3. **Review**: Validate output
4. **Approval**: Final sign-off

**Characteristics**:
- Linear workflow
- Quality gates between stages
- Each stage depends on previous
- Best for: Complex tasks requiring staged approach

#### Pattern 3: Consensus Review

**Use Case**: High-stakes decisions requiring agreement

```python
# Critical decisions require 2/3 majority
result = await patterns.execute_pattern(
    pattern_type=CollaborationPatternType.CONSENSUS,
    task_id="task-1",
    team_id="team-1",
    agents=reviewers,
    task_data={"artifact": artifact, "threshold": 0.66},
    executor_callback=review_artifact,
)
```

**Characteristics**:
- Democratic decision-making
- Weighted voting by expertise
- Escalation on disagreement
- Best for: Critical decisions, high-quality outputs

#### Pattern 4: Expert Override

**Use Case**: Domain-specific tasks with specialist

```python
# General agents propose, expert decides
result = await patterns.execute_pattern(
    pattern_type=CollaborationPatternType.EXPERT_OVERRIDE,
    task_id="task-1",
    team_id="team-1",
    agents=[agent1, agent2, expert],
    task_data={"expert": expert, ...},
    executor_callback=execute_and_review,
)
```

**Characteristics**:
- General agents provide solutions
- Expert reviews and can override
- Expert gets extra weight
- Best for: Domain-specific, specialized tasks

### 6. Performance Metrics

**Purpose**: Track and compare team vs individual performance.

**Metrics Tracked**:

**Individual Metrics**:
- Tasks completed
- Success rate
- Avg duration
- Quality score

**Team Metrics**:
- Tasks completed
- Success rate
- Avg duration
- Communication overhead
- Collaboration efficiency
- Quality score

**Comparison**:
```python
# Compare team vs individual for task type
comparison = metrics.compare_performance("code_generation")

print(f"Team success: {comparison.team_success_rate:.1%}")
print(f"Individual success: {comparison.individual_success_rate:.1%}")
print(f"Team advantage: {comparison.team_advantage:+.3f}")
print(f"Recommendation: {comparison.recommendation}")
```

**Cost-Benefit Analysis**:
```python
analysis = metrics.calculate_cost_benefit()

print(f"Team ROI: {analysis['roi']:+.3f}")
print(f"Recommendation: {analysis['recommendation']}")
```

**Performance**:
- Real-time tracking: Yes
- Comparison samples: 10+ minimum
- Cost model: Configurable
- Regression detection: 7-day window

## API Reference

### Team Formation API

#### POST /api/collaboration/teams/form

Form optimal team for task.

**Request**:
```json
{
  "task_id": "task-123",
  "description": "Implement user authentication",
  "required_capabilities": ["code_generation", "security"],
  "complexity": 4,
  "min_team_size": 2,
  "max_team_size": 5
}
```

**Response**:
```json
{
  "team": {
    "team_id": "team-task-123-1234567890",
    "members": [
      {
        "agent": {...},
        "role": "orchestrator"
      },
      {
        "agent": {...},
        "role": "executor"
      }
    ],
    "pattern": "hub",
    "predicted_performance": 0.85
  },
  "message": "Team formed with 2 members"
}
```

### Communication API

#### POST /api/collaboration/messages/send

Send message between agents.

**Request**:
```json
{
  "from_agent": "agent-1",
  "to_agent": "agent-2",
  "team_id": "team-1",
  "message_type": "request",
  "content": {"action": "review_code"},
  "priority": "high",
  "requires_response": true
}
```

#### GET /api/collaboration/messages/receive/{agent_id}

Receive next message for agent.

#### POST /api/collaboration/context/update

Update shared context.

### Planning API

#### POST /api/collaboration/plans/create

Create collaborative plan.

#### POST /api/collaboration/plans/contribute

Add contribution to plan.

#### POST /api/collaboration/plans/synthesize

Synthesize plan from contributions.

### Consensus API

#### POST /api/collaboration/consensus/create

Create consensus session.

#### POST /api/collaboration/consensus/review

Submit review for consensus.

#### POST /api/collaboration/consensus/evaluate/{session_id}

Evaluate consensus.

### Patterns API

#### POST /api/collaboration/patterns/execute

Execute collaboration pattern.

#### GET /api/collaboration/patterns

Get available patterns and metrics.

### Metrics API

#### POST /api/collaboration/metrics/record

Record task completion.

#### GET /api/collaboration/metrics/comparison

Get team vs individual comparison.

#### GET /api/collaboration/metrics/summary

Get overall metrics summary.

## Configuration

See `config/multi-agent-collaboration.yaml` for full configuration.

**Key Settings**:

```yaml
team_formation:
  optimal_team_size_range: [2, 5]
  formation_timeout: 1.0

communication:
  queue_max_size: 1000
  default_timeout_seconds: 300
  latency_sla_ms: 50

consensus:
  default_threshold: "simple_majority"
  min_reviewers: 3

patterns:
  parallel:
    min_agents: 2
    parallelization_factor: 0.7

metrics:
  enable_metrics: true
  regression_threshold: 0.05
```

## Best Practices

### 1. Team Formation

**DO**:
- Register agents with accurate capability scores
- Update performance history after each task
- Use appropriate team size (2-5 optimal)
- Cache teams for similar tasks

**DON'T**:
- Over-staff teams (diminishing returns >5)
- Ignore agent availability
- Skip performance tracking

### 2. Communication

**DO**:
- Use appropriate priority levels
- Set reasonable timeouts
- Handle conflicts promptly
- Monitor queue sizes

**DON'T**:
- Broadcast unnecessarily
- Ignore message expiry
- Create circular dependencies

### 3. Planning

**DO**:
- Collect diverse contributions
- Validate plan feasibility
- Assign based on capabilities
- Track risks

**DON'T**:
- Skip validation
- Ignore dependencies
- Over-complicate phases

### 4. Consensus

**DO**:
- Use appropriate threshold for stakes
- Weight by expertise
- Handle escalations
- Track reviewer accuracy

**DON'T**:
- Require unanimous for everything
- Ignore tie-breaking
- Skip conflict resolution

### 5. Patterns

**DO**:
- Select pattern based on task characteristics
- Monitor pattern performance
- Use adaptive selection
- Handle pattern failures

**DON'T**:
- Force wrong pattern
- Ignore performance data
- Skip retry logic

### 6. Performance

**DO**:
- Track all tasks
- Compare regularly
- Detect regressions
- Optimize based on data

**DON'T**:
- Ignore cost overhead
- Skip quality scoring
- Ignore warnings

## Performance Targets

| Metric | Target | Actual (Typical) |
|--------|--------|------------------|
| Team formation time | <1s | 0.2-0.5s |
| Message latency | <50ms | 10-30ms |
| Consensus time (5 agents) | <500ms | 100-300ms |
| Plan synthesis | <5s | 2-4s |
| Team success advantage | >60% | 65-75% |
| Communication overhead | <30% | 15-25% |

## Troubleshooting

### Issue: Teams not forming

**Symptoms**: No suitable agents found

**Solutions**:
1. Check agent registrations
2. Verify capability scores
3. Reduce requirements
4. Check availability

### Issue: High message latency

**Symptoms**: Messages taking >100ms

**Solutions**:
1. Check queue sizes
2. Increase priority
3. Clean expired messages
4. Scale message queues

### Issue: Consensus not reached

**Symptoms**: Frequent escalations

**Solutions**:
1. Lower threshold
2. Add more reviewers
3. Improve reviewer weighting
4. Enable tie-breaking

### Issue: Poor team performance

**Symptoms**: Team worse than individual

**Solutions**:
1. Check communication overhead
2. Optimize team size
3. Improve role assignment
4. Select better pattern

## Future Enhancements

- LLM-powered plan synthesis
- Vector DB for team caching
- Advanced pattern learning
- Real-time adaptation
- Cross-team coordination
- Hierarchical teams (teams of teams)
