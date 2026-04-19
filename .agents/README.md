# `.agents/` Directory Structure

Unified workflow artifact management following strands-agents SOP pattern.

## Directory Layout

```
.agents/
├── summary/      # All final documentation, reports, analyses, audits
├── planning/     # All designs, plans, research, architectural decisions  
├── tasks/        # Task tracking, issues, checklists
└── scratchpad/   # Temporary work files (gitignored)
```

## Categories

### `summary/` - Final Documentation
**Git Policy**: Always commit

All completed workflows, final reports, and documentation:
- Workflow completion reports (brownfield PDRs, session summaries)
- Analysis results and findings
- Audit reports (`summary/audits/`)
- Performance optimization reports
- Decision records
- Post-mortem documentation

### `planning/` - Design & Strategy
**Git Policy**: Often commit

All planning, design, and preparatory work:
- Technical designs (`planning/designs/`)
- Implementation plans and roadmaps (`planning/plans/`)
- Research notes and investigations (`planning/research/`)
- Architecture decision records
- Strategy documents

### `tasks/` - Work Tracking
**Git Policy**: Optionally commit

Task management and issue tracking:
- Issue documentation and resolutions
- Sprint task lists
- Implementation checklists
- Bug tracking artifacts
- Test coverage plans

### `scratchpad/` - Temporary Work
**Git Policy**: Never commit (excluded in .gitignore)

Temporary working files:
- Draft notes
- Experimental code snippets
- Temporary analysis files
- Debug traces
- Work-in-progress research

## Usage

### Via MCP Client

```python
from mcp_client import get_mcp_client

client = get_mcp_client()

# Write summary
client.write_artifact("summary", "deployment-report.md", content)

# Write planning doc
client.write_artifact("planning", "architecture-design.md", content)

# List artifacts
summaries = client.list_artifacts("summary", "*.md")
```

### Direct File Access

```python
from pathlib import Path

# Read summary
report = Path(".agents/summary/deployment-report.md").read_text()

# Write planning doc
(Path(".agents/planning") / "new-design.md").write_text(content)
```

## Strands-Agents Pattern

This structure is inspired by [strands-agents/agent-sop](https://github.com/strands-agents/agent-sop):

**Key Principles**:
1. Clear separation between permanent and temporary artifacts
2. Git-friendly organization preserving important decisions
3. Consistent structure across workflows
4. Self-documenting hierarchy

**Integration**:
- SOP workflows write to appropriate categories
- Agent interface stores results in `summary/`
- Workflow graphs log to `summary/`
- Tool outputs saved based on permanence

## Migration from Legacy

**Old structure** (now consolidated):
- `.agent/workflows/` → `.agents/summary/`
- `.agents/reports/` → `.agents/summary/`
- `.agents/audits/` → `.agents/summary/audits/`
- `.agents/designs/` → `.agents/planning/designs/`
- `.agents/research/` → `.agents/planning/research/`
- `.agents/plans/` → `.agents/planning/plans/`
- `.agents/issues/` → `.agents/tasks/`

**Single unified pattern** - no parallel systems, no confusion.

## Related Documentation

- [50-STRANDS-INTEGRATION.md](../docs/agent-guides/50-STRANDS-INTEGRATION.md) - Integration guide
- [CLAUDE.md](../CLAUDE.md) - Agent behavior and workflow guidance
- [TOOL_DECORATORS.md](../ai-stack/local-orchestrator/TOOL_DECORATORS.md) - Tool system
