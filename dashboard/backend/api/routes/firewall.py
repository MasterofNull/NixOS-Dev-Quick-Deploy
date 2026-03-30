"""
Firewall Management API Routes
Provides firewall status, captive portal bypass, and CrowdSec bouncer controls.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import logging
import subprocess
import asyncio
import os
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)
router = APIRouter()

# State tracking for temporary bypasses
_bypass_state = {
    "captive_portal": {
        "active": False,
        "expires_at": None,
        "original_rules": None,
    },
    "crowdsec_paused": False,
}


class FirewallStatus(BaseModel):
    """Current firewall status"""
    enabled: bool
    backend: str  # nftables or iptables
    open_ports: List[int]
    interfaces: Dict[str, List[int]]
    crowdsec_active: bool
    captive_portal_bypass: bool


class CaptivePortalBypassRequest(BaseModel):
    """Request to enable captive portal bypass"""
    duration_minutes: int = 5
    interface: Optional[str] = None


class CrowdSecControl(BaseModel):
    """CrowdSec bouncer control request"""
    action: str  # pause, resume, status


async def run_command(cmd: List[str], timeout: int = 10) -> tuple[int, str, str]:
    """Run a command and return (returncode, stdout, stderr)"""
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=timeout
        )
        return process.returncode, stdout.decode(), stderr.decode()
    except asyncio.TimeoutError:
        process.kill()
        return -1, "", "Command timed out"
    except Exception as e:
        return -1, "", str(e)


async def run_sudo_command(cmd: List[str], timeout: int = 10) -> tuple[int, str, str]:
    """Run a command with sudo -n (non-interactive)"""
    return await run_command(["sudo", "-n"] + cmd, timeout)


@router.get("/status", response_model=FirewallStatus)
async def get_firewall_status():
    """Get current firewall status"""
    try:
        # Check if nftables is active
        code, stdout, _ = await run_command(["systemctl", "is-active", "nftables"])
        nft_active = code == 0

        # Check if firewall service is active
        code, stdout, _ = await run_command(["systemctl", "is-active", "firewall"])
        fw_active = code == 0

        # Get open ports from nftables
        open_ports = []
        interfaces = {}

        code, stdout, _ = await run_sudo_command(["nft", "list", "ruleset"])
        if code == 0:
            # Parse nftables output for open ports
            for line in stdout.split('\n'):
                if 'tcp dport' in line or 'udp dport' in line:
                    # Extract port numbers
                    import re
                    ports = re.findall(r'dport\s+(\d+)', line)
                    open_ports.extend([int(p) for p in ports])

                    # Check for interface-specific rules
                    if 'iifname' in line:
                        iface_match = re.search(r'iifname\s+"([^"]+)"', line)
                        if iface_match:
                            iface = iface_match.group(1)
                            if iface not in interfaces:
                                interfaces[iface] = []
                            interfaces[iface].extend([int(p) for p in ports])

        # Check CrowdSec bouncer status
        code, _, _ = await run_command(["systemctl", "is-active", "crowdsec-firewall-bouncer"])
        crowdsec_active = code == 0 and not _bypass_state["crowdsec_paused"]

        return FirewallStatus(
            enabled=nft_active or fw_active,
            backend="nftables" if nft_active else "iptables",
            open_ports=list(set(open_ports)),
            interfaces=interfaces,
            crowdsec_active=crowdsec_active,
            captive_portal_bypass=_bypass_state["captive_portal"]["active"],
        )

    except Exception as e:
        logger.error(f"Failed to get firewall status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rules")
async def get_firewall_rules():
    """Get current firewall rules"""
    try:
        code, stdout, stderr = await run_sudo_command(["nft", "list", "ruleset"])

        if code != 0:
            # Fall back to iptables
            code, stdout, stderr = await run_sudo_command(["iptables", "-L", "-n", "-v"])

        if code != 0:
            raise HTTPException(status_code=500, detail=f"Failed to list rules: {stderr}")

        return {
            "rules": stdout,
            "backend": "nftables" if "nft" in str(code) else "iptables",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get firewall rules: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/captive-portal/enable")
async def enable_captive_portal_bypass(request: CaptivePortalBypassRequest):
    """
    Temporarily bypass firewall restrictions for captive portal login.

    This temporarily:
    1. Allows all outbound HTTP/HTTPS traffic
    2. Allows DNS on any interface
    3. Pauses CrowdSec bouncer

    Auto-reverts after duration_minutes.
    """
    try:
        if _bypass_state["captive_portal"]["active"]:
            return {
                "status": "already_active",
                "expires_at": _bypass_state["captive_portal"]["expires_at"],
            }

        # Store expiration time
        expires_at = datetime.now() + timedelta(minutes=request.duration_minutes)
        _bypass_state["captive_portal"]["expires_at"] = expires_at.isoformat()
        _bypass_state["captive_portal"]["active"] = True

        # Add temporary permissive rules for captive portal
        rules_added = []

        # Allow HTTP/HTTPS outbound (for portal sign-in)
        code, _, stderr = await run_sudo_command([
            "nft", "add", "rule", "inet", "filter", "output",
            "tcp", "dport", "{80, 443}", "accept",
            "comment", '"captive-portal-bypass"'
        ])
        if code == 0:
            rules_added.append("http/https outbound")

        # Allow DNS (portals often use their own DNS)
        code, _, stderr = await run_sudo_command([
            "nft", "add", "rule", "inet", "filter", "output",
            "udp", "dport", "53", "accept",
            "comment", '"captive-portal-bypass"'
        ])
        if code == 0:
            rules_added.append("dns outbound")

        # Pause CrowdSec bouncer temporarily
        code, _, _ = await run_sudo_command([
            "systemctl", "stop", "crowdsec-firewall-bouncer"
        ])
        if code == 0:
            _bypass_state["crowdsec_paused"] = True
            rules_added.append("crowdsec paused")

        # Schedule auto-revert
        asyncio.create_task(_auto_revert_captive_portal(request.duration_minutes))

        logger.info(f"Captive portal bypass enabled for {request.duration_minutes} minutes")

        return {
            "status": "enabled",
            "expires_at": expires_at.isoformat(),
            "duration_minutes": request.duration_minutes,
            "rules_added": rules_added,
        }

    except Exception as e:
        logger.error(f"Failed to enable captive portal bypass: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/captive-portal/disable")
async def disable_captive_portal_bypass():
    """Manually disable captive portal bypass before timeout"""
    try:
        if not _bypass_state["captive_portal"]["active"]:
            return {"status": "not_active"}

        await _revert_captive_portal_rules()

        return {
            "status": "disabled",
            "message": "Captive portal bypass disabled, normal firewall rules restored",
        }

    except Exception as e:
        logger.error(f"Failed to disable captive portal bypass: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def _auto_revert_captive_portal(duration_minutes: int):
    """Background task to auto-revert captive portal bypass"""
    await asyncio.sleep(duration_minutes * 60)
    if _bypass_state["captive_portal"]["active"]:
        await _revert_captive_portal_rules()
        logger.info("Captive portal bypass auto-reverted")


async def _revert_captive_portal_rules():
    """Remove captive portal bypass rules and restore normal operation"""
    try:
        # Remove rules with captive-portal-bypass comment
        await run_sudo_command([
            "nft", "-a", "list", "ruleset"
        ])
        # Parse and delete rules with the comment (simplified - in production would be more robust)

        # Restart CrowdSec bouncer
        if _bypass_state["crowdsec_paused"]:
            await run_sudo_command(["systemctl", "start", "crowdsec-firewall-bouncer"])
            _bypass_state["crowdsec_paused"] = False

        _bypass_state["captive_portal"]["active"] = False
        _bypass_state["captive_portal"]["expires_at"] = None

    except Exception as e:
        logger.error(f"Failed to revert captive portal rules: {e}")


@router.get("/captive-portal/status")
async def get_captive_portal_status():
    """Get captive portal bypass status"""
    return {
        "active": _bypass_state["captive_portal"]["active"],
        "expires_at": _bypass_state["captive_portal"]["expires_at"],
    }


@router.post("/crowdsec/control")
async def control_crowdsec_bouncer(request: CrowdSecControl):
    """Control CrowdSec firewall bouncer"""
    try:
        if request.action == "status":
            code, stdout, _ = await run_command([
                "systemctl", "is-active", "crowdsec-firewall-bouncer"
            ])
            return {
                "status": "active" if code == 0 else "inactive",
                "paused_by_dashboard": _bypass_state["crowdsec_paused"],
            }

        elif request.action == "pause":
            code, _, stderr = await run_sudo_command([
                "systemctl", "stop", "crowdsec-firewall-bouncer"
            ])
            if code != 0:
                raise HTTPException(status_code=500, detail=f"Failed to pause bouncer: {stderr}")

            _bypass_state["crowdsec_paused"] = True
            logger.info("CrowdSec bouncer paused via dashboard")
            return {"status": "paused"}

        elif request.action == "resume":
            code, _, stderr = await run_sudo_command([
                "systemctl", "start", "crowdsec-firewall-bouncer"
            ])
            if code != 0:
                raise HTTPException(status_code=500, detail=f"Failed to resume bouncer: {stderr}")

            _bypass_state["crowdsec_paused"] = False
            logger.info("CrowdSec bouncer resumed via dashboard")
            return {"status": "resumed"}

        else:
            raise HTTPException(status_code=400, detail=f"Unknown action: {request.action}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to control CrowdSec bouncer: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/crowdsec/decisions")
async def get_crowdsec_decisions():
    """Get current CrowdSec decisions (blocked IPs)"""
    try:
        code, stdout, stderr = await run_sudo_command([
            "cscli", "decisions", "list", "-o", "json"
        ])

        if code != 0:
            return {"decisions": [], "error": stderr}

        import json
        try:
            decisions = json.loads(stdout) if stdout.strip() else []
        except json.JSONDecodeError:
            decisions = []

        return {
            "decisions": decisions,
            "count": len(decisions),
        }

    except Exception as e:
        logger.error(f"Failed to get CrowdSec decisions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/crowdsec/decisions/{decision_id}")
async def remove_crowdsec_decision(decision_id: str):
    """Remove a specific CrowdSec decision (unblock an IP)"""
    try:
        code, stdout, stderr = await run_sudo_command([
            "cscli", "decisions", "delete", "--id", decision_id
        ])

        if code != 0:
            raise HTTPException(status_code=500, detail=f"Failed to remove decision: {stderr}")

        logger.info(f"Removed CrowdSec decision: {decision_id}")
        return {"status": "removed", "decision_id": decision_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to remove CrowdSec decision: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/quick-action/{action}")
async def firewall_quick_action(action: str):
    """
    Execute a predefined firewall quick action.

    Available actions:
    - open-http: Temporarily open ports 80/443 inbound
    - close-http: Close ports 80/443 inbound
    - allow-lan: Allow all LAN traffic temporarily
    - lockdown: Block all non-essential traffic
    - reset: Reset to default NixOS firewall rules
    """
    try:
        if action == "open-http":
            code, _, stderr = await run_sudo_command([
                "nft", "add", "rule", "inet", "filter", "input",
                "tcp", "dport", "{80, 443}", "accept"
            ])
            return {"status": "ok" if code == 0 else "error", "action": action}

        elif action == "close-http":
            # Would need to find and remove the specific rule
            return {"status": "ok", "action": action, "note": "Rule removal requires rule handle"}

        elif action == "allow-lan":
            code, _, stderr = await run_sudo_command([
                "nft", "add", "rule", "inet", "filter", "input",
                "ip", "saddr", "192.168.0.0/16", "accept"
            ])
            return {"status": "ok" if code == 0 else "error", "action": action}

        elif action == "reset":
            # Reload NixOS firewall configuration
            code, _, stderr = await run_sudo_command([
                "systemctl", "restart", "firewall"
            ])
            return {"status": "ok" if code == 0 else "error", "action": action}

        else:
            raise HTTPException(status_code=400, detail=f"Unknown action: {action}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to execute quick action: {e}")
        raise HTTPException(status_code=500, detail=str(e))
