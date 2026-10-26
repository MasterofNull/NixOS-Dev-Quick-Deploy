#!/usr/bin/env python3
"""Durable Agent Runtime & Effect Sandwich Middleware (DP-2).

Implements atomic intent logging, monotonic CAS state document versioning,
tool mutation categorization (Class 1, 2, and 3), and OUTCOME_UNKNOWN
reconciliation surviving mid-step process crashes.
"""

from __future__ import annotations

import dataclasses
import datetime
import enum
import fcntl
import hashlib
import json
import logging
import os
from pathlib import Path
import sys
import threading
import uuid
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

logger = logging.getLogger("aq.durable_runtime")


class ToolClass(str, enum.Enum):
    """Categorization of side-effect mutability."""
    CLASS_1_READ_ONLY = "read_only"
    CLASS_2_IDEMPOTENT_WRITE = "idempotent_write"
    CLASS_3_EXTERNAL_MUTATION = "external_mutation"


class IntentState(str, enum.Enum):
    """State machine lifecycle for effect intents."""
    PREPARED = "PREPARED"
    EXECUTING = "EXECUTING"
    COMMITTED = "COMMITTED"
    FAILED_KNOWN = "FAILED_KNOWN"
    OUTCOME_UNKNOWN = "OUTCOME_UNKNOWN"
    RECONCILING = "RECONCILING"
    RECONCILED_COMMITTED = "RECONCILED_COMMITTED"
    RECONCILED_FAILED = "RECONCILED_FAILED"


_LEGAL_TRANSITIONS = {
    IntentState.PREPARED.value: {IntentState.EXECUTING.value},
    IntentState.EXECUTING.value: {
        IntentState.COMMITTED.value,
        IntentState.FAILED_KNOWN.value,
        IntentState.OUTCOME_UNKNOWN.value,
    },
    IntentState.FAILED_KNOWN.value: {IntentState.EXECUTING.value},
    IntentState.OUTCOME_UNKNOWN.value: {IntentState.RECONCILING.value},
    IntentState.RECONCILING.value: {
        IntentState.OUTCOME_UNKNOWN.value,
        IntentState.RECONCILED_COMMITTED.value,
        IntentState.RECONCILED_FAILED.value,
    },
    IntentState.RECONCILED_FAILED.value: {IntentState.EXECUTING.value},
    IntentState.COMMITTED.value: set(),
    IntentState.RECONCILED_COMMITTED.value: set(),
}


class ConcurrencyConflictError(RuntimeError):
    """Raised when CAS (Compare-and-Swap) version check fails."""
    pass


class OutcomeUnknownError(RuntimeError):
    """Raised when an operation crashes or times out and its outcome is uncertain."""
    pass


@dataclasses.dataclass
class IntentRecord:
    """Persistent intent document."""
    intent_id: str
    run_id: str
    step_id: int
    tool_name: str
    tool_class: str
    args: Dict[str, Any]
    idempotency_key: str
    state: str
    version: int
    created_at: str
    updated_at: str
    target_state_query: Optional[Dict[str, Any]] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    reconciliation_attempts: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IntentRecord":
        return cls(**data)


def compute_idempotency_key(run_id: str, step_id: int, tool_name: str, args: Dict[str, Any]) -> str:
    """Generate deterministic SHA256 idempotency key for an intent."""
    normalized_args = json.dumps(args, sort_keys=True, default=str)
    raw = f"{run_id}:{step_id}:{tool_name}:{normalized_args}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def classify_tool(tool_name: str) -> ToolClass:
    """Classify tool mutation safety into Class 1, 2, or 3."""
    name = tool_name.lower()

    # Class 1: Read-only tools
    read_prefixes = ("read_", "view_", "get_", "list_", "query_", "inspect_", "check_", "search_", "find_")
    read_exact = {"cat", "agrep", "als", "git_status", "status", "diff", "head", "tail"}
    if name in read_exact or any(name.startswith(p) for p in read_prefixes):
        return ToolClass.CLASS_1_READ_ONLY

    # Class 2: Idempotent overwrite tools
    idempotent_prefixes = ("write_file", "write_to_file", "replace_file_content", "edit_file", "put_", "save_")
    if any(name.startswith(p) for p in idempotent_prefixes):
        return ToolClass.CLASS_2_IDEMPOTENT_WRITE

    # Class 3: Non-idempotent or external mutations
    return ToolClass.CLASS_3_EXTERNAL_MUTATION


