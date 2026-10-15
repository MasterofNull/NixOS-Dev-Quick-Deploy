#!/usr/bin/env python3
"""aq-confine core library (W2-S2a): one bubblewrap launcher, profiles as data.

Design SSOT: .agents/plans/sota-rounding/aq-confine-DESIGN.md (v6 + V1/V2).
Fail closed: the only things this module spawns are bwrap (wrapped in
prlimit), the preflight probe and hardened host-side git. There is no
unconfined fallback and no preexec_fn.

Public API: load_profile, preflight, build_argv, run, host_git, run_host_git,
explain, lint_host_git, append_denial, kill_run.
"""
from __future__ import annotations

import ast
import dataclasses
import hashlib
import json
import os
import re
import shlex
import fcntl
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_PATH = REPO_ROOT / "config" / "confine-profiles" / "profile.schema.json"
GUIDANCE_PATH = REPO_ROOT / "config" / "confine-guidance.json"

EXIT_USAGE = 64
EXIT_UNAVAILABLE = 70
EXIT_PROFILE = 71
EXIT_POLICY = 72
EXIT_TIMEOUT = 124
EXIT_KILLED = 137

SANDBOX_QUARANTINE = "/run/aq-quarantine"
SANDBOX_GUIDANCE = "/run/aqg"
MAX_REFS = 64
OUTPUT_CAP = 4 * 1024 * 1024
POLL_S = 0.5
SIZE_CHECK_INTERVAL_S = 5.0
PREFLIGHT_TTL_S = 60.0
STATE_RETENTION_S = 14 * 86400
TELEMETRY_MAX_BYTES = 50 * 1024 * 1024
TELEMETRY_KEEP = 3
TELEMETRY_LINE_MAX = 4000

_NAME_RE = re.compile(r"^[a-z][a-z0-9-]{0,39}$")
_RUN_ID_RE = re.compile(r"^[a-z0-9]{6,32}$")
_SLUG_RE = re.compile(r"^[a-z0-9-]{1,40}$")
_CLAIM_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_OID_RE = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
_ENV_NAME_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
_ENV_DENY_RE = re.compile(r"(TOKEN|SECRET|KEY|AUTH|PASSW|CRED|SOPS|CERT|SSH)|^(GH_|GITHUB_|AWS_)")
_ENV_GIT_OK = {"GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_AUTHOR_DATE",
               "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL", "GIT_COMMITTER_DATE"}
_ENV_RESERVED = {"PATH", "HOME", "TMPDIR", "IFS", "BASH_ENV", "ENV", "AQ_CONFINED", "AQ_CONFINE_GUIDANCE"}
_DEST_RE = re.compile(r"^[A-Za-z0-9.-]{1,253}(:[0-9]{1,5})?$")
_BAD_PATH_CHARS = re.compile(r"[\x00-\x1f:]")


class ConfineError(Exception):
    """Policy/usage/setup failure carrying exit code and reason."""

    def __init__(self, exit_code: int, reason: str, detail: str = ""):
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.exit_code = exit_code
        self.reason = reason
        self.detail = detail


def _usage(reason: str, detail: str = "") -> ConfineError:
    return ConfineError(EXIT_USAGE, reason, detail)


# ---------------------------------------------------------------------------
# Host facts (injectable so argv construction is pure and golden-testable)
# ---------------------------------------------------------------------------

class HostFacts:
    def exists(self, path: str) -> bool:
        return os.path.exists(path)

    def realpath(self, path: str) -> str:
        return os.path.realpath(path)

    def which(self, name: str) -> Optional[str]:
        return shutil.which(name)

    def uid_tasks(self) -> int:
        """Threads+processes owned by this uid: RLIMIT_NPROC counts per uid."""
        uid = os.getuid()
        total = 0
        try:
            names = os.listdir("/proc")
        except OSError:
            return 0
        for n in names:
            if not n.isdigit():
                continue
            try:
                with open(f"/proc/{n}/status", "r", encoding="utf-8", errors="replace") as fh:
                    txt = fh.read()
            except OSError:
                continue
            m_uid = re.search(r"^Uid:\s+(\d+)", txt, re.M)
            m_thr = re.search(r"^Threads:\s+(\d+)", txt, re.M)
            if m_uid and m_thr and int(m_uid.group(1)) == uid:
                total += int(m_thr.group(1))
        return total

    def python_bin(self) -> str:
        return os.path.realpath(sys.executable)


# ---------------------------------------------------------------------------
# Profiles
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class Profile:
    data: Dict[str, Any]

    def __getattr__(self, key: str) -> Any:
        try:
            return self.__dict__["data"][key]
        except KeyError:
            raise AttributeError(key)


def _profile_dir() -> Path:
    override = os.environ.get("AQ_CONFINE_PROFILE_DIR")
    return Path(override) if override else REPO_ROOT / "config" / "confine-profiles"


def delegation_dir() -> str:
    return os.environ.get("AQ_DELEGATION_DIR") or str(REPO_ROOT / ".agents" / "delegation")


def _expand(value: str) -> str:
    return value.replace("${REPO}", str(REPO_ROOT)).replace("${AQ_DELEGATION_DIR}", delegation_dir())


