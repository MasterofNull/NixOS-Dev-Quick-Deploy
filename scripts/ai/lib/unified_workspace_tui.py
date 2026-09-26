#!/usr/bin/env python3
"""
unified_workspace_tui — Dual-Board TUI fallback for aq-workspace.

Renders the automatically aligned dual-board agentic workspace in a terminal:
  ┌──────────────────────────────┬──────────────────────────────┐
  │ 󰚩 LEFT BOARD: MAIN AGENTS    │ 󰚩 RIGHT BOARD: SUB-AGENTS   │
  │ • Coordinator / Active Model │ • Sub-Agent Delegation Tree  │
  │ • Interactive Steering       ├──────────────────────────────┤
  │                              │ • Sub-Agent Live Operations  │
  └──────────────────────────────┴──────────────────────────────┘
"""

import argparse
import asyncio
import os
import sys
import time
from pathlib import Path

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "ai"))

from importlib.machinery import SourceFileLoader

def _load_script_module(script_path: Path, module_name: str):
    return SourceFileLoader(module_name, str(script_path)).load_module()

cockpit_mod = _load_script_module(REPO_ROOT / "scripts" / "ai" / "aq-cockpit-monitor", "aq_cockpit_monitor")
fleet_mod = _load_script_module(REPO_ROOT / "scripts" / "ai" / "aq-fleet-monitor", "aq_fleet_monitor")

render_cockpit = cockpit_mod.render_cockpit
render_fleet_panel = fleet_mod.render_fleet_panel
render_tree_panel = fleet_mod.render_tree_panel

console = Console()


def make_layout() -> Layout:
    """Create the dual-board workspace layout: Main Agents Left, Sub-Agents Right."""
    layout = Layout(name="root")
    layout.split_row(
        Layout(name="main_agents", ratio=5),
        Layout(name="sub_agents", ratio=5),
    )
    layout["sub_agents"].split_column(
        Layout(name="subagent_tree", ratio=5),
        Layout(name="subagent_ops", ratio=5),
    )
    return layout


def update_layout(layout: Layout):
    """Populate layout panes with live renderables."""
    coord_text = Text()
    coord_text.append("󰚩 LEFT BOARD — MAIN AGENT ORCHESTRATION\n", style="bold #00d9ff")
    coord_text.append("Active Models: Qwen3-35B (APU) · Claude 3.7 · Codex · Gemini 3.8\n\n", style="dim white")
    coord_text.append("Launch dedicated interactive floating window with:\n", style="white")
    coord_text.append("  $ aq-workspace agent claude\n", style="bold #ff79c6")
    coord_text.append("  $ aq-workspace agent codex\n", style="bold #50fa7b")
    coord_text.append("  $ aq-workspace agent gemini\n", style="bold #bd93f9")
    coord_text.append("  $ aq-workspace agent local\n", style="bold #00d9ff")
    coord_text.append("  $ aq-workspace agent <any-model-name>\n\n", style="bold #ffb86c")
    coord_text.append("Available Controls:\n", style="bold cyan")
    coord_text.append("  /subagents          View sub-agent hierarchy & tool calls\n", style="dim")
    coord_text.append("  /delegate <lane>    Spin off sub-agent to execute slice\n", style="dim")
    coord_text.append("  /model <name>       Switch active model dynamically\n", style="dim")
    coord_text.append("  /steer <id> <msg>   Inject steering instruction into sub-agent\n", style="dim")
    coord_text.append("  /kill <id>          Cancel running sub-agent task\n\n", style="dim")
    coord_text.append("Press Ctrl+C to return to shell.", style="dim italic")

    layout["main_agents"].update(Panel(coord_text, title="[bold #00d9ff]󰚩 Left Board: Main Agents[/bold #00d9ff]", border_style="#00d9ff"))
    layout["subagent_tree"].update(render_tree_panel())
    layout["subagent_ops"].update(render_fleet_panel())


def main():
    parser = argparse.ArgumentParser(description="AQ-OS Unified Dual-Board TUI")
    parser.add_argument("--once", action="store_true", help="Render single frame and exit")
    parser.add_argument("--interval", type=float, default=2.0, help="Refresh interval")
    args = parser.parse_args()

    layout = make_layout()
    update_layout(layout)

    if args.once or not sys.stdout.isatty():
        console.print(layout)
        return

    with Live(layout, refresh_per_second=2, console=console, screen=True) as live:
        try:
            while True:
                time.sleep(args.interval)
                update_layout(layout)
                live.update(layout)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
