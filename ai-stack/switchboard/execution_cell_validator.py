"""Out-of-cell validator — Foundation C, C3b R3 (default-OFF, enforcement-tier).

Implements ONLY the primitive authorized by
`.agents/plans/aqos-foundation-c/C3B-R3-DESIGN-AND-AUTHORIZATION.md` §7 (frozen
by `C3B-R3-FREEZE-AND-ACTIVATION.md`, owner activation
`c4aaf0117ec84f8e`): the OUT-OF-CELL validator that turns a cell's untrusted
filesystem evidence into the runner's final GREEN/RED verdict.

Design §7 — the cell's git metadata + files are UNTRUSTED EVIDENCE, not the
verdict. This module receives ONLY `{grant_digest, base_oid, cell_root,
declared_output_paths}` (the runner's own trusted config — bare mirror path,
bwrap binary, python interpreter — is bound at `ValidatorConfig` construction,
never smuggled in per-call from the cell or the grant). It:

  1. Obtains the base tree via a FRESH validator-built throwaway clone from
     the configured bare mirror at `base_oid` (validator-constructed git
     invocation, own env, own `-c core.hooksPath=/dev/null`, `GIT_CONFIG_*`
     cleared — never trusts the cell's own `.git`).
  2. Compares filesystem bytes/modes/symlink-targets/adds/deletes DIRECTLY
     between the base clone and the cell root — NO `git diff`, hooks,
     filters, clean/smudge, textconv, attributes, or cell-controlled
     executables of any kind. `.git` itself is excluded from the comparison
     (it is the cell's own untrusted metadata, never the verdict).
  3. Runs the actual byte-for-byte comparison INSIDE its own minimal bwrap
     confinement (Q-R3-2: `--unshare-all --unshare-net`, read-only binds of
     both trees, its own throwaway clone) — a second, independent sandbox
     boundary from the runner's cell-execution sandbox.
  4. Requires every changed path to equal one declared, already-rebased
     output path. Any undeclared change, special file, path escape,
     unreadable entry, base mismatch, timeout, or internal error -> typed
     RED. Only an all-pass comparison -> GREEN.

This module opens NO socket, holds NO execution-grant signing key, and
performs NO network call (git operates only against the caller-supplied
local bare mirror path). It NEVER raises to its caller — every code path
returns a `ValidationResult` (fail-closed: RED is the safe default for any
unexpected condition).
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Optional, Sequence

VERDICT_GREEN = "green"
VERDICT_RED = "red"

# Git invocations the validator itself makes (building the throwaway base
# clone) are hermetically scoped: no repo/system/global config, no hooks, no
# terminal prompts. This is defense-in-depth even though `clone`+`checkout`
# do not normally invoke smudge/clean filters — a compromised cell has no
# leverage over these variables since they come from this module's own
# constant, never from the cell or the grant.
_GIT_ENV_OVERRIDES = {
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_SYSTEM": "/dev/null",
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_TERMINAL_PROMPT": "0",
    "GIT_ATTR_NOSYSTEM": "1",
}

_GIT_HOOKS_OFF = ["-c", "core.hooksPath=/dev/null"]


@dataclass(frozen=True)
class ValidatorConfig:
    """The validator's OWN trusted, statically-bound configuration — never
    per-call input (design §7: the per-call surface is exactly
    `{grant_digest, base_oid, cell_root, declared_output_paths}`)."""

    bare_mirror_path: str
    bwrap_path: Optional[str]
    python_bin: str
    work_root: str
    timeout_s: float = 20.0
    git_timeout_s: float = 30.0


@dataclass(frozen=True)
class ValidationResult:
    """Terminal, typed validation verdict. `changed_paths` is populated ONLY
    on GREEN (the retained diff for later, separate orchestrator review —
    design §4.5/§10-7: no auto-merge, ever)."""

    verdict: str
    reason: str
    changed_paths: tuple = ()


# ---------------------------------------------------------------------------
# The compare worker — a FIXED, closed-vocabulary constant run inside the
# validator's own bwrap sandbox. Never derived from cell/grant/caller text;
# its only dynamic input is the small descriptor JSON the OUTER (unsandboxed)
# validate() function writes itself, ro-bound in.
# ---------------------------------------------------------------------------

_COMPARE_WORKER_SRC = r"""
import hashlib, json, os, stat, sys

