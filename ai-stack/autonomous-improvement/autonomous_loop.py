#!/usr/bin/env python3
"""
Autonomous Improvement Loop - Main Orchestrator

Orchestrates the complete improvement cycle driven by local LLM:
  Trigger → Research → Execute → Validate → Learn

This is the "brain" that makes the system continuously self-improving
without human intervention.
"""

import asyncio
import json
import sys
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import psycopg2
from psycopg2.extras import RealDictCursor

from trend_database import TrendDatabase
from trigger_engine import TriggerEngine, TriggerEvent
from research_phase import ResearchPhase, OptimizationHypothesis


@dataclass
class ImprovementCycle:
    """
    Complete improvement cycle from trigger to validation
    """
    id: str
    cycle_type: str  # autoresearch, anomaly_response, scheduled, manual
    triggered_by: Optional[str]  # trigger_event.id
    research_summary: Optional[Dict[str, Any]]
    experiments_run: int = 0
    experiments_accepted: int = 0
    experiments_rejected: int = 0
    total_improvement_pct: Optional[float] = None
    cost_tokens: int = 0
    cost_dollars: float = 0.0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: str = "pending"  # pending, running, completed, failed, cancelled
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if self.started_at:
            d['started_at'] = self.started_at.isoformat()
        if self.completed_at:
            d['completed_at'] = self.completed_at.isoformat()
        return d


