# Multi-Agent Collaboration Operations Guide

**Status:** Active
**Owner:** AI Harness Team
**Last Updated:** 2026-03-21

Practical guide for operating and monitoring the multi-agent collaboration system.

## Quick Start

### 1. Register Agents

```bash
# Register an agent via API
curl -X POST http://localhost:8080/api/collaboration/agents/register \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "claude-opus",
    "name": "Claude Opus",
    "capabilities": {
      "code_generation": 0.95,
      "code_review": 0.90,
      "architecture": 0.95
    },
    "preferred_roles": ["orchestrator", "planner"],
    "cost_per_task": 5.0
  }'
```

### 2. Form a Team

```bash
# Form team for task
curl -X POST http://localhost:8080/api/collaboration/teams/form \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "implement-auth",
    "description": "Implement user authentication",
    "required_capabilities": ["code_generation", "security"],
    "complexity": 4,
    "min_team_size": 2,
    "max_team_size": 5
  }'
```

### 3. Monitor Performance

```bash
# Get metrics summary
curl http://localhost:8080/api/collaboration/metrics/summary

# Compare team vs individual
curl http://localhost:8080/api/collaboration/metrics/comparison?task_type=code_generation
```

## Configuration

### Adjust Team Formation

Edit `config/multi-agent-collaboration.yaml`:

```yaml
team_formation:
  optimal_team_size_range: [2, 5]  # Adjust for your needs
  formation_timeout: 1.0  # Increase if needed
  
  # Adjust selection weights
  selection_weights:
    capability_match: 0.5
    performance_history: 0.3
    availability: 0.2
```

### Configure Communication

```yaml
communication:
  queue_max_size: 1000  # Increase for high traffic
  default_timeout_seconds: 300
  latency_sla_ms: 50  # Alert if exceeded
```

### Set Consensus Thresholds

```yaml
consensus:
  default_threshold: "simple_majority"  # or "supermajority", "unanimous"
  min_reviewers: 3
  enable_tie_breaking: true
```

## Monitoring

### Key Metrics to Watch

**Team Formation**:
- Formation time: Should be <1s
- Cache hit rate: Higher is better (30%+)
- Team size distribution: Most should be 2-5

**Communication**:
- Message latency: Should be <50ms
- Queue sizes: Monitor for buildup
- Conflict rate: Should be <10%

**Consensus**:
- Consensus rate: Should be >80%
- Escalation rate: Should be <20%
- Avg review time: Monitor for delays

**Performance**:
- Team success rate: Should be >individual
- Communication overhead: Should be <30%
- Quality scores: Monitor trends

### Dashboard Queries

```bash
# Team formation metrics
curl http://localhost:8080/api/collaboration/metrics/summary | jq '.team_formation'

# Communication metrics
curl http://localhost:8080/api/collaboration/metrics/summary | jq '.communication'

# Pattern performance
curl http://localhost:8080/api/collaboration/patterns
```

### Alerts to Configure

1. **High Queue Size**: Queue >800 messages
2. **High Latency**: Message latency >100ms
3. **Low Consensus**: Consensus rate <70%
4. **Performance Regression**: Team advantage drops >5%

## Troubleshooting

### Common Issues

#### Issue 1: Teams Not Forming Quickly

**Diagnosis**:
```bash
# Check formation times
curl http://localhost:8080/api/collaboration/metrics/summary | jq '.team_formation.avg_formation_time'
```

**Solutions**:
1. Check agent availability
2. Reduce capability requirements
3. Increase cache size
4. Review agent profiles

#### Issue 2: High Message Latency

**Diagnosis**:
```bash
# Check queue status for agent
curl http://localhost:8080/api/collaboration/messages/queue/agent-1
```

**Solutions**:
1. Increase queue size
2. Clean expired messages
3. Optimize message priority
4. Scale horizontally

#### Issue 3: Consensus Not Reached

**Diagnosis**:
```bash
# Check consensus metrics
curl http://localhost:8080/api/collaboration/metrics/summary | jq '.consensus'
```

**Solutions**:
1. Lower threshold for non-critical decisions
2. Add more reviewers
3. Improve reviewer weights
4. Enable expert override

## Best Practices

### Agent Registration

- **Update regularly**: Keep capability scores current
- **Track performance**: Update after each task
- **Set realistic costs**: Helps with budget optimization
- **Define clear roles**: Improves team composition

### Team Management

- **Use caching**: Reuse successful teams
- **Monitor diversity**: Ensure varied capabilities
- **Track patterns**: Learn which work best
- **Optimize size**: Usually 2-5 is optimal

### Communication

- **Set appropriate priorities**: Don't overuse CRITICAL
- **Clean expired messages**: Prevent queue buildup
- **Monitor conflicts**: Resolve promptly
- **Use broadcast sparingly**: Reduces overhead

### Performance Optimization

- **Track all tasks**: Enable comprehensive comparison
- **Review regularly**: Weekly performance reviews
- **Detect regressions**: Enable auto-detection
- **Optimize costs**: Monitor ROI

## Maintenance

### Daily Tasks

- Monitor dashboard for anomalies
- Review performance trends
- Check queue sizes
- Clear expired sessions

### Weekly Tasks

- Review team performance
- Analyze consensus patterns
- Update agent profiles
- Optimize configurations

### Monthly Tasks

- Review collaboration patterns
- Analyze cost-benefit
- Update capability scores
- Performance tuning

## Security

### Access Control

Configure in system settings:
- Agent registration: Admin only
- Team formation: Authenticated users
- Metrics viewing: All authenticated users

### Data Privacy

- Message logs: Configure retention
- Shared context: Encrypt sensitive data
- Performance data: Anonymize if needed

## Performance Tuning

### For High Throughput

```yaml
communication:
  queue_max_size: 2000
  max_messages_per_second: 2000

circuit_breakers:
  max_concurrent_teams: 100
```

### For Low Latency

```yaml
communication:
  latency_sla_ms: 25

team_formation:
  formation_timeout: 0.5
```

### For High Quality

```yaml
consensus:
  default_threshold: "supermajority"
  min_reviewers: 5

patterns:
  sequential:
    enable_all_quality_gates: true
```

## Scaling

### Horizontal Scaling

- Run multiple API instances
- Use external message queue (Redis/RabbitMQ)
- Shared state via database
- Load balancer for API requests

### Vertical Scaling

- Increase queue sizes
- More concurrent teams
- Larger cache
- More worker threads

## Support

For issues:
1. Check logs: `/var/log/ai-harness/collaboration.log`
2. Review metrics dashboard
3. Consult troubleshooting guide
4. Contact system administrator

