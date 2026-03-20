# Orchestration Visibility Operator Guide

**Status:** Active
**Owner:** AI Harness Team
**Last Updated:** 2026-03-20

## Quick Start

1. Open dashboard: `http://localhost:8889`
2. Scroll to "AI Orchestration" card
3. Enter a session ID from workflow logs
4. Click "Load" to inspect team formation

## Dashboard Cards Overview

### AI Orchestration Card

Displays detailed team formation for workflow orchestration sessions.

**Features**:
- Session ID input for on-demand inspection
- Team composition metrics (consensus mode, selection strategy, active slots)
- Team members table showing assigned agents with scores and activation reasons
- Candidate scoring breakdown with all 7 score components
- Historical bias values for each candidate
- Arbiter decision history (when arbiter-review mode active)

**Workflow**:
1. Obtain a session ID from workflow logs or API
2. Enter session ID in the input field
3. Click "Load" button
4. View team composition, scoring details, and arbiter decisions

### Agent Evaluation Trends Card

Displays longitudinal agent performance metrics from the evaluation registry.

**Features**:
- Auto-refreshes every 30 seconds
- Summary metrics: agent count, total reviews/selections/runtime events
- Performance table with per-agent metrics
- Color-coded scores (green/yellow/red)
- Historical bias components explanation

**No action required** - data loads automatically on page load and refreshes periodically.

---

## Understanding Team Formation

### Team Members Table

| Column | Description |
|--------|-------------|
| **Slot** | Role in team: `primary`, `reviewer`, `escalation` |
| **Agent** | Agent identifier: `codex`, `claude`, `qwen`, etc. |
| **Lane** | Execution lane: `implementation`, `codex-review`, `remote-reasoning`, etc. |
| **Role** | Orchestration role: `orchestrator`, `reviewer`, `escalation`, `sub-agent` |
| **Score** | Composite score (0-4 range, higher is better) |
| **Activation Reason** | Explanation for why this agent was selected |

### Scoring Components

Each candidate receives a score built from 7 components:

#### Base Components
| Component | Range | Description |
|-----------|-------|-------------|
| **Strategy Fit** | 0-0.4 | Alignment with selection strategy (orchestrator-first, escalate-on-complexity, etc.) |
| **Locality** | 0-0.25 | Preference for local execution vs remote |
| **Review Alignment** | 0-0.45 | Fit with consensus mode (reviewer-gate, arbiter-review, etc.) |
| **Requester Bias** | 0-0.4 | Boost for original requester to maintain continuity |

#### Historical Bias Components
| Component | Range | Description | Weighting |
|-----------|-------|-------------|-----------|
| **Historical Review** | 0-1.0 | Past review performance | Weighted by review events (up to 5) |
| **Historical Selection** | 0-1.0 | Past selection frequency | Weighted by consensus selections (up to 5) |
| **Historical Runtime Quality** | 0-1.0 | Past runtime performance | Weighted by runtime events (up to 6) |

**Total Score** = Sum of all components, typically 0-4

**Historical Bias Calculation**:
```
review_score = avg_review_score × min(review_events, 5) / 5
selection_score = consensus_selected × min(consensus_selected, 5) / 5 × 0.08
runtime_score = avg_runtime_score × min(runtime_events, 6) / 6
```

---

## Understanding Arbiter Mode

### When Arbiter Mode Activates

Arbiter mode only applies when:
- Consensus mode is set to `arbiter-review`
- Typically used for complex/high-risk workflows requiring human/expert oversight
- Example: `remote-reasoning-escalation` blueprint uses arbiter mode

### Arbiter Decision Fields

| Field | Description |
|-------|-------------|
| **Arbiter** | Identifier of arbiter (human or AI expert) |
| **Verdict** | Decision: `accept`, `reject`, or `prefer` |
| **Selected Candidate** | Agent/lane chosen by arbiter |
| **Rationale** | Detailed explanation of decision |
| **Summary** | Brief decision summary |
| **Timestamp** | When decision was made |

### Verdict Colors

