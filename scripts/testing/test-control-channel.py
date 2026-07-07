#!/usr/bin/env python3
"""Unit tests for control_channel — operator intervention queue (send/poll/safety)."""
import os
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
cc = SourceFileLoader(
    "control_channel", str(ROOT / "ai-stack" / "local-agents" / "control_channel.py")
).load_module()

TID = "test-ctrl-unit"


def _fail(m):
    print(f"FAIL: {m}"); sys.exit(1)


def _clean():
    try:
        os.remove(cc.control_path(TID))
    except OSError:
        pass


def test_send_poll_exactly_once():
    _clean()
    cc.send(TID, "message one")
    cc.send(TID, "message two", kind="cancel")
    new, cur = cc.poll(TID, 0)
    if len(new) != 2 or cur != 2:
        _fail(f"expected 2 msgs cursor 2, got {len(new)} cursor {cur}")
    if new[0]["kind"] != "inject" or new[1]["kind"] != "cancel":
        _fail(f"kinds wrong: {[m['kind'] for m in new]}")
    # second poll at cursor delivers nothing (exactly-once)
    new2, cur2 = cc.poll(TID, cur)
    if new2 or cur2 != cur:
        _fail(f"exactly-once violated: {new2}")
    print("PASS  send/poll cursor-based exactly-once delivery")


def test_incremental_delivery():
    _clean()
    cc.send(TID, "a")
    _, cur = cc.poll(TID, 0)
    cc.send(TID, "b")
    new, cur2 = cc.poll(TID, cur)
    if len(new) != 1 or new[0]["text"] != "b":
        _fail(f"incremental delivery wrong: {new}")
    print("PASS  incremental delivery from cursor")


def test_missing_queue_no_error():
    _clean()
    new, cur = cc.poll("never-sent-anything", 0)
    if new or cur != 0:
        _fail(f"missing queue should yield [],0 got {new},{cur}")
    print("PASS  missing queue -> no messages, no error (fail-open)")


def test_unsafe_id_rejected():
    for bad in ("../../etc/passwd", "a/b", "", "x;y", "a b"):
        try:
            cc.control_path(bad)
            _fail(f"unsafe id not rejected: {bad!r}")
        except ValueError:
            pass
    # send with unsafe id also raises
    try:
        cc.send("../evil", "x"); _fail("send with unsafe id should raise")
    except ValueError:
        pass
    print("PASS  unsafe task_id rejected (no path traversal)")


def test_malformed_lines_skipped():
    _clean()
    cc.send(TID, "good")
    with open(cc.control_path(TID), "a") as fh:
        fh.write("not json\n\n")
    new, _ = cc.poll(TID, 0)
    if len(new) != 1 or new[0]["text"] != "good":
        _fail(f"malformed lines should be skipped: {new}")
    print("PASS  malformed queue lines skipped")


if __name__ == "__main__":
    test_send_poll_exactly_once()
    test_incremental_delivery()
    test_missing_queue_no_error()
    test_unsafe_id_rejected()
    test_malformed_lines_skipped()
    _clean()
    print("\n5/5 control-channel tests passed")
