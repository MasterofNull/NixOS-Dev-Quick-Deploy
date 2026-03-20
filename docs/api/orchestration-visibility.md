# Orchestration Visibility API

## Overview
Provides operator visibility into AI orchestration layer decisions, team formation, and agent performance tracking.

## Endpoints

### GET /workflow/run/{session_id}/team/detailed

Returns detailed team formation with scoring breakdown and historical bias.

**Base URL**: `http://localhost:8003` (hybrid coordinator)

**Parameters**:
- `session_id` (path): UUID of the workflow run session

**Response** (200 OK):
```json
{
  "session_id": "uuid-string",
  "consensus_mode": "reviewer-gate" | "arbiter-review" | "evidence-review",
  "selection_strategy": "orchestrator-first" | "escalate-on-complexity" | "local-first" | "evidence-first",
  "formation_mode": "dynamic-role-assignment",
  "active_slots": ["primary", "reviewer", "escalation"],
  "selected_candidate_id": "candidate-id",
  "team_members": [
    {
      "slot": "primary",
      "candidate_id": "candidate-id",
      "lane": "implementation",
      "agent": "codex",
      "role": "orchestrator",
      "score": 2.4567,
      "required": true,
      "activation_reason": "Selected by orchestrator-first strategy"
    }
  ],
  "candidates": [
    {
      "candidate_id": "primary",
      "lane": "implementation",
      "agent": "codex",
      "role": "orchestrator",
      "basis": "Orchestrator-first strategy with local execution preference",
      "score": 2.4567,
      "score_components": {
        "strategy_fit": 0.4,
        "locality": 0.25,
        "review_alignment": 0.45,
        "requester_bias": 0.4,
        "historical_review": 0.3456,
        "historical_selection": 0.4111,
        "historical_runtime_quality": 0.2
      },
      "history_bias": {
        "review_score": 0.3456,
        "selection_score": 0.4111,
        "runtime_score": 0.2
      }
    }
  ]
}
```

**Error Responses**:
- `404 Not Found`: Session not found

---

### GET /workflow/run/{session_id}/arbiter/history

Returns arbiter decision history for a workflow run (only for arbiter-review mode).

**Base URL**: `http://localhost:8003` (hybrid coordinator)

**Parameters**:
- `session_id` (path): UUID of the workflow run session
- `limit` (query, optional): Maximum decisions to return (default: 10, max: 50)

**Response** (200 OK):
```json
{
  "session_id": "uuid-string",
  "arbiter_active": true,
  "arbiter": "human-operator",
  "current_status": "resolved",
  "history_count": 15,
  "history": [
    {
      "ts": 1710960000,
      "arbiter": "human-operator",
      "verdict": "accept" | "reject" | "prefer",
      "selected_candidate_id": "primary",
      "selected_lane": "reasoning",
      "selected_agent": "claude",
      "rationale": "Claude reasoning model better suited for complex architecture decision",
      "summary": "Selected remote reasoning over local implementation",
      "supporting_decisions": []
    }
  ]
}
```

**Non-Arbiter Mode Response** (200 OK):
```json
{
  "session_id": "uuid-string",
  "arbiter_active": false,
  "history": [],
  "message": "arbiter mode not active"
}
```

**Error Responses**:
- `404 Not Found`: Session not found

---

### GET /control/ai-coordinator/evaluations/trends

Returns agent performance trends over time from longitudinal evaluation registry.

**Base URL**: `http://localhost:8003` (hybrid coordinator)

**Response** (200 OK):
```json
{
  "status": "ok",
  "agent_count": 3,
  "trends": [
    {
      "agent": "codex",
      "total_review_events": 45,
      "total_consensus_selected": 32,
      "total_runtime_events": 67,
      "average_review_score": 0.842,
      "average_runtime_score": 0.756,
      "profile_count": 4,
      "last_event_at": 1710960000,
      "profiles": {
        "implementation": {
          "review_events": 20,
          "consensus_selected": 15,
          "runtime_events": 30,
          "average_review_score": 0.85,
          "average_runtime_score": 0.78
        }
      }
    }
  ],
  "summary": {
    "review_events": 120,
    "consensus_events": 87,
    "runtime_events": 150
  },
  "recent_events": [
    {
      "ts": 1710960000,
      "event_type": "review" | "consensus" | "runtime",
      "agent": "codex",
      "profile": "implementation",
      "detail": "..."
    }
  ]
}
```

