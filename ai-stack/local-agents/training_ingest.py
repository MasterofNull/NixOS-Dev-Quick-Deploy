#!/usr/bin/env python3
"""
training_ingest.py — Telemetry → fine-tuning dataset pipeline.

Reads the three dormant telemetry streams that have accumulated data but never
produced fine-tuning samples (learning stats show 0 patterns learned):

  • hybrid-events.jsonl  (352k+ events — successful completions → training pairs)
  • delegation-feedback.jsonl (failure analysis → negative examples + gap patterns)
  • optimization_proposals.jsonl (auto-approves safe proposals e.g. iteration limit bumps)

Writes structured JSONL samples to the fine-tuning dataset so the local model
can learn from its own production traffic.

Usage (standalone):
    python3 training_ingest.py [--dry-run] [--hours N] [--min-quality 0.7]

Usage (as module):
    from training_ingest import TrainingIngestor
    ingestor = TrainingIngestor()
    report = ingestor.run(hours=24)
    print(report)
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ── paths ─────────────────────────────────────────────────────────────────────

_SCRIPT_DIR = Path(__file__).resolve().parent
# Use REPO_ROOT env var (set by systemd unit) so writes go to the live repo,
# not the Nix store copy which is read-only (OSError EROFS).
_REPO_ROOT = Path(os.environ["REPO_ROOT"]) if "REPO_ROOT" in os.environ else _SCRIPT_DIR.parent.parent

# Prefer harness_paths for canonical path resolution; fall back to legacy env-var logic.
try:
    import sys as _sys
    _sys.path.insert(0, str(_SCRIPT_DIR))
    from harness_paths import (  # noqa: E402
        TELEMETRY_DIR,
        DELEGATION_FEEDBACK,
        HYBRID_EVENTS,
        OPTIMIZATION_PROPOSALS,
        USER_EVENTS_SPOOL,
        DATASET as FINE_TUNING_DATASET,
    )
    _sys.path.pop(0)
except ImportError:
    TELEMETRY_DIR = Path(os.getenv("TELEMETRY_DIR", "/var/lib/ai-stack/hybrid/telemetry"))
    FINE_TUNING_DATASET = Path(os.getenv("FINE_TUNING_DATASET", "/var/lib/ai-stack/hybrid/fine-tuning/dataset.jsonl"))
    OPTIMIZATION_PROPOSALS = TELEMETRY_DIR / "optimization_proposals.jsonl"
    DELEGATION_FEEDBACK    = TELEMETRY_DIR / "delegation-feedback.jsonl"
    HYBRID_EVENTS          = TELEMETRY_DIR / "hybrid-events.jsonl"
    USER_EVENTS_SPOOL = _REPO_ROOT / ".agents" / "telemetry" / "hybrid-events.jsonl"

# P1: labeled failure samples written by training_capture.capture_failure. Defined
# UNCONDITIONALLY (both try/except branches above set TELEMETRY_DIR + _REPO_ROOT).
TRAINING_SAMPLES       = TELEMETRY_DIR / "training-samples.jsonl"
TRAINING_SAMPLES_SPOOL = _REPO_ROOT / ".agents" / "telemetry" / "training-samples.jsonl"

# HITL poison guard: a teacher-corrected repair pair must be APPROVED (aq-review-repairs) before it can
# enter the training dataset — a bad correction would otherwise train the model on wrong behaviour.
#   review_status == "approved" -> ingests · "rejected" -> never · missing/"pending" -> waits for review
# Set AQ_REPAIR_REQUIRE_APPROVAL=0 for fully-autonomous ingest (gate off, e.g. a trusted-teacher run).
_REQUIRE_REPAIR_APPROVAL = os.getenv("AQ_REPAIR_REQUIRE_APPROVAL", "1").strip().lower() not in (
    "0", "false", "no", "off",
)

# PII guard: strip actual secrets (API keys, tokens) from training content before
# quality scoring or writing. Uses redact_secrets (not scrub_telemetry_payload —
# that hashes the entire field, destroying training signal).
try:
    _SHARED_PATH = str(_SCRIPT_DIR.parent / "mcp-servers")
    if _SHARED_PATH not in sys.path:
        sys.path.insert(0, _SHARED_PATH)
    from shared.telemetry_privacy import redact_secrets as _redact_secrets  # noqa: E402

    def _scrub_text(text: str) -> str:
        cleaned, _ = _redact_secrets(text)
        return cleaned
except ImportError:
    def _scrub_text(text: str) -> str:  # type: ignore[misc]
        return text

# ── quality thresholds ────────────────────────────────────────────────────────

# Events with latency below this are likely cached/trivial — skip as training signal.
MIN_LATENCY_MS = 500.0
# Minimum keyword-coverage score to accept a completion as a positive training sample.
DEFAULT_MIN_QUALITY = 0.65
# How many tokens a response needs to be considered non-trivial.
MIN_RESPONSE_TOKENS = 20
# Auto-approve iteration-limit proposals up to this multiplier (safe).
MAX_SAFE_LIMIT_MULTIPLIER = 1.5

# ── helpers ───────────────────────────────────────────────────────────────────

def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _parse_ts(ts_str) -> Optional[datetime]:
    """Parse ISO-8601 string or Unix float/int timestamp. Return None on failure."""
    if not ts_str:
        return None
    # Health-spider and some telemetry producers emit Unix float timestamps.
    if isinstance(ts_str, (int, float)):
        try:
            return datetime.fromtimestamp(float(ts_str), tz=timezone.utc)
        except (OSError, OverflowError, ValueError):
            return None
    try:
        # Python 3.7+ fromisoformat handles most ISO-8601 but not trailing Z.
        # Some producers emit +00:00Z (double suffix) — strip trailing Z first.
        ts_clean = str(ts_str)
        ts_clean = ts_clean.replace("+00:00Z", "+00:00")
        ts_clean = ts_clean.replace("Z", "+00:00")
        return datetime.fromisoformat(ts_clean)
    except ValueError:
        return None


def _read_jsonl(path: Path, since: Optional[datetime] = None) -> List[Dict]:
    """Read JSONL file, optionally filtering to entries newer than `since`."""
    if not path.exists():
        return []
    entries = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            raw = raw.strip()
            if not raw:
                continue
            try:
                entry = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if since is not None:
                ts = _parse_ts(entry.get("timestamp", ""))
                if ts is None or ts < since:
                    continue
            entries.append(entry)
    return entries


def _token_count(text: str) -> int:
    """Rough token estimate: ~4 chars per token."""
    return max(1, len(text) // 4)


_STRUCTURED_MARKERS = (
    "```", "def ", "class ", "import ", "return ", "function ",
    "## ", "### ", "1. ", "2. ", "- [", "* ", "| ",  # markdown / lists
    '"function"', '"arguments"',  # JSON tool-call blobs from agent_step_complete
    "COMPLETED:",  # agent synthesis guard output — verified task completion sentence
    '{"success": true',   # short tool result JSON (success path)
    '{"result":',         # tool result JSON wrapper
)


def _quality_score(response: str, query: str) -> float:
    """
    Quality signal: length + query-term coverage, code/structure-aware.
    Returns 0.0–1.0.  Not ML — a heuristic gate to reject junk.

    Keyword coverage is a poor signal for code or structured analytical
    responses (agent tasks) — they don't repeat query terms verbatim.
    For those, weight response length and structure instead.
    """
    if not response or not query:
        return 0.0
    resp_lower = response.lower()
    query_tokens = [t for t in query.lower().split() if len(t) > 3]
    if not query_tokens:
        coverage = 0.5
    else:
        covered = sum(1 for t in query_tokens if t in resp_lower)
        coverage = covered / len(query_tokens)
    # Boost for longer, substantive responses (up to ~2k chars).
    length_bonus = min(0.3, len(response) / 6000.0)
    # Structured/code/analytical content doesn't repeat query vocabulary.
    # Multi-line prose (>5 newlines) is also likely structured agent output.
    is_structured = (
        any(m in response for m in _STRUCTURED_MARKERS)
        or response.count("\n") > 5
    )
    if is_structured:
        # Structured/code/agent outputs score 0.50 base — higher than prose
        # with zero coverage, since they typically don't repeat query terms.
        return min(1.0, 0.50 + length_bonus + coverage * 0.30)
    return min(1.0, coverage * 0.7 + length_bonus)


def _is_useful_hybrid_event(event: Dict) -> bool:
    """Return True for events that represent a completed successful inference."""
    etype = event.get("event_type", "")
    if etype not in ("inference_complete", "chat_completion", "hybrid_completion",
                     "local_inference", "agent_step_complete", "tool_result"):
        return False
    # tool_result events must explicitly succeed; other events use absence-of-error signal.
    if etype == "tool_result" and not event.get("success", False):
        return False
    if event.get("error") or event.get("success") is False:
        return False
    # tool_result latency reflects tool execution speed, not inference quality.
    # Skip the latency gate for tool_result — tools complete in <500ms by design.
    if etype != "tool_result":
        latency = event.get("latency_ms", 0.0)
        if latency < MIN_LATENCY_MS:
            return False
    return True


# ── ingestor ─────────────────────────────────────────────────────────────────

class TrainingIngestor:
    """
    Reads production telemetry and extracts training samples for the local model.

    Three sources:
      1. hybrid-events.jsonl → positive training pairs (query → high-quality response)
      2. delegation-feedback.jsonl → failure patterns + negative/gap examples
      3. optimization_proposals.jsonl → auto-approves safe iteration-limit proposals
    """

    def __init__(
        self,
        dataset_path: Path = FINE_TUNING_DATASET,
        min_quality: float = DEFAULT_MIN_QUALITY,
        dry_run: bool = False,
    ):
        self.dataset_path = dataset_path
        self.min_quality = min_quality
        self.dry_run = dry_run

    # ── public ───────────────────────────────────────────────────────────────

    def run(self, hours: int = 24) -> Dict[str, Any]:
        """
        Execute a full ingest cycle.

        Returns a summary dict with counts and actionable findings.
        """
        since = _now_utc() - timedelta(hours=hours)
        report: Dict[str, Any] = {
            "timestamp": _now_utc().isoformat(),
            "hours_window": hours,
            "dry_run": self.dry_run,
            "positive_samples_added": 0,
            "gap_patterns": [],
            "failure_summary": {},
            "proposals_auto_approved": [],
            "proposals_needing_review": [],
            "dataset_total": self._count_dataset(),
        }

        report["positive_samples_added"] = self._ingest_hybrid_events(since)
        # P1: turn captured local failures into repair training pairs (closed loop).
        repair_added, repair_pending, repair_pending_review = self._ingest_failure_samples(since)
        report["failure_repair_samples_added"] = repair_added
        report["failure_repair_pending"] = repair_pending
        report["failure_repair_pending_review"] = repair_pending_review
        report["samples_added"] = report["positive_samples_added"] + repair_added
        gaps, failures = self._analyze_delegation_feedback(since)
        report["gap_patterns"] = gaps
        report["failure_summary"] = failures
        approved, review = self._process_proposals(since)
        report["proposals_auto_approved"] = approved
        report["proposals_needing_review"] = review
        report["dataset_total"] = self._count_dataset()

        return report

    # ── private ──────────────────────────────────────────────────────────────

    def _count_dataset(self) -> int:
        if not self.dataset_path.exists():
            return 0
        return sum(1 for _ in open(self.dataset_path, encoding="utf-8", errors="replace"))

    def _ingest_hybrid_events(self, since: datetime) -> int:
        """Extract positive training pairs from hybrid-events.jsonl.

        Reads both the service telemetry file and the user-space spool written
        by delegate-to-local (DirectRunner) when the service dir isn't writable.
        """
        events = _read_jsonl(HYBRID_EVENTS, since=since)
        if USER_EVENTS_SPOOL.exists():
            events = events + _read_jsonl(USER_EVENTS_SPOOL, since=since)
        added = 0

        self.dataset_path.parent.mkdir(parents=True, exist_ok=True)

        existing_hashes: set = set()
        if self.dataset_path.exists():
            for raw in open(self.dataset_path, encoding="utf-8", errors="replace"):
                try:
                    e = json.loads(raw)
                    existing_hashes.add(e.get("source_hash", ""))
                except json.JSONDecodeError:
                    pass

        samples_to_write: List[Dict] = []
        for event in events:
            if not _is_useful_hybrid_event(event):
                continue

            query = (
                event.get("query") or event.get("prompt") or
                event.get("task") or event.get("input", "")
            )
            response = (
                event.get("response") or event.get("output") or
                event.get("result") or event.get("content", "")
            )
            if not query or not response:
                continue
            if _token_count(response) < MIN_RESPONSE_TOKENS:
                continue

            # PII guard: strip secrets from content before scoring or writing.
            response = _scrub_text(response)
            query = _scrub_text(query)

            score = _quality_score(response, query)
            # agent_step_complete: verified DirectRunner outputs — lower floor acceptable.
            # tool_result: success is binary (bool flag); lower floor acceptable.
            etype = event.get("event_type")
            if etype == "agent_step_complete":
                floor = 0.40
            elif etype == "tool_result":
                floor = 0.35
            else:
                floor = self.min_quality
            if score < floor:
                continue

            # Deduplicate by content hash.
            import hashlib
            content_hash = hashlib.sha256(f"{query}||{response}".encode()).hexdigest()[:16]
            if content_hash in existing_hashes:
                continue
            existing_hashes.add(content_hash)

            sample = {
                "messages": [
                    {"role": "user", "content": query},
                    {"role": "assistant", "content": response},
                ],
                "source": event.get("event_type", "hybrid-events"),
                "source_hash": content_hash,
                "quality_score": round(score, 3),
                "latency_ms": event.get("latency_ms"),
                "profile": event.get("profile"),
                "timestamp": event.get("timestamp"),
            }
            samples_to_write.append(sample)

        if samples_to_write and not self.dry_run:
            with open(self.dataset_path, "a", encoding="utf-8") as fh:
                for s in samples_to_write:
                    fh.write(json.dumps(s) + "\n")
            added = len(samples_to_write)
        elif samples_to_write:
            added = len(samples_to_write)  # dry-run: count but don't write

        return added

    def _ingest_failure_samples(self, since: datetime) -> Tuple[int, int, int]:
        """P1: turn captured local failures (training_capture spool) into training data.

        A failure record WITH a corrected_output becomes an SFT repair pair (prompt → correct output),
        so the model learns the right response for the case it got wrong — this is the closed-loop's
        producer-fix-as-training-signal. A record WITHOUT a correction is counted as repair_pending
        (it needs a correction pass — a remote agent's fix — before it can train). A CORRECTED record
        that has not been approved by the HITL gate (aq-review-repairs) is counted as pending_review
        and NOT ingested (poison guard). Returns (repair_samples_added, repair_pending, pending_review).
        Dedupes against the dataset by content hash."""
        import hashlib

        records = _read_jsonl(TRAINING_SAMPLES, since=since)
        if TRAINING_SAMPLES_SPOOL.exists():
            records = records + _read_jsonl(TRAINING_SAMPLES_SPOOL, since=since)

        self.dataset_path.parent.mkdir(parents=True, exist_ok=True)
        existing_hashes: set = set()
        if self.dataset_path.exists():
            for raw in open(self.dataset_path, encoding="utf-8", errors="replace"):
                try:
                    existing_hashes.add(json.loads(raw).get("source_hash", ""))
                except json.JSONDecodeError:
                    pass

        samples_to_write: List[Dict] = []
        pending = 0
        pending_review = 0
        for rec in records:
            kind = rec.get("kind")
            prompt = _scrub_text(rec.get("prompt", ""))
            if not prompt:
                continue
            if kind == "success_sample":
                # Positive pair captured at the completion point (reliable source vs mining hybrid-events).
                target_out = _scrub_text(rec.get("good_output", ""))
                source = f"success-capture:{rec.get('source', 'local')}"
            elif kind == "failure_sample":
                corrected = rec.get("corrected_output")
                if not corrected:
                    pending += 1  # needs a correction before it can be an SFT pair
                    continue
                # HITL poison guard: only an APPROVED repair pair may train. rejected -> drop;
                # missing/pending -> hold for aq-review-repairs. Gate off => treat as approved.
                if _REQUIRE_REPAIR_APPROVAL:
                    review = str(rec.get("review_status", "") or "").strip().lower()
                    if review == "rejected":
                        continue
                    if review != "approved":
                        pending_review += 1
                        continue
                target_out = _scrub_text(corrected)
                source = f"failure-repair:{rec.get('failure_class', 'unknown')}"
            else:
                continue
            if not target_out:
                continue
            content_hash = hashlib.sha256(f"{prompt}||{target_out}".encode()).hexdigest()[:16]
            if content_hash in existing_hashes:
                continue
            existing_hashes.add(content_hash)
            samples_to_write.append({
                "messages": [
                    {"role": "user", "content": prompt},
                    {"role": "assistant", "content": target_out},
                ],
                "source": source,
                "source_hash": content_hash,
                "quality_score": 1.0,
                "timestamp": rec.get("timestamp"),
            })

        added = 0
        if samples_to_write and not self.dry_run:
            with open(self.dataset_path, "a", encoding="utf-8") as fh:
                for s in samples_to_write:
                    fh.write(json.dumps(s) + "\n")
            added = len(samples_to_write)
        elif samples_to_write:
            added = len(samples_to_write)
        return added, pending, pending_review

    def _analyze_delegation_feedback(
        self, since: datetime
    ) -> Tuple[List[Dict], Dict[str, int]]:
        """
        Analyze delegation-feedback.jsonl for failure patterns and gap signals.

        Returns:
            gap_patterns: list of {task_type, pattern, count, example_task}
            failure_summary: {failure_class: count}
        """
        entries = _read_jsonl(DELEGATION_FEEDBACK, since=since)
        failure_counts: Dict[str, int] = {}
        gap_map: Dict[str, Dict] = {}

        for entry in entries:
            fclass = entry.get("failure_class", "unknown")
            failure_counts[fclass] = failure_counts.get(fclass, 0) + 1

            # Extract gap patterns from improvement_actions field.
            for action in entry.get("improvement_actions", []):
                key = action[:80]  # deduplicate by first 80 chars
                if key not in gap_map:
                    gap_map[key] = {
                        "pattern": action,
                        "count": 0,
                        "example_task": entry.get("task_excerpt", ""),
                        "failure_class": fclass,
                    }
                gap_map[key]["count"] += 1

        # Return top 10 gaps by frequency.
        top_gaps = sorted(gap_map.values(), key=lambda x: x["count"], reverse=True)[:10]
        return top_gaps, failure_counts

    def _process_proposals(
        self, since: datetime
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        Read optimization_proposals.jsonl and auto-approve safe proposals.

        Safe = iteration_limit_increase up to MAX_SAFE_LIMIT_MULTIPLIER.
        Everything else goes to needs_review list.
        """
        proposals = _read_jsonl(OPTIMIZATION_PROPOSALS, since=None)  # all time
        pending = [p for p in proposals if p.get("status") == "pending"]

        auto_approved: List[Dict] = []
        needs_review: List[Dict] = []

        for p in pending:
            ptype = p.get("proposal_type", "")
            if ptype == "iteration_limit_increase":
                evidence = p.get("evidence", {})
                current = evidence.get("adaptive_limit", 1)
                recommended_increase = 0.25  # "25%" from rationale
                new_limit = current * (1 + recommended_increase)
                if new_limit / max(current, 1) <= MAX_SAFE_LIMIT_MULTIPLIER:
                    auto_approved.append({
                        "proposal_id": p.get("proposal_id"),
                        "type": ptype,
                        "rationale": p.get("rationale"),
                        "evidence": evidence,
                    })
                    # Mark as approved in the proposals file.
                    if not self.dry_run:
                        self._mark_proposal(p.get("proposal_id"), "auto_approved")
                    continue
            needs_review.append({
                "proposal_id": p.get("proposal_id"),
                "type": ptype,
                "title": p.get("title"),
                "rationale": p.get("rationale"),
            })

        return auto_approved, needs_review

    def _mark_proposal(self, proposal_id: Optional[str], new_status: str) -> None:
        """Update a proposal's status in optimization_proposals.jsonl."""
        if not proposal_id or not OPTIMIZATION_PROPOSALS.exists():
            return
        lines: List[str] = []
        with open(OPTIMIZATION_PROPOSALS, encoding="utf-8", errors="replace") as fh:
            for raw in fh:
                raw = raw.rstrip("\n")
                try:
                    entry = json.loads(raw)
                    if entry.get("proposal_id") == proposal_id:
                        entry["status"] = new_status
                        raw = json.dumps(entry)
                except json.JSONDecodeError:
                    pass
                lines.append(raw)
        with open(OPTIMIZATION_PROPOSALS, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")


# ── prompt extensions export ──────────────────────────────────────────────────

PROMPT_EXTENSIONS_FILE = _REPO_ROOT / "config" / "harness-prompt-extensions.yaml"
# Volatile per-run bookkeeping (last_updated, dataset_size, auto_approved_proposals) is
# written to a GITIGNORED sidecar so the tracked extensions file only changes when the
# actual injected content (rules/routing) changes — no per-run churn, and the file stays
# reviewable. No reader depends on these fields; they are diagnostics only.
PROMPT_EXTENSIONS_META_FILE = _REPO_ROOT / "config" / ".harness-prompt-ext.meta.json"


def generate_prompt_extensions(
    ingest_report: Dict[str, Any],
    extensions_path: Path = PROMPT_EXTENSIONS_FILE,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Convert accumulated training signals into a model-agnostic YAML prompt
    extension file that any new agent or model must load at init time.

    The file is cumulative: existing entries are preserved; new gap patterns
    are appended if they are not already present.

    Returns a summary dict of what was written.
    """
    import hashlib

    existing: Dict[str, Any] = {}
    # Try YAML path first, then JSON sibling — handles runtime without pyyaml.
    _candidates = [extensions_path, extensions_path.with_suffix(".json")]
    for _cand in _candidates:
        if not _cand.exists():
            continue
        try:
            if _cand.suffix == ".json":
                import json as _json
                raw = _json.loads(_cand.read_text()) or {}
            else:
                import yaml as _yaml
                docs = [doc for doc in _yaml.safe_load_all(_cand.read_text()) if isinstance(doc, dict)]
                raw = docs[-1] if docs else {}
            existing = raw if isinstance(raw, dict) else {}
            break  # use first readable file
        except Exception:
            pass  # try next candidate or start fresh

    rules: List[Dict] = existing.get("rules", [])
    existing_patterns = {r.get("pattern", "") for r in rules}
    added = 0

    # Derive rules from gap patterns (recurring improvement actions).
    for gap in ingest_report.get("gap_patterns", []):
        pattern_text = gap.get("pattern", "")
        if not pattern_text or pattern_text in existing_patterns:
            continue
        rule = {
            "pattern": pattern_text,
            "source": "delegation-feedback-gap",
            "count": gap.get("count", 1),
            "failure_class": gap.get("failure_class", ""),
            "example_task": gap.get("example_task", "")[:120],
            "added_at": _now_utc().isoformat(),
        }
        rules.append(rule)
        existing_patterns.add(pattern_text)
        added += 1

    # Summarise failure classes as routing hints.
    failure_hints: List[str] = []
    for fclass, count in ingest_report.get("failure_summary", {}).items():
        if count >= 3:  # only noteworthy recurring failures
            failure_hints.append(f"{fclass} ({count}x in last 24h)")

    # Preserve routing_rules if already set (written by Phase 158+ design tooling)
    _existing_routing_rules: dict = {}
    for _try_path in (extensions_path, extensions_path.with_suffix(".json")):
        if _try_path.exists():
            try:
                import yaml as _yaml
                _existing = _yaml.safe_load(_try_path.read_text(encoding="utf-8"))
            except Exception:
                try:
                    import json as _json
                    _existing = _json.loads(_try_path.read_text(encoding="utf-8"))
                except Exception:
                    _existing = {}
            if isinstance(_existing, dict) and _existing.get("routing_rules"):
                _existing_routing_rules = _existing["routing_rules"]
                break

    # Stable, tracked content — only the injected rules + routing_rules land in the
    # versioned file, so it changes only when that content actually changes. Everything
    # telemetry-derived and rolling (last_updated, dataset_size, routing_hints — a 24h
    # failure snapshot that no reader consumes) goes to the gitignored sidecar to avoid
    # per-run churn.
    extensions = {
        "schema_version": "1.0",
        "instructions": (
            "This file is auto-generated by training_ingest.py (stable content only). "
            "Load it into any new agent or model system prompt via agent_executor.py "
            "_get_system_prompt() or Continue config rules. Do NOT edit manually. "
            "Volatile per-run metadata (last_updated, dataset_size, routing_hints) lives in "
            "the gitignored sidecar config/.harness-prompt-ext.meta.json."
        ),
        "rules": rules,
        "routing_rules": _existing_routing_rules,
    }
    # Volatile bookkeeping — gitignored sidecar, regenerated every run, never committed.
    meta = {
        "schema_version": "1.0",
        "last_updated": _now_utc().isoformat(),
        "dataset_size": ingest_report.get("dataset_total", 0),
        "auto_approved_proposals": len(ingest_report.get("proposals_auto_approved", [])),
        "routing_hints": sorted(failure_hints),
        "total_rules": len(rules),
        "source": str(extensions_path.name),
    }

    if not dry_run:
        import os as _os
        extensions_path.parent.mkdir(parents=True, exist_ok=True)
        # Write via NamedTemporaryFile + atomic replace to prevent concurrent write loss.
        # Fixed .tmp path (_target.suffix + ".tmp" or ".json.tmp") is unsafe when two
        # training_ingest processes run concurrently: process B overwrites A's .tmp before
        # A calls os.replace(), causing A to atomically promote B's partial content.
        # NamedTemporaryFile in the same directory gets a unique path per process.
        import tempfile as _tempfile
        try:
            import yaml as _yaml
            _target = extensions_path
            with _tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=_target.parent, delete=False, suffix=".tmp"
            ) as _fh:
                _fh.write(_yaml.dump(extensions, allow_unicode=True, sort_keys=False))
                _tmp_path = _fh.name
            _os.replace(_tmp_path, _target)
        except ImportError:
            import json as _json
            _target = extensions_path.with_suffix(".json")
            with _tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=_target.parent, delete=False, suffix=".json.tmp"
            ) as _fh:
                _fh.write(_json.dumps(extensions, indent=2))
                _tmp_path = _fh.name
            _os.replace(_tmp_path, _target)

        # Volatile metadata -> gitignored sidecar (atomic). Never dirties the tracked file.
        import json as _json
        try:
            with _tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=PROMPT_EXTENSIONS_META_FILE.parent,
                delete=False, suffix=".meta.tmp"
            ) as _mfh:
                _mfh.write(_json.dumps(meta, indent=2))
                _meta_tmp = _mfh.name
            _os.replace(_meta_tmp, PROMPT_EXTENSIONS_META_FILE)
        except OSError:
            pass  # sidecar is diagnostics-only; never fail ingest on it

    return {"rules_added": added, "total_rules": len(rules), "file": str(extensions_path)}


# ── HITL alert push ───────────────────────────────────────────────────────────

def _push_review_alerts(proposals: List[Dict]) -> List[str]:
    """Push each proposal needing human review onto the HITL attention queue.

    Returns the proposal_ids successfully alerted so the caller can mark them
    so they are surfaced exactly once. Without that mark, every ingest run
    re-pushes an alert for the same still-pending proposal, and an operator who
    rejects the *alert* (which never writes back to the proposal record) sees it
    resurrect on the next run — alert fatigue that erodes the HITL gate.
    """
    try:
        import sys as _sys
        _sys.path.insert(0, str(_REPO_ROOT / "scripts" / "ai" / "lib"))
        from attention_queue import push as _push
    except ImportError:
        return []  # attention_queue not available — skip silently

    alerted: List[str] = []
    for p in proposals:
        proposal_id = p.get("proposal_id", "unknown")
        ptype = p.get("type", "unknown")
        title = f"Training proposal needs review: {ptype}"[:80]
        detail = p.get("rationale") or f"Proposal {proposal_id} of type '{ptype}' flagged by training_ingest"
        _push(
            source="training-ingest",
            severity="medium",
            autonomy_boundary="human_gate",
            title=title,
            detail=detail,
            proposed_action=(
                f"Review proposal {proposal_id} in "
                f".agents/telemetry/optimization_proposals.jsonl, "
                f"then run: scripts/ai/aq-approve <alert-id>"
            ),
            payload=p,
        )
        if proposal_id and proposal_id != "unknown":
            alerted.append(proposal_id)
    return alerted


# ── CLI ───────────────────────────────────────────────────────────────────────

def _cli() -> None:
    parser = argparse.ArgumentParser(description="Ingest telemetry into fine-tuning dataset")
    parser.add_argument("--dry-run", action="store_true",
                        help="Count samples but do not write to dataset")
    parser.add_argument("--hours", type=int, default=24,
                        help="Window of events to process (default: 24)")
    parser.add_argument("--min-quality", type=float, default=DEFAULT_MIN_QUALITY,
                        help=f"Minimum quality score 0–1 (default: {DEFAULT_MIN_QUALITY})")
    parser.add_argument("--json", dest="as_json", action="store_true",
                        help="Output report as JSON")
    args = parser.parse_args()

    ingestor = TrainingIngestor(min_quality=args.min_quality, dry_run=args.dry_run)
    report = ingestor.run(hours=args.hours)

    # Generate/update prompt extensions for agent-agnostic durability.
    ext_summary = generate_prompt_extensions(report, dry_run=args.dry_run)
    report["prompt_extensions"] = ext_summary

    if args.as_json:
        print(json.dumps(report, indent=2))
        return

    dry_tag = " [DRY RUN]" if args.dry_run else ""
    print(f"Training ingest report{dry_tag} — last {args.hours}h")
    print(f"  Positive samples added : {report['positive_samples_added']}")
    print(f"  Dataset total          : {report['dataset_total']}")
    if report["failure_summary"]:
        print(f"  Failure classes        : {report['failure_summary']}")
    if report["gap_patterns"]:
        print(f"  Top gap patterns       :")
        for g in report["gap_patterns"][:5]:
            print(f"    [{g['count']}x] {g['pattern'][:80]}")
    if report["proposals_auto_approved"]:
        print(f"  Auto-approved proposals: {len(report['proposals_auto_approved'])}")
    if report["proposals_needing_review"]:
        print(f"  Needs human review     : {len(report['proposals_needing_review'])}")
        if not args.dry_run:
            alerted_ids = _push_review_alerts(report["proposals_needing_review"])
            # Surface each proposal exactly once: move it out of the "pending"
            # set so the next ingest run does not re-alert. The single queued
            # alert persists until the operator acts on it.
            for _pid in alerted_ids:
                ingestor._mark_proposal(_pid, "review_pending")
    print(f"  Prompt extensions      : +{ext_summary['rules_added']} rules → {ext_summary['file']}")


if __name__ == "__main__":
    _cli()
