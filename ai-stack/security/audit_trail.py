#!/usr/bin/env python3
"""
Audit Trail & Compliance Framework

Tamper-proof audit logging with compliance reporting and forensic analysis.
Part of Phase 2 Batch 2.3: Audit Trail & Compliance

Key Features:
- Comprehensive audit logging for all actions
- Tamper-proof append-only audit trail with cryptographic verification
- Compliance reporting (SOC 2, GDPR-ready)
- User action tracking
- Forensic analysis and query tools

Reference: SOC 2 Trust Service Criteria, GDPR Article 30, NIST SP 800-92
"""

import asyncio
import hashlib
import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class ActionType(Enum):
    """Types of auditable actions"""
    # Authentication
    LOGIN = "login"
    LOGOUT = "logout"
    AUTH_FAILURE = "auth_failure"

    # Data access
    DATA_READ = "data_read"
    DATA_WRITE = "data_write"
    DATA_DELETE = "data_delete"
    DATA_EXPORT = "data_export"

    # Configuration
    CONFIG_CHANGE = "config_change"
    POLICY_UPDATE = "policy_update"

    # System
    SERVICE_START = "service_start"
    SERVICE_STOP = "service_stop"
    DEPLOYMENT = "deployment"

    # Security
    PERMISSION_GRANT = "permission_grant"
    PERMISSION_REVOKE = "permission_revoke"
    SECURITY_ALERT = "security_alert"


