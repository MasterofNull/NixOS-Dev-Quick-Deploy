#!/usr/bin/env python3
"""Regression test for the DESTRUCTIVE-DELETION guard in _verify_edit_quality
(2026-08-29).

issues-backlog: shallow-dogfood-verify-cmd-false-passes-deletions +
local-edit-destructive-span-correct-logic-wrong-blast-radius. Governing value:
CLAUDE.md Rule 21 (help local reach its best self — this is a SAFETY NET that
coaches local away from destructive edits, not a punitive gate).

Root cause this guards against (measured 2026-08-29, scaffolded dogfood-01):
local finally LANDED an edit whose core logic was correct, but its edit_file
old_string spanned ~96 lines and DELETED `route()` and `_emit()` — two
top-level functions still called elsewhere in the file — leaving a file that
crashes with NameError at runtime. The behavioral verify_cmd was
`{file} --help`, which argparse SHORT-CIRCUITS (exits 0) before `route()` is
ever called, so the deletion passed the gate and the coach never fired. The
pyflakes undefined-name lint that would otherwise catch a dangling call is not
importable in this repo's Nix env, and a call to a now-undefined name still
COMPILES — so compile-only lint could not see it either.

Fix under test (agent_executor.py `_find_destructive_deletion` +
`_verify_edit_quality`): a stdlib-`ast`-only check — no external linter — that
flags a top-level def/class the edit deleted which is STILL referenced (Name or
Attribute) anywhere in the post-edit AST. Placed first in the post-edit checks
(most severe outcome), returns a `destructive_deletion:<name>` verdict with
coaching to use the smallest old_string.

Coverage:
  (a) unit: destructive deletion (route deleted, still called by cmd_route) is
      flagged, naming `route`.
  (b) unit: a clean edit that deletes nothing is not flagged.
  (c) unit: a LEGITIMATE deletion (route removed AND its only caller cmd_route
      removed too — no dangling reference) is NOT flagged (no false positive on
      an intentional refactor).
  (d) unit: no pre-content -> None (cannot decide).
  (e) unit: non-Python / unparseable pre or post -> None (a broken post-edit is
      caught by the compile/lint check, never here).
  (f) integration (write_region): _verify_edit_quality returns a verdict with
      passed=False and reason startswith 'destructive_deletion:route' for the
      real dogfood-01 route()/_emit() deletion shape.
  (g) integration (write_region): a clean edit (only the target function body
      changed, nothing deleted) does NOT return a destructive_deletion verdict.
  (h) integration (edit_file): the same destructive deletion expressed as an
      edit_file old_string/new_string (pre-image reconstructed by reversing the
      substitution) is flagged.
  (i) fail-safe: a destructive deletion in a NON-Python (.md) file is not
      flagged by this guard (guard is Python-only; returns None, other checks
      proceed) and _verify_edit_quality never raises.
"""
from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[2]
LOCAL_AGENTS = ROOT / "ai-stack" / "local-agents"
sys.path.insert(0, str(LOCAL_AGENTS))

sys.modules.setdefault("httpx", MagicMock())
spec = importlib.util.spec_from_file_location("agent_executor", LOCAL_AGENTS / "agent_executor.py")
ae = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ae)

_find_destructive_deletion = ae._find_destructive_deletion
_verify_edit_quality = ae._verify_edit_quality

PASS = 0
FAIL = 0


def check(name: str, cond: bool) -> None:
    global PASS, FAIL
    if cond:
        print(f"  PASS  {name}")
        PASS += 1
    else:
        print(f"  FAIL  {name}")
        FAIL += 1


PRE = '''\
def _matches_exclude(lane_id, token):
    return token.split("-")[0] == lane_id


def _emit(payload, as_json):
    print(payload)
    return 0


def route(role, subject, exclude):
    return {"ok": True}


def cmd_route(args):
    return route(args.role, args.subject, args.exclude)
'''

# route + _emit deleted; cmd_route (which calls route) survives -> dangling ref
POST_DESTRUCTIVE = '''\
def _matches_exclude(lane_id, token):
    if "-" in token:
        return False
    return token.split("-")[0] == lane_id


def cmd_route(args):
    return route(args.role, args.subject, args.exclude)
'''

