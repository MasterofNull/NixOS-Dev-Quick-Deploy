#!/usr/bin/env python3
"""config_loader — validated config loading with env overlay and hot-reload.

WS1 (AQ-OS PRD): kills the two most repeated config failure classes —
unvalidated edits reaching a running service, and restart-to-apply latency.

Core API:
    load_validated(path)         -> (raw_doc, model_instance)   # raises on invalid
    round_trip_ok(path)          -> bool                        # CI primitive
    ConfigWatcher(path, on_reload).start()                      # mtime hot-reload

Design contracts:
  - Validate-only: the RAW document is always returned unchanged alongside the
    validated model, so existing consumers keep working (incremental adoption).
  - Fail-safe reload: a hot-reload that fails validation KEEPS the last-good
    config and logs; a bad edit never takes down a running service.
  - Env overlay: SWB_*-style env vars already resolve inside consumers; this
    module exposes an optional overlay hook without imposing a scheme.
  - Schema source of truth: contracts/config registry. Unregistered paths load
    raw (no validation) so the loader is safe for any config.

Kill switch: CONFIG_HOT_RELOAD=0 disables the watcher (load path unaffected).
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable, Optional

# contracts/ is at repo root: scripts/ai/lib/config_loader.py -> ../../..
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def _repo_rel(path: str | Path) -> str:
    p = Path(path)
    try:
        return str(p.resolve().relative_to(_REPO_ROOT))
    except ValueError:
        return str(p)


def _schema_for(path: str | Path):
    """Return the registered pydantic model for a config path, or None."""
    try:
        from contracts.config import registry
    except Exception:
        return None
    return registry().get(_repo_rel(path))


def _read_doc(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    if path.suffix in (".yaml", ".yml"):
        import yaml
        return yaml.safe_load(text)
    return json.loads(text)


def load_validated(path: str | Path) -> tuple[Any, Optional[Any]]:
    """Load a config file and validate it against its registered schema.

    Returns (raw_doc, model_instance). model_instance is None when no schema is
    registered for this path (raw load, no validation). Raises on invalid data
    for a registered path — callers decide whether to fail-safe.
    """
    p = Path(path)
    raw = _read_doc(p)
    model = _schema_for(p)
    if model is None:
        return raw, None
    return raw, model.model_validate(raw)


def validate_file(path: str | Path) -> tuple[bool, str]:
    """(ok, message). True + 'ok' when valid or unregistered; False + reason on error."""
    try:
        _, inst = load_validated(path)
    except FileNotFoundError:
        return False, "file not found"
    except Exception as exc:  # pydantic ValidationError, yaml/json errors
        return False, f"{type(exc).__name__}: {exc}"
    return True, "ok" if inst is not None else "ok (no schema registered)"


def round_trip_ok(path: str | Path) -> tuple[bool, str]:
    """Verify the validated model re-serializes without loss of required fields.

    Guards the F2-class bug (inf -> null -> re-validation failure): if a model
    dumps to something that no longer validates, that is a schema/data defect.
    """
    try:
        raw, inst = load_validated(path)
    except Exception as exc:
        return False, f"load failed: {type(exc).__name__}: {exc}"
    if inst is None:
        return True, "ok (no schema)"
    try:
        dumped = inst.model_dump(mode="json")
        type(inst).model_validate(dumped)
    except Exception as exc:
        return False, f"round-trip failed: {type(exc).__name__}: {exc}"
    return True, "ok"


class ConfigWatcher:
    """Poll a config file's mtime; on change, validate and invoke on_reload.

    mtime polling (not inotify) so there is no hard dependency and it works over
    bind mounts / NixOS store paths. Interval defaults to 2s (well under the
    <5s adoption target). Fail-safe: a change that fails validation is logged
    and skipped; the last-good config stays live.
    """

    def __init__(
        self,
        path: str | Path,
        on_reload: Callable[[Any], None],
        *,
        interval_s: float = 2.0,
        logger: Optional[Callable[[str], None]] = None,
    ):
        self._path = Path(path)
        self._on_reload = on_reload
        self._interval = interval_s
        self._log = logger or (lambda m: print(m, file=sys.stderr))
        self._mtime = self._safe_mtime()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def _safe_mtime(self) -> float:
        try:
            return self._path.stat().st_mtime
        except OSError:
            return -1.0

    def enabled(self) -> bool:
        return os.environ.get("CONFIG_HOT_RELOAD", "1") != "0"

    def start(self) -> "ConfigWatcher":
        if not self.enabled():
            self._log(f"[config_loader] hot-reload disabled (CONFIG_HOT_RELOAD=0) for {self._path.name}")
            return self
        self._thread = threading.Thread(target=self._run, name=f"cfgwatch:{self._path.name}", daemon=True)
        self._thread.start()
        self._log(f"[config_loader] watching {self._path} every {self._interval}s")
        return self

    def stop(self) -> None:
        self._stop.set()

    def check_once(self) -> bool:
        """Poll once; return True if a valid reload was applied. Public for tests."""
        m = self._safe_mtime()
        if m <= self._mtime:
            return False
        self._mtime = m
        try:
            raw, inst = load_validated(self._path)
        except Exception as exc:
            self._log(f"[config_loader] REJECTED reload of {self._path.name}: "
                      f"{type(exc).__name__}: {exc} — keeping last-good config")
            return False
        try:
            self._on_reload(raw)
        except Exception as exc:
            self._log(f"[config_loader] on_reload callback failed for {self._path.name}: {exc}")
            return False
        self._log(f"[config_loader] applied reload of {self._path.name} "
                  f"({'validated' if inst is not None else 'raw'})")
        return True

    def _run(self) -> None:
        while not self._stop.wait(self._interval):
            try:
                self.check_once()
            except Exception as exc:  # watcher must never die
                self._log(f"[config_loader] watcher error on {self._path.name}: {exc}")


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(prog="config_loader.py")
    ap.add_argument("action", choices=["validate", "round-trip"])
    ap.add_argument("path")
    args = ap.parse_args()
    fn = validate_file if args.action == "validate" else round_trip_ok
    ok, msg = fn(args.path)
    print(f"{'OK' if ok else 'FAIL'}: {args.path}: {msg}")
    sys.exit(0 if ok else 1)
