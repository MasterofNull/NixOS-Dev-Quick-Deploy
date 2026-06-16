import fcntl
import json
import os
import shutil
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

VALID_STATES = ["proposed", "evaluating", "reviewed", "adopted", "rejected", "retired"]
_REQUIRED_FIELDS = {"id", "category", "title"}


@contextmanager
def _file_lock(lock_path: Path):
    """Exclusive file lock for cross-process safety (AppArmor needs 'k' on this path)."""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "w") as lf:
        try:
            fcntl.flock(lf, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)

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
        """Persist candidates with exclusive file lock to prevent lost updates."""
        lock_path = self.path.with_suffix(".lock")
        with _file_lock(lock_path):
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

        # Validate required fields before any state change
        missing = _REQUIRED_FIELDS - set(cand.keys())
        if missing:
            raise ValueError(f"Candidate {candidate_id} missing required fields: {missing}")
        
        old_state = cand.get("state", "proposed")
        cand["state"] = new_state
        
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
            "from_state": old_state,
            "to_state": new_state,
            "by": by,
            "note": note
        }
        
        if "lifecycle_log" not in cand:
            cand["lifecycle_log"] = []
        cand["lifecycle_log"].append(log_entry)

        if new_state == "evaluating":
            try:
                from eval_sandbox import EvalSandboxExecutor  # noqa: PLC0415
                sandbox_results = EvalSandboxExecutor().evaluate(cand)
                if "eval_results" not in cand:
                    cand["eval_results"] = {}
                cand["eval_results"].update(sandbox_results)
            except Exception as exc:  # noqa: BLE001
                if "eval_results" not in cand:
                    cand["eval_results"] = {}
                cand["eval_results"]["sandbox_error"] = str(exc)

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
