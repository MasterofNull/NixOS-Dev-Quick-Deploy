#!/usr/bin/env python3
"""
unified_workspace_tui — Single-window Rich fallback TUI for aq-workspace.

Renders the multi-pane agentic workspace in a single terminal window:
  ┌──────────────────────────────┬──────────────────────────────┐
  │ 󰚩 Coordinator / Steering      │ 󰓅 Sub-Agent Fleet Matrix     │
  │                              ├──────────────────────────────┤
  │                              │ 󰒋 Telemetry Cockpit          │
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

console = Console()


def make_layout() -> Layout:
    """Create the 3-tile workspace layout."""
    layout = Layout(name="root")
    layout.split_row(
        Layout(name="coordinator", ratio=6),
        Layout(name="side", ratio=4),
    )
    layout["side"].split_column(
        Layout(name="fleet", ratio=5),
        Layout(name="cockpit", ratio=5),
    )
    return layout


def update_layout(layout: Layout):
    """Populate layout panes with live renderables."""
    # Coordinator placeholder/guide
    coord_text = Text()
    coord_text.append("󰚩 AQ-OS Agentic Coordinator\n", style="bold #00d9ff")
    coord_text.append("Active Lane: Local APU (Qwen3-35B)\n\n", style="dim white")
    coord_text.append("To start full interactive steering, launch without --tui:\n", style="white")
    coord_text.append("  $ aq-workspace\n\n", style="bold green")
    coord_text.append("Available Commands in REPL:\n", style="bold cyan")
    coord_text.append("  /model <name>      Switch model (local, claude, codex, gemini)\n", style="dim")
    coord_text.append("  /dispatch <role>   Spawn background sub-agent\n", style="dim")
    coord_text.append("  /steer <id> <msg>  Inject guidance into running agent\n", style="dim")
    coord_text.append("  /kill <id>         Cancel a running task\n", style="dim")
    coord_text.append("  /status            Print AI stack telemetry\n\n", style="dim")
    coord_text.append("Press Ctrl+C to return to shell.", style="dim italic")

    layout["coordinator"].update(Panel(coord_text, title="[bold #00d9ff]󰚩 Coordinator Console[/bold #00d9ff]", border_style="#00d9ff"))
    layout["fleet"].update(render_fleet_panel())
    layout["cockpit"].update(render_cockpit())


def main():
    parser = argparse.ArgumentParser(description="AQ-OS Unified Single-Window TUI")
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