def _walk(root):
    out = {}
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        rel_dir = os.path.relpath(dirpath, root)
        for name in list(dirnames) + list(filenames):
            full = os.path.join(dirpath, name)
            rel = name if rel_dir == "." else os.path.normpath(os.path.join(rel_dir, name))
            parts = rel.split(os.sep)
            if parts and parts[0] == ".git":
                continue
            try:
                st = os.lstat(full)
            except OSError as exc:
                out[rel] = {"type": "unreadable", "detail": str(exc)}
                continue
            if stat.S_ISLNK(st.st_mode):
                try:
                    target = os.readlink(full)
                except OSError:
                    target = None
                out[rel] = {"type": "symlink", "target": target}
            elif stat.S_ISREG(st.st_mode):
                try:
                    with open(full, "rb") as fh:
                        digest = hashlib.sha256(fh.read()).hexdigest()
                    out[rel] = {"type": "file", "sha256": digest, "mode": stat.S_IMODE(st.st_mode)}
                except OSError as exc:
                    out[rel] = {"type": "unreadable", "detail": str(exc)}
            elif stat.S_ISDIR(st.st_mode):
                out[rel] = {"type": "dir"}
            else:
                out[rel] = {"type": "special"}
    return out

def main():
    with open("/run/validator-descriptor.json", "r", encoding="utf-8") as fh:
        descriptor = json.load(fh)
    declared = set(descriptor.get("declared_output_paths", []))

    base = _walk("/base")
    cell = _walk("/cell")

    changed = []
    specials = []
    unreadable = []
    for key in sorted(set(base) | set(cell)):
        b = base.get(key)
        c = cell.get(key)
        if b == c:
            continue
        if (b and b.get("type") == "unreadable") or (c and c.get("type") == "unreadable"):
            unreadable.append(key)
            continue
        if (b and b.get("type") == "special") or (c and c.get("type") == "special"):
            specials.append(key)
            continue
        changed.append(key)

    undeclared = [k for k in changed if k not in declared]

    print(json.dumps({
        "changed": changed,
        "specials": specials,
        "unreadable": unreadable,
        "undeclared": undeclared,
    }))

if __name__ == "__main__":
    main()