- **Green** (accept): Arbiter approved the candidate
- **Red** (reject): Arbiter rejected the candidate
- **Yellow** (prefer): Arbiter expressed preference but didn't mandate

---

## Agent Evaluation Trends

### Metrics Explained

| Metric | Description |
|--------|-------------|
| **Review Events** | Number of review gate passes agent went through |
| **Avg Review Score** | Average score from reviewers (0-1 scale) |
| **Consensus Selections** | Times selected by consensus for execution |
| **Runtime Events** | Executions tracked (completed, failed, etc.) |
| **Avg Runtime Score** | Average quality score during execution (0-1 scale) |
| **Profiles** | Number of distinct profiles/lanes agent operates in |

### Performance Indicators

| Color | Score Range | Interpretation |
|-------|-------------|----------------|
| **Green** | > 0.7 | Excellent performance |
| **Yellow** | 0.5-0.7 | Adequate performance |
| **Red** | < 0.5 | Needs attention or improvement |

### Historical Bias Impact

Historical bias values directly influence future team formation:
- High review scores → More likely to be selected for reviewer roles
- High selection scores → More likely to be chosen for primary execution
- High runtime scores → More likely to be preferred for production workflows

---

## Common Tasks

### Investigate Why an Agent Was Selected

1. Load session details in orchestration card
2. Find the selected candidate in scoring breakdown (marked "SELECTED")
3. Review score components breakdown:
   - Check base components (strategy_fit, locality, review_alignment, requester_bias)
   - Check historical bias values (review_score, selection_score, runtime_score)
4. Compare to other candidates to understand selection rationale
5. Check activation reason for summary explanation

### Debug Poor Agent Selection

**Symptoms**: Wrong agent selected, suboptimal lane assignment

**Investigation**:
1. Load session and review selected candidate's score breakdown
2. Compare historical bias values across candidates
3. Check if historical data is outdated or insufficient
4. Review agent trends card for recent performance dips
5. Check if selection strategy aligns with workflow intent

**Resolution**:
- If historical data is stale: Wait for more evaluation events to accumulate
- If scoring weights are off: May require orchestration policy tuning
- If agent performance degraded: Investigate agent-specific issues

### Monitor Agent Performance Degradation

1. Regularly check Agent Evaluation Trends card
2. Look for agents with declining scores (changing from green → yellow → red)
3. Click into specific agent profiles to see per-lane performance
4. Correlate with system metrics (CPU, memory, latency)
5. Review recent runtime events for failures or errors

### Understand Arbiter Decisions

**When arbiter-review mode is active:**

1. Load session details
2. Scroll to "Arbiter Decision History" section
3. Review each decision entry:
   - **Timestamp**: When arbiter made decision
   - **Verdict**: Accept/reject/prefer
   - **Selected Agent**: Who arbiter chose
   - **Rationale**: Why arbiter made that choice
4. Look for patterns in arbiter decisions
5. Use rationale to understand decision-making criteria

---

## Troubleshooting

### Session Not Found

**Error**: `Session not found` when loading team details

**Cause**: Invalid session ID or session has expired

**Solution**:
- Verify session ID is correct (copy from logs)
- Check if session is recent (sessions may have retention policy)
- Try a different session ID from active workflows

### No Evaluation Data

**Symptom**: Agent Evaluation Trends card shows "No evaluation data available"

**Cause**: Evaluation registry is empty (no agents have been evaluated yet)

**Solution**:
- Wait for workflow runs with review gates to complete
- Verify orchestration policies include reviewer-gate or arbiter-review
- Check that evaluation registry file exists and is writable

### Arbiter Section Not Showing

**Symptom**: Arbiter history section remains hidden

**Cause**: Session is not using arbiter-review consensus mode

**Solution**:
- Verify session was created with arbiter-review mode
- Check workflow blueprint for consensus_mode setting
- Use a session from "remote-reasoning-escalation" blueprint as test

### Dashboard Not Auto-Refreshing

**Symptom**: Agent trends not updating automatically

