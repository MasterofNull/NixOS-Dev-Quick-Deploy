#!/usr/bin/env python3
"""Move hybrid-coordinator modules into domain subpackages with root shims."""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections import Counter
from pathlib import Path


DOMAIN_MAP: dict[str, str] = {
    # NOTE: http_server.py and server.py are kept at root (entrypoints).
    # They use Path(__file__).parent.parent.parent path arithmetic to locate
    # ai-stack/ siblings; moving them one level deeper would break those refs.
    # All other core/ modules are safe to move.
    "route_handler.py": "core",
    "route_aliases.py": "core",
    "routing_contract.py": "core",
    "config.py": "core",
    "metrics.py": "core",
    "auth_middleware.py": "core",
    "circuit_breaker.py": "core",
    "llm_client.py": "core",
    "session_builders.py": "core",
    "task_classifier.py": "core",
    "domain_router.py": "core",
    "lifecycle_fsm.py": "workflow",
    "intake_gateway.py": "workflow",
    "evidence_safety_handlers.py": "workflow",
    "safe_command_executor.py": "workflow",
    "runtime_manager.py": "workflow",
    "runtime_control_handlers.py": "workflow",
    "workflow_executor.py": "workflow",
    "workflow_planning.py": "workflow",
    "workflow_session_handlers.py": "workflow",
    "yaml_workflow_handlers.py": "workflow",
    "ops_handlers.py": "workflow",
    "prsi_handlers.py": "workflow",
    "orchestration_handlers.py": "workflow",
    "orchestration_utils.py": "workflow",
    "coordinator.py": "workflow",
    "delegation_handlers.py": "workflow",
    "delegation_feedback.py": "workflow",
    "agents_task_handlers.py": "workflow",
    "agent_registry.py": "workflow",
    "agent_capability_registry.py": "workflow",
    "hints_engine.py": "knowledge",
    "hints_handlers.py": "knowledge",
    "search_router.py": "knowledge",
    "query_expansion.py": "knowledge",
    "memory_manager.py": "knowledge",
    "memory_context_handlers.py": "knowledge",
    "agentic_memory_journal.py": "knowledge",
    "semantic_cache.py": "knowledge",
    "context_compression.py": "knowledge",
    "context_summary_handlers.py": "knowledge",
    "multi_turn_context.py": "knowledge",
    "embedder.py": "knowledge",
    "embedding_cache.py": "knowledge",
    "llm_router.py": "knowledge",
    "llm_router_handlers.py": "knowledge",
    "rag_reflection.py": "knowledge",
    "progressive_disclosure.py": "knowledge",
    "tooling_manifest.py": "knowledge",
    "capability_discovery.py": "knowledge",
    "collections_config.py": "knowledge",
    "continuous_learning.py": "extensions",
    "continuous_learning_daemon.py": "extensions",
    "real_time_learning_engine.py": "extensions",
    "affective_handlers.py": "extensions",
    "identity_handlers.py": "extensions",
    "federated_integration.py": "extensions",
    "federated_mcp_handlers.py": "extensions",
    "federation_sync.py": "extensions",
    "model_optimization.py": "extensions",
    "model_coordinator.py": "extensions",
    "model_fleet_manager.py": "extensions",
    "model_loader.py": "extensions",
    "model_probe.py": "extensions",
    "model_opt_handlers.py": "extensions",
    "openai_a2a_handlers.py": "extensions",
    "advanced_features.py": "extensions",
    "quality_cache.py": "extensions",
    "quality_monitor.py": "extensions",
    "auto_quality_improver.py": "extensions",
    "generator_critic.py": "extensions",
    "harness_eval.py": "extensions",
    "interaction_tracker.py": "extensions",
    "skill_usage_tracker.py": "extensions",
    "skill_validator.py": "extensions",
    "lesson_effectiveness_tracker.py": "extensions",
    "remediation_tracker.py": "extensions",
    "pattern_integration.py": "extensions",
    "auto_tool_select_handlers.py": "extensions",
    "mcp_handlers.py": "extensions",
    "ai_coordinator.py": "extensions",
    "ai_coordinator_handlers.py": "extensions",
    "trading_handlers.py": "extensions",
    "web_research.py": "extensions",
    "browser_research.py": "extensions",
    "research_workflows.py": "extensions",
    "remote_llm_feedback.py": "extensions",
    "harness_sdk.py": "extensions",
    "advisor_detector.py": "extensions",
    # garbage_collection.py was archived in Phase B.2 — not present
    "garbage_collector.py": "extensions",
    "prompt_injection.py": "extensions",
    "test_advisor_detector.py": "tests",
    "test_advisor_fallback_chains.py": "tests",
    "test_ai_coordinator_model_awareness.py": "tests",
    "test_config_local_system_prompt.py": "tests",
    "test_harness_eval_scorecard.py": "tests",
    "test_http_query_runtime_optimization.py": "tests",
    "test_http_server_delegated_message_optimization.py": "tests",
    "test_llm_client.py": "tests",
    "test_llm_router.py": "tests",
    "test_optimizations_simple.py": "tests",
    "test_qdrant_client_compat.py": "tests",
    "test_reasoning_profiles.py": "tests",
    "test_route_handler_optimizations.py": "tests",
    "test_search_router_reranking.py": "tests",
    "test_workflow_executor.py": "tests",
    "test_workflow_plan_optimization_watch.py": "tests",
    "test_workflow_run_blueprint_auto_selection.py": "tests",
}

