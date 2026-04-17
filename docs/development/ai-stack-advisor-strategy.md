# AI Advisor Strategy

Status: Implemented
Owner: AI Stack Team
Last Updated: 2026-04-17

## Overview

The AI Advisor Strategy integrates the [Anthropic advisor pattern](https://claude.com/blog/the-advisor-strategy) into the NixOS-Dev-Quick-Deploy AI harness. This strategy pairs cost-effective executor models with a frontier-level advisor model that provides guidance on complex decisions without executing them.

### Key Benefits

1. **Cost Efficiency**: Maintains lower-cost executors while accessing frontier reasoning when needed
2. **Improved Success Rate**: Provides expert guidance at critical decision points
3. **Proactive Consultation**: Detects complex decisions before attempting execution
4. **Multi-Model Support**: Works with remote APIs (Anthropic, OpenAI, Google) and local models

## Architecture

### Components

1. **Decision Point Detector** (`advisor_detector.py`)
   - Identifies when executor should consult advisor
   - Five decision types: architecture, security, ambiguity, tradeoff, planning
   - Confidence-based filtering (default threshold: 0.7)

2. **Advisor Invocation** (in `llm_router.py`)
   - Routes advisor requests through hybrid coordinator
   - Tracks advisor consultations separately from escalations
   - Respects max_uses limit per task

3. **Metrics & Observability**
   - Dedicated advisor_consultations table
   - Tracks: decision type, tokens, cost, success rate
   - Separate from failure escalation metrics

### Decision Types

| Type | Description | Example Signals |
|------|-------------|----------------|
| **Architecture** | Design patterns, system structure, API design | "design pattern", "architecture decision", "module design" |
| **Security** | Authentication, authorization, vulnerabilities | "authentication", "xss", "sql injection", "secure" |
| **Ambiguity** | Unclear requirements, multiple approaches | "unclear", "not sure", "which way", "alternative" |
| **Tradeoff** | Comparing alternatives, pros/cons | "versus", "tradeoff", "pros and cons", "which is better" |
| **Planning** | Multi-step workflows, roadmaps | "multi-step", "roadmap", "migration plan", "orchestration" |

## Configuration

See full documentation for complete configuration options, multi-model examples, and usage patterns.

Implementation files:
- `ai-stack/mcp-servers/hybrid-coordinator/advisor_detector.py`
- `ai-stack/mcp-servers/hybrid-coordinator/llm_router.py`
- `ai-stack/mcp-servers/hybrid-coordinator/config.py`
- `ai-stack/mcp-servers/hybrid-coordinator/test_advisor_detector.py`
- `.agent/workflows/advisor-strategy-design.md` (detailed design)

Reference: https://claude.com/blog/the-advisor-strategy
