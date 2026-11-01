"""Owner-side activation signer (SSOT: .agents/plans/system-integrity-recovery/ACTIVATION-PIPELINE.md rev7).

Runs only from the Nix store, as root, via `sudo aq-activation-sign` (fresh password every call). Reads
agent-controlled request/evidence files as inert bytes (openat-style O_NOFOLLOW reads, size capped, one
captured snapshot used for checks, display and signature), appends signed envelopes to the root-owned
chain read by `activation_chain.load_chain`. Every path is injected through `Paths` so tests run
without root; the only key material is the root-only signing key file.

Envelope shapes and canonicalisation come from `activation_chain` (imported from the same store bundle).

Line-oriented formats the signer itself parses (rev7 is silent on exact field syntax; everything is `Key: value`,
one per line, keys case-sensitive, duplicates refused, anything else ignored as prose):
  attestation  six DoD dimension lines `Integrated|Turned ON|Validated|Observable|Intervenable|PM-tracked: <evidence>`
               (optional leading `1 `..`6 `), each evidence or `deferred: <reason>, <YYYY-MM-DD>`; plus
               `Author-Lane: <lane>`, `System-Closure: <store path>`, `Config-Revision: <clean git rev>`.
  review       `Review-Disposition: PASS|PASS_WITH_FOLLOWUPS`, `Reviewer-Lane: <lane>` (must differ from Author-Lane),
               `Reviewed-Closure: <store path>`, `Reviewed-Validation-Digest: <sha256>`.
  request      `attestation_sha256` must equal the digest of the captured attestation bytes.
Evidence baseline: `baseline-inputs.json` in the evidence copy is the canonical JSON whose sha256 IS the signed
`evidence_baseline_sha256` (the envelope field set is fixed by activation_chain), so the enable_evidence and
detection_snapshot values are authenticated by the signature.
Deployment identity: only /etc/aq-activation/deployment-id (verifier reads the same file); `--init-id` provisions it
as sha256(salt:/etc/machine-id)[:32] when Nix does not declare one; absent => refuse.
"""
from __future__ import annotations

import fcntl
import hashlib
import shlex
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

if __name__ == "__main__":  # python -I drops the script dir; the bundle dir is a Nix store path
    sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import activation_chain as ac  # noqa: E402

_REQUEST_ID = re.compile(r"^[a-z0-9]{8,40}$")
_NAME = re.compile(r"^[a-z0-9._-]{1,64}$")
_UNIT = re.compile(r"^[A-Za-z0-9@._-]{1,128}\.(service|socket|timer)$")
_APPROVER = re.compile(r"^[A-Za-z0-9._-]{1,32}$")
_MAX_FILE = 1 << 20
_UNIT_PROPS = ("ExecCondition", "ExecStartPre", "ExecStart", "ExecStartPost", "ExecReload", "ExecStop",
               "ExecStopPost", "Environment",
               "EnvironmentFiles", "ReadOnlyPaths", "ReadWritePaths", "WorkingDirectory")
_EXEC_PROPS = {"ExecCondition", "ExecStartPre", "ExecStart", "ExecStartPost", "ExecReload", "ExecStop",
               "ExecStopPost"}
_INTERPRETERS = re.compile(r"^(python[0-9.]*|pypy[0-9]*|sh|bash|dash|zsh|fish|ksh|env|node(js)?|deno|bun|perl[0-9.]*|"
                           r"ruby|lua(jit)?[0-9.-]*|php[0-9]*|java|guile|racket|tclsh[0-9.]*|awk|gawk|xargs|busybox)$")
_SCRIPT_EXT = re.compile(r"\.(py|pyc|sh|bash|js|mjs|cjs|rb|pl|pm|lua|php|jar|tcl|conf|cfg|ini|json|ya?ml|toml|env)$",
                         re.IGNORECASE)
# environment variables that steer code/library loading: every entry must be an absolute store path
_SEARCH_VARS = re.compile(r"^(PATH|PYTHONPATH|PYTHONHOME|PYTHONSTARTUP|PYTHONUSERBASE|NODE_PATH|NODE_OPTIONS|PERL5LIB|"
                          r"PERL5OPT|RUBYLIB|RUBYOPT|GEM_PATH|GEM_HOME|CLASSPATH|LUA_PATH|LUA_CPATH|XDG_CONFIG_DIRS|"
                          r"XDG_DATA_DIRS|GI_TYPELIB_PATH|LD_[A-Z_]+|GCONV_PATH|LOCPATH|NIX_[A-Z_]*PATH)$")
_STATE_PROPS = {"ReadOnlyPaths", "ReadWritePaths", "WorkingDirectory"}   # may name declared state_paths
_STORE = "/nix/store/"
_PATH_TOKEN = re.compile(r"(?:^|[\s=:'\"({])(/[A-Za-z0-9_.+@%~/-]*)")
_EXEC_FIELD = re.compile(r"(?:path|argv\[\])=([^;}]*)")
_SECTION = ("attestation", "validation", "review")