def _expand_obj(obj: Any) -> Any:
    if isinstance(obj, str):
        return _expand(obj)
    if isinstance(obj, list):
        return [_expand_obj(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _expand_obj(v) for k, v in obj.items()}
    return obj


_TYPES = {"string": str, "boolean": bool, "integer": int, "array": list, "object": dict}


def _check_type(key: str, value: Any, typ: str) -> None:
    ok = isinstance(value, _TYPES[typ]) and not (typ == "integer" and isinstance(value, bool))
    if not ok:
        raise ConfineError(EXIT_PROFILE, "profile-invalid", f"{key}: expected {typ}")


def load_profile(name: str) -> Profile:
    if not _NAME_RE.match(name or ""):
        raise ConfineError(EXIT_PROFILE, "profile-missing", "bad profile name")
    path = _profile_dir() / f"{name}.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ConfineError(EXIT_PROFILE, "profile-missing", name)
    except (OSError, ValueError) as exc:
        raise ConfineError(EXIT_PROFILE, "profile-invalid", f"{name}: {exc}")
    if not isinstance(raw, dict):
        raise ConfineError(EXIT_PROFILE, "profile-invalid", "not an object")
    props = schema["properties"]
    unknown = sorted(set(raw) - set(props))
    if unknown:
        raise ConfineError(EXIT_PROFILE, "profile-invalid", f"unknown keys: {unknown}")
    missing = [k for k in schema["required"] if k not in raw]
    if missing:
        raise ConfineError(EXIT_PROFILE, "profile-invalid", f"missing keys: {missing}")
    for key, value in raw.items():
        spec = props[key]
        _check_type(key, value, spec["type"])
        if "enum" in spec and value not in spec["enum"]:
            raise ConfineError(EXIT_PROFILE, "profile-invalid", f"{key}: {value!r} not allowed")
        for sub, subtype in spec.get("keys", {}).items():
            if sub in value:
                _check_type(f"{key}.{sub}", value[sub], subtype)
        if "keys" in spec and set(value) - set(spec["keys"]):
            raise ConfineError(EXIT_PROFILE, "profile-invalid", f"{key}: unknown subkeys")
    if raw["name"] != name:
        raise ConfineError(EXIT_PROFILE, "profile-invalid", "name does not match file")
    if raw["unshare"] != ["all"]:
        raise ConfineError(EXIT_PROFILE, "profile-invalid", "unshare must be ['all'] (net is never shared)")
    if raw["git_refs"] == "heads":
        raise ConfineError(EXIT_PROFILE, "profile-invalid", "git_refs 'heads' is reserved (not implemented in S2a)")
    if raw["egress"].get("mode", "none") != "none":
        raise ConfineError(EXIT_PROFILE, "profile-invalid", "egress mode must be 'none' in S2a")
    if raw["net_default"] == "loopback" and raw["net_ceiling"] == "none":
        raise ConfineError(EXIT_PROFILE, "profile-invalid", "net_default exceeds net_ceiling")
    if raw["git"] == "worktree" and not raw["needs_worktree"]:
        raise ConfineError(EXIT_PROFILE, "profile-invalid", "git worktree requires needs_worktree")
    nested = bool(raw.get("allow_nested_userns", False))
    if not raw["disable_userns"] and not nested:
        raise ConfineError(EXIT_PROFILE, "profile-invalid", "disable_userns false needs allow_nested_userns")
    if nested and raw["git"] == "worktree":
        raise ConfineError(EXIT_PROFILE, "profile-invalid", "nested userns is never allowed with a worktree profile")
    if not raw["home"].startswith("/") or ".." in raw["home"].split("/"):
        raise ConfineError(EXIT_PROFILE, "profile-invalid", "home must be absolute")
    for n in raw["env_allow"]:
        if not isinstance(n, str):
            raise ConfineError(EXIT_PROFILE, "profile-invalid", "env_allow entries must be strings")
        try:
            check_env_name(n)
        except ConfineError as exc:
            raise ConfineError(EXIT_PROFILE, "profile-invalid", f"env_allow {n}: {exc.reason}")
    for k, v in raw["env_base"].items():
        if not _ENV_NAME_RE.match(k) or not isinstance(v, str):
            raise ConfineError(EXIT_PROFILE, "profile-invalid", f"env_base {k}")
    for lst in ("ro_system", "path_from_system", "rw_allowed_roots"):
        if not all(isinstance(x, str) for x in raw[lst]):
            raise ConfineError(EXIT_PROFILE, "profile-invalid", f"{lst} entries must be strings")
    return Profile(_expand_obj(raw))


def check_env_name(name: str) -> None:
    if not _ENV_NAME_RE.match(name):
        raise _usage("env-name-invalid", name)
    if name in _ENV_GIT_OK:
        return
    if (_ENV_DENY_RE.search(name) or name in _ENV_RESERVED or name.startswith("LD_")
            or name.startswith("GIT_") or name.startswith("AQ_")):
        raise _usage("env-name-denied", name)


# ---------------------------------------------------------------------------
# Paths, secrets policy
# ---------------------------------------------------------------------------

def _secret_prefixes() -> List[str]:
    homes = {os.path.expanduser("~")}
    try:
        import pwd
        homes.add(pwd.getpwuid(os.getuid()).pw_dir)
    except Exception:
        pass
    out = ["/run/secrets"]
    for h in sorted(homes):
        out += [f"{h}/.ssh", f"{h}/.gnupg", f"{h}/.config/sops"]
    return out


def _under(path: str, prefix: str) -> bool:
    return path == prefix or path.startswith(prefix.rstrip("/") + "/")


_PROTECTED_TREES = ("/proc", "/sys", "/dev", "/etc", "/run", "/var/run", "/nix/var", "/root", "/mnt", "/media", "/boot")


def _homes() -> List[str]:
    homes = {os.path.expanduser("~")}
    try:
        import pwd
        homes.add(pwd.getpwuid(os.getuid()).pw_dir)
    except Exception:
        pass
    return sorted(h for h in homes if h.startswith("/") and h != "/")


def path_is_protected(cand: str) -> bool:
    """True if cand is, is inside, or is an ANCESTOR of a protected location
    (secrets, session sockets, nix daemon socket, $HOME itself, '/')."""
    if cand == "/":
        return True
    points = _secret_prefixes() + list(_PROTECTED_TREES)
    if any(_under(cand, p) or _under(p, cand) for p in points):
        return True
    return any(cand == h or _under(h, cand) for h in _homes())


def find_special(path: str, max_entries: int = 200000, max_depth: int = 48) -> str:
    """Bounded lstat walk. Returns '' if clean, else a reason: a socket, FIFO or
    device node (filesystem unix sockets cross the netns boundary), or a limit/error
    (fail closed)."""
    n = 0
    stack = [(path, 0)]
    while stack:
        d, depth = stack.pop()
        try:
            st = os.lstat(d)
        except OSError:
            return f"unreadable: {d}"
        if stat.S_ISSOCK(st.st_mode) or stat.S_ISFIFO(st.st_mode) or stat.S_ISCHR(st.st_mode) or stat.S_ISBLK(st.st_mode):
            return f"special file: {d}"
        if not stat.S_ISDIR(st.st_mode):
            continue
        if depth >= max_depth:
            return "too deep"
        try:
            entries = list(os.scandir(d))
        except OSError:
            return f"unreadable: {d}"
        for e in entries:
            n += 1
            if n > max_entries:
                return "too many entries"
            stack.append((os.path.join(d, e.name), depth + 1))
    return ""


def check_user_path(path: str, facts: HostFacts, *, must_exist: bool = True, scan: bool = True) -> str:
    """--ro/--rw/--worktree argument policy: absolute, normalized, no symlinks, not
    protected (secrets, ancestors of them, $HOME, /run, /etc ...), and no socket,
    FIFO or device node anywhere in the subtree. Returns the validated path."""
    if not isinstance(path, str) or not path.startswith("/") or _BAD_PATH_CHARS.search(path):
        raise _usage("path-invalid", repr(path)[:80])
    for cand in (path, facts.realpath(path)):
        if path_is_protected(cand):
            raise _usage("path-protected", path)
    if path != os.path.normpath(path) or path == "/":
        raise _usage("path-not-normalized", path)
    real = facts.realpath(path)
    if real != path:
        raise _usage("path-symlink", path)
    if must_exist and not facts.exists(path):
        raise _usage("path-missing", path)
    if scan and must_exist:
        why = find_special(path)
        if why:
            raise _usage("path-special", f"{path}: {why}")
    return path


def _checked_roots(extra: str, var: str) -> List[str]:
    out = []
    for r in [x for x in extra.split(":") if x]:
        if not r.startswith("/") or os.path.normpath(r) != r or path_is_protected(r):
            raise _usage("root-invalid", f"{var} entry {r!r} is not an allowed root")
        out.append(r)
    return out


def worktree_roots() -> List[str]:
    roots = [os.path.join(delegation_dir(), "worktrees"), "/tmp"]
    return roots + _checked_roots(os.environ.get("AQ_CONFINE_WORKTREE_ROOTS", ""), "AQ_CONFINE_WORKTREE_ROOTS")


def ro_roots(profile: "Profile") -> List[str]:
    return list(profile.ro_allowed_roots) + _checked_roots(os.environ.get("AQ_CONFINE_RO_ROOTS", ""), "AQ_CONFINE_RO_ROOTS")


# ---------------------------------------------------------------------------
# Hardened host-side git (the only sanctioned way to run git on a confined tree)
# ---------------------------------------------------------------------------

_HOST_GIT_CONFIG = (
    ("core.fsmonitor", "false"),
    ("core.hooksPath", "/dev/null"),
    ("core.attributesFile", "/dev/null"),
    ("core.excludesFile", "/dev/null"),
    ("diff.external", ""),
    ("protocol.allow", "never"),
    ("safe.bareRepository", "explicit"),
    ("core.askPass", ""),
    ("gc.auto", "0"),
)


def _git_bin() -> str:
    found = shutil.which("git")
    if not found:
        raise ConfineError(EXIT_UNAVAILABLE, "git-missing")
    return os.path.realpath(found)


def host_git(args: Sequence[str], *, git_dir: str, work_tree: Optional[str] = None,
             alternates: Optional[Sequence[str]] = None) -> Tuple[List[str], Dict[str, str]]:
    """Build (argv, env) for a hardened host git call. Always explicit git dir,
    never cwd-selected; run it with cwd='/' (run_host_git does)."""
    argv = [_git_bin(), "--no-pager", "--git-dir", git_dir]
    if work_tree:
        argv += ["--work-tree", work_tree]
    for key, value in _HOST_GIT_CONFIG:
        argv += ["-c", f"{key}={value}"]
    argv += list(args)
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": "/nonexistent",
        "LC_ALL": "C",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_ATTR_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_ASKPASS": "",
        "SSH_ASKPASS": "",
        "GIT_PAGER": "cat",
        "GIT_OPTIONAL_LOCKS": "0",
    }
    if alternates:
        env["GIT_ALTERNATE_OBJECT_DIRECTORIES"] = ":".join(alternates)
    return argv, env


def run_host_git(args: Sequence[str], *, git_dir: str, work_tree: Optional[str] = None,
                 alternates: Optional[Sequence[str]] = None, input: Optional[bytes] = None,
                 timeout: float = 300.0) -> "subprocess.CompletedProcess[bytes]":
    argv, env = host_git(args, git_dir=git_dir, work_tree=work_tree, alternates=alternates)
    return subprocess.run(argv, input=input, capture_output=True, env=env, cwd="/", timeout=timeout, check=False)


def _git_out(args: Sequence[str], git_dir: str) -> str:
    cp = run_host_git(args, git_dir=git_dir)
    if cp.returncode != 0:
        raise ConfineError(EXIT_UNAVAILABLE, "git-failed", (cp.stderr or b"")[:200].decode("utf-8", "replace"))
    return cp.stdout.decode("utf-8", "replace")


# ---------------------------------------------------------------------------
# Git layout, snapshots
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class GitLayout:
    worktree: str
    admin: str
    common: str
    claim: str
    slug: str

    @property
    def ns_ref_dir(self) -> str:
        return f"{self.common}/refs/heads/aq/{self.claim}"

    @property
    def ns_log_dir(self) -> str:
        return f"{self.common}/logs/refs/heads/aq/{self.claim}"

    @property
    def ns_prefix(self) -> str:
        return f"refs/heads/aq/{self.claim}/"


def _read_small(path: str, limit: int = 4096) -> Optional[str]:
    try:
        st = os.lstat(path)
        if not stat.S_ISREG(st.st_mode):
            return None
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read(limit)
    except OSError:
        return None