class AutonomousLoop:
    """
    Main orchestrator for autonomous improvement cycles
    """

    def __init__(
        self,
        pg_host: str = "127.0.0.1",
        pg_port: int = 5432,
        pg_user: str = "aidb",
        pg_database: str = "aidb",
        pg_password: Optional[str] = None,
        dry_run: bool = False,
    ):
        self.pg_host = pg_host
        self.pg_port = pg_port
        self.pg_user = pg_user
        self.pg_database = pg_database
        self.pg_password = pg_password
        self.dry_run = dry_run

        # Initialize components
        self.trend_db = TrendDatabase(
            pg_host=pg_host,
            pg_port=pg_port,
            pg_user=pg_user,
            pg_database=pg_database,
            pg_password=pg_password,
        )

        self.trigger_engine = TriggerEngine(
            pg_host=pg_host,
            pg_port=pg_port,
            pg_user=pg_user,
            pg_database=pg_database,
            pg_password=pg_password,
        )

        self.research_phase = ResearchPhase(
            pg_host=pg_host,
            pg_port=pg_port,
            pg_user=pg_user,
            pg_database=pg_database,
            pg_password=pg_password,
        )

    def get_connection(self) -> psycopg2.extensions.connection:
        """Get PostgreSQL connection"""
        return psycopg2.connect(
            host=self.pg_host,
            port=self.pg_port,
            user=self.pg_user,
            database=self.pg_database,
            password=self.pg_password,
        )

    def create_cycle(
        self,
        cycle_type: str,
        triggered_by: Optional[str] = None,
    ) -> ImprovementCycle:
        """
        Create new improvement cycle in database
        """
        cycle = ImprovementCycle(
            id=str(uuid.uuid4()),
            cycle_type=cycle_type,
            triggered_by=triggered_by,
            research_summary=None,
            started_at=datetime.now(),
            status="running",
        )

        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO improvement_cycles
                    (id, cycle_type, triggered_by, started_at, status)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (cycle.id, cycle.cycle_type, cycle.triggered_by,
                 cycle.started_at, cycle.status),
            )
            conn.commit()
            cursor.close()
        finally:
            conn.close()

        return cycle

    def update_cycle(self, cycle: ImprovementCycle):
        """
        Update improvement cycle in database
        """
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE improvement_cycles
                SET research_summary = %s,
                    experiments_run = %s,
                    experiments_accepted = %s,
                    experiments_rejected = %s,
                    total_improvement_pct = %s,
                    cost_tokens = %s,
                    cost_dollars = %s,
                    completed_at = %s,
                    status = %s,
                    error_message = %s,
                    metadata = %s
                WHERE id = %s
                """,
                (
                    json.dumps(cycle.research_summary) if cycle.research_summary else None,
                    cycle.experiments_run,
                    cycle.experiments_accepted,
                    cycle.experiments_rejected,
                    cycle.total_improvement_pct,
                    cycle.cost_tokens,
                    cycle.cost_dollars,
                    cycle.completed_at,
                    cycle.status,
                    cycle.error_message,
                    json.dumps(cycle.metadata) if cycle.metadata else None,
                    cycle.id,
                ),
            )
            conn.commit()
            cursor.close()
        finally:
            conn.close()

    async def run_improvement_cycle(
        self,
        cycle_type: str = "scheduled",
    ) -> Optional[ImprovementCycle]:
        """
        Run complete improvement cycle:
        1. Sync metrics
        2. Check for triggers
        3. Research (if triggered)
        4. Execute experiments (placeholder for now)
        5. Validate and learn
        """
        print("🔄 Autonomous Improvement Loop")
        print("=" * 70)
        print(f"Cycle type: {cycle_type}")
        print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Dry run: {self.dry_run}")
        print()

        # Phase 1: Sync Metrics
        print("📊 Phase 1: Syncing metrics from all sources...")
        try:
            stats = await self.trend_db.sync_metrics_pipeline(since_hours=24)
            print(f"   ✅ Metrics collected: {stats['metrics_collected']}")
            print(f"   ✅ Metrics inserted: {stats['metrics_inserted']}")
            print(f"   ✅ Trends updated: {stats['trends_updated']}")
            print(f"   ✅ Anomalies detected: {stats['anomalies_detected']}")
            print()
        except Exception as e:
            print(f"   ❌ Metric sync failed: {e}")
            return None

        # Phase 2: Check Triggers
        print("🎯 Phase 2: Checking trigger conditions...")
        try:
            trigger = await self.trigger_engine.check_and_trigger()

            if not trigger:
                print("   ✅ No triggers - system operating normally")
                return None

            print(f"   🚀 Trigger activated: {trigger.id}")
            print(f"   📍 Severity: {trigger.severity}")
            print(f"   📊 Metric: {trigger.metric_name}")
            print()

        except Exception as e:
            print(f"   ❌ Trigger check failed: {e}")
            return None

        # Create improvement cycle
        cycle = self.create_cycle(
            cycle_type="anomaly_response",
            triggered_by=trigger.id,
        )

        try:
            # Phase 3: Research
            print("🔬 Phase 3: Research - Local LLM generating hypotheses...")
            try:
                hypotheses = await self.research_phase.conduct_research(
                    trigger_event_id=trigger.id,
                )

                if not hypotheses:
                    print("   ⚠️  No optimization hypotheses generated")
                    cycle.status = "completed"
                    cycle.completed_at = datetime.now()
                    cycle.research_summary = {
                        "trigger_id": trigger.id,
                        "hypotheses_generated": 0,
                        "reason": "No actionable optimization opportunities found"
                    }
                    self.update_cycle(cycle)
                    return cycle

                cycle.research_summary = {
                    "trigger_id": trigger.id,
                    "hypotheses_generated": len(hypotheses),
                    "top_hypothesis": hypotheses[0].to_dict() if hypotheses else None,
                }

                print(f"   ✅ Generated {len(hypotheses)} hypotheses")
                print()

            except Exception as e:
                print(f"   ❌ Research phase failed: {e}")
                cycle.status = "failed"
                cycle.error_message = f"Research phase error: {str(e)}"
                cycle.completed_at = datetime.now()
                self.update_cycle(cycle)
                return cycle

            # Phase 4: Execute Experiments
            print("🧪 Phase 4: Experiment Execution...")
            if self.dry_run:
                print("   🏃 DRY RUN MODE - Skipping actual experiment execution")
                print(f"   Would execute: {hypotheses[0].description}")
                print(f"   Experiment config: {json.dumps(hypotheses[0].experiment_config, indent=2)}")
                cycle.experiments_run = 0
                cycle.experiments_accepted = 0
                cycle.experiments_rejected = 0
            else:
                print("   ⏸️  Experiment execution not yet implemented")
                print("   📝 Next: Integrate with existing autoresearch framework")
                print(f"   Top hypothesis: {hypotheses[0].description}")

                # Placeholder: In real implementation, would:
                # 1. Convert hypothesis to autoresearch experiment config
                # 2. Run A/B test (baseline vs variant)
                # 3. Collect metrics and compute statistical significance
                # 4. Auto-accept if improvement >5% and p<0.05
                # 5. Apply changes to production if accepted

                cycle.experiments_run = 0
                cycle.experiments_accepted = 0
                cycle.experiments_rejected = 0

            print()

            # Phase 5: Validate & Learn
            print("✅ Phase 5: Validation & Learning...")
            print(f"   Cycle completed successfully")
            print(f"   Hypotheses generated: {len(hypotheses)}")
            print(f"   Experiments run: {cycle.experiments_run}")
            print(f"   Ready for execution when autoresearch integration complete")
            print()

            # Mark cycle complete
            cycle.status = "completed"
            cycle.completed_at = datetime.now()
            cycle.total_improvement_pct = 0.0  # Will be updated when experiments run
            self.update_cycle(cycle)

            return cycle

        except Exception as e:
            print(f"❌ Cycle failed: {e}")
            cycle.status = "failed"
            cycle.error_message = str(e)
            cycle.completed_at = datetime.now()
            self.update_cycle(cycle)
            raise

    async def run_once(self) -> bool:
        """
        Run one improvement cycle check
        Returns True if cycle was executed, False if no trigger
        """
        cycle = await self.run_improvement_cycle(cycle_type="scheduled")
        return cycle is not None

    async def run_daemon(self, interval_minutes: int = 60):
        """
        Run continuously, checking for improvements every interval
        """
        print(f"🤖 Autonomous Improvement Daemon Started")
        print(f"   Checking every {interval_minutes} minutes")
        print(f"   Press Ctrl+C to stop")
        print()

        while True:
            try:
                await self.run_once()
            except KeyboardInterrupt:
                print("\n⏸️  Daemon stopped by user")
                break
            except Exception as e:
                print(f"❌ Cycle error: {e}")
                print("   Will retry on next interval")

            # Wait for next interval
            await asyncio.sleep(interval_minutes * 60)


async def main():
    """
    Main entry point - run one improvement cycle
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="Autonomous Improvement Loop - Local LLM-driven system optimization"
    )
    parser.add_argument(
        "--daemon",
        action="store_true",
        help="Run as daemon (continuous loop)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=60,
        help="Check interval in minutes for daemon mode (default: 60)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run mode - generate hypotheses but don't execute experiments",
    )

    args = parser.parse_args()

    # Read PostgreSQL password from secrets
    pg_password = None
    secret_path = Path("/run/secrets/postgres_password")
    if secret_path.exists():
        pg_password = secret_path.read_text().strip()

    # Create autonomous loop
    loop = AutonomousLoop(
        pg_password=pg_password,
        dry_run=args.dry_run,
    )

    # Run
    if args.daemon:
        await loop.run_daemon(interval_minutes=args.interval)
    else:
        cycle = await loop.run_improvement_cycle(cycle_type="manual")

        if cycle:
            print("\n📈 Improvement Cycle Summary")
            print("=" * 70)
            print(f"Cycle ID: {cycle.id}")
            print(f"Status: {cycle.status}")
            print(f"Duration: {(cycle.completed_at - cycle.started_at).total_seconds():.1f}s")
            print(f"Hypotheses: {cycle.research_summary.get('hypotheses_generated', 0) if cycle.research_summary else 0}")
            print(f"Experiments: {cycle.experiments_run} run, {cycle.experiments_accepted} accepted")

            if cycle.status == "failed":
                print(f"Error: {cycle.error_message}")
                sys.exit(1)
        else:
            print("\n✅ No improvement cycle needed - system healthy")


if __name__ == "__main__":
    asyncio.run(main())
