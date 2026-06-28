---
name: understand-anything
description: Generate and use Understand-Anything codebase knowledge graphs, dashboard visualizations, diff impact overlays, and graph-backed explanations for this harness.
---

# Understand Anything

## Tags
understand-anything, knowledge-graph, visualization, architecture, dashboard, diff-impact, onboarding, codebase-clarity, operating-system-map

## When to Use
Use this skill when a task needs a visual or graph-backed understanding of the harness, NixOS configuration, service topology, agent orchestration, dashboard wiring, or change impact.

Use it for:
- Explaining how repo files, services, agents, dashboards, and Nix modules connect.
- Generating or refreshing `.understand-anything/knowledge-graph.json`.
- Launching the interactive graph dashboard.
- Answering architecture questions from the generated graph instead of re-reading the whole repo.
- Reviewing change blast radius before commits.
- Producing onboarding or subsystem maps for agents and humans.

## Upstream
This integrates Egonex-AI Understand-Anything, version 2.8.1 at the time of integration:
`https://github.com/Egonex-AI/Understand-Anything`

The upstream plugin provides these native skills after installation:
- `understand`: scan/analyze a repo into `.understand-anything/knowledge-graph.json`
- `understand-dashboard`: launch the interactive dashboard
- `understand-chat`: answer questions from the graph
- `understand-diff`: generate diff impact analysis and `.understand-anything/diff-overlay.json`
- `understand-explain`: deep dive into a file or symbol
- `understand-domain`: extract business/domain flow graphs
- `understand-onboard`: generate graph-backed onboarding

## Install or Sync
Before first use on a machine, run:

```bash
scripts/ai/aq-understand-anything ensure
```

By default this installs the upstream skills for the shared `.agents` skill directory used by Codex/Gemini-style agents and the Antigravity skill directory. To install only selected platforms:

```bash
scripts/ai/aq-understand-anything ensure codex gemini antigravity
```

Check availability and project graph state:

```bash
scripts/ai/aq-understand-anything status
```

## Agent Workflow
1. Start with `scripts/ai/aq-understand-anything status`.
2. If the plugin is missing, run `scripts/ai/aq-understand-anything ensure` or tell the user that installation requires network access.
3. If no graph exists, invoke the native upstream skill/command:
   - Claude Code: `/understand`
   - Codex/Gemini-compatible agents: load the upstream `understand` skill from `~/.agents/skills/understand/SKILL.md` and follow it.
4. For large harness-wide runs, prefer scoped analysis first:
   - `ai-stack/`
   - `nix/modules/`
   - `scripts/ai/`
   - `assets/` and `dashboard.html`
5. After generating the graph, use graph-backed answers before broad repo scans:
   - Query names, summaries, tags, layers, and edges in `.understand-anything/knowledge-graph.json`.
   - Cite concrete file nodes and edge relationships when explaining.
6. For change review, run the native `understand-diff` skill before commit-sensitive edits when graph data exists.
7. For visual inspection, run the native `understand-dashboard` skill or:

```bash
scripts/ai/aq-understand-anything dashboard
```

Always report the full dashboard URL including `?token=` when launching the dashboard.

## Harness-Specific Guidance
- Treat blank or missing graph/dashboard fields as visibility gaps. The graph is part of the measurement surface for the harness.
- Prefer graph refreshes after service, routing, dashboard, Nix module, or agent orchestration changes.
- Do not commit `.understand-anything/intermediate/`, `.understand-anything/tmp/`, `.understand-anything/diff-overlay.json`, or `.trash-*` scratch directories.
- Committing `.understand-anything/knowledge-graph.json` is acceptable only when intentionally sharing a refreshed graph snapshot.
- LLM-produced graph content is advisory. Verify security-sensitive, deploy-sensitive, and NixOS activation conclusions against source files and live checks.

## Useful Commands
```bash
# Install/sync upstream plugin links for shared agents.
scripts/ai/aq-understand-anything ensure

# Show plugin links, upstream checkout, and graph file state.
scripts/ai/aq-understand-anything status

# Launch dashboard for the current repo after /understand has generated a graph.
scripts/ai/aq-understand-anything dashboard

# Print dashboard launch command without starting it.
scripts/ai/aq-understand-anything dashboard-command
```