class SignerError(Exception):
    """A refusal; the message is shown to the owner and nothing is written."""


@dataclass
class Paths:
    state: Path = Path("/var/lib/aq-activation")
    etc: Path = Path("/etc/aq-activation")
    current_system: Path = Path("/run/current-system")

    log = property(lambda s: s.state / "log")
    head = property(lambda s: s.state / "head")
    lock = property(lambda s: s.state / "lock")
    key = property(lambda s: s.state / "signing.key")
    pub = property(lambda s: s.state / "signing.pub")
    evidence = property(lambda s: s.state / "evidence")
    signers = property(lambda s: s.etc / "signers.json")
    deployment_id = property(lambda s: s.etc / "deployment-id")
    eligible = property(lambda s: s.etc / "eligible.json")
    deployment_salt = property(lambda s: s.etc / "deployment-salt")
    machine_id: Path = Path("/etc/machine-id")


def invoking_identity(environ) -> tuple[int, int]:
    """uid/gid whose access rights bound what root may read on its behalf. Under root there is no safe
    default: SUDO_UID/SUDO_GID must be present and numeric."""
    if os.geteuid() != 0:
        return os.geteuid(), os.getegid()
    try:
        uid, gid = int(environ.get("SUDO_UID", "")), int(environ.get("SUDO_GID", ""))
    except ValueError:
        raise SignerError("SUDO_UID/SUDO_GID missing: cannot determine whose access rights apply") from None
    if uid <= 0 or gid < 0:
        raise SignerError("refusing to treat root as the invoking user")
    return uid, gid


def _tty_available() -> bool:
    try:
        return os.isatty(0) and os.isatty(1) and os.path.exists("/dev/tty")
    except OSError:
        return False


def _tty_confirm(display: str, token: str) -> bool:
    with open("/dev/tty", "r+", encoding="utf-8", errors="replace") as tty:
        tty.write(display + f"\nType 'sign {token}' to sign, anything else aborts: ")
        tty.flush()
        return tty.readline().strip() == f"sign {token}"


def _systemctl_show(unit: str) -> str:
    # fixed binary and environment: never inherits PATH or PYTHON* from the caller
    exe = os.environ.get("AQ_ACTIVATION_SYSTEMCTL", "/run/current-system/sw/bin/systemctl")
    res = subprocess.run([exe, "show", "--no-pager", *[f"-p{p}" for p in _UNIT_PROPS], unit], env={},
                         capture_output=True, text=True, timeout=20, check=False)
    return res.stdout if res.returncode == 0 else ""


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class Env:
    paths: Paths
    approver: str = "owner"
    is_tty: Callable[[], bool] = _tty_available
    confirm: Callable[[str, str], bool] = _tty_confirm
    unit_show: Callable[[str], str] = _systemctl_show
    now: Callable[[], str] = _now
    out: Callable[[str], None] = print
    invoker: Callable[[], tuple[int, int]] = lambda: invoking_identity(os.environ)


# --------------------------------------------------------------------------- safe reads / writes

def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _may(st: os.stat_result, uid: int, gid: int, bit: int) -> bool:
    """Explicit mode/owner check (os.access is meaningless under root). `bit` is 4/2/1 (r/w/x)."""
    if uid == 0:
        return True
    shift = 6 if st.st_uid == uid else 3 if st.st_gid == gid else 0
    return bool((st.st_mode >> shift) & bit)


def safe_read(path: str, cap: int = _MAX_FILE, invoker: tuple[int, int] | None = None) -> bytes:
    """Absolute path walked component by component from `/` with O_NOFOLLOW (no symlink anywhere in the path),
    the invoking uid/gid must hold search permission on every ancestor and read permission on the file, regular
    file only, world-readable (so copying it into the world-readable evidence dir discloses nothing new), size
    capped."""
    if not isinstance(path, str) or not os.path.isabs(path) or "\0" in path or path.endswith("/"):
        raise SignerError(f"bad path: {path!r}")
    parts = path.split("/")[1:]
    if any(c in ("", ".", "..") for c in parts):
        raise SignerError(f"bad path: {path!r}")
    uid, gid = invoker if invoker is not None else invoking_identity(os.environ)
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        for i, comp in enumerate(parts):
            last = i == len(parts) - 1
            if not _may(os.fstat(fd), uid, gid, 1):
                raise SignerError(f"invoking user cannot search the directory above {comp} in {path}")
            try:
                nfd = os.open(comp, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | (os.O_NONBLOCK if last else os.O_DIRECTORY),
                              dir_fd=fd)
            except OSError as e:
                raise SignerError(f"cannot open {path}: {e.strerror}") from None
            os.close(fd)
            fd = nfd
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            raise SignerError(f"{path} is not a regular file")
        if not _may(st, uid, gid, 4):
            raise SignerError(f"invoking user cannot read {path}")
        if not st.st_mode & stat.S_IROTH:
            raise SignerError(f"{path} is not world-readable (refusing to copy a private file)")
        if st.st_size > cap:
            raise SignerError(f"{path} exceeds {cap} bytes")
        data = b""
        while len(data) <= cap:
            chunk = os.read(fd, 65536)
            if not chunk:
                break
            data += chunk
        if len(data) > cap:
            raise SignerError(f"{path} exceeds {cap} bytes")
        return data
    finally:
        os.close(fd)