# only _matches_exclude changed, nothing deleted
POST_CLEAN = '''\
def _matches_exclude(lane_id, token):
    if "-" in token:
        return False
    return token.split("-")[0] == lane_id


def _emit(payload, as_json):
    print(payload)
    return 0


def route(role, subject, exclude):
    return {"ok": True}


def cmd_route(args):
    return route(args.role, args.subject, args.exclude)
'''

# legitimate refactor: route AND its only caller cmd_route both removed
POST_LEGIT_DELETION = '''\
def _matches_exclude(lane_id, token):
    return token.split("-")[0] == lane_id


def _emit(payload, as_json):
    print(payload)
    return 0
'''


def test_unit() -> None:
    check("(a) destructive: route deleted + still called -> 'route'",
          _find_destructive_deletion(PRE, POST_DESTRUCTIVE) == "route")
    check("(b) clean: nothing deleted -> None",
          _find_destructive_deletion(PRE, POST_CLEAN) is None)
    check("(c) legit deletion: route + cmd_route both gone -> None",
          _find_destructive_deletion(PRE, POST_LEGIT_DELETION) is None)
    check("(d) no pre-content -> None",
          _find_destructive_deletion(None, POST_DESTRUCTIVE) is None)
    check("(e) unparseable pre -> None",
          _find_destructive_deletion("def broken( {", POST_DESTRUCTIVE) is None)
    check("(e2) unparseable post -> None",
          _find_destructive_deletion(PRE, "def broken( {") is None)

    # ---- FALSE-POSITIVE cases (independent review, Codex 2026-08-29 DEFECT) ----
    # (j) route() def deleted, but the only post reference is an ATTRIBUTE access
    #     `client.route()` on an unrelated object — must NOT flag route.
    post_attr_only = '''\
def _matches_exclude(lane_id, token):
    return token.split("-")[0] == lane_id


def cmd_route(args):
    client = get_client()
    return client.route(args)
'''
    check("(j) deleted name only used as obj.attr -> None (no false positive)",
          _find_destructive_deletion(PRE, post_attr_only) is None)

    # (k) route() def deleted but RE-PROVIDED by an import -> valid replacement.
    post_import_repl = '''\
from routing import route


def _matches_exclude(lane_id, token):
    return token.split("-")[0] == lane_id


def _emit(payload, as_json):
    return 0


def cmd_route(args):
    return route(args)
'''
    check("(k) deleted def replaced by import of same name -> None",
          _find_destructive_deletion(PRE, post_import_repl) is None)

    # (l) route() def deleted but RE-PROVIDED by a top-level assignment.
    post_assign_repl = '''\
def _matches_exclude(lane_id, token):
    return token.split("-")[0] == lane_id


def _emit(payload, as_json):
    return 0


route = make_router()


def cmd_route(args):
    return route(args)
'''
    check("(l) deleted def replaced by assignment of same name -> None",
          _find_destructive_deletion(PRE, post_assign_repl) is None)

    # (m) file-type gate: a non-Python path is never checked, even if the content
    #     happens to be ast-parseable and would otherwise flag.
    check("(m) .md path with parseable destructive content -> None (gated)",
          _find_destructive_deletion(PRE, POST_DESTRUCTIVE, file_path="notes.md") is None)
    check("(m2) .py path still flags the real destructive deletion",
          _find_destructive_deletion(PRE, POST_DESTRUCTIVE, file_path="x.py") == "route")

    # ---- SCOPE SENSITIVITY (independent review round 2, Codex 2026-08-29) ----
    # (n) FALSE-NEGATIVE guard: a genuinely dangling GLOBAL route() call must
    #     stay flagged even when an UNRELATED function has a local `route = ...`.
    #     A flat ast.walk would merge that local into `bound` and mask it.
    post_global_call_plus_unrelated_local = '''\
def _matches_exclude(lane_id, token):
    return token.split("-")[0] == lane_id


def _emit(payload, as_json):
    return 0


def cmd_route(args):
    return route(args)


def unrelated(x):
    route = x + 1
    return route
'''
    check("(n) dangling global call + unrelated function-local shadow -> 'route'",
          _find_destructive_deletion(PRE, post_global_call_plus_unrelated_local) == "route")

    # (o) TRUE-NEGATIVE: a purely function-LOCAL use of the deleted name (its own
    #     local binding, no global call) is safe -> not flagged.
    post_local_only = '''\
def _matches_exclude(lane_id, token):
    return token.split("-")[0] == lane_id


def _emit(payload, as_json):
    return 0


def helper(x):
    route = compute(x)
    return route
'''
    check("(o) deleted name only used as a function-local -> None",
          _find_destructive_deletion(PRE, post_local_only) is None)

    # (p) CLOSURE (independent review round 3): a nested inner() capturing an
    #     enclosing function's local/param `route` is a closure (is_free), NOT a
    #     module reference — must NOT be flagged when top-level route is deleted.
    post_closure_local = '''\
def _matches_exclude(lane_id, token):
    return token.split("-")[0] == lane_id


def _emit(payload, as_json):
    return 0


def outer():
    route = build()
    def inner():
        return route()
    return inner
'''
    check("(p) closure over enclosing-function local -> None (not module)",
          _find_destructive_deletion(PRE, post_closure_local) is None)

    post_closure_param = '''\
def _matches_exclude(lane_id, token):
    return token.split("-")[0] == lane_id


def _emit(payload, as_json):
    return 0


def outer(route):
    def inner():
        return route()
    return inner
'''
    check("(p2) closure over enclosing-function param -> None",
          _find_destructive_deletion(PRE, post_closure_param) is None)


