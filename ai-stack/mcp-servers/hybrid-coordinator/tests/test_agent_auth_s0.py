"""agent-auth AUTH-S0 (DESIGN 8.1): constant-time compare, empty-key fail-closed,
raw credential absent from audit identity. Hermetic."""

import ast
import os
import unittest
from pathlib import Path
from unittest import mock

from aiohttp import web
from aiohttp.test_utils import make_mocked_request

from middleware import auth
from shared import api_key_auth
from shared.api_key_auth import api_key_required, assert_key_provisioned, keys_equal


class KeysEqualTest(unittest.TestCase):
    def test_match_and_mismatch(self):
        self.assertTrue(keys_equal("s3cret", "s3cret"))
        self.assertFalse(keys_equal("s3cret", "s3creT"))
        self.assertFalse(keys_equal("s3cret-longer", "s3cret"))

    def test_empty_and_non_string_never_match(self):
        self.assertFalse(keys_equal("", ""))
        self.assertFalse(keys_equal(None, "x"))
        self.assertFalse(keys_equal("x", None))
        self.assertFalse(keys_equal(b"x", "x"))

    def test_non_ascii_does_not_raise(self):
        self.assertTrue(keys_equal("kéy", "kéy"))
        self.assertFalse(keys_equal("kéy", "key"))

    def test_uses_hmac_compare_digest(self):
        with mock.patch.object(api_key_auth.hmac, "compare_digest", return_value=True) as cd:
            self.assertTrue(keys_equal("a", "b"))
        cd.assert_called_once()


class ResolveAuthContextTest(unittest.TestCase):
    PATH = "/admin/v1/x"  # not a loopback-agent prefix, not public

    def _resolve(self, key, token):
        return auth.resolve_auth_context(self.PATH, "127.0.0.1", {"X-API-Key": token} if token else {}, key)

    def test_valid_and_invalid_key(self):
        ctx, status = self._resolve("k1", "k1")
        self.assertEqual((status, ctx["mode"]), (0, "api-key"))
        _, status = self._resolve("k1", "k2")
        self.assertEqual(status, 401)
        _, status = self._resolve("k1", "")
        self.assertEqual(status, 401)

    def test_empty_key_legacy_compat_when_not_required(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("AI_STACK_REQUIRE_API_KEY", None)
            ctx, status = self._resolve("", "")
        self.assertEqual((status, ctx["mode"]), (0, "no-api-key-configured"))

    def test_empty_key_rejected_when_required(self):
        with mock.patch.dict(os.environ, {"AI_STACK_REQUIRE_API_KEY": "1"}):
            for token in ("", "anything"):
                ctx, status = self._resolve("", token)
                self.assertEqual(status, 503)
                self.assertEqual(ctx["error"], "api_key_not_provisioned")

    def test_required_flag_does_not_break_loopback_prefixes_or_public(self):
        with mock.patch.dict(os.environ, {"AI_STACK_REQUIRE_API_KEY": "1"}):
            _, status = auth.resolve_auth_context("/hints", "127.0.0.1", {}, "")
            self.assertEqual(status, 0)
            _, status = auth.resolve_auth_context("/health", "10.0.0.5", {}, "")
            self.assertEqual(status, 0)


class StartupAssertionTest(unittest.TestCase):
    def test_required_and_empty_raises(self):
        with mock.patch.dict(os.environ, {"AI_STACK_REQUIRE_API_KEY": "true"}):
            self.assertTrue(api_key_required())
            for empty in ("", "  ", None):
                with self.assertRaises(RuntimeError):
                    assert_key_provisioned(empty, "svc")
            assert_key_provisioned("present", "svc")

    def test_not_required_is_noop(self):
        with mock.patch.dict(os.environ, {}):
            os.environ.pop("AI_STACK_REQUIRE_API_KEY", None)
            assert_key_provisioned("", "svc")

    def test_middleware_factory_fails_closed_without_key(self):
        with mock.patch.dict(os.environ, {"AI_STACK_REQUIRE_API_KEY": "1"}), \
                mock.patch.object(auth.Config, "API_KEY", ""):
            with self.assertRaises(RuntimeError):
                auth.create_api_key_middleware()
        with mock.patch.dict(os.environ, {"AI_STACK_REQUIRE_API_KEY": "1"}), \
                mock.patch.object(auth.Config, "API_KEY", "k"):
            auth.create_api_key_middleware()


_IMPL = Path(__file__).resolve().parents[1] / "http_server_impl.py"


def _load_audit_identity():
    """http_server_impl needs the full service env (mcp, strict config), so the
    function under test is extracted from source and exec'd in isolation."""
    tree = ast.parse(_IMPL.read_text())
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_audit_caller_identity")
    ns = {"web": web, "_AUTH_CONTEXT_KEY": auth.AUTH_CONTEXT_KEY, "_API_KEY_HEADER": auth.API_KEY_HEADER}
    exec(compile(ast.Module([fn], []), str(_IMPL), "exec"), ns)  # noqa: S102
    return ns["_audit_caller_identity"]


class AuditIdentityTest(unittest.TestCase):
    SECRET = "super-secret-key-value"

    def _identity(self, headers, ctx=None):
        req = make_mocked_request("GET", "/research/web/fetch", headers=headers)
        if ctx is not None:
            req[auth.AUTH_CONTEXT_KEY] = ctx
        return _load_audit_identity()(req)

    def test_raw_token_never_in_identity(self):
        for headers in ({"X-API-Key": self.SECRET}, {"Authorization": f"Bearer {self.SECRET}"}):
            for ctx in (None, {"mode": "api-key"}):
                self.assertNotIn(self.SECRET, self._identity(headers, ctx))
        self.assertEqual(self._identity({"X-API-Key": self.SECRET}, {"mode": "api-key"}), "api-key")
        self.assertEqual(self._identity({"X-API-Key": self.SECRET}), "credentialed")
        self.assertEqual(self._identity({}), "anonymous")

    def test_no_audit_site_assigns_raw_token(self):
        src = _IMPL.read_text()
        self.assertNotIn("caller_identity = token", src)
        self.assertEqual(src.count("caller_identity = _audit_caller_identity(request)"), 2)


if __name__ == "__main__":
    unittest.main()