**Cause**: JavaScript polling not initialized or dashboard connection issue

**Solution**:
- Refresh browser page
- Check browser console for JavaScript errors
- Verify dashboard API is accessible: `curl http://localhost:8889/api/aistack/orchestration/evaluations/trends`

---

## Advanced Operations

### Correlating Orchestration with System Metrics

1. Load orchestration session details
2. Note timestamp and selected agents
3. Switch to AI Stack Services card
4. Correlate service metrics around same timestamp
5. Look for latency spikes, errors, or resource constraints
6. Use deployment operations card for infrastructure context

### Identifying Orchestration Patterns

1. Review multiple sessions over time
2. Note which agents are consistently selected for which slots
3. Check historical bias trends in Agent Evaluation Trends
4. Identify patterns:
   - Always local vs always remote
   - Specific agents for specific blueprints
   - Arbiter intervention frequency
5. Use patterns to validate orchestration policy effectiveness

### Exporting Orchestration Data

For deeper analysis outside dashboard:

```bash
# Export evaluation trends
curl -sf http://localhost:8889/api/aistack/orchestration/evaluations/trends | \
  jq . > evaluation-trends-$(date +%Y%m%d).json

# Export team details for specific session
SESSION_ID="your-session-id"
curl -sf http://localhost:8889/api/aistack/orchestration/team/$SESSION_ID | \
  jq . > team-details-$SESSION_ID.json

# Export arbiter history
curl -sf http://localhost:8889/api/aistack/orchestration/arbiter/$SESSION_ID | \
  jq . > arbiter-history-$SESSION_ID.json
```

---

## Best Practices

### Regular Monitoring

- Check Agent Evaluation Trends daily to catch performance regressions early
- Review high-impact orchestration sessions (complex workflows, arbiter decisions)
- Monitor for imbalanced agent utilization (one agent dominating all selections)

### Incident Investigation

When investigating orchestration-related incidents:
1. Identify session ID from error logs
2. Load team details to understand which agents were involved
3. Check historical bias to see if selection was anomalous
4. Review arbiter decisions if applicable
5. Correlate with system metrics and deployment operations

### Performance Tuning

- Use historical bias data to identify consistently high-performing agents
- Review selection patterns to ensure strategy alignment
- Monitor arbiter intervention rate (high rate may indicate policy misconfiguration)
- Track score component distributions to validate scoring weights

---

## Security Considerations

### Data Sensitivity

Orchestration visibility exposes:
- Internal agent identifiers
- Scoring algorithms and weights
- Historical performance data
- Arbiter decision rationale

**Access Control**: Assumed authenticated at dashboard level. Operators should have read-only access to this data.

### Audit Trail

All orchestration decisions are logged in:
- Agent evaluation registry (`~/.local/share/nixos-ai-stack/agent-evaluations.json`)
- Workflow session trajectories
- Arbiter decision history

These logs provide forensic evidence for incident investigation and compliance.

---

## Performance Impact

### Dashboard Polling

- Agent Evaluation Trends: Auto-refreshes every 30 seconds
- Team Details: On-demand only (manual load)
- Arbiter History: On-demand only (manual load)

**Load Impact**: Minimal - polling uses lightweight endpoints with in-memory data.

### Storage Growth

- Evaluation registry grows with agent activity (~10KB per agent)
- Session storage bounded by retention policy
- Arbiter history limited to last 10 decisions per session

**Monitoring**: Alert if evaluation registry exceeds 1MB.

---

## Related Documentation

- [Orchestration Visibility API](../api/orchestration-visibility.md) - API endpoint reference
- Workflow blueprints: `config/workflow-blueprints.json`
- Agent evaluation registry: `~/.local/share/nixos-ai-stack/agent-evaluations.json`

---

## Feedback & Support

For issues or enhancement requests:
- Check logs: `journalctl -u ai-hybrid-coordinator.service -f`
- Review dashboard logs: `journalctl -u command-center-dashboard-api.service -f`
- Report issues to development team with session IDs and screenshots
