"""agent-auth AUTH-S0 on aidb (DESIGN 8.1, section 5.4 aidb fail-closed).

aidb/server.py needs sqlalchemy and the full service env, so the auth methods
are extracted from source and exec'd against a stub settings object.
"""
import ast
import __future__
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from fastapi import HTTPException

SERVERS = Path(__file__).resolve().parents[2] / "mcp-servers"
sys.path.insert(0, str(SERVERS))
from shared.api_key_auth import api_key_required, assert_key_provisioned, keys_equal  # noqa: E402

SRC = (SERVERS / "aidb" / "server.py").read_text()
WANTED = {"_require_api_key", "_authenticate", "_validate_tool_disclosure"}


def _methods():
    ns = {"HTTPException": HTTPException, "api_key_required": api_key_required, "keys_equal": keys_equal,
          "Any": object, "Dict": dict, "Optional": object, "Request": object}
    funcs = [n for c in ast.walk(ast.parse(SRC)) if isinstance(c, ast.ClassDef)
             for n in c.body if isinstance(n, ast.FunctionDef) and n.name in WANTED]
    # _require_api_key is defined twice; the later (effective) definition wins, as in the class body.
    mod = ast.Module(funcs, [])
    ast.fix_missing_locations(mod)
    exec(compile(mod, "aidb/server.py", "exec", flags=__future__.annotations.compiler_flag), ns)  # noqa: S102
    return ns


def _req(**headers):
    return SimpleNamespace(headers={k.replace("_", "-"): v for k, v in headers.items()})


class AidbAuthTest(unittest.TestCase):
    def setUp(self):
        self.ns = _methods()
        os.environ.pop("AI_STACK_REQUIRE_API_KEY", None)

    def _srv(self, key):
        return SimpleNamespace(settings=SimpleNamespace(api_key=key, full_tool_disclosure_requires_key=True))

    def test_every_compare_is_constant_time(self):
        self.assertGreaterEqual(SRC.count("keys_equal("), 4)
        for bad in ("token != expected", "token != self.settings.api_key", "api_key != self.settings.api_key"):
            self.assertNotIn(bad, SRC)

    def test_http_valid_invalid(self):
        s = self._srv("k1")
        self.ns["_require_api_key"](s, _req(x_api_key="k1"))
        self.ns["_require_api_key"](s, _req(authorization="Bearer k1"))
        for r in (_req(x_api_key="nope"), _req()):
            with self.assertRaises(HTTPException) as ctx:
                self.ns["_require_api_key"](s, r)
            self.assertEqual(ctx.exception.status_code, 401)

    def test_empty_key_compat_when_not_required(self):
        self.ns["_require_api_key"](self._srv(None), _req())

    def test_empty_key_rejected_when_required(self):
        with mock.patch.dict(os.environ, {"AI_STACK_REQUIRE_API_KEY": "1"}):
            for key in (None, ""):
                with self.assertRaises(HTTPException) as ctx:
                    self.ns["_require_api_key"](self._srv(key), _req(x_api_key="anything"))
                self.assertEqual(ctx.exception.status_code, 503)
                with self.assertRaises(PermissionError):
                    self.ns["_authenticate"](self._srv(key), {"api_key": "anything"})
                with self.assertRaises(RuntimeError):
                    assert_key_provisioned(key, "aidb")

    def test_message_auth_and_disclosure(self):
        s = self._srv("k1")
        self.ns["_authenticate"](s, {"api_key": "k1"})
        with self.assertRaises(PermissionError):
            self.ns["_authenticate"](s, {"api_key": "x"})
        s.settings.full_tool_disclosure_requires_key = True
        with self.assertRaises(PermissionError):
            self.ns["_validate_tool_disclosure"](s, "full", "wrong")
        self.assertEqual(self.ns["_validate_tool_disclosure"](s, "full", "k1"), "full")

    def test_startup_asserts_provisioned_key(self):
        self.assertIn('assert_key_provisioned(self.settings.api_key, "aidb")', SRC)


if __name__ == "__main__":
    unittest.main()
