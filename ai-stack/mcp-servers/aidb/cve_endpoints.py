"""
Kernel CVE API Endpoints
FastAPI routes for CVE tracking, kernel releases, and host vulnerability scanning.

Endpoints:
- GET  /kernel/cves                     - List tracked CVEs
- GET  /kernel/cves/{cve_id}            - CVE details
- POST /kernel/cves/sync                - Trigger NVD sync
- GET  /kernel/releases                 - Current kernel releases
- POST /kernel/releases/sync            - Sync from kernel.org
- GET  /kernel/hosts/{host}/vulnerabilities - Host vulnerability scan
- POST /kernel/scan                     - Scan host for CVEs
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import sqlalchemy as sa
from fastapi import BackgroundTasks, HTTPException, Query
from pydantic import BaseModel

try:
    from .schema import (
        KERNEL_CVES,
        KERNEL_CVE_HOSTS,
        KERNEL_RELEASES,
        KERNEL_SUBSYSTEM_CVES,
    )
except ImportError:
    from schema import (
        KERNEL_CVES,
        KERNEL_CVE_HOSTS,
        KERNEL_RELEASES,
        KERNEL_SUBSYSTEM_CVES,
    )

LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------------------------

class CVEListItem(BaseModel):
    """CVE summary for list views."""
    cve_id: str
    severity: str
    cvss_v3_score: Optional[float]
    description: str
    subsystems: List[str]
    local_status: str
    published_date: datetime


class CVEDetail(BaseModel):
    """Full CVE details."""
    cve_id: str
    description: str
    severity: str
    cvss_v3_score: Optional[float]
    cvss_v3_vector: Optional[str]
    affected_versions: List[Dict[str, str]]
    fixed_in_version: Optional[str]
    subsystems: List[str]
    cwe_ids: List[str]
    references: List[Dict[str, str]]
    exploit_available: bool
    cisa_kev: bool
    local_status: str
    local_patch_id: Optional[int]
    published_date: datetime
    last_modified: datetime


class KernelReleaseInfo(BaseModel):
    """Kernel release information."""
    version: str
    track: str
    release_date: datetime
    eol_date: Optional[datetime]
    tarball_url: str
    rust_version_required: Optional[str]


class HostVulnerability(BaseModel):
    """Vulnerability affecting a host."""
    cve_id: str
    severity: str
    cvss_v3_score: Optional[float]
    status: str
    description: str


class HostScanRequest(BaseModel):
    """Request to scan a host for vulnerabilities."""
    hostname: str
    kernel_version: str
    architecture: Optional[str] = "x86_64"


class HostScanResult(BaseModel):
    """Result of host vulnerability scan."""
    hostname: str
    kernel_version: str
    total_cves: int
    critical: int
    high: int
    medium: int
    low: int
    vulnerabilities: List[HostVulnerability]


class SyncStatus(BaseModel):
    """Status of CVE/release sync operation."""
    status: str
    message: str
    task_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Endpoint Registration
# ---------------------------------------------------------------------------

def register_cve_routes(app, mcp_server):
    """Register kernel CVE API routes on FastAPI app."""
    db_engine = mcp_server._engine

    @app.get("/kernel/cves", response_model=Dict[str, Any])
    async def list_kernel_cves(
        severity: Optional[str] = Query(None, description="Filter by severity"),
        subsystem: Optional[str] = Query(None, description="Filter by subsystem"),
        status: Optional[str] = Query(None, description="Filter by local status"),
        exploit_available: Optional[bool] = Query(None, description="Filter by exploit availability"),
        limit: int = Query(100, le=1000),
        offset: int = Query(0, ge=0),
    ):
        """List tracked kernel CVEs with filters."""
        query = sa.select(KERNEL_CVES).order_by(KERNEL_CVES.c.published_date.desc())

        if severity:
            query = query.where(KERNEL_CVES.c.severity == severity.lower())
        if status:
            query = query.where(KERNEL_CVES.c.local_status == status)
        if exploit_available is not None:
            query = query.where(KERNEL_CVES.c.exploit_available == exploit_available)

        query = query.limit(limit).offset(offset)

        with db_engine.connect() as conn:
            # Get total count
            count_query = sa.select(sa.func.count()).select_from(KERNEL_CVES)
            if severity:
                count_query = count_query.where(KERNEL_CVES.c.severity == severity.lower())
            total = conn.execute(count_query).scalar() or 0

            # Get CVEs
            rows = conn.execute(query).fetchall()
            cves = []
            for row in rows:
                row_dict = row._asdict()
                # Filter by subsystem in Python (JSONB contains)
                if subsystem:
                    if subsystem.lower() not in [s.lower() for s in row_dict.get("subsystems", [])]:
                        continue
                cves.append(CVEListItem(
                    cve_id=row_dict["cve_id"],
                    severity=row_dict["severity"],
                    cvss_v3_score=row_dict.get("cvss_v3_score"),
                    description=row_dict["description"][:200] + "..." if len(row_dict["description"]) > 200 else row_dict["description"],
                    subsystems=row_dict.get("subsystems", []),
                    local_status=row_dict["local_status"],
                    published_date=row_dict["published_date"],
                ).dict())

        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "cves": cves,
        }

    @app.get("/kernel/cves/{cve_id}", response_model=CVEDetail)
    async def get_cve_details(cve_id: str):
        """Get detailed CVE information."""
        with db_engine.connect() as conn:
            row = conn.execute(
                sa.select(KERNEL_CVES).where(KERNEL_CVES.c.cve_id == cve_id)
            ).first()

            if not row:
                raise HTTPException(status_code=404, detail=f"CVE {cve_id} not found")

            row_dict = row._asdict()
            return CVEDetail(**row_dict)

    @app.post("/kernel/cves/sync", response_model=SyncStatus)
    async def sync_nvd_cves(
        background_tasks: BackgroundTasks,
        full_sync: bool = Query(False, description="Full sync (all CVEs) vs incremental"),
        severity: Optional[str] = Query(None, description="Only sync this severity"),
    ):
        """Trigger NVD CVE sync (runs in background)."""
        try:
            from .nvd_client import NVDClient
        except ImportError:
            from nvd_client import NVDClient

        async def do_sync():
            client = NVDClient()
            try:
                result = await client.sync_kernel_cves(
                    db_engine,
                    full_sync=full_sync,
                    severity_filter=severity,
                )
                LOGGER.info(
                    "NVD sync complete: %d new, %d updated",
                    result.new_cves,
                    result.updated_cves,
                )
            except Exception as e:
                LOGGER.error("NVD sync failed: %s", e)

        background_tasks.add_task(do_sync)

        return SyncStatus(
            status="started",
            message="NVD CVE sync started in background",
        )

    @app.get("/kernel/releases", response_model=Dict[str, Any])
    async def list_kernel_releases(
        track: Optional[str] = Query(None, description="Filter by track"),
        include_eol: bool = Query(False, description="Include EOL releases"),
    ):
        """List tracked kernel releases."""
        query = sa.select(KERNEL_RELEASES).order_by(KERNEL_RELEASES.c.release_date.desc())

        if track:
            query = query.where(KERNEL_RELEASES.c.track == track)
        if not include_eol:
            query = query.where(KERNEL_RELEASES.c.eol_date.is_(None))

        with db_engine.connect() as conn:
            rows = conn.execute(query).fetchall()
            releases = [
                KernelReleaseInfo(
                    version=row.version,
                    track=row.track,
                    release_date=row.release_date,
                    eol_date=row.eol_date,
                    tarball_url=row.tarball_url,
                    rust_version_required=row.rust_version_required,
                ).dict()
                for row in rows
            ]

        return {
            "count": len(releases),
            "releases": releases,
        }

    @app.post("/kernel/releases/sync", response_model=SyncStatus)
    async def sync_kernel_releases(background_tasks: BackgroundTasks):
        """Sync kernel releases from kernel.org."""
        from .kernelorg_client import KernelOrgClient

        async def do_sync():
            client = KernelOrgClient()
            try:
                synced = await client.sync_releases_to_db(db_engine)
                LOGGER.info("kernel.org sync: %d releases synced", synced)
            except Exception as e:
                LOGGER.error("kernel.org sync failed: %s", e)
            finally:
                await client.close()

        background_tasks.add_task(do_sync)

        return SyncStatus(
            status="started",
            message="kernel.org release sync started in background",
        )

    @app.get("/kernel/hosts/{hostname}/vulnerabilities", response_model=Dict[str, Any])
    async def get_host_vulnerabilities(hostname: str):
        """Get vulnerabilities affecting a specific host."""
        with db_engine.connect() as conn:
            query = (
                sa.select(
                    KERNEL_CVE_HOSTS,
                    KERNEL_CVES.c.description,
                    KERNEL_CVES.c.cvss_v3_score,
                )
                .join(KERNEL_CVES, KERNEL_CVE_HOSTS.c.cve_id == KERNEL_CVES.c.cve_id)
                .where(KERNEL_CVE_HOSTS.c.hostname == hostname)
                .order_by(KERNEL_CVES.c.cvss_v3_score.desc().nullslast())
            )

            rows = conn.execute(query).fetchall()

            vulns = []
            for row in rows:
                vulns.append(HostVulnerability(
                    cve_id=row.cve_id,
                    severity=row.status,  # This should be from CVE table
                    cvss_v3_score=row.cvss_v3_score,
                    status=row.status,
                    description=row.description[:200] if row.description else "",
                ).dict())

        return {
            "hostname": hostname,
            "vulnerability_count": len(vulns),
            "vulnerabilities": vulns,
        }

    @app.post("/kernel/scan", response_model=HostScanResult)
    async def scan_host_vulnerabilities(request: HostScanRequest):
        """
        Scan a host kernel for known vulnerabilities.

        Checks the kernel version against tracked CVEs and records results.
        """
        hostname = request.hostname
        kernel_version = request.kernel_version
        architecture = request.architecture

        # Parse kernel version to extract major.minor
        version_parts = kernel_version.split(".")
        if len(version_parts) < 2:
            raise HTTPException(status_code=400, detail="Invalid kernel version format")

        major_minor = f"{version_parts[0]}.{version_parts[1]}"

        with db_engine.begin() as conn:
            # Find CVEs that affect this kernel version
            # This is a simplified check - real implementation would parse affected_versions properly
            all_cves = conn.execute(sa.select(KERNEL_CVES)).fetchall()

            vulnerabilities = []
            severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}

            for cve in all_cves:
                cve_dict = cve._asdict()
                affected = cve_dict.get("affected_versions", [])

                # Check if version is affected (simplified)
                is_affected = False
                for version_range in affected:
                    criteria = version_range.get("criteria", "")
                    if major_minor in criteria or "linux_kernel" in criteria.lower():
                        # Check version bounds if present
                        from_ver = version_range.get("from", "0.0.0")
                        to_ver = version_range.get("to", "999.999.999")
                        # Simplified comparison
                        is_affected = True
                        break

                if is_affected:
                    severity = cve_dict["severity"]
                    if severity in severity_counts:
                        severity_counts[severity] += 1

                    vulnerabilities.append(HostVulnerability(
                        cve_id=cve_dict["cve_id"],
                        severity=severity,
                        cvss_v3_score=cve_dict.get("cvss_v3_score"),
                        status="vulnerable",
                        description=cve_dict["description"][:200],
                    ))

                    # Record in host CVE table
                    existing = conn.execute(
                        sa.select(KERNEL_CVE_HOSTS.c.id)
                        .where(KERNEL_CVE_HOSTS.c.cve_id == cve_dict["cve_id"])
                        .where(KERNEL_CVE_HOSTS.c.hostname == hostname)
                    ).first()

                    if not existing:
                        conn.execute(
                            KERNEL_CVE_HOSTS.insert().values(
                                cve_id=cve_dict["cve_id"],
                                hostname=hostname,
                                kernel_version=kernel_version,
                                architecture=architecture,
                                status="vulnerable",
                            )
                        )

        return HostScanResult(
            hostname=hostname,
            kernel_version=kernel_version,
            total_cves=len(vulnerabilities),
            critical=severity_counts["critical"],
            high=severity_counts["high"],
            medium=severity_counts["medium"],
            low=severity_counts["low"],
            vulnerabilities=vulnerabilities[:50],  # Limit response size
        )

    @app.get("/kernel/subsystems", response_model=Dict[str, Any])
    async def list_subsystem_cve_counts():
        """Get CVE counts by kernel subsystem."""
        with db_engine.connect() as conn:
            # Aggregate CVEs by subsystem
            rows = conn.execute(sa.select(KERNEL_CVES.c.subsystems)).fetchall()

            subsystem_counts: Dict[str, int] = {}
            for row in rows:
                for subsystem in row.subsystems or []:
                    subsystem_counts[subsystem] = subsystem_counts.get(subsystem, 0) + 1

            # Sort by count
            sorted_subsystems = sorted(
                subsystem_counts.items(),
                key=lambda x: x[1],
                reverse=True,
            )

        return {
            "subsystems": [
                {"name": name, "cve_count": count}
                for name, count in sorted_subsystems
            ]
        }

    LOGGER.info("Registered kernel CVE API endpoints")
