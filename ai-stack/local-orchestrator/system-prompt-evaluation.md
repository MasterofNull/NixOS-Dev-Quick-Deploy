# System Prompt Optimization Analysis

**Date:** 2026-04-19
**Version:** v1 → v2-optimized
**Target Model:** Gemma 4 E4B (7.5B parameters, quantized Q4_K_M)

---

## Executive Summary

Optimized system prompt from 216 lines to 84 lines (61% reduction) while maintaining all critical capabilities. Tailored specifically for Gemma 4 E4B's constraints and strengths.

---

## Comparison

| Metric | v1 (Original) | v2 (Optimized) | Improvement |
|--------|---------------|----------------|-------------|
| **Total Lines** | 216 | 84 | **61% reduction** |
| **Word Count** | ~1,450 | ~520 | **64% reduction** |
| **Token Estimate** | ~2,100 | ~750 | **64% reduction** |
| **JSON Examples** | 3 complex | 0 | **Simplified** |
| **Sections** | 11 | 9 | **Streamlined** |
| **Cognitive Load** | High | Low | **Reduced** |

---

## Optimization Strategy

### 1. Removed Verbose Sections

**Removed:**
- Detailed JSON response schemas (3 examples, ~60 lines)
- Extensive delegation protocol details (~40 lines)
- Intent contract template (~20 lines)
- Redundant explanations

**Rationale:** Smaller models struggle with complex structured output. Clear natural language instructions work better than JSON schemas.

### 2. Simplified Tool Descriptions

**Before (v1):**
```
- `workflow_run_start(query, safety_mode, token_limit, tool_call_limit,
   intent_contract, blueprint_id, orchestration_policy, isolation_profile,
   workspace_root, network_policy)` - Start guarded workflow...
```

**After (v2):**
```
- `workflow_run_start(query)` - Execute workflow
```

**Rationale:** Showing all parameters overwhelming for smaller models. They'll discover parameters via MCP tool schemas when needed.

### 3. Consolidated Delegation Rules

**Before (v1):**
- Delegation routing table
- Delegation protocol (5 steps)
- Delegation guardrails (2 lists)

**After (v2):**
- Single clear "Routing Rules" section
- Emphasis on "delegation is expensive"
- Simple decision tree

**Rationale:** Reduce cognitive load. Make the decision process clearer.

### 4. Simplified Response Format

**Before (v1):**
- 3 different JSON schemas
- Complex nested structures
- Multiple response types with templates

**After (v2):**
- Natural language guidelines
- Simple bullet points
- Focus on behavior, not structure

**Rationale:** Gemma 4 better at following behavioral instructions than strict schema compliance.

### 5. Added Clear Workflow

**New in v2:**
1. Understand
2. Search
3. Decide
4. Execute
5. Validate

**Rationale:** Step-by-step process easier for smaller models to follow than abstract principles.

---

## Key Improvements

### Cognitive Load Reduction

**v1 Issues:**
- Information overload (11 sections)
- Complex examples (JSON schemas)
- Redundant information across sections
- Abstract concepts without concrete steps

**v2 Solutions:**
- Streamlined to 9 focused sections
- No JSON schemas
- Each section has one clear purpose
- Concrete workflow steps

### Focus on Core Capabilities

**Prioritized:**
- Tool usage (most critical)
- Routing decisions (core responsibility)
- Search-first approach (leverage RAG)
- Validation steps (quality gate)

**De-emphasized:**
- Complex delegation protocols
- Budget tracking details
- Error handling edge cases
- Intent contract formalism

### Better Model Alignment

**Gemma 4 E4B Strengths:**
- Good at following clear instructions
- Strong at tool use with MCP
- Can handle sequential tasks well
- Effective with concrete examples

**Gemma 4 E4B Limitations:**
- Struggles with complex structured output
- Context window constraints (13

1K tokens)
- Limited reasoning about abstract concepts
- Quantization affects precision

**v2 Optimizations:**
- Simple, clear instructions (strength)
- MCP tool focus (strength)
- Step-by-step workflow (strength)
- Minimal structured output (limitation)
- Reduced token count (limitation)
- Concrete guidelines vs abstractions (limitation)

---

## Removed Features & Rationale

### 1. Intent Contract Template
**Why removed:** Too formal for smaller model, adds complexity without clear benefit

### 2. Detailed JSON Response Schemas
**Why removed:** Models don't need schemas in prompts - better to give behavioral guidance

### 3. Extensive Delegation Protocol
**Why removed:** Simplified to essential decision criteria - smaller model shouldn't track complex multi-step protocols

### 4. Memory Type Details
**Why removed:** Can be inferred from context or provided when storing

### 5. Token Budget Specifics
**Why removed:** Budget tracked externally, model doesn't need exact dollar amounts

---

## Retained Critical Features

✅ **Core Identity** - Model knows its role and capabilities
✅ **Essential Tools** - All MCP tools documented
✅ **Routing Rules** - Clear delegation criteria
✅ **Task Workflow** - Step-by-step execution process
✅ **Response Guidelines** - How to handle different scenarios
✅ **Critical Constraints** - Security, validation, git discipline
✅ **Validation Checklist** - Quality gates
✅ **Git Commit Format** - Essential for proper history

