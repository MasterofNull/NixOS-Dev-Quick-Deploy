"""Lost-authenticator recovery CORE — Approval Control Plane P1b (pure
library; no socket server, no systemd, no live console/UDS wiring here).

Implements `.agents/plans/approval-control-plane/ACP-P1b-DESIGN-20260816.md`
(authoritative), consuming the "P1b enrollment copy" / "P1b recovery copy"
verbatim strings from
`.agents/plans/approval-control-plane/ACP-PREP-COPY-20260816.md` as
`ENROLLMENT_COPY` / `RECOVERY_COPY` below (data only — P2 renders them; no UI
here). Predecessor: `approval_signer.py` (P1) — this module never edits it,
only reads its public constants/loader for compatibility (see below).

The problem (design "problem, stated precisely"): P1 gates every owner
action on a WebAuthn assertion from a registered authenticator. One
registered authenticator is a single point of failure. This module is the
multi-authenticator allowlist MANAGER (enroll/list/remove of the SET P1
already knows how to verify assertions against) plus the console-gated
DECLARATIVE RECOVERY BOOTSTRAP for total loss — never new signing logic,
never a stored secret.

## P1-compatible allowlist file, extended with bookkeeping (no P1 edits)
P1's `load_credential_allowlist` (approval_signer.py) requires the on-disk
document's top-level `schema_version` to match and, for each entry in
`credentials`, an EXACT key-set match of `{credential_id, public_key,
sign_count, status}` — but does NOT restrict which OTHER top-level keys the
document may carry. This module exploits exactly that: it persists
`credentials` entries in P1's exact 4-key shape (so `AS.load_credential_
allowlist` and a live `ApprovalSigner` read them completely unmodified —
verified end-to-end in the test suite) and adds a sibling top-level
`recovery_metadata` map (`{credential_id_hex: {label, kind, enrolled_at}}`)
for the `label`/`kind`/enrollment-time bookkeeping this design needs but P1
never looks at. Net result: ONE allowlist file, P1 reads its 4 fields and
ignores the rest, P1b reads all of it. No edit to `approval_signer.py`.

## Invariants (design "Invariants" section)
  - No recovery path is reachable over the signer UDS by an agent: recovery
    (`bootstrap_recovery` / `require_console_root`) requires host-console
    root (`os.geteuid() == 0` AND a caller-supplied console-presence token
    matching a value ONLY a physically-present console session could have
    produced — see `require_console_root`'s docstring for the real,
    not-built-here, NixOS wiring).
  - Recovery never yields a signature or a standing authorization: this
    entire module never imports the owner private-key type, never invokes a
    signing method on anything, never touches owner key material at all —
    it only ever writes PUBLIC
    key bytes into the allowlist, exactly like P1's own registration
    concept. `bootstrap_recovery` returns a `MutationVerdict`, which has no
    signature-shaped field (asserted structurally in the test suite).
  - No self-lockout, no fail-open empty allowlist: `set_status` (disable/
    revoke) and `remove` both refuse any mutation that would leave the
    allowlist with zero ACTIVE credentials, UNLESS a valid replacement
    credential is enrolled atomically in the SAME call (single allowlist
    write, single audit sequence).
  - Every allowlist mutation (enroll / status-change / remove / recovery
    bootstrap) appends a durable audited event via `AuditLog` — mirrors the
    append/ledger idiom in `approval_signer.py` and the event-dict shape in
    `approval_request.transition()` (`event`/`actor`/`at`, plus the fields
    specific to that mutation).
  - No recovery code, no stored break-glass secret: physical presence
    (console root) IS the recovery factor. There is no function anywhere in
    this module that mints/prints/emails/SMSes a bypass code, and no field
    in the schema for one (statically asserted in the test suite).

## Scope fence (design "Scope fence" + task bounds)
No Nix/systemd unit, no live UDS/console wiring (the real mechanism is
documented in `require_console_root`'s docstring, not built), no real
WebAuthn assertion-verification logic (P1 owns that; this module only
manages the allowlist SET + gates recovery), no web UI (P2), no headless CLI
(P4), no runbook automation. Default-OFF: nothing in this module is wired
into any running service.
"""

from __future__ import annotations

import hmac
import json
import os
import re
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional

_LIB = os.path.dirname(os.path.abspath(__file__))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import approval_signer as AS  # noqa: E402 - read-only reuse of P1's constants/loader

