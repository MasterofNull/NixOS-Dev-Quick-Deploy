"""JSON reporter — output schema identical to the bash aq-qa --json format.

Schema:
{
  "phase": "0",
  "passed": N, "failed": N, "skipped": N, "duration_s": N,
  "degraded_confidence": bool,
  "tests": [{"layer": N, "id": "...", "status": "PASS|FAIL|SKIP", "description": "..."}],
  "layers": {"1": [...], "4": [...]}
}
"""
from __future__ import annotations

import json
import sys
from ..core.result import ResultSet


class JsonReporter:
    def render(self, rs: ResultSet) -> None:
        layers: dict[str, list] = {}
        tests = []
        for r in rs.results:
            item = {
                "layer": r.layer,
                "id": r.id,
                "status": r.status.value,
                "description": f"{r.description} ({r.reason})" if r.reason else r.description,
            }
            tests.append(item)
            layers.setdefault(str(r.layer), []).append(item)

        output = {
            "phase": rs.phase,
            "passed": rs.passed,
            "failed": rs.failed,
            "skipped": rs.skipped,
            "duration_s": rs.duration_s,
            "degraded_confidence": rs.degraded_confidence,
            "tests": tests,
            "layers": {k: v for k, v in sorted(layers.items(), key=lambda x: int(x[0]))},
        }
        print(json.dumps(output, indent=2))
