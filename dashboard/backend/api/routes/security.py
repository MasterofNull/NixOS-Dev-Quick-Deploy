"""
Security & Compliance API Routes
Provides security scanning, audit logging, and compliance checking endpoints
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
import logging
import json
import subprocess
import os
from pathlib import Path
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

router = APIRouter()

# Configuration
REPO_ROOT = os.getenv('REPO_ROOT', os.getcwd())
SECURITY_LIB_DIR = Path(REPO_ROOT) / "lib" / "security"
AUDIT_LOGGER_SCRIPT = SECURITY_LIB_DIR / "audit-logger.py"
SECURITY_SCAN_DIR = Path(REPO_ROOT) / ".agent" / "security" / "scans"
SECURITY_REPORTS_DIR = Path(REPO_ROOT) / ".agent" / "security" / "reports"
COMPLIANCE_REPORTS_DIR = Path(REPO_ROOT) / ".agent" / "security" / "compliance" / "reports"
AUDIT_LOCAL_DIR = Path(REPO_ROOT) / ".agent" / "security" / "audit" / "local"


def run_security_scanner(command: List[str]) -> dict:
    """Run security scanner bash script"""
    try:
        env = os.environ.copy()
        env['REPO_ROOT'] = REPO_ROOT

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=120,
            env=env,
            cwd=REPO_ROOT
        )

        if result.returncode != 0:
            logger.error(f"Scanner command failed: {result.stderr}")
            return {"error": result.stderr}

        # Try to parse JSON output
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return {"output": result.stdout}

    except subprocess.TimeoutExpired:
        logger.error("Scanner command timed out")
        return {"error": "Scanner timed out"}
    except Exception as e:
        logger.error(f"Scanner execution failed: {e}")
        return {"error": str(e)}


def run_audit_logger(action: str, **kwargs) -> dict:
    """Run audit logger Python script"""
    try:
        cmd = ["python3", str(AUDIT_LOGGER_SCRIPT), "--action", action]

        for key, value in kwargs.items():
            if value is not None:
                cmd.extend([f"--{key.replace('_', '-')}", str(value)])

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10,
            cwd=REPO_ROOT
        )

        if result.returncode != 0:
            logger.error(f"Audit logger failed: {result.stderr}")
            return {"error": result.stderr}

        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return {"output": result.stdout}

    except Exception as e:
        logger.error(f"Audit logger execution failed: {e}")
        return {"error": str(e)}


# ============================================================================
# Security Scan Endpoints
# ============================================================================

@router.get("/scan/{deployment_id}")
async def get_security_scan(deployment_id: str):
    """Get security scan results for a deployment"""
    try:
        # Find latest scan for deployment
        scan_files = list(SECURITY_REPORTS_DIR.glob(f"*_report.json"))

        if not scan_files:
            raise HTTPException(status_code=404, detail="No security scans found")

        # Get most recent scan
        latest_scan = max(scan_files, key=lambda p: p.stat().st_mtime)

        with open(latest_scan, 'r') as f:
            scan_data = json.load(f)

        return {
            "deployment_id": deployment_id,
            "scan_id": scan_data.get("scan_id"),
            "timestamp": scan_data.get("timestamp"),
            "duration_seconds": scan_data.get("duration_seconds"),
            "scans": scan_data.get("scans", {}),
            "security_score": scan_data.get("security_score", {}),
            "recommendations": scan_data.get("recommendations", [])
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get security scan: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scan/trigger")
async def trigger_security_scan(deployment_id: str):
    """Trigger an ad-hoc security scan"""
    try:
        # Run security scanner via bash
        scanner_script = SECURITY_LIB_DIR / "scanner.sh"

        result = subprocess.run(
            ["bash", "-c", f"source {scanner_script} && scan_deployment {deployment_id}"],
            capture_output=True,
            text=True,
            timeout=120,
            env={**os.environ, "REPO_ROOT": REPO_ROOT},
            cwd=REPO_ROOT
        )

        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=f"Scan failed: {result.stderr}")

        # Parse scan result
        try:
            scan_result = json.loads(result.stdout)
        except json.JSONDecodeError:
            scan_result = {"output": result.stdout}

        return {
            "status": "completed",
            "deployment_id": deployment_id,
            "scan_result": scan_result
        }

    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Scan timed out")
    except Exception as e:
        logger.error(f"Failed to trigger scan: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/vulnerabilities")
async def get_vulnerabilities(
    severity: Optional[str] = Query(None, description="Filter by severity"),
    limit: int = Query(100, ge=1, le=1000)
):
    """List vulnerabilities by severity"""
    try:
        # Get latest scan results
        scan_files = list(SECURITY_REPORTS_DIR.glob("*_report.json"))

        if not scan_files:
            return {"vulnerabilities": [], "total": 0}

        latest_scan = max(scan_files, key=lambda p: p.stat().st_mtime)

        with open(latest_scan, 'r') as f:
            scan_data = json.load(f)

        # Extract vulnerabilities
        vulns = []
        vuln_scans = scan_data.get("scans", {}).get("vulnerabilities", [])

        for service_scan in vuln_scans:
            service = service_scan.get("service")
            scan_data_inner = service_scan.get("scan", {})

            for vuln_type in ["known", "dependencies", "container"]:
                for vuln in scan_data_inner.get("vulnerabilities", {}).get(vuln_type, []):
                    if severity is None or vuln.get("severity") == severity:
                        vulns.append({
                            "service": service,
                            "type": vuln_type,
                            **vuln
                        })

        # Apply limit
        vulns = vulns[:limit]

        return {
            "vulnerabilities": vulns,
            "total": len(vulns),
            "severity_filter": severity
        }

    except Exception as e:
        logger.error(f"Failed to get vulnerabilities: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recommendations")
async def get_security_recommendations():
    """Get security improvement recommendations"""
    try:
        # Get latest scan with recommendations
        scan_files = list(SECURITY_REPORTS_DIR.glob("*_report.json"))

        if not scan_files:
            return {"recommendations": []}

        latest_scan = max(scan_files, key=lambda p: p.stat().st_mtime)

        with open(latest_scan, 'r') as f:
            scan_data = json.load(f)

        recommendations = scan_data.get("recommendations", [])

        return {
            "recommendations": recommendations,
            "total": len(recommendations),
            "scan_timestamp": scan_data.get("timestamp")
        }

    except Exception as e:
        logger.error(f"Failed to get recommendations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Audit Event Endpoints
# ============================================================================

@router.get("/audit/events")
async def get_audit_events(
    event_type: Optional[str] = Query(None),
    actor: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """Query audit events with filtering"""
    try:
        # Use audit logger query
        result = run_audit_logger(
            "query",
            event_type=event_type,
            actor=actor,
            severity=severity,
            limit=limit,
            offset=offset
        )

        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])

        # Result is already a list of events
        events = result if isinstance(result, list) else []

        return {
            "events": events,
            "total": len(events),
            "filters": {
                "event_type": event_type,
                "actor": actor,
                "severity": severity
            },
            "pagination": {
                "limit": limit,
                "offset": offset
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to query audit events: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/audit/statistics")
async def get_audit_statistics():
    """Get audit log statistics"""
    try:
        result = run_audit_logger("stats")

        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get audit statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Compliance Endpoints
# ============================================================================

@router.get("/compliance/status")
async def get_compliance_status(deployment_id: Optional[str] = None):
    """Get compliance status summary"""
    try:
        # Get latest compliance reports
        report_files = list(COMPLIANCE_REPORTS_DIR.glob("*_report.json"))

        if not report_files:
            return {
                "frameworks": [],
                "overall_status": "unknown"
            }

        frameworks = []

        # Load recent reports for each framework
        for report_file in sorted(report_files, key=lambda p: p.stat().st_mtime, reverse=True)[:10]:
            try:
                with open(report_file, 'r') as f:
                    report_data = json.load(f)

                framework = report_data.get("framework")
                summary = report_data.get("summary", {})

                frameworks.append({
                    "framework": framework,
                    "compliance_percentage": summary.get("compliance_percentage", 0),
                    "total_controls": summary.get("total_controls", 0),
                    "passed_controls": summary.get("passed_controls", 0),
                    "failed_controls": summary.get("failed_controls", 0),
                    "timestamp": report_data.get("timestamp")
                })
            except Exception as e:
                logger.warning(f"Failed to load compliance report {report_file}: {e}")
                continue

        # Calculate overall status
        if frameworks:
            avg_compliance = sum(f["compliance_percentage"] for f in frameworks) / len(frameworks)
            if avg_compliance >= 90:
                overall_status = "compliant"
            elif avg_compliance >= 70:
                overall_status = "partial"
            else:
                overall_status = "non_compliant"
        else:
            overall_status = "unknown"

        return {
            "frameworks": frameworks,
            "overall_status": overall_status,
            "deployment_id": deployment_id
        }

    except Exception as e:
        logger.error(f"Failed to get compliance status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/compliance/report/{framework}")
async def get_compliance_report(
    framework: str,
    deployment_id: Optional[str] = None
):
    """Generate compliance report for a specific framework"""
    try:
        # Find latest report for framework
        pattern = f"*_{framework.lower()}*_report.json"
        report_files = list(COMPLIANCE_REPORTS_DIR.glob(pattern))

        if not report_files:
            raise HTTPException(
                status_code=404,
                detail=f"No compliance reports found for framework: {framework}"
            )

        # Get most recent report
        latest_report = max(report_files, key=lambda p: p.stat().st_mtime)

        with open(latest_report, 'r') as f:
            report_data = json.load(f)

        return report_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get compliance report: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compliance/check")
async def trigger_compliance_check(
    deployment_id: str,
    framework: str = "SOC2"
):
    """Trigger compliance check for a framework"""
    try:
        # Run compliance checker
        compliance_script = SECURITY_LIB_DIR.parent / "security" / "compliance-checker.sh"

        result = subprocess.run(
            ["bash", "-c", f"source {compliance_script} && check_compliance {deployment_id} {framework}"],
            capture_output=True,
            text=True,
            timeout=60,
            env={**os.environ, "REPO_ROOT": REPO_ROOT},
            cwd=REPO_ROOT
        )

        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=f"Compliance check failed: {result.stderr}")

        # Parse result
        try:
            check_result = json.loads(result.stdout)
        except json.JSONDecodeError:
            check_result = {"output": result.stdout}

        return {
            "status": "completed",
            "deployment_id": deployment_id,
            "framework": framework,
            "result": check_result
        }

    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Compliance check timed out")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to trigger compliance check: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Security Dashboard Summary
# ============================================================================

@router.get("/summary")
async def get_security_summary(deployment_id: Optional[str] = None):
    """Get security dashboard summary"""
    try:
        summary = {
            "timestamp": datetime.now().isoformat(),
            "deployment_id": deployment_id
        }

        # Get latest security scan
        scan_files = list(SECURITY_REPORTS_DIR.glob("*_report.json"))
        if scan_files:
            latest_scan = max(scan_files, key=lambda p: p.stat().st_mtime)
            with open(latest_scan, 'r') as f:
                scan_data = json.load(f)

            summary["security_score"] = scan_data.get("security_score", {})

            # Count vulnerabilities by severity
            vuln_scans = scan_data.get("scans", {}).get("vulnerabilities", [])
            summary["vulnerability_counts"] = {
                "critical": 0,
                "high": 0,
                "medium": 0,
                "low": 0
            }

            for service_scan in vuln_scans:
                severity_counts = service_scan.get("scan", {}).get("severity_counts", {})
                for severity in ["critical", "high", "medium", "low"]:
                    summary["vulnerability_counts"][severity] += severity_counts.get(severity, 0)
        else:
            summary["security_score"] = {"overall": 0, "max": 100}
            summary["vulnerability_counts"] = {"critical": 0, "high": 0, "medium": 0, "low": 0}

        # Get compliance status
        compliance_status = await get_compliance_status(deployment_id)
        summary["compliance"] = compliance_status

        # Get recent audit events
        audit_stats = run_audit_logger("stats")
        summary["audit"] = {
            "total_events": audit_stats.get("total_events", 0),
            "recent_events": audit_stats.get("type_counts", {})
        }

        return summary

    except Exception as e:
        logger.error(f"Failed to get security summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))