def resolve_layout(worktree: str, facts: HostFacts) -> GitLayout:
    wt = check_user_path(worktree, facts, scan=False)
    why = find_special(wt, max_entries=2_000_000, max_depth=128)
    if why:
        raise _usage("path-special", f"{wt}: {why}")
    if not any(_under(wt, r) for r in worktree_roots()):
        raise _usage("worktree-root", "worktree is not under an allowed root")
    if not os.path.isdir(wt):
        raise _usage("worktree-not-dir", wt)
    dotgit = _read_small(os.path.join(wt, ".git"))
    if dotgit is None or not dotgit.startswith("gitdir: "):
        raise _usage("worktree-not-linked", "'.git' must be a gitdir file (linked worktree)")
    admin = facts.realpath(dotgit[len("gitdir: "):].strip())
    if os.path.basename(os.path.dirname(admin)) != "worktrees":
        raise _usage("worktree-layout", "admin dir is not <common>/worktrees/<name>")
    common = os.path.dirname(os.path.dirname(admin))
    back = _read_small(os.path.join(admin, "gitdir"))
    if back is None or facts.realpath(back.strip()) != os.path.join(wt, ".git"):
        raise _usage("worktree-layout", "admin gitdir does not point back at the worktree")
    cdir = _read_small(os.path.join(admin, "commondir"))
    if cdir is None or facts.realpath(os.path.join(admin, cdir.strip())) != common:
        raise _usage("worktree-layout", "commondir mismatch")
    for p in (wt, admin, common):
        if _BAD_PATH_CHARS.search(p):
            raise _usage("path-invalid", "control character or ':' in path")
        try:
            if os.lstat(p).st_uid != os.getuid():
                raise _usage("worktree-owner", f"{p} is not owned by the current uid")
        except OSError:
            raise _usage("worktree-layout", "cannot stat " + p)
    head = _read_small(os.path.join(admin, "HEAD")) or ""
    m = re.match(r"^ref: refs/heads/aq/([^/\s]+)/([^/\s]+)\n?$", head)
    if not m or not _CLAIM_RE.match(m.group(1)) or ".." in m.group(1) or not _SLUG_RE.match(m.group(2)):
        raise _usage("worktree-branch", "worktree HEAD must be refs/heads/aq/<claim>/<slug>")
    wcfg = run_host_git(["config", "--get", "extensions.worktreeConfig"], git_dir=common)
    if wcfg.stdout.decode().strip().lower() in ("true", "1", "yes", "on"):
        raise _usage("worktree-config-ext", "extensions.worktreeConfig repositories are refused")
    return GitLayout(wt, admin, common, m.group(1), m.group(2))


def _sha256_file(path: str) -> Optional[str]:
    try:
        st = os.lstat(path)
        if stat.S_ISLNK(st.st_mode):
            return "symlink:" + os.readlink(path)
        if not stat.S_ISREG(st.st_mode):
            return "special"
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def _hooks_listing(common: str) -> List[List[Any]]:
    out: List[List[Any]] = []
    hooks = os.path.join(common, "hooks")
    try:
        names = sorted(os.listdir(hooks))
    except OSError:
        return out
    for n in names:
        p = os.path.join(hooks, n)
        try:
            st = os.lstat(p)
        except OSError:
            continue
        out.append([n, stat.S_IMODE(st.st_mode), _sha256_file(p)])
    return out


def snapshot(layout: GitLayout) -> Dict[str, Any]:
    refs: Dict[str, List[str]] = {}
    txt = _git_out(["for-each-ref", "--format=%(refname) %(objectname) %(objecttype)"], layout.common)
    for line in txt.splitlines():
        parts = line.split(" ")
        if len(parts) == 3:
            refs[parts[0]] = [parts[1], parts[2]]
    a = layout.admin
    return {
        "refs": refs,
        "main_head": _sha256_file(os.path.join(layout.common, "HEAD")),
        "admin": {n: _sha256_file(os.path.join(a, n)) for n in ("HEAD", "commondir", "gitdir", "config.worktree")},
        "config": _sha256_file(os.path.join(layout.common, "config")),
        "packed_refs": _sha256_file(os.path.join(layout.common, "packed-refs")),
        "worktree_dotgit": _sha256_file(os.path.join(layout.worktree, ".git")),
        "index": _sha256_file(os.path.join(a, "index")),
        "hooks": _hooks_listing(layout.common),
    }


# ---------------------------------------------------------------------------
# Hostile-directory helpers (never follow symlinks)
# ---------------------------------------------------------------------------

def scan_tree(root: str, cap: Optional[int] = None) -> Tuple[int, bool, List[str]]:
    """lstat walk. Returns (bytes in regular files, cap_exceeded, embedded .git
    directories relative to root). Never follows symlinks."""
    total = 0
    embedded: List[str] = []
    stack = [""]
    while stack:
        rel = stack.pop()
        d = os.path.join(root, rel) if rel else root
        try:
            it = list(os.scandir(d))
        except OSError:
            continue
        for e in it:
            try:
                st = e.stat(follow_symlinks=False)
            except OSError:
                continue
            r = os.path.join(rel, e.name) if rel else e.name
            if stat.S_ISDIR(st.st_mode):
                if e.name == ".git":
                    embedded.append(r)
                    continue
                stack.append(r)
            elif stat.S_ISREG(st.st_mode):
                total += st.st_size
                if cap is not None and total > cap:
                    return total, True, embedded
            elif e.name == ".git" and rel:
                embedded.append(r)
    return total, False, embedded


def _rmtree_nofollow(path: str) -> None:
    try:
        st = os.lstat(path)
    except OSError:
        return
    if stat.S_ISLNK(st.st_mode) or not stat.S_ISDIR(st.st_mode):
        try:
            os.unlink(path)
        except OSError:
            pass
        return
    shutil.rmtree(path, ignore_errors=True)


def _clear_dir(path: str) -> None:
    try:
        names = os.listdir(path)
    except OSError:
        return
    for n in names:
        _rmtree_nofollow(os.path.join(path, n))


_OBJ_DIR_RE = re.compile(r"^[0-9a-f]{2}$")
_OBJ_FILE_RE = re.compile(r"^[0-9a-f]{38,62}$")
_PACK_RE = re.compile(r"^pack-[0-9a-f]{40,64}\.(pack|idx)$")


def sanitize_quarantine(q: str) -> Tuple[int, int]:
    """Treat the quarantine as hostile: keep only loose objects and packs that are
    regular single-link files; remove everything else (info/alternates, symlinks,
    temp files) without following links. Returns (kept_bytes, junk_removed)."""
    kept = junk = 0
    try:
        top = list(os.scandir(q))
    except OSError:
        return 0, 0
    for e in top:
        p = os.path.join(q, e.name)
        try:
            st = os.lstat(p)
        except OSError:
            continue
        if stat.S_ISDIR(st.st_mode) and (_OBJ_DIR_RE.match(e.name) or e.name == "pack"):
            pat = _OBJ_FILE_RE if e.name != "pack" else _PACK_RE
            for f in os.scandir(p):
                fp = os.path.join(p, f.name)
                try:
                    fst = os.lstat(fp)
                except OSError:
                    continue
                if stat.S_ISREG(fst.st_mode) and pat.match(f.name):
                    kept += fst.st_size
                else:
                    _rmtree_nofollow(fp)
                    junk += 1
        else:
            _rmtree_nofollow(p)
            junk += 1
    return kept, junk


