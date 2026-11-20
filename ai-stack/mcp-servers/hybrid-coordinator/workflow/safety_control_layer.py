"""
Safety Control Layer (Phase 13.1 — Harden)
Inspired by Agentix: plan -> sandbox -> propose -> verify.

Intercepts risky tool calls and converts them into 'Proposals' 
requiring human approval or automated validation.
"""

import json
import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, Optional

from extensions.blast_radius_classifier import classify

logger = logging.getLogger(__name__)

def _resolve_repo_root() -> Path:
    """Resolve REPO_ROOT from env or by walking up from this file to CLAUDE.md."""
    env_root = os.environ.get("REPO_ROOT", "").strip()
    if env_root:
        return Path(env_root).resolve()
    current = Path(__file__).resolve().parent
    while current != current.parent:
        if (current / "CLAUDE.md").exists():
            return current
        current = current.parent
    return Path.cwd()


def _resolve_proposals_dir() -> Path:
    return _resolve_repo_root() / ".agent/proposals"


PROPOSALS_DIR = _resolve_proposals_dir()
PROPOSALS_DB = PROPOSALS_DIR / "proposals.json"


class SafetyControlLayer:
    def __init__(self, mode: str = "review", proposals_dir: Optional[Path] = None):
        self.mode = mode  # open, review, strict
        self.proposals_dir = Path(proposals_dir) if proposals_dir is not None else _resolve_proposals_dir()
        self.proposals_db = self.proposals_dir / "proposals.json"
        # Created lazily on first write: the sandboxed coordinator can only write
        # declared paths, and registration must not fail on an unwritable repo.

    def _ensure_db(self):
        self.proposals_dir.mkdir(parents=True, exist_ok=True)
        if not self.proposals_db.exists():
            with open(self.proposals_db, "w") as f:
                json.dump({"proposals": [], "last_id": 0}, f)

    def _get_next_id(self) -> int:
        self._ensure_db()
        with open(self.proposals_db, "r") as f:
            db = json.load(f)
        new_id = db.get("last_id", 0) + 1
        db["last_id"] = new_id
        with open(self.proposals_db, "w") as f:
            json.dump(db, f)
        return new_id

    def intercept_action(self, action_type: str, params: Dict[str, Any], agent_id: str) -> Optional[Dict[str, Any]]:
        """
        Check if an action should be intercepted and turned into a proposal.
        Returns a 'proposal_result' dict if intercepted, else None.
        """
        if self.mode == "open":
            return None

        # Convert action to string for classifier
        action_str = f"{action_type}({json.dumps(params)})"
        tier = classify(action_str)

        should_intercept = False
        if self.mode == "review" and tier in ("critical", "high"):
            should_intercept = True
        elif self.mode == "strict" and tier in ("critical", "high", "medium"):
            should_intercept = True

        if not should_intercept:
            return None

        # Intercept! An unwritable proposals dir fails closed (action blocked).
        try:
            return self._write_proposal(action_type, params, agent_id, tier)
        except OSError as exc:
            logger.warning("proposals dir %s unwritable: %s", self.proposals_dir, exc)
            return {
                "status": "blocked",
                "reason": "proposals_dir_unwritable",
                "tier": tier,
            }

    def _write_proposal(self, action_type: str, params: Dict[str, Any], agent_id: str, tier: str) -> Dict[str, Any]:
        proposal_id = self._get_next_id()
        proposal_path = self.proposals_dir / f"proposal_{proposal_id:04d}.json"
        
        proposal_data = {
            "id": proposal_id,
            "ts": time.time(),
            "agent_id": agent_id,
            "action_type": action_type,
            "params": params,
            "tier": tier,
            "status": "pending",
            "validation": "unverified"
        }

        with open(proposal_path, "w") as f:
            json.dump(proposal_data, f, indent=2)

        # Update DB index
        with open(self.proposals_db, "r") as f:
            db = json.load(f)
        db["proposals"].append({
            "id": proposal_id,
            "ts": proposal_data["ts"],
            "tier": tier,
            "status": "pending",
            "path": str(proposal_path)
        })
        with open(self.proposals_db, "w") as f:
            json.dump(db, f, indent=2)

        return {
            "status": "intercepted",
            "proposal_id": proposal_id,
            "tier": tier,
            "message": f"Action intercepted by Safety Control Layer. Proposal #{proposal_id} created for {tier}-risk action. View in {proposal_path}.",
            "next_step": "Waiting for human approval or automated validation run."
        }

    def validate_proposal(self, proposal_id: int) -> Dict[str, Any]:
        """Perform automated validation (dry-runs) on a proposal."""
        proposal_path = self.proposals_dir / f"proposal_{proposal_id:04d}.json"
        if not proposal_path.exists():
            return {"error": "Proposal not found"}

        with open(proposal_path, "r") as f:
            proposal = json.load(f)

        action_type = proposal.get("action_type")
        params = proposal.get("params", {})
        validation_results = []

        # 1. Nix Syntax Check
        if action_type in ("write_file", "replace"):
            file_path = params.get("file_path", "")
            if file_path.endswith(".nix"):
                content = params.get("content") or params.get("new_string", "")
                if content:
                    # Write temporary file for check
                    tmp_nix = Path("/tmp/proposal_check.nix")
                    tmp_nix.write_text(content)
                    try:
                        res = subprocess.run(["nix-instantiate", "--parse", str(tmp_nix)], 
                                           capture_output=True, text=True, timeout=5)
                        if res.returncode == 0:
                            validation_results.append({"type": "nix_syntax", "status": "pass"})
                        else:
                            validation_results.append({"type": "nix_syntax", "status": "fail", "error": res.stderr})
                    except Exception as e:
                        validation_results.append({"type": "nix_syntax", "status": "error", "error": str(e)})

        # 2. Blast Radius Check (already done by intercept, but re-verify)
        validation_results.append({"type": "risk_assessment", "tier": proposal.get("tier")})

        # Update proposal status
        proposal["validation"] = validation_results
        with open(proposal_path, "w") as f:
            json.dump(proposal, f, indent=2)

        return {"id": proposal_id, "validation": validation_results}
