"""ANSI console reporter — output matches the bash aq-qa human-readable format."""
from __future__ import annotations

import sys
from ..core.result import ResultSet, Status

GREEN = "\033[0;32m"
RED = "\033[0;31m"
YELLOW = "\033[1;33m"
BLUE = "\033[0;34m"
NC = "\033[0m"


def _no_color() -> bool:
    import os
    return os.environ.get("NO_COLOR", "") != "" or not sys.stdout.isatty()


class ConsoleReporter:
    def render(self, rs: ResultSet) -> None:
        use_color = not _no_color()

        def c(code: str, text: str) -> str:
            return f"{code}{text}{NC}" if use_color else text

        print(f"\n{c(BLUE, f'━━━ aq-qa phase {rs.phase} ━━━')}")

        prev_layer = None
        for result in rs.results:
            if result.layer != prev_layer:
                print(c(BLUE, f"  [L{result.layer}]"))
                prev_layer = result.layer
            desc = result.description
            if result.reason:
                desc = f"{desc} ({result.reason})"
            if result.status == Status.PASS:
                print(f"  {c(GREEN, '✓')} {result.id:<16} {desc}")
            elif result.status == Status.FAIL:
                print(f"  {c(RED, '✗')} {result.id:<16} {desc}")
            else:
                print(f"  {c(YELLOW, '–')} {result.id:<16} {desc}")

        if rs.causality_mode and rs.layer_filter > 0 and rs.failed > 0:
            print(c(YELLOW,
                    f"\n⚠ DEGRADED CONFIDENCE — lower-layer failures may invalidate L{rs.layer_filter} results"))

        summary = (
            f"\n{c(GREEN, str(rs.passed))} passed · "
            f"{c(RED, str(rs.failed))} failed · "
            f"{rs.skipped} skipped · {rs.duration_s}s\n"
        )
        print(summary)