def validate_ref_dir(d: str) -> Tuple[Dict[str, str], List[Dict[str, str]]]:
    """Validate the host-owned private ref directory. Returns (accepted name->oid,
    problems)."""
    accepted: Dict[str, str] = {}
    problems: List[Dict[str, str]] = []
    try:
        entries = list(os.scandir(d))
    except OSError as exc:
        return accepted, [{"kind": "ref-foreign-changed", "detail": f"unreadable: {exc.strerror}"}]
    if len(entries) > MAX_REFS:
        problems.append({"kind": "ref-foreign-changed", "detail": f"{len(entries)} entries exceeds cap {MAX_REFS}"})
        entries = entries[:MAX_REFS]
    for e in entries:
        try:
            st = os.lstat(os.path.join(d, e.name))
        except OSError:
            continue
        if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1:
            problems.append({"kind": "ref-foreign-changed", "ref": e.name[:60], "detail": "not a single-link regular file"})
            continue
        if not _SLUG_RE.match(e.name):
            problems.append({"kind": "ref-foreign-changed", "ref": e.name[:60], "detail": "bad ref name"})
            continue
        try:
            fd = os.open(os.path.join(d, e.name), os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(fd, "r", encoding="ascii", errors="replace") as fh:
                content = fh.read(200)
        except OSError:
            problems.append({"kind": "ref-foreign-changed", "ref": e.name, "detail": "unreadable"})
            continue
        oid = content.strip()
        if not _OID_RE.match(oid) or content != oid + "\n":
            problems.append({"kind": "ref-foreign-changed", "ref": e.name, "detail": "not a single object name"})
            continue
        accepted[e.name] = oid
    return accepted, problems


# ---------------------------------------------------------------------------
# Object import (V2): rev-list -> pack-objects -> index-pack --strict -> connectivity
# ---------------------------------------------------------------------------

def _outside_oids(layout: GitLayout) -> List[str]:
    txt = _git_out(["for-each-ref", "--format=%(refname) %(objectname)"], layout.common)
    seen: List[str] = []
    for line in txt.splitlines():
        name, _, oid = line.partition(" ")
        if name.startswith(layout.ns_prefix) or not _OID_RE.match(oid):
            continue
        if oid not in seen:
            seen.append(oid)
    return seen


def import_objects(layout: GitLayout, quarantine: str, tip: str, outside: List[str]) -> Optional[str]:
    """Return None on success, else a short failure reason. Real store gets objects
    only through index-pack --strict (names recomputed from content)."""
    stdin = (tip + "\n" + "".join(f"^{o}\n" for o in outside)).encode()
    try:
        rl = run_host_git(["rev-list", "--objects", "--missing=error", "--stdin"], git_dir=layout.common,
                          alternates=[quarantine], input=stdin)
        if rl.returncode != 0:
            return "rev-list failed: " + rl.stderr[:160].decode("utf-8", "replace")
        names = "".join(l.split(" ", 1)[0] + "\n" for l in rl.stdout.decode("utf-8", "replace").splitlines() if l)
        if names:
            pa_argv, pa_env = host_git(["pack-objects", "--stdout", "-q"], git_dir=layout.common, alternates=[quarantine])
            ip_argv, ip_env = host_git(["index-pack", "--stdin", "--strict"], git_dir=layout.common)
            err2 = tempfile.TemporaryFile()
            p2 = subprocess.Popen(pa_argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=err2,
                                  env=pa_env, cwd="/")
            p3 = subprocess.Popen(ip_argv, stdin=p2.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  env=ip_env, cwd="/")
            p2.stdout.close()
            try:
                p2.stdin.write(names.encode())
                p2.stdin.close()
            except OSError:
                pass
            try:
                _, e3 = p3.communicate(timeout=300)
                p2.wait(timeout=30)
            except subprocess.TimeoutExpired:
                p2.kill()
                p3.kill()
                raise
            err2.seek(0)
            e2 = err2.read(400)
            if p2.returncode != 0:
                return "pack-objects failed: " + e2[:160].decode("utf-8", "replace")
            if p3.returncode != 0:
                return "index-pack --strict failed: " + e3[:160].decode("utf-8", "replace")
        # Connectivity against the real store alone (no alternates).
        cn = run_host_git(["rev-list", "--objects", "--missing=error", "--stdin"], git_dir=layout.common, input=stdin)
        if cn.returncode != 0:
            return "connectivity failed: " + cn.stderr[:160].decode("utf-8", "replace")
        ty = run_host_git(["cat-file", "-t", tip], git_dir=layout.common)
        if ty.stdout.decode().strip() != "commit":
            return "tip is not a commit"
    except subprocess.TimeoutExpired:
        return "import timed out"
    return None


# ---------------------------------------------------------------------------
# Plan / argv (pure given HostFacts)
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class RunPaths:
    run_dir: str
    sandbox_dir: str
    quarantine: str
    refs: str
    logs: str
    guidance: str
    admin: str

    @staticmethod
    def for_run(state_dir: str, run_id: str) -> "RunPaths":
        rd = os.path.join(state_dir, "runs", run_id)
        sb = os.path.join(rd, "sandbox")
        return RunPaths(rd, sb, os.path.join(sb, "quarantine"), os.path.join(sb, "refs"),
                        os.path.join(sb, "logs"), os.path.join(rd, "guidance"), os.path.join(sb, "admin"))


@dataclasses.dataclass
class Plan:
    profile: Profile
    run_id: str
    bwrap: str
    prlimit: str
    paths: RunPaths
    layout: Optional[GitLayout]
    cwd: str
    ro: List[str]
    rw: List[str]
    env: Dict[str, str]
    net: str
    nested_userns: bool
    cmd: List[str]
    limits: Dict[str, int]
    timeout_s: int
    status_fd: Optional[int] = None
    extra_ro_dirs: List[str] = dataclasses.field(default_factory=list)
    scratch: bool = False


def state_dir() -> str:
    explicit = os.environ.get("AQ_CONFINE_STATE_DIR")
    if explicit:
        return explicit
    base = os.environ.get("XDG_STATE_HOME") or os.path.join(os.path.expanduser("~"), ".local", "state")
    return os.path.join(base, "aq-confine")


def _resolve_path_dirs(profile: Profile, facts: HostFacts) -> Tuple[List[str], List[str]]:
    dirs: List[str] = []
    for name in profile.path_from_system:
        found = facts.which(name)
        if not found:
            continue
        d = os.path.dirname(facts.realpath(found))
        if path_is_protected(d):
            continue
        if d not in dirs:
            dirs.append(d)
    extra = [d for d in dirs if not any(_under(d, s) for s in profile.ro_system)]
    return dirs, extra


def build_env(profile: Profile, caller_env: Dict[str, str], explicit: Sequence[str],
              layout: Optional[GitLayout], path_dirs: List[str], facts: HostFacts) -> Dict[str, str]:
    env: Dict[str, str] = dict(profile.env_base)
    for n in profile.env_allow:
        if n in caller_env:
            env[n] = caller_env[n]
    for n in explicit:
        check_env_name(n)
        if n in caller_env:
            env[n] = caller_env[n]
    sys_path = [d for d in ("/usr/bin", "/bin") if d in profile.ro_system or any(_under(d, s) for s in profile.ro_system)]
    sys_path = [d for d in sys_path if facts.exists(d)]
    env["PATH"] = ":".join(path_dirs + sys_path) or "/usr/bin:/bin"
    env["HOME"] = profile.home
    env["TMPDIR"] = profile.home + "/tmp"
    env["AQ_CONFINED"] = profile.name
    if profile.guidance:
        env["AQ_CONFINE_GUIDANCE"] = SANDBOX_GUIDANCE + "/GUIDANCE.md"
    if layout:
        cfg = [("gc.auto", "0"), ("maintenance.auto", "false"), ("safe.directory", layout.worktree),
               ("core.hooksPath", "/dev/null"), ("core.fsmonitor", "false"), ("commit.gpgsign", "false"),
               ("safe.bareRepository", "explicit"),
               ("receive.autogc", "false")]
        env.update({
            "GIT_DIR": layout.admin,
            "GIT_WORK_TREE": layout.worktree,
            "GIT_OBJECT_DIRECTORY": SANDBOX_QUARANTINE,
            "GIT_ALTERNATE_OBJECT_DIRECTORIES": layout.common + "/objects",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_ATTR_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_CONFIG_COUNT": str(len(cfg)),
        })
        for i, (k, v) in enumerate(cfg):
            env[f"GIT_CONFIG_KEY_{i}"] = k
            env[f"GIT_CONFIG_VALUE_{i}"] = v
    return env


_LIMIT_FLAGS = (("as", "--as"), ("cpu", "--cpu"), ("fsize", "--fsize"), ("nofile", "--nofile"),
                ("nproc", "--nproc"), ("core", "--core"))


def build_argv(plan: Plan, facts: Optional[HostFacts] = None) -> List[str]:
    """Full launch argv: prlimit(1) wrapping bwrap. Pure given the plan."""
    p = plan.profile
    L = plan.layout
    a: List[str] = [plan.bwrap, "--unshare-all", "--unshare-user", "--unshare-net", "--die-with-parent",
                    "--new-session", "--clearenv"]
    if not plan.nested_userns:
        a += ["--disable-userns", "--assert-userns-disabled"]
    if plan.status_fd is not None:
        a += ["--json-status-fd", str(plan.status_fd)]
    for k in sorted(plan.env):
        a += ["--setenv", k, plan.env[k]]
    # 1. scratch and system
    for s in p.ro_system:
        if facts is None or facts.exists(s):
            a += ["--ro-bind", s, s]
    for d in plan.extra_ro_dirs:
        a += ["--ro-bind", d, d]
    a += ["--proc", "/proc", "--dev", "/dev", "--size", str(p.tmp_size), "--tmpfs", "/tmp",
          "--size", str(p.home_size), "--tmpfs", p.home, "--dir", p.home + "/tmp"]
    if plan.scratch:
        a += ["--bind", plan.paths.run_dir + "/scratch", "/scratch"]
    if p.guidance:
        a += ["--ro-bind", plan.paths.guidance, SANDBOX_GUIDANCE]
    for d in plan.ro:
        a += ["--ro-bind", d, d]
    for d in plan.rw:
        a += ["--bind", d, d]
    if L:
        # 2-3. common dir read-only, admin dir writable with read-only overlays
        a += ["--ro-bind", L.common, L.common]
        a += ["--bind", plan.paths.admin, L.admin]   # private copy: index/reflog may name quarantine-only objects
        for n in ("commondir", "gitdir", "HEAD"):
            a += ["--ro-bind", f"{L.admin}/{n}", f"{L.admin}/{n}"]
        # 4. object quarantine
        a += ["--bind", plan.paths.quarantine, SANDBOX_QUARANTINE]
        # 5. private ref and reflog directories over the real namespace paths
        a += ["--bind", plan.paths.refs, L.ns_ref_dir]
        a += ["--bind", plan.paths.logs, L.ns_log_dir]
        # 6. worktree, then the .git file overlay (must follow the worktree bind)
        a += ["--bind", L.worktree, L.worktree]
        a += ["--ro-bind", f"{L.worktree}/.git", f"{L.worktree}/.git"]
    if p.readonly_root:
        a += ["--remount-ro", "/tmp", "--remount-ro", "/"]
    a += ["--chdir", L.worktree if L else (plan.cwd or p.home)]
    a += ["--"] + plan.cmd
    pre = [plan.prlimit]
    for key, flag in _LIMIT_FLAGS:
        if key in plan.limits:
            pre.append(f"{flag}={plan.limits[key]}")
    return pre + ["--"] + a


def explain_text(plan: Plan, facts: Optional[HostFacts] = None) -> str:
    argv = build_argv(plan, facts)
    lines = [f"# aq-confine --explain profile={plan.profile.name} net={plan.net} timeout_s={plan.timeout_s}",
             "ARGV"] + [shlex.quote(x) if x != "" else "''" for x in argv]
    lines += ["ENV-NAMES"] + sorted(plan.env)
    return "\n".join(lines) + "\n"


def make_plan(profile: Profile, cmd: Sequence[str], *, worktree: Optional[str] = None, net: Optional[str] = None,
              ro: Sequence[str] = (), rw: Sequence[str] = (), env_allow: Sequence[str] = (),
              timeout: Optional[int] = None, rlimit_as: Optional[int] = None, run_id: Optional[str] = None,
              caller_env: Optional[Dict[str, str]] = None, allow_nested_userns: bool = False,
              facts: Optional[HostFacts] = None, bwrap: Optional[str] = None, prlimit: Optional[str] = None,
              state: Optional[str] = None, scratch: bool = False) -> Plan:
    facts = facts or HostFacts()
    if not cmd or not all(isinstance(c, str) for c in cmd):
        raise _usage("no-command")
    net = net or profile.net_default
    if net not in ("none", "loopback"):
        raise _usage("net-invalid", net)
    if net == "loopback" and profile.net_ceiling == "none":
        raise _usage("net-above-ceiling", f"profile {profile.name} allows only net=none")
    if allow_nested_userns and not profile.data.get("allow_nested_userns", False):
        raise _usage("nested-userns-denied", profile.name)
    run_id = run_id or uuid.uuid4().hex[:12]
    if not _RUN_ID_RE.match(run_id):
        raise _usage("run-id-invalid")
    layout = None
    if profile.needs_worktree:
        if not worktree:
            raise _usage("worktree-required", profile.name)
        layout = resolve_layout(worktree, facts)
    elif worktree:
        raise _usage("worktree-unexpected", profile.name)
    ro_l = []
    for x in ro:
        x = check_user_path(x, facts)
        if not any(_under(x, _expand(r)) for r in ro_roots(profile)):
            raise _usage("ro-not-allowed", x)
        ro_l.append(x)
    if scratch and not profile.scratch:
        raise _usage("scratch-not-allowed", profile.name)
    rw_l = []
    for x in rw:
        x = check_user_path(x, facts)
        if not any(_under(x, _expand(r)) and x != _expand(r).rstrip("/") for r in profile.rw_allowed_roots):
            raise _usage("rw-not-allowed", x)
        rw_l.append(x)
    path_dirs, extra = _resolve_path_dirs(profile, facts)
    env = build_env(profile, caller_env if caller_env is not None else dict(os.environ), env_allow, layout, path_dirs, facts)
    limits = dict(profile.limits)
    if rlimit_as is not None:
        if rlimit_as <= 0:
            raise _usage("rlimit-invalid")
        limits["as"] = min(limits["as"], rlimit_as) if "as" in limits else rlimit_as
    if "nproc" in limits:  # RLIMIT_NPROC is per uid: profile value is headroom above current tasks
        limits["nproc"] = limits["nproc"] + facts.uid_tasks()
    tmo = profile.timeout_s if timeout is None else min(profile.timeout_s, int(timeout))
    if tmo <= 0:
        raise _usage("timeout-invalid")
    bw = bwrap or resolve_bwrap()
    pl = prlimit or resolve_prlimit()
    paths = RunPaths.for_run(state or state_dir(), run_id)
    if scratch:
        env["AQ_CONFINE_SCRATCH"] = "/scratch"
    return Plan(profile, run_id, bw or "", pl or "", paths, layout, "", ro_l, rw_l, env, net,
                allow_nested_userns, list(cmd), limits, tmo, extra_ro_dirs=extra, scratch=scratch)


# ---------------------------------------------------------------------------
# Preflight (fail closed)
# ---------------------------------------------------------------------------

def resolve_bwrap() -> Optional[str]:
    cand = os.environ.get("BWRAP_PATH")
    if cand:
        return cand if os.path.isfile(cand) and os.access(cand, os.X_OK) else None
    return shutil.which("bwrap")


def resolve_prlimit() -> Optional[str]:
    return shutil.which("prlimit")


@dataclasses.dataclass
class PreflightResult:
    ok: bool
    reason: str = ""
    detail: str = ""


_pf_cache: Dict[Tuple[str, str], Tuple[float, PreflightResult]] = {}

_DEFAULT_RO = ["/nix/store", "/usr", "/bin", "/lib", "/lib64", "/etc/alternatives"]


def preflight_argv(bwrap: str, python_bin: str, facts: HostFacts, ro_system: Sequence[str] = _DEFAULT_RO) -> List[str]:
    a = [bwrap, "--unshare-all", "--unshare-user", "--unshare-net", "--disable-userns", "--die-with-parent",
         "--new-session", "--clearenv"]
    bound: List[str] = []
    for s in ro_system:
        if facts.exists(s):
            a += ["--ro-bind", s, s]
            bound.append(s)
    if not any(_under(python_bin, s) for s in bound):
        prefix = os.path.dirname(os.path.dirname(python_bin))
        a += ["--ro-bind", prefix, prefix]
    a += ["--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp", "--", python_bin, "-c", "pass"]
    return a


def preflight(*, use_cache: bool = True, facts: Optional[HostFacts] = None) -> PreflightResult:
    facts = facts or HostFacts()
    bwrap = resolve_bwrap()
    if not bwrap:
        return PreflightResult(False, "bwrap-missing", "no usable bwrap (BWRAP_PATH or PATH)")
    if not resolve_prlimit():
        return PreflightResult(False, "prlimit-missing", "prlimit(1) not found")
    py = facts.python_bin()
    if not py or not os.path.isfile(py):
        return PreflightResult(False, "python-bin-missing")
    key = (bwrap, py)
    now = time.monotonic()
    if use_cache and key in _pf_cache and now - _pf_cache[key][0] < PREFLIGHT_TTL_S:
        return _pf_cache[key][1]
    try:
        cp = subprocess.run(preflight_argv(bwrap, py, facts), capture_output=True, timeout=15, check=False,
                            env={"PATH": "/nonexistent"}, stdin=subprocess.DEVNULL)
        rc, err = cp.returncode, cp.stderr[:200].decode("utf-8", "replace").strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        rc, err = 1, str(exc)
    if rc == 0:
        res = PreflightResult(True)
    else:
        extra = []
        for p in ("/proc/sys/kernel/apparmor_restrict_unprivileged_userns", "/proc/sys/user/max_user_namespaces"):
            v = _read_small(p, 32)
            if v is not None:
                extra.append(f"{os.path.basename(p)}={v.strip()}")
        res = PreflightResult(False, "userns-unavailable", "; ".join([err] + extra))
    _pf_cache[key] = (now, res)
    return res


# ---------------------------------------------------------------------------
# Telemetry, incidents
# ---------------------------------------------------------------------------

def telemetry_path() -> str:
    return os.path.join(os.environ.get("AQ_TELEMETRY_DIR") or "/var/lib/ai-stack/hybrid/telemetry", "aq-confine.jsonl")


def _rotate(path: str) -> None:
    try:
        if os.path.getsize(path) < TELEMETRY_MAX_BYTES:
            return
        for i in range(TELEMETRY_KEEP - 1, 0, -1):
            if os.path.exists(f"{path}.{i}"):
                os.replace(f"{path}.{i}", f"{path}.{i + 1}")
        os.replace(path, path + ".1")
    except OSError:
        pass


def write_telemetry(record: Dict[str, Any]) -> None:
    """Single O_APPEND write of one line under 4096 bytes; failures are silent."""
    try:
        line = json.dumps(record, separators=(",", ":"), sort_keys=True)
        if len(line) > TELEMETRY_LINE_MAX:
            record = dict(record)
            record["refs"] = {"truncated": True}
            line = json.dumps(record, separators=(",", ":"), sort_keys=True)[:TELEMETRY_LINE_MAX]
        path = telemetry_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        _rotate(path)
        fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW, 0o640)
        try:
            os.write(fd, (line + "\n").encode("utf-8"))
        finally:
            os.close(fd)
    except OSError:
        pass


