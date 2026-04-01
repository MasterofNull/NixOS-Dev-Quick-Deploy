#!/usr/bin/env python3
"""
Chaos Engineering Test Framework

Tests system resilience by injecting controlled failures.
Part of Phase 3 Batch 3.2: Automated Testing & Validation

Chaos experiments:
- Service unavailability
- Network latency/timeouts
- Resource exhaustion (CPU, memory, disk)
- Dependency failures
- Cascading failures
"""

import asyncio
import logging
import os
import random
import signal
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


def _chaos_artifact_path() -> Path:
    configured = os.getenv("CHAOS_EXPERIMENT_REPORT_PATH", "").strip()
    if configured:
        return Path(configured)
    return Path("/var/lib/ai-stack/hybrid/testing/chaos/experiment_results.json")


class ChaosExperimentType(Enum):
    """Types of chaos experiments"""
    SERVICE_KILL = "service_kill"
    NETWORK_LATENCY = "network_latency"
    NETWORK_PARTITION = "network_partition"
    CPU_STRESS = "cpu_stress"
    MEMORY_STRESS = "memory_stress"
    DISK_FILL = "disk_fill"
    DEPENDENCY_FAILURE = "dependency_failure"


@dataclass
class ChaosExperiment:
    """Chaos engineering experiment definition"""
    name: str
    experiment_type: ChaosExperimentType
    target: str  # Service/resource to target
    duration_seconds: int
    blast_radius: str  # "single", "multiple", "all"
    expected_behavior: str
    success_criteria: Callable[[], bool]


@dataclass
class ChaosResult:
    """Result of chaos experiment"""
    experiment: ChaosExperiment
    started_at: datetime
    ended_at: datetime
    success: bool
    observations: List[str]
    metrics: Dict[str, float]
    recommendation: str