def _fsync_write_json(path: Path, data: Any) -> None:
    """Atomic durable JSON write: temp-same-dir, write, fsync, atomic replace, dir fsync."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.parent / f"{path.name}.tmp-{uuid.uuid4().hex}"
    serialized = (json.dumps(data, indent=2, sort_keys=True, default=str) + "\n").encode("utf-8")

    fd = os.open(str(tmp_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_CLOEXEC, 0o600)
    try:
        os.write(fd, serialized)
        os.fsync(fd)
    finally:
        os.close(fd)

    os.replace(str(tmp_path), str(path))
    try:
        dir_fd = os.open(str(path.parent), os.O_DIRECTORY | os.O_CLOEXEC)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except OSError:
        pass


class DurableEffectStore:
    """Thread-safe, process-safe durable intent store with atomic CAS."""

    def __init__(self, ledger_path: Optional[Union[str, Path]] = None) -> None:
        if ledger_path is None:
            env_path = os.environ.get("AQ_DURABLE_STORE_PATH")
            if env_path:
                self.ledger_path = Path(env_path)
            else:
                repo_root = Path(__file__).resolve().parents[3]
                self.ledger_path = repo_root / ".agents" / "durable" / "ledger.json"
        else:
            self.ledger_path = Path(ledger_path)

        self.lock_path = self.ledger_path.parent / f"{self.ledger_path.stem}.lock"
        self._thread_lock = threading.Lock()
        self._ensure_store()

    def _ensure_store(self) -> None:
        """Initialize ledger file if missing."""
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.ledger_path.exists():
            _fsync_write_json(self.ledger_path, {"schema_version": "aq.durable-ledger.v1", "intents": {}})

    def _acquire_process_lock(self):
        """Cross-process file lock context manager."""
        class _LockCtx:
            def __init__(self, lock_file: Path):
                self.lock_file = lock_file
                self.fd = None

            def __enter__(self):
                self.lock_file.parent.mkdir(parents=True, exist_ok=True)
                self.fd = open(self.lock_file, "w")
                fcntl.flock(self.fd, fcntl.LOCK_EX)
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                if self.fd:
                    try:
                        fcntl.flock(self.fd, fcntl.LOCK_UN)
                        self.fd.close()
                    except Exception:
                        pass
        return _LockCtx(self.lock_path)

    def _read_ledger(self) -> Dict[str, Any]:
        """Read current ledger from disk."""
        try:
            with open(self.ledger_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {"schema_version": "aq.durable-ledger.v1", "intents": {}}

    def _write_ledger(self, ledger: Dict[str, Any]) -> None:
        """Write updated ledger to disk durably."""
        _fsync_write_json(self.ledger_path, ledger)

    def prepare_intent(
        self,
        run_id: str,
        step_id: int,
        tool_name: str,
        args: Dict[str, Any],
        tool_class: Optional[Union[ToolClass, str]] = None,
        target_state_query: Optional[Dict[str, Any]] = None,
    ) -> IntentRecord:
        """Log PREPARED intent. Returns existing committed intent if idempotency matches."""
        if tool_class is None:
            tool_class = classify_tool(tool_name)
        tool_class_val = tool_class.value if isinstance(tool_class, ToolClass) else str(tool_class)

        idempotency_key = compute_idempotency_key(run_id, step_id, tool_name, args)
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()

        with self._thread_lock, self._acquire_process_lock():
            ledger = self._read_ledger()
            intents = ledger.setdefault("intents", {})

            # Check if this exact intent already exists
            for existing in intents.values():
                if existing.get("idempotency_key") == idempotency_key:
                    # If already committed, return cached receipt
                    if existing.get("state") in (
                        IntentState.COMMITTED.value,
                        IntentState.RECONCILED_COMMITTED.value,
                    ):
                        return IntentRecord.from_dict(existing)
                    # If previously interrupted, return existing record
                    return IntentRecord.from_dict(existing)

            # Create fresh intent
            intent_id = f"intent-{uuid.uuid4().hex[:12]}"
            record = IntentRecord(
                intent_id=intent_id,
                run_id=run_id,
                step_id=step_id,
                tool_name=tool_name,
                tool_class=tool_class_val,
                args=args,
                idempotency_key=idempotency_key,
                state=IntentState.PREPARED.value,
                version=1,
                created_at=now,
                updated_at=now,
                target_state_query=target_state_query,
                result=None,
                error=None,
                reconciliation_attempts=0,
            )
            intents[intent_id] = record.to_dict()
            self._write_ledger(ledger)
            return record

    def transition(
        self,
        intent_id: str,
        target_state: Union[IntentState, str],
        expected_version: int,
        result: Optional[Any] = None,
        error: Optional[str] = None,
    ) -> IntentRecord:
        """Atomic CAS transition to a legal target state."""
        target_state_val = target_state.value if isinstance(target_state, IntentState) else str(target_state)
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()

        with self._thread_lock, self._acquire_process_lock():
            ledger = self._read_ledger()
            intents = ledger.get("intents", {})
            if intent_id not in intents:
                raise KeyError(f"Intent {intent_id} not found in ledger")

            current = intents[intent_id]
            current_version = current.get("version", 1)
            if current_version != expected_version:
                raise ConcurrencyConflictError(
                    f"CAS failure on intent {intent_id}: expected version {expected_version}, got {current_version}"
                )

            current_state = current.get("state")
            if target_state_val not in _LEGAL_TRANSITIONS.get(current_state, set()):
                raise ValueError(
                    f"Illegal transition for intent {intent_id}: {current_state} -> {target_state_val}"
                )

            current["state"] = target_state_val
            current["version"] = current_version + 1
            current["updated_at"] = now
            if result is not None:
                current["result"] = result
            if error is not None:
                current["error"] = error
            if target_state_val in (IntentState.RECONCILING.value,):
                current["reconciliation_attempts"] = current.get("reconciliation_attempts", 0) + 1

            self._write_ledger(ledger)
            return IntentRecord.from_dict(current)

    def get_intent(self, intent_id: str) -> Optional[IntentRecord]:
        """Fetch intent by ID."""
        with self._thread_lock, self._acquire_process_lock():
            ledger = self._read_ledger()
            raw = ledger.get("intents", {}).get(intent_id)
            return IntentRecord.from_dict(raw) if raw else None

    def list_intents(
        self,
        run_id: Optional[str] = None,
        state: Optional[Union[IntentState, str]] = None,
    ) -> List[IntentRecord]:
        """List intents matching filter criteria."""
        state_val = state.value if isinstance(state, IntentState) else state
        with self._thread_lock, self._acquire_process_lock():
            ledger = self._read_ledger()
            records = []
            for item in ledger.get("intents", {}).values():
                if run_id and item.get("run_id") != run_id:
                    continue
                if state_val and item.get("state") != state_val:
                    continue
                records.append(IntentRecord.from_dict(item))
            records.sort(key=lambda x: (x.run_id, x.step_id, x.created_at))
            return records

    def list_unresolved(self, run_id: Optional[str] = None) -> List[IntentRecord]:
        """List intents needing reconciliation (OUTCOME_UNKNOWN or stuck in EXECUTING)."""
        with self._thread_lock, self._acquire_process_lock():
            ledger = self._read_ledger()
            unresolved = []
            for item in ledger.get("intents", {}).values():
                if run_id and item.get("run_id") != run_id:
                    continue
                st = item.get("state")
                if st in (
                    IntentState.OUTCOME_UNKNOWN.value,
                    IntentState.RECONCILING.value,
                    IntentState.EXECUTING.value,
                ):
                    unresolved.append(IntentRecord.from_dict(item))
            unresolved.sort(key=lambda x: (x.run_id, x.step_id, x.created_at))
            return unresolved


class EffectSandwichMiddleware:
    """Effect Sandwich execution wrapper and reconciliation coordinator."""

    def __init__(self, store: Optional[DurableEffectStore] = None) -> None:
        self.store = store or DurableEffectStore()

    def execute(
        self,
        run_id: str,
        step_id: int,
        tool_name: str,
        args: Dict[str, Any],
        execution_fn: Callable[[Dict[str, Any]], Any],
        target_inspector_fn: Optional[Callable[[Dict[str, Any]], Tuple[bool, Any]]] = None,
        tool_class: Optional[Union[ToolClass, str]] = None,
        target_state_query: Optional[Dict[str, Any]] = None,
    ) -> Tuple[IntentRecord, Any]:
        """Execute a tool call wrapped in the 3-phase Effect Sandwich.

        Returns (intent_record, tool_result).
        """
        # Phase 1: PREPARE (Intent logged before mutation)
        intent = self.store.prepare_intent(
            run_id=run_id,
            step_id=step_id,
            tool_name=tool_name,
            args=args,
            tool_class=tool_class,
            target_state_query=target_state_query,
        )

        # If already committed (idempotent replay), return cached receipt immediately
        if intent.state in (IntentState.COMMITTED.value, IntentState.RECONCILED_COMMITTED.value):
            logger.info("Idempotent replay match: returning cached result for %s", intent.intent_id)
            return intent, intent.result

        # Phase 2: atomically claim only work that is safe to execute.
        # OUTCOME_UNKNOWN and active claims must be reconciled or resolved first.
        if intent.state == IntentState.EXECUTING.value:
            raise ConcurrencyConflictError(
                f"Intent {intent.intent_id} is already executing and cannot be claimed again"
            )
        if intent.state in (IntentState.OUTCOME_UNKNOWN.value, IntentState.RECONCILING.value):
            raise OutcomeUnknownError(
                f"Intent {intent.intent_id} has unresolved outcome and requires reconciliation"
            )
        if intent.state == IntentState.FAILED_KNOWN.value and intent.tool_class != ToolClass.CLASS_1_READ_ONLY.value:
            raise OutcomeUnknownError(
                f"Intent {intent.intent_id} is not safe to replay without reconciliation"
            )
        if intent.state not in (
            IntentState.PREPARED.value,
            IntentState.FAILED_KNOWN.value,
            IntentState.RECONCILED_FAILED.value,
        ):
            raise ValueError(f"Intent {intent.intent_id} cannot execute from state {intent.state}")

        intent = self.store.transition(intent.intent_id, IntentState.EXECUTING, intent.version)

        try:
            raw_result = execution_fn(args)
            # Success -> COMMITTED
            intent = self.store.transition(
                intent.intent_id,
                IntentState.COMMITTED,
                intent.version,
                result=raw_result,
            )
            return intent, raw_result

        except Exception as crash_or_interruption:
            if (
                isinstance(
                    crash_or_interruption,
                    (ValueError, KeyError, FileNotFoundError, PermissionError),
                )
                and intent.tool_class == ToolClass.CLASS_1_READ_ONLY.value
            ):
                self.store.transition(
                    intent.intent_id,
                    IntentState.FAILED_KNOWN,
                    intent.version,
                    error=str(crash_or_interruption),
                )
                raise

            # Crash / timeout / unknown failure -> OUTCOME_UNKNOWN
            err_msg = str(crash_or_interruption)
            logger.warning(
                "Execution interrupted for %s (%s). Marking OUTCOME_UNKNOWN: %s",
                intent.intent_id, tool_name, err_msg
            )
            intent = self.store.transition(
                intent.intent_id,
                IntentState.OUTCOME_UNKNOWN,
                intent.version,
                error=err_msg,
            )

            # Auto-reconcile immediately if inspector is provided
            if target_inspector_fn:
                reconciled_intent, rec_result = self.reconcile(intent.intent_id, target_inspector_fn)
                if reconciled_intent.state == IntentState.RECONCILED_COMMITTED.value:
                    return reconciled_intent, rec_result

            raise OutcomeUnknownError(
                f"Tool execution {tool_name} entered OUTCOME_UNKNOWN: {err_msg}"
            ) from crash_or_interruption

    def reconcile(
        self,
        intent_id: str,
        target_inspector_fn: Optional[Callable[[Dict[str, Any]], Tuple[bool, Any]]] = None,
    ) -> Tuple[IntentRecord, Optional[Any]]:
        """Reconcile an intent whose execution outcome is unknown."""
        intent = self.store.get_intent(intent_id)
        if not intent:
            raise KeyError(f"Intent {intent_id} not found")

        # A live EXECUTING claim cannot be distinguished from a crashed worker
        # without a lease/owner protocol, so leave it untouched and fail closed.
        if intent.state == IntentState.EXECUTING.value:
            raise ConcurrencyConflictError(
                f"Intent {intent.intent_id} is actively executing and cannot be reconciled"
            )
        if intent.state == IntentState.RECONCILING.value:
            raise ConcurrencyConflictError(
                f"Intent {intent.intent_id} is already being reconciled"
            )
        if intent.state != IntentState.OUTCOME_UNKNOWN.value:
            return intent, intent.result

        # Transition to RECONCILING
        intent = self.store.transition(intent.intent_id, IntentState.RECONCILING, intent.version)

        # Class 1: Read-Only -> Safe to treat as not committed (read had no persistent side-effects)
        if intent.tool_class == ToolClass.CLASS_1_READ_ONLY.value:
            intent = self.store.transition(
                intent.intent_id,
                IntentState.RECONCILED_FAILED,
                intent.version,
                error="Read-only operation interrupted; safe to re-execute",
            )
            return intent, None

        # Class 2 & Class 3: Query target state
        if target_inspector_fn:
            try:
                mutation_observed, observed_state = target_inspector_fn(intent.args)
                if mutation_observed:
                    # Target reflects mutation -> mark RECONCILED_COMMITTED
                    intent = self.store.transition(
                        intent.intent_id,
                        IntentState.RECONCILED_COMMITTED,
                        intent.version,
                        result=observed_state,
                    )
                    return intent, observed_state
                else:
                    # Target confirms mutation did NOT land -> mark RECONCILED_FAILED
                    intent = self.store.transition(
                        intent.intent_id,
                        IntentState.RECONCILED_FAILED,
                        intent.version,
                        error="Target inspector confirmed mutation was not applied; safe to re-execute",
                    )
                    return intent, None
            except Exception as inspector_err:
                logger.error("Inspector error during reconciliation of %s: %s", intent_id, inspector_err)
                intent = self.store.transition(
                    intent.intent_id,
                    IntentState.OUTCOME_UNKNOWN,
                    intent.version,
                    error=f"Inspector error: {inspector_err}",
                )
                return intent, None

        # Without an inspector, Class 3 remains fail-closed in OUTCOME_UNKNOWN
        intent = self.store.transition(
            intent.intent_id,
            IntentState.OUTCOME_UNKNOWN,
            intent.version,
            error="No target inspector available; remains fail-closed",
        )
        return intent, None


def health_summary(repo_root: Optional[Path] = None) -> Dict[str, Any]:
    """Bounded, read-only health summary of Durable Agent Runtime (DP-2)."""
    try:
        env_path = os.environ.get("AQ_DURABLE_STORE_PATH")
        if env_path:
            ledger_path = Path(env_path)
        elif repo_root:
            ledger_path = Path(repo_root) / ".agents" / "durable" / "ledger.json"
        else:
            root = Path(__file__).resolve().parents[3]
            ledger_path = root / ".agents" / "durable" / "ledger.json"

        if not ledger_path.exists():
            return {
                "available": False,
                "status": "unconfigured",
                "total_intents": 0,
                "unresolved_intents": 0,
                "committed_intents": 0,
                "ledger_path": str(ledger_path),
            }

        # Read directly without acquiring write lock or mutating store
        with open(ledger_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)

        intents_dict = data.get("intents", {})
        intents = [IntentRecord.from_dict(v) for v in intents_dict.values()]
        unresolved = [
            i for i in intents
            if i.state in (
                IntentState.OUTCOME_UNKNOWN.value,
                IntentState.FAILED_KNOWN.value,
                IntentState.RECONCILING.value,
            )
        ]
        committed = [
            i for i in intents
            if i.state in (
                IntentState.COMMITTED.value,
                IntentState.RECONCILED_COMMITTED.value,
            )
        ]
        return {
            "available": True,
            "status": "operational",
            "total_intents": len(intents),
            "unresolved_intents": len(unresolved),
            "committed_intents": len(committed),
            "ledger_path": str(ledger_path),
        }
    except Exception as exc:
        return {
            "available": False,
            "status": "unverified",
            "total_intents": 0,
            "unresolved_intents": 0,
            "committed_intents": 0,
            "reason": f"durable_runtime_unavailable:{type(exc).__name__}",
        }