def _verify(tmp: Path, post: str, *, tool: str, args: dict, pre: str | None,
            name: str = "target.py") -> "ae._EditVerdict":
    p = tmp / name
    p.write_text(post, encoding="utf-8")
    return _verify_edit_quality(
        tool_name=tool,
        arguments={**args, "file_path": str(p)},
        file_path=str(p),
        pre_content=pre,
        task_objective="fix the exclude lane granularity in _matches_exclude",
    )


def test_integration() -> None:
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)

        # (f) write_region: destructive deletion flagged
        v = _verify(tmp, POST_DESTRUCTIVE, tool="write_region", args={}, pre=PRE)
        check("(f) write_region destructive -> passed False",
              v.passed is False)
        check("(f) write_region destructive -> reason destructive_deletion:route",
              str(v.reason).startswith("destructive_deletion:route"))
        check("(f) coaching names route + smallest old_string",
              "route" in v.coaching_message and "old_string" in v.coaching_message)

        # (g) write_region: clean edit not flagged as destructive
        v = _verify(tmp, POST_CLEAN, tool="write_region", args={}, pre=PRE)
        check("(g) write_region clean -> not a destructive_deletion verdict",
              not str(v.reason).startswith("destructive_deletion"))

        # (h) edit_file: same deletion via reversible substitution.
        # new_string is the replacement text (appears exactly once in post so the
        # pre-image reconstructs by reversing it back to old_string).
        old_string = (
            "def _matches_exclude(lane_id, token):\n"
            "    return token.split(\"-\")[0] == lane_id\n\n\n"
            "def _emit(payload, as_json):\n"
            "    print(payload)\n"
            "    return 0\n\n\n"
            "def route(role, subject, exclude):\n"
            "    return {\"ok\": True}\n"
        )
        new_string = (
            "def _matches_exclude(lane_id, token):\n"
            "    if \"-\" in token:\n"
            "        return False\n"
            "    return token.split(\"-\")[0] == lane_id\n"
        )
        v = _verify(tmp, POST_DESTRUCTIVE, tool="edit_file",
                    args={"old_string": old_string, "new_string": new_string},
                    pre=None)
        check("(h) edit_file destructive (reconstructed pre) -> destructive_deletion:route",
              v.passed is False and str(v.reason).startswith("destructive_deletion:route"))

        # (i) fail-safe: non-Python file — guard is Python-only, never raises.
        raised = False
        try:
            v = _verify(tmp, "# just markdown\nno defs here\n", tool="write_region",
                        args={}, pre="# old markdown\n", name="target.md")
        except Exception:  # noqa: BLE001
            raised = True
        check("(i) non-python file -> no crash",
              raised is False)
        check("(i) non-python file -> not a destructive_deletion verdict",
              raised is False and not str(v.reason).startswith("destructive_deletion"))


if __name__ == "__main__":
    print("test-destructive-deletion-guard")
    test_unit()
    test_integration()
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
