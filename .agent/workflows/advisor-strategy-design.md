# AI Advisor Strategy Integration Design

**Date**: 2026-04-17
**Status**: Design Phase
**Author**: Claude Sonnet 4.5

## Overview

This document outlines the integration of the AI Advisor Strategy (as described in https://claude.com/blog/the-advisor-strategy) into the NixOS-Dev-Quick-Deploy AI harness. The advisor strategy pairs a cost-effective executor model with a frontier advisor model that provides guidance on complex decisions without executing them.

## Current Architecture Analysis

### Existing Components

1. **LLMRouter** (`llm_router.py`)
   - Routes tasks across LOCAL > FREE > PAID > CRITICAL tiers
   - Implements failure-based escalation
   - Delegates to hybrid coordinator for remote execution
   - Tracks routing metrics and cost savings

2. **TaskClassifier** (`task_classifier.py`)
   - Heuristic-based classification (no LLM calls)
   - Classifies into: lookup, format, synthesize, code, reasoning
   - Determines local_suitable vs remote_required
   - Creates optimized prompts for local models

3. **ModelCoordinator** (`model_coordinator.py`)
   - Classifies tasks by ModelRole: orchestrator, reasoning, coding, embedding, fast_chat
   - Routes to appropriate model types
   - Supports cost optimization with tier-based routing

4. **AICoordinator** (`ai_coordinator.py`)
   - Manages runtime profiles
   - Profiles: local-hybrid, local-tool-calling, remote-gemini, remote-free, remote-coding, remote-reasoning

### Current vs Advisor Strategy

| Aspect | Current | Advisor Strategy |
|--------|---------|------------------|
| **Escalation Trigger** | Failure/error | Proactive decision point detection |
| **Escalation Purpose** | Retry task at higher tier | Get guidance/plan for executor |
| **Execution** | Escalated tier executes | Executor maintains control |
| **Token Usage** | Full context retried | Advisor provides concise guidance |
| **Cost Model** | Tier-based (failure → higher cost) | Selective consultation (predictable cost) |

## Design Goals

1. **Full Integration**: Incorporate advisor strategy into existing harness, not as separate mode
2. **Multi-Model Support**: Work with remote APIs (Anthropic, OpenAI, etc.) and local models
3. **Cost Optimization**: Maintain existing cost tiers while adding advisor consultation
4. **Backward Compatible**: Existing routing continues to work
5. **Measurable**: Track advisor consultations, success rate, cost impact

## Architecture Design

### 1. Advisor Configuration

Add advisor configuration to `config.py`:

```python
class AdvisorConfig:
    """Configuration for advisor strategy."""

    # Advisor model selection
    ADVISOR_MODEL = os.getenv("ADVISOR_MODEL", "claude-opus-4-5")
    ADVISOR_ENDPOINT = os.getenv("ADVISOR_ENDPOINT", "switchboard")  # anthropic, openrouter, local, switchboard
    ADVISOR_PROFILE = os.getenv("ADVISOR_PROFILE", "remote-reasoning")

    # Decision-type specific advisor routing (multi-model support)
    ADVISOR_ARCHITECTURE_MODEL = os.getenv("ADVISOR_ARCHITECTURE_MODEL", "")
    ADVISOR_SECURITY_MODEL = os.getenv("ADVISOR_SECURITY_MODEL", "")
    ADVISOR_PLANNING_MODEL = os.getenv("ADVISOR_PLANNING_MODEL", "")
    ADVISOR_TRADEOFF_MODEL = os.getenv("ADVISOR_TRADEOFF_MODEL", "")
    ADVISOR_AMBIGUITY_MODEL = os.getenv("ADVISOR_AMBIGUITY_MODEL", "")

    # Fallback advisor models (supports gemini, qwen, gpt, deepseek, etc.)
    ADVISOR_FALLBACK_MODELS = json.loads(
        os.getenv("ADVISOR_FALLBACK_MODELS_JSON",
                  '["claude-sonnet","gpt-4o","gemini-2.0-flash-thinking","qwen-max","deepseek-r1"]')
    )

    # Advisor invocation limits
    ADVISOR_MAX_USES_PER_TASK = int(os.getenv("ADVISOR_MAX_USES_PER_TASK", "3"))
    ADVISOR_TOKEN_BUDGET = int(os.getenv("ADVISOR_TOKEN_BUDGET", "700"))  # Typical 400-700 tokens

    # Decision point detection
    ADVISOR_ENABLED = os.getenv("ADVISOR_ENABLED", "true").lower() == "true"
    ADVISOR_DECISION_POINT_THRESHOLD = float(os.getenv("ADVISOR_DECISION_POINT_THRESHOLD", "0.7"))

    # Local advisor support (for fully local deployments)
    LOCAL_ADVISOR_MODEL = os.getenv("LOCAL_ADVISOR_MODEL", "deepseek-r1")
    LOCAL_ADVISOR_URL = os.getenv("LOCAL_ADVISOR_URL", LLAMA_CPP_REASONING_URL)
```

### 2. Decision Point Detector

Create `advisor_detector.py` to identify when executor should consult advisor:

```python
@dataclass
class DecisionPoint:
    """Represents a decision point requiring advisor consultation."""
    task_id: str
    decision_type: str  # architecture, security, ambiguity, tradeoff, planning
    question: str  # Question to ask advisor
    context: Dict[str, Any]  # Relevant context for advisor
    confidence: float  # Confidence that this needs advisor (0-1)
    detected_signals: List[str]  # Signals that triggered detection

class DecisionPointDetector:
    """Detects when executor should consult advisor."""

    DECISION_SIGNALS = {
        "architecture": [
            "design pattern", "architecture decision", "structure",
            "organization", "module design", "api design"
        ],
        "security": [
            "security", "authentication", "authorization", "encryption",
            "vulnerability", "sanitize", "validate input", "xss", "sql injection"
        ],
        "ambiguity": [
            "unclear", "ambiguous", "multiple approaches", "not sure",
            "which way", "should i", "alternative"
        ],
        "tradeoff": [
            "tradeoff", "trade-off", "versus", "vs", "compare approaches",
            "pros and cons", "advantages", "disadvantages"
        ],
        "planning": [
            "multi-step", "complex workflow", "sequence of", "phase",
            "roadmap", "implementation plan"
        ]
    }

    def detect(self, task: str, context: Dict, executor_tier: str) -> Optional[DecisionPoint]:
        """
        Detect if task has decision points requiring advisor consultation.

        Args:
            task: Task description
            context: Execution context
            executor_tier: Current executor tier (local, free, paid)

        Returns:
            DecisionPoint if detected, None otherwise
        """
```

### 3. Advisor Invocation Layer

Extend `llm_router.py` with advisor consultation:

```python
class LLMRouter:
    def __init__(self, ...):
        # ... existing init ...
        self.advisor_detector = DecisionPointDetector()
        self.advisor_uses = {}  # Track advisor uses per task

    async def execute_with_advisor(self, task: Dict) -> Dict:
        """
        Execute task with optional advisor consultation.

        Flow:
        1. Route to executor tier
        2. Detect decision points during execution
        3. Consult advisor if decision point found
        4. Resume executor with advisor guidance
        5. Return result
        """
        task_id = task.get("task_id", str(uuid.uuid4()))
        executor_tier, executor_model = self.route_task(task["description"], task.get("context"))

        # Initialize advisor tracking
        self.advisor_uses[task_id] = 0
        max_advisor_uses = task.get("max_advisor_uses", AdvisorConfig.ADVISOR_MAX_USES_PER_TASK)

        # Check for decision points before execution
        decision_point = self.advisor_detector.detect(
            task["description"],
            task.get("context", {}),
            executor_tier.value
        )

        if decision_point and AdvisorConfig.ADVISOR_ENABLED:
            # Consult advisor first
            advisor_guidance = await self._consult_advisor(decision_point, task_id)
            task["advisor_guidance"] = advisor_guidance
            self.advisor_uses[task_id] += 1

        # Execute with executor (potentially with advisor guidance)
        result = await self._execute_with_tier(task, executor_tier, executor_model)

        return result

    async def _consult_advisor(
        self,
        decision_point: DecisionPoint,
        task_id: str
    ) -> Dict:
        """
        Consult advisor for guidance on decision point.

        Advisor provides:
        - Plan/approach recommendation
        - Corrections to executor's approach
        - Stop signal if task is unsafe/inappropriate
        """
        advisor_prompt = self._build_advisor_prompt(decision_point)

        # Route to advisor model (typically highest tier)
        advisor_response = await self._execute_advisor_call(
            prompt=advisor_prompt,
            model=AdvisorConfig.ADVISOR_MODEL,
            max_tokens=AdvisorConfig.ADVISOR_TOKEN_BUDGET
        )

        # Record advisor consultation
        self._record_advisor_consultation(
            task_id=task_id,
            decision_type=decision_point.decision_type,
            guidance=advisor_response
        )

        return advisor_response
```

### 4. Multi-Model Support

Support for different advisor backends:

```python
class AdvisorBackend(Enum):
    """Supported advisor backends."""
    ANTHROPIC = "anthropic"      # Claude Opus via Anthropic API
    OPENROUTER = "openrouter"    # Route through OpenRouter
    LOCAL = "local"              # Local high-capability model (DeepSeek-R1, etc.)
    SWITCHBOARD = "switchboard"  # Route through switchboard

async def _execute_advisor_call(self, prompt: str, model: str, max_tokens: int) -> Dict:
    """Execute advisor call through appropriate backend."""
    backend = self._determine_advisor_backend()

    if backend == AdvisorBackend.ANTHROPIC:
        return await self._advisor_via_anthropic(prompt, model, max_tokens)
    elif backend == AdvisorBackend.OPENROUTER:
        return await self._advisor_via_openrouter(prompt, model, max_tokens)
    elif backend == AdvisorBackend.LOCAL:
        return await self._advisor_via_local(prompt, model, max_tokens)
    else:  # SWITCHBOARD
        return await self._advisor_via_switchboard(prompt, model, max_tokens)
```

### 5. Metrics and Observability

Track advisor strategy metrics in existing metrics DB:

```sql
CREATE TABLE IF NOT EXISTS advisor_consultations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    task_id TEXT,
    decision_type TEXT,
    executor_tier TEXT,
    executor_model TEXT,
    advisor_model TEXT,
    advisor_tokens INTEGER,
    advisor_cost REAL,
    guidance_applied BOOLEAN,
    task_success BOOLEAN,
    time_to_consult_ms INTEGER
);

CREATE INDEX IF NOT EXISTS idx_advisor_task_id ON advisor_consultations(task_id);
CREATE INDEX IF NOT EXISTS idx_advisor_decision_type ON advisor_consultations(decision_type);
CREATE INDEX IF NOT EXISTS idx_advisor_timestamp ON advisor_consultations(timestamp);
```

### 6. Integration Points

#### A. Task Classifier Integration

Update `task_classifier.py` to flag tasks that may need advisor:

```python
@dataclass
class TaskComplexity:
    # ... existing fields ...
    advisor_recommended: bool = False  # NEW
    advisor_reason: str = ""  # NEW
```

#### B. Model Coordinator Integration

Update `model_coordinator.py` to include advisor routing:

```python
@dataclass
class TaskClassification:
    # ... existing fields ...
    advisor_consultation_points: List[str] = field(default_factory=list)  # NEW
```

#### C. AI Coordinator Integration

Add advisor runtime profile to `ai_coordinator.py`:

```python
_runtime_record(
    "advisor-claude-opus",
    name="Claude Opus Advisor",
    profile="advisor",
    runtime_class="advisor-agent",
    tags=["advisor", "remote", "claude-opus", "reasoning"],
    status="ready" if AdvisorConfig.ADVISOR_ENABLED else "disabled",
    note="Frontier advisor model for complex decision points",
    model_alias=AdvisorConfig.ADVISOR_MODEL,
    now=now_ts,
)
```

## Implementation Phases

### Phase 1: Foundation (Day 1)
- [ ] Add advisor configuration to `config.py`
- [ ] Create `advisor_detector.py` with decision point detection
- [ ] Add advisor metrics schema to routing DB
- [ ] Unit tests for decision point detection

### Phase 2: Core Integration (Day 2-3)
- [ ] Implement advisor invocation in `llm_router.py`
- [ ] Add multi-backend support (Anthropic, OpenRouter, Local, Switchboard)
- [ ] Update task classifier to flag advisor-recommended tasks
- [ ] Integration tests for advisor flow

### Phase 3: Coordinator Integration (Day 4)
- [ ] Update `model_coordinator.py` for advisor routing
- [ ] Add advisor runtime profile to `ai_coordinator.py`
- [ ] Implement advisor guidance application in executors
- [ ] End-to-end tests

### Phase 4: Observability & Tuning (Day 5)
- [ ] Add advisor metrics dashboard queries
- [ ] Tune decision point detection thresholds
- [ ] Performance benchmarking
- [ ] Cost analysis

### Phase 5: Documentation (Day 6)
- [ ] Configuration guide
- [ ] Usage examples
- [ ] Troubleshooting guide
- [ ] Migration guide from current escalation

## Success Metrics

1. **Advisor Consultation Rate**: 5-15% of tasks (similar to Anthropic's findings)
2. **Cost Reduction**: Maintain or improve cost efficiency vs current escalation
3. **Success Rate Improvement**: Measure task success with vs without advisor
4. **Latency Impact**: Advisor consultations should add <2s per task
5. **Token Efficiency**: Advisor consumes 400-700 tokens per consultation (as per blog post)

## Edge Cases & Considerations

1. **Local-Only Deployments**: Use local high-capability model as advisor
2. **Offline Mode**: Graceful degradation when advisor unavailable
3. **Cost Limits**: Respect advisor max_uses and token budgets
4. **Circular Consultation**: Prevent advisor from requesting more advisors
5. **Context Size**: Limit advisor prompts to essential decision context

## Backward Compatibility

- Existing routing continues to work without advisor
- Advisor opt-in via configuration flag `ADVISOR_ENABLED`
- Current escalation logic remains for failure cases
- New advisor consultation is separate from failure escalation

## References

- [Claude Blog: The Advisor Strategy](https://claude.com/blog/the-advisor-strategy)
- Existing routing: `ai-stack/mcp-servers/hybrid-coordinator/llm_router.py`
- Task classification: `ai-stack/mcp-servers/hybrid-coordinator/task_classifier.py`
- Model coordination: `ai-stack/mcp-servers/hybrid-coordinator/model_coordinator.py`
