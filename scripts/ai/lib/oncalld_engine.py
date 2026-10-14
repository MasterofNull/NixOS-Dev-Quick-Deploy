#!/usr/bin/env python3
"""Autonomous On-Call Incident Daemon Engine (`aq-oncalld`).

Implements System 1 high-confidence triage wakeup, worktree-isolated remediation,
monotonic epoch fencing, ambient credential scrubbing, independent model review,
and candidate SHA binding.

Lifecycle State Machine:
  INTAKE -> CORRELATE -> ADMIT -> CLAIM -> ISOLATE -> REPRODUCE
         -> DIAGNOSE -> FIX -> VALIDATE -> INDEPENDENT_REVIEW
         -> STAGE_PR -> AWAIT_OPERATOR -> ACTIVATION
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import logging
import os
import re
import shutil
import sqlite3
import subprocess
import tempfile
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger("aq-oncalld")

_DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_STATE_DIR = Path(
    os.getenv("AQ_ONCALL_STATE_DIR")
    or _DEFAULT_REPO_ROOT / ".agent" / "oncall"
)


class EpochFencingError(Exception):
    """Raised when an operation is attempted with an expired or mismatched epoch token."""
    pass


class ContainmentViolationError(Exception):
    """Raised when a workspace path violates worktree containment."""
    pass


class ReviewIntegrityError(Exception):
    """Raised when self-review or candidate drift is detected."""
    pass


class WorktreeIsolationError(Exception):
    """Raised when an isolated git worktree cannot be created (fail closed, no fallback)."""
    pass


class DuplicateClaimError(Exception):
    """Raised when an incident already has an active implementer claim."""
    pass


@dataclass
class OnCallIncident:
    incident_id: str
    title: str
    source: str
    severity: str  # "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | "NOISE"
    incident_class: str  # "CRASH" | "HEALTH_CHECK_FAILURE" | "RESOURCE_EXHAUSTION" | etc.
    confidence: float
    correlation_key: str
    reproduction_cmd: Optional[str]
    status: str  # "INTAKE" | "CORRELATE" | "ADMITTED" | "CLAIMED" | "RESOLVED" | "REJECTED"
    raw_details: Dict[str, Any]
    created_at: str
    updated_at: str


@dataclass
class RemediationClaim:
    claim_id: str
    incident_id: str
    epoch: int  # Monotonic fencing token
    claimant_lane: str  # e.g. "codex", "local", "claude", "antigravity"
    worktree_path: str
    worktree_branch: str
    state: str  # "ISOLATING" | "REPRODUCING" | "DIAGNOSING" | "FIXING" | "VALIDATING" | "REVIEWING" | "AWAITING_REVIEW" | "PENDING_PR" | "PR_STAGED" | "AWAIT_OPERATOR" | "ACTIVATED" | "FAILED"
    # AWAITING_REVIEW: candidate bound, no reviewer verdict recorded yet.
    # PENDING_PR: real reviewer PASS recorded, no PR opened yet (PR_STAGED needs a real PR).
    candidate_sha256: Optional[str] = None
    git_tree_hash: Optional[str] = None
    test_proofs_hash: Optional[str] = None
    reviewer_lane: Optional[str] = None
    reviewer_verdict: Optional[str] = None  # None until a real reviewer records one: "PASS" | "CONCERNS" | "REJECTED"
    review_explanation: Optional[str] = None
    pr_branch: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# Security & Containment Utilities
# ─────────────────────────────────────────────────────────────────────────────

_SAFE_ENV_VARS = {
    "PATH", "USER", "LOGNAME", "HOME", "TERM", "SHELL", "LANG", "LC_ALL",
    "LC_CTYPE", "TZ", "TMPDIR", "REPO_ROOT", "PYTHONPATH"
}

_SECRET_PATTERN = re.compile(
    r"(?i)(token|secret|key|auth|password|cred|sops|passwd|cert)"
)


def scrub_credentials(env: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Scrub ambient secrets (tokens, API keys, SOPS, SSH auth) from sub-process environment."""
    base_env = env if env is not None else dict(os.environ)
    scrubbed: Dict[str, str] = {}

    for k, v in base_env.items():
        if k in _SAFE_ENV_VARS:
            scrubbed[k] = v
        elif _SECRET_PATTERN.search(k):
            # Block secrets
            continue
        elif k.startswith(("SSH_", "GIT_", "AWS_", "GITHUB_", "GH_", "OPENAI_", "ANTHROPIC_", "GEMINI_")):
            # Block credential namespaces
            continue
        else:
            scrubbed[k] = v

    scrubbed["AQ_ONCALL_CONFINED"] = "1"
    scrubbed["AQ_DELEGATE_HANDBACK"] = "1"
    return scrubbed


