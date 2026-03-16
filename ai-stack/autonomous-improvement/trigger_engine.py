#!/usr/bin/env python3
"""
Trigger Engine - Local LLM-powered autonomous improvement trigger
Uses llama.cpp at localhost:8080 to analyze system metrics and decide
when to trigger improvement cycles based on anomaly patterns
"""

import asyncio
import json
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiohttp
import psycopg2
from psycopg2.extras import RealDictCursor

from trend_database import TrendDatabase


@dataclass
class TriggerEvent:
    """
    Event that triggered an improvement cycle
    """
    id: str
    trigger_type: str  # anomaly, schedule, threshold, event
    trigger_source: str  # baseline_profiler, prometheus, trend_analysis, manual
    severity: str  # low, medium, high, critical
    metric_name: Optional[str]
    observed_value: Optional[float]
    threshold_value: Optional[float]
    context: Dict[str, Any]
    triggered_at: datetime

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d['triggered_at'] = self.triggered_at.isoformat()
        return d


class TriggerEngine:
    """
    Analyzes metrics using local LLM and triggers improvement cycles
    """

    def __init__(
        self,
        llm_url: str = "http://localhost:8080/v1/chat/completions",
        pg_host: str = "127.0.0.1",
        pg_port: int = 5432,
        pg_user: str = "aidb",
        pg_database: str = "aidb",
        pg_password: Optional[str] = None,
    ):
        self.llm_url = llm_url
        self.pg_host = pg_host
        self.pg_port = pg_port
        self.pg_user = pg_user
        self.pg_database = pg_database
        self.pg_password = pg_password

        self.trend_db = TrendDatabase(
            pg_host=pg_host,
            pg_port=pg_port,
            pg_user=pg_user,
            pg_database=pg_database,
            pg_password=pg_password,
        )

        # Trigger thresholds
        self.degradation_threshold = -10.0  # % change
        self.volatility_threshold = 0.4
        self.cooldown_minutes = 60  # Don't trigger same metric twice within 1 hour

    async def call_local_llm(
        self,
        prompt: str,
        max_tokens: int = 500,
        temperature: float = 0.3,
    ) -> str:
        """
        Call local llama.cpp for analysis
        Low temperature for consistent, analytical responses
        """
        payload = {
            "model": "local",
            "messages": [
                {
                    "role": "system",
                    "content": "You are an AI system performance analyst. "
                               "Analyze metrics and provide concise, actionable insights. "
                               "Focus on root causes and specific recommendations."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(self.llm_url, json=payload, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status != 200:
                    raise Exception(f"LLM API error: {resp.status}")

                result = await resp.json()
                return result["choices"][0]["message"]["content"]

    async def analyze_anomalies_with_llm(
        self,
        anomalies: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Use local LLM to analyze anomalies and determine if they warrant a trigger
        Returns analysis with should_trigger flag and reasoning
        """
        if not anomalies:
            return {
                "should_trigger": False,
                "reasoning": "No anomalies detected",
                "severity": "low",
            }

        # Build context for LLM
        anomaly_summary = []
        for anomaly in anomalies:
            if anomaly["type"] == "degrading_trend":
                anomaly_summary.append(
                    f"- {anomaly['metric_name']} degraded by {anomaly['change_pct']:.1f}% "
                    f"(from {anomaly['baseline_value']:.2f} to {anomaly['current_value']:.2f})"
                )
            elif anomaly["type"] == "high_volatility":
                anomaly_summary.append(
                    f"- {anomaly['metric_name']} is volatile (CV: {anomaly['volatility']:.2f}) "
                    f"current: {anomaly['current_value']:.2f}"
                )

        prompt = f"""Analyze these AI system performance anomalies:

{chr(10).join(anomaly_summary)}

Should we trigger an autonomous improvement cycle? Consider:
1. Severity and impact on system performance
2. Whether multiple metrics are affected (systemic issue)
3. Potential for automated optimization

Respond in JSON format:
{{
  "should_trigger": true/false,
  "reasoning": "Brief explanation (1-2 sentences)",
  "severity": "low/medium/high/critical",
  "recommended_focus": "area to focus improvement efforts"
}}"""

        try:
            response = await self.call_local_llm(prompt, max_tokens=200)

            # Parse JSON response
            # LLM might wrap JSON in markdown code blocks
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                response = response.split("```")[1].split("```")[0].strip()

            analysis = json.loads(response)

            # Validate required fields
            if "should_trigger" not in analysis:
                analysis["should_trigger"] = False
            if "severity" not in analysis:
                analysis["severity"] = "medium"
            if "reasoning" not in analysis:
                analysis["reasoning"] = "LLM analysis incomplete"

            return analysis

        except Exception as e:
            print(f"⚠️  LLM analysis failed: {e}")
            # Fallback: trigger on high-severity anomalies
            high_severity_count = sum(1 for a in anomalies if a.get("severity") == "high")

            return {
                "should_trigger": high_severity_count > 0,
                "reasoning": f"LLM unavailable, fallback triggered on {high_severity_count} high-severity anomalies",
                "severity": "high" if high_severity_count > 0 else "medium",
                "recommended_focus": "metric_degradation",
            }

    def check_cooldown(self, metric_name: str) -> bool:
        """
        Check if enough time has passed since last trigger for this metric
        Returns True if cooldown period has elapsed
        """
        conn = psycopg2.connect(
            host=self.pg_host,
            port=self.pg_port,
            user=self.pg_user,
            database=self.pg_database,
            password=self.pg_password,
        )

        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT triggered_at
                FROM trigger_events
                WHERE metric_name = %s
                ORDER BY triggered_at DESC
                LIMIT 1
                """,
                (metric_name,)
            )

            row = cursor.fetchone()
            if not row:
                return True  # No previous triggers

            last_trigger = row[0]
            if isinstance(last_trigger, str):
                last_trigger = datetime.fromisoformat(last_trigger)

            elapsed_minutes = (datetime.now() - last_trigger).total_seconds() / 60

            return elapsed_minutes >= self.cooldown_minutes

        finally:
            conn.close()

    def record_trigger_event(self, trigger: TriggerEvent) -> str:
        """
        Record trigger event to PostgreSQL
        Returns trigger event ID
        """
        conn = psycopg2.connect(
            host=self.pg_host,
            port=self.pg_port,
            user=self.pg_user,
            database=self.pg_database,
            password=self.pg_password,
        )

        try:
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO trigger_events
                    (id, trigger_type, trigger_source, severity, metric_name,
                     observed_value, threshold_value, context, triggered_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    trigger.id,
                    trigger.trigger_type,
                    trigger.trigger_source,
                    trigger.severity,
                    trigger.metric_name,
                    trigger.observed_value,
                    trigger.threshold_value,
                    json.dumps(trigger.context),
                    trigger.triggered_at,
                ),
            )

            conn.commit()
            trigger_id = cursor.fetchone()[0]

            return trigger_id

        finally:
            conn.close()

    async def check_and_trigger(self) -> Optional[TriggerEvent]:
        """
        Main trigger check loop:
        1. Detect anomalies from trend database
        2. Analyze with local LLM
        3. Trigger improvement cycle if warranted
        Returns TriggerEvent if triggered, None otherwise
        """
        # Step 1: Detect anomalies
        anomalies = self.trend_db.detect_anomalies()

        if not anomalies:
            print("✅ No anomalies detected - system healthy")
            return None

        print(f"🔍 Detected {len(anomalies)} anomalies, analyzing with local LLM...")

        # Step 2: Filter by cooldown
        filtered_anomalies = []
        for anomaly in anomalies:
            metric_name = anomaly.get("metric_name")
            if metric_name and self.check_cooldown(metric_name):
                filtered_anomalies.append(anomaly)
            else:
                print(f"   ⏳ Cooldown active for {metric_name}, skipping")

        if not filtered_anomalies:
            print("⏳ All anomalies in cooldown period")
            return None

        # Step 3: LLM analysis
        analysis = await self.analyze_anomalies_with_llm(filtered_anomalies)

        print(f"🤖 LLM Analysis:")
        print(f"   Should trigger: {analysis['should_trigger']}")
        print(f"   Severity: {analysis['severity']}")
        print(f"   Reasoning: {analysis['reasoning']}")

        if not analysis["should_trigger"]:
            print("✋ LLM decided not to trigger improvement cycle")
            return None

        # Step 4: Create trigger event
        # Use the most severe anomaly as the primary trigger
        primary_anomaly = max(
            filtered_anomalies,
            key=lambda a: {"critical": 4, "high": 3, "medium": 2, "low": 1}.get(a.get("severity", "low"), 0)
        )

        trigger = TriggerEvent(
            id=str(uuid.uuid4()),
            trigger_type="anomaly",
            trigger_source="trend_analysis_llm",
            severity=analysis["severity"],
            metric_name=primary_anomaly.get("metric_name"),
            observed_value=primary_anomaly.get("current_value"),
            threshold_value=primary_anomaly.get("baseline_value"),
            context={
                "anomalies": filtered_anomalies,
                "llm_analysis": analysis,
                "anomaly_count": len(filtered_anomalies),
            },
            triggered_at=datetime.now(),
        )

        # Step 5: Record trigger
        trigger_id = self.record_trigger_event(trigger)

        print(f"🚀 Improvement cycle triggered: {trigger_id}")
        print(f"   Focus area: {analysis.get('recommended_focus', 'general')}")

        return trigger


async def main():
    """
    Example usage: periodic trigger check
    """
    # Read password from secrets
    pg_password = None
    secret_path = Path("/run/secrets/postgres_password")
    if secret_path.exists():
        pg_password = secret_path.read_text().strip()

    engine = TriggerEngine(pg_password=pg_password)

    print("🔧 Trigger Engine - Autonomous Improvement")
    print("=" * 60)

    # First, sync metrics to get latest data
    print("\n📊 Syncing metrics from all sources...")
    await engine.trend_db.sync_metrics_pipeline(since_hours=24)

    # Then check for triggers
    print("\n🔍 Checking for trigger conditions...")
    trigger = await engine.check_and_trigger()

    if trigger:
        print(f"\n✅ Trigger recorded: {trigger.id}")
        print(f"   Next step: Launch research phase to analyze {trigger.metric_name}")
    else:
        print("\n✅ No triggers - system operating normally")


if __name__ == "__main__":
    asyncio.run(main())