def _recent_tamper_runs(window_s: int = 3600) -> int:
    path = telemetry_path()
    cutoff = time.time() - window_s
    n = 0
    try:
        with open(path, "rb") as fh:
            fh.seek(0, os.SEEK_END)
            fh.seek(max(0, fh.tell() - (1 << 20)))
            for raw in fh.read().splitlines():
                try:
                    r = json.loads(raw)
                except ValueError:
                    continue
                if r.get("reason") == "ref-tamper" and r.get("epoch", 0) >= cutoff:
                    n += 1
    except OSError:
        pass
    return n


def _incident(result: "ConfineResult", plan: Plan, kinds: List[str], promoted: List[Dict[str, str]]) -> None:
    """Attention-queue incident for tamper; never changes the run result."""
    if os.environ.get("AQ_CONFINE_INCIDENTS", "1") == "0":
        return
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import attention_queue  # type: ignore
        common = plan.layout.common if plan.layout else ""
        cmds = [f"ls -la {shlex.quote(plan.paths.refs)}   # saved private ref directory",
                f"cat {shlex.quote(plan.paths.run_dir)}/pre-snapshot.json"]
        for pr in promoted:
            cmds.append(f"git --git-dir={shlex.quote(common)} update-ref {shlex.quote(pr['ref'])} {pr['old']} {pr['new']}"
                        "   # restore")
        attention_queue.push(
            "aq-confine", "high", "human_gate",
            title=f"aq-confine ref-tamper run {plan.run_id[:8]} ({os.path.basename(sys.argv[0])})"[:80],
            detail=f"kinds={','.join(sorted(set(kinds)))} profile={plan.profile.name} run={plan.run_id}",
            proposed_action="\n".join(cmds),
            payload={"run_id": plan.run_id, "kinds": sorted(set(kinds))},
        )
        if _recent_tamper_runs() >= 3:
            attention_queue.push("aq-confine", "high", "human_gate",
                                 title="aq-confine: ref tamper in 3+ runs within an hour",
                                 detail="see aq-confine.jsonl", proposed_action="inspect recent aq-confine runs")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Guidance
