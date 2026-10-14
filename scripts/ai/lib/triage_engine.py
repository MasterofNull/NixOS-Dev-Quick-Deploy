#!/usr/bin/env python3
"""System 1 High-Frequency Stream Triage Engine (`aq-triage`).

Provides sub-second journald telemetry ingestion, persistent cursor tracking,
token-bucket flood limiting, and fast structured incident classification.
P95 classification latency target: < 200ms.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_DB_DIR = Path(os.getenv("AQ_TRIAGE_STATE_DIR") or _DEFAULT_REPO_ROOT / ".agent" / "triage")


@dataclass
class TriageClassification:
    incident_id: str
    source: str
    cursor: str
    timestamp: str
    severity: str  # "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | "NOISE"
    incident_class: str  # "CRASH" | "RESOURCE_EXHAUSTION" | "SECURITY_VIOLATION" | "TIMEOUT" | "HEALTH_CHECK_FAILURE" | "CONFIGURATION" | "BENIGN_INFO"
    confidence: float
    correlation_key: str
    actionable: bool
    suggested_lane: str  # "local" | "codex" | "antigravity"
    summary: str
    reproduction_cmd: Optional[str] = None


class TokenBucketLimiter:
    """Per-source token bucket rate limiter to prevent incident flood storms."""

    def __init__(self, capacity: int = 10, refill_rate_per_sec: float = 2.0) -> None:
        self.capacity = capacity
        self.refill_rate = refill_rate_per_sec
        self._tokens: Dict[str, float] = {}
        self._last_refill: Dict[str, float] = {}

    def allow(self, source: str, tokens_needed: float = 1.0, now: Optional[float] = None) -> bool:
        current_time = now if now is not None else time.time()
        tokens = self._tokens.get(source, float(self.capacity))
        last = self._last_refill.get(source, current_time)

        delta = max(0.0, current_time - last)
        tokens = min(float(self.capacity), tokens + (delta * self.refill_rate))
        self._last_refill[source] = current_time

        if tokens >= tokens_needed:
            self._tokens[source] = tokens - tokens_needed
            return True
        self._tokens[source] = tokens
        return False


class FastClassifier:
    """Fast, deterministic structured classifier for telemetry and journal logs."""

    # Normalization regexes to produce stable signature hashes
    _RE_UUID = re.compile(r"\b[0-9a-fA-F]{8}(-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}\b")
    _RE_HEX = re.compile(r"\b0x[0-9a-fA-F]+\b")
    _RE_IP = re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b")
    _RE_HASH = re.compile(r"\b[0-9a-fA-F]{16,64}\b")
    _RE_NUM = re.compile(r"\b\d+\b")

    _PATTERNS: List[Tuple[re.Pattern, str, str, float, str]] = [
        # (Pattern, severity, incident_class, base_confidence, suggested_lane)
        (re.compile(r"(out of memory|oom-killer|killed process|cannot allocate memory)", re.I),
         "CRITICAL", "RESOURCE_EXHAUSTION", 0.95, "local"),
        (re.compile(r"(kernel panic|segfault|segmentation fault|core dump|general protection fault)", re.I),
         "CRITICAL", "CRASH", 0.98, "local"),
        (re.compile(r"(private key|secret leak|cve-\d{4}-\d+|unauthorized access|privilege escalation)", re.I),
         "CRITICAL", "SECURITY_VIOLATION", 0.92, "antigravity"),
        (re.compile(r"(traceback \(most recent call last\)|exception group traceback|unhandled exception|fatal error)", re.I),
         "HIGH", "CRASH", 0.90, "local"),
        (re.compile(r"(failed to start|service loaded failed|unit .* in failed state|main process exited, code=exited, status=[^0])", re.I),
         "HIGH", "HEALTH_CHECK_FAILURE", 0.92, "local"),
        (re.compile(r"(connection refused|failed to connect to (postgres|redis|qdrant|127\.0\.0\.1|localhost))", re.I),
         "HIGH", "HEALTH_CHECK_FAILURE", 0.88, "local"),
        (re.compile(r"(timed out after|timeout waiting for|deadline exceeded|request timeout)", re.I),
         "HIGH", "TIMEOUT", 0.86, "codex"),
        (re.compile(r"(syntaxerror|parse error|invalid configuration|malformed json|unknown option)", re.I),
         "HIGH", "CONFIGURATION", 0.89, "codex"),
        (re.compile(r"(retry limit exceeded|restarting too quickly|loop error|degraded mode)", re.I),
         "MEDIUM", "HEALTH_CHECK_FAILURE", 0.80, "local"),
        (re.compile(r"(warning:|deprecated|temporary failure|connection reset by peer)", re.I),
         "LOW", "BENIGN_INFO", 0.70, "local"),
        (re.compile(r"(update_slots: all slots are idle|health check passed|started service|session completed successfully)", re.I),
         "NOISE", "BENIGN_INFO", 0.99, "local"),
    ]

    @classmethod
    def normalize_signature(cls, message: str) -> str:
        text = cls._RE_UUID.sub("<UUID>", message)
        text = cls._RE_HEX.sub("<HEX>", text)
        text = cls._RE_IP.sub("<IP>", text)
        text = cls._RE_HASH.sub("<HASH>", text)
        text = cls._RE_NUM.sub("<NUM>", text)
        return text.strip().lower()

    @classmethod
    def classify(cls, source: str, message: str, cursor: str = "", timestamp: str = "") -> TriageClassification:
        t0 = time.perf_counter()
        norm_sig = cls.normalize_signature(message)
        correlation_key = hashlib.sha256(f"{source}:{norm_sig}".encode("utf-8")).hexdigest()[:16]

        ts = timestamp or datetime.now(timezone.utc).isoformat()
        incident_id = hashlib.sha256(f"{source}:{ts}:{correlation_key}".encode("utf-8")).hexdigest()[:12]

        matched = False
        severity = "LOW"
        incident_class = "BENIGN_INFO"
        confidence = 0.50
        suggested_lane = "local"

        for pat, sev, cls_type, conf, lane in cls._PATTERNS:
            if pat.search(message):
                severity = sev
                incident_class = cls_type
                confidence = conf
                suggested_lane = lane
                matched = True
                break

        if not matched:
            # Fallback heuristic based on generic level keywords
            lower_msg = message.lower()
            if "err" in lower_msg or "fail" in lower_msg:
                severity = "MEDIUM"
                incident_class = "HEALTH_CHECK_FAILURE"
                confidence = 0.65
            elif "warn" in lower_msg:
                severity = "LOW"
                incident_class = "BENIGN_INFO"
                confidence = 0.60
            else:
                severity = "NOISE"
                incident_class = "BENIGN_INFO"
                confidence = 0.75

        actionable = severity in ("CRITICAL", "HIGH") and confidence >= 0.85
        summary = message.strip().splitlines()[0][:120] if message else "empty message"

        repro_cmd = None
        if actionable and source:
            repro_cmd = f"journalctl -u {source} -n 20 --no-pager"

        return TriageClassification(
            incident_id=incident_id,
            source=source or "unknown",
            cursor=cursor,
            timestamp=ts,
            severity=severity,
            incident_class=incident_class,
            confidence=round(confidence, 4),
            correlation_key=correlation_key,
            actionable=actionable,
            suggested_lane=suggested_lane,
            summary=summary,
            reproduction_cmd=repro_cmd,
        )


class JournalStreamTriage:
    """Manages persistent cursor storage, stream ingestion, and telemetry metrics."""

    def __init__(self, state_dir: Optional[Path] = None) -> None:
        self.state_dir = state_dir or _DEFAULT_DB_DIR
        self.limiter = TokenBucketLimiter(capacity=15, refill_rate_per_sec=3.0)
        fallback_dir = Path("/tmp") / f"aq-triage-{os.getuid() if hasattr(os, 'getuid') else 'user'}"
        try:
            self.state_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = self.state_dir / "triage_state.sqlite"
            self._init_db()
        except OSError:
            try:
                fallback_dir.mkdir(parents=True, exist_ok=True)
                self.state_dir = fallback_dir
                self.db_path = self.state_dir / "triage_state.sqlite"
                self._init_db()
            except OSError:
                self.db_path = Path(":memory:")
                self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cursors (
                    subsystem TEXT PRIMARY KEY,
                    last_cursor TEXT NOT NULL,
                    last_timestamp TEXT NOT NULL,
                    updated_at REAL NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS telemetry_metrics (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    total_ingested INTEGER NOT NULL DEFAULT 0,
                    total_actionable INTEGER NOT NULL DEFAULT 0,
                    p95_latency_ms REAL NOT NULL DEFAULT 0.0,
                    updated_at REAL NOT NULL
                )
            """)
            conn.execute("""
                INSERT OR IGNORE INTO telemetry_metrics (id, total_ingested, total_actionable, p95_latency_ms, updated_at)
                VALUES (1, 0, 0, 0.0, 0.0)
            """)
            conn.commit()

    def get_cursor(self, subsystem: str = "journald") -> Tuple[str, str]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT last_cursor, last_timestamp FROM cursors WHERE subsystem = ?", (subsystem,))
            row = cursor.fetchone()
            if row:
                return str(row[0]), str(row[1])
            return "", ""

    def update_cursor(self, subsystem: str, cursor_val: str, timestamp_val: str) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO cursors (subsystem, last_cursor, last_timestamp, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(subsystem) DO UPDATE SET
                    last_cursor = excluded.last_cursor,
                    last_timestamp = excluded.last_timestamp,
                    updated_at = excluded.updated_at
            """, (subsystem, cursor_val, timestamp_val, time.time()))
            conn.commit()

    def ingest_entries(self, entries: List[Dict[str, Any]], subsystem: str = "journald") -> List[TriageClassification]:
        """Classify a batch of log/journal entries and advance the persistent cursor."""
        classifications: List[TriageClassification] = []
        actionable_count = 0
        latencies_ms: List[float] = []
        last_cursor = ""
        last_ts = ""

        for entry in entries:
            source = entry.get("_SYSTEMD_UNIT") or entry.get("unit") or entry.get("source") or "system"
            if not self.limiter.allow(source):
                # Leave the cursor before this entry so the next poll can retry it.
                break

            msg = entry.get("MESSAGE") or entry.get("message") or ""
            cursor_val = entry.get("__CURSOR") or entry.get("cursor") or ""
            ts = entry.get("__REALTIME_TIMESTAMP") or entry.get("timestamp") or ""

            t_start = time.perf_counter()
            classified = FastClassifier.classify(source=source, message=str(msg), cursor=cursor_val, timestamp=str(ts))
            duration_ms = (time.perf_counter() - t_start) * 1000.0
            latencies_ms.append(duration_ms)

            classifications.append(classified)
            if classified.actionable:
                actionable_count += 1
            if cursor_val:
                last_cursor = cursor_val
            if ts:
                last_ts = str(ts)

        if last_cursor or last_ts:
            self.update_cursor(subsystem, last_cursor, last_ts)

        # Update telemetry metrics
        if latencies_ms:
            latencies_ms.sort()
            idx = int(0.95 * len(latencies_ms))
            p95 = latencies_ms[idx if idx < len(latencies_ms) else -1]
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    UPDATE telemetry_metrics SET
                        total_ingested = total_ingested + ?,
                        total_actionable = total_actionable + ?,
                        p95_latency_ms = ?,
                        updated_at = ?
                    WHERE id = 1
                """, (len(classifications), actionable_count, round(p95, 3), time.time()))
                conn.commit()

        return classifications

    def ingest_live_journal(self, units: Optional[List[str]] = None, limit: int = 50) -> List[TriageClassification]:
        """Query live journald via journalctl -o json, applying persistent cursor if present."""
        last_cursor, _ = self.get_cursor("journald")
        cmd = ["journalctl", "-o", "json", "-n", str(limit), "--no-pager"]
        if last_cursor:
            cmd.extend(["--after-cursor", last_cursor])
        if units:
            for u in units:
                cmd.extend(["-u", u])

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=10, check=False)
            if res.returncode != 0 and not res.stdout:
                return []
            entries = []
            for line in res.stdout.splitlines():
                line = line.strip()
                if line.startswith("{") and line.endswith("}"):
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
            return self.ingest_entries(entries, subsystem="journald")
        except (subprocess.TimeoutExpired, OSError):
            return []

    def benchmark(self, sample_count: int = 500) -> Dict[str, Any]:
        """Benchmark classification latency across synthetic telemetry samples. Target P95 < 200ms."""
        sample_messages = [
            ("ai-hybrid-coordinator.service", "Traceback (most recent call last):\n  File 'main.py', line 12: NameError: foo"),
            ("llama-cpp.service", "kernel: oom-killer: killed process llama-server pid 9821"),
            ("postgres.service", "LOG: database system is ready to accept connections"),
            ("swb.service", "Connection refused to upstream at 127.0.0.1:8080"),
            ("aidb.service", "update_slots: all slots are idle, poll tick 128"),
            ("ai-oncalld.service", "Failed to start service ai-oncalld: exit code 1"),
            ("nginx.service", "request timeout after 30000ms from client 192.168.1.100"),
            ("auth.service", "invalid configuration in sops secrets: syntax error line 14"),
        ]

        latencies_ms: List[float] = []
        for i in range(sample_count):
            source, msg = sample_messages[i % len(sample_messages)]
            t0 = time.perf_counter()
            FastClassifier.classify(source=source, message=msg, cursor=f"cursor-{i}", timestamp="2026-10-13T07:00:00Z")
            latencies_ms.append((time.perf_counter() - t0) * 1000.0)

        latencies_ms.sort()
        n = len(latencies_ms)
        p50 = latencies_ms[int(0.50 * n)]
        p90 = latencies_ms[int(0.90 * n)]
        p95 = latencies_ms[int(0.95 * n)]
        p99 = latencies_ms[int(0.99 * n)]

        passed = p95 < 200.0
        return {
            "samples": sample_count,
            "p50_ms": round(p50, 4),
            "p90_ms": round(p90, 4),
            "p95_ms": round(p95, 4),
            "p99_ms": round(p99, 4),
            "target_p95_ms": 200.0,
            "passed": passed,
        }

    def health_summary(self) -> Dict[str, Any]:
        """Bounded, read-only health summary for QA phase 0 and dashboard visibility."""
        try:
            last_cursor, last_ts = self.get_cursor("journald")
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT total_ingested, total_actionable, p95_latency_ms FROM telemetry_metrics WHERE id = 1")
                row = cursor.fetchone()
                total_ingested = int(row[0]) if row else 0
                total_actionable = int(row[1]) if row else 0
                p95_ms = float(row[2]) if row else 0.0

            return {
                "available": True,
                "status": "ready",
                "p95_ms": round(p95_ms, 3),
                "cursor_tracked": bool(last_cursor or last_ts),
                "total_classified": total_ingested,
                "actionable_count": total_actionable,
                "last_cursor": last_cursor[:24] if last_cursor else None,
                "last_timestamp": last_ts if last_ts else None,
            }
        except (OSError, sqlite3.Error) as exc:
            return {
                "available": False,
                "status": "unverified",
                "reason": f"triage_state_unavailable:{type(exc).__name__}",
                "cursor_tracked": False,
            }


def health_summary(repo_root: Optional[Path] = None) -> Dict[str, Any]:
    """Top-level entrypoint for QA checks and dashboard route."""
    state_dir = (repo_root or _DEFAULT_REPO_ROOT) / ".agent" / "triage"
    engine = JournalStreamTriage(state_dir=state_dir)
    return engine.health_summary()