class Severity(Enum):
    """Audit event severity"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class AuditEvent:
    """Single audit event"""
    event_id: str
    timestamp: datetime
    action_type: ActionType
    severity: Severity
    actor: str  # User, service, or system
    resource: str  # What was accessed/modified
    details: Dict[str, Any] = field(default_factory=dict)
    result: str = "success"  # success, failure, partial
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

    # Tamper protection
    previous_hash: Optional[str] = None
    event_hash: Optional[str] = None

    def calculate_hash(self) -> str:
        """Calculate cryptographic hash of event"""
        # Create canonical representation
        canonical = json.dumps({
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "action_type": self.action_type.value,
            "actor": self.actor,
            "resource": self.resource,
            "details": self.details,
            "result": self.result,
            "previous_hash": self.previous_hash,
        }, sort_keys=True)

        return hashlib.sha256(canonical.encode()).hexdigest()


@dataclass
class ComplianceReport:
    """Compliance audit report"""
    report_id: str
    report_type: str  # SOC2, GDPR, etc.
    period_start: datetime
    period_end: datetime
    total_events: int
    events_by_type: Dict[str, int]
    security_incidents: int
    access_violations: int
    data_exports: int
    recommendations: List[str] = field(default_factory=list)
    generated_at: datetime = field(default_factory=datetime.now)


class AuditLogger:
    """Tamper-proof audit logging system"""

    def __init__(self, audit_dir: Path):
        self.audit_dir = audit_dir
        self.audit_dir.mkdir(parents=True, exist_ok=True)

        self.events: List[AuditEvent] = []
        self.last_hash: Optional[str] = None

        self._load_existing_events()
        logger.info(f"Audit Logger initialized: {audit_dir}")

    def _load_existing_events(self):
        """Load existing audit events"""
        # Load from daily log files
        for log_file in sorted(self.audit_dir.glob("audit_*.jsonl")):
            with open(log_file) as f:
                for line in f:
                    try:
                        data = json.loads(line)
                        event = AuditEvent(
                            event_id=data["event_id"],
                            timestamp=datetime.fromisoformat(data["timestamp"]),
                            action_type=ActionType(data["action_type"]),
                            severity=Severity(data["severity"]),
                            actor=data["actor"],
                            resource=data["resource"],
                            details=data.get("details", {}),
                            result=data.get("result", "success"),
                            ip_address=data.get("ip_address"),
                            user_agent=data.get("user_agent"),
                            previous_hash=data.get("previous_hash"),
                            event_hash=data.get("event_hash"),
                        )
                        self.events.append(event)
                        self.last_hash = event.event_hash
                    except Exception as e:
                        logger.error(f"Failed to load audit event: {e}")

        if self.events:
            logger.info(f"Loaded {len(self.events)} existing audit events")

    def log_event(
        self,
        action_type: ActionType,
        actor: str,
        resource: str,
        severity: Severity = Severity.INFO,
        details: Dict = None,
        result: str = "success",
        ip_address: str = None,
        user_agent: str = None,
    ) -> AuditEvent:
        """Log an audit event"""
        event = AuditEvent(
            event_id=f"evt_{len(self.events)}",
            timestamp=datetime.now(),
            action_type=action_type,
            severity=severity,
            actor=actor,
            resource=resource,
            details=details or {},
            result=result,
            ip_address=ip_address,
            user_agent=user_agent,
            previous_hash=self.last_hash,
        )

        # Calculate hash for tamper protection
        event.event_hash = event.calculate_hash()
        self.last_hash = event.event_hash

        # Append to events
        self.events.append(event)

        # Write to daily log file (append-only)
        log_file = self.audit_dir / f"audit_{datetime.now().strftime('%Y%m%d')}.jsonl"
        with open(log_file, "a") as f:
            f.write(json.dumps({
                "event_id": event.event_id,
                "timestamp": event.timestamp.isoformat(),
                "action_type": event.action_type.value,
                "severity": event.severity.value,
                "actor": event.actor,
                "resource": event.resource,
                "details": event.details,
                "result": event.result,
                "ip_address": event.ip_address,
                "user_agent": event.user_agent,
                "previous_hash": event.previous_hash,
                "event_hash": event.event_hash,
            }) + "\n")

        logger.debug(
            f"Audit event logged: {action_type.value} by {actor} on {resource} "
            f"(severity={severity.value})"
        )

        return event

    def verify_chain_integrity(self) -> tuple[bool, List[str]]:
        """Verify audit trail integrity"""
        logger.info("Verifying audit trail integrity...")

        issues = []
        prev_hash = None

        for i, event in enumerate(self.events):
            # Check previous hash link
            if event.previous_hash != prev_hash:
                issues.append(
                    f"Event {event.event_id}: Previous hash mismatch "
                    f"(expected {prev_hash}, got {event.previous_hash})"
                )

            # Recalculate and verify event hash
            expected_hash = event.calculate_hash()
            if event.event_hash != expected_hash:
                issues.append(
                    f"Event {event.event_id}: Hash mismatch "
                    f"(expected {expected_hash}, got {event.event_hash})"
                )

            prev_hash = event.event_hash

        is_valid = len(issues) == 0
        if is_valid:
            logger.info("Audit trail integrity verified: OK")
        else:
            logger.error(f"Audit trail integrity check failed: {len(issues)} issues")

        return is_valid, issues


class UserActionTracker:
    """Track user actions for compliance"""

    def __init__(self, audit_logger: AuditLogger):
        self.audit_logger = audit_logger
        self.active_sessions: Dict[str, Dict] = {}  # user_id -> session info

        logger.info("User Action Tracker initialized")

    def track_login(
        self,
        user_id: str,
        ip_address: str,
        user_agent: str,
        success: bool = True,
    ):
        """Track user login"""
        if success:
            session_id = hashlib.sha256(f"{user_id}{datetime.now()}".encode()).hexdigest()[:16]

            self.active_sessions[user_id] = {
                "session_id": session_id,
                "login_time": datetime.now(),
                "ip_address": ip_address,
                "user_agent": user_agent,
            }

            self.audit_logger.log_event(
                ActionType.LOGIN,
                actor=user_id,
                resource="system",
                severity=Severity.INFO,
                details={"session_id": session_id},
                ip_address=ip_address,
                user_agent=user_agent,
            )
        else:
            self.audit_logger.log_event(
                ActionType.AUTH_FAILURE,
                actor=user_id,
                resource="system",
                severity=Severity.MEDIUM,
                result="failure",
                ip_address=ip_address,
                user_agent=user_agent,
            )

    def track_logout(self, user_id: str):
        """Track user logout"""
        session = self.active_sessions.pop(user_id, None)

        if session:
            duration = (datetime.now() - session["login_time"]).total_seconds()

            self.audit_logger.log_event(
                ActionType.LOGOUT,
                actor=user_id,
                resource="system",
                severity=Severity.INFO,
                details={
                    "session_id": session["session_id"],
                    "session_duration_seconds": duration,
                },
            )

    def track_data_access(
        self,
        user_id: str,
        operation: str,  # read, write, delete, export
        resource: str,
        data_type: str = None,
        record_count: int = None,
    ):
        """Track data access"""
        action_map = {
            "read": ActionType.DATA_READ,
            "write": ActionType.DATA_WRITE,
            "delete": ActionType.DATA_DELETE,
            "export": ActionType.DATA_EXPORT,
        }

        action_type = action_map.get(operation, ActionType.DATA_READ)
        severity = Severity.HIGH if operation == "delete" else Severity.INFO

        details = {}
        if data_type:
            details["data_type"] = data_type
        if record_count:
            details["record_count"] = record_count

        self.audit_logger.log_event(
            action_type,
            actor=user_id,
            resource=resource,
            severity=severity,
            details=details,
        )


class ComplianceReporter:
    """Generate compliance reports"""

    def __init__(self, audit_logger: AuditLogger):
        self.audit_logger = audit_logger
        logger.info("Compliance Reporter initialized")

    def generate_soc2_report(
        self,
        period_start: datetime,
        period_end: datetime,
    ) -> ComplianceReport:
        """Generate SOC 2 compliance report"""
        logger.info(f"Generating SOC 2 report: {period_start} to {period_end}")

        # Filter events in period
        events = [
            e for e in self.audit_logger.events
            if period_start <= e.timestamp <= period_end
        ]

        # Count events by type
        events_by_type = defaultdict(int)
        for event in events:
            events_by_type[event.action_type.value] += 1

        # Count security incidents
        security_incidents = sum(
            1 for e in events
            if e.severity in [Severity.CRITICAL, Severity.HIGH]
            and e.action_type in [ActionType.SECURITY_ALERT, ActionType.AUTH_FAILURE]
        )

        # Count access violations
        access_violations = sum(
            1 for e in events
            if e.result == "failure"
            and "access" in e.action_type.value.lower()
        )

        # Count data exports
        data_exports = sum(
            1 for e in events
            if e.action_type == ActionType.DATA_EXPORT
        )

        # Generate recommendations
        recommendations = []

        if security_incidents > 0:
            recommendations.append(
                f"Review {security_incidents} security incidents for root cause analysis"
            )

        if access_violations > 10:
            recommendations.append(
                f"High number of access violations ({access_violations}). "
                "Review access control policies."
            )

        if data_exports > 100:
            recommendations.append(
                f"Large number of data exports ({data_exports}). "
                "Ensure data handling policies are followed."
            )

        # Check audit trail integrity
        is_valid, issues = self.audit_logger.verify_chain_integrity()
        if not is_valid:
            recommendations.append(
                f"Audit trail integrity issues detected: {len(issues)} problems. "
                "Investigate potential tampering."
            )

        report = ComplianceReport(
            report_id=f"soc2_{period_end.strftime('%Y%m%d')}",
            report_type="SOC2",
            period_start=period_start,
            period_end=period_end,
            total_events=len(events),
            events_by_type=dict(events_by_type),
            security_incidents=security_incidents,
            access_violations=access_violations,
            data_exports=data_exports,
            recommendations=recommendations,
        )

        logger.info(f"SOC 2 report generated: {report.report_id}")
        return report

    def generate_gdpr_report(
        self,
        period_start: datetime,
        period_end: datetime,
        data_subject: Optional[str] = None,
    ) -> ComplianceReport:
        """Generate GDPR compliance report"""
        logger.info(f"Generating GDPR report: {period_start} to {period_end}")

        # Filter events
        events = [
            e for e in self.audit_logger.events
            if period_start <= e.timestamp <= period_end
        ]

        # Filter by data subject if specified
        if data_subject:
            events = [
                e for e in events
                if data_subject in str(e.details)
            ]

        # Count relevant events
        events_by_type = defaultdict(int)
        for event in events:
            events_by_type[event.action_type.value] += 1

        # GDPR-specific checks
        data_exports = sum(
            1 for e in events
            if e.action_type == ActionType.DATA_EXPORT
        )

        data_deletions = sum(
            1 for e in events
            if e.action_type == ActionType.DATA_DELETE
        )

        recommendations = []

        # GDPR requires logging of data processing activities
        if not events:
            recommendations.append(
                "No data processing activities logged in this period. "
                "Ensure all processing is being audited."
            )

        # Data exports should have justification
        if data_exports > 0:
            exports_with_justification = sum(
                1 for e in events
                if e.action_type == ActionType.DATA_EXPORT
                and "justification" in e.details
            )

            if exports_with_justification < data_exports:
                recommendations.append(
                    f"{data_exports - exports_with_justification} data exports "
                    "missing justification. GDPR requires documenting the purpose."
                )

        report = ComplianceReport(
            report_id=f"gdpr_{period_end.strftime('%Y%m%d')}",
            report_type="GDPR",
            period_start=period_start,
            period_end=period_end,
            total_events=len(events),
            events_by_type=dict(events_by_type),
            security_incidents=0,  # Not GDPR-specific
            access_violations=0,  # Not GDPR-specific
            data_exports=data_exports,
            recommendations=recommendations,
        )

        logger.info(f"GDPR report generated: {report.report_id}")
        return report

    def export_report(self, report: ComplianceReport, output_path: Path):
        """Export compliance report"""
        report_data = {
            "report_id": report.report_id,
            "report_type": report.report_type,
            "period_start": report.period_start.isoformat(),
            "period_end": report.period_end.isoformat(),
            "generated_at": report.generated_at.isoformat(),
            "summary": {
                "total_events": report.total_events,
                "security_incidents": report.security_incidents,
                "access_violations": report.access_violations,
                "data_exports": report.data_exports,
            },
            "events_by_type": report.events_by_type,
            "recommendations": report.recommendations,
        }

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(report_data, f, indent=2)

        logger.info(f"Report exported: {output_path}")


class ForensicAnalyzer:
    """Forensic analysis of audit logs"""

    def __init__(self, audit_logger: AuditLogger):
        self.audit_logger = audit_logger
        logger.info("Forensic Analyzer initialized")

    def search_events(
        self,
        actor: Optional[str] = None,
        action_type: Optional[ActionType] = None,
        resource_pattern: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        severity: Optional[Severity] = None,
    ) -> List[AuditEvent]:
        """Search audit events"""
        results = self.audit_logger.events

        if actor:
            results = [e for e in results if e.actor == actor]

        if action_type:
            results = [e for e in results if e.action_type == action_type]

        if resource_pattern:
            import fnmatch
            results = [e for e in results if fnmatch.fnmatch(e.resource, resource_pattern)]

        if start_time:
            results = [e for e in results if e.timestamp >= start_time]

        if end_time:
            results = [e for e in results if e.timestamp <= end_time]

        if severity:
            results = [e for e in results if e.severity == severity]

        logger.info(f"Search found {len(results)} matching events")
        return results

    def analyze_user_activity(self, user_id: str, days: int = 7) -> Dict:
        """Analyze user activity patterns"""
        since = datetime.now() - timedelta(days=days)

        events = self.search_events(actor=user_id, start_time=since)

        # Analyze patterns
        actions_by_hour = defaultdict(int)
        actions_by_type = defaultdict(int)
        resources_accessed = set()

        for event in events:
            hour = event.timestamp.hour
            actions_by_hour[hour] += 1
            actions_by_type[event.action_type.value] += 1
            resources_accessed.add(event.resource)

        return {
            "user_id": user_id,
            "period_days": days,
            "total_actions": len(events),
            "unique_resources": len(resources_accessed),
            "actions_by_hour": dict(actions_by_hour),
            "actions_by_type": dict(actions_by_type),
            "most_active_hour": max(actions_by_hour.items(), key=lambda x: x[1])[0] if actions_by_hour else None,
        }

    def detect_anomalies(self, user_id: str) -> List[str]:
        """Detect anomalous behavior"""
        anomalies = []

        # Get recent activity
        activity = self.analyze_user_activity(user_id, days=7)

        # Check for unusual patterns
        if activity["total_actions"] > 1000:
            anomalies.append(
                f"Unusually high activity: {activity['total_actions']} actions in 7 days"
            )

        # Check for after-hours activity (example: 2 AM - 5 AM)
        after_hours = sum(
            activity["actions_by_hour"].get(h, 0)
            for h in range(2, 6)
        )

        if after_hours > 50:
            anomalies.append(
                f"Significant after-hours activity: {after_hours} actions between 2 AM - 5 AM"
            )

        # Check for unusual action types
        if activity["actions_by_type"].get("data_export", 0) > 10:
            anomalies.append(
                f"High number of data exports: {activity['actions_by_type']['data_export']}"
            )

        return anomalies


async def main():
    """Test audit trail framework"""
    logging.basicConfig(level=logging.INFO)

    logger.info("Audit Trail & Compliance Framework Test")
    logger.info("=" * 60)

    # Initialize components
    audit_dir = Path(".agents/security/audit")
    audit_logger = AuditLogger(audit_dir)

    tracker = UserActionTracker(audit_logger)
    reporter = ComplianceReporter(audit_logger)
    forensics = ForensicAnalyzer(audit_logger)

    # Simulate user activity
    logger.info("\n1. Simulating user activity...")

    tracker.track_login("user_alice", "192.168.1.100", "Mozilla/5.0")
    tracker.track_data_access("user_alice", "read", "/api/hints", data_type="hints", record_count=50)
    tracker.track_data_access("user_alice", "write", "/api/tasks", data_type="tasks", record_count=5)
    tracker.track_logout("user_alice")

    tracker.track_login("user_bob", "192.168.1.101", "Chrome/90.0", success=False)
    tracker.track_login("user_bob", "192.168.1.101", "Chrome/90.0", success=True)

    # Log security event
    audit_logger.log_event(
        ActionType.SECURITY_ALERT,
        actor="system",
        resource="firewall",
        severity=Severity.HIGH,
        details={"alert_type": "port_scan", "source_ip": "10.0.0.50"},
    )

    logger.info(f"  Total events logged: {len(audit_logger.events)}")

    # Verify integrity
    logger.info("\n2. Verifying audit trail integrity...")
    is_valid, issues = audit_logger.verify_chain_integrity()
    logger.info(f"  Integrity check: {'PASS' if is_valid else 'FAIL'}")
    if issues:
        for issue in issues:
            logger.info(f"    - {issue}")

    # Generate compliance reports
    logger.info("\n3. Generating compliance reports...")

    period_start = datetime.now() - timedelta(days=30)
    period_end = datetime.now()

    soc2_report = reporter.generate_soc2_report(period_start, period_end)
    logger.info(f"  SOC 2 Report:")
    logger.info(f"    Total events: {soc2_report.total_events}")
    logger.info(f"    Security incidents: {soc2_report.security_incidents}")
    logger.info(f"    Recommendations: {len(soc2_report.recommendations)}")

    gdpr_report = reporter.generate_gdpr_report(period_start, period_end)
    logger.info(f"  GDPR Report:")
    logger.info(f"    Total events: {gdpr_report.total_events}")
    logger.info(f"    Data exports: {gdpr_report.data_exports}")

    # Export reports
    reporter.export_report(soc2_report, Path(".agents/security/reports/soc2_latest.json"))
    reporter.export_report(gdpr_report, Path(".agents/security/reports/gdpr_latest.json"))

    # Forensic analysis
    logger.info("\n4. Forensic Analysis:")

    activity = forensics.analyze_user_activity("user_alice")
    logger.info(f"  User activity (user_alice):")
    logger.info(f"    Total actions: {activity['total_actions']}")
    logger.info(f"    Unique resources: {activity['unique_resources']}")
    logger.info(f"    Actions by type: {activity['actions_by_type']}")

    anomalies = forensics.detect_anomalies("user_alice")
    if anomalies:
        logger.info(f"  Anomalies detected:")
        for anomaly in anomalies:
            logger.info(f"    - {anomaly}")
    else:
        logger.info(f"  No anomalies detected")

    logger.info(f"\nAudit logs stored in: {audit_dir}")


if __name__ == "__main__":
    asyncio.run(main())
