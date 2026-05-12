from workflow.lifecycle_fsm import *
import logging
from typing import Dict, List, Any

logger = logging.getLogger(__name__)

# Phase 28.1: Guarded Execution Safety State
safety_mode = "permissive"  # "permissive" | "enforcing" | "learning"
safety_gate_log: List[Dict[str, Any]] = []

def set_safety_mode(mode: str) -> None:
    """Update the current safety mode of the hybrid coordinator."""
    global safety_mode
    if mode in ["permissive", "enforcing", "learning"]:
        safety_mode = mode
        logger.info(f"Lifecycle FSM safety mode transitioned to: {mode}")
    else:
        raise ValueError(f"Invalid safety mode: {mode}")

def log_safety_action(action: str, blast_radius: str, allowed: bool, reason: str = "") -> None:
    """Record a safety gate decision for audit and learning."""
    entry = {"action": action, "blast_radius": blast_radius, "allowed": allowed, "reason": reason}
    safety_gate_log.append(entry)
