"""
NVD (National Vulnerability Database) API Client
Fetches Linux kernel CVEs from NIST NVD API 2.0

API Docs: https://nvd.nist.gov/developers/vulnerabilities
Rate Limits:
  - Unauthenticated: 5 requests per 30 seconds
  - With API key: 50 requests per 30 seconds

Usage:
    client = NVDClient(api_key="optional-key")
    cves = await client.search_kernel_cves(severity="CRITICAL")
    await client.sync_to_database(db_session)
"""
from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import aiohttp

LOGGER = logging.getLogger(__name__)

NVD_API_BASE = "https://services.nvd.nist.gov/rest/json/cves/2.0"
KERNEL_KEYWORD = "linux kernel"
DEFAULT_RESULTS_PER_PAGE = 100
MAX_RESULTS_PER_PAGE = 2000


@dataclass
class CVSSv3:
    """CVSS v3.x scoring data."""
    score: float
    vector: str
    severity: str  # LOW, MEDIUM, HIGH, CRITICAL


@dataclass
class CVERecord:
    """Parsed CVE record from NVD."""
    cve_id: str
    description: str
    severity: str
    cvss_v3: Optional[CVSSv3]
    affected_versions: List[Dict[str, str]]
    fixed_in_version: Optional[str]
    subsystems: List[str]
    cwe_ids: List[str]
    references: List[Dict[str, str]]
    published_date: datetime
    last_modified: datetime
    exploit_available: bool = False
    cisa_kev: bool = False

    def to_db_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database insertion."""
        return {
            "cve_id": self.cve_id,
            "description": self.description,
            "severity": self.severity.lower(),
            "cvss_v3_score": self.cvss_v3.score if self.cvss_v3 else None,
            "cvss_v3_vector": self.cvss_v3.vector if self.cvss_v3 else None,
            "affected_versions": self.affected_versions,
            "fixed_in_version": self.fixed_in_version,
            "subsystems": self.subsystems,
            "cwe_ids": self.cwe_ids,
            "references": self.references,
            "exploit_available": self.exploit_available,
            "cisa_kev": self.cisa_kev,
            "published_date": self.published_date,
            "last_modified": self.last_modified,
            "local_status": "open",
        }


@dataclass
class SyncResult:
    """Result of CVE sync operation."""
    total_fetched: int = 0
    new_cves: int = 0
    updated_cves: int = 0
    errors: List[str] = field(default_factory=list)
    duration_seconds: float = 0.0


class NVDClient:
    """Client for NIST National Vulnerability Database API 2.0."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        rate_limit_delay: float = 6.0,  # 5 req/30s = 6s between requests
    ):
        self.api_key = api_key or os.getenv("NVD_API_KEY")
        self.rate_limit_delay = rate_limit_delay if not self.api_key else 0.6
        self._last_request_time: Optional[float] = None
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            headers = {"Accept": "application/json"}
            if self.api_key:
                headers["apiKey"] = self.api_key
            self._session = aiohttp.ClientSession(headers=headers)
        return self._session

    async def _rate_limit(self) -> None:
        """Enforce rate limiting between requests."""
        if self._last_request_time is not None:
            elapsed = asyncio.get_event_loop().time() - self._last_request_time
            if elapsed < self.rate_limit_delay:
                await asyncio.sleep(self.rate_limit_delay - elapsed)
        self._last_request_time = asyncio.get_event_loop().time()

    async def close(self) -> None:
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()

    def _parse_cve(self, vuln: Dict[str, Any]) -> Optional[CVERecord]:
        """Parse NVD vulnerability record into CVERecord."""
        try:
            cve = vuln.get("cve", {})
            cve_id = cve.get("id", "")

            # Get description (prefer English)
            descriptions = cve.get("descriptions", [])
            description = next(
                (d["value"] for d in descriptions if d.get("lang") == "en"),
                descriptions[0]["value"] if descriptions else "",
            )

            # Parse CVSS v3.x (prefer 3.1, fallback to 3.0)
            cvss_v3 = None
            metrics = cve.get("metrics", {})
            for cvss_key in ["cvssMetricV31", "cvssMetricV30"]:
                if cvss_key in metrics and metrics[cvss_key]:
                    cvss_data = metrics[cvss_key][0].get("cvssData", {})
                    cvss_v3 = CVSSv3(
                        score=cvss_data.get("baseScore", 0.0),
                        vector=cvss_data.get("vectorString", ""),
                        severity=cvss_data.get("baseSeverity", "UNKNOWN"),
                    )
                    break

            severity = cvss_v3.severity if cvss_v3 else "UNKNOWN"

            # Parse CWE IDs
            cwe_ids = []
            for weakness in cve.get("weaknesses", []):
                for desc in weakness.get("description", []):
                    cwe_value = desc.get("value", "")
                    if cwe_value.startswith("CWE-"):
                        cwe_ids.append(cwe_value)

            # Parse references
            references = [
                {"url": ref.get("url", ""), "source": ref.get("source", "")}
                for ref in cve.get("references", [])
            ]

            # Parse affected configurations (simplified)
            affected_versions = []
            configurations = cve.get("configurations", [])
            for config in configurations:
                for node in config.get("nodes", []):
                    for cpe_match in node.get("cpeMatch", []):
                        if "linux_kernel" in cpe_match.get("criteria", "").lower():
                            version_info = {
                                "criteria": cpe_match.get("criteria", ""),
                            }
                            if "versionStartIncluding" in cpe_match:
                                version_info["from"] = cpe_match["versionStartIncluding"]
                            if "versionEndExcluding" in cpe_match:
                                version_info["to"] = cpe_match["versionEndExcluding"]
                            affected_versions.append(version_info)

            # Extract subsystems from description
            subsystems = self._extract_subsystems(description)

            # Parse dates
            published = datetime.fromisoformat(
                cve.get("published", "").replace("Z", "+00:00")
            )
            modified = datetime.fromisoformat(
                cve.get("lastModified", "").replace("Z", "+00:00")
            )

            return CVERecord(
                cve_id=cve_id,
                description=description,
                severity=severity,
                cvss_v3=cvss_v3,
                affected_versions=affected_versions,
                fixed_in_version=None,  # Requires additional lookup
                subsystems=subsystems,
                cwe_ids=cwe_ids,
                references=references,
                published_date=published,
                last_modified=modified,
            )
        except Exception as e:
            LOGGER.warning("Failed to parse CVE: %s", e)
            return None

    def _extract_subsystems(self, description: str) -> List[str]:
        """Extract kernel subsystems from CVE description."""
        subsystems = []
        desc_lower = description.lower()

        subsystem_keywords = {
            "drm": ["drm", "graphics", "gpu", "radeon", "amdgpu", "i915", "nouveau"],
            "net": ["network", "netfilter", "tcp", "udp", "ipv4", "ipv6", "socket", "netdev"],
            "fs": ["filesystem", "ext4", "btrfs", "xfs", "nfs", "f2fs", "overlayfs"],
            "mm": ["memory", "mmap", "vmalloc", "slab", "page", "hugepage"],
            "security": ["selinux", "apparmor", "seccomp", "lsm", "capabilities"],
            "usb": ["usb", "usbhid", "usbcore"],
            "bluetooth": ["bluetooth", "btusb"],
            "sound": ["alsa", "sound", "audio"],
            "block": ["block", "scsi", "nvme", "md"],
            "kvm": ["kvm", "virtualization", "vmx", "svm"],
        }

        for subsystem, keywords in subsystem_keywords.items():
            if any(kw in desc_lower for kw in keywords):
                subsystems.append(subsystem)

        return subsystems if subsystems else ["other"]

    async def search_kernel_cves(
        self,
        keyword: str = KERNEL_KEYWORD,
        cvss_severity: Optional[str] = None,
        published_start: Optional[datetime] = None,
        published_end: Optional[datetime] = None,
        results_per_page: int = DEFAULT_RESULTS_PER_PAGE,
        max_results: Optional[int] = None,
    ) -> List[CVERecord]:
        """
        Search for Linux kernel CVEs from NVD.

        Args:
            keyword: Search keyword (default: "linux kernel")
            cvss_severity: Filter by severity (LOW, MEDIUM, HIGH, CRITICAL)
            published_start: Filter by publish date start
            published_end: Filter by publish date end
            results_per_page: Results per API request
            max_results: Maximum total results to fetch

        Returns:
            List of parsed CVE records
        """
        session = await self._get_session()
        all_cves: List[CVERecord] = []
        start_index = 0

        while True:
            await self._rate_limit()

            params: Dict[str, Any] = {
                "keywordSearch": keyword,
                "resultsPerPage": min(results_per_page, MAX_RESULTS_PER_PAGE),
                "startIndex": start_index,
            }

            if cvss_severity:
                params["cvssV3Severity"] = cvss_severity.upper()

            if published_start:
                params["pubStartDate"] = published_start.strftime("%Y-%m-%dT%H:%M:%S.000")

            if published_end:
                params["pubEndDate"] = published_end.strftime("%Y-%m-%dT%H:%M:%S.000")

            try:
                async with session.get(NVD_API_BASE, params=params) as resp:
                    if resp.status == 403:
                        LOGGER.error("NVD API rate limit exceeded or invalid API key")
                        break
                    resp.raise_for_status()
                    data = await resp.json()

                    total_results = data.get("totalResults", 0)
                    vulnerabilities = data.get("vulnerabilities", [])

                    LOGGER.info(
                        "NVD: Fetched %d/%d CVEs (offset %d)",
                        len(vulnerabilities),
                        total_results,
                        start_index,
                    )

                    for vuln in vulnerabilities:
                        cve = self._parse_cve(vuln)
                        if cve:
                            all_cves.append(cve)

                    start_index += len(vulnerabilities)

                    # Check if we've fetched all results
                    if start_index >= total_results:
                        break

                    # Check max_results limit
                    if max_results and len(all_cves) >= max_results:
                        break

            except aiohttp.ClientError as e:
                LOGGER.error("NVD API request failed: %s", e)
                break

        return all_cves

    async def get_cve_by_id(self, cve_id: str) -> Optional[CVERecord]:
        """Fetch a single CVE by its ID."""
        session = await self._get_session()
        await self._rate_limit()

        try:
            async with session.get(NVD_API_BASE, params={"cveId": cve_id}) as resp:
                resp.raise_for_status()
                data = await resp.json()

                vulnerabilities = data.get("vulnerabilities", [])
                if vulnerabilities:
                    return self._parse_cve(vulnerabilities[0])
                return None

        except aiohttp.ClientError as e:
            LOGGER.error("Failed to fetch CVE %s: %s", cve_id, e)
            return None

    async def sync_kernel_cves(
        self,
        db_engine,
        since: Optional[datetime] = None,
        full_sync: bool = False,
        severity_filter: Optional[str] = None,
    ) -> SyncResult:
        """
        Sync kernel CVEs from NVD to local database.

        Args:
            db_engine: SQLAlchemy engine for database connection
            since: Only fetch CVEs modified since this date
            full_sync: If True, fetch all CVEs regardless of 'since'
            severity_filter: Only sync CVEs of this severity

        Returns:
            SyncResult with statistics
        """
        import sqlalchemy as sa
        try:
            from .schema import KERNEL_CVES
        except ImportError:
            from schema import KERNEL_CVES

        result = SyncResult()
        start_time = asyncio.get_event_loop().time()

        # Determine date range
        if full_sync:
            published_start = None
        elif since:
            published_start = since
        else:
            # Default: last 7 days
            published_start = datetime.now(timezone.utc) - timedelta(days=7)

        try:
            cves = await self.search_kernel_cves(
                published_start=published_start,
                cvss_severity=severity_filter,
            )
            result.total_fetched = len(cves)

            with db_engine.begin() as conn:
                for cve in cves:
                    # Check if CVE exists
                    existing = conn.execute(
                        sa.select(KERNEL_CVES.c.cve_id, KERNEL_CVES.c.last_modified)
                        .where(KERNEL_CVES.c.cve_id == cve.cve_id)
                    ).first()

                    cve_dict = cve.to_db_dict()

                    if existing is None:
                        # Insert new CVE
                        conn.execute(KERNEL_CVES.insert().values(**cve_dict))
                        result.new_cves += 1
                    elif existing.last_modified < cve.last_modified:
                        # Update existing CVE
                        conn.execute(
                            KERNEL_CVES.update()
                            .where(KERNEL_CVES.c.cve_id == cve.cve_id)
                            .values(**cve_dict)
                        )
                        result.updated_cves += 1

            LOGGER.info(
                "CVE sync complete: %d fetched, %d new, %d updated",
                result.total_fetched,
                result.new_cves,
                result.updated_cves,
            )

        except Exception as e:
            LOGGER.error("CVE sync failed: %s", e)
            result.errors.append(str(e))

        finally:
            result.duration_seconds = asyncio.get_event_loop().time() - start_time
            await self.close()

        return result


async def main():
    """Test NVD client."""
    logging.basicConfig(level=logging.INFO)

    client = NVDClient()
    try:
        # Fetch recent critical kernel CVEs
        cves = await client.search_kernel_cves(
            cvss_severity="CRITICAL",
            published_start=datetime.now(timezone.utc) - timedelta(days=30),
            max_results=10,
        )

        for cve in cves:
            print(f"{cve.cve_id}: {cve.severity} - {cve.description[:100]}...")

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