DOMAIN_DIRS = ("core", "workflow", "knowledge", "extensions", "tests")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Move hybrid-coordinator Python modules into domain subdirectories.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned changes without modifying files.",
    )
    return parser.parse_args()


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def hybrid_coordinator_dir() -> Path:
    return repo_root() / "ai-stack" / "mcp-servers" / "hybrid-coordinator"


def ensure_package_dirs(base_dir: Path, dry_run: bool) -> list[Path]:
    created_or_checked: list[Path] = []
    for domain in DOMAIN_DIRS:
        package_dir = base_dir / domain
        init_path = package_dir / "__init__.py"
        created_or_checked.append(package_dir)
        created_or_checked.append(init_path)
        if dry_run:
            print(f"DRY-RUN mkdir -p {package_dir}")
            if init_path.exists():
                print(f"DRY-RUN keep existing {init_path}")
            else:
                print(f"DRY-RUN create empty {init_path}")
            continue
        package_dir.mkdir(parents=True, exist_ok=True)
        init_path.touch(exist_ok=True)
    return created_or_checked


def run_git_mv(source: Path, target: Path, cwd: Path, dry_run: bool) -> None:
    command = ["git", "mv", str(source), str(target)]
    if dry_run:
        print("DRY-RUN", " ".join(command))
        return
    subprocess.run(command, cwd=cwd, check=True)


def write_shim(shim_path: Path, domain: str, module_name: str, dry_run: bool) -> None:
    # Absolute import (no leading dot) — hybrid-coordinator/ is on sys.path directly,
    # so relative imports would fail with "no known parent package".
    shim_line = f"from {domain}.{module_name} import *  # noqa: F401,F403\n"
    if dry_run:
        print(f"DRY-RUN shim {shim_path.name} → {shim_line.strip()}")
        return
    shim_path.write_text(shim_line, encoding="utf-8")


def main() -> int:
    args = parse_args()
    repo = repo_root()
    base_dir = hybrid_coordinator_dir()

    if not base_dir.exists():
        print(f"hybrid-coordinator directory not found: {base_dir}", file=sys.stderr)
        return 1

    ensure_package_dirs(base_dir, args.dry_run)

    moved_counts: Counter[str] = Counter()
    missing_sources: list[str] = []
    skipped_targets: list[str] = []

    for filename, domain in DOMAIN_MAP.items():
        source_path = base_dir / filename
        target_path = base_dir / domain / filename
        module_name = Path(filename).stem

        if not source_path.exists():
            missing_sources.append(filename)
            message = f"missing source: {source_path}"
            if args.dry_run:
                print(f"DRY-RUN skip {message}")
            else:
                print(f"WARNING {message}")
            continue

        if target_path.exists():
            skipped_targets.append(filename)
            message = f"target already exists: {target_path}"
            if args.dry_run:
                print(f"DRY-RUN skip {message}")
            else:
                print(f"WARNING {message}")
            continue

        run_git_mv(source_path, target_path, repo, args.dry_run)
        write_shim(base_dir / filename, domain, module_name, args.dry_run)
        moved_counts[domain] += 1

    total_planned = sum(moved_counts.values())
    mode = "DRY-RUN summary" if args.dry_run else "Migration summary"
    print(f"\n{mode}")
    print(f"  repo root: {repo}")
    print(f"  hybrid-coordinator: {base_dir}")
    print(f"  planned moves: {total_planned}")
    for domain in DOMAIN_DIRS:
        print(f"  {domain}: {moved_counts[domain]}")
    if missing_sources:
        print(f"  missing sources: {len(missing_sources)}")
        for filename in missing_sources:
            print(f"    - {filename}")
    if skipped_targets:
        print(f"  skipped existing targets: {len(skipped_targets)}")
        for filename in skipped_targets:
            print(f"    - {filename}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