def verify_worktree_containment(worktree_path: str, repo_root: Optional[Path] = None) -> bool:
    """Verify that the worktree resides strictly inside designated isolation directory and is not main."""
    root = (repo_root or _DEFAULT_REPO_ROOT).resolve()
    wt = Path(worktree_path).resolve()

    if wt == root:
        return False

    allowed_parent = (root / ".agents" / "delegation" / "worktrees").resolve()
    try:
        wt.relative_to(allowed_parent)
        return True
    except ValueError:
        # Check custom delegation dir if set
        delegation_env = os.getenv("AQ_DELEGATION_DIR")
        if delegation_env:
            custom_parent = (Path(delegation_env).resolve() / "worktrees").resolve()
            try:
                wt.relative_to(custom_parent)
                return True
            except ValueError:
                pass
        return False


def compute_candidate_sha256(git_tree_hash: str, test_proofs: str) -> Tuple[str, str, str]:
    """Compute candidate SHA binding: candidate_sha256 = hash(tree_hash + proofs_hash).

    Returns (git_tree_hash, test_proofs_hash, candidate_sha256).
    """
    proofs_hash = hashlib.sha256(test_proofs.encode("utf-8")).hexdigest()
    combined = f"{git_tree_hash}:{proofs_hash}"
    candidate_sha = hashlib.sha256(combined.encode("utf-8")).hexdigest()
    return git_tree_hash, proofs_hash, candidate_sha


def verify_candidate_binding(
    candidate_sha256: str,
    current_tree_hash: str,
    test_proofs: str
) -> bool:
    """Verify that current tree state and test proofs still bind to candidate_sha256."""
    _, _, expected_sha = compute_candidate_sha256(current_tree_hash, test_proofs)
    return candidate_sha256 == expected_sha


# ─────────────────────────────────────────────────────────────────────────────
# SQLite Durable Storage & Monotonic Epoch Fencing
# ─────────────────────────────────────────────────────────────────────────────