# --------------------------------------------------------------------------
# Plain-language copy (ACP-PREP-COPY-20260816.md, "P1b enrollment copy" /
# "P1b recovery copy") — used VERBATIM. Data only; P2 renders it.
# --------------------------------------------------------------------------

ENROLLMENT_COPY: dict = {
    "title": "Setup Your Security Key",
    "intro": "Add your physical security key to verify your identity when approving important actions.",
    "steps": [
        "Go to the Settings page and select 'Security Keys'.",
        "Click 'Add New Key' and follow the on-screen prompts.",
        "Touch the light on your key when asked to confirm it is present.",
        "Give your key a name (like 'Home Key') so you can recognize it later.",
    ],
    "backup_reminder": "Please add a second key immediately in case you lose or misplace this one.",
}

RECOVERY_COPY: dict = {
    "add_backup_key": {
        "title": "Add a Backup Key",
        "body": "Register a second key now so you never get locked out if you lose the first one.",
        "steps": [
            "Go to your account security settings.",
            "Select 'Add another security key'.",
            "Plug in or tap your new key to finish.",
        ],
    },
    "recover_lost_key": {
        "title": "Recover Lost Keys",
        "body": "If you have no keys left, you must sit at this computer to reset access.",
        "steps": [
            "Sit down physically at this computer (recovery only works at the machine itself).",
            "Open the recovery option shown on the local screen.",
            "Register a new security key when prompted.",
            "Add a second backup key right away so this can't happen again.",
        ],
    },
}

# --------------------------------------------------------------------------
# Kinds (bookkeeping only — P1 never looks at `kind`; any registered,
# active credential satisfies a signer assertion identically regardless of
# kind) + field bounds.
# --------------------------------------------------------------------------

KIND_PRIMARY = "primary"
KIND_BACKUP = "backup"
KIND_RECOVERY = "recovery"
KINDS = (KIND_PRIMARY, KIND_BACKUP, KIND_RECOVERY)

LABEL_MAX_LEN = 80

# Reimplemented (not imported) — same "self-contained confined-service
# bundle" reasoning `approval_signer.SingleUseLedger`'s docstring gives for
# reimplementing rather than importing `revocation_epoch.DurableReplayLedger`.
_HEX_CREDENTIAL_ID_RE = re.compile(r"[0-9a-f]+")
_HEX_PUBLIC_KEY_RE = re.compile(r"[0-9a-f]{64}")
_MAX_ALLOWLIST_FILE_BYTES = 1 << 20

RECOVERY_METADATA_KEYS = frozenset({"label", "kind", "enrolled_at"})

# --------------------------------------------------------------------------
# Typed, safe-to-log reason vocabulary — never raises into the caller.
# --------------------------------------------------------------------------

OK = "ok"

DENY_INVALID_CREDENTIAL_ID = "credential-id-invalid"
DENY_INVALID_PUBLIC_KEY = "public-key-invalid"
DENY_INVALID_LABEL = "label-invalid"
DENY_INVALID_KIND = "kind-invalid"
DENY_INVALID_STATUS = "status-invalid"
DENY_DUPLICATE_CREDENTIAL = "duplicate-credential"
DENY_UNKNOWN_CREDENTIAL = "unknown-credential"
DENY_ALLOWLIST_UNREADABLE = "allowlist-unreadable"
DENY_LAST_ACTIVE_CREDENTIAL = "last-active-credential"
DENY_REPLACEMENT_INVALID = "replacement-invalid"
DENY_INTERNAL = "internal-error"

DENY_EUID_NOT_ROOT = "euid-not-root"
DENY_CONSOLE_TOKEN_MISSING = "console-token-missing"
DENY_CONSOLE_TOKEN_MISCONFIGURED = "console-token-misconfigured"
DENY_CONSOLE_TOKEN_MISMATCH = "console-token-mismatch"

AUDIT_EVENT_ENROLLED = "credential_enrolled"
AUDIT_EVENT_STATUS_CHANGED = "credential_status_changed"
AUDIT_EVENT_REMOVED = "credential_removed"
AUDIT_EVENT_RECOVERY_BOOTSTRAP = "recovery_bootstrap_enrolled"