# ---------------------------------------------------------------------------

def _guidance_cfg() -> Dict[str, Any]:
    return json.loads(GUIDANCE_PATH.read_text(encoding="utf-8"))


def render_guidance(profile_name: str, run_id: str) -> str:
    cfg = _guidance_cfg()
    parts = [cfg["intro"], cfg["profiles"].get(profile_name, ""), f"Run id: {run_id}",
             "Denied network requests are listed in denials.md in this directory."]
    return "\n\n".join(p for p in parts if p) + "\n"


def append_denial(guidance_dir: str, cls: str, destination: Optional[str] = None) -> str:
    """Append one fixed-template line to denials.md with a single O_APPEND write.
    The destination appears only in an escaped code span. Returns the opaque id."""
    cfg = _guidance_cfg()
    if cls not in cfg["denials"]:
        raise ValueError("unknown denial class")
    did = "d" + uuid.uuid4().hex[:10]
    line = f"[{did}] {cls}: {cfg['denials'][cls]}"
    if destination is not None:
        dest = destination if (isinstance(destination, str) and destination.isascii()
                               and _DEST_RE.match(destination)) else "[invalid-destination]"
        line += f" dest=`{dest}`"
    fd = os.open(os.path.join(guidance_dir, "denials.md"), os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW)
    try:
        os.write(fd, (line + "\n").encode("ascii"))
    finally:
        os.close(fd)
    return did


def denial_reason_phrase(cls: str, did: str) -> str:
    return f"aq-confine: egress denied ({cls}) id {did}"[:100]


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class ConfineResult:
    status: str
    rc: int
    exit_code: int
    run_id: str
    profile: str
    net: str
    worktree: Optional[str]
    duration_s: float
    argv_sha256: str
    reason: str
    limits: Dict[str, int]
    refs: Dict[str, Any]
    egress: Optional[Dict[str, Any]]
    stdout: bytes = b""
    stderr: bytes = b""
    ts: str = ""

    def json_line(self) -> str:
        d = dataclasses.asdict(self)
        d.pop("stdout"), d.pop("stderr")
        return json.dumps(d, separators=(",", ":"), sort_keys=True)


def _fail_result(plan_or_none: Optional[Plan], err: ConfineError, cmd: Sequence[str], profile_name: str,
                 net: str = "none", run_id: str = "", worktree: Optional[str] = None) -> ConfineResult:
    status = {EXIT_USAGE: "usage", EXIT_PROFILE: "profile-error"}.get(err.exit_code, "setup-failed")
    return ConfineResult(status, -1, err.exit_code, run_id, profile_name, net, worktree, 0.0, _argv_hash(cmd),
                         err.reason + (f": {err.detail}" if err.detail else ""), {}, {}, None,
                         ts=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))


def _argv_hash(cmd: Sequence[str]) -> str:
    return hashlib.sha256("\0".join(cmd).encode("utf-8", "replace")).hexdigest()


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

def _proc_start_ticks(pid: int) -> Optional[int]:
    try:
        with open(f"/proc/{pid}/stat", "r", encoding="utf-8", errors="replace") as fh:
            txt = fh.read()
        return int(txt.rsplit(")", 1)[1].split()[19])
    except (OSError, ValueError, IndexError):
        return None


def _write_private(path: str, data: str) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(data)


def _seed_dir(src: str, dst: str) -> None:
    """Copy regular files (no symlink following, names pre-validated) one level deep."""
    try:
        entries = list(os.scandir(src))
    except OSError:
        return
    for e in entries:
        if not _SLUG_RE.match(e.name):
            continue
        try:
            st = os.lstat(os.path.join(src, e.name))
            if not stat.S_ISREG(st.st_mode):
                continue
            with open(os.path.join(src, e.name), "rb") as fh:
                data = fh.read(65536)
        except OSError:
            continue
        with open(os.path.join(dst, e.name), "wb") as out:
            out.write(data)


def prune_runs(state: str, now: Optional[float] = None) -> None:
    root = os.path.join(state, "runs")
    cutoff = (now or time.time()) - STATE_RETENTION_S
    try:
        for e in os.scandir(root):
            try:
                if e.is_dir(follow_symlinks=False) and e.stat(follow_symlinks=False).st_mtime < cutoff:
                    _rmtree_nofollow(e.path)
            except OSError:
                continue
    except OSError:
        pass


def _read_status_events(raw: bytes) -> List[Dict[str, Any]]:
    out, dec, text, i = [], json.JSONDecoder(), raw.decode("utf-8", "replace"), 0
    while i < len(text):
        while i < len(text) and text[i] in " \r\n\t":
            i += 1
        if i >= len(text):
            break
        try:
            obj, i = dec.raw_decode(text, i)
        except ValueError:
            break
        if isinstance(obj, dict):
            out.append(obj)
    return out


def _drain(fd: int, cap: int, sink: List[bytes]) -> None:
    total = 0
    while True:
        try:
            chunk = os.read(fd, 65536)
        except OSError:
            break
        if not chunk:
            break
        if total < cap:
            sink.append(chunk[: cap - total])
        total += len(chunk)


def _prepare_git(plan: Plan, facts: HostFacts) -> Tuple[Dict[str, Any], Dict[str, str], List[str]]:
    """Create the host-owned per-run directories, seed private refs, take the
    pre-run snapshot. Returns (snapshot, old_ref_values, embedded_gits)."""
    L, P = plan.layout, plan.paths
    for d in (P.quarantine, P.refs, P.logs, os.path.join(P.admin, "logs")):
        os.makedirs(d, mode=0o700, exist_ok=True)
    for rel in ("index", os.path.join("logs", "HEAD")):
        src = os.path.join(L.admin, rel)
        try:
            if stat.S_ISREG(os.lstat(src).st_mode):
                shutil.copyfile(src, os.path.join(P.admin, rel), follow_symlinks=False)
        except OSError:
            pass
    os.makedirs(L.ns_ref_dir, exist_ok=True)   # bind destinations must exist under the read-only common dir
    os.makedirs(L.ns_log_dir, exist_ok=True)
    _seed_dir(L.ns_ref_dir, P.refs)
    _seed_dir(L.ns_log_dir, P.logs)
    snap = snapshot(L)
    _write_private(os.path.join(P.run_dir, "pre-snapshot.json"), json.dumps(snap, indent=1, sort_keys=True))
    old = {name: v[0] for name, v in snap["refs"].items() if name.startswith(L.ns_prefix)}
    cap = plan.profile.size_caps["worktree"]
    size, over, embedded = scan_tree(L.worktree, cap)
    if over:
        raise ConfineError(EXIT_USAGE, "worktree-over-cap", f"{size} bytes at launch")
    return snap, old, embedded


def _rebuild_index(plan: Plan, pre: Dict[str, Any], rep: Dict[str, Any]) -> str:
    """Never copy the sandbox index (forged extensions). After the own ref was promoted,
    rebuild the real index on the host from the promoted tip; leave it untouched if no ref
    moved or the real index changed during the run."""
    L = plan.layout
    own = f"{L.ns_prefix}{L.slug}"
    tips = [p["new"] for p in rep["promoted"] if p["ref"] == own]
    if not tips:
        return "index-untouched: own ref did not move"
    real = os.path.join(L.admin, "index")
    if _sha256_file(real) != pre["index"]:
        return "index-untouched: real index changed during run"
    tmp = real + f".aqc{os.getpid()}"
    argv, env = host_git(["read-tree", f"--index-output={tmp}", tips[0]], git_dir=L.admin)
    cp = subprocess.run(argv, env=env, cwd="/", capture_output=True, timeout=120)
    if cp.returncode != 0:
        return "index-untouched: read-tree failed"
    try:
        os.replace(tmp, real)
    except OSError as exc:
        return f"index-untouched: {exc.strerror}"
    return "index-rebuilt-from-tip"


