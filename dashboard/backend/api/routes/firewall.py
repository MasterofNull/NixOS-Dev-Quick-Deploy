"""
Firewall Management API Routes
Provides firewall status, captive portal bypass, and CrowdSec bouncer controls.

Security Controls:
- All operations are audit logged
- Duration limits prevent indefinite bypasses
- Confirmation required for destructive actions
- Input validation on all parameters
- Non-interactive sudo (NOPASSWD) for specific commands only
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any, Literal
import logging
import asyncio
import os
import re
import json
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)
router = APIRouter()

# ── Security Constants ──────────────────────────────────────────────────────────
# Maximum captive portal bypass duration (prevents indefinite exposure)
MAX_BYPASS_DURATION_MINUTES = 15
# Minimum bypass duration (prevents accidental instant reverts)
MIN_BYPASS_DURATION_MINUTES = 1
# Allowed quick actions (whitelist approach)
ALLOWED_QUICK_ACTIONS = frozenset({"open-http", "close-http", "allow-lan", "reset"})
# Allowed CrowdSec control actions
ALLOWED_CROWDSEC_ACTIONS = frozenset({"pause", "resume", "status"})
# Valid decision ID pattern (alphanumeric, dashes)
DECISION_ID_PATTERN = re.compile(r'^[a-zA-Z0-9\-]+$')

# ── Audit Logging ───────────────────────────────────────────────────────────────
AUDIT_LOG_PATH = os.getenv(
    "FIREWALL_AUDIT_LOG_PATH",
    os.getenv("DASHBOARD_DATA_DIR", "/tmp") + "/firewall-audit.jsonl"
)


def audit_log(action: str, details: Dict[str, Any], success: bool, client_ip: str = "unknown"):
    """Append firewall operation to audit log."""
    try:
        entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "action": action,
            "success": success,
            "client_ip": client_ip,
            "details": details,
        }
        log_path = Path(AUDIT_LOG_PATH)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")
        logger.info(f"Firewall audit: {action} success={success} ip={client_ip}")
    except Exception as e:
        logger.warning(f"Failed to write firewall audit log: {e}")


# ── State Tracking ──────────────────────────────────────────────────────────────
_bypass_state = {
    "captive_portal": {
        "active": False,
        "expires_at": None,
        "enabled_by": None,
        "enabled_at": None,
        "rule_handles": [],  # Track nft rule handles for cleanup
    },
    "crowdsec_paused": False,
    "crowdsec_paused_by": None,
}


# ── Request/Response Models ─────────────────────────────────────────────────────
class FirewallStatus(BaseModel):
    """Current firewall status"""
    enabled: bool
    backend: str  # nftables or iptables
    open_ports: List[int]
    interfaces: Dict[str, List[int]]
    crowdsec_active: bool
    captive_portal_bypass: bool
    bypass_expires_at: Optional[str] = None


class CaptivePortalBypassRequest(BaseModel):
    """Request to enable captive portal bypass"""
    duration_minutes: int = Field(
        default=5,
        ge=MIN_BYPASS_DURATION_MINUTES,
        le=MAX_BYPASS_DURATION_MINUTES,
        description=f"Bypass duration ({MIN_BYPASS_DURATION_MINUTES}-{MAX_BYPASS_DURATION_MINUTES} minutes)"
    )
    interface: Optional[str] = Field(
        default=None,
        max_length=32,
        description="Optional: specific interface for bypass"
    )

    @field_validator('interface')
    @classmethod
    def validate_interface(cls, v):
        if v is not None:
            # Interface names: alphanumeric, dashes, dots (e.g., wlan0, eth0, enp3s0)
            if not re.match(r'^[a-zA-Z0-9\-\.]+$', v):
                raise ValueError('Invalid interface name format')
        return v


class CrowdSecControl(BaseModel):
    """CrowdSec bouncer control request"""
    action: Literal["pause", "resume", "status"]


class QuickActionRequest(BaseModel):
    """Quick action request with optional confirmation"""
    confirm: bool = Field(
        default=False,
        description="Set to true to confirm destructive actions"
    )


class DecisionRemovalRequest(BaseModel):
    """Request to remove a CrowdSec decision"""
    confirm: bool = Field(
        default=False,
        description="Set to true to confirm IP unblock"
    )


# ── Command Execution ───────────────────────────────────────────────────────────
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
    """Run a command with sudo -n (non-interactive, requires NOPASSWD sudoers entry)"""
    return await run_command(["sudo", "-n"] + cmd, timeout)


def get_client_ip(request: Request) -> str:
    """Extract client IP from request."""
    return getattr(request.client, "host", None) or "unknown"


# ── API Endpoints ───────────────────────────────────────────────────────────────
@router.get("/status", response_model=FirewallStatus)
async def get_firewall_status(request: Request):
    """Get current firewall status"""
    client_ip = get_client_ip(request)
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
            bypass_expires_at=_bypass_state["captive_portal"]["expires_at"],
        )

    except Exception as e:
        logger.error(f"Failed to get firewall status: {e}")
        audit_log("status", {"error": str(e)}, success=False, client_ip=client_ip)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rules")
async def get_firewall_rules(request: Request):
    """Get current firewall rules (read-only, no audit needed)"""
    try:
        code, stdout, stderr = await run_sudo_command(["nft", "list", "ruleset"])

        if code != 0:
            # Fall back to iptables
            code, stdout, stderr = await run_sudo_command(["iptables", "-L", "-n", "-v"])

        if code != 0:
            raise HTTPException(status_code=500, detail=f"Failed to list rules: {stderr}")

        return {
            "rules": stdout,
            "backend": "nftables" if "table" in stdout else "iptables",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get firewall rules: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/captive-portal/enable")
async def enable_captive_portal_bypass(request: Request, body: CaptivePortalBypassRequest):
    """
    Temporarily bypass firewall restrictions for captive portal login.

    This temporarily:
    1. Allows all outbound HTTP/HTTPS traffic
    2. Allows DNS on any interface
    3. Pauses CrowdSec bouncer

    Auto-reverts after duration_minutes (max 15 minutes).
    """
    client_ip = get_client_ip(request)
    try:
        if _bypass_state["captive_portal"]["active"]:
            return {
                "status": "already_active",
                "expires_at": _bypass_state["captive_portal"]["expires_at"],
                "enabled_by": _bypass_state["captive_portal"]["enabled_by"],
            }

        # Calculate expiration
        now = datetime.now()
        expires_at = now + timedelta(minutes=body.duration_minutes)

        # Update state first (before making changes)
        _bypass_state["captive_portal"]["expires_at"] = expires_at.isoformat()
        _bypass_state["captive_portal"]["active"] = True
        _bypass_state["captive_portal"]["enabled_by"] = client_ip
        _bypass_state["captive_portal"]["enabled_at"] = now.isoformat()
        _bypass_state["captive_portal"]["rule_handles"] = []

        rules_added = []
        errors = []

        # Allow HTTP/HTTPS outbound (for portal sign-in)
        code, stdout, stderr = await run_sudo_command([
            "nft", "add", "rule", "inet", "filter", "output",
            "tcp", "dport", "{80, 443}", "accept",
            "comment", '"captive-portal-bypass"'
        ])
        if code == 0:
            rules_added.append("http/https outbound")
        else:
            errors.append(f"http/https: {stderr}")

        # Allow DNS (portals often use their own DNS)
        code, stdout, stderr = await run_sudo_command([
            "nft", "add", "rule", "inet", "filter", "output",
            "udp", "dport", "53", "accept",
            "comment", '"captive-portal-bypass"'
        ])
        if code == 0:
            rules_added.append("dns outbound")
        else:
            errors.append(f"dns: {stderr}")

        # Pause CrowdSec bouncer temporarily
        code, _, stderr = await run_sudo_command([
            "systemctl", "stop", "crowdsec-firewall-bouncer"
        ])
        if code == 0:
            _bypass_state["crowdsec_paused"] = True
            _bypass_state["crowdsec_paused_by"] = "captive-portal"
            rules_added.append("crowdsec paused")
        else:
            errors.append(f"crowdsec: {stderr}")

        # Schedule auto-revert
        asyncio.create_task(_auto_revert_captive_portal(body.duration_minutes))

        audit_log(
            "captive_portal_enable",
            {
                "duration_minutes": body.duration_minutes,
                "interface": body.interface,
                "rules_added": rules_added,
                "errors": errors,
            },
            success=len(rules_added) > 0,
            client_ip=client_ip,
        )

        logger.info(f"Captive portal bypass enabled for {body.duration_minutes}m by {client_ip}")

        return {
            "status": "enabled",
            "expires_at": expires_at.isoformat(),
            "duration_minutes": body.duration_minutes,
            "rules_added": rules_added,
            "errors": errors if errors else None,
        }

    except Exception as e:
        # Revert state on failure
        _bypass_state["captive_portal"]["active"] = False
        _bypass_state["captive_portal"]["expires_at"] = None
        logger.error(f"Failed to enable captive portal bypass: {e}")
        audit_log("captive_portal_enable", {"error": str(e)}, success=False, client_ip=client_ip)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/captive-portal/disable")
async def disable_captive_portal_bypass(request: Request):
    """Manually disable captive portal bypass before timeout"""
    client_ip = get_client_ip(request)
    try:
        if not _bypass_state["captive_portal"]["active"]:
            return {"status": "not_active"}

        await _revert_captive_portal_rules()

        audit_log("captive_portal_disable", {"manual": True}, success=True, client_ip=client_ip)

        return {
            "status": "disabled",
            "message": "Captive portal bypass disabled, normal firewall rules restored",
        }

    except Exception as e:
        logger.error(f"Failed to disable captive portal bypass: {e}")
        audit_log("captive_portal_disable", {"error": str(e)}, success=False, client_ip=client_ip)
        raise HTTPException(status_code=500, detail=str(e))


async def _auto_revert_captive_portal(duration_minutes: int):
    """Background task to auto-revert captive portal bypass"""
    await asyncio.sleep(duration_minutes * 60)
    if _bypass_state["captive_portal"]["active"]:
        await _revert_captive_portal_rules()
        audit_log("captive_portal_auto_revert", {"duration_minutes": duration_minutes}, success=True)
        logger.info("Captive portal bypass auto-reverted")


async def _revert_captive_portal_rules():
    """Remove captive portal bypass rules and restore normal operation"""
    try:
        # Get current rules with handles
        code, stdout, _ = await run_sudo_command(["nft", "-a", "list", "ruleset"])
        if code == 0:
            # Find and delete rules with captive-portal-bypass comment
            for line in stdout.split('\n'):
                if 'captive-portal-bypass' in line:
                    # Extract handle number
                    handle_match = re.search(r'handle\s+(\d+)', line)
                    if handle_match:
                        handle = handle_match.group(1)
                        # Determine chain (output rules are in filter output)
                        if 'output' in line.lower():
                            await run_sudo_command([
                                "nft", "delete", "rule", "inet", "filter", "output",
                                "handle", handle
                            ])

        # Restart CrowdSec bouncer
        if _bypass_state["crowdsec_paused"] and _bypass_state["crowdsec_paused_by"] == "captive-portal":
            await run_sudo_command(["systemctl", "start", "crowdsec-firewall-bouncer"])
            _bypass_state["crowdsec_paused"] = False
            _bypass_state["crowdsec_paused_by"] = None

        _bypass_state["captive_portal"]["active"] = False
        _bypass_state["captive_portal"]["expires_at"] = None
        _bypass_state["captive_portal"]["enabled_by"] = None
        _bypass_state["captive_portal"]["enabled_at"] = None
        _bypass_state["captive_portal"]["rule_handles"] = []

    except Exception as e:
        logger.error(f"Failed to revert captive portal rules: {e}")


@router.get("/captive-portal/status")
async def get_captive_portal_status():
    """Get captive portal bypass status"""
    return {
        "active": _bypass_state["captive_portal"]["active"],
        "expires_at": _bypass_state["captive_portal"]["expires_at"],
        "enabled_by": _bypass_state["captive_portal"]["enabled_by"],
        "enabled_at": _bypass_state["captive_portal"]["enabled_at"],
    }


@router.post("/crowdsec/control")
async def control_crowdsec_bouncer(request: Request, body: CrowdSecControl):
    """Control CrowdSec firewall bouncer"""
    client_ip = get_client_ip(request)
    try:
        if body.action == "status":
            code, stdout, _ = await run_command([
                "systemctl", "is-active", "crowdsec-firewall-bouncer"
            ])
            return {
                "status": "active" if code == 0 else "inactive",
                "paused_by_dashboard": _bypass_state["crowdsec_paused"],
                "paused_reason": _bypass_state["crowdsec_paused_by"],
            }

        elif body.action == "pause":
            if _bypass_state["crowdsec_paused"]:
                return {"status": "already_paused", "paused_by": _bypass_state["crowdsec_paused_by"]}

            code, _, stderr = await run_sudo_command([
                "systemctl", "stop", "crowdsec-firewall-bouncer"
            ])
            if code != 0:
                audit_log("crowdsec_pause", {"error": stderr}, success=False, client_ip=client_ip)
                raise HTTPException(status_code=500, detail=f"Failed to pause bouncer: {stderr}")

            _bypass_state["crowdsec_paused"] = True
            _bypass_state["crowdsec_paused_by"] = "manual"
            audit_log("crowdsec_pause", {}, success=True, client_ip=client_ip)
            logger.info(f"CrowdSec bouncer paused via dashboard by {client_ip}")
            return {"status": "paused"}

        elif body.action == "resume":
            code, _, stderr = await run_sudo_command([
                "systemctl", "start", "crowdsec-firewall-bouncer"
            ])
            if code != 0:
                audit_log("crowdsec_resume", {"error": stderr}, success=False, client_ip=client_ip)
                raise HTTPException(status_code=500, detail=f"Failed to resume bouncer: {stderr}")

            _bypass_state["crowdsec_paused"] = False
            _bypass_state["crowdsec_paused_by"] = None
            audit_log("crowdsec_resume", {}, success=True, client_ip=client_ip)
            logger.info(f"CrowdSec bouncer resumed via dashboard by {client_ip}")
            return {"status": "resumed"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to control CrowdSec bouncer: {e}")
        audit_log("crowdsec_control", {"action": body.action, "error": str(e)}, success=False, client_ip=client_ip)
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
async def remove_crowdsec_decision(
    request: Request,
    decision_id: str,
    body: Optional[DecisionRemovalRequest] = None,
):
    """
    Remove a specific CrowdSec decision (unblock an IP).
    Requires confirmation to prevent accidental unblocks.
    """
    client_ip = get_client_ip(request)

    # Validate decision ID format
    if not DECISION_ID_PATTERN.match(decision_id):
        raise HTTPException(status_code=400, detail="Invalid decision ID format")

    # Require confirmation for this destructive action
    if body is None or not body.confirm:
        return {
            "status": "confirmation_required",
            "message": "Set confirm=true in request body to remove this decision",
            "decision_id": decision_id,
        }

    try:
        code, stdout, stderr = await run_sudo_command([
            "cscli", "decisions", "delete", "--id", decision_id
        ])

        if code != 0:
            audit_log(
                "crowdsec_decision_remove",
                {"decision_id": decision_id, "error": stderr},
                success=False,
                client_ip=client_ip,
            )
            raise HTTPException(status_code=500, detail=f"Failed to remove decision: {stderr}")

        audit_log(
            "crowdsec_decision_remove",
            {"decision_id": decision_id},
            success=True,
            client_ip=client_ip,
        )
        logger.info(f"Removed CrowdSec decision {decision_id} by {client_ip}")
        return {"status": "removed", "decision_id": decision_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to remove CrowdSec decision: {e}")
        audit_log(
            "crowdsec_decision_remove",
            {"decision_id": decision_id, "error": str(e)},
            success=False,
            client_ip=client_ip,
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/quick-action/{action}")
async def firewall_quick_action(
    request: Request,
    action: str,
    body: Optional[QuickActionRequest] = None,
):
    """
    Execute a predefined firewall quick action.

    Available actions:
    - open-http: Temporarily open ports 80/443 inbound
    - close-http: Close ports 80/443 inbound
    - allow-lan: Allow all LAN traffic temporarily
    - reset: Reset to default NixOS firewall rules (requires confirmation)
    """
    client_ip = get_client_ip(request)

    # Validate action is in allowlist
    if action not in ALLOWED_QUICK_ACTIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown action: {action}. Allowed: {', '.join(ALLOWED_QUICK_ACTIONS)}"
        )

    # Require confirmation for destructive actions
    destructive_actions = {"reset", "allow-lan"}
    if action in destructive_actions and (body is None or not body.confirm):
        return {
            "status": "confirmation_required",
            "message": f"Action '{action}' requires confirmation. Set confirm=true in request body.",
            "action": action,
        }

    try:
        result = {"status": "error", "action": action}

        if action == "open-http":
            code, _, stderr = await run_sudo_command([
                "nft", "add", "rule", "inet", "filter", "input",
                "tcp", "dport", "{80, 443}", "accept",
                "comment", '"dashboard-quick-action"'
            ])
            result = {"status": "ok" if code == 0 else "error", "action": action}
            if code != 0:
                result["error"] = stderr

        elif action == "close-http":
            # Find and remove dashboard-quick-action rules for ports 80/443
            code, stdout, _ = await run_sudo_command(["nft", "-a", "list", "ruleset"])
            if code == 0:
                removed = 0
                for line in stdout.split('\n'):
                    if 'dashboard-quick-action' in line and ('80' in line or '443' in line):
                        handle_match = re.search(r'handle\s+(\d+)', line)
                        if handle_match:
                            await run_sudo_command([
                                "nft", "delete", "rule", "inet", "filter", "input",
                                "handle", handle_match.group(1)
                            ])
                            removed += 1
                result = {"status": "ok", "action": action, "rules_removed": removed}
            else:
                result = {"status": "error", "action": action, "note": "Could not list rules"}

        elif action == "allow-lan":
            code, _, stderr = await run_sudo_command([
                "nft", "add", "rule", "inet", "filter", "input",
                "ip", "saddr", "192.168.0.0/16", "accept",
                "comment", '"dashboard-quick-action-lan"'
            ])
            # Also allow 10.0.0.0/8 for corporate/VPN networks
            await run_sudo_command([
                "nft", "add", "rule", "inet", "filter", "input",
                "ip", "saddr", "10.0.0.0/8", "accept",
                "comment", '"dashboard-quick-action-lan"'
            ])
            result = {"status": "ok" if code == 0 else "error", "action": action}
            if code != 0:
                result["error"] = stderr

        elif action == "reset":
            # Reload NixOS firewall configuration (restores declarative rules)
            code, _, stderr = await run_sudo_command([
                "systemctl", "restart", "firewall"
            ])
            result = {
                "status": "ok" if code == 0 else "error",
                "action": action,
                "message": "Firewall reset to NixOS declarative configuration" if code == 0 else stderr,
            }

        audit_log(
            f"quick_action_{action}",
            {"result": result},
            success=result.get("status") == "ok",
            client_ip=client_ip,
        )
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to execute quick action {action}: {e}")
        audit_log(f"quick_action_{action}", {"error": str(e)}, success=False, client_ip=client_ip)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/audit-log")
async def get_firewall_audit_log(limit: int = 100):
    """Get recent firewall audit log entries (last N entries)"""
    try:
        log_path = Path(AUDIT_LOG_PATH)
        if not log_path.exists():
            return {"entries": [], "count": 0}

        entries = []
        with open(log_path, "r") as f:
            for line in f:
                try:
                    entries.append(json.loads(line.strip()))
                except json.JSONDecodeError:
                    continue

        # Return most recent entries
        recent = entries[-limit:] if len(entries) > limit else entries
        return {
            "entries": list(reversed(recent)),  # Newest first
            "count": len(recent),
            "total": len(entries),
        }

    except Exception as e:
        logger.error(f"Failed to read firewall audit log: {e}")
        raise HTTPException(status_code=500, detail=str(e))
