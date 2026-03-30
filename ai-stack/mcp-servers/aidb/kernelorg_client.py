"""
kernel.org Release Tracker
Fetches Linux kernel releases and security information from kernel.org

Sources:
- https://www.kernel.org/releases.json - Official release JSON
- https://www.kernel.org/finger_banner - Version banner
- https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git

Usage:
    client = KernelOrgClient()
    releases = await client.get_releases()
    latest = await client.get_latest_stable()
"""
from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import aiohttp

LOGGER = logging.getLogger(__name__)

RELEASES_JSON_URL = "https://www.kernel.org/releases.json"
FINGER_BANNER_URL = "https://www.kernel.org/finger_banner"
KERNEL_ORG_GIT = "https://git.kernel.org/pub/scm/linux/kernel/git"


@dataclass
class KernelRelease:
    """Kernel release information from kernel.org."""
    version: str
    track: str  # mainline, stable, longterm, linux-next
    released: Optional[datetime]
    eol: bool
    moniker: Optional[str]  # e.g., "longterm", "stable"
    tarball_url: str
    pgp_url: Optional[str]
    changelog_url: Optional[str]
    git_sha: Optional[str] = None
    rust_version: Optional[str] = None

    def to_db_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database insertion."""
        return {
            "version": self.version,
            "release_date": self.released or datetime.now(timezone.utc),
            "eol_date": None if not self.eol else datetime.now(timezone.utc),
            "track": self.track,
            "tarball_url": self.tarball_url,
            "pgp_signature_url": self.pgp_url,
            "changelog_url": self.changelog_url,
            "git_sha": self.git_sha,
            "security_fixes": [],
            "rust_version_required": self.rust_version,
        }


@dataclass
class VersionSecurityStatus:
    """Security status for a kernel version."""
    version: str
    is_supported: bool
    is_eol: bool
    known_cves: int
    critical_cves: int
    recommended_upgrade: Optional[str]
    days_since_release: int


class KernelOrgClient:
    """Client for kernel.org release information."""

    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None
        self._releases_cache: Optional[List[KernelRelease]] = None
        self._cache_time: Optional[float] = None
        self._cache_ttl: float = 3600.0  # 1 hour cache

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={"Accept": "application/json"}
            )
        return self._session

    async def close(self) -> None:
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()

    def _is_cache_valid(self) -> bool:
        """Check if releases cache is still valid."""
        if self._releases_cache is None or self._cache_time is None:
            return False
        return (asyncio.get_event_loop().time() - self._cache_time) < self._cache_ttl

    def _parse_version(self, version_str: str) -> tuple:
        """Parse version string into comparable tuple."""
        parts = re.findall(r"\d+", version_str)
        return tuple(int(p) for p in parts)

    async def get_releases(self, force_refresh: bool = False) -> List[KernelRelease]:
        """
        Fetch all current kernel releases from kernel.org.

        Args:
            force_refresh: Bypass cache and fetch fresh data

        Returns:
            List of KernelRelease objects
        """
        if not force_refresh and self._is_cache_valid():
            return self._releases_cache or []

        session = await self._get_session()
        releases: List[KernelRelease] = []

        try:
            async with session.get(RELEASES_JSON_URL) as resp:
                resp.raise_for_status()
                data = await resp.json()

                for release in data.get("releases", []):
                    version = release.get("version", "")
                    moniker = release.get("moniker", "")

                    # Determine track
                    if moniker == "mainline":
                        track = "mainline"
                    elif moniker == "stable":
                        track = "stable"
                    elif moniker == "longterm":
                        track = "longterm"
                    elif "next" in version.lower():
                        track = "linux-next"
                    else:
                        track = "stable"

                    # Parse release date
                    released = None
                    if release.get("released"):
                        try:
                            released = datetime.fromisoformat(
                                release["released"].get("isodate", "").replace("Z", "+00:00")
                            )
                        except (ValueError, KeyError):
                            pass

                    # Build URLs
                    major = version.split(".")[0] if "." in version else version
                    tarball_url = f"https://cdn.kernel.org/pub/linux/kernel/v{major}.x/linux-{version}.tar.xz"
                    pgp_url = f"{tarball_url}.sign"
                    changelog_url = release.get("changelog_url")

                    releases.append(
                        KernelRelease(
                            version=version,
                            track=track,
                            released=released,
                            eol=release.get("iseol", False),
                            moniker=moniker,
                            tarball_url=tarball_url,
                            pgp_url=pgp_url,
                            changelog_url=changelog_url,
                        )
                    )

                self._releases_cache = releases
                self._cache_time = asyncio.get_event_loop().time()

                LOGGER.info("kernel.org: Fetched %d releases", len(releases))

        except aiohttp.ClientError as e:
            LOGGER.error("Failed to fetch kernel releases: %s", e)

        return releases

    async def get_latest_mainline(self) -> Optional[KernelRelease]:
        """Get the latest mainline (Linus' tree) kernel."""
        releases = await self.get_releases()
        mainline = [r for r in releases if r.track == "mainline"]
        return mainline[0] if mainline else None

    async def get_latest_stable(self) -> Optional[KernelRelease]:
        """Get the latest stable kernel release."""
        releases = await self.get_releases()
        stable = [r for r in releases if r.track == "stable" and not r.eol]
        if not stable:
            return None
        # Sort by version number
        stable.sort(key=lambda r: self._parse_version(r.version), reverse=True)
        return stable[0]

    async def get_longterm_releases(self) -> List[KernelRelease]:
        """Get all active LTS (longterm) kernel releases."""
        releases = await self.get_releases()
        return [r for r in releases if r.track == "longterm" and not r.eol]

    async def get_supported_versions(self) -> List[str]:
        """Get list of all currently supported kernel versions."""
        releases = await self.get_releases()
        return [r.version for r in releases if not r.eol]

    async def is_version_supported(self, version: str) -> bool:
        """Check if a specific kernel version is still supported."""
        supported = await self.get_supported_versions()
        # Extract major.minor from version (e.g., "6.12.5" -> "6.12")
        version_parts = version.split(".")
        if len(version_parts) >= 2:
            major_minor = f"{version_parts[0]}.{version_parts[1]}"
            for supported_ver in supported:
                if supported_ver.startswith(major_minor):
                    return True
        return False

    async def get_upgrade_recommendation(
        self, current_version: str, track: str = "stable"
    ) -> Optional[str]:
        """
        Get recommended upgrade version for current kernel.

        Args:
            current_version: Current kernel version
            track: Preferred track (mainline, stable, longterm)

        Returns:
            Recommended version string or None if already latest
        """
        releases = await self.get_releases()
        current_tuple = self._parse_version(current_version)

        candidates = [
            r for r in releases
            if r.track == track and not r.eol
        ]

        if not candidates:
            return None

        # Sort by version, newest first
        candidates.sort(key=lambda r: self._parse_version(r.version), reverse=True)

        latest = candidates[0]
        latest_tuple = self._parse_version(latest.version)

        if latest_tuple > current_tuple:
            return latest.version
        return None

    async def sync_releases_to_db(self, db_engine) -> int:
        """
        Sync kernel releases to local database.

        Args:
            db_engine: SQLAlchemy engine

        Returns:
            Number of releases synced
        """
        import sqlalchemy as sa
        try:
            from .schema import KERNEL_RELEASES
        except ImportError:
            from schema import KERNEL_RELEASES

        releases = await self.get_releases(force_refresh=True)
        synced = 0

        with db_engine.begin() as conn:
            for release in releases:
                # Upsert release
                existing = conn.execute(
                    sa.select(KERNEL_RELEASES.c.version)
                    .where(KERNEL_RELEASES.c.version == release.version)
                ).first()

                release_dict = release.to_db_dict()

                if existing is None:
                    conn.execute(KERNEL_RELEASES.insert().values(**release_dict))
                    synced += 1
                else:
                    conn.execute(
                        KERNEL_RELEASES.update()
                        .where(KERNEL_RELEASES.c.version == release.version)
                        .values(**release_dict)
                    )

        LOGGER.info("kernel.org: Synced %d releases to database", synced)
        return synced


async def main():
    """Test kernel.org client."""
    logging.basicConfig(level=logging.INFO)

    client = KernelOrgClient()
    try:
        # Get all releases
        releases = await client.get_releases()
        print(f"\nTotal releases: {len(releases)}")

        # Get latest stable
        stable = await client.get_latest_stable()
        if stable:
            print(f"Latest stable: {stable.version}")

        # Get LTS releases
        lts = await client.get_longterm_releases()
        print(f"Active LTS versions: {[r.version for r in lts]}")

        # Check if a version is supported
        is_supported = await client.is_version_supported("6.1.0")
        print(f"Is 6.1.x supported? {is_supported}")

        # Get upgrade recommendation
        upgrade = await client.get_upgrade_recommendation("6.10.0")
        print(f"Upgrade recommendation for 6.10.0: {upgrade}")

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