def _finalize_git(plan: Plan, pre: Dict[str, Any], old: Dict[str, str], pre_embedded: List[str],
                  promote: bool = True) -> Dict[str, Any]:
    """Post-run: validate private refs, import objects, promote, compare snapshots."""
    L, P = plan.layout, plan.paths
    rep: Dict[str, Any] = {"namespace": L.ns_prefix, "accepted": [], "promoted": [], "rejected": [],
                           "kinds": [], "concurrent": [], "stale": [], "quarantine_bytes": 0, "quarantine_junk": 0}

    def reject(kind: str, ref: str = "", detail: str = "") -> None:
        rep["rejected"].append({"kind": kind, "ref": ref, "detail": detail[:200]})
        rep["kinds"].append(kind)

    accepted, problems = validate_ref_dir(P.refs)
    for pr in problems:
        reject(pr["kind"], pr.get("ref", ""), pr.get("detail", ""))
    if problems:
        accepted = {}   # fail closed: a polluted private ref directory promotes nothing
    if not promote:
        rep["promotion_skipped"] = True   # killed, timed-out or aborted runs never change real refs
        accepted = {}
    qbytes, qjunk = sanitize_quarantine(P.quarantine)
    rep["quarantine_bytes"], rep["quarantine_junk"] = qbytes, qjunk
    if qbytes > plan.profile.size_caps["quarantine"]:
        reject("size-cap", "", f"quarantine {qbytes} bytes")
        accepted = {}
    own = f"{L.ns_prefix}{L.slug}"
    outside = _outside_oids(L) if accepted else []
    for slug in sorted(accepted):
        ref, new = L.ns_prefix + slug, accepted[slug]
        before = old.get(ref)
        rep["accepted"].append(ref)
        if before == new:
            continue
        err = import_objects(L, P.quarantine, new, outside)
        if err:
            reject("object-import-failed", ref, err)
            continue
        if ref == own and before:
            anc = run_host_git(["merge-base", "--is-ancestor", before, new], git_dir=L.common)
            if anc.returncode == 1:
                rep["rewrites"] = rep.get("rewrites", []) + [ref]
                if plan.profile.strict_history:
                    reject("ref-own-rewritten", ref, "non-descendant of old tip")
                    continue
                rep["kinds_info"] = rep.get("kinds_info", []) + ["ref-own-rewritten"]
        zero = "0" * len(new)
        up = run_host_git(["update-ref", "-m", f"aq-confine promote {plan.run_id}", ref, new, before or zero],
                          git_dir=L.common)
        if up.returncode != 0:
            rep["stale"].append({"ref": ref, "detail": up.stderr[:160].decode("utf-8", "replace")})
        else:
            rep["promoted"].append({"ref": ref, "old": before or zero, "new": new})
    post = snapshot(L)
    for key in ("main_head", "config", "packed_refs", "hooks"):
        if key == "packed_refs" and rep["promoted"]:
            continue  # update-ref does not rewrite packed-refs; kept for completeness below
        if pre[key] != post[key]:
            reject("protected-file-changed", key)
    if pre["admin"] != post["admin"] or pre["worktree_dotgit"] != post["worktree_dotgit"]:
        reject("worktree-metadata-changed", "admin")
    _, _, embedded = scan_tree(L.worktree)
    new_emb = sorted(set(embedded) - set(pre_embedded))
    if new_emb:
        reject("worktree-metadata-changed", "embedded", f"new embedded .git: {new_emb[:3]}")
    promoted_names = {p["ref"] for p in rep["promoted"]}
    for name, val in post["refs"].items():
        if name not in promoted_names and pre["refs"].get(name) != val:
            rep["concurrent"].append(name)
    for name in pre["refs"]:
        if name not in post["refs"] and name not in rep["concurrent"]:
            rep["concurrent"].append(name)
    rep["ok"] = not rep["kinds"] and not rep["stale"]
    rep["index"] = _rebuild_index(plan, pre, rep) if (promote and rep["ok"]) else "index-untouched: run not promoted"
    _clear_dir(P.quarantine)   # imported or rejected; the saved private ref dir stays for inspection
    return rep