@dataclass(frozen=True)
class MutationVerdict:
    """Result of any allowlist mutation or gate check in this module.
    Deliberately carries NO signature/authorization-shaped field — recovery
    and every other operation here only ever (re)shapes the credential SET,
    never authorizes an action (design invariant 2)."""

    ok: bool
    reason: str
    detail: str = ""
    event: Optional[dict] = None


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _validate_entry_fields(credential_id: Any, public_key: Any, label: Any) -> Optional[str]:
    if (
        not isinstance(credential_id, str)
        or not credential_id
        or _HEX_CREDENTIAL_ID_RE.fullmatch(credential_id) is None
    ):
        return DENY_INVALID_CREDENTIAL_ID
    if not isinstance(public_key, str) or _HEX_PUBLIC_KEY_RE.fullmatch(public_key) is None:
        return DENY_INVALID_PUBLIC_KEY
    if not isinstance(label, str) or not label or len(label) > LABEL_MAX_LEN:
        return DENY_INVALID_LABEL
    return None


# --------------------------------------------------------------------------
# require_console_root — the ONLY authorization for `bootstrap_recovery`.
# --------------------------------------------------------------------------


def require_console_root(
    *,
    euid: Optional[int] = None,
    console_presence_token: Optional[str],
    expected_console_presence_token: Optional[str],
) -> MutationVerdict:
    """Models "physical presence at the host console" (design step 2) as an
    explicit, testable gate: EUID 0 AND a caller-supplied presence token
    matching an expected value that an over-the-UDS agent process cannot
    forge. `euid` defaults to a live `os.geteuid()` read; callers pass an
    explicit value only to get deterministic tests.

    Real NixOS wiring (documented here per the task's request; NOT built —
    no Nix/systemd unit is added by this module):
      - `expected_console_presence_token` would be sourced fresh, per
        attempt, from a root-owned `0600` file under a tmpfs path such as
        `/run/aq-console-presence/token` — written ONLY by a
        `system.activationScripts`-declared oneshot that is itself gated on
        genuine physical presence, e.g. triggered from `agetty@tty1
        .service`'s `ExecStartPost`, or by querying `loginctl show-session
        $XDG_SESSION_ID -p Type -p Seat` and requiring `Type=tty` (or
        `Type=x11`) on `Seat=seat0` — which rules out any SSH/network
        session, including one run by an agent sharing the harness's own
        UID.
      - The token itself would be freshly random (`os.urandom(32).hex()`
        or similar) each time, TTL-bounded (e.g. 60s), and consumed
        (unlinked) after its single successful read — so even a process
        that could somehow read a stale root-owned file gets no replay
        value from it.
      - The recovery caller (a human running an `aq-approve-recover`-style
        CLI AT the console, invoked as root) reads that same file and
        passes its contents as `console_presence_token` here. An agent
        connected over the confined signer UDS runs as the unprivileged
        service UID (not root) and has no console session at all, so it can
        satisfy neither half of this gate — not "euid==0", and even if it
        somehow were root (e.g. a container escape), it still cannot read a
        `0600` file it was never handed and that no longer exists a moment
        after the human's own read.

    Fails CLOSED, never open: a missing/empty `expected_console_presence_
    token` (misconfiguration — the file wasn't wired up yet) denies rather
    than skipping the check, so a broken deployment cannot silently degrade
    into "root euid alone is enough"."""
    try:
        effective_euid = os.geteuid() if euid is None else euid
        if not isinstance(effective_euid, int) or effective_euid != 0:
            return MutationVerdict(False, DENY_EUID_NOT_ROOT)
        if not isinstance(expected_console_presence_token, str) or not expected_console_presence_token:
            return MutationVerdict(False, DENY_CONSOLE_TOKEN_MISCONFIGURED)
        if not isinstance(console_presence_token, str) or not console_presence_token:
            return MutationVerdict(False, DENY_CONSOLE_TOKEN_MISSING)
        if not hmac.compare_digest(console_presence_token, expected_console_presence_token):
            return MutationVerdict(False, DENY_CONSOLE_TOKEN_MISMATCH)
        return MutationVerdict(True, OK)
    except Exception as exc:  # noqa: BLE001 - total function, never raises into the caller
        return MutationVerdict(False, DENY_INTERNAL, f"unhandled:{exc.__class__.__name__}")


# --------------------------------------------------------------------------
# Durable append-only audit trail. Not a single-use ledger (this is a
# sequential journal, one line per mutation) -- same fsync-before-return
# durability discipline as `approval_signer`'s ledgers, different shape
# (O_APPEND, not O_CREAT|O_EXCL) because every call here is meant to
# succeed and accumulate, not deduplicate.
# --------------------------------------------------------------------------