def _fsync_dir(d: Path) -> None:
    fd = os.open(d, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _write_file(path: Path, data: bytes, mode: int = 0o644) -> None:
    """tmp + fsync + rename + dir fsync; replaces atomically."""
    tmp = path.with_name(f".{path.name}.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW | os.O_CLOEXEC, mode)
    try:
        os.fchmod(fd, mode)
        os.write(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(tmp, path)
    _fsync_dir(path.parent)


def _write_segment(log_dir: Path, seq: int, data: bytes) -> None:
    """Exclusive create: written to a tmp name the verifier ignores, fsynced, linked to `<seq>.json`
    (fails if it exists), then the directory is fsynced. A crash leaves no half-written `<seq>.json`."""
    final = log_dir / f"{seq}.json"
    tmp = log_dir / f".{seq}.tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW | os.O_CLOEXEC, 0o644)
    try:
        os.fchmod(fd, 0o644)
        os.write(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)
    try:
        os.link(tmp, final)
    except FileExistsError:
        raise SignerError(f"segment {seq} already exists (refusing to duplicate a seq)") from None
    finally:
        os.unlink(tmp)
    _fsync_dir(log_dir)


class _Lock:
    def __init__(self, paths: Paths):
        self.path = paths.lock

    def __enter__(self):
        self.fd = os.open(self.path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
        fcntl.flock(self.fd, fcntl.LOCK_EX)
        return self

    def __exit__(self, *exc):
        os.close(self.fd)   # closing releases the flock
        return False


# --------------------------------------------------------------------------- configuration readers

def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError as e:
        raise SignerError(f"cannot read {path}: {e.strerror}") from None


def load_signers(paths: Paths) -> list[str]:
    try:
        keys = json.loads(_read_text(paths.signers)).get("keys", [])
    except (ValueError, AttributeError):
        raise SignerError("signers.json malformed") from None
    keys = [k for k in keys if isinstance(k, str) and re.fullmatch(r"[0-9a-f]{64}", k)]
    if not keys:
        raise SignerError("no signer public key is pinned in signers.json (see the owner bootstrap steps)")
    return keys


_ID_RE = re.compile(r"[A-Za-z0-9._-]{8,64}")


def load_deployment_id(paths: Paths) -> str:
    """The one resolution, shared with the verifier (aq-pm-tracker reads the same file): the provisioned
    /etc/aq-activation/deployment-id. Absent, empty or malformed => refuse."""
    if not paths.deployment_id.exists():
        raise SignerError("no deployment identity: /etc/aq-activation/deployment-id is absent (run --init-id or "
                          "set mySystem.activation.signing.deploymentId)")
    dep = _read_text(paths.deployment_id)
    if not _ID_RE.fullmatch(dep):
        raise SignerError("deployment-id malformed or empty")
    return dep


def init_id(paths: Paths) -> str:
    """Provisioning step: write deployment-id = sha256(salt:machine-id)[:32] when none exists (never overwrites)."""
    if paths.deployment_id.exists():
        return load_deployment_id(paths)
    if not (paths.deployment_salt.exists() and paths.machine_id.exists()):
        raise SignerError("cannot derive a deployment identity: deployment salt or /etc/machine-id missing")
    salt, mid = _read_text(paths.deployment_salt), _read_text(paths.machine_id)
    if not salt or not re.fullmatch(r"[0-9a-f]{32}", mid) or mid == "0" * 32:
        raise SignerError("machine-id missing or invalid: cannot derive a deployment identity")
    dep = sha256_hex(f"{salt}:{mid}".encode())[:32]
    _write_file(paths.deployment_id, (dep + "\n").encode("ascii"), 0o644)
    return dep


def load_eligible(paths: Paths) -> list[dict]:
    try:
        data = json.loads(_read_text(paths.eligible))
    except ValueError:
        raise SignerError("eligible.json malformed") from None
    if not isinstance(data, list):
        raise SignerError("eligible.json must be a list")
    return data


def load_key(paths: Paths, signers: list[str]):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    try:
        st = paths.key.lstat()
        if not stat.S_ISREG(st.st_mode) or st.st_mode & 0o077:
            raise SignerError("signing key must be a regular file with mode 0400/0600")
        seed = bytes.fromhex(paths.key.read_text(encoding="ascii").strip())
        key = Ed25519PrivateKey.from_private_bytes(seed)
    except OSError as e:
        raise SignerError(f"cannot read signing key: {e.strerror}") from None
    except ValueError:
        raise SignerError("signing key malformed") from None
    pub = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()
    if pub not in signers:
        raise SignerError(f"signing key {pub[:16]}... is not pinned in signers.json: nothing it signs would verify")
    return key


def init_key(paths: Paths) -> str:
    """Boot-time generator (systemd oneshot, root). Creates the key only when absent; always (re)writes the
    public half to signing.pub. Returns the public key hex."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    paths.state.mkdir(parents=True, exist_ok=True)
    if not paths.key.exists():
        key = Ed25519PrivateKey.generate()
        seed = key.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw,
                                 serialization.NoEncryption()).hex()
        fd = os.open(paths.key, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o400)
        try:
            os.write(fd, (seed + "\n").encode("ascii"))
            os.fsync(fd)
        finally:
            os.close(fd)
        _fsync_dir(paths.state)
    seed = bytes.fromhex(paths.key.read_text(encoding="ascii").strip())
    pub = Ed25519PrivateKey.from_private_bytes(seed).public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()
    _write_file(paths.pub, (pub + "\n").encode("ascii"), 0o644)
    return pub


# --------------------------------------------------------------------------- unit / eligibility checks

def _unit_paths(prop: str, value: str) -> list[str]:
    if prop in _EXEC_PROPS:
        value = " ".join(m for m in _EXEC_FIELD.findall(value))
    return _PATH_TOKEN.findall(value)


def _canon(p: str) -> str:
    """Normalised absolute path; any '..' segment is refused outright (never resolved away)."""
    if ".." in p.split("/"):
        raise SignerError(f"path {p!r} contains a '..' segment")
    return os.path.normpath(p)


def _store_path(p: str) -> bool:
    c = _canon(p)
    return c.startswith(_STORE) and os.path.realpath(c).startswith(_STORE)


def _check_exec(unit: str, prop: str, value: str) -> int:
    """Every command block must name an absolute executable and no argument may resolve outside the Nix store
    (relative arguments would resolve inside a mutable WorkingDirectory). Returns the number of commands."""
    blocks = re.findall(r"\{([^}]*)\}", value)
    if value.strip() and not blocks:
        raise SignerError(f"unit {unit} {prop}: unparseable command (unclassifiable)")
    n = 0
    for blk in blocks:
        pm, am = re.search(r"path=([^;]*)", blk), re.search(r"argv\[\]=([^;]*)", blk)
        exe = (pm.group(1).strip() if pm else "")
        argv = am.group(1).split() if am else []
        if not exe or not argv:
            raise SignerError(f"unit {unit} {prop}: command without executable/argv (unclassifiable)")
        if not exe.startswith("/"):
            raise SignerError(f"unit {unit} {prop}: relative executable {exe!r}")
        n += 1
        interp = bool(_INTERPRETERS.match(os.path.basename(exe)))
        for i, tok in enumerate(argv):
            if tok.startswith("/"):
                continue                      # absolute: classified by the path-token check
            if i == 0:
                continue                      # argv[0] is a display name, not loaded
            if interp and not tok.startswith("-"):
                raise SignerError(f"unit {unit} {prop}: interpreter argument {tok!r} is not a store path")
            if interp and tok in ("-c", "-e", "-E", "-m", "-r"):
                raise SignerError(f"unit {unit} {prop}: interpreter inline code/module option {tok!r}")
            val = tok.split("=", 1)[1] if tok.startswith("-") and "=" in tok else tok
            if val.startswith("/"):
                continue
            if "/" in val or val.startswith(".") or val.startswith("~") or _SCRIPT_EXT.search(val):
                raise SignerError(f"unit {unit} {prop}: relative path argument {tok!r} resolves outside the store")
    return n


def _check_env(unit: str, value: str) -> None:
    try:
        items = shlex.split(value)
    except ValueError:
        raise SignerError(f"unit {unit} Environment: unparseable (unclassifiable)") from None
    for item in items:
        name, eq, val = item.partition("=")
        if not eq or not _SEARCH_VARS.match(name):
            continue
        entries = val.split(":") if name != "NODE_OPTIONS" and name not in ("PERL5OPT", "RUBYOPT") else val.split()
        for ent in entries:
            ent = ent.split("=", 1)[1] if ent.startswith("--") and "=" in ent else ent
            if ent.startswith("-") and name in ("NODE_OPTIONS", "PERL5OPT", "RUBYOPT"):
                continue
            if not ent.startswith("/") or not _store_path(ent):
                raise SignerError(f"unit {unit} Environment {name} entry {ent!r} is empty, relative or not a "
                                  "Nix store path")


def check_unit(env: Env, unit: str, entry: dict) -> None:
    """Executables, helpers, environment and EnvironmentFiles must be Nix-store paths (after normalisation and
    symlink resolution); relative arguments and code-loading environment entries must also stay in the store.
    Declared state_paths may satisfy only the state-class properties (ReadOnlyPaths, ReadWritePaths,
    WorkingDirectory), never an executable or configuration check."""
    if not _UNIT.match(unit):
        raise SignerError(f"manifest unit name invalid: {unit!r}")
    state = [_canon(p) for p in entry.get("state_paths", []) if isinstance(p, str) and p.startswith("/")]
    text = env.unit_show(unit)
    if not text.strip():
        raise SignerError(f"unit {unit} not inspectable (unknown units are refused)")
    exec_paths = 0
    for line in text.splitlines():
        prop, _, value = line.partition("=")
        if prop not in _UNIT_PROPS:
            continue
        if prop in _EXEC_PROPS:
            n = _check_exec(unit, prop, value)
            exec_paths += n if prop == "ExecStart" else 0
        elif prop == "Environment":
            _check_env(unit, value)
        for raw in _unit_paths(prop, value):
            p = _canon(raw)
            if p == "/home" or p.startswith("/home/"):
                raise SignerError(f"unit {unit} {prop} references {p} under /home")
            if _store_path(p):
                continue
            if prop in _STATE_PROPS and any(p == a or p.startswith(a.rstrip("/") + "/") for a in state):
                continue
            raise SignerError(f"unit {unit} {prop} references {p}, which is not a Nix store path"
                              + ("" if prop in _STATE_PROPS else " (declared state paths never satisfy this)"))
    if exec_paths == 0:
        raise SignerError(f"unit {unit}: empty or missing ExecStart (unclassifiable)")


def eligible_entry(env: Env, plan: str, item_id: str) -> dict:
    for e in load_eligible(env.paths):
        if isinstance(e, dict) and e.get("plan") == plan and e.get("item") == item_id:
            if not (isinstance(e.get("units"), list) and e["units"]):
                raise SignerError(f"{plan}:{item_id}: manifest entry lists no units (unclassifiable)")
            return e
    raise SignerError(f"{plan}:{item_id} is not in /etc/aq-activation/eligible.json (not eligible)")


# --------------------------------------------------------------------------- request -> signed tuple

def _printable(s: str) -> str:
    """Strip terminal control characters so an agent-written file cannot repaint the owner's screen."""
    return "".join(c if (c == "\n" or c == "\t" or (c.isprintable() and c != "\x7f")) else "?" for c in s)


def _text(b: bytes) -> str:
    return b.decode("utf-8", errors="replace")


def current_closure(paths: Paths) -> str:
    try:
        return os.path.realpath(paths.current_system, strict=True)
    except OSError:
        raise SignerError("cannot resolve the running system closure") from None


def _ids(req: dict) -> tuple[str, str, str]:
    plan, item_id, subject = req.get("plan"), req.get("item_id"), req.get("subject")
    if not (isinstance(plan, str) and _NAME.match(plan) and isinstance(item_id, str) and _NAME.match(item_id)):
        raise SignerError("plan/item_id must match ^[a-z0-9._-]{1,64}$")
    if subject != f"{plan}:{item_id}":
        raise SignerError("subject must be '<plan>:<item_id>'")
    return plan, item_id, subject


_DIMS = ("Integrated", "Turned ON", "Validated", "Observable", "Intervenable", "PM-tracked")
_DIM_LINE = re.compile(r"^\s*(?:[1-6]\s+)?(" + "|".join(re.escape(d) for d in _DIMS) + r"):[ \t]*(.*?)\s*$")
_FIELD = re.compile(r"^([A-Z][A-Za-z-]{2,40}):[ \t]*(.*?)\s*$")
_DEFERRAL = re.compile(r"^deferred:\s*(\S.*?)\s*,\s*(\d{4}-\d{2}-\d{2})$", re.IGNORECASE)
_VERDICTS = ("PASS", "PASS_WITH_FOLLOWUPS")


def _fields(text: str, keys: tuple[str, ...], what: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        m = _FIELD.match(line)
        if m and m.group(1) in keys:
            if m.group(1) in out:
                raise SignerError(f"{what}: duplicate field {m.group(1)}")
            out[m.group(1)] = m.group(2)
    missing = [k for k in keys if not out.get(k)]
    if missing:
        raise SignerError(f"{what}: missing field(s) {', '.join(missing)}")
    return out


def check_attestation(text: str, closure: str) -> str:
    """Structural DoD check; returns the author lane. Refuses MISSING, absent dimensions, undated deferrals,
    a dirty or absent config revision, and a closure other than the running one."""
    if "MISSING:" in text:
        raise SignerError("attestation contains MISSING: lines")
    dims: dict[str, str] = {}
    for line in text.splitlines():
        m = _DIM_LINE.match(line)
        if m:
            if m.group(1) in dims:
                raise SignerError(f"attestation: duplicate dimension {m.group(1)}")
            dims[m.group(1)] = m.group(2)
    for d in _DIMS:
        v = dims.get(d)
        if v is None:
            raise SignerError(f"attestation: dimension '{d}' is absent")
        if v.lower().startswith("deferred"):
            m = _DEFERRAL.match(v)
            if not m:
                raise SignerError(f"attestation: deferral for '{d}' needs a reason and a date: 'deferred: <reason>, YYYY-MM-DD'")
            try:
                datetime.strptime(m.group(2), "%Y-%m-%d")
            except ValueError:
                raise SignerError(f"attestation: deferral date for '{d}' is not a valid date") from None
        elif len(v) < 3 or v.startswith("<"):
            raise SignerError(f"attestation: dimension '{d}' has no evidence")
    f = _fields(text, ("Author-Lane", "System-Closure", "Config-Revision"), "attestation")
    if f["System-Closure"] != closure:
        raise SignerError("attestation System-Closure differs from the running system")
    if not re.fullmatch(r"[0-9a-f]{7,40}", f["Config-Revision"]):
        raise SignerError("attestation Config-Revision must be a clean revision (hex; no -dirty/unknown)")
    return f["Author-Lane"]


def check_review(text: str, closure: str, val_digest: str, author_lane: str) -> None:
    f = _fields(text, ("Review-Disposition", "Reviewer-Lane", "Reviewed-Closure", "Reviewed-Validation-Digest"), "review")
    if f["Review-Disposition"] not in _VERDICTS:
        raise SignerError(f"review verdict {f['Review-Disposition']!r} is not PASS or PASS_WITH_FOLLOWUPS")
    if f["Reviewer-Lane"].casefold() == author_lane.casefold():
        raise SignerError("review lane equals the author lane (self-review)")
    if f["Reviewed-Closure"] != closure or f["Reviewed-Validation-Digest"] != val_digest:
        raise SignerError("review artifact must name the running closure and the validation digest it reviewed")


def build_grant_tuple(env: Env, req: dict, closure: str) -> tuple[dict, dict, str]:
    """Returns (signed tuple, evidence files {name: bytes}, display text). One read of every input."""
    plan, item_id, subject = _ids(req)
    entry = eligible_entry(env, plan, item_id)
    for unit in entry["units"]:
        check_unit(env, unit, entry)
    if req.get("system_closure", closure) != closure:
        raise SignerError("request names a closure different from the running system")
    inv = env.invoker()
    blobs = {}
    for name in _SECTION:
        blobs[name] = safe_read(req.get(f"{name}_path"), invoker=inv)
    att, val, rev = blobs["attestation"], blobs["validation"], blobs["review"]
    att_digest, val_digest, rev_digest = sha256_hex(att), sha256_hex(val), sha256_hex(rev)
    if req.get("attestation_sha256") != att_digest:
        raise SignerError("request attestation_sha256 does not match the attestation file")
    author = check_attestation(_text(att), closure)
    if req.get("review_digest") != rev_digest:
        raise SignerError("request review_digest does not match the review artifact")
    if closure.encode() not in val:
        raise SignerError("validation artifact does not reference the running closure")
    check_review(_text(rev), closure, val_digest, author)
    enable_evidence, detection = req.get("enable_evidence"), req.get("detection_snapshot")
    if not (isinstance(enable_evidence, str) and enable_evidence and isinstance(detection, dict)):
        raise SignerError("enable_evidence (string) and detection_snapshot (object) are required")
    inputs = ac.canonical({
        "system_closure": closure, "enable_evidence": enable_evidence, "detection_snapshot": detection,
        "validation_digest": val_digest, "review_digest": rev_digest})
    baseline = sha256_hex(inputs)
    tup = {"plan": plan, "item_id": item_id, "subject": subject, "attestation_sha256": att_digest,
           "system_closure": closure, "evidence_baseline_sha256": baseline}
    shown = (f"--- {subject}\n manifest entry relied on: {json.dumps(entry, sort_keys=True)}\n"
             f" declared mutable state paths: {entry.get('state_paths', [])}\n"
             f" attestation sha256 {att_digest}\n validation sha256 {val_digest}\n"
             f" review sha256 {rev_digest}\n baseline {baseline}\n enable_evidence: {enable_evidence}\n"
             f" detection_snapshot: {json.dumps(detection, sort_keys=True)}\n author lane {author}\n"
             f"=== attestation ===\n{_text(att)}\n=== validation ===\n{_text(val)}\n=== review ===\n{_text(rev)}\n")
    return tup, {"attestation.md": att, "validation.md": val, "review.md": rev,
                 "baseline-inputs.json": inputs}, _printable(shown)


# --------------------------------------------------------------------------- chain state

def _head_obj(paths: Paths) -> dict:
    return json.loads(_read_text(paths.head))


def recover_head(env: Env, require_pending: bool, signers: list[str], dep: str) -> dict:
    """Recompute the head from the highest segment after revalidating every signature and link.
    `require_pending` (automatic completion): only a segment exactly one beyond the existing head."""
    p = env.paths
    seqs = sorted(int(m.group(1)) for n in os.listdir(p.log) if (m := ac._SEQ_FILE.match(n)))
    if not seqs:
        raise SignerError("no segments to recover from")
    top = seqs[-1]
    if require_pending:
        try:
            head = _head_obj(p)
        except (OSError, ValueError, SignerError):
            raise SignerError("head unreadable; use --recover") from None
        if head.get("seq") != top - 1:
            raise SignerError("head and segments disagree by more than one pending segment; use --recover")
    seg = json.loads((p.log / f"{top}.json").read_text(encoding="utf-8"))
    candidate = {"seq": top, "hash": ac.envelope_hash(seg["envelope"], seg["sig"])}
    with tempfile.TemporaryDirectory() as td:
        cand = Path(td) / "head"
        cand.write_text(json.dumps(candidate))
        state = ac.load_chain(p.log, cand, signers, dep)
    if not state.ok:
        raise SignerError(f"recovery refused, chain does not verify: {state.reason}")
    _write_file(p.head, json.dumps(candidate, sort_keys=True).encode(), 0o644)
    return candidate


def ensure_finalized(env: Env, signers: list[str], dep: str) -> dict:
    """Under the lock: the chain must verify; a single pending segment is completed (crash recovery)."""
    p = env.paths
    state = ac.load_chain(p.log, p.head, signers, dep)
    if state.ok:
        return _head_obj(p)
    if state.reason.startswith("segment beyond head"):
        head = recover_head(env, True, signers, dep)
        env.out(f"completed pending head update to seq {head['seq']}")
        return head
    raise SignerError(f"chain not healthy: {state.reason}. Owner repair: --recover")


def _common(env: Env, dep: str, op: str, request_id: str, seq: int, prev: str) -> dict:
    return {"v": ac.ENVELOPE_VERSION, "domain": ac.DOMAIN, "op": op, "deployment_id": dep,
            "approver": env.approver, "ts": env.now(), "request_id": request_id, "seq": seq, "prev_hash": prev}


def _append(env: Env, key, envelope: dict, evidence: dict[str, bytes] | None) -> str:
    err = ac._check_envelope(envelope)
    if err:
        raise SignerError(f"refusing to sign a malformed envelope: {err}")
    sig = key.sign(ac.signing_input(envelope)).hex()
    p = env.paths
    if evidence:
        d = p.evidence / str(envelope["seq"])
        d.mkdir(parents=True, exist_ok=True)
        for name, data in evidence.items():
            _write_file(d / name, data, 0o644)
        _fsync_dir(d)
        _fsync_dir(p.evidence)
    _write_segment(p.log, envelope["seq"], json.dumps({"envelope": envelope, "sig": sig}, sort_keys=True).encode())
    h = ac.envelope_hash(envelope, sig)
    _write_file(p.head, json.dumps({"seq": envelope["seq"], "hash": h}, sort_keys=True).encode(), 0o644)
    return h


def _require_owner_session(env: Env) -> None:
    if not env.is_tty():
        raise SignerError("an interactive terminal is required (no noninteractive signing)")


def _confirm(env: Env, display: str, envelope: dict) -> None:
    token = sha256_hex(ac.canonical(envelope))[:10]
    if not env.confirm(display, token):
        raise SignerError("not confirmed; nothing written")


# --------------------------------------------------------------------------- commands

def init_chain(env: Env) -> int:
    _require_owner_session(env)
    p = env.paths
    signers, dep = load_signers(p), load_deployment_id(p)
    key = load_key(p, signers)
    with _Lock(p):
        if p.head.exists() or p.head.is_symlink():
            raise SignerError("head exists: refusing to initialise over existing history")
        p.log.mkdir(parents=True, exist_ok=True)
        if any(p.log.iterdir()):
            raise SignerError("log directory is not empty: refusing to initialise (use --recover)")
        env_ = _common(env, dep, "genesis", "genesis0", 0, ac.GENESIS_PREV)
        _confirm(env, _printable(f"INIT CHAIN\n deployment_id: {dep}\n signers: {signers}\n"), env_)
        _append(env, key, env_, None)
    env.out(f"chain initialised for deployment {dep}")
    return 0


def recover(env: Env) -> int:
    _require_owner_session(env)
    p = env.paths
    signers, dep = load_signers(p), load_deployment_id(p)
    with _Lock(p):
        state = ac.load_chain(p.log, p.head, signers, dep)
        if state.ok:
            env.out("chain already healthy; nothing to recover")
            return 0
        token_env = {"recover": state.reason}
        _confirm(env, _printable(f"RECOVER HEAD\n current state: {state.reason}\n"
                                 "all segment signatures and links will be revalidated\n"), token_env)
        head = recover_head(env, False, signers, dep)
    env.out(f"head rewritten to seq {head['seq']} after full revalidation")
    return 0


def sign(env: Env, op: str, request_path: str) -> int:
    _require_owner_session(env)
    p = env.paths
    raw = safe_read(request_path, invoker=env.invoker())
    try:
        req = json.loads(raw)
    except ValueError:
        raise SignerError("request is not valid JSON") from None
    if not isinstance(req, dict) or req.get("op") != op:
        raise SignerError(f"request op does not match command {op!r}")
    rid = req.get("request_id")
    if not isinstance(rid, str) or not _REQUEST_ID.match(rid):
        raise SignerError("request_id must match ^[a-z0-9]{8,40}$")
    signers, dep = load_signers(p), load_deployment_id(p)
    key = load_key(p, signers)
    with _Lock(p):
        head = ensure_finalized(env, signers, dep)
        seq, prev = head["seq"] + 1, head["hash"]
        envelope = _common(env, dep, op, rid, seq, prev)
        evidence: dict[str, bytes] = {}
        if op == "revoke":
            plan, item_id, subject = _ids(req)
            envelope.update(plan=plan, item_id=item_id, subject=subject)
            display = f"REVOKE {subject}\n"
        else:
            closure = current_closure(p)
            if op == "grant":
                tup, files, shown = build_grant_tuple(env, req, closure)
                envelope.update(tup)
                evidence = files
                display = f"GRANT\n{shown}"
            else:
                wave_id, items = req.get("wave_id"), req.get("items")
                if not (isinstance(wave_id, str) and _NAME.match(wave_id) and isinstance(items, list) and items):
                    raise SignerError("wave needs wave_id and a non-empty items list")
                tuples, shown_all = [], []
                for i, sub in enumerate(items):
                    if not isinstance(sub, dict):
                        raise SignerError("wave item must be an object")
                    tup, files, shown = build_grant_tuple(env, sub, closure)
                    tuples.append(tup)
                    shown_all.append(shown)
                    evidence.update({f"{i}-{n}": d for n, d in files.items()})
                tuples.sort(key=lambda t: (t["plan"], t["item_id"], t["subject"]))
                envelope.update(wave_id=wave_id, items=tuples)
                display = f"WAVE-GRANT {wave_id} ({len(tuples)} items)\n" + "".join(shown_all)
        err = ac._check_envelope(envelope)
        if err:
            raise SignerError(f"request produces a malformed envelope: {err}")
        if evidence:
            evidence["envelope-digests.json"] = json.dumps(
                {n: sha256_hex(d) for n, d in sorted(evidence.items())}, sort_keys=True).encode()
        _confirm(env, display + f"seq {seq}  prev {prev}\napprover {env.approver}\n", envelope)
        h = _append(env, key, envelope, evidence or None)
        state = ac.load_chain(p.log, p.head, signers, dep)
    if not state.ok:
        raise SignerError(f"WROTE seq {seq} but the chain does not verify afterwards: {state.reason}")
    env.out(f"signed {op} seq {seq} hash {h[:16]}")
    return 0


def main(argv: list[str], environ: dict | None = None, paths: Paths | None = None, env: Env | None = None) -> int:
    environ = os.environ if environ is None else environ
    approver = environ.get("SUDO_USER", "")
    if not _APPROVER.match(approver):
        approver = "owner"
    env = env or Env(paths=paths or Paths(), approver=approver)
    try:
        if argv == ["--init-id"]:
            print(init_id(env.paths))
            return 0
        if argv == ["--init-key"]:
            print(init_key(env.paths))
            return 0
        if argv == ["--init-chain"]:
            return init_chain(env)
        if argv == ["--recover"]:
            return recover(env)
        if len(argv) == 2 and argv[0] in ("grant", "revoke", "wave-grant"):
            return sign(env, argv[0], argv[1])
        print("usage: aq-activation-sign --init-id | --init-chain | --recover | grant|revoke|wave-grant <request.json>",
              file=sys.stderr)
        return 2
    except SignerError as e:
        print(f"REFUSED: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
