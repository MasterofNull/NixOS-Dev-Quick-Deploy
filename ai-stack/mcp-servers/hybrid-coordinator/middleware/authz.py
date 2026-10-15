"""
middleware/authz.py - agent-auth AUTH-S2: policy engine and shadow authorization.

Design: .agents/plans/agent-auth/DESIGN.md sections 4.1-4.4 (v1) and 6.1, 8.1 (v2).

S2 scope only: `off` and `shadow`. Shadow never blocks. It resolves a caller
class (stub: every TCP caller is `legacy-loopback`, valid-key callers are
`api-key`; real peer identity arrives with S3), matches the request to a scope
by longest prefix on (method, path), and records what enforcement WOULD say
(`X-AQ-Would-Deny` header, JSONL row, Prometheus counters). `enforce` and
`lockdown` are S5 and are treated as `shadow` here, with a startup warning.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
from datetime import date
from pathlib import Path
from typing import Optional

from aiohttp import web

from middleware.auth import AUTH_CONTEXT_KEY, PUBLIC_PATHS

logger = logging.getLogger("hybrid-coordinator.authz")

MODES = ("off", "shadow", "enforce", "lockdown")
AUDIT_MAX_BYTES = 50 * 1024 * 1024
AUDIT_KEEP = 3
WOULD_DENY_HEADER = "X-AQ-Would-Deny"
_REPO_ROOT = Path(__file__).resolve().parents[4]

try:  # metrics are optional (tests / minimal imports)
    from prometheus_client import Counter, Gauge, Histogram

    AUTH_DECISIONS = Counter(
        "agent_auth_decisions_total", "Agent-auth decisions",
        ["mode", "caller_class", "scope", "decision"],
    )
    AUTH_WOULD_DENY = Counter(
        "agent_auth_would_deny_total", "Requests enforcement would deny",
        ["caller_class", "scope"],
    )
    AUTH_DECISION_SECONDS = Histogram(
        "agent_auth_decision_seconds", "Agent-auth decision latency",
        buckets=(0.00001, 0.00005, 0.0001, 0.0005, 0.001, 0.005),
    )
    AUTH_SHADOW_ERRORS = Counter(
        "agent_auth_shadow_errors_total", "Shadow decision errors swallowed to keep requests flowing",
    )
    AUTH_EFFECTIVE_MODE = Gauge(
        "agent_auth_effective_mode", "1 for the (configured, effective) mode pair in force",
        ["configured", "effective"],
    )
    AUTH_POLICY_ERROR = Gauge("agent_auth_policy_error", "1 when the policy failed to load")
    AUTH_SHADOW_EXPIRED = Gauge(
        "agent_auth_shadow_expired", "1 when shadowUntil has passed while in shadow",
    )
except Exception:  # noqa: BLE001
    AUTH_DECISIONS = AUTH_WOULD_DENY = AUTH_DECISION_SECONDS = AUTH_SHADOW_EXPIRED = None
    AUTH_SHADOW_ERRORS = AUTH_EFFECTIVE_MODE = AUTH_POLICY_ERROR = None


class PolicyError(ValueError):
    """The policy file is structurally invalid."""


class Policy:
    """Parsed, validated agent-auth policy (config/agent-auth-policy.json)."""

    def __init__(self, data: dict, sha256: str = "") -> None:
        self.sha256 = sha256
        self.data = data
        self.default_scope = str(data.get("default_scope") or "admin")
        self.public_scope = str(data.get("public_paths_scope") or "public")
        self.scopes: dict = dict(data.get("scopes") or {})
        self.classes: dict = {k: frozenset(v) for k, v in (data.get("classes") or {}).items()}
        flat = []
        for rule in data.get("rules") or []:
            methods = frozenset(m.upper() for m in rule.get("methods") or [])
            for prefix in rule.get("prefixes") or []:
                flat.append((prefix, methods, rule["scope"]))
        # Longest prefix first; at equal length a methods-restricted rule wins.
        flat.sort(key=lambda e: (-len(e[0]), 0 if e[1] else 1))
        self._rules = flat
        self.validate()

    def validate(self) -> None:
        for name in (self.default_scope, self.public_scope):
            if name not in self.scopes:
                raise PolicyError(f"scope '{name}' is not declared")
        for scope, body in self.scopes.items():
            if not (isinstance(body, dict) and body.get("why") and body.get("hint")):
                raise PolicyError(f"scope '{scope}' lacks guidance (why/hint)")
        for _, _, scope in self._rules:
            if scope not in self.scopes:
                raise PolicyError(f"rule references undeclared scope '{scope}'")
        for cls, granted in self.classes.items():
            for scope in granted:
                if scope not in self.scopes:
                    raise PolicyError(f"class '{cls}' grants undeclared scope '{scope}'")
        owner = self.classes.get("owner-agent", frozenset())
        for name, scopes in (self.data.get("self_service") or {}).items():
            if not (set(scopes) < set(owner)):
                raise PolicyError(f"self_service profile '{name}' is not a strict subset of owner-agent")

    def match(self, method: str, path: str) -> tuple:
        """Return (scope, matched_prefix). Unmatched routes get default_scope."""
        if path in PUBLIC_PATHS:
            return self.public_scope, path
        method = method.upper()
        for prefix, methods, scope in self._rules:
            if path.startswith(prefix) and (not methods or method in methods):
                return scope, prefix
        return self.default_scope, ""

    def allows(self, caller_class: str, scope: str) -> bool:
        if scope == self.public_scope:
            return True
        return scope in self.classes.get(caller_class, frozenset())

    def guidance(self, scope: str) -> dict:
        return dict(self.scopes.get(scope) or self.scopes[self.default_scope])


def load_policy(path: Optional[str] = None) -> Policy:
    path = path or os.getenv("AQ_AGENT_AUTH_POLICY") or str(_REPO_ROOT / "config" / "agent-auth-policy.json")
    raw = Path(path).read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    policy = Policy(json.loads(raw), digest)
    logger.info("agent-auth policy loaded path=%s sha256=%s", path, digest)
    return policy


def resolve_class(request: web.Request) -> str:
    """S2 stub. S3 replaces this with SO_PEERCRED/cgroup identity (design 2)."""
    ctx = request.get(AUTH_CONTEXT_KEY)
    if isinstance(ctx, dict) and ctx.get("mode") == "api-key":
        return "api-key"
    return "legacy-loopback"


def configured_mode() -> str:
    mode = os.getenv("AQ_AGENT_AUTH_MODE", "off").strip().lower()
    return mode if mode in MODES else "off"


def shadow_expired(mode: str, until: str, today: Optional[date] = None) -> bool:
    """Design 6.1: expiry is a runtime signal, never a silent auto-enforce."""
    if mode != "shadow" or not until:
        return False
    try:
        return (today or date.today()) > date.fromisoformat(until)
    except ValueError:
        return False


class _Audit:
    """Single-write JSONL appender with size rotation (design 4.4)."""

    def __init__(self, path: str) -> None:
        self.path = path
        self._lock = threading.Lock()
        self._fd: Optional[int] = None

    def _rotate(self) -> None:
        os.close(self._fd)
        self._fd = None
        for i in range(AUDIT_KEEP - 1, 0, -1):
            src = f"{self.path}.{i}"
            if os.path.exists(src):
                os.replace(src, f"{self.path}.{i + 1}")
        os.replace(self.path, f"{self.path}.1")

    def write(self, row: dict) -> None:
        line = (json.dumps(row, separators=(",", ":"))[:4000] + "\n").encode()
        try:
            with self._lock:
                if self._fd is None:
                    os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
                    self._fd = os.open(self.path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o640)
                if os.fstat(self._fd).st_size >= AUDIT_MAX_BYTES:
                    self._rotate()
                    self._fd = os.open(self.path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o640)
                os.write(self._fd, line)
        except OSError as exc:
            logger.warning("agent-auth audit write failed: %s", exc)


class AuthzState:
    """Process-wide counters backing GET /admin/v1/auth/stats."""

    def __init__(self) -> None:
        self.policy: Optional[Policy] = None
        self.mode = "off"
        self.shadow_until = ""
        self.decisions: dict = {}
        self.would_deny: dict = {}
        self.policy_error = ""
        self.configured_mode = "off"
        self.shadow_errors = 0

    def snapshot(self) -> dict:
        top = sorted(self.would_deny.items(), key=lambda kv: -kv[1])[:20]
        return {
            "mode": self.mode,
            "shadow_until": self.shadow_until or None,
            "shadow_expired": shadow_expired(self.mode, self.shadow_until),
            "configured_mode": self.configured_mode,
            "shadow_errors": self.shadow_errors,
            "policy_error": self.policy_error or None,
            "policy_sha256": self.policy.sha256 if self.policy else None,
            "decisions": [
                {"caller_class": c, "scope": s, "decision": d, "count": n}
                for (c, s, d), n in sorted(self.decisions.items())
            ],
            "would_deny": [
                {"caller_class": c, "scope": s, "count": n} for (c, s), n in top
            ],
        }


STATE = AuthzState()


def explain(policy: Policy, method: str, path: str, caller_class: str) -> dict:
    scope, prefix = policy.match(method, path)
    allowed = policy.allows(caller_class, scope)
    out = {
        "method": method.upper(), "path": path, "caller_class": caller_class,
        "scope": scope, "matched_prefix": prefix, "decision": "allow" if allowed else "would-deny",
    }
    if not allowed:
        out["guidance"] = policy.guidance(scope)
    return out


def _passthrough():
    @web.middleware
    async def authz_off(request: web.Request, handler):
        return await handler(request)
    return authz_off


def _publish_mode(configured: str, effective: str, policy_error: bool) -> None:
    """S8 health-spider must go RED when configured=shadow and effective=off."""
    STATE.configured_mode = configured
    STATE.mode = effective
    if AUTH_EFFECTIVE_MODE is not None:
        for c in MODES:
            for e in MODES:
                AUTH_EFFECTIVE_MODE.labels(c, e).set(1 if (c, e) == (configured, effective) else 0)
        AUTH_POLICY_ERROR.set(1 if policy_error else 0)


_last_error_log = 0.0


def _note_shadow_error(exc: Exception) -> None:
    global _last_error_log
    if AUTH_SHADOW_ERRORS is not None:
        AUTH_SHADOW_ERRORS.inc()
    STATE.shadow_errors += 1
    now = time.monotonic()
    if now - _last_error_log >= 60:
        _last_error_log = now
        logger.error("agent-auth shadow decision failed; request passed through: %r", exc)


def create_authz_middleware(policy: Optional[Policy] = None, mode: Optional[str] = None,
                            audit_path: Optional[str] = None):
    """Return the shadow-authorization middleware (a pass-through when mode is off)."""
    configured = (mode or configured_mode())
    effective = configured
    STATE.shadow_until = os.getenv("AQ_AGENT_AUTH_SHADOW_UNTIL", "")
    if AUTH_SHADOW_EXPIRED is not None:
        AUTH_SHADOW_EXPIRED.set(1 if shadow_expired(configured, STATE.shadow_until) else 0)
    if configured in ("enforce", "lockdown"):
        logger.warning("agent-auth mode '%s' is not implemented until AUTH-S5; running as shadow", configured)
        effective = "shadow"
    if effective == "off":
        _publish_mode(configured, "off", False)
        return _passthrough()

    try:
        policy = policy or load_policy()
    except Exception as exc:  # noqa: BLE001
        # Shadow never blocks, so a bad/missing policy must not take the coordinator down.
        logger.error("agent-auth policy unavailable (%s); shadow disabled", exc)
        STATE.policy_error = str(exc)
        _publish_mode(configured, "off", True)
        return _passthrough()
    STATE.policy = policy
    STATE.policy_error = ""
    _publish_mode(configured, effective, False)
    audit = _Audit(audit_path or os.getenv(
        "AQ_AGENT_AUTH_AUDIT_PATH", "/var/lib/ai-stack/hybrid/telemetry/agent-auth.jsonl"))

    def decide(request: web.Request) -> tuple:
        start = time.perf_counter_ns()
        caller_class = resolve_class(request)
        scope, prefix = policy.match(request.method, request.path)
        allowed = policy.allows(caller_class, scope)
        decision = "allow" if allowed else "would-deny"
        deny_id = ""
        key = (caller_class, scope, decision)
        STATE.decisions[key] = STATE.decisions.get(key, 0) + 1
        if not allowed:
            wk = (caller_class, scope)
            STATE.would_deny[wk] = STATE.would_deny.get(wk, 0) + 1
            deny_id = f"d-{time.strftime('%Y%m%d')}-{os.urandom(2).hex()}"
        latency_us = (time.perf_counter_ns() - start) // 1000
        if AUTH_DECISIONS is not None:
            AUTH_DECISIONS.labels("shadow", caller_class, scope, decision).inc()
            AUTH_DECISION_SECONDS.observe(latency_us / 1e6)
            if not allowed:
                AUTH_WOULD_DENY.labels(caller_class, scope).inc()
        # Log every would-deny and every allow that is not a read/public scope.
        if not allowed or not scope.startswith(("read.", "public")):
            audit.write({
                "ts": time.time(), "decision": decision, "mode": "shadow",
                "caller_class": caller_class, "peer_uid": None, "unit": None,
                "run_id": None, "jti8": None, "listener": "tcp",
                "method": request.method, "path_family": prefix, "scope": scope,
                "deny_id": deny_id or None, "latency_us": latency_us,
            })
        return allowed, scope, deny_id

    @web.middleware
    async def authz_shadow(request: web.Request, handler):
        try:
            allowed, scope, deny_id = decide(request)
        except Exception as exc:  # noqa: BLE001 - shadow must never fail a request
            _note_shadow_error(exc)
            return await handler(request)
        response = await handler(request)
        if not allowed and isinstance(response, web.StreamResponse) and not response.prepared:
            response.headers[WOULD_DENY_HEADER] = f"scope={scope};id={deny_id}"
        return response

    return authz_shadow


# ---------------------------------------------------------------------------
# Admin endpoints (registered from control/control_service.py)
# ---------------------------------------------------------------------------


async def handle_auth_stats(request: web.Request) -> web.Response:
    """GET /admin/v1/auth/stats - mode, per-class decisions, top would-deny scopes."""
    return web.json_response(STATE.snapshot())


async def handle_auth_explain(request: web.Request) -> web.Response:
    """GET /admin/v1/auth/explain?path=&method=&class= - what the policy would say."""
    q = request.query
    path = q.get("path", "")
    if not path.startswith("/"):
        return web.json_response({"error": "path query parameter required"}, status=400)
    policy = STATE.policy
    if policy is None:
        try:
            policy = load_policy()
        except Exception as exc:  # noqa: BLE001
            return web.json_response({"error": f"policy unavailable: {exc}"}, status=503)
    return web.json_response(
        explain(policy, q.get("method", "GET"), path, q.get("class", "legacy-loopback")))
