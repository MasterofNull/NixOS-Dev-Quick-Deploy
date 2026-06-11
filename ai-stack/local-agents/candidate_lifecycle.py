import json
import os
import shutil
from datetime import datetime
from pathlib import Path

VALID_STATES = ["proposed", "evaluating", "reviewed", "adopted", "rejected", "retired"]

class CandidateLifecycleManager:
    def __init__(self, candidates_path: Path):
        self.path = Path(candidates_path)
        self.candidates = []

    def _get_defaults(self):
        return {
            "state": "proposed",
            "trust_score": 0.0,
            "relevance": 0.5,
            "governance": {"proposals": [], "reviews": [], "consensus_prd": None},
            "eval_results": {"sandbox_pass": None, "tokenomics_impact": "unknown", "hardware_compatible": None},
            "lifecycle_log": []
        }

    def load(self) -> list[dict]:
        if not self.path.exists():
            self.candidates = []
            return []

        with open(self.path, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = {}

        # candidates.json is a dict wrapper: {"candidates": [...], "schema_version": ...}
        raw = data.get("candidates", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
        self.candidates = list(raw)

        # Apply lifecycle defaults
        defaults = self._get_defaults()
        for cand in self.candidates:
            for key, val in defaults.items():
                if key not in cand:
                    cand[key] = val
                elif isinstance(val, dict) and isinstance(cand[key], dict):
                    for subkey, subval in val.items():
                        if subkey not in cand[key]:
                            cand[key][subkey] = subval
        return self.candidates

    def save(self, candidates: list[dict]):
        """Persist candidates, preserving the outer wrapper schema."""
        self.candidates = candidates
        # Read existing wrapper to preserve metadata fields
        wrapper: dict = {}
        if self.path.exists():
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    existing = json.load(f)
                if isinstance(existing, dict):
                    wrapper = {k: v for k, v in existing.items() if k != "candidates"}
            except (json.JSONDecodeError, OSError):
                pass
        wrapper["candidates"] = candidates
        wrapper.setdefault("schema_version", "discovery-candidates.v1")
        wrapper["total_candidates"] = len(candidates)
        tmp_path = self.path.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(wrapper, f, indent=2, sort_keys=True)
            f.write("\n")
        os.replace(tmp_path, self.path)

    def transition(self, candidate_id, new_state, by="system", note="") -> dict:
        if new_state not in VALID_STATES:
            raise ValueError(f"Invalid state: {new_state}")
        
        cand = next((c for c in self.candidates if c.get("id") == candidate_id), None)
        if not cand:
            raise ValueError(f"Candidate not found: {candidate_id}")
        
        old_state = cand.get("state", "proposed")
        cand["state"] = new_state
        
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "from_state": old_state,
            "to_state": new_state,
            "by": by,
            "note": note
        }
        
        if "lifecycle_log" not in cand:
            cand["lifecycle_log"] = []
        cand["lifecycle_log"].append(log_entry)
        
        return cand

    def set_trust_score(self, candidate_id, score):
        cand = next((c for c in self.candidates if c.get("id") == candidate_id), None)
        if not cand:
            raise ValueError(f"Candidate not found: {candidate_id}")
        cand["trust_score"] = max(0.0, min(1.0, float(score)))

    def set_relevance(self, candidate_id, score):
        cand = next((c for c in self.candidates if c.get("id") == candidate_id), None)
        if not cand:
            raise ValueError(f"Candidate not found: {candidate_id}")
        cand["relevance"] = max(0.0, min(1.0, float(score)))

    def get_by_state(self, state) -> list[dict]:
        return [c for c in self.candidates if c.get("state") == state]
