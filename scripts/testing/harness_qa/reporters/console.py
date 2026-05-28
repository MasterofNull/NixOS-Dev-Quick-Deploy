"""ANSI console reporter — output matches the bash aq-qa human-readable format."""
from __future__ import annotations

import sys
from ..core.result import ResultSet, Status

try:
    from rich.console import Console
    from rich.table import Table
    _RICH = True
except ImportError:
    _RICH = False

console = Console() if _RICH else None

class ConsoleReporter:
    def render(self, rs: ResultSet, machine_mode: bool = False) -> None:
        if machine_mode:
            for result in rs.results:
                if result.status == Status.FAIL:
                    print(f"FAIL {result.id} {result.description}")
            return

        if not _RICH:
            # Plain-text fallback when rich is not in the Python environment.
            print(f"\naq-qa phase {rs.phase}")
            print(f"{'ID':<16} {'Status':<6} Check")
            for result in rs.results:
                sym = "✓" if result.status == Status.PASS else ("✗" if result.status == Status.FAIL else "–")
                reason = f" ({result.reason})" if result.reason else ""
                print(f"{result.id:<16} {sym:<6} {result.description}{reason}")
            print(f"\n{rs.passed} passed · {rs.failed} failed · {rs.skipped} skipped · {rs.duration_s}s\n")
            return

        table = Table(title=f"aq-qa phase {rs.phase}", border_style="blue")
        table.add_column("Layer", style="dim")
        table.add_column("ID", style="bold")
        table.add_column("Check")
        table.add_column("Status", justify="center")

        prev_layer = None
        for result in rs.results:
            layer_str = f"L{result.layer}" if result.layer != prev_layer else ""
            prev_layer = result.layer

            desc = result.description
            if result.reason:
                desc = f"{desc} [dim]({result.reason})[/]"

            if result.status == Status.PASS:
                status_str = "[bold green]✓[/]"
            elif result.status == Status.FAIL:
                status_str = "[bold red]✗[/]"
            else:
                status_str = "[bold yellow]–[/]"

            table.add_row(layer_str, result.id, desc, status_str)

        console.print(table)

        if rs.causality_mode and rs.layer_filter > 0 and rs.failed > 0:
            console.print("[yellow]⚠ DEGRADED CONFIDENCE — lower-layer failures may invalidate results[/]")

        console.print(
            f"\n[green]{rs.passed} passed[/] · "
            f"[red]{rs.failed} failed[/] · "
            f"{rs.skipped} skipped · {rs.duration_s}s\n"
        )