def run(profile: "str | Profile", cmd: Sequence[str], *, worktree: Optional[str] = None, net: Optional[str] = None,
        scratch: bool = False,
        ro: Sequence[str] = (), rw: Sequence[str] = (), env_allow: Sequence[str] = (),
        timeout: Optional[int] = None, rlimit_as: Optional[int] = None, run_id: Optional[str] = None,
        caller_env: Optional[Dict[str, str]] = None, allow_nested_userns: bool = False,
        egress_services: Sequence[str] = (), egress_grants: Sequence[str] = (),
        facts: Optional[HostFacts] = None) -> ConfineResult:
    """Run `cmd` confined. Never raises for policy failures; inspect result.status.
    There is no unconfined path."""
    facts = facts or HostFacts()
    pname = profile if isinstance(profile, str) else profile.name
    try:
        prof = load_profile(profile) if isinstance(profile, str) else profile
        if egress_services or egress_grants:
            raise _usage("egress-not-implemented", "egress flags arrive with S2c")
        plan = make_plan(prof, cmd, worktree=worktree, net=net, ro=ro, rw=rw, env_allow=env_allow, timeout=timeout,
                         rlimit_as=rlimit_as, run_id=run_id, caller_env=caller_env,
                         allow_nested_userns=allow_nested_userns, facts=facts, scratch=scratch)
    except ConfineError as err:
        res = _fail_result(None, err, cmd, pname, net or "none", run_id or "", worktree)
        _telemetry(res, None)
        return res
    pf = preflight(facts=facts)
    if not pf.ok or not plan.bwrap or not plan.prlimit:
        res = _fail_result(plan, ConfineError(EXIT_UNAVAILABLE, pf.reason or "bwrap-missing", pf.detail), cmd,
                           prof.name, plan.net, plan.run_id, worktree)
        _telemetry(res, plan)
        return res
    lock_fd = None
    try:
        if plan.layout:
            lock_dir = os.path.join(state_dir(), "locks")
            os.makedirs(lock_dir, mode=0o700, exist_ok=True)
            lock_fd = os.open(os.path.join(lock_dir, hashlib.sha256(plan.layout.admin.encode()).hexdigest()[:32]),
                              os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                raise _usage("worktree-busy", "another run holds this worktree")
        return _execute(plan, facts)
    except ConfineError as err:
        res = _fail_result(plan, err, cmd, prof.name, plan.net, plan.run_id, worktree)
    except Exception as exc:   # never raise from run(); fail closed
        res = _fail_result(plan, ConfineError(EXIT_POLICY, "internal-error", f"{type(exc).__name__}: {exc}"[:200]),
                           cmd, prof.name, plan.net, plan.run_id, worktree)
        res.status = "child-failed"
    finally:
        if lock_fd is not None:
            os.close(lock_fd)
    _telemetry(res, plan)
    return res


def _telemetry(res: ConfineResult, plan: Optional[Plan]) -> None:
    rec = {"event": "launch", "epoch": time.time(), "ts": res.ts, "run_id": res.run_id, "profile": res.profile,
           "status": res.status, "rc": res.rc, "exit_code": res.exit_code, "net": res.net,
           "worktree": res.worktree, "duration_s": round(res.duration_s, 3), "argv_sha256": res.argv_sha256,
           "reason": res.reason.split(":", 1)[0], "limits": res.limits,
           "nested_userns": bool(plan and plan.nested_userns),
           "refs": {k: res.refs.get(k) for k in ("kinds", "promoted", "stale") if k in res.refs}}
    if plan and plan.nested_userns:
        rec["incident"] = "nested-userns-enabled"
    write_telemetry(rec)


def _execute(plan: Plan, facts: HostFacts) -> ConfineResult:
    prof, P = plan.profile, plan.paths
    t0 = time.monotonic()
    wt = plan.layout.worktree if plan.layout else None
    refs: Dict[str, Any] = {}
    pre = old = pre_emb = None
    try:
        prune_runs(state_dir())
        os.makedirs(os.path.dirname(P.run_dir), mode=0o700, exist_ok=True)
        try:
            os.mkdir(P.run_dir, 0o700)   # exclusive: a reused run id must not inherit private refs
        except FileExistsError:
            raise _usage("run-id-in-use", plan.run_id)
        os.makedirs(P.sandbox_dir, mode=0o700, exist_ok=True)
        if plan.scratch:
            os.mkdir(P.run_dir + "/scratch", 0o700)
        if prof.guidance:
            os.makedirs(P.guidance, mode=0o755, exist_ok=True)
            with open(os.path.join(P.guidance, "GUIDANCE.md"), "w", encoding="utf-8") as fh:
                fh.write(render_guidance(prof.name, plan.run_id))
            open(os.path.join(P.guidance, "denials.md"), "a").close()
        if plan.layout:
            pre, old, pre_emb = _prepare_git(plan, facts)
    except ConfineError as err:
        res = _fail_result(plan, err, plan.cmd, prof.name, plan.net, plan.run_id, wt)
        _telemetry(res, plan)
        return res
    except OSError as exc:
        res = _fail_result(plan, ConfineError(EXIT_UNAVAILABLE, "run-dir-failed", exc.strerror or ""), plan.cmd,
                           prof.name, plan.net, plan.run_id, wt)
        _telemetry(res, plan)
        return res

    r_fd, w_fd = os.pipe()
    plan.status_fd = w_fd
    argv = build_argv(plan, facts)
    host_env = {"PATH": "/nonexistent"}
    out_sink: List[bytes] = []
    err_sink: List[bytes] = []
    reason = ""
    status = "ok"
    timed_out = killed_by = None
    try:
        proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                env=host_env, start_new_session=True, close_fds=True, pass_fds=(w_fd,))
    except OSError as exc:
        os.close(r_fd), os.close(w_fd)
        res = _fail_result(plan, ConfineError(EXIT_UNAVAILABLE, "spawn-failed", exc.strerror or ""), plan.cmd,
                           prof.name, plan.net, plan.run_id, wt)
        _telemetry(res, plan)
        return res
    os.close(w_fd)
    _write_private(os.path.join(P.run_dir, "process.json"), json.dumps(
        {"pid": proc.pid, "pgid": proc.pid, "start_ticks": _proc_start_ticks(proc.pid), "run_id": plan.run_id}))
    threads = [threading.Thread(target=_drain, args=(proc.stdout.fileno(), OUTPUT_CAP, out_sink), daemon=True),
               threading.Thread(target=_drain, args=(proc.stderr.fileno(), OUTPUT_CAP, err_sink), daemon=True)]
    status_chunks: List[bytes] = []
    threads.append(threading.Thread(target=_drain, args=(r_fd, 1 << 16, status_chunks), daemon=True))
    for t in threads:
        t.start()

    def kill() -> None:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except OSError:
            pass
        try:
            proc.kill()
        except OSError:
            pass

    marker = os.path.join(P.run_dir, "kill-requested")
    deadline = t0 + plan.timeout_s
    next_size = t0 + SIZE_CHECK_INTERVAL_S
    size_reason = ""
    while True:
        try:
            proc.wait(timeout=POLL_S)
            break
        except subprocess.TimeoutExpired:
            pass
        now = time.monotonic()
        if os.path.lexists(marker):
            killed_by = "egress-burst"
            kill()
        elif now > deadline:
            timed_out = True
            kill()
        elif now >= next_size:
            next_size = now + SIZE_CHECK_INTERVAL_S
            size_reason = _size_violation(plan)
            if size_reason:
                kill()
        if killed_by or timed_out or size_reason:
            proc.wait()
            break
    for t in threads:
        t.join(timeout=5)
    os.close(r_fd)
    rc = proc.returncode
    duration = time.monotonic() - t0
    events = _read_status_events(b"".join(status_chunks))
    ran = any("child-pid" in e for e in events)
    if os.path.lexists(marker):
        killed_by = killed_by or "egress-burst"   # marker present at reap time wins, even with rc 0
        try:
            os.unlink(marker)
        except OSError:
            pass
    violation = ""
    if plan.layout:
        try:
            no_promote = bool(timed_out or killed_by or size_reason or rc in (-9, EXIT_KILLED))
            refs = _finalize_git(plan, pre, old, pre_emb, promote=not no_promote)
        except Exception as err:   # fail closed: any post-run failure is a structured, unpromoted failure
            refs = {"ok": False, "kinds": ["object-import-failed"], "rejected": [{
                "kind": "object-import-failed", "detail": f"post-run error: {type(err).__name__}: {err}"[:200]}]}
        kinds = set(refs.get("kinds", []))
        wsize, wover, _ = scan_tree(plan.layout.worktree, prof.size_caps["worktree"])
        if wover and not size_reason:
            size_reason = "worktree-over-cap"
        if "object-import-failed" in kinds:
            violation = "object-import-failed"
        elif kinds - {"size-cap"}:
            violation = "ref-tamper"
        elif refs.get("stale"):
            violation = "ref-stale"
        if "size-cap" in kinds and not size_reason:
            size_reason = "quarantine-over-cap"
    if killed_by:
        status, reason, exit_code = "child-failed", killed_by, EXIT_POLICY
    elif size_reason:
        status, reason, exit_code = "child-failed", "size-cap", EXIT_POLICY
    elif violation:
        status, reason, exit_code = "child-failed", violation, EXIT_POLICY
    elif not ran:
        status, reason, exit_code = "setup-failed", "bwrap-setup-failed", EXIT_UNAVAILABLE
    elif timed_out:
        status, reason, exit_code = "timeout", "timeout", EXIT_TIMEOUT
    elif rc == 0:
        status, reason, exit_code = "ok", "", 0
    elif rc in (EXIT_KILLED, -9):
        status, reason, exit_code = "child-failed", "killed", EXIT_KILLED
    else:
        status, reason, exit_code = "child-failed", "child-exit", rc
    err_bytes = b"".join(err_sink)
    if status == "setup-failed":
        reason += ": " + err_bytes[-200:].decode("utf-8", "replace").strip().replace("\n", " ")[:200]
    res = ConfineResult(status, rc, exit_code, plan.run_id, prof.name, plan.net, wt, duration, _argv_hash(plan.cmd),
                        reason, plan.limits, refs, None, b"".join(out_sink), err_bytes,
                        time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    if violation == "ref-tamper" or violation == "object-import-failed":
        _incident(res, plan, list(refs.get("kinds", [])), refs.get("promoted", []))
    _telemetry(res, plan)
    return res


def _size_violation(plan: Plan) -> str:
    try:
        if plan.layout:
            _, over, _ = scan_tree(plan.layout.worktree, plan.profile.size_caps["worktree"])
            if over:
                return "worktree-over-cap"
            _, over, _ = scan_tree(plan.paths.quarantine, plan.profile.size_caps["quarantine"])
            if over:
                return "quarantine-over-cap"
    except OSError:
        pass
    return ""


# ---------------------------------------------------------------------------
# --kill RUN (pidfd path)
# ---------------------------------------------------------------------------

def kill_run(run_id: str) -> Tuple[int, str]:
    """Signal a recorded sandbox through a pidfd after verifying its start time.
    Returns (exit_code, message)."""
    if not _RUN_ID_RE.match(run_id or ""):
        return EXIT_USAGE, "bad run id"
    rec_path = os.path.join(state_dir(), "runs", run_id, "process.json")
    try:
        rec = json.loads(Path(rec_path).read_text(encoding="utf-8"))
        pid, ticks = int(rec["pid"]), rec["start_ticks"]
    except (OSError, ValueError, KeyError):
        return EXIT_USAGE, "no process record for run"
    try:
        fd = os.pidfd_open(pid)
    except OSError:
        return EXIT_USAGE, "process is not running"
    try:
        if ticks is None or _proc_start_ticks(pid) != ticks:
            return EXIT_USAGE, "recorded start time does not match; refusing to signal"
        signal.pidfd_send_signal(fd, signal.SIGKILL)
        return 0, f"killed run {run_id}"
    except OSError as exc:
        return EXIT_USAGE, f"signal failed: {exc.strerror}"
    finally:
        os.close(fd)


# ---------------------------------------------------------------------------
# Host-git lint
# ---------------------------------------------------------------------------

_SPAWNERS = {"run", "Popen", "check_output", "check_call", "call", "system", "popen", "getoutput"}


def lint_host_git(path: str) -> List[Tuple[int, str]]:
    """Flag git spawns that do not use an explicit --git-dir (or host_git) in a
    Python script that handles worktrees. Returns [(lineno, text)]."""
    src = Path(path).read_text(encoding="utf-8", errors="replace")
    if "worktree" not in src.lower():
        return []
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return [(1, "unparseable")]
    findings: List[Tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        f = node.func
        name = f.attr if isinstance(f, ast.Attribute) else (f.id if isinstance(f, ast.Name) else "")
        if name not in _SPAWNERS:
            continue
        a0 = node.args[0]
        if isinstance(a0, (ast.List, ast.Tuple)) and a0.elts:
            first = a0.elts[0]
            is_git = (isinstance(first, ast.Constant) and isinstance(first.value, str)
                      and os.path.basename(first.value) == "git")
            if is_git:
                has_dir = any(isinstance(e, ast.Constant) and isinstance(e.value, str)
                              and (e.value == "--git-dir" or e.value.startswith("--git-dir=")) for e in a0.elts)
                if not has_dir:
                    findings.append((node.lineno, "git spawn without explicit --git-dir; use confine.host_git"))
        elif isinstance(a0, ast.Constant) and isinstance(a0.value, str) and re.match(r"^\s*git\s", a0.value):
            findings.append((node.lineno, "shell git string without explicit --git-dir"))
        elif isinstance(a0, ast.JoinedStr):
            lead = a0.values[0] if a0.values else None
            if isinstance(lead, ast.Constant) and isinstance(lead.value, str) and re.match(r"^\s*git\s", lead.value):
                findings.append((node.lineno, "shell git f-string without explicit --git-dir"))
    return findings


def lint_script_names(paths: Sequence[str]) -> Dict[str, List[Tuple[int, str]]]:
    return {p: f for p in paths if (f := lint_host_git(p))}
