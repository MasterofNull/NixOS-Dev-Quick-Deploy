"""
AI Insights Service
Provides analytics and insights from the AI stack's operational data.
Integrates with aq-report for comprehensive system intelligence.
"""

import asyncio
import subprocess
import json
import logging
import os
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

from api.config.service_endpoints import HYBRID_URL
from api.services.runtime_controls import get_dashboard_rate_limiter, get_operator_audit_log

logger = logging.getLogger(__name__)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _phase4_acceptance_report_path() -> Path:
    configured = os.getenv("PHASE4_ACCEPTANCE_REPORT_PATH", "").strip()
    if configured:
        return Path(configured)
    return _repo_root() / ".reports" / "phase-4-acceptance-report.json"


def _reviewer_gate_checklist_path() -> Path:
    configured = os.getenv("REVIEWER_GATE_CHECKLIST_PATH", "").strip()
    if configured:
        return Path(configured)
    reports_dir = _repo_root() / ".reports"
    candidates = sorted(reports_dir.glob("reviewer-gate-checklist-*.md"))
    if candidates:
        return candidates[-1]
    return reports_dir / "reviewer-gate-checklist-latest.md"


def _persisted_aq_report_path() -> Path:
    configured = os.getenv("DASHBOARD_AI_INSIGHTS_REPORT_PATH", "").strip()
    if configured:
        return Path(configured)
    return Path("/var/lib/ai-stack/hybrid/telemetry/latest-aq-report.json")


def _optimization_proposals_path() -> Path:
    configured = os.getenv("DASHBOARD_OPTIMIZATION_PROPOSALS_PATH", "").strip()
    if configured:
        return Path(configured)
    configured = os.getenv("OPTIMIZATION_PROPOSALS_PATH", "").strip()
    if configured:
        return Path(configured)
    return Path("/var/lib/ai-stack/hybrid/telemetry/optimization_proposals.jsonl")


def _improvement_candidates_path() -> Path:
    configured = os.getenv("DASHBOARD_IMPROVEMENT_CANDIDATES_PATH", "").strip()
    if configured:
        return Path(configured)
    return _repo_root() / ".agents" / "improvement" / "candidates.json"


def _code_review_results_path() -> Path:
    configured = os.getenv("DASHBOARD_CODE_REVIEW_RESULTS_PATH", "").strip()
    if configured:
        return Path(configured)
    return _repo_root() / ".agents" / "reviews" / "code-review.json"


def _prometheus_metric_sum(metrics_text: str, metric_name: str) -> Optional[float]:
    total = 0.0
    matched = False
    prefix = f"{metric_name}"
    for line in metrics_text.splitlines():
        if not line or line.startswith("#") or not line.startswith(prefix):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        try:
            total += float(parts[-1])
            matched = True
        except ValueError:
            continue
    return total if matched else None


def _prometheus_metric_scalar(metrics_text: str, metric_name: str) -> Optional[float]:
    prefix = f"{metric_name}"
    for line in metrics_text.splitlines():
        if not line or line.startswith("#") or not line.startswith(prefix):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        try:
            return float(parts[-1])
        except ValueError:
            continue
    return None