class AuditLog:
    def __init__(self, path: Any) -> None:
        self._path = str(path)
        parent = os.path.dirname(self._path) or "."
        os.makedirs(parent, mode=0o700, exist_ok=True)

    def append(self, event: Mapping[str, Any]) -> None:
        line = json.dumps(dict(event), sort_keys=True).encode("utf-8") + b"\n"
        fd = os.open(self._path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            os.write(fd, line)
            os.fsync(fd)
        finally:
            os.close(fd)

    def read_all(self) -> list[dict]:
        try:
            raw = Path(self._path).read_text(encoding="utf-8")
        except OSError:
            return []
        events: list[dict] = []
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                doc = json.loads(line)
            except ValueError:
                continue
            if isinstance(doc, dict):
                events.append(doc)
        return events


# --------------------------------------------------------------------------
# RecoveryAllowlistStore — atomic read/write of the extended allowlist
# document. Write path mirrors `approval_signer.PendingChallengeStore.put`
# exactly (tempfile + fsync(file) + os.replace + fsync(dir)).
# --------------------------------------------------------------------------


class RecoveryAllowlistStore:
    def __init__(self, path: Any) -> None:
        self._path = str(path)

    def read_or_empty(self) -> Optional[dict]:
        """A missing file is a fresh, empty, valid document (first
        enrollment ever). A PRESENT but malformed file is `None` — fail
        closed, never silently treated as empty (that would let a mutation
        clobber a corrupted-but-real allowlist instead of refusing)."""
        p = Path(self._path)
        if not p.exists():
            return {
                "schema_version": AS.CREDENTIAL_ALLOWLIST_SCHEMA_VERSION,
                "revision": 0,
                "credentials": [],
                "recovery_metadata": {},
            }
        try:
            raw = p.read_bytes()
        except OSError:
            return None
        if len(raw) > _MAX_ALLOWLIST_FILE_BYTES:
            return None
        try:
            doc = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            return None
        if not isinstance(doc, dict) or doc.get("schema_version") != AS.CREDENTIAL_ALLOWLIST_SCHEMA_VERSION:
            return None
        if not isinstance(doc.get("credentials"), list) or not isinstance(doc.get("recovery_metadata"), dict):
            return None
        return doc

    def write(self, doc: Mapping[str, Any]) -> None:
        parent = os.path.dirname(self._path) or "."
        os.makedirs(parent, mode=0o700, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=parent, prefix=".allowlist.", suffix=".tmp")
        try:
            os.write(fd, json.dumps(dict(doc), sort_keys=True).encode("utf-8"))
            os.fsync(fd)
        finally:
            os.close(fd)
        os.chmod(tmp_path, 0o600)
        os.replace(tmp_path, self._path)
        dir_fd = os.open(parent, os.O_DIRECTORY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)


# --------------------------------------------------------------------------
# AllowlistManager — the multi-authenticator model + console-gated recovery.
# --------------------------------------------------------------------------


class AllowlistManager:
    def __init__(self, *, allowlist_path: Any, audit_log_path: Any) -> None:
        self._store = RecoveryAllowlistStore(allowlist_path)
        self._audit = AuditLog(audit_log_path)

    def audit_events(self) -> list[dict]:
        return self._audit.read_all()

    def list_credentials(self) -> Optional[list[dict]]:
        """Merged view (credential fields + label/kind/enrolled_at), or
        `None` if the on-disk allowlist is unreadable/malformed."""
        doc = self._store.read_or_empty()
        if doc is None:
            return None
        out = []
        for entry in doc["credentials"]:
            meta = doc["recovery_metadata"].get(entry["credential_id"], {})
            out.append(
                {
                    **entry,
                    "label": meta.get("label"),
                    "kind": meta.get("kind"),
                    "enrolled_at": meta.get("enrolled_at"),
                }
            )
        return out

    # -- enroll (primary / backup / recovery) -----------------------------

    def enroll(
        self,
        *,
        credential_id: str,
        public_key: str,
        label: str,
        kind: str = KIND_BACKUP,
        status: str = AS.CREDENTIAL_STATUS_ACTIVE,
        actor: str,
        now: Optional[datetime] = None,
        _event_name: str = AUDIT_EVENT_ENROLLED,
    ) -> MutationVerdict:
        moment = now or datetime.now(timezone.utc)
        try:
            if kind not in KINDS:
                return MutationVerdict(False, DENY_INVALID_KIND, kind)
            if status not in AS.CREDENTIAL_STATUS_VALUES:
                return MutationVerdict(False, DENY_INVALID_STATUS, status)
            field_err = _validate_entry_fields(credential_id, public_key, label)
            if field_err:
                return MutationVerdict(False, field_err)

            doc = self._store.read_or_empty()
            if doc is None:
                return MutationVerdict(False, DENY_ALLOWLIST_UNREADABLE)
            if any(e["credential_id"] == credential_id for e in doc["credentials"]):
                return MutationVerdict(False, DENY_DUPLICATE_CREDENTIAL)

            doc = json.loads(json.dumps(doc))
            doc["credentials"].append(
                {"credential_id": credential_id, "public_key": public_key, "sign_count": 0, "status": status}
            )
            doc["recovery_metadata"][credential_id] = {"label": label, "kind": kind, "enrolled_at": _iso(moment)}
            doc["revision"] = int(doc.get("revision", 0)) + 1
            self._store.write(doc)

            event = {
                "event": _event_name,
                "credential_id": credential_id,
                "kind": kind,
                "label": label,
                "status": status,
                "actor": actor,
                "at": _iso(moment),
            }
            self._audit.append(event)
            return MutationVerdict(True, OK, event=event)
        except Exception as exc:  # noqa: BLE001 - total function, never raises into the caller
            return MutationVerdict(False, DENY_INTERNAL, f"unhandled:{exc.__class__.__name__}")

    # -- status change (e.g. "disable"/revoke the primary) ----------------

    def set_status(
        self,
        credential_id: str,
        new_status: str,
        *,
        actor: str,
        now: Optional[datetime] = None,
        replacement: Optional[Mapping[str, Any]] = None,
    ) -> MutationVerdict:
        """Change one credential's status (e.g. revoke a lost/broken
        primary). Refused if it would leave zero ACTIVE credentials, unless
        `replacement` (a fresh credential dict) is enrolled atomically in
        this same call -- no self-lockout, no fail-open empty-active state."""
        moment = now or datetime.now(timezone.utc)
        try:
            if new_status not in AS.CREDENTIAL_STATUS_VALUES:
                return MutationVerdict(False, DENY_INVALID_STATUS, new_status)
            doc = self._store.read_or_empty()
            if doc is None:
                return MutationVerdict(False, DENY_ALLOWLIST_UNREADABLE)
            idx = next(
                (i for i, e in enumerate(doc["credentials"]) if e["credential_id"] == credential_id), None
            )
            if idx is None:
                return MutationVerdict(False, DENY_UNKNOWN_CREDENTIAL)

            doc = json.loads(json.dumps(doc))
            old_status = doc["credentials"][idx]["status"]
            doc["credentials"][idx]["status"] = new_status

            replacement_event = None
            if replacement is not None:
                rep_err, doc, replacement_event = self._apply_replacement(doc, replacement, actor, moment)
                if rep_err is not None:
                    return rep_err

            active_count = sum(1 for e in doc["credentials"] if e["status"] == AS.CREDENTIAL_STATUS_ACTIVE)
            if active_count == 0:
                return MutationVerdict(False, DENY_LAST_ACTIVE_CREDENTIAL)

            doc["revision"] = int(doc.get("revision", 0)) + 1
            self._store.write(doc)

            event = {
                "event": AUDIT_EVENT_STATUS_CHANGED,
                "credential_id": credential_id,
                "from_status": old_status,
                "to_status": new_status,
                "actor": actor,
                "at": _iso(moment),
            }
            self._audit.append(event)
            if replacement_event:
                self._audit.append(replacement_event)
            return MutationVerdict(True, OK, event=event)
        except Exception as exc:  # noqa: BLE001 - total function, never raises into the caller
            return MutationVerdict(False, DENY_INTERNAL, f"unhandled:{exc.__class__.__name__}")

    # -- remove (hard delete) ----------------------------------------------

    def remove(
        self,
        credential_id: str,
        *,
        actor: str,
        now: Optional[datetime] = None,
        replacement: Optional[Mapping[str, Any]] = None,
    ) -> MutationVerdict:
        """Hard-delete a credential from the allowlist. Refused if it is
        the last ACTIVE credential, unless `replacement` is enrolled
        atomically in this same call (single allowlist write, single audit
        sequence: a `credential_removed` event, then a `credential_enrolled`
        event for the replacement)."""
        moment = now or datetime.now(timezone.utc)
        try:
            doc = self._store.read_or_empty()
            if doc is None:
                return MutationVerdict(False, DENY_ALLOWLIST_UNREADABLE)
            if not any(e["credential_id"] == credential_id for e in doc["credentials"]):
                return MutationVerdict(False, DENY_UNKNOWN_CREDENTIAL)

            doc = json.loads(json.dumps(doc))
            doc["credentials"] = [e for e in doc["credentials"] if e["credential_id"] != credential_id]
            doc["recovery_metadata"].pop(credential_id, None)

            replacement_event = None
            if replacement is not None:
                rep_err, doc, replacement_event = self._apply_replacement(doc, replacement, actor, moment)
                if rep_err is not None:
                    return rep_err

            active_count = sum(1 for e in doc["credentials"] if e["status"] == AS.CREDENTIAL_STATUS_ACTIVE)
            if active_count == 0:
                return MutationVerdict(False, DENY_LAST_ACTIVE_CREDENTIAL)

            doc["revision"] = int(doc.get("revision", 0)) + 1
            self._store.write(doc)

            event = {
                "event": AUDIT_EVENT_REMOVED,
                "credential_id": credential_id,
                "actor": actor,
                "at": _iso(moment),
            }
            self._audit.append(event)
            if replacement_event:
                self._audit.append(replacement_event)
            return MutationVerdict(True, OK, event=event)
        except Exception as exc:  # noqa: BLE001 - total function, never raises into the caller
            return MutationVerdict(False, DENY_INTERNAL, f"unhandled:{exc.__class__.__name__}")

    def _apply_replacement(
        self, doc: dict, replacement: Mapping[str, Any], actor: str, moment: datetime
    ) -> tuple[Optional[MutationVerdict], dict, Optional[dict]]:
        """Shared helper for `set_status`/`remove`'s `replacement=` path:
        validates + appends the replacement credential into `doc` (already
        a private deep copy owned by the caller). Returns `(error_verdict,
        doc, event)`; `error_verdict` is non-None on any failure, in which
        case the caller must return it immediately WITHOUT writing `doc`."""
        rep_id = replacement.get("credential_id")
        rep_pub = replacement.get("public_key")
        rep_label = replacement.get("label")
        rep_kind = replacement.get("kind", KIND_BACKUP)
        if rep_kind not in KINDS:
            return MutationVerdict(False, DENY_REPLACEMENT_INVALID, DENY_INVALID_KIND), doc, None
        field_err = _validate_entry_fields(rep_id, rep_pub, rep_label)
        if field_err:
            return MutationVerdict(False, DENY_REPLACEMENT_INVALID, field_err), doc, None
        if any(e["credential_id"] == rep_id for e in doc["credentials"]):
            return MutationVerdict(False, DENY_REPLACEMENT_INVALID, DENY_DUPLICATE_CREDENTIAL), doc, None
        doc["credentials"].append(
            {
                "credential_id": rep_id,
                "public_key": rep_pub,
                "sign_count": 0,
                "status": AS.CREDENTIAL_STATUS_ACTIVE,
            }
        )
        doc["recovery_metadata"][rep_id] = {"label": rep_label, "kind": rep_kind, "enrolled_at": _iso(moment)}
        event = {
            "event": AUDIT_EVENT_ENROLLED,
            "credential_id": rep_id,
            "kind": rep_kind,
            "label": rep_label,
            "status": AS.CREDENTIAL_STATUS_ACTIVE,
            "actor": actor,
            "at": _iso(moment),
        }
        return None, doc, event

    # -- console-gated declarative recovery bootstrap ----------------------

    def bootstrap_recovery(
        self,
        *,
        credential_id: str,
        public_key: str,
        label: str,
        console_presence_token: Optional[str],
        expected_console_presence_token: Optional[str],
        euid: Optional[int] = None,
        actor: str = "owner-console",
        now: Optional[datetime] = None,
    ) -> MutationVerdict:
        """Total-loss recovery (design step 2): enrolls a fresh
        authenticator, authorized ONLY by `require_console_root`. This is
        the sole path in this module that may add a credential without any
        existing one "vouching" for the operation -- appropriate ONLY
        because the gate itself (physical presence at the console) is
        stronger than a WebAuthn assertion, not weaker. Never signs, never
        returns a standing authorization -- it enrolls a credential the
        human then uses through the ordinary P1 `sign_request` flow."""
        gate = require_console_root(
            euid=euid,
            console_presence_token=console_presence_token,
            expected_console_presence_token=expected_console_presence_token,
        )
        if not gate.ok:
            return gate
        return self.enroll(
            credential_id=credential_id,
            public_key=public_key,
            label=label,
            kind=KIND_RECOVERY,
            status=AS.CREDENTIAL_STATUS_ACTIVE,
            actor=actor,
            now=now,
            _event_name=AUDIT_EVENT_RECOVERY_BOOTSTRAP,
        )