class OnCallStorage:
    """SQLite-backed transactional store with monotonic epoch fencing."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._fallback_memory = False
        self._mem_conn: Optional[sqlite3.Connection] = None
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._init_db()
        except (OSError, sqlite3.Error) as err:
            logger.error(
                "oncalld storage at %s unusable (%s): FALLING BACK TO VOLATILE :memory: "
                "- persisted state is NOT being used", self.db_path, err)
            self._fallback_memory = True
            self.db_path = Path(":memory:")
            self._mem_conn = sqlite3.connect(":memory:", timeout=30.0)
            self._mem_conn.row_factory = sqlite3.Row
            self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        if self._fallback_memory and self._mem_conn is not None:
            return self._mem_conn
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
        except sqlite3.OperationalError:
            pass
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS oncall_incidents (
                    incident_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    source TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    incident_class TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    correlation_key TEXT NOT NULL,
                    reproduction_cmd TEXT,
                    status TEXT NOT NULL,
                    raw_details TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_incidents_correlation
                ON oncall_incidents (correlation_key, status);

                CREATE TABLE IF NOT EXISTS oncall_claims (
                    claim_id TEXT PRIMARY KEY,
                    incident_id TEXT NOT NULL,
                    epoch INTEGER NOT NULL,
                    claimant_lane TEXT NOT NULL,
                    worktree_path TEXT NOT NULL,
                    worktree_branch TEXT NOT NULL,
                    state TEXT NOT NULL,
                    candidate_sha256 TEXT,
                    git_tree_hash TEXT,
                    test_proofs_hash TEXT,
                    reviewer_lane TEXT,
                    reviewer_verdict TEXT,
                    review_explanation TEXT,
                    pr_branch TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (incident_id) REFERENCES oncall_incidents(incident_id)
                );

                CREATE INDEX IF NOT EXISTS idx_claims_incident
                ON oncall_claims (incident_id, epoch);

                CREATE TABLE IF NOT EXISTS oncall_incident_epochs (
                    incident_id TEXT PRIMARY KEY,
                    current_epoch INTEGER NOT NULL
                );
            """)
            # Old-schema DBs may hold duplicate active rows; supersede them (keep newest)
            # before the unique indexes so index creation cannot fail.
            conn.execute("""
                UPDATE oncall_incidents SET status = 'REJECTED',
                    updated_at = strftime('%Y-%m-%dT%H:%M:%f+00:00','now')
                WHERE status NOT IN ('RESOLVED', 'REJECTED') AND rowid NOT IN (
                    SELECT MAX(rowid) FROM oncall_incidents
                    WHERE status NOT IN ('RESOLVED', 'REJECTED') GROUP BY correlation_key)
            """)
            conn.execute("""
                UPDATE oncall_claims SET state = 'FAILED',
                    review_explanation = 'superseded: duplicate active claim found at schema migration',
                    updated_at = strftime('%Y-%m-%dT%H:%M:%f+00:00','now')
                WHERE state NOT IN ('ACTIVATED', 'FAILED') AND rowid NOT IN (
                    SELECT MAX(rowid) FROM oncall_claims
                    WHERE state NOT IN ('ACTIVATED', 'FAILED') GROUP BY incident_id)
            """)
            conn.executescript("""
                CREATE UNIQUE INDEX IF NOT EXISTS uq_incidents_active_correlation
                ON oncall_incidents (correlation_key)
                WHERE status NOT IN ('RESOLVED', 'REJECTED');

                CREATE UNIQUE INDEX IF NOT EXISTS uq_claims_one_active_per_incident
                ON oncall_claims (incident_id)
                WHERE state NOT IN ('ACTIVATED', 'FAILED');
            """)

    def save_incident(self, inc: OnCallIncident) -> None:
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO oncall_incidents (
                    incident_id, title, source, severity, incident_class,
                    confidence, correlation_key, reproduction_cmd, status,
                    raw_details, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(incident_id) DO UPDATE SET
                    status=excluded.status,
                    updated_at=excluded.updated_at,
                    raw_details=excluded.raw_details
            """, (
                inc.incident_id, inc.title, inc.source, inc.severity,
                inc.incident_class, inc.confidence, inc.correlation_key,
                inc.reproduction_cmd, inc.status, json.dumps(inc.raw_details),
                inc.created_at, inc.updated_at
            ))

    def get_incident(self, incident_id: str) -> Optional[OnCallIncident]:
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM oncall_incidents WHERE incident_id = ?",
                (incident_id,)
            ).fetchone()
            if not row:
                return None
            return OnCallIncident(
                incident_id=row["incident_id"],
                title=row["title"],
                source=row["source"],
                severity=row["severity"],
                incident_class=row["incident_class"],
                confidence=row["confidence"],
                correlation_key=row["correlation_key"],
                reproduction_cmd=row["reproduction_cmd"],
                status=row["status"],
                raw_details=json.loads(row["raw_details"]),
                created_at=row["created_at"],
                updated_at=row["updated_at"]
            )

    def find_active_by_correlation(self, correlation_key: str) -> Optional[OnCallIncident]:
        with self._get_connection() as conn:
            row = conn.execute("""
                SELECT * FROM oncall_incidents
                WHERE correlation_key = ?
                  AND status NOT IN ('RESOLVED', 'REJECTED')
                ORDER BY created_at DESC LIMIT 1
            """, (correlation_key,)).fetchone()
            if not row:
                return None
            return OnCallIncident(
                incident_id=row["incident_id"],
                title=row["title"],
                source=row["source"],
                severity=row["severity"],
                incident_class=row["incident_class"],
                confidence=row["confidence"],
                correlation_key=row["correlation_key"],
                reproduction_cmd=row["reproduction_cmd"],
                status=row["status"],
                raw_details=json.loads(row["raw_details"]),
                created_at=row["created_at"],
                updated_at=row["updated_at"]
            )

    def allocate_epoch(self, incident_id: str) -> int:
        """Atomically increment and return the monotonic epoch token for an incident."""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO oncall_incident_epochs (incident_id, current_epoch)
                VALUES (?, 1)
                ON CONFLICT(incident_id) DO UPDATE SET current_epoch = current_epoch + 1
            """, (incident_id,))
            row = conn.execute(
                "SELECT current_epoch FROM oncall_incident_epochs WHERE incident_id = ?",
                (incident_id,)
            ).fetchone()
            return int(row["current_epoch"])

    def get_current_epoch(self, incident_id: str) -> int:
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT current_epoch FROM oncall_incident_epochs WHERE incident_id = ?",
                (incident_id,)
            ).fetchone()
            return int(row["current_epoch"]) if row else 0

    def save_claim(self, claim: RemediationClaim, expected_epoch: Optional[int] = None) -> None:
        """Save claim, enforcing monotonic epoch fencing to reject stale workers."""
        with self._get_connection() as conn:
            curr_epoch_row = conn.execute(
                "SELECT current_epoch FROM oncall_incident_epochs WHERE incident_id = ?",
                (claim.incident_id,)
            ).fetchone()
            curr_epoch = int(curr_epoch_row["current_epoch"]) if curr_epoch_row else 0

            if expected_epoch is not None and expected_epoch != curr_epoch:
                raise EpochFencingError(
                    f"Fencing collision for incident {claim.incident_id}: "
                    f"worker epoch {expected_epoch} does not match current epoch {curr_epoch}"
                )

            if claim.epoch < curr_epoch:
                raise EpochFencingError(
                    f"Stale claim {claim.claim_id}: epoch {claim.epoch} < current epoch {curr_epoch}"
                )

            try:
                conn.execute("""
                    INSERT INTO oncall_claims (
                        claim_id, incident_id, epoch, claimant_lane,
                        worktree_path, worktree_branch, state,
                        candidate_sha256, git_tree_hash, test_proofs_hash,
                        reviewer_lane, reviewer_verdict, review_explanation,
                        pr_branch, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(claim_id) DO UPDATE SET
                        state=excluded.state,
                        candidate_sha256=excluded.candidate_sha256,
                        git_tree_hash=excluded.git_tree_hash,
                        test_proofs_hash=excluded.test_proofs_hash,
                        reviewer_lane=excluded.reviewer_lane,
                        reviewer_verdict=excluded.reviewer_verdict,
                        review_explanation=excluded.review_explanation,
                        pr_branch=excluded.pr_branch,
                        updated_at=excluded.updated_at
                """, (
                    claim.claim_id, claim.incident_id, claim.epoch, claim.claimant_lane,
                    claim.worktree_path, claim.worktree_branch, claim.state,
                    claim.candidate_sha256, claim.git_tree_hash, claim.test_proofs_hash,
                    claim.reviewer_lane, claim.reviewer_verdict, claim.review_explanation,
                    claim.pr_branch, claim.created_at, claim.updated_at
                ))
            except sqlite3.IntegrityError as err:
                raise DuplicateClaimError(
                    f"Incident {claim.incident_id} already has an active implementer claim"
                ) from err

    def get_active_claim_for_incident(self, incident_id: str) -> Optional[str]:
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT claim_id FROM oncall_claims WHERE incident_id = ? "
                "AND state NOT IN ('ACTIVATED', 'FAILED')",
                (incident_id,),
            ).fetchone()
            return row["claim_id"] if row else None

    def supersede_active_claims(self, incident_id: str) -> None:
        """Mark active claims FAILED (explicit takeover); the new epoch fences them out."""
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE oncall_claims SET state = 'FAILED', updated_at = ? "
                "WHERE incident_id = ? AND state NOT IN ('ACTIVATED', 'FAILED')",
                (datetime.now(timezone.utc).isoformat(), incident_id),
            )

    def get_claim(self, claim_id: str) -> Optional[RemediationClaim]:
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM oncall_claims WHERE claim_id = ?",
                (claim_id,)
            ).fetchone()
            if not row:
                return None
            return RemediationClaim(
                claim_id=row["claim_id"],
                incident_id=row["incident_id"],
                epoch=row["epoch"],
                claimant_lane=row["claimant_lane"],
                worktree_path=row["worktree_path"],
                worktree_branch=row["worktree_branch"],
                state=row["state"],
                candidate_sha256=row["candidate_sha256"],
                git_tree_hash=row["git_tree_hash"],
                test_proofs_hash=row["test_proofs_hash"],
                reviewer_lane=row["reviewer_lane"],
                reviewer_verdict=row["reviewer_verdict"],
                review_explanation=row["review_explanation"],
                pr_branch=row["pr_branch"],
                created_at=row["created_at"],
                updated_at=row["updated_at"]
            )

    def list_active_claims(self) -> List[RemediationClaim]:
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM oncall_claims
                WHERE state NOT IN ('ACTIVATED', 'FAILED')
                ORDER BY created_at DESC
            """).fetchall()
            return [
                RemediationClaim(
                    claim_id=r["claim_id"],
                    incident_id=r["incident_id"],
                    epoch=r["epoch"],
                    claimant_lane=r["claimant_lane"],
                    worktree_path=r["worktree_path"],
                    worktree_branch=r["worktree_branch"],
                    state=r["state"],
                    candidate_sha256=r["candidate_sha256"],
                    git_tree_hash=r["git_tree_hash"],
                    test_proofs_hash=r["test_proofs_hash"],
                    reviewer_lane=r["reviewer_lane"],
                    reviewer_verdict=r["reviewer_verdict"],
                    review_explanation=r["review_explanation"],
                    pr_branch=r["pr_branch"],
                    created_at=r["created_at"],
                    updated_at=r["updated_at"]
                ) for r in rows
            ]

    def count_summary(self) -> Dict[str, int]:
        with self._get_connection() as conn:
            inc_total = conn.execute("SELECT COUNT(*) FROM oncall_incidents").fetchone()[0]
            inc_resolved = conn.execute("SELECT COUNT(*) FROM oncall_incidents WHERE status = 'RESOLVED'").fetchone()[0]
            claims_active = conn.execute("SELECT COUNT(*) FROM oncall_claims WHERE state NOT IN ('ACTIVATED', 'FAILED')").fetchone()[0]
            prs_staged = conn.execute("SELECT COUNT(*) FROM oncall_claims WHERE state IN ('PR_STAGED', 'AWAIT_OPERATOR')").fetchone()[0]
            awaiting = conn.execute("SELECT COUNT(*) FROM oncall_claims WHERE state = 'AWAITING_REVIEW'").fetchone()[0]
            pending_pr = conn.execute("SELECT COUNT(*) FROM oncall_claims WHERE state = 'PENDING_PR'").fetchone()[0]
            return {
                "awaiting_review": awaiting,
                "pending_pr": pending_pr,
                "total_incidents": inc_total,
                "resolved_incidents": inc_resolved,
                "active_claims": claims_active,
                "staged_prs": prs_staged
            }


# ─────────────────────────────────────────────────────────────────────────────
# Daemon Engine Core
# ─────────────────────────────────────────────────────────────────────────────

class OnCallDaemonEngine:
    """Core Autonomous On-Call Incident Daemon Engine."""

    def __init__(
        self,
        repo_root: Optional[Path] = None,
        state_dir: Optional[Path] = None,
        confidence_threshold: float = 0.70
    ) -> None:
        self.repo_root = (repo_root or _DEFAULT_REPO_ROOT).resolve()
        self.state_dir = (state_dir or _DEFAULT_STATE_DIR).resolve()
        self.confidence_threshold = confidence_threshold
        self.storage = OnCallStorage(self.state_dir / "oncall.db")

    def admit_incident(
        self,
        triage_record: Union[Any, Dict[str, Any]]
    ) -> Optional[OnCallIncident]:
        """Evaluate triage record and admit if actionable, confident, and not deduplicated."""
        if hasattr(triage_record, "incident_id"):
            raw = {
                "incident_id": getattr(triage_record, "incident_id", ""),
                "source": getattr(triage_record, "source", "unknown"),
                "severity": str(getattr(triage_record, "severity", "NOISE")).upper(),
                "incident_class": str(getattr(triage_record, "incident_class", "CRASH")).upper(),
                "confidence": float(getattr(triage_record, "confidence", 0.0)),
                "correlation_key": getattr(triage_record, "correlation_key", ""),
                "actionable": bool(getattr(triage_record, "actionable", False)),
                "summary": getattr(triage_record, "summary", ""),
                "reproduction_cmd": getattr(triage_record, "reproduction_cmd", None),
            }
        else:
            raw = dict(triage_record)
            raw["severity"] = str(raw.get("severity", "NOISE")).upper()
            raw["incident_class"] = str(raw.get("incident_class", "CRASH")).upper()
            raw["confidence"] = float(raw.get("confidence", 0.0))
            raw["actionable"] = bool(raw.get("actionable", False))

        # Check actionability and confidence threshold
        if not raw["actionable"]:
            logger.debug("Filtered out: not actionable (%s)", raw.get("incident_id"))
            return None

        if raw["confidence"] < self.confidence_threshold:
            logger.info(
                "Filtered out: confidence %.2f < threshold %.2f",
                raw["confidence"], self.confidence_threshold
            )
            return None

        if raw["severity"] not in {"CRITICAL", "HIGH", "MEDIUM"}:
            logger.info("Filtered out: severity %s not eligible for autonomous wakeup", raw["severity"])
            return None

        # Check correlation deduplication
        correlation_key = raw.get("correlation_key") or f"{raw['source']}:{raw['incident_class']}"
        existing = self.storage.find_active_by_correlation(correlation_key)
        if existing:
            logger.info("Deduplicated: incident %s already active for key %s", existing.incident_id, correlation_key)
            return None

        now_iso = datetime.now(timezone.utc).isoformat()
        incident_id = raw.get("incident_id") or f"oncall-inc-{hashlib.sha256(now_iso.encode()).hexdigest()[:12]}"
        title = raw.get("summary") or f"Incident in {raw.get('source', 'unknown')}"

        incident = OnCallIncident(
            incident_id=incident_id,
            title=title,
            source=raw.get("source", "unknown"),
            severity=raw["severity"],
            incident_class=raw["incident_class"],
            confidence=raw["confidence"],
            correlation_key=correlation_key,
            reproduction_cmd=raw.get("reproduction_cmd"),
            status="ADMITTED",
            raw_details=raw,
            created_at=now_iso,
            updated_at=now_iso
        )
        try:
            self.storage.save_incident(incident)
        except sqlite3.IntegrityError:
            # Lost a race: unique index on active correlation_key already holds a twin.
            logger.info("Deduplicated (race): active incident exists for key %s", correlation_key)
            return None
        logger.info("Admitted incident %s (severity=%s, class=%s)", incident_id, incident.severity, incident.incident_class)
        return incident

    def claim_incident(
        self,
        incident_id: str,
        claimant_lane: str = "codex",
        takeover: bool = False
    ) -> RemediationClaim:
        """Atomically claim an admitted incident with a monotonic fencing epoch.

        Only one active implementer per incident: a second claim raises
        DuplicateClaimError unless takeover=True, which fails the old claim and
        fences it out via a higher epoch.
        """
        incident = self.storage.get_incident(incident_id)
        if not incident:
            raise ValueError(f"Incident {incident_id} not found")

        active = self.storage.get_active_claim_for_incident(incident_id)
        if active and not takeover:
            raise DuplicateClaimError(f"Incident {incident_id} already claimed by {active}")
        if active:
            self.storage.supersede_active_claims(incident_id)

        epoch = self.storage.allocate_epoch(incident_id)
        now_iso = datetime.now(timezone.utc).isoformat()
        claim_id = f"claim-{incident_id}-{epoch}"

        # Setup isolated worktree path
        delegation_env = os.getenv("AQ_DELEGATION_DIR")
        if delegation_env:
            wt_root = Path(delegation_env).resolve() / "worktrees"
        else:
            wt_root = self.repo_root / ".agents" / "delegation" / "worktrees"
        wt_path = (wt_root / claim_id).resolve()
        wt_branch = f"delegate/{claim_id}"

        # Validate containment
        if not verify_worktree_containment(str(wt_path), self.repo_root):
            raise ContainmentViolationError(f"Path {wt_path} is outside allowed isolation boundary")

        claim = RemediationClaim(
            claim_id=claim_id,
            incident_id=incident_id,
            epoch=epoch,
            claimant_lane=claimant_lane,
            worktree_path=str(wt_path),
            worktree_branch=wt_branch,
            state="ISOLATING",
            created_at=now_iso,
            updated_at=now_iso
        )
        self.storage.save_claim(claim, expected_epoch=epoch)

        incident.status = "CLAIMED"
        incident.updated_at = now_iso
        self.storage.save_incident(incident)

        return claim

    def _release_incident(self, incident_id: str, status: str = "ADMITTED",
                          actor: str = "system", action: str = "release", note: str = "") -> None:
        """Return an incident to a claimable state (never RESOLVED) and audit it."""
        inc = self.storage.get_incident(incident_id)
        if not inc:
            raise ValueError(f"Incident {incident_id} not found")
        now_iso = datetime.now(timezone.utc).isoformat()
        inc.status = status
        inc.updated_at = now_iso
        inc.raw_details.setdefault("operator_actions", []).append(
            {"action": action, "actor": actor, "ts": now_iso, "note": note})
        self.storage.save_incident(inc)

    def _fail_claim(self, claim: RemediationClaim, reason: str) -> None:
        claim.state = "FAILED"
        claim.review_explanation = reason[:500]
        claim.updated_at = datetime.now(timezone.utc).isoformat()
        try:
            self.storage.save_claim(claim, expected_epoch=claim.epoch)
        except EpochFencingError:
            return
        self._release_incident(claim.incident_id, action="claim_failed", note=reason[:200])

    def resolve_incident(self, incident_id: str, actor: str, note: str) -> None:
        """Operator action: mark an incident RESOLVED and close its active claim."""
        self.storage.supersede_active_claims(incident_id)
        self._release_incident(incident_id, status="RESOLVED", actor=actor,
                               action="resolve", note=note)

    def requeue_incident(self, incident_id: str, actor: str, note: str = "") -> None:
        """Operator action: fail the active claim and make the incident claimable again."""
        self.storage.supersede_active_claims(incident_id)
        self._release_incident(incident_id, status="ADMITTED", actor=actor,
                               action="requeue", note=note)

    def create_isolated_worktree(self, claim: RemediationClaim) -> Path:
        """Create the git worktree for a claim. Fails closed: no plain-directory fallback."""
        wt_dir = Path(claim.worktree_path)
        simulate = (os.getenv("AQ_ONCALL_SIMULATE_WORKTREE") == "1"
                    and os.getenv("AQ_ONCALL_TEST_MODE") == "1")  # test-only: needs both markers
        if simulate:
            logger.warning("SIMULATED worktree (plain directory) in use for %s - test mode only",
                           claim.claim_id)
        try:
            wt_dir.parent.mkdir(parents=True, exist_ok=True)
            if simulate:
                wt_dir.mkdir(parents=True, exist_ok=True)
            elif wt_dir.exists():
                if not (wt_dir / ".git").exists():
                    raise WorktreeIsolationError(f"{wt_dir} exists but is not a git worktree")
            else:
                subprocess.run(
                    ["git", "-c", "core.hooksPath=/dev/null", "worktree", "add", "-q",
                     "-b", claim.worktree_branch, str(wt_dir), "HEAD"],
                    cwd=str(self.repo_root),
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=15
                )
        except (subprocess.CalledProcessError, OSError, subprocess.TimeoutExpired,
                WorktreeIsolationError) as err:
            detail = getattr(err, "stderr", None) or str(err)
            self._fail_claim(claim, f"worktree_creation_failed: {detail}")
            raise WorktreeIsolationError(f"Worktree creation failed for {claim.claim_id}: {detail}") from err

        claim.state = "REPRODUCING"
        claim.updated_at = datetime.now(timezone.utc).isoformat()
        self.storage.save_claim(claim, expected_epoch=claim.epoch)
        return wt_dir

    def reproduce_incident(
        self,
        claim: RemediationClaim,
        custom_cmd: Optional[str] = None
    ) -> Dict[str, Any]:
        """Run the reproduction command confined by bubblewrap; refuse (defer) if unavailable."""
        incident = self.storage.get_incident(claim.incident_id)
        cmd = custom_cmd or (incident.reproduction_cmd if incident else None)
        if not cmd:
            return {"reproduced": False, "reason": "no_reproduction_command"}

        wt_path = Path(claim.worktree_path)
        if not wt_path.is_dir() or not verify_worktree_containment(str(wt_path), self.repo_root):
            return {"reproduced": False, "deferred": True, "reason": "no_isolated_worktree"}
        bwrap = shutil.which("bwrap")
        if not bwrap:
            return {"reproduced": False, "deferred": True, "reason": "no_sandbox_available"}

        home = os.environ.get("HOME")
        argv = [bwrap, "--ro-bind", "/", "/", "--dev", "/dev", "--proc", "/proc",
                "--tmpfs", "/tmp"]
        if home:
            argv += ["--tmpfs", home]
        argv += ["--bind", str(wt_path), str(wt_path), "--chdir", str(wt_path),
                 "--unshare-all", "--die-with-parent", "bash", "-c", cmd]

        try:
            res = subprocess.run(
                argv,
                env=scrub_credentials(),
                capture_output=True,
                text=True,
                timeout=30
            )
            return {
                "reproduced": res.returncode != 0,
                "confined": "bwrap",
                "returncode": res.returncode,
                "stdout": res.stdout[:2000],
                "stderr": res.stderr[:2000]
            }
        except Exception as e:
            return {"reproduced": False, "error": str(e)}

    def complete_remediation(
        self,
        claim_id: str,
        git_tree_hash: str,
        test_proofs: str,
        reviewer_lane: Optional[str] = None
    ) -> RemediationClaim:
        """Bind candidate SHA, execute independent review, and stage for operator."""
        claim = self.storage.get_claim(claim_id)
        if not claim:
            raise ValueError(f"Claim {claim_id} not found")

        # 1. Independent reviewer assignment (Rule 18: distinct lane, never self-review).
        # No reviewer integration exists in this engine: the claim stops at
        # AWAITING_REVIEW until record_review() receives a real verdict.
        selected_reviewer = reviewer_lane or (
            "antigravity" if claim.claimant_lane != "antigravity" else "codex"
        )
        if selected_reviewer == claim.claimant_lane:
            raise ReviewIntegrityError(
                f"Rule 18 Violation: Claimant {claim.claimant_lane} cannot self-review. "
                f"Must route to distinct model lane."
            )

        # 2. Candidate SHA Binding
        tree_hash, proofs_hash, candidate_sha = compute_candidate_sha256(
            git_tree_hash, test_proofs
        )
        claim.git_tree_hash = tree_hash
        claim.test_proofs_hash = proofs_hash
        claim.candidate_sha256 = candidate_sha
        claim.state = "REVIEWING"
        claim.updated_at = datetime.now(timezone.utc).isoformat()
        self.storage.save_claim(claim, expected_epoch=claim.epoch)

        claim.reviewer_lane = selected_reviewer
        claim.reviewer_verdict = None
        if not test_proofs or "FAIL" in test_proofs:
            self._fail_claim(claim, "Validation proofs missing or contain failure indicators")
            return claim
        else:
            claim.state = "AWAITING_REVIEW"
            claim.review_explanation = f"awaiting independent review by {selected_reviewer}"
        claim.updated_at = datetime.now(timezone.utc).isoformat()
        self.storage.save_claim(claim, expected_epoch=claim.epoch)
        return claim

    def record_review(
        self,
        claim_id: str,
        reviewer_lane: str,
        verdict: str,
        explanation: str,
        git_tree_hash: str,
        test_proofs: str,
    ) -> RemediationClaim:
        """Record a verdict produced by a real reviewer; verifies binding and independence.

        PASS moves to PENDING_PR (no PR exists yet); the incident is NOT marked resolved.
        """
        claim = self.storage.get_claim(claim_id)
        if not claim:
            raise ValueError(f"Claim {claim_id} not found")
        if claim.state != "AWAITING_REVIEW":
            raise ReviewIntegrityError(f"Claim {claim_id} is {claim.state}, not AWAITING_REVIEW")
        if reviewer_lane == claim.claimant_lane:
            raise ReviewIntegrityError("Rule 18 Violation: reviewer is the claimant")
        if verdict not in {"PASS", "CONCERNS", "REJECTED"}:
            raise ReviewIntegrityError(f"Invalid verdict {verdict!r}")
        if not claim.candidate_sha256 or not verify_candidate_binding(
            claim.candidate_sha256, git_tree_hash, test_proofs
        ):
            raise ReviewIntegrityError("Candidate binding failed: git tree or proofs drifted")

        claim.reviewer_lane = reviewer_lane
        claim.reviewer_verdict = verdict
        claim.review_explanation = explanation
        claim.state = "PENDING_PR" if verdict == "PASS" else "FAILED"
        claim.updated_at = datetime.now(timezone.utc).isoformat()
        self.storage.save_claim(claim, expected_epoch=claim.epoch)
        if claim.state == "FAILED":
            self._release_incident(claim.incident_id, action="review_rejected", note=explanation[:200])
        return claim

    # ── Heartbeat (written only by the running daemon loop) ──────────────────

    @property
    def heartbeat_path(self) -> Path:
        return self.state_dir / "heartbeat.json"

    def write_heartbeat(self, loop_count: int = 0) -> None:
        payload = {"ts": datetime.now(timezone.utc).isoformat(), "pid": os.getpid(),
                   "loop_count": loop_count}
        self.state_dir.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(self.state_dir), prefix=".hb-")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh)
        os.replace(tmp, self.heartbeat_path)

    def read_heartbeat(self) -> Dict[str, Any]:
        """Return {"state": alive|stale|unknown, "last_heartbeat", "age_s"} from the daemon's file."""
        stale_after = float(os.getenv("AQ_ONCALL_HEARTBEAT_STALE_S", "120"))
        try:
            data = json.loads(self.heartbeat_path.read_text(encoding="utf-8"))
            ts = datetime.fromisoformat(data["ts"])
            age = (datetime.now(timezone.utc) - ts).total_seconds()
        except (OSError, ValueError, KeyError, TypeError):
            return {"state": "unknown", "last_heartbeat": None, "age_s": None}
        return {"state": "alive" if age <= stale_after else "stale",
                "last_heartbeat": data["ts"], "age_s": round(age, 1), "pid": data.get("pid")}

    def run_daemon(
        self,
        triage_engine: Optional[Any] = None,
        interval: float = 30.0,
        max_iterations: Optional[int] = None,
        limit: int = 10,
    ) -> int:
        """Long-running loop: heartbeat, then one intake pass, every `interval` seconds."""
        n = 0
        while max_iterations is None or n < max_iterations:
            n += 1
            self.write_heartbeat(loop_count=n)
            try:
                self.run_once(triage_engine=triage_engine, limit=limit)
            except Exception:  # keep the loop alive; the failure is logged
                logger.exception("oncalld pass failed")
            if max_iterations is None or n < max_iterations:
                time.sleep(interval)
        return n

    def health_summary(self) -> Dict[str, Any]:
        """Return engine health metrics and active remediation counts."""
        counts = self.storage.count_summary()
        active = self.storage.list_active_claims()
        hb = self.read_heartbeat()
        if hb["state"] == "unknown":
            status = "unverified"
        elif hb["state"] == "stale":
            status = "stale"
        else:
            status = "healthy" if counts["active_claims"] == 0 else "remediating"
        return {
            "available": True,
            "status": "degraded" if self.storage._fallback_memory else status,
            "storage_fallback_memory": self.storage._fallback_memory,
            "heartbeat_status": status,
            "heartbeat": hb,
            "awaiting_review": counts["awaiting_review"],
            "pending_pr": counts["pending_pr"],
            "engine": "OnCallDaemonEngine",
            "version": "1.1.0",
            "confidence_threshold": self.confidence_threshold,
            "total_incidents": counts["total_incidents"],
            "resolved_incidents": counts["resolved_incidents"],
            "active_claims": counts["active_claims"],
            "staged_prs": counts["staged_prs"],
            "active_claim_ids": [c.claim_id for c in active],
            "last_heartbeat": hb["last_heartbeat"],
        }

    def run_once(
        self,
        triage_engine: Optional[Any] = None,
        limit: int = 10
    ) -> List[RemediationClaim]:
        """Execute a single scan-and-remediate cycle."""
        processed_claims: List[RemediationClaim] = []
        if triage_engine is not None and hasattr(triage_engine, "ingest_live_journal"):
            records = triage_engine.ingest_live_journal(limit=limit)
            for rec in records:
                if not getattr(rec, "actionable", False):
                    continue
                incident = self.admit_incident(rec)
                if incident:
                    lane = getattr(rec, "suggested_lane", "codex") or "codex"
                    try:
                        claim = self.claim_incident(incident.incident_id, claimant_lane=lane)
                        self.create_isolated_worktree(claim)
                    except (DuplicateClaimError, WorktreeIsolationError) as err:
                        logger.warning("Skipping incident %s: %s", incident.incident_id, err)
                        continue
                    processed_claims.append(claim)
        return processed_claims


def health_summary(
    state_dir: Optional[Path] = None,
    repo_root: Optional[Path] = None
) -> Dict[str, Any]:
    """Module-level health summary accessor for dashboard and aq-qa."""
    engine = OnCallDaemonEngine(repo_root=repo_root, state_dir=state_dir)
    return engine.health_summary()