---

## Dashboard Proxy Endpoints

These endpoints are available through the dashboard API at `http://localhost:8889/api/aistack/orchestration/`.

### GET /api/aistack/orchestration/team/{session_id}

Proxies to hybrid coordinator `/workflow/run/{session_id}/team/detailed`.

Returns same structure as hybrid coordinator endpoint.

---

### GET /api/aistack/orchestration/arbiter/{session_id}

Proxies to hybrid coordinator `/workflow/run/{session_id}/arbiter/history`.

Query parameter: `limit` (optional, default: 10)

Returns same structure as hybrid coordinator endpoint.

---

### GET /api/aistack/orchestration/evaluations/trends

Proxies to hybrid coordinator `/control/ai-coordinator/evaluations/trends`.

Returns same structure as hybrid coordinator endpoint.

---

### GET /api/aistack/orchestration/sessions

Placeholder endpoint for future session listing.

**Response** (200 OK):
```json
{
  "status": "ok",
  "sessions": [],
  "message": "session listing requires hybrid coordinator list endpoint"
}
```

---

## Dashboard Integration

The dashboard automatically polls the evaluation trends endpoint every 30 seconds and displays:

1. **AI Orchestration Card**:
   - Session input for on-demand team inspection
   - Team composition metrics
   - Team members table with scoring
   - Candidate scoring breakdown with historical bias
   - Arbiter decision history (conditional)

2. **Agent Evaluation Trends Card**:
   - Summary metrics (agent count, total events)
   - Agent performance table with color-coded scores
   - Historical bias components explanation

## Scoring Components Explained

### Base Scoring Components
- **strategy_fit** (0-0.4): Alignment with selection strategy
- **locality** (0-0.25): Preference for local execution
- **review_alignment** (0-0.45): Fit with consensus mode
- **requester_bias** (0-0.4): Boost for original requester

### Historical Bias Components
- **historical_review** (0-1.0): Review score weighted by review events (up to 5)
- **historical_selection** (0-1.0): Selection score weighted by consensus selections (up to 5)
- **historical_runtime_quality** (0-1.0): Runtime score weighted by runtime events (up to 6)

**Total Score**: Sum of all components, typically in range 0-4

## Usage Examples

### Inspect Team Formation

```bash
# Get detailed team composition for a workflow run
curl -sf http://localhost:8003/workflow/run/<session-id>/team/detailed | jq .

# View only candidates and their scores
curl -sf http://localhost:8003/workflow/run/<session-id>/team/detailed | \
  jq '.candidates[] | {agent, lane, score, score_components, history_bias}'
```

### View Arbiter Decisions

```bash
# Get last 10 arbiter decisions
curl -sf http://localhost:8003/workflow/run/<session-id>/arbiter/history | jq .

# Get last 5 arbiter decisions
curl -sf "http://localhost:8003/workflow/run/<session-id>/arbiter/history?limit=5" | jq .
```

### Track Agent Performance

```bash
# Get all agent evaluation trends
curl -sf http://localhost:8003/control/ai-coordinator/evaluations/trends | jq .

# View top 3 agents by activity
curl -sf http://localhost:8003/control/ai-coordinator/evaluations/trends | \
  jq '.trends[:3] | .[] | {agent, total_review_events, average_review_score}'
```

## Error Handling

All endpoints return standard error responses:

```json
{
  "error": "session not found" | "internal_error",
  "detail": "...",
  "status": 404 | 500
}
```

## Security Considerations

- Endpoints expose internal orchestration state (agent names, scores, decisions)
- Assumed authenticated at dashboard level (no additional auth required)
- Rate limiting: Dashboard polls every 30s (low volume, no additional limiting needed)
- No sensitive secrets exposed (only system performance metrics)