---

## Expected Improvements

### Performance Metrics

**Context Window Usage:**
- Before: ~2,100 tokens consumed by system prompt
- After: ~750 tokens consumed by system prompt
- **Savings: 1,350 tokens** available for task context

**Comprehension:**
- Simpler instructions → better understanding
- Clear workflow → more consistent behavior
- Fewer abstractions → less confusion

**Response Quality:**
- Focus on core capabilities → better execution
- Clearer routing rules → better delegation decisions
- Step-by-step process → fewer mistakes

### Validation Plan

Test the optimized prompt with:

1. **Simple queries** (should handle locally)
   - "What is the current git status?"
   - "Search for authentication code"
   - "List available workflows"

2. **Medium complexity** (search + synthesis)
   - "How does the hybrid coordinator route requests?"
   - "Find all references to memory storage"
   - "Explain the delegation protocol"

3. **Complex tasks** (should delegate)
   - "Implement a new route alias system"
   - "Refactor the memory manager"
   - "Add security audit logging"

4. **Planning tasks** (use workflow_plan)
   - "Create a plan to add caching"
   - "Design the architecture for feature X"

**Success Criteria:**
- Simple queries: 90%+ handled correctly locally
- Medium complexity: 80%+ good synthesis with search
- Complex tasks: 90%+ correct delegation decisions
- Planning: 85%+ useful workflow plans

---

## Rollback Plan

If v2 performs worse than v1:

1. **Immediate:** Switch back to v1 system prompt file
2. **Measure:** Collect specific failure examples
3. **Iterate:** Create v2.1 with targeted fixes
4. **Test:** Validate v2.1 before redeploying

**Rollback is simple:**
```bash
# Revert to v1
cp ai-stack/local-orchestrator/system-prompt.md \
   ai-stack/local-orchestrator/system-prompt-active.md

# Restart orchestrator
# (or configure to use system-prompt.md directly)
```

---

## A/B Testing Plan

### Test Corpus (20 prompts across categories)

**Category 1: Simple Queries (5 prompts)**
1. "What's in the README?"
2. "Show git status"
3. "List available MCP tools"
4. "Search for 'authentication' in the codebase"
5. "What workflows are available?"

**Category 2: Context Synthesis (5 prompts)**
1. "How does routing work in the coordinator?"
2. "Explain the memory system architecture"
3. "What's the purpose of the hints engine?"
4. "How do I add a new workflow?"
5. "What validation checks are required?"

**Category 3: Delegation Decisions (5 prompts)**
1. "Implement a new cache layer for AIDB"
2. "Add logging to all API endpoints"
3. "Refactor the search router for better performance"
4. "Create unit tests for the memory manager"
5. "Add security headers to HTTP responses"

**Category 4: Planning (5 prompts)**
1. "Plan implementation of distributed caching"
2. "Design a monitoring dashboard"
3. "Create workflow for onboarding new models"
4. "Plan security hardening improvements"
5. "Design integration test framework"

### Metrics

For each prompt, measure:
- **Correctness** (0-5 scale)
- **Completeness** (0-5 scale)
- **Response Time** (seconds)
- **Tool Usage** (count and appropriateness)
- **Delegation Decision** (correct/incorrect, if applicable)

### Comparison

Run both v1 and v2 through the test corpus:
- **v1 baseline:** Establish current performance
- **v2 optimized:** Measure improvements
- **Delta analysis:** Identify wins and regressions

**Target Improvements:**
- Correctness: maintain 90%+ (no regression)
- Completeness: maintain 85%+ (no regression)
- Response Time: improve 20-30% (fewer tokens to process)
- Tool Usage: improve relevance by 15%
- Delegation: improve accuracy by 25%

---

## Implementation Notes

### Deployment

1. Create v2 system prompt ✅ (this file)
2. Create evaluation doc ✅ (this document)
3. Create test framework ⏳ (next step)
4. Run A/B tests ⏳
5. Analyze results ⏳
6. Deploy if successful ⏳

### Configuration

The orchestrator loads system prompt from:
```python
# In orchestrator.py
prompt_path = Path(__file__).parent / "system-prompt.md"
```

To use v2-optimized:
- Option A: Rename `system-prompt-v2-optimized.md` → `system-prompt.md`
- Option B: Update `orchestrator.py` to load v2 filename
- Option C: Use feature flag to switch between versions

---

## Conclusion

The v2-optimized prompt reduces complexity by 61% while retaining all critical capabilities. It's specifically tailored for Gemma 4 E4B's strengths (clear instructions, tool use, sequential tasks) and limitations (context window, structured output, abstract reasoning).

Expected improvements:
- ✅ 64% reduction in system prompt tokens
- ✅ Better comprehension (simpler language)
- ✅ Faster response times (less to process)
- ✅ More consistent behavior (clear workflow)
- ✅ Better tool usage (focused guidance)

Next steps:
1. Create test framework
2. Run A/B testing
3. Validate improvements
4. Deploy if successful

---

**Document Version:** 1.0.0
**Author:** Claude Sonnet 4.5
**Status:** Ready for Testing
**Next:** Create test framework and run validation
