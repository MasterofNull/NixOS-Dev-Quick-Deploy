#!/usr/bin/env python3
"""A local run that stops on finish_reason=length is reported TRUNCATED; a normal stop is not."""
import contextlib
import importlib.machinery
import importlib.util
import io
import json
import sys
import tempfile
from pathlib import Path

LIB = Path(__file__).resolve().parents[1] / "ai" / "lib"
sys.path.insert(0, str(LIB))


def _load(name):
    loader = importlib.machinery.SourceFileLoader(name, str(LIB / f"{name}.py"))
    mod = importlib.util.module_from_spec(importlib.util.spec_from_loader(name, loader))
    loader.exec_module(mod)
    return mod


class _Socket:
    def settimeout(self, timeout):
        return None


class _Response:
    def __init__(self, lines):
        self.lines = lines
        self.fp = type("FP", (), {"raw": type("Raw", (), {"_sock": _Socket()})()})()

    def __enter__(self):
        return self

    def __exit__(self, *unused):
        return False

    def __iter__(self):
        return iter(self.lines)


def _run_direct(dispatch, root, finish):
    chunks = [b'data: {"choices":[{"delta":{"content":"half an ans"}}]}\n',
              b'data: {"choices":[{"delta":{},"finish_reason":"%s"}]}\n' % finish.encode(),
              b'data: {"choices":[],"usage":{"completion_tokens":3}}\n', b'data: [DONE]\n']
    dispatch.urllib.request.urlopen = lambda *a, **k: _Response(chunks)
    dispatch.wait_for_slot = lambda *a: None
    dispatch._slot_queue = None
    dispatch._emit_training_event = lambda *a: None
    config = dispatch.TaskConfig(mode="direct", role="implementer", timeout_secs=5, max_tokens=8,
                                 llama_url="http://127.0.0.1:1", hybrid_url="http://127.0.0.1:1",
                                 ralph_url="http://127.0.0.1:1", task_type="code")
    out = root / f"{finish}.log"
    ok = dispatch.DirectRunner().run(config, "prompt", out, f"t-{finish}")
    return ok, json.loads(Path(str(out) + ".usage.json").read_text()), out


def _registry_with(reg_mod, root, task_id, out):
    reg = reg_mod.TaskRegistry(root / "delegation")
    reg.append(task_id, "d", str(out), "direct", "implementer")
    return reg


def test_length_stop_is_truncated_in_status_and_check_but_still_succeeds():
    dispatch, reg_mod = _load("dispatch"), _load("task_registry")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        ok, usage, out = _run_direct(dispatch, root, "length")
        assert ok is True, "a truncated run must keep its success exit"
        assert usage["finish_reason"] == "length", usage
        reg = _registry_with(reg_mod, root, "t-length", out)
        reg.update_status("t-length", "done")
        reg.update_finish_reason("t-length", usage["finish_reason"])
        row = reg.get("t-length")
        assert row["status"] == "done" and row["truncated"] is True and row["finish_reason"] == "length", row
        buf, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(buf):
            assert reg.cmd_status("t-length") == 0
        assert json.loads(buf.getvalue())["status"] == "TRUNCATED", buf.getvalue()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            assert reg.cmd_check("t-length") == 0
        assert "TRUNCATED" in err.getvalue(), err.getvalue()


def test_normal_stop_is_not_truncated():
    dispatch, reg_mod = _load("dispatch"), _load("task_registry")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        ok, usage, out = _run_direct(dispatch, root, "stop")
        reg = _registry_with(reg_mod, root, "t-stop", out)
        reg.update_status("t-stop", "done")
        reg.update_finish_reason("t-stop", usage["finish_reason"])
        assert ok and reg.get("t-stop")["truncated"] is False
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            reg.cmd_status("t-stop")
        assert json.loads(buf.getvalue())["status"] == "done"


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except Exception as e:  # noqa: BLE001
                fails += 1
                print(f"FAIL {name}: {e!r}")
    sys.exit(1 if fails else 0)