class AIInsightsService:
    """Service for AI stack insights and analytics."""

    def __init__(self):
        self._persisted_report_path = _persisted_aq_report_path()
        self._cache: Optional[Dict[str, Any]] = None
        self._cache_timestamp: Optional[datetime] = None
        self._cache_ttl_seconds = 60  # 1 minute cache
        self._report_lock = asyncio.Lock()
        self._report_task: Optional[asyncio.Task[Dict[str, Any]]] = None
        self._seed_cache_from_persisted_report()

    async def get_full_report(self) -> Dict[str, Any]:
        """Get the complete aq-report data."""
        if self._is_cache_valid():
            return self._cache

        try:
            task = await self._get_or_start_report_task()
            return await asyncio.shield(task)
        except RuntimeError:
            stale = self._get_cached_report(max_age_seconds=None)
            if stale is not None:
                logger.warning("Serving stale aq-report cache after refresh failure")
                return stale
            persisted = self._load_persisted_report()
            if persisted is not None:
                logger.warning("Serving persisted aq-report snapshot after refresh failure")
                return persisted
            raise

    async def _get_or_start_report_task(self) -> asyncio.Task[Dict[str, Any]]:
        """Share one in-flight aq-report refresh across concurrent dashboard requests."""
        async with self._report_lock:
            if self._is_cache_valid():
                return asyncio.create_task(self._return_cached_report())
            if self._report_task is None or self._report_task.done():
                self._report_task = asyncio.create_task(self._refresh_report())
            return self._report_task

    async def _return_cached_report(self) -> Dict[str, Any]:
        if self._cache is None:
            raise RuntimeError("AI insights cache is empty")
        return self._cache

    async def _refresh_report(self) -> Dict[str, Any]:
        try:
            result = await asyncio.to_thread(
                subprocess.run,
                ["python3", "/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/scripts/ai/aq-report", "--format=json"],
                capture_output=True,
                text=True,
                check=True,
                timeout=60,
            )

            data = json.loads(result.stdout)
            self._update_cache(data, timestamp=datetime.now(timezone.utc), persist=True)
            return data
        except subprocess.TimeoutExpired as exc:
            logger.error("aq-report execution timed out: %s", exc)
            raise RuntimeError("AI insights report generation timed out") from exc
        except subprocess.CalledProcessError as exc:
            logger.error("aq-report execution failed: %s", exc.stderr)
            raise RuntimeError(f"Failed to generate AI insights report: {exc.stderr}") from exc
        except json.JSONDecodeError as exc:
            logger.error("Failed to parse aq-report JSON: %s", exc)
            raise RuntimeError(f"Invalid JSON from aq-report: {exc}") from exc
        finally:
            async with self._report_lock:
                if self._report_task is not None and self._report_task.done():
                    self._report_task = None

    def _get_cached_report(self, max_age_seconds: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Return cached report payload if it is newer than the supplied age limit."""
        if self._cache is None or self._cache_timestamp is None:
            return None
        age = (datetime.now(timezone.utc) - self._cache_timestamp).total_seconds()
        if max_age_seconds is not None and age >= max_age_seconds:
            return None
        return self._cache

    def _is_cache_valid(self) -> bool:
        """Check if cached data is still valid."""
        return self._get_cached_report(max_age_seconds=self._cache_ttl_seconds) is not None

    def _seed_cache_from_persisted_report(self) -> None:
        """Warm the in-memory cache from the last persisted aq-report snapshot after restart."""
        persisted = self._load_persisted_report()
        if persisted is None:
            return
        logger.info("Seeded dashboard insights cache from %s", self._persisted_report_path)

    def _load_persisted_report(self) -> Optional[Dict[str, Any]]:
        if not self._persisted_report_path.exists():
            return None
        try:
            raw = json.loads(self._persisted_report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Failed to load persisted aq-report snapshot %s: %s", self._persisted_report_path, exc)
            return None
        if not isinstance(raw, dict):
            return None
        ts = self._entry_timestamp(raw) or datetime.fromtimestamp(
            self._persisted_report_path.stat().st_mtime,
            tz=timezone.utc,
        )
        self._update_cache(raw, timestamp=ts, persist=False)
        return raw

    def _persist_report(self, report: Dict[str, Any]) -> None:
        try:
            self._persisted_report_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = self._persisted_report_path.with_name(f"{self._persisted_report_path.name}.tmp")
            temp_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            temp_path.replace(self._persisted_report_path)
        except OSError as exc:
            logger.warning("Failed to persist aq-report snapshot to %s: %s", self._persisted_report_path, exc)

    def _update_cache(self, report: Dict[str, Any], *, timestamp: datetime, persist: bool) -> None:
        self._cache = report
        self._cache_timestamp = timestamp
        if persist:
            self._persist_report(report)

    def _entry_timestamp(self, report: Dict[str, Any]) -> Optional[datetime]:
        raw = report.get("generated_at")
        if not raw:
            return None
        try:
            normalized = str(raw).replace("Z", "+00:00")
            dt = datetime.fromisoformat(normalized)
        except ValueError:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    def _load_recent_optimization_history(self, limit: int = 25) -> Dict[str, Any]:
        """Load a bounded summary of recent optimization proposals from telemetry."""
        path = _optimization_proposals_path()
        if limit <= 0:
            limit = 1
        if not path.exists():
            return {
                "available": False,
                "path": str(path),
                "total_recent": 0,
                "recent": [],
                "types": {},
                "target_keys": {},
                "last_proposal_at": None,
            }

        entries: List[Dict[str, Any]] = []
        try:
            with path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    raw_line = line.strip()
                    if not raw_line:
                        continue
                    try:
                        payload = json.loads(raw_line)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(payload, dict):
                        entries.append(payload)
        except OSError as exc:
            logger.warning("Failed to load optimization proposal history from %s: %s", path, exc)
            return {
                "available": False,
                "path": str(path),
                "total_recent": 0,
                "recent": [],
                "types": {},
                "target_keys": {},
                "last_proposal_at": None,
                "error": str(exc),
            }

        recent_entries = entries[-limit:]
        type_counts: Dict[str, int] = {}
        target_key_counts: Dict[str, int] = {}
        recent: List[Dict[str, Any]] = []
        last_proposal_at: Optional[str] = None

        for entry in reversed(recent_entries):
            proposal_type = str(entry.get("proposal_type") or "unknown")
            target_key = str(entry.get("target_config_key") or "unknown")
            type_counts[proposal_type] = type_counts.get(proposal_type, 0) + 1
            target_key_counts[target_key] = target_key_counts.get(target_key, 0) + 1
            recent.append(
                {
                    "proposal_type": proposal_type,
                    "target_config_key": target_key,
                    "current_value": entry.get("current_value"),
                    "proposed_value": entry.get("proposed_value"),
                    "confidence": entry.get("confidence"),
                    "evidence_summary": entry.get("evidence_summary"),
                    "proposal_hash": entry.get("proposal_hash"),
                }
            )

        if recent:
            last_proposal_at = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()

        return {
            "available": True,
            "path": str(path),
            "total_recent": len(recent),
            "recent": recent,
            "types": type_counts,
            "target_keys": target_key_counts,
            "last_proposal_at": last_proposal_at,
        }

    def _load_improvement_candidates_summary(self, limit: int = 5) -> Dict[str, Any]:
        """Load a bounded summary of persisted improvement candidates."""
        path = _improvement_candidates_path()
        if not path.exists():
            return {
                "available": False,
                "path": str(path),
                "status": "pending",
                "total_candidates": 0,
                "top_candidates": [],
                "categories": {},
                "priority_counts": {},
                "generated_at": None,
            }

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Failed to load improvement candidates from %s: %s", path, exc)
            return {
                "available": False,
                "path": str(path),
                "status": "error",
                "total_candidates": 0,
                "top_candidates": [],
                "categories": {},
                "priority_counts": {},
                "generated_at": None,
                "error": str(exc),
            }

        raw_candidates = payload.get("candidates", []) if isinstance(payload, dict) else []
        categories: Dict[str, int] = {}
        priority_counts: Dict[str, int] = {}
        top_candidates: List[Dict[str, Any]] = []

        for item in raw_candidates:
            if not isinstance(item, dict):
                continue
            category = str(item.get("category") or "unknown")
            priority = int(item.get("priority", 0) or 0)
            categories[category] = categories.get(category, 0) + 1
            priority_key = str(priority or "unknown")
            priority_counts[priority_key] = priority_counts.get(priority_key, 0) + 1

        for item in raw_candidates[:limit]:
            if not isinstance(item, dict):
                continue
            top_candidates.append(
                {
                    "title": item.get("title"),
                    "category": item.get("category"),
                    "priority": item.get("priority"),
                    "estimated_impact": item.get("estimated_impact"),
                    "effort": item.get("effort"),
                    "related_files": item.get("related_files", [])[:5],
                }
            )

        status = "active" if top_candidates else "pending"
        if any(int(item.get("priority", 9) or 9) <= 2 for item in raw_candidates if isinstance(item, dict)):
            status = "watch"

        return {
            "available": True,
            "path": str(path),
            "status": status,
            "total_candidates": int(payload.get("total_candidates", len(raw_candidates)) or len(raw_candidates)),
            "top_candidates": top_candidates,
            "categories": categories,
            "priority_counts": priority_counts,
            "generated_at": payload.get("generated_at"),
        }

    def _load_improvement_automation_readiness(self) -> Dict[str, Any]:
        """Inspect repo-native self-improvement automation coverage."""
        root = _repo_root()
        detector = root / "ai-stack" / "self-improvement" / "improvement_detector.py"
        reviewer = root / "ai-stack" / "self-improvement" / "llm_code_reviewer.py"
        online_learning = root / "ai-stack" / "real-time-learning" / "online_learning.py"

        def _contains(path: Path, needle: str) -> bool:
            try:
                return needle in path.read_text(encoding="utf-8")
            except OSError:
                return False

        features = {
            "code_smell_detection": detector.exists() and _contains(detector, "class CodeSmellDetector"),
            "performance_regression_detection": detector.exists() and _contains(detector, "class PerformanceRegressionDetector"),
            "improvement_candidate_generation": detector.exists() and _contains(detector, "class ImprovementCandidateGenerator"),
            "telemetry_pattern_mining": online_learning.exists() and _contains(online_learning, "class LivePatternMiner"),
            "llm_code_review": reviewer.exists() and _contains(reviewer, "class LLMCodeReviewer"),
        }
        enabled_count = sum(1 for enabled in features.values() if enabled)
        status = "pending"
        if enabled_count > 0:
            status = "active"
        if enabled_count >= 4:
            status = "watch"

        return {
            "available": enabled_count > 0,
            "status": status,
            "feature_count": enabled_count,
            "features": features,
            "paths": {
                "detector": str(detector),
                "reviewer": str(reviewer),
                "online_learning": str(online_learning),
            },
        }

    def _load_code_review_summary(self, limit: int = 5) -> Dict[str, Any]:
        """Load a bounded summary of persisted LLM code-review results."""
        path = _code_review_results_path()
        if not path.exists():
            return {
                "available": False,
                "path": str(path),
                "status": "pending",
                "reviewed_at": None,
                "reviewer": None,
                "total_files": 0,
                "average_quality": None,
                "severity_counts": {},
                "category_counts": {},
                "top_findings": [],
            }

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Failed to load code review results from %s: %s", path, exc)
            return {
                "available": False,
                "path": str(path),
                "status": "error",
                "reviewed_at": None,
                "reviewer": None,
                "total_files": 0,
                "average_quality": None,
                "severity_counts": {},
                "category_counts": {},
                "top_findings": [],
                "error": str(exc),
            }

        files = payload.get("files", []) if isinstance(payload, dict) else []
        severity_counts: Dict[str, int] = {}
        category_counts: Dict[str, int] = {}
        qualities: List[float] = []
        top_findings: List[Dict[str, Any]] = []

        for item in files:
            if not isinstance(item, dict):
                continue
            quality = item.get("overall_quality")
            if isinstance(quality, (int, float)):
                qualities.append(float(quality))
            for comment in item.get("comments", []) or []:
                if not isinstance(comment, dict):
                    continue
                severity = str(comment.get("severity") or "unknown")
                category = str(comment.get("category") or "unknown")
                severity_counts[severity] = severity_counts.get(severity, 0) + 1
                category_counts[category] = category_counts.get(category, 0) + 1
                if len(top_findings) < limit:
                    top_findings.append(
                        {
                            "file_path": item.get("file_path"),
                            "line": comment.get("line"),
                            "severity": severity,
                            "category": category,
                            "message": comment.get("message"),
                            "suggestion": comment.get("suggestion"),
                        }
                    )

        status = "active" if files else "pending"
        if severity_counts.get("critical", 0) > 0 or severity_counts.get("major", 0) > 0:
            status = "watch"

        average_quality = round(sum(qualities) / len(qualities), 4) if qualities else None
        return {
            "available": True,
            "path": str(path),
            "status": status,
            "reviewed_at": payload.get("reviewed_at"),
            "reviewer": payload.get("reviewer"),
            "total_files": int(payload.get("total_files", len(files)) or len(files)),
            "average_quality": average_quality,
            "severity_counts": severity_counts,
            "category_counts": category_counts,
            "top_findings": top_findings,
        }

    def _load_testing_validation_readiness(self) -> Dict[str, Any]:
        """Inspect repo-native Phase 3.2 testing and validation framework coverage."""
        root = _repo_root()
        property_tests = root / "ai-stack" / "testing" / "property_based_tests.py"
        chaos_tests = root / "ai-stack" / "testing" / "chaos_engineering.py"
        benchmarks = root / "ai-stack" / "testing" / "performance_benchmarks.py"
        canary_suite = root / "scripts" / "automation" / "run-prsi-canary-suite.sh"

        def _contains(path: Path, needle: str) -> bool:
            try:
                return needle in path.read_text(encoding="utf-8")
            except OSError:
                return False

        features = {
            "property_based_testing": property_tests.exists() and _contains(property_tests, "hypothesis"),
            "chaos_engineering": chaos_tests.exists() and _contains(chaos_tests, "ChaosExperimentType"),
            "performance_benchmarks": benchmarks.exists() and _contains(benchmarks, "BenchmarkComparison"),
            "canary_automation": canary_suite.exists() or _contains(root / "ai-stack" / "deployment" / "auto_deployer.py", "_deploy_canary"),
        }
        enabled_count = sum(1 for enabled in features.values() if enabled)
        status = "active" if enabled_count > 0 else "pending"
        if enabled_count >= 3:
            status = "watch"

        return {
            "available": enabled_count > 0,
            "status": status,
            "feature_count": enabled_count,
            "features": features,
            "paths": {
                "property_based_testing": str(property_tests),
                "chaos_engineering": str(chaos_tests),
                "performance_benchmarks": str(benchmarks),
                "canary_automation": str(canary_suite),
            },
        }

    def _load_deployment_pipeline_readiness(self) -> Dict[str, Any]:
        """Inspect repo-native Phase 3.3 deployment pipeline coverage."""
        path = _repo_root() / "ai-stack" / "deployment" / "auto_deployer.py"
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as exc:
            return {
                "available": False,
                "status": "pending",
                "path": str(path),
                "error": str(exc),
                "features": {},
            }

        features = {
            "safe_auto_deployment": "class AutoDeployer" in content and "_run_validation" in content,
            "blue_green": "_deploy_blue_green" in content,
            "rollback": "_rollback" in content and "--rollback" in content,
            "gradual_rollout_metrics": "_deploy_canary" in content and "canary_percentage" in content,
            "approval_gate": "require_approval" in content and "_request_approval" in content,
        }
        enabled_count = sum(1 for enabled in features.values() if enabled)
        status = "active" if enabled_count > 0 else "pending"
        if enabled_count >= 4:
            status = "watch"

        return {
            "available": enabled_count > 0,
            "status": status,
            "path": str(path),
            "feature_count": enabled_count,
            "features": features,
        }

    def _load_agentic_pattern_library_readiness(self) -> Dict[str, Any]:
        """Inspect repo-native Phase 4.1 agentic pattern library coverage."""
        root = _repo_root()
        react_path = root / "ai-stack" / "agentic-patterns" / "react_pattern.py"
        tot_path = root / "ai-stack" / "agentic-patterns" / "tree_of_thoughts.py"
        reflexion_path = root / "ai-stack" / "agentic-patterns" / "reflexion_pattern.py"
        hints_path = root / "ai-stack" / "mcp-servers" / "hybrid-coordinator" / "hints_engine.py"

        def _contains(path: Path, needle: str) -> bool:
            try:
                return needle in path.read_text(encoding="utf-8")
            except OSError:
                return False

        features = {
            "react": react_path.exists() and _contains(react_path, "class ReActAgent"),
            "tree_of_thoughts": tot_path.exists() and _contains(tot_path, "class TreeOfThoughtsAgent"),
            "reflexion": reflexion_path.exists() and _contains(reflexion_path, "class ReflexionAgent"),
            "constitutional_guardrails": hints_path.exists()
            and (_contains(hints_path, "guardrails") or _contains(hints_path, "safety policy")),
        }
        enabled_count = sum(1 for enabled in features.values() if enabled)
        status = "active" if enabled_count > 0 else "pending"
        if enabled_count >= 4:
            status = "watch"

        return {
            "available": enabled_count > 0,
            "status": status,
            "feature_count": enabled_count,
            "features": features,
            "paths": {
                "react": str(react_path),
                "tree_of_thoughts": str(tot_path),
                "reflexion": str(reflexion_path),
                "constitutional_guardrails": str(hints_path),
            },
        }

    def _load_experimentation_readiness(self) -> Dict[str, Any]:
        """Inspect repo-native A/B experimentation and comparison coverage."""
        root = _repo_root()
        ab_framework = root / "ai-stack" / "mcp-servers" / "shared" / "ab_testing.py"
        hybrid_server = root / "ai-stack" / "mcp-servers" / "hybrid-coordinator" / "http_server.py"
        interaction_tracker = root / "ai-stack" / "mcp-servers" / "hybrid-coordinator" / "interaction_tracker.py"

        def _contains(path: Path, needle: str) -> bool:
            try:
                return needle in path.read_text(encoding="utf-8")
            except OSError:
                return False

        features = {
            "ab_framework": ab_framework.exists() and _contains(ab_framework, "class ABTestEngine"),
            "variant_feedback_compare": hybrid_server.exists() and _contains(hybrid_server, "handle_learning_ab_compare"),
            "variant_stats_tracking": interaction_tracker.exists() and _contains(interaction_tracker, "get_feedback_variant_stats"),
            "embedding_variant_partitioning": root.joinpath("ai-stack/mcp-servers/hybrid-coordinator/embedding_cache.py").exists()
            and _contains(root / "ai-stack" / "mcp-servers" / "hybrid-coordinator" / "embedding_cache.py", "variant_tag"),
        }
        enabled_count = sum(1 for enabled in features.values() if enabled)
        status = "active" if enabled_count > 0 else "pending"
        if enabled_count >= 3:
            status = "watch"

        return {
            "available": enabled_count > 0,
            "status": status,
            "feature_count": enabled_count,
            "features": features,
            "paths": {
                "ab_framework": str(ab_framework),
                "variant_feedback_compare": str(hybrid_server),
                "variant_stats_tracking": str(interaction_tracker),
            },
        }

    def _load_performance_profiling_readiness(self) -> Dict[str, Any]:
        """Inspect repo-native continuous profiling and reporting coverage."""
        root = _repo_root()
        profiler = root / "ai-stack" / "observability" / "performance_profiler.py"
        ai_stack_nix = root / "nix" / "modules" / "roles" / "ai-stack.nix"
        search_performance = root / "dashboard" / "backend" / "api" / "routes" / "search_performance.py"

        def _contains(path: Path, needle: str) -> bool:
            try:
                return needle in path.read_text(encoding="utf-8")
            except OSError:
                return False

        features = {
            "continuous_profiler": profiler.exists() and _contains(profiler, "class PerformanceProfiler"),
            "weekly_performance_report": ai_stack_nix.exists() and _contains(ai_stack_nix, "ai-weekly-report"),
            "query_profile_api": search_performance.exists() and _contains(search_performance, '@router.get("/performance/profile")'),
        }
        enabled_count = sum(1 for enabled in features.values() if enabled)
        status = "pending"
        if enabled_count > 0:
            status = "active"
        if enabled_count == len(features):
            status = "watch"

        return {
            "available": enabled_count > 0,
            "status": status,
            "feature_count": enabled_count,
            "features": features,
            "paths": {
                "continuous_profiler": str(profiler),
                "weekly_performance_report": str(ai_stack_nix),
                "query_profile_api": str(search_performance),
            },
        }

    def _load_unified_observability_readiness(self) -> Dict[str, Any]:
        """Inspect repo-native telemetry, tracing, and structured logging coverage."""
        root = _repo_root()
        otel_config = root / "ai-stack" / "observability" / "opentelemetry_config.py"
        mcp_servers = root / "nix" / "modules" / "services" / "mcp-servers.nix"
        monitoring = root / "nix" / "modules" / "services" / "monitoring.nix"
        logging_nix = root / "nix" / "modules" / "core" / "logging.nix"

        def _contains(path: Path, needle: str) -> bool:
            try:
                return needle in path.read_text(encoding="utf-8")
            except OSError:
                return False

        features = {
            "opentelemetry_instrumentation": otel_config.exists() and _contains(otel_config, "class OpenTelemetryConfig"),
            "unified_otel_collector": mcp_servers.exists() and _contains(mcp_servers, 'systemd.services.ai-otel-collector'),
            "distributed_tracing": monitoring.exists() and _contains(monitoring, 'systemd.services.ai-tempo'),
            "structured_logging_stack": logging_nix.exists() and _contains(logging_nix, "services.loki"),
            "journal_shipping": logging_nix.exists() and _contains(logging_nix, "services.promtail"),
        }
        enabled_count = sum(1 for enabled in features.values() if enabled)
        status = "pending"
        if enabled_count > 0:
            status = "active"
        if enabled_count >= 4:
            status = "watch"

        return {
            "available": enabled_count > 0,
            "status": status,
            "feature_count": enabled_count,
            "features": features,
            "paths": {
                "opentelemetry_instrumentation": str(otel_config),
                "unified_otel_collector": str(mcp_servers),
                "distributed_tracing": str(monitoring),
                "structured_logging_stack": str(logging_nix),
            },
        }

    async def get_tool_performance_summary(self) -> Dict[str, Any]:
        """Get summarized tool performance metrics."""
        report = await self.get_full_report()
        tool_perf = report.get("tool_performance", {})

        # Calculate summary statistics
        total_calls = sum(t.get("calls", 0) for t in tool_perf.values())
        total_errors = sum(t.get("error_count", 0) for t in tool_perf.values())

        # Find slowest tools (p95 > 1000ms)
        slow_tools = [
            {
                "name": name,
                "calls": metrics["calls"],
                "p95_ms": metrics["p95_ms"],
                "success_pct": metrics["success_pct"],
            }
            for name, metrics in tool_perf.items()
            if metrics.get("p95_ms", 0) > 1000
        ]
        slow_tools.sort(key=lambda x: x["p95_ms"], reverse=True)

        # Find most-used tools
        top_tools = sorted(
            [
                {
                    "name": name,
                    "calls": metrics["calls"],
                    "p50_ms": metrics["p50_ms"],
                    "success_pct": metrics["success_pct"],
                }
                for name, metrics in tool_perf.items()
            ],
            key=lambda x: x["calls"],
            reverse=True,
        )[:10]

        # Find tools with errors
        error_tools = [
            {
                "name": name,
                "calls": metrics["calls"],
                "error_count": metrics["error_count"],
                "success_pct": metrics["success_pct"],
            }
            for name, metrics in tool_perf.items()
            if metrics.get("error_count", 0) > 0
        ]
        error_tools.sort(key=lambda x: x["error_count"], reverse=True)

        return {
            "timestamp": report.get("generated_at"),
            "window": report.get("window"),
            "summary": {
                "total_tools": len(tool_perf),
                "total_calls": total_calls,
                "total_errors": total_errors,
                "error_rate_pct": (total_errors / total_calls * 100) if total_calls > 0 else 0,
            },
            "top_tools": top_tools,
            "slow_tools": slow_tools,
            "error_tools": error_tools,
        }

    async def get_ai_specific_metrics_summary(self) -> Dict[str, Any]:
        """Get AI-specific operational metrics from the live hybrid Prometheus surface."""
        report = await self.get_full_report()
        metrics_url = f"{HYBRID_URL.rstrip('/')}/metrics"
        try:
            request = Request(metrics_url, headers={"Accept": "text/plain"})
            with urlopen(request, timeout=10.0) as response:
                metrics_text = response.read().decode("utf-8", errors="replace")
        except Exception as exc:
            logger.warning("Failed to fetch hybrid metrics from %s: %s", metrics_url, exc)
            return {
                "timestamp": report.get("generated_at"),
                "window": report.get("window"),
                "available": False,
                "metrics_url": metrics_url,
                "status": "unavailable",
                "error": str(exc),
            }

        before_count = _prometheus_metric_sum(metrics_text, "hybrid_delegated_prompt_tokens_before_count")
        before_sum = _prometheus_metric_sum(metrics_text, "hybrid_delegated_prompt_tokens_before_sum")
        after_count = _prometheus_metric_sum(metrics_text, "hybrid_delegated_prompt_tokens_after_count")
        after_sum = _prometheus_metric_sum(metrics_text, "hybrid_delegated_prompt_tokens_after_sum")
        quality_count = _prometheus_metric_sum(metrics_text, "hybrid_delegated_quality_score_count")
        quality_sum = _prometheus_metric_sum(metrics_text, "hybrid_delegated_quality_score_sum")
        token_savings = _prometheus_metric_sum(metrics_text, "hybrid_delegated_prompt_token_savings_total")
        quality_events = _prometheus_metric_sum(metrics_text, "hybrid_delegated_quality_events_total")
        progressive_context_loads = _prometheus_metric_sum(metrics_text, "hybrid_progressive_context_loads_total")
        capability_gap_detections = _prometheus_metric_sum(metrics_text, "hybrid_capability_gap_detections_total")
        real_time_learning_events = _prometheus_metric_sum(metrics_text, "hybrid_real_time_learning_events_total")
        meta_learning_adaptations = _prometheus_metric_sum(metrics_text, "hybrid_meta_learning_adaptations_total")
        process_memory_bytes = _prometheus_metric_scalar(metrics_text, "hybrid_process_memory_bytes")

        avg_prompt_tokens_before = round(before_sum / before_count, 2) if before_sum is not None and before_count else None
        avg_prompt_tokens_after = round(after_sum / after_count, 2) if after_sum is not None and after_count else None
        avg_quality_score = round(quality_sum / quality_count, 4) if quality_sum is not None and quality_count else None

        return {
            "timestamp": report.get("generated_at"),
            "window": report.get("window"),
            "available": True,
            "metrics_url": metrics_url,
            "status": "active",
            "delegated_prompt_optimization": {
                "samples_before": int(round(before_count)) if before_count is not None else 0,
                "samples_after": int(round(after_count)) if after_count is not None else 0,
                "avg_tokens_before": avg_prompt_tokens_before,
                "avg_tokens_after": avg_prompt_tokens_after,
                "tokens_saved_total": int(round(token_savings)) if token_savings is not None else 0,
            },
            "delegated_quality": {
                "score_samples": int(round(quality_count)) if quality_count is not None else 0,
                "avg_quality_score": avg_quality_score,
                "quality_events_total": int(round(quality_events)) if quality_events is not None else 0,
            },
            "learning_and_adaptation": {
                "progressive_context_loads_total": int(round(progressive_context_loads)) if progressive_context_loads is not None else 0,
                "capability_gap_detections_total": int(round(capability_gap_detections)) if capability_gap_detections is not None else 0,
                "real_time_learning_events_total": int(round(real_time_learning_events)) if real_time_learning_events is not None else 0,
                "meta_learning_adaptations_total": int(round(meta_learning_adaptations)) if meta_learning_adaptations is not None else 0,
            },
            "process": {
                "memory_bytes": int(round(process_memory_bytes)) if process_memory_bytes is not None else None,
            },
        }

    async def get_routing_analytics(self) -> Dict[str, Any]:
        """Get LLM routing analytics and model performance."""
        report = await self.get_full_report()

        return {
            "timestamp": report.get("generated_at"),
            "window": report.get("window"),
            "current": report.get("routing", {}),
            "recent": report.get("recent_routing", {}),
            "windows": report.get("routing_windows", {}),
            "remote_profile_utilization": report.get("remote_profile_utilization_windows", {}),
        }

    async def get_hint_effectiveness(self) -> Dict[str, Any]:
        """Get hint adoption and effectiveness metrics."""
        report = await self.get_full_report()

        return {
            "timestamp": report.get("generated_at"),
            "window": report.get("window"),
            "adoption": report.get("hint_adoption", {}),
            "recent_adoption": report.get("recent_hint_adoption", {}),
            "diversity": report.get("hint_diversity", {}),
            "recent_diversity": report.get("recent_hint_diversity", {}),
            "watchlist": report.get("historical_hint_watchlist", {}),
        }

    async def get_workflow_compliance(self) -> Dict[str, Any]:
        """Get agentic workflow success and compliance metrics."""
        report = await self.get_full_report()

        return {
            "timestamp": report.get("generated_at"),
            "window": report.get("window"),
            "intent_contract": report.get("intent_contract_compliance", {}),
            "task_tooling": report.get("task_tooling_quality", {}),
            "delegated_failures": report.get("delegated_prompt_failures", {}),
            "delegated_failure_windows": report.get("delegated_prompt_failure_windows", {}),
            "feedback_acceleration": report.get("feedback_acceleration", {}),
        }

    async def get_improvement_candidates(self) -> Dict[str, Any]:
        """Return the current persisted improvement-candidate summary."""
        report = await self.get_full_report()
        summary = self._load_improvement_candidates_summary()
        return {
            "timestamp": report.get("generated_at"),
            "window": report.get("window"),
            **summary,
        }

    async def get_code_review_summary(self) -> Dict[str, Any]:
        """Return the current persisted LLM code-review summary."""
        report = await self.get_full_report()
        summary = self._load_code_review_summary()
        return {
            "timestamp": report.get("generated_at"),
            "window": report.get("window"),
            **summary,
        }

    async def get_improvement_automation_readiness(self) -> Dict[str, Any]:
        """Return the repo-native improvement automation readiness summary."""
        report = await self.get_full_report()
        return {
            "timestamp": report.get("generated_at"),
            "window": report.get("window"),
            **self._load_improvement_automation_readiness(),
        }

    async def get_testing_validation_readiness(self) -> Dict[str, Any]:
        """Return the repo-native testing and validation readiness summary."""
        report = await self.get_full_report()
        return {
            "timestamp": report.get("generated_at"),
            "window": report.get("window"),
            **self._load_testing_validation_readiness(),
        }

    async def get_deployment_pipeline_readiness(self) -> Dict[str, Any]:
        """Return the repo-native autonomous deployment readiness summary."""
        report = await self.get_full_report()
        return {
            "timestamp": report.get("generated_at"),
            "window": report.get("window"),
            **self._load_deployment_pipeline_readiness(),
        }

    async def get_agentic_pattern_library_readiness(self) -> Dict[str, Any]:
        """Return the repo-native agentic pattern library readiness summary."""
        report = await self.get_full_report()
        return {
            "timestamp": report.get("generated_at"),
            "window": report.get("window"),
            **self._load_agentic_pattern_library_readiness(),
        }

    async def get_experimentation_readiness(self) -> Dict[str, Any]:
        """Return the repo-native experimentation readiness summary."""
        report = await self.get_full_report()
        return {
            "timestamp": report.get("generated_at"),
            "window": report.get("window"),
            **self._load_experimentation_readiness(),
        }

    async def get_performance_profiling_readiness(self) -> Dict[str, Any]:
        """Return the repo-native performance profiling readiness summary."""
        report = await self.get_full_report()
        return {
            "timestamp": report.get("generated_at"),
            "window": report.get("window"),
            **self._load_performance_profiling_readiness(),
        }

    async def get_unified_observability_readiness(self) -> Dict[str, Any]:
        """Return the repo-native unified observability readiness summary."""
        report = await self.get_full_report()
        return {
            "timestamp": report.get("generated_at"),
            "window": report.get("window"),
            **self._load_unified_observability_readiness(),
        }

    async def get_roadmap_readiness(self) -> Dict[str, Any]:
        """Return a consolidated readiness summary for the active next-gen roadmap phases."""
        report = await self.get_full_report()
        phase4 = await self.get_phase4_acceptance_summary()
        a2a = await self.get_a2a_readiness()
        ai_specific_metrics = await self.get_ai_specific_metrics_summary()
        experimentation = self._load_experimentation_readiness()
        profiling = self._load_performance_profiling_readiness()
        observability = self._load_unified_observability_readiness()
        improvement_candidates = self._load_improvement_candidates_summary()
        improvement_automation = self._load_improvement_automation_readiness()
        code_review_summary = self._load_code_review_summary()
        testing_validation = self._load_testing_validation_readiness()
        deployment_pipeline = self._load_deployment_pipeline_readiness()
        pattern_library = self._load_agentic_pattern_library_readiness()

        routing = report.get("routing", {}) if isinstance(report.get("routing"), dict) else {}
        continue_editor = report.get("continue_editor", {}) if isinstance(report.get("continue_editor"), dict) else {}
        gap_remediation = report.get("gap_remediation", {}) if isinstance(report.get("gap_remediation"), dict) else {}
        feedback_acceleration = report.get("feedback_acceleration", {}) if isinstance(report.get("feedback_acceleration"), dict) else {}
        agent_lessons = report.get("agent_lessons", {}) if isinstance(report.get("agent_lessons"), dict) else {}
        intent_contract = report.get("intent_contract_compliance", {}) if isinstance(report.get("intent_contract_compliance"), dict) else {}
        route_latency = (
            report.get("route_search_latency_decomposition", {})
            if isinstance(report.get("route_search_latency_decomposition"), dict)
            else {}
        )
        remote_profile = (
            report.get("remote_profile_utilization", {})
            if isinstance(report.get("remote_profile_utilization"), dict)
            else {}
        )
        structured_actions = report.get("structured_actions", []) if isinstance(report.get("structured_actions"), list) else []
        recommendations = report.get("recommendations", []) if isinstance(report.get("recommendations"), list) else []
        route_breakdown = route_latency.get("breakdown", []) if isinstance(route_latency.get("breakdown"), list) else []

        phase1_hotspots = [
            {
                "label": str(item.get("label", "") or ""),
                "calls": int(item.get("calls", 0) or 0),
                "p95_ms": item.get("p95_ms"),
            }
            for item in route_breakdown
            if isinstance(item, dict) and str(item.get("label", "") or "").strip()
        ][:3]
        phase1_status = "pending"
        if route_latency.get("available"):
            phase1_status = "healthy"
            overall_p95 = route_latency.get("overall_p95_ms")
            if (
                any("route_search" in str(rec or "").lower() for rec in recommendations)
                or (isinstance(overall_p95, (int, float)) and overall_p95 >= 3000)
            ):
                phase1_status = "watch"
        if ai_specific_metrics.get("available"):
            quality_score = ((ai_specific_metrics.get("delegated_quality") or {}).get("avg_quality_score"))
            tokens_saved_total = ((ai_specific_metrics.get("delegated_prompt_optimization") or {}).get("tokens_saved_total"))
            if quality_score is not None or tokens_saved_total:
                if phase1_status == "pending":
                    phase1_status = "active"

        phase4_failed = int(((phase4.get("summary") or {}).get("failed_flows", 0) or 0)) if isinstance(phase4, dict) else 0
        phase4_status = "healthy"
        if not phase4.get("available", False):
            phase4_status = "pending"
        elif phase4_failed > 0 or a2a.get("status") == "unavailable":
            phase4_status = "watch"

        phase3_status = str(improvement_candidates.get("status", "pending") or "pending")
        if not improvement_candidates.get("available", False):
            phase3_status = "pending"
        elif improvement_automation.get("available", False) and phase3_status == "pending":
            phase3_status = "active"

        remote_calls = int((routing.get("remote_n", 0) or 0))
        phase6_status = "healthy" if routing.get("available") and remote_calls == 0 else "watch"

        candidate_count = int(gap_remediation.get("candidate_count", 0) or 0)
        phase9_status = str(gap_remediation.get("status", "healthy") or "healthy")
        if not gap_remediation.get("available", False):
            phase9_status = "pending"

        promotable_lessons = int(feedback_acceleration.get("promotable_lessons", 0) or 0)
        phase10_status = str(feedback_acceleration.get("status", "healthy") or "healthy")
        if not feedback_acceleration.get("available", False):
            phase10_status = "pending"

        continue_status = str(continue_editor.get("status", "unknown") or "unknown")
        local_pct = routing.get("local_pct")
        phase11_status = "healthy"
        if continue_status not in {"healthy", "available"}:
            phase11_status = "watch"
        elif local_pct is None or float(local_pct) < 80.0:
            phase11_status = "watch"

        checklist_path = _reviewer_gate_checklist_path()
        checklist_available = checklist_path.exists()

        return {
            "timestamp": report.get("generated_at"),
            "window": report.get("window"),
            "status": "healthy" if all(
                status in {"healthy", "active"}
                for status in (phase1_status, phase3_status, phase4_status, phase6_status, phase11_status)
            ) and phase9_status in {"healthy", "low_sample"} and phase10_status in {"healthy", "low_sample"} else "watch",
            "phases": {
                "phase1": {
                    "status": phase1_status,
                    "profiling_available": bool(route_latency.get("available")),
                    "unified_observability": observability,
                    "ai_specific_metrics": ai_specific_metrics,
                    "experimentation": experimentation,
                    "continuous_profiling": profiling,
                    "route_search_latency": {
                        "overall_p95_ms": route_latency.get("overall_p95_ms"),
                        "synthesis_p95_ms": route_latency.get("synthesis_p95_ms"),
                        "retrieval_only_p95_ms": route_latency.get("retrieval_only_p95_ms"),
                    },
                    "top_hotspots": phase1_hotspots,
                },
                "phase3": {
                    "status": phase3_status,
                    "improvement_automation": improvement_automation,
                    "improvement_candidates": improvement_candidates,
                    "code_review": code_review_summary,
                    "testing_validation": testing_validation,
                    "deployment_pipeline": deployment_pipeline,
                    "candidate_count": int(improvement_candidates.get("total_candidates", 0) or 0),
                    "top_candidates": improvement_candidates.get("top_candidates", []),
                },
                "phase4": {
                    "status": phase4_status,
                    "acceptance": phase4,
                    "a2a_readiness": a2a,
                    "pattern_library": pattern_library,
                    "reviewer_gate_required_runs": int(intent_contract.get("reviewer_gate_required_runs", 0) or 0),
                    "accepted_reviews": int(intent_contract.get("accepted_reviews", 0) or 0),
                },
                "phase6": {
                    "status": phase6_status,
                    "routing": routing,
                    "remote_profile_utilization": remote_profile,
                    "route_search_latency": {
                        "overall_p95_ms": route_latency.get("overall_p95_ms"),
                        "synthesis_p95_ms": route_latency.get("synthesis_p95_ms"),
                    },
                },
                "phase9": {
                    "status": phase9_status,
                    "gap_remediation": gap_remediation,
                    "candidate_count": candidate_count,
                },
                "phase10": {
                    "status": phase10_status,
                    "feedback_acceleration": feedback_acceleration,
                    "promotable_lessons": promotable_lessons,
                },
                "phase11": {
                    "status": phase11_status,
                    "continue_editor": continue_editor,
                    "local_routing_pct": local_pct,
                    "active_lessons": int(((agent_lessons.get("registry") or {}).get("active_count", 0) or 0)),
                },
            },
            "reviewer_gate_checklist": {
                "available": checklist_available,
                "path": str(checklist_path),
            },
            "structured_action_count": len(structured_actions),
            "priority_recommendations": recommendations[:3],
        }

    async def get_phase4_acceptance_summary(self) -> Dict[str, Any]:
        """Return the latest consolidated Phase 4 workflow acceptance report."""
        report_path = _phase4_acceptance_report_path()
        if not report_path.exists():
            return {
                "available": False,
                "status": "no_report",
                "phase": "4",
                "report_path": str(report_path),
                "flows": {},
            }

        try:
            payload = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.error("Failed to read Phase 4 acceptance report: %s", exc)
            return {
                "available": False,
                "status": "error",
                "phase": "4",
                "report_path": str(report_path),
                "message": str(exc),
                "flows": {},
            }

        flows = payload.get("flows", {}) if isinstance(payload.get("flows"), dict) else {}
        summarized_flows = {
            key: {
                "label": flow.get("label"),
                "status": flow.get("status"),
                "script": flow.get("script"),
                "ended_at": flow.get("ended_at"),
            }
            for key, flow in flows.items()
            if isinstance(flow, dict)
        }
        passed = sum(1 for flow in summarized_flows.values() if flow.get("status") == "passed")
        failed = sum(1 for flow in summarized_flows.values() if flow.get("status") != "passed")
        return {
            "available": True,
            "status": payload.get("status", "unknown"),
            "phase": str(payload.get("phase", "4")),
            "generated_at": payload.get("generated_at"),
            "report_path": str(report_path),
            "summary": {
                "total_flows": len(summarized_flows),
                "passed_flows": passed,
                "failed_flows": failed,
            },
            "flows": summarized_flows,
        }

    async def get_a2a_readiness(self) -> Dict[str, Any]:
        """Get A2A compatibility readiness from the live hybrid coordinator."""
        agent_card_url = f"{HYBRID_URL.rstrip('/')}/.well-known/agent.json"
        rpc_url = f"{HYBRID_URL.rstrip('/')}/a2a"
        try:
            request = Request(agent_card_url, headers={"Accept": "application/json"})
            with urlopen(request, timeout=10.0) as response:
                card = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            logger.error("Failed to get A2A agent card: %s", exc)
            return {
                "available": False,
                "status": "unavailable",
                "agent_card_url": agent_card_url,
                "rpc_url": rpc_url,
                "error": str(exc),
            }

        capabilities = card.get("capabilities", {}) if isinstance(card.get("capabilities"), dict) else {}
        skills = card.get("skills", []) if isinstance(card.get("skills"), list) else []
        endpoints = card.get("endpoints", {}) if isinstance(card.get("endpoints"), dict) else {}
        protocol_version = str(card.get("protocolVersion", "") or "")
        required_methods = [
            "agent/getCard",
            "message/send",
            "message/stream",
            "tasks/get",
            "tasks/list",
            "tasks/cancel",
        ]
        input_modes = card.get("defaultInputModes", []) if isinstance(card.get("defaultInputModes"), list) else []
        output_modes = card.get("defaultOutputModes", []) if isinstance(card.get("defaultOutputModes"), list) else []
        task_events_url = endpoints.get("taskEvents")

        return {
            "available": True,
            "status": "ready" if protocol_version and endpoints.get("rpc") and task_events_url else "degraded",
            "protocol_version": protocol_version,
            "agent_card_url": agent_card_url,
            "rpc_url": endpoints.get("rpc") or rpc_url,
            "task_events_url": task_events_url,
            "streaming": bool(capabilities.get("streaming", False)),
            "push_notifications": bool(capabilities.get("pushNotifications", False)),
            "state_transition_history": bool(capabilities.get("stateTransitionHistory", False)),
            "input_modes": input_modes,
            "output_modes": output_modes,
            "features": {
                "message_stream": True,
                "task_events": bool(task_events_url),
                "task_artifacts": True,
                "status_messages": True,
            },
            "skills": {
                "count": len(skills),
                "ids": [str(item.get("id", "")).strip() for item in skills if isinstance(item, dict)][:10],
            },
            "methods": {
                "implemented": required_methods,
                "count": len(required_methods),
            },
        }

    async def get_security_compliance_summary(self) -> Dict[str, Any]:
        """Summarize dashboard/operator security and compliance controls."""
        audit_log = get_operator_audit_log()
        rate_limiter = get_dashboard_rate_limiter()
        audit_summary = audit_log.summary(limit=500)
        integrity = audit_summary.get("integrity") or {}
        csp = str(
            os.getenv(
                "DASHBOARD_CSP",
                "default-src 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'none'",
            )
        )
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "in_progress",
            "controls": {
                "content_security_policy": bool(csp),
                "security_headers": True,
                "rate_limiting": bool(rate_limiter.enabled()),
                "operator_audit_log": bool(audit_summary.get("append_only")),
                "tamper_evident_audit_sealing": bool(audit_summary.get("tamper_evident")),
                "dashboard_security_scan_automation": True,
                "secrets_rotation_planning": True,
            },
            "rate_limiting": {
                "enabled": bool(rate_limiter.enabled()),
                "window_seconds": int(os.getenv("DASHBOARD_RATE_LIMIT_WINDOW_SECONDS", "60") or 60),
                "default_rpm": int(os.getenv("DASHBOARD_RATE_LIMIT_DEFAULT_RPM", "240") or 240),
                "operator_write_rpm": int(os.getenv("DASHBOARD_RATE_LIMIT_OPERATOR_WRITE_RPM", "30") or 30),
                "search_rpm": int(os.getenv("DASHBOARD_RATE_LIMIT_SEARCH_RPM", "90") or 90),
            },
            "audit": audit_summary,
            "audit_integrity": integrity,
            "gaps": [
                "automated compliance report export still pending",
                "external security scan automation still pending",
                "live secrets rotation execution still requires explicit operator approval",
            ],
        }

    async def get_query_complexity_analysis(self) -> Dict[str, Any]:
        """Get query complexity and gap analysis."""
        report = await self.get_full_report()

        # Extract route_search latency decomposition for complexity analysis
        route_decomp = report.get("route_search_latency_decomposition", {})

        # Get query gaps (unanswered queries)
        query_gaps = report.get("query_gaps", [])

        # Get retrieval breadth (complexity indicator)
        retrieval_breadth = report.get("route_retrieval_breadth_windows", {})

        return {
            "timestamp": report.get("generated_at"),
            "window": report.get("window"),
            "latency_breakdown": route_decomp,
            "query_gaps": query_gaps,
            "gap_remediation": report.get("gap_remediation", {}),
            "retrieval_breadth": retrieval_breadth,
            "rag_posture": report.get("rag_posture", {}),
        }

    async def get_performance_hotspots(self) -> Dict[str, Any]:
        """Return the highest-signal performance hotspots for current optimization work."""
        report = await self.get_full_report()
        optimization_history = self._load_recent_optimization_history()
        cache = report.get("cache", {}) if isinstance(report.get("cache"), dict) else {}
        rag_posture = report.get("rag_posture", {}) if isinstance(report.get("rag_posture"), dict) else {}
        route_latency = (
            report.get("route_search_latency_decomposition", {})
            if isinstance(report.get("route_search_latency_decomposition"), dict)
            else {}
        )
        retrieval_breadth = (
            report.get("route_retrieval_breadth", {})
            if isinstance(report.get("route_retrieval_breadth"), dict)
            else {}
        )
        retrieval_windows = (
            report.get("route_retrieval_breadth_windows", {})
            if isinstance(report.get("route_retrieval_breadth_windows"), dict)
            else {}
        )
        structured_actions = report.get("structured_actions", []) if isinstance(report.get("structured_actions"), list) else []
        recommendations = report.get("recommendations", []) if isinstance(report.get("recommendations"), list) else []
        route_breakdown = route_latency.get("breakdown", []) if isinstance(route_latency.get("breakdown"), list) else []
        recent_mix = ((rag_posture.get("retrieval_mix") or {}).get("recent") or {}) if isinstance(rag_posture, dict) else {}
        top_candidate = None
        for candidate in rag_posture.get("prewarm_candidates", []) or []:
            if isinstance(candidate, dict) and candidate.get("id"):
                top_candidate = {
                    "id": candidate.get("id"),
                    "name": candidate.get("name"),
                }
                break

        hotspots: List[Dict[str, Any]] = []
        route_p95 = route_latency.get("p95_ms")
        if route_p95 is None:
            route_p95 = route_latency.get("overall_p95_ms")
        if route_p95 is not None:
            hotspots.append(
                {
                    "id": "route_latency",
                    "label": "Route Search Latency",
                    "status": "watch" if float(route_p95) >= 2500 else "healthy",
                    "summary": f"p95={float(route_p95):.0f}ms",
                }
            )
        if cache.get("available") and cache.get("hit_pct") is not None:
            cache_hit = float(cache.get("hit_pct") or 0.0)
            hotspots.append(
                {
                    "id": "semantic_cache",
                    "label": "Semantic Cache Hit Rate",
                    "status": "watch" if cache_hit < 60.0 else "healthy",
                    "summary": f"hit_rate={cache_hit:.1f}%",
                }
            )
        breadth_avg = retrieval_breadth.get("avg_collection_count")
        if breadth_avg is not None:
            hotspots.append(
                {
                    "id": "retrieval_breadth",
                    "label": "Retrieval Breadth",
                    "status": "watch" if float(breadth_avg) > 2.5 else "healthy",
                    "summary": f"avg_collections={float(breadth_avg):.2f}",
                }
            )
        memory_miss_pct = rag_posture.get("memory_recall_miss_pct")
        if memory_miss_pct is not None:
            hotspots.append(
                {
                    "id": "memory_recall_quality",
                    "label": "Memory Recall Quality",
                    "status": "watch" if float(memory_miss_pct) >= 50.0 else "healthy",
                    "summary": f"miss_rate={float(memory_miss_pct):.1f}%",
                }
            )

        top_bottlenecks = [
            {
                "label": str(item.get("label", "") or ""),
                "calls": int(item.get("calls", 0) or 0),
                "p95_ms": item.get("p95_ms"),
                "status": "watch" if float(item.get("p95_ms", 0) or 0) >= 2500.0 else "healthy",
            }
            for item in route_breakdown
            if isinstance(item, dict) and str(item.get("label", "") or "").strip()
        ][:5]

        optimization_recommendations: List[Dict[str, Any]] = []
        for item in structured_actions[:5]:
            if not isinstance(item, dict):
                continue
            optimization_recommendations.append(
                {
                    "summary": item.get("summary") or item.get("title") or item.get("action"),
                    "action": item.get("action"),
                    "priority": item.get("priority"),
                    "category": item.get("category"),
                }
            )
        if not optimization_recommendations:
            for rec in recommendations[:5]:
                if not str(rec or "").strip():
                    continue
                optimization_recommendations.append({"summary": str(rec)})

        return {
            "timestamp": report.get("generated_at"),
            "window": report.get("window"),
            "hotspots": hotspots,
            "top_bottlenecks": top_bottlenecks,
            "optimization_recommendations": optimization_recommendations,
            "route_latency": route_latency,
            "cache": cache,
            "retrieval_breadth": retrieval_breadth,
            "retrieval_breadth_windows": retrieval_windows,
            "optimization_history": optimization_history,
            "rag_posture": {
                "status": rag_posture.get("status"),
                "reasons": rag_posture.get("reasons", []),
                "recent_retrieval_calls": rag_posture.get("recent_retrieval_calls"),
                "retrieval_mix_recent": recent_mix,
                "memory_recall_share_pct": rag_posture.get("memory_recall_share_pct"),
                "memory_recall_miss_pct": memory_miss_pct,
                "top_prewarm_candidate": top_candidate,
            },
        }

    async def get_operator_insight_digest(self, insight_target: str) -> Dict[str, Any]:
        """Return a compact insight summary suitable for operator search guidance."""
        normalized_target = str(insight_target or "full_report").strip().lower()
        if normalized_target == "a2a_readiness":
            readiness = await self.get_a2a_readiness()
            return {
                "target": normalized_target,
                "title": "A2A Readiness",
                "status": readiness.get("status", "unknown"),
                "summary": (
                    f"protocol={readiness.get('protocol_version', '--')} "
                    f"| streaming={readiness.get('streaming', False)} "
                    f"| methods={readiness.get('methods', {}).get('count', 0)}"
                ),
            }
        if normalized_target == "query_complexity":
            complexity = await self.get_query_complexity_analysis()
            query_gaps = complexity.get("query_gaps") or []
            rag_posture = complexity.get("rag_posture") or {}
            return {
                "target": normalized_target,
                "title": "Query Complexity",
                "status": "active",
                "summary": (
                    f"query_gaps={len(query_gaps)} "
                    f"| rag_enabled={rag_posture.get('enabled', 'unknown')} "
                    f"| breadth_windows={len(complexity.get('retrieval_breadth') or {})}"
                ),
            }
        if normalized_target == "performance_hotspots":
            hotspots = await self.get_performance_hotspots()
            top_hotspot = (hotspots.get("hotspots") or [{}])[0]
            return {
                "target": normalized_target,
                "title": "Performance Hotspots",
                "status": "active",
                "summary": (
                    f"hotspots={len(hotspots.get('hotspots') or [])} "
                    f"| top={top_hotspot.get('id', '--')} "
                    f"| prewarm={((hotspots.get('rag_posture') or {}).get('top_prewarm_candidate') or {}).get('id', '--')}"
                ),
            }
        if normalized_target == "roadmap_readiness":
            readiness = await self.get_roadmap_readiness()
            phases = readiness.get("phases") or {}
            return {
                "target": normalized_target,
                "title": "Roadmap Readiness",
                "status": readiness.get("status", "unknown"),
                "summary": (
                    f"phase4={((phases.get('phase4') or {}).get('status', '--'))} "
                    f"| phase6={((phases.get('phase6') or {}).get('status', '--'))} "
                    f"| phase9={((phases.get('phase9') or {}).get('candidate_count', 0))} gaps "
                    f"| phase10={((phases.get('phase10') or {}).get('promotable_lessons', 0))} lessons"
                ),
            }
        if normalized_target == "improvement_candidates":
            candidates = await self.get_improvement_candidates()
            return {
                "target": normalized_target,
                "title": "Improvement Candidates",
                "status": candidates.get("status", "unknown"),
                "summary": (
                    f"candidates={candidates.get('total_candidates', 0)} "
                    f"| top={((candidates.get('top_candidates') or [{}])[0]).get('title', '--')} "
                    f"| categories={len(candidates.get('categories') or {})}"
                ),
            }
        if normalized_target == "improvement-automation":
            readiness = await self.get_improvement_automation_readiness()
            return {
                "target": normalized_target,
                "title": "Improvement Automation",
                "status": readiness.get("status", "unknown"),
                "summary": (
                    f"features={readiness.get('feature_count', 0)} "
                    f"| smells={((readiness.get('features') or {}).get('code_smell_detection', False))} "
                    f"| mining={((readiness.get('features') or {}).get('telemetry_pattern_mining', False))}"
                ),
            }
        if normalized_target == "ai_specific_metrics":
            metrics = await self.get_ai_specific_metrics_summary()
            delegated = metrics.get("delegated_prompt_optimization") or {}
            learning = metrics.get("learning_and_adaptation") or {}
            return {
                "target": normalized_target,
                "title": "AI-Specific Metrics",
                "status": metrics.get("status", "unknown"),
                "summary": (
                    f"saved={delegated.get('tokens_saved_total', 0)} "
                    f"| quality={((metrics.get('delegated_quality') or {}).get('avg_quality_score', '--'))} "
                    f"| learning={learning.get('real_time_learning_events_total', 0)}"
                ),
            }
        if normalized_target == "code_review":
            review = await self.get_code_review_summary()
            return {
                "target": normalized_target,
                "title": "Code Review",
                "status": review.get("status", "unknown"),
                "summary": (
                    f"files={review.get('total_files', 0)} "
                    f"| reviewer={review.get('reviewer', '--')} "
                    f"| critical={((review.get('severity_counts') or {}).get('critical', 0))}"
                ),
            }
        if normalized_target == "testing_validation":
            readiness = await self.get_testing_validation_readiness()
            return {
                "target": normalized_target,
                "title": "Testing Validation",
                "status": readiness.get("status", "unknown"),
                "summary": (
                    f"features={readiness.get('feature_count', 0)} "
                    f"| property={((readiness.get('features') or {}).get('property_based_testing', False))} "
                    f"| chaos={((readiness.get('features') or {}).get('chaos_engineering', False))}"
                ),
            }
        if normalized_target == "deployment_pipeline":
            readiness = await self.get_deployment_pipeline_readiness()
            return {
                "target": normalized_target,
                "title": "Deployment Pipeline",
                "status": readiness.get("status", "unknown"),
                "summary": (
                    f"features={readiness.get('feature_count', 0)} "
                    f"| blue_green={((readiness.get('features') or {}).get('blue_green', False))} "
                    f"| rollback={((readiness.get('features') or {}).get('rollback', False))}"
                ),
            }
        if normalized_target == "pattern_library":
            readiness = await self.get_agentic_pattern_library_readiness()
            return {
                "target": normalized_target,
                "title": "Pattern Library",
                "status": readiness.get("status", "unknown"),
                "summary": (
                    f"features={readiness.get('feature_count', 0)} "
                    f"| react={((readiness.get('features') or {}).get('react', False))} "
                    f"| tot={((readiness.get('features') or {}).get('tree_of_thoughts', False))}"
                ),
            }
        if normalized_target == "experimentation":
            readiness = await self.get_experimentation_readiness()
            return {
                "target": normalized_target,
                "title": "Experimentation",
                "status": readiness.get("status", "unknown"),
                "summary": (
                    f"features={readiness.get('feature_count', 0)} "
                    f"| compare={((readiness.get('features') or {}).get('variant_feedback_compare', False))} "
                    f"| stats={((readiness.get('features') or {}).get('variant_stats_tracking', False))}"
                ),
            }
        if normalized_target == "profiling":
            readiness = await self.get_performance_profiling_readiness()
            return {
                "target": normalized_target,
                "title": "Continuous Profiling",
                "status": readiness.get("status", "unknown"),
                "summary": (
                    f"features={readiness.get('feature_count', 0)} "
                    f"| profiler={((readiness.get('features') or {}).get('continuous_profiler', False))} "
                    f"| reports={((readiness.get('features') or {}).get('weekly_performance_report', False))}"
                ),
            }
        if normalized_target == "observability":
            readiness = await self.get_unified_observability_readiness()
            return {
                "target": normalized_target,
                "title": "Unified Observability",
                "status": readiness.get("status", "unknown"),
                "summary": (
                    f"features={readiness.get('feature_count', 0)} "
                    f"| otel={((readiness.get('features') or {}).get('opentelemetry_instrumentation', False))} "
                    f"| tracing={((readiness.get('features') or {}).get('distributed_tracing', False))}"
                ),
            }

        report = await self.get_full_report()
        recommendations = report.get("structured_recommendations") or report.get("recommendations") or []
        query_gaps = report.get("query_gaps") or []
        return {
            "target": "full_report",
            "title": "Full Insights Report",
            "status": "ready",
            "summary": (
                f"recommendations={len(recommendations)} "
                f"| query_gaps={len(query_gaps)} "
                f"| generated={report.get('generated_at', '--')}"
            ),
        }

    async def get_cache_analytics(self) -> Dict[str, Any]:
        """Get cache performance analytics."""
        report = await self.get_full_report()

        return {
            "timestamp": report.get("generated_at"),
            "window": report.get("window"),
            "cache": report.get("cache", {}),
            "cache_prewarm": report.get("cache_prewarm", {}),
        }

    async def get_system_health_overview(self) -> Dict[str, Any]:
        """Get high-level system health overview."""
        report = await self.get_full_report()
        a2a = await self.get_a2a_readiness()

        # Aggregate health indicators
        routing = report.get("routing", {})
        cache = report.get("cache", {})
        recent_health = report.get("recent_health", {})
        eval_trend = report.get("eval_trend", {})

        # Determine overall health status
        issues = []

        if not routing.get("available", False):
            issues.append("LLM routing unavailable")

        if not cache.get("available", False):
            issues.append("Cache unavailable")

        if not recent_health.get("healthy", True):
            issues.append(f"{len(recent_health.get('slow_tools', []))} slow tools, {len(recent_health.get('flaky_tools', []))} flaky tools")

        if eval_trend.get("trend") == "falling":
            issues.append(f"Eval score falling (latest: {eval_trend.get('latest_pct')}%)")

        overall_status = "healthy" if len(issues) == 0 else "degraded" if len(issues) < 3 else "unhealthy"

        return {
            "timestamp": report.get("generated_at"),
            "window": report.get("window"),
            "status": overall_status,
            "issues": issues,
            "a2a": a2a,
            "routing": routing,
            "cache": cache,
            "recent_health": recent_health,
            "eval_trend": eval_trend,
            "recommendations": report.get("recommendations", []),
        }

    async def get_agent_lessons(self) -> Dict[str, Any]:
        """Get agent lessons and continuous learning metrics."""
        report = await self.get_full_report()

        return {
            "timestamp": report.get("generated_at"),
            "window": report.get("window"),
            "lessons": report.get("agent_lessons", {}),
        }

    async def get_structured_actions(self) -> List[Dict[str, Any]]:
        """Get structured actionable recommendations."""
        report = await self.get_full_report()
        return report.get("structured_actions", [])


# Singleton instance
_insights_service: Optional[AIInsightsService] = None


def get_insights_service() -> AIInsightsService:
    """Get singleton insights service instance."""
    global _insights_service
    if _insights_service is None:
        _insights_service = AIInsightsService()
    return _insights_service
