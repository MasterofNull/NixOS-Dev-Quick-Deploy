#!/usr/bin/env python3
"""Regression checks for vectorization dashboard visibility."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AISTACK = ROOT / "dashboard/backend/api/routes/aistack.py"
DASHBOARD = ROOT / "dashboard.html"
JS = ROOT / "assets/dashboard.js"
QA = ROOT / "scripts/ai/_aq-qa-bash"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    api = read(AISTACK)
    html = read(DASHBOARD)
    js = read(JS)
    qa = read(QA)

    require('@router.get("/graph/vectorization")' in api, "missing vectorization posture route")
    require("get_vectorization_posture" in api, "missing posture route handler")
    require("knowledge_observatory()" in api, "posture route must reuse collection observatory")
    require("get_memory_collections()" in api, "posture route must include memory vectors")
    require("get_ragas_scores()" in api, "posture route must include RAGAS quality")

    require("vectorPostureBadge" in html, "missing vectorization posture dashboard badge")
    require("vectorPostureDetails" in html, "missing vectorization posture dashboard details")
    require('apiFetch("/graph/vectorization"' in js, "dashboard does not fetch posture endpoint")
    require("loadVectorizationPosture" in js, "missing vectorization posture renderer")
    require("loadVectorizationPosture();" in js, "map lens does not load posture renderer")

    require("0.10.31" in qa, "phase-0 QA missing vectorization visualization check")
    require("test-vectorization-visualization.py" in qa, "phase-0 QA missing focused test hook")

    print("ok vectorization visualization wiring")


if __name__ == "__main__":
    main()
