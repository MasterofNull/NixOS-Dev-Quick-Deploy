#!/usr/bin/env python3
"""aq-model-switch: NixOS skips the runtime GPU drop-in; post-switch hooks never run as root."""
import contextlib
import importlib.machinery
import importlib.util
import io
import sys
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
loader = importlib.machinery.SourceFileLoader("aq_model_switch", str(ROOT / "scripts" / "ai" / "aq-model-switch"))
spec = importlib.util.spec_from_loader(loader.name, loader)
mod = importlib.util.module_from_spec(spec)
loader.exec_module(mod)


def dry_run(nixos: bool) -> str:
    out = io.StringIO()
    with mock.patch.object(mod, "_is_nixos", return_value=nixos), \
            mock.patch.object(sys, "argv", ["aq-model-switch", "--dry-run", "qwen3.6-35b-mtp"]), \
            contextlib.redirect_stdout(out):
        try:
            mod.main()
        except SystemExit:
            pass
    return out.getvalue()


def hooks(euid: int, env: dict, repo_owner_uid: int = 1000) -> tuple[list, str]:
    calls, out = [], io.StringIO()
    fake_pw = mock.Mock(pw_uid=1000, pw_gid=100, pw_dir="/home/hyperd", pw_name="hyperd")
    manifest = "post_switch_hooks:\n  - id: h1\n    command: 'true'\n"
    with mock.patch.object(mod.os, "geteuid", return_value=euid), \
            mock.patch.dict(mod.os.environ, env, clear=False), \
            mock.patch("pwd.getpwnam", return_value=fake_pw), \
            mock.patch("pwd.getpwuid", side_effect=lambda uid: mock.Mock(pw_name="root" if uid == 0 else "hyperd")), \
            mock.patch.object(mod.os, "getgrouplist", return_value=[100]), \
            mock.patch.object(Path, "exists", return_value=True), \
            mock.patch.object(Path, "read_text", return_value=manifest), \
            mock.patch.object(Path, "stat", return_value=mock.Mock(st_uid=repo_owner_uid)), \
            mock.patch("subprocess.Popen", side_effect=lambda *a, **k: calls.append(k)), \
            mock.patch("builtins.open", mock.mock_open()), \
            contextlib.redirect_stdout(out):
        mod._run_post_switch_hooks("qwen3.6-35b-mtp")
    return calls, out.getvalue()


def main() -> int:
    nix = dry_run(True)
    assert "skipping runtime drop-in" in nix and "would write drop-in" not in nix, nix
    other = dry_run(False)
    assert "skipping runtime drop-in" not in other, other

    calls, _ = hooks(0, {"SUDO_USER": "hyperd", "AQ_POST_SWITCH_HOOKS": "1"})
    assert len(calls) == 1 and calls[0]["user"] == 1000 and calls[0]["group"] == 100, calls
    assert calls[0]["env"]["HOME"] == "/home/hyperd"

    calls, out = hooks(0, {"SUDO_USER": "", "AQ_POST_SWITCH_HOOKS": "1"}, repo_owner_uid=0)
    assert calls == [] and "refusing to run repo hooks as root" in out, out

    calls, out = hooks(0, {"SUDO_USER": "hyperd", "AQ_POST_SWITCH_HOOKS": "0"})
    assert calls == [] and "AQ_POST_SWITCH_HOOKS=0" in out, out

    calls, _ = hooks(1000, {"AQ_POST_SWITCH_HOOKS": "1"})
    assert len(calls) == 1 and "user" not in calls[0], calls
    print("PASS: aq-model-switch NixOS drop-in skip + hooks drop root to invoking user")
    return 0


if __name__ == "__main__":
    sys.exit(main())