"""


def _build_throwaway_base_clone(bare_mirror_path: str, base_oid: str, work_dir: str, timeout_s: float) -> Optional[str]:
    """Validator-constructed throwaway clone at `base_oid` — the trusted
    comparison base. Own env, own hooks-off flag, own timeout. Returns the
    clone directory or None on ANY failure (never raises)."""
    try:
        dest = os.path.join(work_dir, "base-clone")
        env = {**os.environ, **_GIT_ENV_OVERRIDES}
        clone = subprocess.run(
            ["git"] + _GIT_HOOKS_OFF + ["clone", "--template=", "--no-local", "--no-hardlinks", bare_mirror_path, dest],
            check=False, capture_output=True, env=env, timeout=timeout_s,
        )
        if clone.returncode != 0:
            return None
        checkout = subprocess.run(
            ["git", "-C", dest] + _GIT_HOOKS_OFF + ["checkout", "--detach", base_oid],
            check=False, capture_output=True, env=env, timeout=timeout_s,
        )
        if checkout.returncode != 0:
            return None
        return dest
    except (OSError, subprocess.TimeoutExpired, Exception):  # noqa: BLE001 — total fail-closed
        return None


def _run_confined_compare(
    config: ValidatorConfig, base_clone: str, cell_root: str, declared_output_paths: Sequence[str]
) -> ValidationResult:
    """Runs `_COMPARE_WORKER_SRC` inside the validator's OWN bwrap sandbox
    (Q-R3-2): unshare-all + unshare-net, read-only binds of both trees, no
    writable path at all (a pure comparison needs none). Never raises."""
    if not config.bwrap_path:
        return ValidationResult(VERDICT_RED, "confinement-unavailable")
    if not config.python_bin or not os.path.isfile(config.python_bin):
        return ValidationResult(VERDICT_RED, "confinement-unavailable")

    descriptor_path = None
    try:
        descriptor_fd, descriptor_path = tempfile.mkstemp(prefix="aq-validator-descriptor-", dir=config.work_root)
        with os.fdopen(descriptor_fd, "w", encoding="utf-8") as fh:
            json.dump({"declared_output_paths": list(declared_output_paths)}, fh)
        os.chmod(descriptor_path, 0o400)

        argv = [
            config.bwrap_path,
            "--unshare-all", "--unshare-net",
            "--die-with-parent", "--new-session", "--clearenv",
            "--setenv", "HOME", "/tmp",
            "--setenv", "LANG", "C.UTF-8",
            "--setenv", "PATH", "/nonexistent",
            "--ro-bind", "/nix/store", "/nix/store",
            "--ro-bind", base_clone, "/base",
            "--ro-bind", cell_root, "/cell",
            "--ro-bind", descriptor_path, "/run/validator-descriptor.json",
            "--proc", "/proc",
            "--dev", "/dev",
            "--tmpfs", "/tmp",
            "--",
            config.python_bin, "-c", _COMPARE_WORKER_SRC,
        ]
        try:
            proc = subprocess.run(argv, capture_output=True, timeout=config.timeout_s)
        except (OSError, subprocess.TimeoutExpired):
            return ValidationResult(VERDICT_RED, "validator-confinement-error")

        if proc.returncode != 0:
            return ValidationResult(VERDICT_RED, "validator-compare-failed")

        try:
            payload = json.loads(proc.stdout.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return ValidationResult(VERDICT_RED, "validator-malformed-output")

        if not isinstance(payload, dict):
            return ValidationResult(VERDICT_RED, "validator-malformed-output")

        if payload.get("unreadable"):
            return ValidationResult(VERDICT_RED, "unreadable-entry")
        if payload.get("specials"):
            return ValidationResult(VERDICT_RED, "special-file-present")
        if payload.get("undeclared"):
            return ValidationResult(VERDICT_RED, "undeclared-change")

        changed = payload.get("changed", [])
        if not isinstance(changed, list):
            return ValidationResult(VERDICT_RED, "validator-malformed-output")

        return ValidationResult(VERDICT_GREEN, "ok", changed_paths=tuple(changed))
    except Exception as exc:  # noqa: BLE001 — total fail-closed
        return ValidationResult(VERDICT_RED, f"validator-internal-error:{type(exc).__name__}")
    finally:
        if descriptor_path is not None:
            try:
                os.remove(descriptor_path)
            except OSError:
                pass


def validate(
    *,
    grant_digest: str,
    base_oid: str,
    cell_root: str,
    declared_output_paths: Sequence[str],
    config: ValidatorConfig,
) -> ValidationResult:
    """The sole entry point (design §7). Per-call surface is EXACTLY
    `{grant_digest, base_oid, cell_root, declared_output_paths}` —
    `grant_digest` is carried through only for correlation in the caller's
    receipt, never used by the comparison itself. Never raises: any
    unexpected exception anywhere is caught and reported as a typed RED
    (fail-closed) rather than propagating."""
    del grant_digest  # correlation-only; not used by the comparison itself
    try:
        for path in declared_output_paths:
            if not isinstance(path, str) or not path:
                return ValidationResult(VERDICT_RED, "declared-path-invalid")
            if path.startswith("/") or "\\" in path:
                return ValidationResult(VERDICT_RED, "declared-path-invalid")
            components = [c for c in path.split("/") if c != ""]
            if not components or ".." in components:
                return ValidationResult(VERDICT_RED, "declared-path-invalid")

        if not isinstance(base_oid, str) or not base_oid:
            return ValidationResult(VERDICT_RED, "base-oid-invalid")
        if not cell_root or not os.path.isdir(cell_root):
            return ValidationResult(VERDICT_RED, "cell-root-invalid")

        os.makedirs(config.work_root, mode=0o700, exist_ok=True)
        work_dir = tempfile.mkdtemp(prefix="aq-validator-", dir=config.work_root)
        try:
            base_clone = _build_throwaway_base_clone(config.bare_mirror_path, base_oid, work_dir, config.git_timeout_s)
            if base_clone is None:
                return ValidationResult(VERDICT_RED, "base-clone-failed")

            return _run_confined_compare(config, base_clone, cell_root, declared_output_paths)
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)
    except Exception as exc:  # noqa: BLE001 — total fail-closed
        return ValidationResult(VERDICT_RED, f"validator-internal-error:{type(exc).__name__}")
