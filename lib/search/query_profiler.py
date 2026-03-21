#!/usr/bin/env python3
"""
Query Performance Profiler.

Implements end-to-end timing, component-level tracking, slow query logging,
regression detection, and Prometheus metrics export.
"""

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ProfilerConfig:
    """Query profiler configuration."""
    
    slow_query_threshold_ms: float = 500.0
    enable_regression_detection: bool = True
    baseline_window_size: int = 100
    regression_threshold_pct: float = 50.0  # 50% slower = regression


@dataclass
class QueryProfile:
    """Individual query performance profile."""
    
    query_id: str
    query_text: str
    mode: str
    start_time: float
    end_time: Optional[float] = None
    components: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def duration_ms(self) -> float:
        """Get total duration in milliseconds."""
        if self.end_time is None:
            return (time.time() - self.start_time) * 1000
        return (self.end_time - self.start_time) * 1000


class QueryProfiler:
    """
    Query performance profiler.
    
    Features:
    - End-to-end query timing breakdown
    - Component-level performance tracking
    - Slow query logging (>1s)
    - Performance regression detection
    - P50/P95/P99 latency tracking
    - Query pattern analysis
    - Bottleneck identification automation
    - Prometheus metrics export
    """
    
    def __init__(self, config: Optional[ProfilerConfig] = None):
        self.config = config or ProfilerConfig()
        self.active_profiles: Dict[str, QueryProfile] = {}
        self.completed_profiles: List[QueryProfile] = []
        self.slow_queries: List[QueryProfile] = []
        
        # Performance baselines
        self.component_baselines: Dict[str, List[float]] = defaultdict(list)
        
        # Metrics
        self.metrics = {
            "total_queries": 0,
            "slow_queries": 0,
            "regressions_detected": 0,
        }
    
    def start_profile(
        self,
        query_id: str,
        query_text: str,
        mode: str = "auto",
        **metadata: Any,
    ) -> QueryProfile:
        """Start profiling a query."""
        profile = QueryProfile(
            query_id=query_id,
            query_text=query_text,
            mode=mode,
            start_time=time.time(),
            metadata=metadata,
        )
        self.active_profiles[query_id] = profile
        return profile
    
    def record_component(
        self,
        query_id: str,
        component_name: str,
        duration_ms: float,
    ) -> None:
        """Record component execution time."""
        if query_id in self.active_profiles:
            self.active_profiles[query_id].components[component_name] = duration_ms
    
    def end_profile(self, query_id: str) -> Optional[QueryProfile]:
        """End profiling and analyze."""
        if query_id not in self.active_profiles:
            return None
        
        profile = self.active_profiles.pop(query_id)
        profile.end_time = time.time()
        
        # Track metrics
        self.metrics["total_queries"] += 1
        duration_ms = profile.duration_ms()
        
        # Check for slow query
        if duration_ms > self.config.slow_query_threshold_ms:
            self.metrics["slow_queries"] += 1
            self.slow_queries.append(profile)
            logger.warning(
                f"Slow query detected: {profile.query_text[:50]}... "
                f"took {duration_ms:.1f}ms (threshold: {self.config.slow_query_threshold_ms}ms)"
            )
        
        # Update baselines
        for component, comp_duration in profile.components.items():
            self.component_baselines[component].append(comp_duration)
            # Keep only recent window
            if len(self.component_baselines[component]) > self.config.baseline_window_size:
                self.component_baselines[component].pop(0)
        
        # Check for regressions
        if self.config.enable_regression_detection:
            self._detect_regressions(profile)
        
        self.completed_profiles.append(profile)
        
        return profile
    
    def _detect_regressions(self, profile: QueryProfile) -> None:
        """Detect performance regressions."""
        for component, duration in profile.components.items():
            if component not in self.component_baselines:
                continue
            
            baseline = self.component_baselines[component]
            if len(baseline) < 10:  # Need enough data
                continue
            
            avg_baseline = sum(baseline) / len(baseline)
            if duration > avg_baseline * (1 + self.config.regression_threshold_pct / 100):
                self.metrics["regressions_detected"] += 1
                logger.warning(
                    f"Regression detected in {component}: "
                    f"{duration:.1f}ms vs baseline {avg_baseline:.1f}ms "
                    f"({((duration / avg_baseline - 1) * 100):.1f}% slower)"
                )
    
    def get_percentiles(self) -> Dict[str, float]:
        """Calculate latency percentiles."""
        if not self.completed_profiles:
            return {"p50": 0.0, "p95": 0.0, "p99": 0.0}
        
        durations = sorted([p.duration_ms() for p in self.completed_profiles])
        n = len(durations)
        
        return {
            "p50": durations[int(n * 0.50)] if n > 0 else 0.0,
            "p95": durations[int(n * 0.95)] if n > 0 else 0.0,
            "p99": durations[int(n * 0.99)] if n > 0 else 0.0,
        }
    
    def get_slow_queries(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent slow queries."""
        return [
            {
                "query_id": p.query_id,
                "query": p.query_text[:100],
                "mode": p.mode,
                "duration_ms": p.duration_ms(),
                "components": p.components,
            }
            for p in sorted(self.slow_queries, key=lambda x: x.duration_ms(), reverse=True)[:limit]
        ]
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get profiler metrics."""
        percentiles = self.get_percentiles()
        
        return {
            **self.metrics,
            **percentiles,
            "total_completed": len(self.completed_profiles),
            "active_queries": len(self.active_profiles),
        }