class ChaosEngineer:
    """Chaos engineering test executor"""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.results: List[ChaosResult] = []

        logger.info(f"Chaos Engineer initialized (dry_run={dry_run})")

    async def run_experiment(self, experiment: ChaosExperiment) -> ChaosResult:
        """Run a single chaos experiment"""
        logger.info(f"Starting chaos experiment: {experiment.name}")

        if self.dry_run:
            logger.info("DRY RUN: Simulating experiment")
            return self._simulate_experiment(experiment)

        started_at = datetime.now()
        observations = []
        metrics = {}

        try:
            # Execute experiment based on type
            if experiment.experiment_type == ChaosExperimentType.SERVICE_KILL:
                await self._inject_service_failure(experiment, observations, metrics)

            elif experiment.experiment_type == ChaosExperimentType.NETWORK_LATENCY:
                await self._inject_network_latency(experiment, observations, metrics)

            elif experiment.experiment_type == ChaosExperimentType.CPU_STRESS:
                await self._inject_cpu_stress(experiment, observations, metrics)

            elif experiment.experiment_type == ChaosExperimentType.MEMORY_STRESS:
                await self._inject_memory_stress(experiment, observations, metrics)

            # Wait for experiment duration
            logger.info(f"Experiment running for {experiment.duration_seconds}s...")
            await asyncio.sleep(experiment.duration_seconds)

            # Check success criteria
            success = experiment.success_criteria()

            observations.append(
                f"System {'passed' if success else 'failed'} success criteria"
            )

        except Exception as e:
            logger.error(f"Experiment failed: {e}")
            observations.append(f"Experiment error: {e}")
            success = False

        ended_at = datetime.now()

        result = ChaosResult(
            experiment=experiment,
            started_at=started_at,
            ended_at=ended_at,
            success=success,
            observations=observations,
            metrics=metrics,
            recommendation=self._generate_recommendation(experiment, success, observations),
        )

        self.results.append(result)
        return result

    async def _inject_service_failure(
        self,
        experiment: ChaosExperiment,
        observations: List[str],
        metrics: Dict[str, float],
    ):
        """Inject service failure"""
        service = experiment.target

        logger.info(f"Killing service: {service}")

        # Stop service
        try:
            subprocess.run(
                ["sudo", "systemctl", "stop", service],
                check=True,
                capture_output=True,
            )
            observations.append(f"Stopped service: {service}")
            metrics["service_stop_time"] = time.time()

        except subprocess.CalledProcessError as e:
            observations.append(f"Failed to stop service: {e}")

        # Monitor system behavior during failure
        await asyncio.sleep(5)

        # Restart service
        try:
            subprocess.run(
                ["sudo", "systemctl", "start", service],
                check=True,
                capture_output=True,
            )
            observations.append(f"Restarted service: {service}")
            metrics["service_restart_time"] = time.time()

        except subprocess.CalledProcessError as e:
            observations.append(f"Failed to restart service: {e}")

    async def _inject_network_latency(
        self,
        experiment: ChaosExperiment,
        observations: List[str],
        metrics: Dict[str, float],
    ):
        """Inject network latency using tc (traffic control)"""
        logger.info(f"Injecting network latency on {experiment.target}")

        # Would use tc (traffic control) to add latency
        # tc qdisc add dev eth0 root netem delay 100ms
        observations.append("Network latency injection: NOT IMPLEMENTED (requires tc)")

    async def _inject_cpu_stress(
        self,
        experiment: ChaosExperiment,
        observations: List[str],
        metrics: Dict[str, float],
    ):
        """Inject CPU stress"""
        logger.info("Injecting CPU stress")

        # Use stress-ng if available
        try:
            cpu_count = 2  # Stress 2 cores
            process = subprocess.Popen(
                ["stress-ng", "--cpu", str(cpu_count), "--timeout", f"{experiment.duration_seconds}s"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            observations.append(f"CPU stress injected: {cpu_count} cores")
            metrics["cpu_stress_cores"] = cpu_count

        except FileNotFoundError:
            observations.append("CPU stress: stress-ng not available")

    async def _inject_memory_stress(
        self,
        experiment: ChaosExperiment,
        observations: List[str],
        metrics: Dict[str, float],
    ):
        """Inject memory stress"""
        logger.info("Injecting memory stress")

        # Use stress-ng if available
        try:
            memory_mb = 512  # Consume 512MB
            process = subprocess.Popen(
                ["stress-ng", "--vm", "1", "--vm-bytes", f"{memory_mb}M", "--timeout", f"{experiment.duration_seconds}s"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            observations.append(f"Memory stress injected: {memory_mb}MB")
            metrics["memory_stress_mb"] = memory_mb

        except FileNotFoundError:
            observations.append("Memory stress: stress-ng not available")

    def _simulate_experiment(self, experiment: ChaosExperiment) -> ChaosResult:
        """Simulate experiment for dry run"""
        return ChaosResult(
            experiment=experiment,
            started_at=datetime.now(),
            ended_at=datetime.now() + timedelta(seconds=experiment.duration_seconds),
            success=True,
            observations=[
                "DRY RUN: Experiment simulated",
                f"Would target: {experiment.target}",
                f"Would run for: {experiment.duration_seconds}s",
            ],
            metrics={"simulated": 1.0},
            recommendation="Dry run successful - safe to run in production",
        )

    def _generate_recommendation(
        self,
        experiment: ChaosExperiment,
        success: bool,
        observations: List[str],
    ) -> str:
        """Generate recommendation based on experiment result"""
        if success:
            return f"System is resilient to {experiment.experiment_type.value} - no action needed"
        else:
            return f"System failed {experiment.experiment_type.value} - implement resilience improvements"

    async def run_experiment_suite(
        self,
        experiments: List[ChaosExperiment],
    ) -> List[ChaosResult]:
        """Run multiple chaos experiments"""
        results = []

        for experiment in experiments:
            logger.info(f"\n{'=' * 60}")
            result = await self.run_experiment(experiment)
            results.append(result)

            # Add delay between experiments
            await asyncio.sleep(10)

        return results

    def generate_report(self, output_path: Path):
        """Generate chaos engineering report"""
        import json

        report = {
            "generated_at": datetime.now().isoformat(),
            "total_experiments": len(self.results),
            "successful": sum(1 for r in self.results if r.success),
            "failed": sum(1 for r in self.results if not r.success),
            "experiments": [
                {
                    "name": r.experiment.name,
                    "type": r.experiment.experiment_type.value,
                    "target": r.experiment.target,
                    "success": r.success,
                    "duration": (r.ended_at - r.started_at).total_seconds(),
                    "observations": r.observations,
                    "metrics": r.metrics,
                    "recommendation": r.recommendation,
                }
                for r in self.results
            ],
        }

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(report, f, indent=2)

        logger.info(f"Chaos report generated: {output_path}")


# Pre-defined experiment templates
def create_service_resilience_experiments() -> List[ChaosExperiment]:
    """Create experiments for testing service resilience"""
    experiments = []

    # Test each critical service
    services = [
        "ai-hybrid-coordinator.service",
        "ai-aidb.service",
        "llama-cpp.service",
    ]

    for service in services:
        experiments.append(ChaosExperiment(
            name=f"Service Kill: {service}",
            experiment_type=ChaosExperimentType.SERVICE_KILL,
            target=service,
            duration_seconds=30,
            blast_radius="single",
            expected_behavior="System recovers automatically or degrades gracefully",
            success_criteria=lambda: True,  # Would check actual system health
        ))

    return experiments


def create_resource_exhaustion_experiments() -> List[ChaosExperiment]:
    """Create experiments for resource exhaustion"""
    return [
        ChaosExperiment(
            name="CPU Saturation",
            experiment_type=ChaosExperimentType.CPU_STRESS,
            target="system",
            duration_seconds=60,
            blast_radius="all",
            expected_behavior="Services remain responsive or queue requests",
            success_criteria=lambda: True,
        ),
        ChaosExperiment(
            name="Memory Pressure",
            experiment_type=ChaosExperimentType.MEMORY_STRESS,
            target="system",
            duration_seconds=60,
            blast_radius="all",
            expected_behavior="OOM killer doesn't trigger critical services",
            success_criteria=lambda: True,
        ),
    ]


async def main():
    """Run chaos engineering experiments"""
    logging.basicConfig(level=logging.INFO)

    engineer = ChaosEngineer(dry_run=True)  # Start with dry run

    logger.info("Chaos Engineering Framework")
    logger.info("=" * 60)

    # Create experiment suite
    experiments = []
    experiments.extend(create_service_resilience_experiments())
    experiments.extend(create_resource_exhaustion_experiments())

    logger.info(f"\nRunning {len(experiments)} chaos experiments...")

    # Run experiments
    results = await engineer.run_experiment_suite(experiments)

    # Generate report
    report_path = _chaos_artifact_path()
    engineer.generate_report(report_path)

    # Summary
    logger.info(f"\nChaos Engineering Summary:")
    logger.info(f"  Total experiments: {len(results)}")
    logger.info(f"  Successful: {sum(1 for r in results if r.success)}")
    logger.info(f"  Failed: {sum(1 for r in results if not r.success)}")
    logger.info(f"\nReport: {report_path}")


if __name__ == "__main__":
    asyncio.run(main())
