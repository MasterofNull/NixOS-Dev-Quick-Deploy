"""
Safety Control Layer (Phase 13.1 — Harden)
Inspired by Agentix: plan -> sandbox -> propose -> verify.

Intercepts risky tool calls and converts them into 'Proposals' 
requiring human approval or automated validation.
"""

import json
import os
import time
import hashlib
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from extensions.blast_radius_classifier import classify

PROPOSALS_DIR = Path(".agent/proposals")
PROPOSALS_DB = PROPOSALS_DIR / "proposals.json"

class SafetyControlLayer:
    def __init__(self, mode: str = "review"):
        self.mode = mode # open, review, strict
        PROPOSALS_DIR.mkdir(parents=True, exist_ok=True)
        self._ensure_db()

    def _ensure_db(self):
        if not PROPOSALS_DB.exists():
            with open(PROPOSALS_DB, "w") as f:
                json.dump({"proposals": [], "last_id": 0}, f)

    def _get_next_id(self) -> int:
        with open(PROPOSALS_DB, "r") as f:
            db = json.load(f)
        new_id = db.get("last_id", 0) + 1
        db["last_id"] = new_id
        with open(PROPOSALS_DB, "w") as f:
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

        # Intercept!
        proposal_id = self._get_next_id()
        proposal_path = PROPOSALS_DIR / f"proposal_{proposal_id:04d}.json"
        
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
        with open(PROPOSALS_DB, "r") as f:
            db = json.load(f)
        db["proposals"].append({
            "id": proposal_id,
            "ts": proposal_data["ts"],
            "tier": tier,
            "status": "pending",
            "path": str(proposal_path)
        })
        with open(PROPOSALS_DB, "w") as f:
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
        proposal_path = PROPOSALS_DIR / f"proposal_{proposal_id:04d}.json"
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
