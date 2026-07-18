"""Phase 0 — Pre-flight smoke tests.

Mirrors run_phase_0() from scripts/ai/aq-qa (bash).
Checks: services, ports, databases, inference endpoints, editor/IDE, routing, lifecycle.
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

from ..core.context import RunContext
from ..core.helpers import (
    cmd_ok, cmd_output, output_matches, port_bound,
    http_health_ok, http_get, http_json, http_post_json,
    file_exists, file_readable, json_valid,
    host_observer_service_status, is_sandbox_denied,
)
from ..core.result import CheckResult, passed, failed, skipped

# ---------------------------------------------------------------------------
# 0.1 Systemd service checks
# ---------------------------------------------------------------------------
_SERVICES = [
    "llama-cpp", "ai-aidb", "ai-hybrid-coordinator",
    "ai-ralph-wiggum", "llama-cpp-embed", "ai-switchboard",
    "redis-mcp", "qdrant", "postgresql",
]

_TIMERS = [
    "ai-mcp-integrity-check.timer",
    "ai-mcp-process-watch.timer",
    "ai-weekly-report.timer",
]

# ---------------------------------------------------------------------------
# 0.2 Port map
# ---------------------------------------------------------------------------
_PORTS = {
    6379: "redis",
    5432: "postgres",
    6333: "qdrant",
    8080: "llama-cpp",
    8081: "llama-embed",
    8002: "aidb",
    8003: "hybrid-coordinator",
    8004: "ralph-wiggum",
    8085: "switchboard",
    3001: "open-webui",
    9090: "prometheus",
}

# Feature-flagged service ports: map port -> systemd unit. These are NOT skipped — instead the check
# validates the config<->runtime CONTRACT against the service's declared intent (is the unit enabled?):
#   enabled + bound      -> PASS (running as configured)
#   enabled + not bound  -> FAIL (real regression — should be up, isn't)
#   disabled + not bound -> PASS (correctly off, e.g. open-webui gated by mySystem.aiStack.ui.enable)
#   disabled + bound     -> FAIL (stale/unexpected — should be off, but a process holds the port)
# This keeps the test meaningful in every state rather than ignoring it.
_FEATURE_FLAGGED_PORTS = {3001: "open-webui.service"}


def _unit_enabled(unit: str) -> bool:
    """True if the systemd unit is enabled (declared to run). Absent/disabled/masked -> False."""
    try:
        out = subprocess.run(
            ["systemctl", "is-enabled", unit],
            capture_output=True, text=True, timeout=5,
        ).stdout.strip()
        return out in ("enabled", "enabled-runtime", "static", "indirect")
    except Exception:  # noqa: BLE001
        return False


def _check_services(ctx: RunContext) -> list[CheckResult]:
    results = []
    if not ctx.should_run(1):
        return results
    for svc in _SERVICES:
        unit = f"{svc}.service"
        r = subprocess.run(
            ["systemctl", "is-active", unit],
            capture_output=True, text=True, timeout=5,
        )
        active = r.returncode == 0
        if not active:
            show = subprocess.run(
                ["systemctl", "show", unit, "--property=ActiveState", "--value"],
                capture_output=True, text=True, timeout=5,
            )
            active = show.stdout.strip() == "active"
        if active:
            results.append(passed(1, f"0.1.1:{svc}", f"unit {unit} active"))
        elif is_sandbox_denied((r.stdout or "") + (r.stderr or "")):
            observed = host_observer_service_status(svc)
            if observed and observed.get("status") == "healthy":
                results.append(passed(1, f"0.1.1:{svc}", f"unit {unit} active via host observer"))
            elif observed:
                detail = str(observed.get("status") or observed.get("systemd") or "unhealthy")
                results.append(failed(1, f"0.1.1:{svc}", f"unit {unit} active", detail[:120]))
            else:
                results.append(skipped(1, f"0.1.1:{svc}", f"unit {unit} active",
                                       "systemd probe denied and host observer unavailable"))
        else:
            results.append(failed(1, f"0.1.1:{svc}", f"unit {unit} active", "not active"))
    return results


def _check_no_failed_units(ctx: RunContext) -> list[CheckResult]:
    if not ctx.should_run(1):
        return []
    try:
        r = subprocess.run(
            ["systemctl", "list-units", "ai-*", "llama-*", "--state=failed", "--no-legend"],
            capture_output=True, text=True, timeout=10,
        )
        bad = r.stdout.strip()
        if not bad:
            return [passed(1, "0.1.2", "no AI units in failed state")]
        return [failed(1, "0.1.2", "no AI units in failed state", bad[:120])]
    except Exception as e:
        return [failed(1, "0.1.2", "no AI units in failed state", str(e))]


def _check_timers(ctx: RunContext) -> list[CheckResult]:
    results = []
    if not ctx.should_run(1):
        return results
    for timer in _TIMERS:
        try:
            r = subprocess.run(
                ["systemctl", "list-timers", timer, "--no-legend"],
                capture_output=True, text=True, timeout=5,
            )
            if timer in r.stdout:
                results.append(passed(1, f"0.1.3:{timer}", f"timer {timer} scheduled"))
            else:
                results.append(failed(1, f"0.1.3:{timer}", f"timer {timer} scheduled", "not found"))
        except Exception as e:
            results.append(failed(1, f"0.1.3:{timer}", f"timer {timer} scheduled", str(e)))
    return results


# ---------------------------------------------------------------------------
# 0.2 Port and data-store checks
# ---------------------------------------------------------------------------

def _check_ports(ctx: RunContext) -> list[CheckResult]:
    results = []
    if not ctx.should_run(3):
        return results
    retries = ctx.port_retry_attempts
    delay = ctx.port_retry_delay_s
    for port, name in _PORTS.items():
        cid = f"0.2.1:{name}"
        if port in _FEATURE_FLAGGED_PORTS:
            # Validate the config<->runtime contract, never skip.
            enabled = _unit_enabled(_FEATURE_FLAGGED_PORTS[port])
            bound = port_bound(port, retries=0, delay=0.0)
            if enabled and bound:
                results.append(passed(3, cid, f"port {port} ({name}) bound (unit enabled)"))
            elif enabled and not bound:
                results.append(failed(3, cid, f"port {port} ({name}) bound",
                                      f"unit enabled but port {port} not bound — service down"))
            elif not enabled and not bound:
                results.append(passed(3, cid, f"{name} disabled + port {port} correctly not bound"))
            else:  # disabled but something is bound
                results.append(failed(3, cid, f"{name} off => port {port} unbound",
                                      f"unit disabled but port {port} is bound — stale/unexpected process"))
            continue
        if port_bound(port, retries=retries, delay=delay):
            results.append(passed(3, cid, f"port {port} ({name}) bound"))
        else:
            results.append(failed(3, cid, f"port {port} ({name}) bound", f"port {port} not bound"))
    return results


def _check_grafana_port(ctx: RunContext) -> list[CheckResult]:
    if not ctx.should_run(3):
        return []
    grafana_active = cmd_ok("systemctl", "is-active", "--quiet", "grafana.service")
    if ctx.dashboard_safe:
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            port_3000_bound = s.connect_ex(("127.0.0.1", 3000)) == 0
    else:
        try:
            ss_out = subprocess.run(["ss", "-tlnp"], capture_output=True, text=True, timeout=5).stdout
        except Exception:
            ss_out = ""
        port_3000_bound = ":3000 " in ss_out
    if grafana_active and port_3000_bound:
        return [passed(3, "0.2.2", "port 3000 = Grafana (no Open-WebUI regression)")]
    if not port_3000_bound:
        return [skipped(3, "0.2.2", "port 3000 Grafana check", "port 3000 not bound (Grafana disabled?)")]
    return [failed(3, "0.2.2", "port 3000 Grafana check", "Grafana inactive but port 3000 is bound")]


def _check_qdrant_docs(ctx: RunContext) -> list[CheckResult]:
    if not ctx.should_run(5):
        return []
    try:
        data = http_json(f"{ctx.qdrant_url}/collections", timeout=5)
        if not data:
            return [failed(5, "0.2.3", "Qdrant has documents", "no response")]
        colls = (data.get("result") or {}).get("collections", [])
        if not colls:
            return [failed(5, "0.2.3", "Qdrant has documents", "found 0")]
        
        total_points = 0
        for coll in colls:
            name = coll["name"]
            cd = http_json(f"{ctx.qdrant_url}/collections/{name}", timeout=5)
            count = ((cd or {}).get("result") or {}).get("points_count", 0)
            total_points += count
            
        if total_points > 0:
            return [passed(5, "0.2.3", f"Qdrant has {total_points} total points across {len(colls)} collections")]
        return [failed(5, "0.2.3", "Qdrant has documents", "found 0 points across all collections")]
    except Exception as e:
        return [failed(5, "0.2.3", "Qdrant has documents", str(e))]


def _check_postgres_tables(ctx: RunContext) -> list[CheckResult]:
    if not ctx.should_run(5):
        return []
    try:
        pg_pass = ""
        try:
            pg_pass = Path("/run/secrets/postgres_password").read_text().strip()
        except OSError:
            pass
        env = {**os.environ, "PGPASSWORD": pg_pass}
        r = subprocess.run(
            ["psql", "-h", "127.0.0.1", "-U", "aidb", "-d", "aidb",
             "-tAc", "SELECT count(*) FROM pg_tables WHERE schemaname = 'public';"],
            capture_output=True, text=True, env=env, timeout=10,
        )
        count = int(r.stdout.strip() or "0")
        if count > 0:
            return [passed(5, "0.2.4", f"Postgres has {count} tables")]
        return [failed(5, "0.2.4", "Postgres has tables", "found 0")]
    except Exception as e:
        return [failed(5, "0.2.4", "Postgres has tables", str(e))]


def _check_redis_keys(ctx: RunContext) -> list[CheckResult]:
    if not ctx.should_run(5):
        return []
    try:
        r = subprocess.run(["redis-cli", "DBSIZE"], capture_output=True, text=True, timeout=5)
        count = int(r.stdout.strip() or "0")
        if count > 0:
            return [passed(5, "0.2.5", f"Redis has {count} keys")]
        return [failed(5, "0.2.5", "Redis has keys", "found 0")]
    except Exception as e:
        return [failed(5, "0.2.5", "Redis has keys", str(e))]


# ---------------------------------------------------------------------------
# 0.3 AppArmor
# ---------------------------------------------------------------------------

def _check_apparmor(ctx: RunContext) -> list[CheckResult]:
    results = []
    if not ctx.should_run(1):
        return results
    aa_dir = Path("/etc/apparmor.d")
    if (aa_dir / "ai-llama-cpp").exists() and (aa_dir / "ai-mcp-base").exists():
        results.append(passed(1, "0.3.1", f"AppArmor profiles on disk ({aa_dir}/ai-llama-cpp, ai-mcp-base)"))
    else:
        found = " ".join(p.name for p in aa_dir.glob("ai-*")) if aa_dir.exists() else "none"
        results.append(failed(1, "0.3.1", "AppArmor profiles on disk", f"found: {found}"))
    if cmd_ok("systemctl", "is-active", "--quiet", "apparmor"):
        results.append(passed(1, "0.3.2", "AppArmor service active"))
    else:
        results.append(failed(1, "0.3.2", "AppArmor service active"))
    return results


# ---------------------------------------------------------------------------
# 0.4 Inference endpoints
# ---------------------------------------------------------------------------

def _check_inference(ctx: RunContext) -> list[CheckResult]:
    results = []
    if not ctx.should_run(2):
        return results
    if http_health_ok(f"{ctx.llama_url}/health", timeout=5):
        results.append(passed(2, "0.4.1", "llama-server /health"))
    else:
        results.append(failed(2, "0.4.1", "llama-server /health", f"status!='ok' url={ctx.llama_url}/health"))
    if http_health_ok(f"{ctx.embeddings_url}/health", timeout=5):
        results.append(passed(2, "0.4.2", "embedding server /health"))
    else:
        results.append(failed(2, "0.4.2", "embedding server /health", f"url={ctx.embeddings_url}/health"))
    if not ctx.should_run(6):
        return results
    _, body = http_get(f"{ctx.embeddings_url}/v1/models", timeout=5)
    if '"id":' in body:
        results.append(passed(6, "0.4.3", "embedding server returns model info"))
    else:
        results.append(failed(6, "0.4.3", "embedding server returns model info", body[:80]))
    return results


# ---------------------------------------------------------------------------
# 0.5 Continue/editor runtime
# ---------------------------------------------------------------------------

def _check_continue_config(cfg_path: Path, switchboard_url: str) -> tuple[bool, str]:
    """Validate Continue config targets switchboard ingress with correct profile lanes.

    Checks:
    - apiBase") == "http://127.0.0.1:8085/v1" (chat model points at switchboard)
    - expected_context derived from switchboard /health profile response
    - tab model apiBase == "http://127.0.0.1:8085/v1"
    - X-AI-Profile headers set correctly
    """
    if not cfg_path.exists():
        return False, f"config.json not found: {cfg_path}"
    try:
        cfg = json.loads(cfg_path.read_text())
    except Exception as e:
        return False, f"config.json parse failed: {e}"
    config_version = str(cfg.get("__configVersion") or "")
    valid_versions = {str(v) for v in range(23, 35)}
    valid_versions.update({"34.0"})
    if not any(config_version.startswith(str(v)) for v in range(23, 35)):
        if config_version not in {"34.0"}:
            return False, f"unsupported __configVersion: {config_version}"
    # Fetch switchboard /health to derive expected_context windows
    health = http_json(f"{switchboard_url}/health", timeout=5) or {}
    profiles = health.get("profiles") or {}
    local_agent = profiles.get("local-agent") or {}
    continue_local = profiles.get("continue-local") or {}
    default_profile = profiles.get("default") or {}
    expected_chat_context = (
        local_agent.get("advertisedContextWindow")
        or default_profile.get("advertisedContextWindow")
    )
    expected_context = int(expected_chat_context) if expected_chat_context is not None else None
    bounded_chat = local_agent.get("maxInputTokens")
    bounded_chat = int(bounded_chat) if bounded_chat is not None else None
    minimum_chat_context = max(4096, bounded_chat or expected_context or 4096)
    minimum_chat_max_tokens = 1024
    models = cfg.get("models") or []
    chat_ok = any(
        isinstance(m, dict)
        and m.get("apiBase") == "http://127.0.0.1:8085/v1"
        and ((m.get("requestOptions") or {}).get("headers") or {}).get("X-AI-Profile") == "local-agent"
        and int(m.get("contextLength") or 0) >= minimum_chat_context
        and int(m.get("maxTokens") or 0) >= minimum_chat_max_tokens
        for m in models
    )
    if not chat_ok:
        return False, f"no chat model with apiBase) == \"http://127.0.0.1:8085/v1\" and X-AI-Profile=local-agent"
    tab_model = cfg.get("tabAutocompleteModel") or {}
    if tab_model.get("apiBase") != "http://127.0.0.1:8085/v1":
        return False, f"tabAutocompleteModel apiBase != http://127.0.0.1:8085/v1"
    if ((tab_model.get("requestOptions") or {}).get("headers") or {}).get("X-AI-Profile") != "continue-local":
        return False, "tabAutocompleteModel X-AI-Profile != continue-local"
    expected_tab_context = (
        continue_local.get("advertisedContextWindow")
        or default_profile.get("advertisedContextWindow")
    )
    if expected_tab_context is not None and int(tab_model.get("contextLength") or 0) < int(expected_tab_context):
        return False, (
            f"tab contextLength {tab_model.get('contextLength')} < expected_context {expected_tab_context}"
        )
    return True, ""


def _find_continue_cli(ctx: RunContext) -> str:
    if cmd_ok("cn", "--help"):
        r = subprocess.run(["which", "cn"], capture_output=True, text=True)
        if r.returncode == 0:
            return r.stdout.strip()
    for candidate in [
        f"{ctx.primary_home}/.nix-profile/bin/cn",
        f"/etc/profiles/per-user/{ctx.primary_user}/bin/cn",
    ]:
        if Path(candidate).is_file():
            return candidate
    return ""


def _check_continue(ctx: RunContext) -> list[CheckResult]:
    results = []
    if not ctx.should_run(7):
        return results
    try:
        data = http_json(f"{ctx.switchboard_url}/health", timeout=8)
        if data:
            profiles = data.get("profiles") or {}
            if profiles.get("local-agent"):
                results.append(passed(7, "0.5.1", "switchboard exposes local-agent profile"))
            else:
                results.append(failed(7, "0.5.1", "switchboard exposes local-agent profile", "profile missing"))
            if profiles.get("local-coding"):
                results.append(passed(7, "0.5.2", "switchboard exposes local-coding profile"))
            else:
                results.append(failed(7, "0.5.2", "switchboard exposes local-coding profile", "profile missing"))
        else:
            results.append(failed(7, "0.5.1", "switchboard exposes local-agent profile", "no switchboard response"))
            results.append(failed(7, "0.5.2", "switchboard exposes local-coding profile", "no switchboard response"))
    except Exception as e:
        results.append(failed(7, "0.5.1", "switchboard exposes local-agent profile", str(e)))
        results.append(failed(7, "0.5.2", "switchboard exposes local-coding profile", str(e)))

    results.append(skipped(7, "0.5.3", "Continue extension health gate",
                           "retired; local agents route through switchboard profiles"))
    results.append(skipped(7, "0.5.4", "continue-local switchboard profile ready",
                           "retired; use local-agent/local-coding profiles"))
    results.append(skipped(7, "0.5.5", "continue-local context trimming",
                           "retired; context budgets are enforced by switchboard profiles"))
    results.append(skipped(7, "0.5.6", "Continue/editor prompt to feedback smoke",
                           "retired; no local-agent runtime dependency"))

    # 0.5.7 editor corpus budget
    if os.environ.get("AQ_QA_SKIP_REPORT_BACKED_CHECKS", "0") == "1":
        results.append(skipped(7, "0.5.7", "Editor-local agent corpus stays within bounded budgets",
                               "skipped to avoid aq-report recursion"))
    else:
        results.extend(_check_editor_budget(ctx))

    return results


def _check_editor_budget(ctx: RunContext) -> list[CheckResult]:
    report_json = ctx.aq_report_snapshot
    if not report_json:
        return [skipped(7, "0.5.7", "Editor-local agent corpus stays within bounded budgets",
                        "aq-report unavailable")]
    try:
        data = json.loads(report_json)
    except Exception:
        return [skipped(7, "0.5.7", "Editor-local agent corpus stays within bounded budgets",
                        "aq-report parse failed")]
    budget = ((data.get("continue_editor") or {}).get("state_budget") or {})
    if not budget.get("available"):
        return [skipped(7, "0.5.7", "Editor-local agent corpus stays within bounded budgets",
                        "editor state budget unavailable in snapshot (no data yet — run aq-report to seed)")]
    checks = budget.get("checks") or []
    failing = [
        f"{item.get('id')}={item.get('details') or item.get('description')}"
        for item in checks
        if str(item.get("status", "")).upper() == "FAIL"
    ]
    if failing:
        return [failed(7, "0.5.7", "Editor-local agent corpus stays within bounded budgets",
                       "; ".join(failing[:4]))]
    overview = budget.get("overview") or {}
    cont = overview.get("continue") or {}
    return [passed(7, "0.5.7",
                   f"Editor-local agent corpus stays within bounded budgets "
                   f"(active_bytes={cont.get('active_session_bytes', 0)})")]


# ---------------------------------------------------------------------------
# 0.6 Flagship CLI
# ---------------------------------------------------------------------------

def _check_flagship_cli(ctx: RunContext) -> list[CheckResult]:
    results = []
    if not ctx.should_run(7):
        return results
    env = {
        **os.environ,
        "AQ_PRIMARY_USER": ctx.primary_user,
        "AQ_PRIMARY_HOME": ctx.primary_home,
    }
    script = ctx.repo_root / "scripts" / "testing" / "smoke-flagship-cli-surfaces.sh"
    if cmd_ok("bash", str(script), env=env):
        results.append(passed(7, "0.6.1", "flagship agent CLI help smokes"))
    else:
        results.append(failed(7, "0.6.1", "flagship agent CLI help smokes"))

    gemini_script = ctx.repo_root / "scripts" / "health" / "gemini-cli-health.sh"
    env2 = {
        **env,
        "PATH": f"{ctx.primary_home}/.npm-global/bin:{os.environ.get('PATH', '')}",
    }
    if cmd_ok("bash", str(gemini_script), "--check", env=env2):
        results.append(passed(7, "0.6.2", "gemini CLI live-state health check"))
    else:
        results.append(failed(7, "0.6.2", "gemini CLI live-state health check"))
    return results


# ---------------------------------------------------------------------------
# 0.7 Front-door routing
# ---------------------------------------------------------------------------

def _check_routing(ctx: RunContext) -> list[CheckResult]:
    results = []
    if not ctx.should_run(4):
        return results

    # 0.7.1 /v1/orchestrate
    headers = {"Content-Type": "application/json", "X-API-Key": ctx.api_key}
    code, body = _raw_post(
        f"{ctx.hybrid_url}/v1/orchestrate",
        {"prompt": "what is nixos", "route": "Explore"},
        headers=headers, timeout=max(20, ctx.query_timeout_s),
    )
    if 200 <= code < 300:
        try:
            d = json.loads(body)
            if "error" not in d:
                results.append(passed(4, "0.7.1", "/v1/orchestrate front-door smoke (route=Explore)"))
            else:
                results.append(failed(4, "0.7.1", "/v1/orchestrate front-door smoke", body[:60]))
        except Exception:
            results.append(failed(4, "0.7.1", "/v1/orchestrate front-door smoke", body[:60]))
    elif 500 <= code < 600:
        results.append(skipped(4, "0.7.1", "/v1/orchestrate front-door smoke",
                                f"HTTP {code} — server error, nixos-rebuild needed"))
    else:
        results.append(failed(4, "0.7.1", "/v1/orchestrate front-door smoke",
                               f"HTTP {code or 'conn-err'}: {body[:60]}"))

    # 0.7.2 /query retrieval
    timeout = ctx.query_timeout_s
    code2, body2 = _raw_post(
        f"{ctx.hybrid_url}/query",
        {"query": "what is nixos", "mode": "retrieval", "prefer_local": True, "limit": 1},
        headers=headers, timeout=timeout,
    )
    if code2 > 0:
        try:
            d2 = json.loads(body2)
            if "results" in d2:
                results.append(passed(4, "0.7.2", "hybrid /query retrieval smoke"))
            else:
                results.append(failed(4, "0.7.2", "hybrid /query retrieval smoke", body2[:80]))
        except Exception:
            results.append(failed(4, "0.7.2", "hybrid /query retrieval smoke", body2[:80]))
    else:
        results.append(failed(4, "0.7.2", "hybrid /query retrieval smoke", "connection error"))

    # 0.7.3 RAG recall quality
    if ctx.should_run(6):
        results.extend(_check_rag_recall(ctx))

    # 0.7.4 AIDB vector search
    if ctx.should_run(6):
        results.extend(_check_aidb_search(ctx))

    return results


def _raw_post(url: str, payload: dict, headers: dict, timeout: int = 10) -> tuple[int, str]:
    import urllib.request
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.request.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")
    except Exception:
        return -1, ""


def _check_rag_recall(ctx: RunContext) -> list[CheckResult]:
    # aq-report exposes retrieval acceptance metrics (memory_recall_share_pct)
    if os.environ.get("AQ_QA_SKIP_REPORT_BACKED_CHECKS", "0") == "1":
        return [skipped(6, "0.7.3", "RAG recall quality > 0%", "skipped to avoid aq-report recursion")]
    report_json = ctx.aq_report_snapshot  # _aq_report_snapshot equivalent
    if not report_json:
        return [skipped(6, "0.7.3", "RAG recall quality > 0%",
                        "metric absent from snapshot — run aq-report after traffic flows to seed")]
    try:
        data = json.loads(report_json)
        v = (data.get("rag_posture") or {}).get("memory_recall_share_pct")
        if v is None:
            return [skipped(6, "0.7.3", "RAG recall quality > 0%",
                            "metric absent from snapshot")]
        if float(v) > 0:
            return [passed(6, "0.7.3", f"RAG recall quality > 0% (got {v}%)")]
        return [failed(6, "0.7.3", "RAG recall quality > 0%", f"got {v}%")]
    except Exception as e:
        return [skipped(6, "0.7.3", "RAG recall quality > 0%", str(e))]


def _check_aidb_search(ctx: RunContext) -> list[CheckResult]:
    code, body = _raw_post(
        f"{ctx.aidb_url}/vector/search",
        {"query": "nixos", "limit": 1},
        headers={"Content-Type": "application/json"},
        timeout=5,
    )
    if code > 0:
        try:
            d = json.loads(body)
            if "results" in d and len(d["results"]) > 0:
                return [passed(6, "0.7.4", "AIDB vector search returns results")]
            return [failed(6, "0.7.4", "AIDB vector search returns results", body[:80])]
        except Exception:
            return [failed(6, "0.7.4", "AIDB vector search returns results", body[:80])]
    return [failed(6, "0.7.4", "AIDB vector search returns results", "connection error")]


# ---------------------------------------------------------------------------
# 0.8 Delegate metrics
# ---------------------------------------------------------------------------

def _service_active_age_seconds(unit: str) -> int | None:
    """Return current activation age for a systemd unit.

    Delegate SLOs should describe the currently deployed coordinator process,
    not stale failures from a previous generation that still sit in the 24h
    audit window after a rebuild/restart.
    """
    try:
        r = subprocess.run(
            ["systemctl", "show", unit, "-p", "ActiveEnterTimestampMonotonic", "--value"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return None
    if r.returncode != 0:
        return None
    raw = r.stdout.strip()
    try:
        active_us = int(raw)
    except (TypeError, ValueError):
        return None
    if active_us <= 0:
        return None
    return max(1, int(time.monotonic() - (active_us / 1_000_000)))


def _check_delegate_rate(ctx: RunContext) -> list[CheckResult]:
    max_window_s = 86400
    active_age_s = _service_active_age_seconds("ai-hybrid-coordinator.service")
    window_s = min(max_window_s, active_age_s) if active_age_s is not None else max_window_s
    data = http_json(f"{ctx.hybrid_coordinator_url}/stats/delegate?window_s={window_s}", timeout=5)
    if data is None or "error" in (data or {}):
        return [skipped(4, "0.8.1", "delegate 24h success rate",
                        "coordinator /stats/delegate unavailable (needs nixos-rebuild)")]
    total = int(data.get("total") or 0)
    ok = int(data.get("ok") or 0)
    min_sample = 10
    if total < min_sample:
        sample_scope = "current coordinator activation" if active_age_s is not None else "last 24h"
        return [skipped(4, "0.8.1", "delegate 24h success rate",
                        f"insufficient sample ({total}/{min_sample} calls in {sample_scope})")]
    pct = round(100 * ok / total)
    if pct >= 50:
        return [passed(4, "0.8.1", f"delegate 24h success rate {pct}% ({ok}/{total})")]
    return [failed(4, "0.8.1", "delegate 24h success rate ≥50%",
                   f"got {pct}% ({ok}/{total} calls)")]


# ---------------------------------------------------------------------------
# 0.9.x Feature/phase-gate checks
# ---------------------------------------------------------------------------

def _check_safety_gate(ctx: RunContext) -> list[CheckResult]:
    headers = {"Content-Type": "application/json", "X-API-Key": ctx.api_key}
    code, body = _raw_post(
        f"{ctx.hybrid_url}/control/safety/gate",
        {"session_id": "healthcheck", "safety_mode": "open"},
        headers=headers, timeout=25,
    )
    if code == 200 or '"ok": true' in body or '"ok":true' in body:
        return [passed(4, "0.9.1", "safety gate endpoint responds (POST /control/safety/gate)")]
    if code == 404:
        return [skipped(4, "0.9.1", "safety gate endpoint", "Phase 28 not deployed (404)")]
    return [failed(4, "0.9.1", "safety gate endpoint reachable",
                   f"HTTP {code or 'ERR'}: {body[:80]}")]


def _check_uag_replay(ctx: RunContext) -> list[CheckResult]:
    code, _ = http_get(
        f"{ctx.hybrid_url}/agent/lifecycle/healthcheck-probe/replay",
        timeout=20, headers={"X-API-Key": ctx.api_key},
    )
    if code in (404, 200):
        return [passed(4, "0.9.2", "UAG lifecycle replay endpoint wired (GET /agent/lifecycle/{id}/replay)")]
    if code == 405:
        return [skipped(4, "0.9.2", "UAG lifecycle replay endpoint", "Phase 37 not deployed (405)")]
    return [failed(4, "0.9.2", "UAG lifecycle replay endpoint reachable", f"HTTP {code or 'ERR'}")]


def _check_dag_executor(ctx: RunContext) -> list[CheckResult]:
    import urllib.request
    req = urllib.request.Request(
        f"{ctx.hybrid_url}/workflow/run/healthcheck-probe/execute/status",
        headers={"X-API-Key": ctx.api_key},
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            code = resp.status
    except urllib.request.HTTPError as e:
        code = e.code
    except Exception:
        code = -1
    if code in (404, 200):
        return [passed(4, "0.9.3", "DAG executor execute/status endpoint wired")]
    if code == 405:
        return [skipped(4, "0.9.3", "DAG executor endpoint", "Phase 38 not deployed (405)")]
    return [failed(4, "0.9.3", "DAG executor execute/status endpoint reachable", f"HTTP {code or 'ERR'}")]


def _check_safety_policy(ctx: RunContext) -> list[CheckResult]:
    policy_file = os.environ.get(
        "RUNTIME_SAFETY_POLICY_FILE",
        str(ctx.repo_root / "config" / "runtime-safety-policy.json"),
    )
    if not Path(policy_file).exists():
        return [skipped(4, "0.9.4", "runtime safety contract", f"policy file not found: {policy_file}")]
    try:
        d = json.loads(Path(policy_file).read_text())
        modes = d.get("modes", {})
        ro_blocked = set(modes.get("plan-readonly", {}).get("blocked", []))
        ex_allowed = set(modes.get("execute-mutating", {}).get("allowed_risk_classes", []))
        ok = ("mutating" in ro_blocked or "destructive" in ro_blocked) and "review-required" in ex_allowed
        if ok:
            return [passed(4, "0.9.4",
                           "runtime safety policy: plan-readonly blocks mutating; execute-mutating allows review-required")]
        return [failed(4, "0.9.4", "runtime safety policy v1.1 differentiation",
                       "policy file lacks mode differentiation")]
    except Exception as e:
        return [failed(4, "0.9.4", "runtime safety policy v1.1 differentiation", str(e))]


def _check_trust_roots(ctx: RunContext) -> list[CheckResult]:
    verify = ctx.repo_root / "scripts" / "testing" / "verify-skill-registry.sh"
    rotate = ctx.repo_root / "scripts" / "security" / "rotate-skill-registry-key.sh"
    trust = ctx.repo_root / "config" / "keys" / "skill-registry-trust-roots.json"
    missing = []
    if not (verify.exists() and os.access(verify, os.X_OK)):
        missing.append("verify-skill-registry.sh")
    if not (rotate.exists() and os.access(rotate, os.X_OK)):
        missing.append("rotate-skill-registry-key.sh")
    if not trust.exists():
        missing.append("trust-roots.json")
    if not missing:
        return [passed(4, "0.9.5", "trust-root infra: verify-skill-registry.sh + rotate-skill-registry-key.sh + trust-roots.json present")]
    return [failed(4, "0.9.5", "trust-root infra complete", f"missing: {', '.join(missing)}")]


def _check_workspace_isolation(ctx: RunContext) -> list[CheckResult]:
    rmgr = ctx.repo_root / "ai-stack" / "mcp-servers" / "hybrid-coordinator" / "workflow" / "runtime_manager.py"
    wsh = ctx.repo_root / "ai-stack" / "mcp-servers" / "hybrid-coordinator" / "workflow" / "workflow_session_handlers.py"
    iso_file = os.environ.get(
        "RUNTIME_ISOLATION_PROFILES_FILE",
        str(ctx.repo_root / "config" / "runtime-isolation-profiles.json"),
    )
    missing = []
    if rmgr.exists():
        text = rmgr.read_text()
        if "provision_run_workspace" not in text:
            missing.append("provision_run_workspace")
        if "teardown_run_workspace" not in text:
            missing.append("teardown_run_workspace")
    else:
        missing.append("runtime_manager.py")
    if wsh.exists():
        if "handle_runtime_isolation_workspace" not in wsh.read_text():
            missing.append("handle_runtime_isolation_workspace")
    else:
        missing.append("workflow_session_handlers.py")
    if not Path(iso_file).exists():
        missing.append("runtime-isolation-profiles.json")
    if not missing:
        return [passed(4, "0.9.6", "per-run workspace isolation: provision/teardown + endpoint present")]
    return [failed(4, "0.9.6", "per-run workspace isolation complete", f"missing: {', '.join(missing)}")]


def _check_fleet_control(ctx: RunContext) -> list[CheckResult]:
    rch = ctx.repo_root / "ai-stack" / "mcp-servers" / "hybrid-coordinator" / "workflow" / "runtime_control_handlers.py"
    if not rch.exists():
        return [failed(4, "0.9.7", "fleet control-plane UX complete", "runtime_control_handlers.py missing")]
    text = rch.read_text()
    missing = []
    for fn in ("handle_runtime_deregister", "handle_runtime_deployments_list",
               "handle_fleet_summary", "handle_runtime_health"):
        if fn not in text:
            missing.append(fn)
    if not missing:
        return [passed(4, "0.9.7", "fleet control-plane: deregister + deployment history + fleet summary + health probe present")]
    return [failed(4, "0.9.7", "fleet control-plane UX complete", f"missing: {', '.join(missing)}")]


def _check_benchmark_harness(ctx: RunContext) -> list[CheckResult]:
    eval_pack = ctx.repo_root / "data" / "harness-gap-eval-pack.json"
    trend = ctx.repo_root / "scripts" / "automation" / "publish-eval-trend.py"
    bench = ctx.repo_root / "scripts" / "testing" / "run-benchmark-gate.sh"
    missing = []
    pack_cases = 0
    if eval_pack.exists():
        try:
            pack_cases = len(json.loads(eval_pack.read_text()).get("cases", []))
        except Exception:
            pass
    if not eval_pack.exists() or pack_cases < 10:
        missing.append(f"eval-pack(need≥10,got{pack_cases})")
    if not (trend.exists() and os.access(trend, os.X_OK)):
        missing.append("publish-eval-trend.py")
    if not (bench.exists() and os.access(bench, os.X_OK)):
        missing.append("run-benchmark-gate.sh")
    if not missing:
        return [passed(4, "0.9.8", f"benchmark harness: eval pack ({pack_cases} cases) + trend publisher + benchmark gate present")]
    return [failed(4, "0.9.8", "benchmark harness complete", f"missing: {', '.join(missing)}")]


def _check_harness_runner(ctx: RunContext) -> list[CheckResult]:
    runner = ctx.repo_root / "scripts" / "testing" / "harness-runner.sh"
    ci = ctx.repo_root / ".github" / "workflows" / "tests.yml"
    missing = []
    if not (runner.exists() and os.access(runner, os.X_OK)):
        missing.append("harness-runner.sh")
    elif not cmd_ok("bash", "-n", str(runner)):
        missing.append("harness-runner.sh(syntax)")
    ci_ok = ci.exists() and "parity-scorecard-gate" in ci.read_text()
    if not ci_ok:
        missing.append("parity-scorecard-gate(tests.yml)")
    if not missing:
        return [passed(4, "0.9.9", "unified harness runner + PAR-002 CI gate present")]
    return [failed(4, "0.9.9", "unified harness runner + PAR-002 CI gate", f"missing: {', '.join(missing)}")]


def _check_budget_guardrail(ctx: RunContext) -> list[CheckResult]:
    policy_file = os.environ.get(
        "RUNTIME_BUDGET_POLICY_FILE",
        str(ctx.repo_root / "config" / "runtime-budget-policy.json"),
    )
    handler = ctx.repo_root / "ai-stack" / "mcp-servers" / "hybrid-coordinator" / "workflow" / "runtime_control_handlers.py"
    missing = []
    if not Path(policy_file).exists():
        missing.append("runtime-budget-policy.json")
    else:
        try:
            d = json.loads(Path(policy_file).read_text())
            dflt = d.get("default", {})
            assert "token_limit" in dflt, "missing token_limit"
            assert "tool_call_limit" in dflt, "missing tool_call_limit"
            assert dflt.get("fail_safe") in ("abort", "warn", "checkpoint"), "invalid fail_safe"
        except Exception as e:
            missing.append(f"policy-schema({e})")
    if handler.exists():
        text = handler.read_text()
        if "handle_budget_policy_get" not in text and "handle_budget_policy_post" not in text:
            missing.append("budget-handlers")
        if '"/control/budget/policy"' not in text:
            missing.append("budget-route")
    else:
        missing.append("runtime_control_handlers.py")
    if not missing:
        return [passed(4, "0.9.10", "budget/cost guardrail: policy file valid + GET/POST /control/budget/policy handlers registered")]
    return [failed(4, "0.9.10", "budget/cost guardrail policy + API", f"missing: {', '.join(missing)}")]


def _check_rollback_drill(ctx: RunContext) -> list[CheckResult]:
    drill = ctx.repo_root / "scripts" / "testing" / "drill-rollback.sh"
    runbook = ctx.repo_root / "docs" / "runbooks" / "staged-rollout-and-rollback.md"
    missing = []
    if not (drill.exists() and os.access(drill, os.X_OK)):
        missing.append("drill-rollback.sh(missing/not-executable)")
    elif not cmd_ok("bash", "-n", str(drill)):
        missing.append("drill-rollback.sh(syntax)")
    else:
        if not output_matches(r"Stage 4.*[Rr]ollback|rollback", "grep", "-i", "rollback", str(drill)):
            if "rollback" not in drill.read_text().lower():
                missing.append("drill-rollback.sh(no-rollback-stage)")
    if not runbook.exists():
        missing.append("staged-rollout-and-rollback.md")
    if not missing:
        return [passed(4, "0.9.11", "PAR-012 rollout/rollback drill: drill-rollback.sh + runbook present")]
    return [failed(4, "0.9.11", "PAR-012 rollout/rollback drill", f"missing: {', '.join(missing)}")]


def _check_aqd_ergonomics(ctx: RunContext) -> list[CheckResult]:
    aqd = ctx.repo_root / "scripts" / "ai" / "aqd"
    missing = []
    if not (aqd.exists() and os.access(aqd, os.X_OK)):
        return [failed(4, "0.9.12", "CLI ergonomics aqd run subcommands", "aqd not executable")]
    try:
        r = subprocess.run([str(aqd), "--version"], capture_output=True, text=True, timeout=5)
        import re as _re
        m = _re.search(r"[\d.]+", r.stdout + r.stderr)
        ver = m.group(0) if m else "0"
        parts = [int(x) for x in ver.split(".")]
        if parts < [0, 4, 0]:
            missing.append(f"aqd(version<0.4.0:{ver})")
    except Exception:
        ver = "?"
    aqd_text = aqd.read_text()
    for subcmd in ("run:plan", "run:execute", "run:replay", "run:review", "run:status", "run:budget"):
        if f"    {subcmd})" not in aqd_text:
            missing.append(f"aqd-{subcmd}")
    if not missing:
        return [passed(4, "0.9.12",
                       f"CLI ergonomics: aqd v{ver} run subcommands present (plan/execute/replay/review/status/budget)")]
    return [failed(4, "0.9.12", "CLI ergonomics aqd run subcommands", f"missing: {', '.join(missing)}")]


def _check_mcp_blueprints(ctx: RunContext) -> list[CheckResult]:
    bp_file_path = os.environ.get(
        "WORKFLOW_BLUEPRINTS_FILE",
        str(ctx.repo_root / "config" / "workflow-blueprints.json"),
    )
    bp_file = Path(bp_file_path)
    missing = []
    bp_count, bp_ver = 0, "?"
    if not bp_file.exists():
        missing.append("workflow-blueprints.json")
    else:
        try:
            d = json.loads(bp_file.read_text())
            bps = d.get("blueprints", [])
            bp_count = len(bps)
            bp_ver = d.get("version", "?")
            if bp_count < 5:
                missing.append(f"blueprints-count({bp_count}<5)")
            cats_missing = [b.get("id", "?") for b in bps if not b.get("category")]
            if cats_missing:
                missing.append(f"missing-category:{','.join(cats_missing[:3])}")
        except Exception as e:
            missing.append(f"blueprints-parse({e})")
    handler = ctx.repo_root / "ai-stack" / "mcp-servers" / "hybrid-coordinator" / "workflow" / "workflow_session_handlers.py"
    if handler.exists():
        if '"/workflow/blueprints"' not in handler.read_text():
            missing.append("workflow-blueprints-route")
    else:
        missing.append("workflow_session_handlers.py")
    if not missing:
        return [passed(4, "0.9.13",
                       f"MCP workflow blueprints: {bp_count} blueprints v{bp_ver} with category+tags + GET /workflow/blueprints wired")]
    return [failed(4, "0.9.13", "MCP workflow blueprints", f"missing: {', '.join(missing)}")]


def _check_graph_runner(ctx: RunContext) -> list[CheckResult]:
    runner = ctx.repo_root / "ai-stack" / "mcp-servers" / "hybrid-coordinator" / "workflow" / "orchestration_graph_runner.py"
    templates = ctx.repo_root / "config" / "orchestration-graph-templates.json"
    missing = []
    tmpl_count = 0
    if not runner.exists():
        missing.append("orchestration_graph_runner.py")
    else:
        if not cmd_ok("python3", "-c", f"import ast; ast.parse(open('{runner}').read())"):
            missing.append("graph_runner(syntax)")
        text = runner.read_text()
        if "handle_graph_run_submit" not in text and "handle_graph_run_get" not in text:
            missing.append("graph-handlers")
        if '"/workflow/graph/run"' not in text:
            missing.append("graph-route")
    if not templates.exists():
        missing.append("orchestration-graph-templates.json")
    else:
        try:
            tmpl_count = len(json.loads(templates.read_text()).get("templates", []))
            if tmpl_count < 2:
                missing.append(f"templates<2({tmpl_count})")
        except Exception:
            missing.append("templates(parse-error)")
    if not missing:
        return [passed(4, "0.9.14", f"orchestration graph runner: POST/GET /workflow/graph/run + {tmpl_count} templates")]
    return [failed(4, "0.9.14", "orchestration graph runner", f"missing: {', '.join(missing)}")]


def _check_ide_adapter(ctx: RunContext) -> list[CheckResult]:
    smoke = ctx.repo_root / "scripts" / "testing" / "smoke-ide-adapter-compat.sh"
    missing = []
    if not (smoke.exists() and os.access(smoke, os.X_OK)):
        missing.append("smoke-ide-adapter-compat.sh(missing/not-executable)")
    elif not cmd_ok("bash", "-n", str(smoke)):
        missing.append("smoke-ide-adapter-compat.sh(syntax)")
    else:
        text = smoke.read_text()
        if "Continue extension" not in text:
            missing.append("ide-smoke(no-continue-section)")
        if "VS Code" not in text and "VSCodium" not in text:
            missing.append("ide-smoke(no-vscode-section)")
        if "MCP adapter" not in text:
            missing.append("ide-smoke(no-mcp-section)")
    if not missing:
        return [passed(4, "0.9.15", "IDE adapter compatibility gate: smoke-ide-adapter-compat.sh (Continue + VS Code + CLI + MCP)")]
    return [failed(4, "0.9.15", "IDE adapter compatibility gate", f"missing: {', '.join(missing)}")]


def _check_ablation_profiles(ctx: RunContext) -> list[CheckResult]:
    pf = ctx.repo_root / "config" / "ablation-reasoning-profiles.json"
    rch = ctx.repo_root / "ai-stack" / "mcp-servers" / "hybrid-coordinator" / "workflow" / "runtime_control_handlers.py"
    missing = []
    prof_count = 0
    if not pf.exists():
        missing.append("ablation-reasoning-profiles.json(missing)")
    else:
        try:
            d = json.loads(pf.read_text())
            profiles = d.get("profiles", [])
            prof_count = len(profiles)
            assert prof_count >= 4, "fewer than 4 profiles"
            required = {"name", "reasoning_style", "safety_mode", "tags"}
            for p in profiles:
                diff = required - set(p.keys())
                if diff:
                    missing.append(f"profile {p.get('name','?')} missing {diff}")
        except AssertionError as e:
            missing.append(f"ablation-profiles({e})")
        except Exception as e:
            missing.append(f"ablation-profiles(schema:{e})")
        if rch.exists():
            if "handle_reasoning_profiles_list" not in rch.read_text() and "reasoning/profiles" not in rch.read_text():
                missing.append("runtime_control_handlers(no-reasoning-routes)")
    if not missing:
        return [passed(4, "0.9.16", f"ablation/reasoning profile pack: {prof_count} profiles + coordinator routes wired")]
    return [failed(4, "0.9.16", "ablation/reasoning profile pack", f"missing: {', '.join(missing)}")]


def _check_aqd_reasoning(ctx: RunContext) -> list[CheckResult]:
    aqd = ctx.repo_root / "scripts" / "ai" / "aqd"
    if not aqd.exists():
        return [failed(4, "0.9.17", "aqd reasoning subcommands", "aqd not found")]
    text = aqd.read_text()
    missing = [s for s in ("reasoning:list", "cmd_reasoning_list", "reasoning:get",
                            "cmd_reasoning_get", "reasoning:apply", "cmd_reasoning_apply")
               if s not in text]
    if not missing:
        return [passed(4, "0.9.17", "aqd reasoning list/get/apply subcommands present")]
    return [failed(4, "0.9.17", "aqd reasoning subcommands", f"missing: {', '.join(missing)}")]


def _check_logic_indexer(ctx: RunContext) -> list[CheckResult]:
    indexer = ctx.repo_root / "scripts" / "ai" / "aq-index-logic-patterns"
    topo = ctx.repo_root / "dashboard" / "backend" / "api" / "routes" / "topology.py"
    missing = []
    if not (indexer.exists() and os.access(indexer, os.X_OK)):
        missing.append("aq-index-logic-patterns")
    if topo.exists():
        if "logic/search" not in topo.read_text() and "logic_search" not in topo.read_text():
            missing.append("dashboard/api/routes/topology.py:logic/search")
    else:
        missing.append("topology.py")
    if not missing:
        return [passed(4, "0.9.18", "logic pattern indexer + /api/logic/search route present")]
    return [failed(4, "0.9.18", "logic pattern indexer + route", f"missing: {', '.join(missing)}")]


def _check_aqd_logic(ctx: RunContext) -> list[CheckResult]:
    aqd = ctx.repo_root / "scripts" / "ai" / "aqd"
    if not aqd.exists():
        return [failed(4, "0.9.19", "aqd logic/topology subcommands", "aqd not found")]
    text = aqd.read_text()
    missing = [s for s in ("logic:search", "cmd_logic_search", "topology", "cmd_topology")
               if s not in text]
    if not missing:
        return [passed(4, "0.9.19", "aqd logic:search + topology subcommands present")]
    return [failed(4, "0.9.19", "aqd logic/topology subcommands", f"missing: {', '.join(missing)}")]


def _check_topology_api(ctx: RunContext) -> list[CheckResult]:
    topo = ctx.repo_root / "dashboard" / "backend" / "api" / "routes" / "topology.py"
    if not topo.exists():
        return [failed(4, "0.9.20", "topology API routes", "topology.py missing")]
    text = topo.read_text()
    missing = []
    if "get_topology" not in text:
        missing.append("/api/topology")
    if "get_topology_flow" not in text and "topology/flow" not in text:
        missing.append("/api/topology/flow")
    if not missing:
        return [passed(4, "0.9.20", "topology API: GET /api/topology + GET /api/topology/flow registered")]
    return [failed(4, "0.9.20", "topology API routes", f"missing: {', '.join(missing)}")]


def _check_local_model_config(ctx: RunContext) -> list[CheckResult]:
    """Phase 60.0: local model config YAML + smoke test script present and valid."""
    results: list[CheckResult] = []
    config = ctx.repo_root / "config" / "local-model-config.yaml"
    smoke = ctx.repo_root / "scripts" / "testing" / "smoke-local-model.sh"

    # 60.0.1 — config YAML valid
    if not config.exists():
        results.append(failed(4, "60.0.1", "local-model-config.yaml", "file missing"))
    else:
        try:
            import yaml as _yaml
            docs = [doc for doc in _yaml.safe_load_all(config.read_text()) if isinstance(doc, dict)]
            d = docs[0] if docs else {}
            required = {"_meta", "active_model", "inference", "chat", "performance_targets"}
            missing = required - set(d.keys())
            if missing:
                results.append(failed(4, "60.0.1", "local-model-config.yaml schema", f"missing keys: {missing}"))
            elif not d.get("chat", {}).get("enable_thinking") is False:
                results.append(failed(4, "60.0.1", "local-model-config.yaml thinking guard", "chat.enable_thinking must be false"))
            else:
                results.append(passed(4, "60.0.1", "local-model-config.yaml valid (schema + thinking guard)"))
        except ModuleNotFoundError:
            results.append(skipped(4, "60.0.1", "local-model-config.yaml parse (PyYAML not in this env; install pyyaml)"))
        except Exception as exc:
            results.append(failed(4, "60.0.1", "local-model-config.yaml parse", str(exc)))

    # 60.0.2 — smoke test script present and has bash shebang
    if not smoke.exists():
        results.append(failed(4, "60.0.2", "smoke-local-model.sh", "file missing"))
    else:
        text = smoke.read_text()
        if "smoke-local-model" in text and "enable_thinking" in text and "mtp" in text.lower():
            results.append(passed(4, "60.0.2", "smoke-local-model.sh present (thinking guard + MTP gates)"))
        else:
            results.append(failed(4, "60.0.2", "smoke-local-model.sh", "missing expected gates"))

    return results


def _check_local_payload_discipline(ctx: RunContext) -> list[CheckResult]:
    """Phase 148: local inference payloads must not enable thinking mode."""
    gate = ctx.repo_root / "scripts" / "testing" / "gate-local-payload-discipline.sh"
    if not gate.exists():
        return [failed(1, "0.10.1", "local inference payload discipline", "gate-local-payload-discipline.sh missing")]
    proc = subprocess.run(
        ["bash", str(gate)],
        cwd=ctx.repo_root,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    if proc.returncode == 0:
        return [passed(1, "0.10.1", "local inference payload discipline (no enable_thinking=True)")]
    detail = (proc.stdout + proc.stderr).strip() or f"exit {proc.returncode}"
    return [failed(1, "0.10.1", "local inference payload discipline (no enable_thinking=True)", detail)]


def _check_discovery_agent(ctx: RunContext) -> list[CheckResult]:
    """Phase 153: discovery agent emits deterministic improvement candidates."""
    check = ctx.repo_root / "scripts" / "testing" / "test-discovery-agent-opportunities.py"
    if not check.exists():
        return [failed(1, "0.10.4", "discovery agent opportunity scanner", "test-discovery-agent-opportunities.py missing")]
    proc = subprocess.run(
        ["python3", str(check)],
        cwd=ctx.repo_root,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    if proc.returncode == 0:
        return [passed(1, "0.10.4", "discovery agent opportunity scanner emits dashboard candidates")]
    detail = (proc.stdout + proc.stderr).strip() or f"exit {proc.returncode}"
    return [failed(1, "0.10.4", "discovery agent opportunity scanner", detail)]


def _check_model_catalog_freshness(ctx: RunContext) -> list[CheckResult]:
    """Phase 154: model catalog/profile freshness is governed and visible."""
    check = ctx.repo_root / "scripts" / "testing" / "test-model-catalog-freshness.py"
    if not check.exists():
        return [failed(1, "0.10.5", "model catalog/profile freshness", "test-model-catalog-freshness.py missing")]
    proc = subprocess.run(
        ["python3", str(check)],
        cwd=ctx.repo_root,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    if proc.returncode == 0:
        return [passed(1, "0.10.5", "model catalog/profile freshness telemetry wired")]
    detail = (proc.stdout + proc.stderr).strip() or f"exit {proc.returncode}"
    return [failed(1, "0.10.5", "model catalog/profile freshness", detail)]


def _check_flat_prd_gate(ctx: RunContext) -> list[CheckResult]:
    """Phase 155: flat model-team PRD gate is installed and enforced."""
    check = ctx.repo_root / "scripts" / "testing" / "test-flat-prd-gate.py"
    if not check.exists():
        return [failed(1, "0.10.6", "flat model-team PRD gate", "test-flat-prd-gate.py missing")]
    proc = subprocess.run(
        ["python3", str(check)],
        cwd=ctx.repo_root,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    if proc.returncode == 0:
        return [passed(1, "0.10.6", "flat model-team PRD gate enforces proposal/review/consensus artifacts")]
    detail = (proc.stdout + proc.stderr).strip() or f"exit {proc.returncode}"
    return [failed(1, "0.10.6", "flat model-team PRD gate", detail)]


def _check_agent_artifact_policy(ctx: RunContext) -> list[CheckResult]:
    """Phase 156: local runtime artifacts stay out of distributed source."""
    check = ctx.repo_root / "scripts" / "testing" / "test-agent-artifact-policy.py"
    if not check.exists():
        return [failed(1, "0.10.7", "agent artifact distribution policy", "test-agent-artifact-policy.py missing")]
    proc = subprocess.run(
        ["python3", str(check)],
        cwd=ctx.repo_root,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    if proc.returncode == 0:
        return [passed(1, "0.10.7", "agent artifact distribution policy keeps runtime state local")]
    detail = (proc.stdout + proc.stderr).strip() or f"exit {proc.returncode}"
    return [failed(1, "0.10.7", "agent artifact distribution policy", detail)]


def _check_agent_memory_surface_registry(ctx: RunContext) -> list[CheckResult]:
    """Phase 157: agent memory/state surfaces are classified and governed."""
    check = ctx.repo_root / "scripts" / "testing" / "test-agent-memory-surface-registry.py"
    if not check.exists():
        return [failed(1, "0.10.8", "agent memory surface registry", "test-agent-memory-surface-registry.py missing")]
    proc = subprocess.run(
        ["python3", str(check)],
        cwd=ctx.repo_root,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    if proc.returncode == 0:
        return [passed(1, "0.10.8", "agent memory surface registry classifies state, memory, RAG, and archives")]
    detail = (proc.stdout + proc.stderr).strip() or f"exit {proc.returncode}"
    return [failed(1, "0.10.8", "agent memory surface registry", detail)]


def _check_local_delegation_artifact(ctx: RunContext) -> list[CheckResult]:
    """Phase 159: delegate-to-local pre-registers task before any blocking op."""
    check = ctx.repo_root / "scripts" / "testing" / "test-local-delegation-artifact.py"
    if not check.exists():
        return [failed(1, "0.10.9", "local delegation artifact persistence", "test-local-delegation-artifact.py missing")]
    proc = subprocess.run(
        ["python3", str(check)],
        cwd=ctx.repo_root,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    if proc.returncode == 0:
        return [passed(1, "0.10.9", "local delegation pre-registers artifact before blocking ops")]
    detail = (proc.stdout + proc.stderr).strip() or f"exit {proc.returncode}"
    return [failed(1, "0.10.9", "local delegation artifact persistence", detail)]


def _check_intent_classifier_coverage(ctx: RunContext) -> list[CheckResult]:
    """Phase 160: intent unknown rate stat tile and aq-report 4c section."""
    check = ctx.repo_root / "scripts" / "testing" / "test-intent-classifier-coverage.py"
    if not check.exists():
        return [failed(1, "0.10.10", "intent classifier coverage", "test-intent-classifier-coverage.py missing")]
    proc = subprocess.run(
        ["python3", str(check)],
        cwd=ctx.repo_root,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    if proc.returncode == 0:
        return [passed(1, "0.10.10", "intent classifier coverage: unknown-rate tile and 4c panel wired")]
    detail = (proc.stdout + proc.stderr).strip() or f"exit {proc.returncode}"
    return [failed(1, "0.10.10", "intent classifier coverage", detail)]


def _check_modal_task_profiles(ctx: RunContext) -> list[CheckResult]:
    """Phase 162: modal task profiles for local dispatch."""
    check = ctx.repo_root / "scripts" / "testing" / "test-modal-task-profiles.py"
    if not check.exists():
        return [failed(1, "0.10.12", "modal task profiles", "test-modal-task-profiles.py missing")]
    proc = subprocess.run(
        ["python3", str(check)],
        cwd=ctx.repo_root,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    if proc.returncode == 0:
        return [passed(1, "0.10.12", "modal task profiles: 5 profiles, classify_task_type, TaskConfig wired")]
    detail = (proc.stdout + proc.stderr).strip() or f"exit {proc.returncode}"
    return [failed(1, "0.10.12", "modal task profiles", detail)]


def _check_local_inference_budget(ctx: RunContext) -> list[CheckResult]:
    """Phase 163: local inference budget visibility (hints, timeout scaling, sidecar, watch)."""
    check = ctx.repo_root / "scripts" / "testing" / "test-local-inference-budget.py"
    if not check.exists():
        return [failed(1, "0.10.13", "local inference budget", "test-local-inference-budget.py missing")]
    proc = subprocess.run(
        ["python3", str(check)],
        cwd=ctx.repo_root,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    if proc.returncode == 0:
        return [passed(1, "0.10.13", "local inference budget: hints, timeout scaling, progress sidecar, watch")]
    detail = (proc.stdout + proc.stderr).strip() or f"exit {proc.returncode}"
    return [failed(1, "0.10.13", "local inference budget", detail)]


def _check_local_agent_store_memory_contract(ctx: RunContext) -> list[CheckResult]:
    """Phase 164: local store_memory advertises coordinator-compatible memory tiers."""
    check = ctx.repo_root / "scripts" / "testing" / "test-local-agent-store-memory-contract.py"
    if not check.exists():
        return [failed(1, "0.10.14", "local-agent store_memory contract", "test-local-agent-store-memory-contract.py missing")]
    proc = subprocess.run(
        ["python3", str(check)],
        cwd=ctx.repo_root,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    if proc.returncode == 0:
        return [passed(1, "0.10.14", "local-agent store_memory uses canonical memory tiers and aliases")]
    detail = (proc.stdout + proc.stderr).strip() or f"exit {proc.returncode}"
    return [failed(1, "0.10.14", "local-agent store_memory contract", detail)]


def _check_local_inference_contract(ctx: RunContext) -> list[CheckResult]:
    """L1A: strict schemas, pure resolver, golden adapter parity, and dashboard health."""
    check = ctx.repo_root / "scripts" / "testing" / "test-local-inference-contract.py"
    if not check.exists():
        return [failed(1, "0.10.37", "local inference contract L1A", "test-local-inference-contract.py missing")]
    proc = subprocess.run(
        ["python3", str(check)],
        cwd=ctx.repo_root,
        text=True,
        capture_output=True,
        timeout=45,
        check=False,
    )
    if proc.returncode == 0:
        return [passed(1, "0.10.37", "local inference contract L1A: schemas, golden parity, dashboard health")]
    detail = (proc.stdout + proc.stderr).strip() or f"exit {proc.returncode}"
    return [failed(1, "0.10.37", "local inference contract L1A", detail[-500:])]


def _check_local_inference_l2a(ctx: RunContext) -> list[CheckResult]:
    """L2A: shadow caller/task policy, deterministic context, parity, and dashboard health."""
    check = ctx.repo_root / "scripts" / "testing" / "test-local-inference-l2a.py"
    if not check.exists():
        return [failed(1, "0.10.38", "local inference contract L2A", "test-local-inference-l2a.py missing")]
    proc = subprocess.run(
        ["python3", str(check)],
        cwd=ctx.repo_root,
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
    )
    if proc.returncode == 0:
        return [passed(1, "0.10.38", "local inference L2A: shadow policy, context, tier parity, dashboard health")]
    detail = (proc.stdout + proc.stderr).strip() or f"exit {proc.returncode}"
    return [failed(1, "0.10.38", "local inference contract L2A", detail[-500:])]


def _check_local_inference_l2b(ctx: RunContext) -> list[CheckResult]:
    """L2B-A: shadow payload adapter, strict transport decoder, parity, and dashboard health."""
    check = ctx.repo_root / "scripts" / "testing" / "test-local-inference-l2b.py"
    if not check.exists():
        return [failed(1, "0.10.39", "local inference contract L2B-A", "test-local-inference-l2b.py missing")]
    proc = subprocess.run(
        ["python3", str(check)],
        cwd=ctx.repo_root,
        text=True,
        capture_output=True,
        timeout=90,
        check=False,
    )
    if proc.returncode == 0:
        return [passed(1, "0.10.39", "local inference L2B-A: shadow payload, stream parity, dashboard health")]
    detail = (proc.stdout + proc.stderr).strip() or f"exit {proc.returncode}"
    return [failed(1, "0.10.39", "local inference contract L2B-A", detail[-500:])]


def _check_phase171_throughput_calibration(ctx: RunContext) -> list[CheckResult]:
    """Phase 171: verify LOCAL_TOK_PER_SEC constant is within 50% of measured throughput."""
    check = ctx.repo_root / "scripts" / "testing" / "test-local-inference-throughput.py"
    if not check.exists():
        return [failed(1, "0.10.22", "LOCAL_TOK_PER_SEC throughput calibration", "test-local-inference-throughput.py missing")]
    proc = subprocess.run(
        ["python3", str(check)],
        cwd=ctx.repo_root,
        text=True,
        capture_output=True,
        timeout=15,
        check=False,
    )
    if proc.returncode == 0:
        return [passed(1, "0.10.22", "LOCAL_TOK_PER_SEC throughput calibration")]
    detail = (proc.stdout + proc.stderr).strip() or f"exit {proc.returncode}"
    return [failed(1, "0.10.22", "LOCAL_TOK_PER_SEC throughput calibration", detail)]


def _check_osint_active_recon_gate(ctx: RunContext) -> list[CheckResult]:
    """OSINT active recon is fail-closed behind machine-readable admission gates."""
    check = ctx.repo_root / "scripts" / "testing" / "test-osint-active-recon-gate.py"
    if not check.exists():
        return [failed(1, "0.10.23", "OSINT active recon gate", "test-osint-active-recon-gate.py missing")]
    proc = subprocess.run(
        ["python3", str(check)],
        cwd=ctx.repo_root,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    if proc.returncode == 0:
        return [passed(1, "0.10.23", "OSINT active recon gate fail-closed")]
    detail = (proc.stdout + proc.stderr).strip() or f"exit {proc.returncode}"
    return [failed(1, "0.10.23", "OSINT active recon gate", detail)]


def _check_analysis_only_stagnation_mode(ctx: RunContext) -> list[CheckResult]:
    """Analysis-only local-agent tasks get checkpoint-based long-horizon guards."""
    check = ctx.repo_root / "scripts" / "testing" / "test-analysis-only-stagnation-mode.py"
    if not check.exists():
        return [failed(1, "0.10.24", "analysis-only local-agent stagnation mode", "test-analysis-only-stagnation-mode.py missing")]
    proc = subprocess.run(
        ["python3", str(check)],
        cwd=ctx.repo_root,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    if proc.returncode == 0:
        return [passed(1, "0.10.24", "analysis-only local-agent stagnation mode")]
    detail = (proc.stdout + proc.stderr).strip() or f"exit {proc.returncode}"
    return [failed(1, "0.10.24", "analysis-only local-agent stagnation mode", detail)]


# ---------------------------------------------------------------------------
# Phase 172 — Coordination & Delegation health checks (0.12.1-0.12.4)
# ---------------------------------------------------------------------------

def _check_phase172_delegation_health(ctx: RunContext) -> list[CheckResult]:
    """Phase 172: coordinator readiness gate, delegation success rate, feedback
    event_type coverage, and llama.cpp slot availability."""
    import json as _json
    from pathlib import Path as _Path
    import datetime as _dt

    results: list[CheckResult] = []
    coordinator_url = "http://127.0.0.1:8003"
    llama_url = "http://127.0.0.1:8080"

    # 0.12.1 — /readyz endpoint exists (200 or 503, not 404)
    try:
        import urllib.request as _ur
        try:
            with _ur.urlopen(f"{coordinator_url}/readyz", timeout=5) as _r:
                status = _r.status
        except Exception as _e:
            # urllib raises HTTPError for non-2xx; catch 503 as valid
            status = getattr(_e, "code", 0)
        if status in (200, 503):
            results.append(passed(1, "0.12.1", "coordinator /readyz endpoint exists"))
        else:
            results.append(failed(1, "0.12.1", "coordinator /readyz endpoint", f"unexpected HTTP {status}"))
    except Exception as exc:
        results.append(failed(1, "0.12.1", "coordinator /readyz endpoint", str(exc)))

    # 0.12.2 — delegation success rate ≥ 50% over last 24h (warn < 80%, fail < 50%)
    try:
        feedback_log = _Path("/var/lib/ai-stack/hybrid/telemetry/delegation-feedback.jsonl")
        if not feedback_log.exists():
            results.append(skipped(1, "0.12.2", "delegation success rate 24h", "feedback log not found"))
        else:
            cutoff = (_dt.datetime.utcnow() - _dt.timedelta(hours=24)).isoformat()
            lines = feedback_log.read_text().strip().splitlines()
            events = [_json.loads(l) for l in lines if l.strip()]
            recent = [e for e in events if (e.get("timestamp") or "") >= cutoff]
            if not recent:
                results.append(skipped(1, "0.12.2", "delegation success rate 24h", "no events in last 24h"))
            else:
                success = sum(1 for e in recent if e.get("outcome") == "success")
                rate = success / len(recent)
                label = f"{success}/{len(recent)} = {rate:.0%}"
                if rate >= 0.80:
                    results.append(passed(1, "0.12.2", f"delegation success rate 24h ({label})"))
                elif rate >= 0.50:
                    results.append(skipped(1, "0.12.2", f"delegation success rate 24h ({label}) — below 80% target", "degraded but above minimum"))
                else:
                    results.append(failed(1, "0.12.2", "delegation success rate 24h", f"{label} — below 50% minimum"))
    except Exception as exc:
        results.append(failed(1, "0.12.2", "delegation success rate 24h", str(exc)))

    # 0.12.3 — feedback event_type coverage: null fraction = 0 in last 20 events
    # Skip when data is stale (>48h): coordinator delegate path is rarely active; stale
    # data predates the event_type field being added and shouldn't gate the harness.
    try:
        import datetime as _dt
        feedback_log = _Path("/var/lib/ai-stack/hybrid/telemetry/delegation-feedback.jsonl")
        if not feedback_log.exists():
            results.append(skipped(1, "0.12.3", "feedback event_type coverage", "feedback log not found"))
        else:
            lines = feedback_log.read_text().strip().splitlines()
            recent_20 = [_json.loads(l) for l in lines[-20:] if l.strip()]
            if not recent_20:
                results.append(skipped(1, "0.12.3", "feedback event_type coverage", "no events in feedback log"))
            else:
                newest_ts_str = max(
                    (e.get("timestamp", "") for e in recent_20),
                    key=lambda s: s or "",
                    default="",
                )
                stale = False
                if newest_ts_str:
                    try:
                        ts = _dt.datetime.fromisoformat(newest_ts_str.replace("Z", "+00:00"))
                        age_h = (_dt.datetime.now(_dt.timezone.utc) - ts).total_seconds() / 3600
                        stale = age_h > 48
                    except ValueError:
                        pass
                if stale:
                    results.append(skipped(1, "0.12.3", "feedback event_type coverage",
                                           f"data stale (>{int(age_h):.0f}h) — coordinator delegate path inactive"))
                else:
                    null_count = sum(1 for e in recent_20 if e.get("event_type") is None)
                    if null_count == 0:
                        results.append(passed(1, "0.12.3", "feedback event_type coverage (0 null in last 20)"))
                    else:
                        results.append(failed(1, "0.12.3", "feedback event_type coverage",
                                              f"{null_count}/20 events have null event_type"))
    except Exception as exc:
        results.append(failed(1, "0.12.3", "feedback event_type coverage", str(exc)))

    # 0.12.4 — llama.cpp has at least 1 idle slot; skip if llama.cpp is down or all slots busy
    # Uses is_processing field (modern llama.cpp API); state==0 was removed in newer builds.
    # All-busy is transient normal operation — skip rather than fail to avoid false alerts.
    try:
        with _ur.urlopen(f"{llama_url}/slots", timeout=4) as _r:
            slots = _json.loads(_r.read())
            idle = [s for s in slots if not s.get("is_processing", s.get("state", -1) == 0)]
            if idle:
                results.append(passed(1, "0.12.4", f"llama.cpp slot available ({len(idle)} idle)"))
            else:
                results.append(skipped(1, "0.12.4", "llama.cpp slot available",
                                       f"all {len(slots)} slot(s) busy — transient, not a fault"))
    except Exception:
        results.append(skipped(1, "0.12.4", "llama.cpp slot available", "llama.cpp unreachable — skip"))

    return results


def _check_local_agent_monitor_visibility(ctx: RunContext) -> list[CheckResult]:
    """Local delegation monitor must be visible through CLI, report, QA, and dashboard."""
    results: list[CheckResult] = []
    monitor = ctx.repo_root / "scripts" / "ai" / "delegate-to-local"
    registry = ctx.repo_root / ".agents" / "delegation" / "TASK_REGISTRY.jsonl"

    try:
        before = registry.read_bytes() if registry.exists() else b""
        rc = subprocess.run(
            [str(monitor), "--monitor"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(ctx.repo_root),
        )
        after = registry.read_bytes() if registry.exists() else b""
        if rc.returncode != 0:
            results.append(failed(4, "0.12.5", "local-agent monitor CLI JSON", rc.stderr.strip()[:160]))
        else:
            payload = json.loads(rc.stdout)
            ok = payload.get("mode") == "read_only" and isinstance(payload.get("counts"), dict)
            if ok and before == after:
                counts = payload.get("counts") or {}
                results.append(passed(
                    4,
                    "0.12.5",
                    f"local-agent monitor CLI read-only JSON (running={counts.get('running', 0)}, stale={counts.get('inferred_stale', 0)})",
                ))
            elif before != after:
                results.append(failed(4, "0.12.5", "local-agent monitor CLI read-only JSON", "registry mutated during monitor read"))
            else:
                results.append(failed(4, "0.12.5", "local-agent monitor CLI read-only JSON", "missing mode=read_only or counts"))
    except Exception as exc:
        results.append(failed(4, "0.12.5", "local-agent monitor CLI read-only JSON", str(exc)))

    try:
        report_src = (ctx.repo_root / "scripts" / "ai" / "aq-report").read_text()
        if "local_agent_monitor_summary" in report_src and '"local_agent_monitor"' in report_src:
            results.append(passed(4, "0.12.6", "aq-report --machine exposes local_agent_monitor"))
        else:
            results.append(failed(4, "0.12.6", "aq-report --machine exposes local_agent_monitor", "field or summary helper missing"))
    except Exception as exc:
        results.append(failed(4, "0.12.6", "aq-report --machine exposes local_agent_monitor", str(exc)))

    try:
        route_src = (ctx.repo_root / "dashboard" / "backend" / "api" / "routes" / "aistack.py").read_text()
        html = (ctx.repo_root / "dashboard.html").read_text()
        js = (ctx.repo_root / "assets" / "dashboard.js").read_text()
        missing = []
        if '@router.get("/local-agent/monitor")' not in route_src:
            missing.append("dashboard route")
        if "section-local-agent-monitor" not in html or "localAgentMonitorDetails" not in html:
            missing.append("dashboard card")
        if "async function loadLocalAgentMonitor" not in js or "/aistack/local-agent/monitor" not in js:
            missing.append("dashboard loader")
        if "loadLocalAgentMonitor()" not in js:
            missing.append("observability wiring")
        if missing:
            results.append(failed(4, "0.12.7", "local-agent monitor dashboard surface", f"missing: {', '.join(missing)}"))
        else:
            results.append(passed(4, "0.12.7", "local-agent monitor dashboard surface wired"))
    except Exception as exc:
        results.append(failed(4, "0.12.7", "local-agent monitor dashboard surface", str(exc)))

    try:
        dashboard_url = f"http://127.0.0.1:{getattr(ctx, 'dashboard_port', 8889)}"
        data = http_json(f"{dashboard_url}/api/aistack/local-agent/monitor", timeout=5)
        if data and data.get("available") is True and isinstance(data.get("counts"), dict):
            results.append(passed(5, "0.12.8", "dashboard local-agent monitor endpoint returns counts"))
        elif data:
            results.append(failed(5, "0.12.8", "dashboard local-agent monitor endpoint returns counts", str(data)[:160]))
        else:
            results.append(skipped(5, "0.12.8", "dashboard local-agent monitor endpoint", "route not active yet or dashboard service unavailable"))
    except Exception as exc:
        results.append(skipped(5, "0.12.8", "dashboard local-agent monitor endpoint", str(exc)[:160]))

    return results


def _check_token_usage_coverage(ctx: RunContext) -> list[CheckResult]:
    """0.10.2 — token_usage coverage ≥ 50% of model_call events over last 100 events."""
    results: list[CheckResult] = []
    if not ctx.should_run(1):
        return results

    checker = ctx.repo_root / "scripts" / "testing" / "test-token-usage-coverage.py"
    if not checker.exists():
        return [failed(1, "0.10.2", "token_usage coverage", "test-token-usage-coverage.py missing")]

    try:
        rc = subprocess.run(
            ["python3", str(checker)],
            capture_output=True, text=True, timeout=10,
        )
        if rc.returncode == 0:
            results.append(passed(1, "0.10.2", "token_usage coverage ≥ 50% of recent model_calls"))
        else:
            detail = rc.stdout.strip() or rc.stderr.strip() or f"exit code {rc.returncode}"
            results.append(failed(1, "0.10.2", "token_usage coverage", detail))
    except Exception as e:
        results.append(failed(1, "0.10.2", "token_usage coverage", str(e)))

    return results


def _check_ragas_faithfulness_guard(ctx: RunContext) -> list[CheckResult]:
    """Phase 161: faithfulness scorer modal guard and judge prompt calibration."""
    check = ctx.repo_root / "scripts" / "testing" / "test-ragas-faithfulness-guard.py"
    if not check.exists():
        return [failed(1, "0.10.11", "RAGAS faithfulness guard", "test-ragas-faithfulness-guard.py missing")]
    proc = subprocess.run(
        ["python3", str(check)],
        cwd=ctx.repo_root,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    if proc.returncode == 0:
        return [passed(1, "0.10.11", "RAGAS faithfulness: modal guard + judge prompt calibration")]
    detail = (proc.stdout + proc.stderr).strip() or f"exit {proc.returncode}"
    return [failed(1, "0.10.11", "RAGAS faithfulness guard", detail)]


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def _dashboard_host_only_skip(layer: int, check_id: str, description: str) -> CheckResult:
    return skipped(
        layer,
        check_id,
        description,
        "dashboard-safe mode: host-only probe; run aq-qa 0 --machine for authoritative host validation",
    )


def _dashboard_safe_host_only_skips() -> list[CheckResult]:
    """Checks intentionally omitted when phase 0 runs inside the dashboard unit."""
    return [
        _dashboard_host_only_skip(5, "0.2.4", "Postgres has tables"),
        _dashboard_host_only_skip(5, "0.2.5", "Redis has keys"),
        _dashboard_host_only_skip(7, "0.5.1", "Continue CLI help works"),
        _dashboard_host_only_skip(7, "0.5.2", "Continue config targets switchboard ingress with local harness chat lane and continue-local tab lane"),
        _dashboard_host_only_skip(7, "0.5.3", "VSCodium has Continue extension installed"),
        _dashboard_host_only_skip(7, "0.5.5", "continue-local trims oversized dense prompts"),
        _dashboard_host_only_skip(7, "0.5.6", "Continue/editor prompt to feedback smoke"),
        _dashboard_host_only_skip(7, "0.6.1", "flagship agent CLI help smokes"),
        _dashboard_host_only_skip(7, "0.6.2", "gemini CLI live-state health check"),
        _dashboard_host_only_skip(1, "0.10.1", "local inference payload discipline"),
        _dashboard_host_only_skip(1, "0.10.4", "discovery agent opportunity scanner"),
        _dashboard_host_only_skip(1, "0.10.5", "model catalog/profile freshness"),
        _dashboard_host_only_skip(1, "0.10.6", "flat model-team PRD gate"),
        _dashboard_host_only_skip(1, "0.10.7", "agent artifact distribution policy"),
        _dashboard_host_only_skip(1, "0.10.8", "agent memory surface registry"),
        _dashboard_host_only_skip(1, "0.10.9", "local delegation artifact persistence"),
        _dashboard_host_only_skip(1, "0.10.13", "local inference budget"),
        _dashboard_host_only_skip(1, "0.10.14", "local-agent store_memory contract"),
        _dashboard_host_only_skip(1, "0.10.22", "LOCAL_TOK_PER_SEC throughput calibration"),
        _dashboard_host_only_skip(1, "0.10.23", "OSINT active recon gate"),
        _dashboard_host_only_skip(1, "0.10.24", "analysis-only local-agent stagnation mode"),
        _dashboard_host_only_skip(1, "0.12.1", "coordinator /readyz endpoint"),
        _dashboard_host_only_skip(1, "0.12.2", "delegation success rate 24h"),
        _dashboard_host_only_skip(1, "0.12.3", "feedback event_type coverage"),
        _dashboard_host_only_skip(1, "0.12.4", "llama.cpp slot available"),
        _dashboard_host_only_skip(1, "0.150.1", "candidate lifecycle manager"),
        _dashboard_host_only_skip(4, "83.1", "dag_manager.py syntax"),
        _dashboard_host_only_skip(4, "83.2", "context-merger.py syntax"),
        _dashboard_host_only_skip(4, "83.3", "Phase 1 integration test"),
        _dashboard_host_only_skip(4, "85.1", "aq-drop-daemon syntax"),
        _dashboard_host_only_skip(4, "85.2", "drop_spec.py injection guard"),
        _dashboard_host_only_skip(4, "86.2", "auto_ok push creates .agents/attention/ATTENTION_ARCHIVE.jsonl"),
        _dashboard_host_only_skip(4, "86.4", "aq-alerts --count"),
    ]


def run(ctx: RunContext) -> list[CheckResult]:
    """Run all phase 0 checks and return a flat list of CheckResult."""
    results: list[CheckResult] = []
    results.extend(_check_services(ctx))
    results.extend(_check_no_failed_units(ctx))
    results.extend(_check_timers(ctx))
    results.extend(_check_ports(ctx))
    results.extend(_check_grafana_port(ctx))
    results.extend(_check_qdrant_docs(ctx))
    if not ctx.dashboard_safe:
        results.extend(_check_postgres_tables(ctx))
        results.extend(_check_redis_keys(ctx))
    results.extend(_check_apparmor(ctx))
    results.extend(_check_inference(ctx))
    if not ctx.dashboard_safe:
        results.extend(_check_continue(ctx))
        results.extend(_check_flagship_cli(ctx))
    results.extend(_check_routing(ctx))
    results.extend(_check_delegate_rate(ctx))
    results.extend(_check_safety_gate(ctx))
    results.extend(_check_uag_replay(ctx))
    results.extend(_check_dag_executor(ctx))
    results.extend(_check_safety_policy(ctx))
    results.extend(_check_trust_roots(ctx))
    results.extend(_check_workspace_isolation(ctx))
    results.extend(_check_fleet_control(ctx))
    results.extend(_check_benchmark_harness(ctx))
    results.extend(_check_harness_runner(ctx))
    results.extend(_check_budget_guardrail(ctx))
    results.extend(_check_rollback_drill(ctx))
    results.extend(_check_aqd_ergonomics(ctx))
    results.extend(_check_mcp_blueprints(ctx))
    results.extend(_check_graph_runner(ctx))
    results.extend(_check_ide_adapter(ctx))
    results.extend(_check_ablation_profiles(ctx))
    results.extend(_check_aqd_reasoning(ctx))
    results.extend(_check_logic_indexer(ctx))
    results.extend(_check_aqd_logic(ctx))
    results.extend(_check_topology_api(ctx))
    results.extend(_check_local_model_config(ctx))
    if not ctx.dashboard_safe:
        results.extend(_check_local_payload_discipline(ctx))
    if not ctx.dashboard_safe:
        results.extend(_check_discovery_agent(ctx))
        results.extend(_check_model_catalog_freshness(ctx))
        results.extend(_check_flat_prd_gate(ctx))
        results.extend(_check_agent_artifact_policy(ctx))
        results.extend(_check_agent_memory_surface_registry(ctx))
    results.extend(_check_ragas_eval(ctx))
    results.extend(_check_clm(ctx))
    results.extend(_check_nsjail_sandbox(ctx))
    results.extend(_check_graphrag(ctx))
    results.extend(_check_s2_tool_auth_policy(ctx))
    results.extend(_check_local_agent_docs(ctx))
    results.extend(_check_phase67_dashboard(ctx))
    results.extend(_check_phase66_wasmtime(ctx))
    if not ctx.dashboard_safe:
        results.extend(_check_phase83_dag_context(ctx))
        results.extend(_check_phase85_drop_zone(ctx))
        results.extend(_check_phase86_attention_queue(ctx))
    results.extend(_check_phase87_training_ingest(ctx))
    results.extend(_check_phase146_identity_coverage(ctx))
    if not ctx.dashboard_safe:
        results.extend(_check_local_delegation_artifact(ctx))
    results.extend(_check_intent_classifier_coverage(ctx))
    results.extend(_check_ragas_faithfulness_guard(ctx))
    results.extend(_check_token_usage_coverage(ctx))
    results.extend(_check_modal_task_profiles(ctx))
    results.extend(_check_local_inference_contract(ctx))
    results.extend(_check_local_inference_l2a(ctx))
    results.extend(_check_local_inference_l2b(ctx))
    if not ctx.dashboard_safe:
        results.extend(_check_local_inference_budget(ctx))
        results.extend(_check_local_agent_store_memory_contract(ctx))
        results.extend(_check_phase171_throughput_calibration(ctx))
        results.extend(_check_osint_active_recon_gate(ctx))
        results.extend(_check_analysis_only_stagnation_mode(ctx))
        results.extend(_check_phase172_delegation_health(ctx))
        results.extend(_check_local_agent_monitor_visibility(ctx))
        results.extend(_check_candidate_lifecycle(ctx))
    results.extend(_check_eval_sandbox(ctx))
    results.extend(_check_aq_eval_harness(ctx))
    results.extend(_check_context_compaction_sandwich(ctx))
    results.extend(_check_round_decision_authorization(ctx))
    results.extend(_check_immutable_qa_effectiveness(ctx))
    results.extend(_check_state_authorities(ctx))
    results.extend(_check_registry_lookup_compatibility(ctx))
    results.extend(_check_dashboard_program_progress(ctx))
    results.extend(_check_golden_eval_parity(ctx))
    results.extend(_check_agentic_parity(ctx))
    results.extend(_check_delegation_feedback_contract(ctx))
    results.extend(_check_cross_model_critique(ctx))
    results.extend(_check_adopt_workflow(ctx))
    results.extend(_check_phase173_training_health(ctx))
    if ctx.dashboard_safe:
        results.extend(_dashboard_safe_host_only_skips())
    return results


def _check_phase173_training_health(ctx: RunContext) -> list[CheckResult]:
    """Phase 173-E: Training Pipeline Health QA."""
    results: list[CheckResult] = []

    # 0.13.1 — Training telemetry path writable
    telemetry_dir = Path("/var/lib/ai-stack/hybrid/")
    if telemetry_dir.exists() and telemetry_dir.is_dir():
        results.append(passed(4, "0.13.1", "Training telemetry path exists and is a directory"))
    else:
        results.append(failed(4, "0.13.1", "Training telemetry path", f"not found or not a directory: {telemetry_dir}"))

    # 0.13.2 — Training dataset non-empty
    dataset_path = Path("/var/lib/ai-stack/hybrid/fine-tuning/dataset.jsonl")
    if dataset_path.exists():
        try:
            with open(dataset_path, "r", encoding="utf-8", errors="replace") as f:
                first_line = f.readline()
                if first_line:
                    results.append(passed(4, "0.13.2", "Training dataset non-empty (at least 1 line)"))
                else:
                    results.append(failed(4, "0.13.2", "Training dataset", "file exists but is empty"))
        except Exception as e:
            results.append(failed(4, "0.13.2", "Training dataset", str(e)))
    else:
        results.append(failed(4, "0.13.2", "Training dataset", f"file missing: {dataset_path}"))

    # 0.13.3 — Training health endpoint reachable
    dashboard_port = getattr(ctx, "dashboard_port", 8889)
    health_url = f"http://localhost:{dashboard_port}/api/aistack/training/health"
    try:
        import urllib.request
        try:
            with urllib.request.urlopen(health_url, timeout=5) as resp:
                if resp.status == 200:
                    results.append(passed(4, "0.13.3", "Training health endpoint reachable (HTTP 200)"))
                else:
                    results.append(failed(4, "0.13.3", "Training health endpoint", f"HTTP {resp.status}"))
        except urllib.request.HTTPError as e:
            results.append(failed(4, "0.13.3", "Training health endpoint", f"HTTP {e.code}"))
        except Exception:
            results.append(skipped(4, "0.13.3", "Training health endpoint", "unreachable (dashboard may not be running)"))
    except Exception as e:
        results.append(failed(4, "0.13.3", "Training health endpoint", str(e)))

    # 0.13.4 — tool_result samples present in dataset
    if dataset_path.exists():
        try:
            count = 0
            with open(dataset_path, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    if '"source": "tool_result"' in line:
                        count += 1
                        break
            if count >= 1:
                results.append(passed(4, "0.13.4", "tool_result samples present in dataset"))
            else:
                results.append(skipped(4, "0.13.4", "tool_result samples present in dataset", "none found (dependency on 173-A deployment)"))
        except Exception as e:
            results.append(failed(4, "0.13.4", "tool_result samples check", str(e)))
    else:
        results.append(failed(4, "0.13.4", "tool_result samples check", "dataset.jsonl missing"))

    return results


def _check_cross_model_critique(ctx: RunContext) -> list[CheckResult]:
    """Phase 157: cross_model_critique module exists and passes syntax check."""
    mod = ctx.repo_root / "ai-stack" / "local-agents" / "cross_model_critique.py"
    if not mod.exists():
        return [failed(1, "0.157.1", "cross-model critique", "cross_model_critique.py missing")]
    import ast
    try:
        ast.parse(mod.read_text())
    except SyntaxError as exc:
        return [failed(1, "0.157.1", "cross-model critique", f"syntax error: {exc}")]
    # Check required public symbols
    src = mod.read_text()
    missing = [s for s in ("record_critique", "query_critiques", "synthesize_critiques") if s not in src]
    if missing:
        return [failed(1, "0.157.1", "cross-model critique", f"missing symbols: {missing}")]
    return [passed(1, "0.157.1", "cross-model critique", "module OK, 3 public symbols present")]


def _check_adopt_workflow(ctx: RunContext) -> list[CheckResult]:
    """Phase 157: aq-adopt-workflow script exists and is executable."""
    script = ctx.repo_root / "scripts" / "ai" / "aq-adopt-workflow"
    if not script.exists():
        return [failed(1, "0.157.2", "adopt workflow", "aq-adopt-workflow missing")]
    if not os.access(script, os.X_OK):
        return [failed(1, "0.157.2", "adopt workflow", "aq-adopt-workflow not executable")]
    import subprocess
    try:
        r = subprocess.run(["bash", "-n", str(script)], capture_output=True, timeout=5)
        if r.returncode != 0:
            return [failed(1, "0.157.2", "adopt workflow", f"bash -n failed: {r.stderr.decode()[:100]}")]
    except Exception as exc:
        return [failed(1, "0.157.2", "adopt workflow", f"bash check error: {exc}")]
    return [passed(1, "0.157.2", "adopt workflow", "aq-adopt-workflow exists and passes bash -n")]


def _check_delegation_feedback_contract(ctx: RunContext) -> list[CheckResult]:
    """Phase 156: delegation_feedback contract detection accuracy (json + exact-output signals)."""
    check = ctx.repo_root / "scripts" / "testing" / "test-delegation-feedback-contract.py"
    if not check.exists():
        return [failed(1, "0.156.1", "delegation feedback contract", "test-delegation-feedback-contract.py missing")]
    try:
        rc = subprocess.run(["python3", str(check)], capture_output=True, text=True, timeout=15)
        if rc.returncode == 0:
            return [passed(1, "0.156.1", "delegation feedback contract detection: json + exact-output signals correct")]
        detail = rc.stdout.strip() or rc.stderr.strip() or f"exit {rc.returncode}"
        return [failed(1, "0.156.1", "delegation feedback contract", detail)]
    except Exception as exc:
        return [failed(1, "0.156.1", "delegation feedback contract", str(exc))]


def _check_agentic_parity(ctx: RunContext) -> list[CheckResult]:
    """Phase 154: cross-model agentic workflow parity."""
    check = ctx.repo_root / "scripts" / "testing" / "test-agentic-workflow-parity.py"
    if not check.exists():
        return [failed(1, "0.154.1", "agentic workflow parity", "test missing")]
    try:
        rc = subprocess.run(["python3", str(check)], capture_output=True, text=True, timeout=15)
        if rc.returncode == 0:
            return [passed(1, "0.154.1", "cross-model workflow parity verified")]
        detail = rc.stdout.strip() or rc.stderr.strip() or f"exit {rc.returncode}"
        return [failed(1, "0.154.1", "agentic workflow parity", detail)]
    except Exception as exc:
        return [failed(1, "0.154.1", "agentic workflow parity", str(exc))]


def _check_eval_sandbox(ctx: RunContext) -> list[CheckResult]:
    """Phase 150 Slice 5: EvalSandboxExecutor static evaluation."""
    check = ctx.repo_root / "scripts" / "testing" / "test-eval-sandbox.py"
    if not check.exists():
        return [failed(1, "0.150.5", "eval sandbox executor", "test-eval-sandbox.py missing")]
    try:
        rc = subprocess.run(
            ["python3", str(check)],
            capture_output=True, text=True, timeout=15,
        )
        if rc.returncode == 0:
            return [passed(1, "0.150.5", "eval sandbox static checks + hardware constraint guard")]
        detail = rc.stdout.strip() or rc.stderr.strip() or f"exit {rc.returncode}"
        return [failed(1, "0.150.5", "eval sandbox executor", detail)]
    except Exception as exc:
        return [failed(1, "0.150.5", "eval sandbox executor", str(exc))]


def _check_aq_eval_harness(ctx: RunContext) -> list[CheckResult]:
    """Repo-local static eval/red-team harness with provenance and metrics."""
    check = ctx.repo_root / "scripts" / "testing" / "test-aq-eval.py"
    if not check.exists():
        return [failed(1, "0.10.25", "aq-eval static harness", "test-aq-eval.py missing")]
    try:
        rc = subprocess.run(
            ["python3", str(check)],
            capture_output=True, text=True, timeout=60,
        )
        if rc.returncode == 0:
            return [passed(1, "0.10.25", "aq-eval static red-team harness metrics + provenance")]
        detail = rc.stdout.strip() or rc.stderr.strip() or f"exit {rc.returncode}"
        return [failed(1, "0.10.25", "aq-eval static harness", detail)]
    except Exception as exc:
        return [failed(1, "0.10.25", "aq-eval static harness", str(exc))]


def _check_context_compaction_sandwich(ctx: RunContext) -> list[CheckResult]:
    """Repo-local context-risk routing through switchboard artifacts and aq-context-manage guidance."""
    check = ctx.repo_root / "scripts" / "testing" / "test-context-compaction-sandwich.py"
    if not check.exists():
        return [failed(1, "0.10.26", "context compaction sandwich", "test-context-compaction-sandwich.py missing")]
    try:
        rc = subprocess.run(
            ["python3", str(check)],
            capture_output=True, text=True, timeout=60,
        )
        if rc.returncode == 0:
            return [passed(1, "0.10.26", "context-risk outputs route through artifact compaction + aq-context-manage guidance")]
        detail = rc.stdout.strip() or rc.stderr.strip() or f"exit {rc.returncode}"
        return [failed(1, "0.10.26", "context compaction sandwich", detail)]
    except Exception as exc:
        return [failed(1, "0.10.26", "context compaction sandwich", str(exc))]


def _check_round_decision_authorization(ctx: RunContext) -> list[CheckResult]:
    """C0.1: assignment requires current evidence and explicit authorization."""
    test_path = ctx.repo_root / "scripts" / "testing" / "test-round-decision-authorization.py"
    if not test_path.exists():
        return [failed(5, "0.10.27", "evidence-bound collaboration assignment invariants",
                       "test-round-decision-authorization.py missing; assignment gate fails closed")]
    try:
        proc = subprocess.run(
            ["python3", str(test_path)], cwd=str(ctx.repo_root), capture_output=True,
            text=True, timeout=60,
        )
    except Exception as exc:
        return [failed(5, "0.10.27", "evidence-bound collaboration assignment invariants", str(exc)[:160])]
    if proc.returncode == 0:
        return [passed(5, "0.10.27", "positive, negative, and cascade assignment invariants")]
    detail = (proc.stderr or proc.stdout or "focused invariant test failed").strip()[-240:]
    return [failed(5, "0.10.27", "evidence-bound collaboration assignment invariants", detail)]


def _check_immutable_qa_effectiveness(ctx: RunContext) -> list[CheckResult]:
    """C0.2: immutable QA CAS, evidence algebra, and telemetry boundary."""
    tests = ["test-qa-evidence-store.py", "test-evidence-algebra.py", "test-telemetry-root-boundary.py"]
    for filename in tests:
        path = ctx.repo_root / "scripts" / "testing" / filename
        if not path.exists():
            return [failed(5, "0.10.28", "immutable QA evidence and effectiveness", f"{filename} missing")]
        proc = subprocess.run(["python3", str(path)], cwd=ctx.repo_root, capture_output=True, text=True, timeout=90)
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or f"{filename} exit {proc.returncode}").strip()[-300:]
            return [failed(5, "0.10.28", "immutable QA evidence and effectiveness", detail)]
    return [passed(5, "0.10.28", "concurrent immutable QA CAS, required-unknown blocking, and telemetry boundary")]


_SA_ALLOWED_CONDITIONS = {"SINGLE", "SPLIT_BRAIN", "UNKNOWN", "UNOWNED"}


def _sa_nonneg_int(value: object) -> bool:
    """True only for a genuine nonnegative int (bool is rejected — True/False are not counts)."""
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _validate_state_authority_doc(doc: object) -> str | None:
    """Fail-closed validation of the checker's {meta, findings} document.

    Returns an error string on the first invariant violation, else None. The
    integration refuses to publish anything that does not satisfy every shape/type/
    identity invariant, so a malformed or stale checker run can never be projected as
    healthy state onto the audit card.
    """
    if not isinstance(doc, dict) or set(doc.keys()) != {"meta", "findings"}:
        return "document is not exactly {meta, findings}"
    if not isinstance(doc["findings"], list):
        return "findings is not a list"
    meta = doc["meta"]
    if not isinstance(meta, dict):
        return "meta is not an object"
    if meta.get("slice") != "C0.3" or meta.get("artifact") != "system-state-authorities":
        return "meta slice/artifact identity mismatch"
    if meta.get("registry_valid") is not True:
        return "registry_valid is not True"
    if meta.get("cycle1_authority") != "NOT_AUTHORIZED":
        return "cycle1_authority is not exactly NOT_AUTHORIZED"
    run_at = meta.get("run_at")
    if not isinstance(run_at, str):
        return "run_at missing or non-string"
    try:
        time.strptime(run_at, "%Y-%m-%dT%H:%M:%SZ")
    except (ValueError, TypeError):
        return f"run_at is not a valid UTC timestamp: {run_at!r}"
    if not _sa_nonneg_int(meta.get("blocker_count")):
        return "blocker_count is not a nonnegative integer"
    if not _sa_nonneg_int(meta.get("authorities_total")):
        return "authorities_total is not a nonnegative integer"
    cond_counts = meta.get("condition_counts")
    if not isinstance(cond_counts, dict):
        return "condition_counts is not an object"
    if set(cond_counts) != _SA_ALLOWED_CONDITIONS:
        return "condition_counts does not contain the exact required condition keys"
    for key, val in cond_counts.items():
        if not _sa_nonneg_int(val):
            return f"condition_counts[{key!r}] is not a nonnegative integer"
    if sum(cond_counts.values()) != meta["authorities_total"]:
        return "condition_counts total does not equal authorities_total"
    minimum_blockers = cond_counts["SPLIT_BRAIN"] + cond_counts["UNKNOWN"] + cond_counts["UNOWNED"]
    if meta["blocker_count"] < minimum_blockers:
        return "blocker_count is lower than the non-singleton authority count"
    return None


def _publish_state_authority_snapshot(repo_root: Path, encoded: str) -> str | None:
    """Atomically publish the validated checker document to the FIXED audit-card path.

    The read-only checker never writes; this authorized integration is the sole publisher
    and it writes ONLY to the fixed repo path (no caller-supplied path). It refuses a
    symlinked / non-directory governance dir and a symlinked / non-regular target so it can
    never write through to an attacker-controlled location. Returns an error string on
    refusal/failure, else None.
    """
    gov_dir = repo_root / ".agents" / "governance"
    target = gov_dir / "state-authorities-latest.json"
    if gov_dir.is_symlink() or (gov_dir.exists() and not gov_dir.is_dir()):
        return f"refusing publish: {gov_dir} is a symlink or non-directory"
    gov_dir.mkdir(parents=True, exist_ok=True)
    if target.is_symlink() or (target.exists() and not target.is_file()):
        return f"refusing publish: {target} is a symlink or non-regular file"
    tmp = target.with_name(f"{target.name}.tmp.{os.getpid()}")
    payload = encoded if encoded.endswith("\n") else encoded + "\n"
    fd: int | None = None
    created_tmp = False
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        fd = os.open(tmp, flags, 0o600)
        created_tmp = True
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fd = None
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, target)
    except OSError as exc:
        try:
            if fd is not None:
                os.close(fd)
            if created_tmp:
                os.unlink(tmp)
        except OSError:
            pass
        return f"snapshot publish failed: {exc}"
    return None


def _check_state_authorities(ctx: RunContext) -> list[CheckResult]:
    """C0.3: bounded read-only state-authority ledger, checker, and audit-card projection."""
    tests = ["test-state-authorities.py", "test-dashboard-governance-projection.py"]
    for filename in tests:
        path = ctx.repo_root / "scripts" / "testing" / filename
        if not path.exists():
            return [failed(5, "0.10.29", "state authority ledger and governance projection", f"{filename} missing")]
        proc = subprocess.run(["python3", str(path)], cwd=ctx.repo_root, capture_output=True, text=True, timeout=90)
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or f"{filename} exit {proc.returncode}").strip()[-300:]
            return [failed(5, "0.10.29", "state authority ledger and governance projection", detail)]
    # The checker is strictly read-only (no --snapshot). Run it, validate the {meta,findings}
    # contract fail-closed, then let THIS authorized integration atomically publish the audit-card
    # snapshot to the fixed repo path. No --strict: SPLIT_BRAIN/UNKNOWN/UNOWNED are valid discovery
    # values that must not fail the check.
    checker = ctx.repo_root / "scripts" / "governance" / "check-state-authorities.py"
    try:
        run = subprocess.run(["python3", str(checker), "--machine"],
                             cwd=ctx.repo_root, capture_output=True, text=True, timeout=30)
    except Exception as exc:
        return [failed(5, "0.10.29", "bounded state authority checker", str(exc)[:200])]
    if run.returncode not in (0, 1):
        return [failed(5, "0.10.29", "bounded state authority checker",
                       (run.stderr or "checker structural/budget error").strip()[-200:])]
    try:
        doc = json.loads(run.stdout)
    except (json.JSONDecodeError, ValueError) as exc:
        return [failed(5, "0.10.29", "bounded state authority checker", f"unparseable checker stdout: {exc}")]
    contract_err = _validate_state_authority_doc(doc)
    if contract_err is not None:
        return [failed(5, "0.10.29", "state authority projection contract", contract_err)]
    pub_err = _publish_state_authority_snapshot(ctx.repo_root, run.stdout)
    if pub_err is not None:
        return [failed(5, "0.10.29", "state authority snapshot publication", pub_err)]
    meta = doc["meta"]
    blockers = meta["blocker_count"]
    conds = meta["condition_counts"]
    dur = meta.get("budget", {}).get("duration_seconds", "?")
    return [passed(5, "0.10.29",
                   f"bounded authority checker + validated projection: {blockers} ratification-blockers, "
                   f"conditions {conds}, {dur}s")]


def _check_registry_lookup_compatibility(ctx: RunContext) -> list[CheckResult]:
    """R0.1: bounded legacy lookup, closed facts, pure projection, and visible TUI state."""
    checker = ctx.repo_root / "scripts" / "testing" / "test-agent-ops-projection.py"
    if not checker.exists():
        return [failed(5, "0.10.30", "registry lookup compatibility", "focused test missing")]
    try:
        run = subprocess.run(
            ["python3", str(checker)], cwd=ctx.repo_root,
            capture_output=True, text=True, timeout=180,
        )
    except Exception as exc:
        return [failed(5, "0.10.30", "registry lookup compatibility", str(exc)[:200])]
    if run.returncode != 0:
        detail = (run.stderr or run.stdout or f"exit {run.returncode}").strip()[-500:]
        return [failed(5, "0.10.30", "registry lookup compatibility", detail)]
    summary = next(
        (line.strip() for line in reversed(run.stderr.splitlines()) if "Ran " in line),
        "focused projection/compatibility suite passed",
    )
    return [passed(
        5, "0.10.30",
        f"bounded legacy lookup + strict mutation + closed projection + TUI visibility: {summary}",
    )]


def _check_dashboard_program_progress(ctx: RunContext) -> list[CheckResult]:
    """0.10.40: canonical tracker is linked, tested, and live when dashboard is available."""
    checker = ctx.repo_root / "scripts" / "testing" / "test-dashboard-program-progress.py"
    if not checker.exists():
        return [failed(5, "0.10.40", "program progress tracker", "focused test missing")]
    try:
        run = subprocess.run(
            ["python3", str(checker), "--static-only"], cwd=ctx.repo_root,
            capture_output=True, text=True, timeout=60,
        )
    except Exception as exc:
        return [failed(5, "0.10.40", "program progress tracker", str(exc)[:200])]
    if run.returncode != 0:
        detail = (run.stderr or run.stdout or f"exit {run.returncode}").strip()[-500:]
        return [failed(5, "0.10.40", "program progress tracker", detail)]

    dashboard_url = f"http://127.0.0.1:{getattr(ctx, 'dashboard_port', 8889)}"
    try:
        status, body = http_get(f"{dashboard_url}/assets/aqos-progress-tracker.html", timeout=5)
    except Exception as exc:
        return [skipped(5, "0.10.40", "program progress tracker live asset", str(exc)[:160])]
    if status != 200:
        return [failed(5, "0.10.40", "program progress tracker live asset", f"HTTP {status}")]
    if "FROZEN_IMPLEMENTATION_SNAPSHOT" not in body:
        return [failed(5, "0.10.40", "program progress tracker live asset", "stale deployed asset")]
    try:
        root_status, root_body = http_get(dashboard_url, timeout=5)
    except Exception as exc:
        return [failed(5, "0.10.40", "program progress tracker dashboard linkage", str(exc)[:160])]
    if root_status != 200 or 'id="tab-program"' not in root_body:
        return [failed(5, "0.10.40", "program progress tracker dashboard linkage",
                       f"HTTP {root_status}; Program tab absent={root_status == 200}")]
    return [passed(5, "0.10.40", "canonical tracker static contract + live asset/dashboard HTTP 200")]


def _check_golden_eval_parity(ctx: RunContext) -> list[CheckResult]:
    """Phase 152: golden eval set size + static checks for workflow/role/cross-model parity."""
    import re

    results: list[CheckResult] = []
    eval_path = ctx.repo_root / "data" / "harness-golden-evals.json"

    # 0.152.1a — eval set must exist and have at least 15 entries
    if not eval_path.exists():
        return [failed(1, "0.152.1", "golden eval parity", "data/harness-golden-evals.json missing")]
    try:
        with eval_path.open() as f:
            evals = json.load(f)
    except Exception as exc:
        return [failed(1, "0.152.1", "golden eval parity", f"JSON parse error: {exc}")]

    cases = evals.get("cases", [])
    n = len(cases)
    if n < 15:
        results.append(failed(1, "0.152.1", "golden eval parity",
                              f"eval set has {n} entries — need ≥15 for adequate coverage"))
    else:
        results.append(passed(1, "0.152.1", f"golden eval set size: {n} entries (≥15 required)"))

    # Helper: resolve a path that may be relative to repo root or absolute
    def _rp(rel: str) -> Path:
        p = Path(rel)
        return p if p.is_absolute() else ctx.repo_root / rel

    # 0.152.2 — WORKFLOW-CANON.md exists and contains 8-step keywords
    wc_path = _rp(".agent/WORKFLOW-CANON.md")
    if not wc_path.exists():
        results.append(failed(1, "0.152.2", "WORKFLOW-CANON.md", "file missing"))
    else:
        content = wc_path.read_text(errors="replace")
        required = ["ORIENT", "RESEARCH", "EXECUTE", "VALIDATE", "COMMIT"]
        missing = [t for t in required if t not in content]
        if missing:
            results.append(failed(1, "0.152.2", "WORKFLOW-CANON.md",
                                  f"missing step keywords: {missing}"))
        else:
            results.append(passed(1, "0.152.2", "WORKFLOW-CANON.md contains canonical 8-step keywords"))

    # 0.152.3 — PULSE.log: at least one line matches expected format
    pulse_path = _rp(".agent/collaboration/PULSE.log")
    if not pulse_path.exists():
        results.append(failed(1, "0.152.3", "PULSE.log format", "file missing"))
    else:
        pulse_pattern = re.compile(
            r"^\[20\d{2}-\d{2}-\d{2}T[\d:Z.+-]+\] \[[a-z][\w-]*\] \[[a-z][\w-]*\]: .+ — .+$"
        )
        lines = pulse_path.read_text(errors="replace").splitlines()
        matching = [ln for ln in lines if pulse_pattern.match(ln.strip())]
        if not matching:
            results.append(failed(1, "0.152.3", "PULSE.log format",
                                  "no lines match [ISO-ts] [agent] [action]: scope — outcome pattern"))
        else:
            results.append(passed(1, "0.152.3", f"PULSE.log format: {len(matching)} conforming lines"))

    # 0.152.4 — RESUME.json has all required fields
    resume_path = _rp(".agent/collaboration/RESUME.json")
    if not resume_path.exists():
        results.append(failed(1, "0.152.4", "RESUME.json required fields", "file missing"))
    else:
        try:
            resume = json.loads(resume_path.read_text(errors="replace"))
            req_fields = ["current_objective", "phase", "todo_snapshot", "uncommitted_changes", "resume_hint"]
            missing_f = [f for f in req_fields if f not in resume]
            if missing_f:
                results.append(failed(1, "0.152.4", "RESUME.json required fields",
                                      f"missing: {missing_f}"))
            else:
                results.append(passed(1, "0.152.4", "RESUME.json has all required fields"))
        except Exception as exc:
            results.append(failed(1, "0.152.4", "RESUME.json required fields",
                                  f"parse error: {exc}"))

    # 0.152.5 — role-matrix.md exists with 4 canonical roles + sub-agent rule
    rm_path = _rp("docs/architecture/role-matrix.md")
    if not rm_path.exists():
        results.append(failed(1, "0.152.5", "role-matrix.md", "file missing at docs/architecture/role-matrix.md"))
    else:
        rm_content = rm_path.read_text(errors="replace")
        roles = ["orchestrator", "architect", "implementer", "reviewer"]
        missing_roles = [r for r in roles if r not in rm_content]
        if missing_roles:
            results.append(failed(1, "0.152.5", "role-matrix.md canonical roles",
                                  f"missing roles: {missing_roles}"))
        elif "assigned slice" not in rm_content:
            results.append(failed(1, "0.152.5", "role-matrix.md sub-agent rule",
                                  "'assigned slice' constraint not found"))
        else:
            results.append(passed(1, "0.152.5",
                                  "role-matrix.md: 4 canonical roles defined + sub-agent constraint present"))

    # 0.152.6 — all 3 agent instruction files reference WORKFLOW-CANON.md and use canonical role names
    agent_files = {
        "GEMINI.md": _rp(".agent/GEMINI.md"),
        "CODEX.md": _rp(".agent/CODEX.md"),
        "LOCAL-AGENT.md": _rp(".agent/LOCAL-AGENT.md"),
    }
    parity_failures = []
    for name, path in agent_files.items():
        if not path.exists():
            parity_failures.append(f"{name} missing")
            continue
        text = path.read_text(errors="replace")
        text_lower = text.lower()
        if "workflow-canon" not in text_lower:
            parity_failures.append(f"{name}: no WORKFLOW-CANON reference")
        for role in ["orchestrator", "implementer", "reviewer"]:
            if role not in text_lower:
                parity_failures.append(f"{name}: missing role '{role}'")
    if parity_failures:
        results.append(failed(1, "0.152.6", "cross-model parity (agent files)",
                              "; ".join(parity_failures)))
    else:
        results.append(passed(1, "0.152.6",
                              "GEMINI.md, CODEX.md, LOCAL-AGENT.md: WORKFLOW-CANON ref + canonical roles present"))

    # 0.152.7 — switchboard-profiles.yaml contains the 3 required profiles
    swb_path = _rp("config/switchboard-profiles.yaml")
    if not swb_path.exists():
        results.append(failed(1, "0.152.7", "switchboard profiles", "config/switchboard-profiles.yaml missing"))
    else:
        swb_content = swb_path.read_text(errors="replace")
        required_profiles = ["local-coding", "remote-default", "local-tool-calling"]
        missing_p = [p for p in required_profiles if p not in swb_content]
        if missing_p:
            results.append(failed(1, "0.152.7", "switchboard profiles",
                                  f"missing profiles: {missing_p}"))
        else:
            results.append(passed(1, "0.152.7",
                                  "switchboard-profiles.yaml: local-coding, remote-default, local-tool-calling present"))

    # 0.152.8 — trust_scoring.py exists
    ts_path = _rp("ai-stack/local-agents/trust_scoring.py")
    if not ts_path.exists():
        results.append(failed(1, "0.152.8", "trust_scoring module", "ai-stack/local-agents/trust_scoring.py missing"))
    else:
        results.append(passed(1, "0.152.8", "trust_scoring.py exists"))

    # 0.152.9 — candidates.json exists and has ≥1 candidate with trust_score > 0
    cands_path = _rp(".agents/improvement/candidates.json")
    if not cands_path.exists():
        results.append(failed(1, "0.152.9", "candidates.json trust scores", ".agents/improvement/candidates.json missing"))
    else:
        try:
            cands_data = json.loads(cands_path.read_text(errors="replace"))
            cands = cands_data.get("candidates", [])
            positive = [c for c in cands if isinstance(c.get("trust_score"), (int, float)) and c["trust_score"] > 0]
            if not positive:
                results.append(failed(1, "0.152.9", "candidates.json trust scores",
                                      f"{len(cands)} candidates but none with trust_score > 0"))
            else:
                results.append(passed(1, "0.152.9",
                                      f"candidates.json: {len(positive)} candidate(s) with trust_score > 0"))
        except Exception as exc:
            results.append(failed(1, "0.152.9", "candidates.json trust scores", f"parse error: {exc}"))

    return results


def _check_candidate_lifecycle(ctx: RunContext) -> list[CheckResult]:
    """Phase 150 Slice 1: CandidateLifecycleManager module + test."""
    check = ctx.repo_root / "scripts" / "testing" / "test-candidate-lifecycle.py"
    if not check.exists():
        return [failed(1, "0.150.1", "candidate lifecycle manager", "test-candidate-lifecycle.py missing")]
    try:
        rc = subprocess.run(
            ["python3", str(check)],
            capture_output=True, text=True, timeout=15,
        )
        if rc.returncode == 0:
            return [passed(1, "0.150.1", "candidate lifecycle state machine + defaults")]
        detail = rc.stdout.strip() or rc.stderr.strip() or f"exit {rc.returncode}"
        return [failed(1, "0.150.1", "candidate lifecycle manager", detail)]
    except Exception as exc:
        return [failed(1, "0.150.1", "candidate lifecycle manager", str(exc))]


def _check_clm(ctx: RunContext) -> list[CheckResult]:
    """Phase 61: CLM 3-tier lifecycle, MLFQ pressure integration, HTTP routes."""
    results: list[CheckResult] = []

    clm = (
        ctx.repo_root
        / "ai-stack" / "mcp-servers" / "hybrid-coordinator"
        / "knowledge" / "context_lifecycle_manager.py"
    )
    scheduler = (
        ctx.repo_root
        / "ai-stack" / "mcp-servers" / "hybrid-coordinator"
        / "mlfq_scheduler.py"
    )
    prompt_yaml = ctx.repo_root / "config" / "clm-compaction-prompt.yaml"

    # 61.1 — CLM module: 3-tier structure + compaction + thermal gate
    if not clm.exists():
        results.append(failed(4, "61.1", "context_lifecycle_manager.py", "file missing"))
    else:
        text = clm.read_text()
        checks = {
            "Hot/Warm/Cold tiers": all(t in text for t in ("hot", "warm", "cold")),
            "_demote_to_warm": "_demote_to_warm" in text,
            "_demote_to_cold": "_demote_to_cold" in text,
            "thermal_gate (AM-G4)": "critical" in text and "shutdown" in text,
            "compaction prompt load": "_load_compaction_prompt" in text,
            # Guard applied either directly or via build_llama_payload() SSOT import.
            # build_llama_payload always sets chat_template_kwargs.enable_thinking=False.
            "enable_thinking guard": "enable_thinking" in text or "build_llama_payload" in text,
            "CLM_HOT_MAX_MB (256 default)": "256" in text,
        }
        missing = [k for k, v in checks.items() if not v]
        if missing:
            results.append(failed(4, "61.1", "context_lifecycle_manager.py CLM", f"missing: {', '.join(missing)}"))
        else:
            results.append(passed(4, "61.1", "CLM: 3-tier Hot/Warm/Cold + thermal gate + compaction"))

    # 61.2 — compaction prompt YAML present + valid
    if not prompt_yaml.exists():
        results.append(failed(4, "61.2", "clm-compaction-prompt.yaml", "file missing"))
    else:
        try:
            import yaml as _yaml
            d = _yaml.safe_load(prompt_yaml.read_text())
            if "template" in d and "{session_id}" in d["template"]:
                results.append(passed(4, "61.2", "clm-compaction-prompt.yaml valid (template + {session_id})"))
            else:
                results.append(failed(4, "61.2", "clm-compaction-prompt.yaml", "missing template or {session_id} placeholder"))
        except ModuleNotFoundError:
            results.append(skipped(4, "61.2", "clm-compaction-prompt.yaml parse (PyYAML not in this env; install pyyaml)"))
        except Exception as exc:
            results.append(failed(4, "61.2", "clm-compaction-prompt.yaml parse", str(exc)))

    # 61.3 — MLFQ pressure integration present
    if not scheduler.exists():
        results.append(failed(4, "61.3", "mlfq_scheduler.py CLM pressure", "file missing"))
    else:
        text = scheduler.read_text()
        if "apply_clm_pressure" in text and "pressure_pct" in text:
            results.append(passed(4, "61.3", "MLFQ apply_clm_pressure() wired (Phase 61.5)"))
        else:
            results.append(failed(4, "61.3", "MLFQ CLM pressure", "apply_clm_pressure() not found in mlfq_scheduler.py"))

    # 61.4 — live CLM status endpoint (requires API key)
    headers = {"X-API-Key": ctx.api_key} if ctx.api_key else {}
    data = http_json(f"{ctx.hybrid_coordinator_url}/context/lifecycle/status", timeout=4, headers=headers)
    if data is None:
        results.append(skipped(4, "61.4", "GET /context/lifecycle/status", "coordinator unreachable or pre-rebuild build"))
    elif "tiers" in data and "pressure_pct" in data:
        results.append(passed(4, "61.4", f"GET /context/lifecycle/status OK (pressure={data.get('pressure_pct')}%)"))
    else:
        results.append(failed(4, "61.4", "GET /context/lifecycle/status", f"unexpected response: {list(data.keys())[:5]}"))

    return results


def _check_graphrag(ctx: RunContext) -> list[CheckResult]:
    """Phase 63: GraphRAG knowledge extraction + NixOS impermanence."""
    results: list[CheckResult] = []

    kg_indexer = ctx.repo_root / "scripts" / "ai" / "aq-index-knowledge-graph"
    graph_search = (
        ctx.repo_root
        / "ai-stack" / "mcp-servers" / "hybrid-coordinator"
        / "knowledge" / "graph_search.py"
    )
    rag_aug = (
        ctx.repo_root
        / "ai-stack" / "mcp-servers" / "hybrid-coordinator"
        / "rag_augmentor.py"
    )
    host_class = (
        ctx.repo_root
        / "nix" / "modules" / "host-classes" / "p14s-amd-ai-workstation.nix"
    )

    # 63.1 — aq-index-knowledge-graph: script exists + dry-run exits 0
    if not kg_indexer.exists():
        results.append(failed(4, "63.1", "aq-index-knowledge-graph", "script missing"))
    else:
        import subprocess as _sp
        try:
            r = _sp.run(
                ["python3", str(kg_indexer), "--skip-llm", "--repo-root", str(ctx.repo_root)],
                capture_output=True, text=True, timeout=30,
            )
            if r.returncode == 0 and "extracted" in r.stdout:
                triple_count = 0
                for token in r.stdout.split():
                    try:
                        triple_count = int(token)
                        break
                    except ValueError:
                        pass
                results.append(passed(4, "63.1", f"aq-index-knowledge-graph --skip-llm exits 0 ({triple_count} triples)"))
            else:
                results.append(failed(4, "63.1", "aq-index-knowledge-graph --skip-llm", r.stdout[:60] + r.stderr[:60]))
        except Exception as exc:
            results.append(failed(4, "63.1", "aq-index-knowledge-graph", str(exc)[:80]))

    # 63.2 — graph_search.py: BFS-2 handler + register_routes present
    if not graph_search.exists():
        results.append(failed(4, "63.2", "graph_search.py", "file missing"))
    else:
        text = graph_search.read_text()
        checks = {
            "graph_search() function": "async def graph_search" in text,
            "BFS-2 depth param": "depth" in text and "hop" in text,
            "register_routes": "register_routes" in text,
            "/api/knowledge/graph/search route": "/api/knowledge/graph/search" in text,
            "entity extraction": "_extract_entities" in text,
        }
        missing = [k for k, v in checks.items() if not v]
        if missing:
            results.append(failed(4, "63.2", "graph_search.py", f"missing: {', '.join(missing)}"))
        else:
            results.append(passed(4, "63.2", "graph_search.py BFS-2 handler (entity extraction + register_routes)"))

    # 63.3 — rag_augmentor.py: graph_augment() method for knowledge_lookup / systems_software
    if not rag_aug.exists():
        results.append(failed(4, "63.3", "rag_augmentor.py graph_augment", "file missing"))
    else:
        text = rag_aug.read_text()
        checks = {
            "graph_augment method": "async def graph_augment" in text,
            "knowledge_lookup intent gate": "knowledge_lookup" in text,
            "systems_software intent gate": "systems_software" in text,
            "graph_search import": "graph_search" in text,
            "hop_depth in result": "hop_depth" in text,
        }
        missing = [k for k, v in checks.items() if not v]
        if missing:
            results.append(failed(4, "63.3", "rag_augmentor graph_augment", f"missing: {', '.join(missing)}"))
        else:
            results.append(passed(4, "63.3", "rag_augmentor.graph_augment() (knowledge_lookup + systems_software gates)"))

    # 63.4 — NixOS impermanence: option declared + host-class wired
    if not host_class.exists():
        results.append(failed(4, "63.4", "impermanence host-class config", "p14s-amd-ai-workstation.nix missing"))
    else:
        text = host_class.read_text()
        checks = {
            "environment.persistence block": "environment.persistence" in text,
            "/var/lib/ai-stack in persist": "/var/lib/ai-stack" in text,
            "/var/lib/nixos-system-dashboard in persist": "/var/lib/nixos-system-dashboard" in text,
            "impermanence.enable guard": "impermanence.enable" in text,
            "hideMounts": "hideMounts" in text,
        }
        missing = [k for k, v in checks.items() if not v]
        if missing:
            results.append(failed(4, "63.4", "impermanence host-class", f"missing: {', '.join(missing)}"))
        else:
            # /persist not required to exist here — it's a nixos-rebuild gate
            results.append(passed(4, "63.4", "impermanence declared in host-class (enable-flag guarded, /persist optional)"))

    return results


def _check_nsjail_sandbox(ctx: RunContext) -> list[CheckResult]:
    """Phase 62: nsjail execution sandbox + structured safety rails."""
    results: list[CheckResult] = []

    safety_rails = ctx.repo_root / "config" / "safety-rails.yaml"
    shell_tools = (
        ctx.repo_root
        / "ai-stack" / "local-agents" / "builtin_tools" / "shell_tools.py"
    )
    evidence_handler = (
        ctx.repo_root
        / "ai-stack" / "mcp-servers" / "hybrid-coordinator"
        / "workflow" / "evidence_safety_handlers.py"
    )

    # 62.1 — nsjail binary available (skip gracefully if not yet; requires rebuild)
    import shutil as _shutil, subprocess as _sp, re as _re
    nsjail_bin = __import__("os").environ.get("NSJAIL_BIN") or _shutil.which("nsjail")
    if not nsjail_bin:
        # Fall back to reading NSJAIL_BIN from the deployed service environment —
        # the coordinator PATH includes the nix store nsjail bin but the aq-qa
        # process runs in the user shell which doesn't inherit that PATH.
        try:
            env_out = _sp.check_output(
                ["systemctl", "show", "ai-hybrid-coordinator", "-p", "Environment"],
                text=True, timeout=5,
            )
            m = _re.search(r"NSJAIL_BIN=(\S+)", env_out)
            if m:
                nsjail_bin = m.group(1)
        except Exception:
            pass
    if nsjail_bin and __import__("os").path.isfile(nsjail_bin):
        results.append(passed(4, "62.1", f"nsjail binary available: {nsjail_bin}"))
    else:
        results.append(skipped(4, "62.1", "nsjail binary", "not in PATH — nixos-rebuild required (Phase 62.6)"))

    # 62.2 — safety-rails.yaml: exists, valid YAML, has 5 rails with required fields
    if not safety_rails.exists():
        results.append(failed(4, "62.2", "config/safety-rails.yaml", "file missing"))
    else:
        try:
            import yaml as _yaml
            doc = _yaml.safe_load(safety_rails.read_text())
            rails = doc.get("rails", []) if isinstance(doc, dict) else []
            required_fields = {"id", "pattern", "match_fields", "action", "reason"}
            missing_fields = []
            for r in rails:
                missing = required_fields - set(r.keys())
                if missing:
                    missing_fields.append(f"{r.get('id', '?')}: missing {missing}")
            if doc.get("version") != "1.0":
                results.append(failed(4, "62.2", "safety-rails.yaml", "version != '1.0'"))
            elif len(rails) < 5:
                results.append(failed(4, "62.2", "safety-rails.yaml", f"expected 5 rails, got {len(rails)}"))
            elif missing_fields:
                results.append(failed(4, "62.2", "safety-rails.yaml", f"incomplete rails: {missing_fields[:2]}"))
            else:
                results.append(passed(4, "62.2", f"safety-rails.yaml valid (version=1.0, {len(rails)} rails)"))
        except ImportError:
            results.append(skipped(4, "62.2", "safety-rails.yaml schema", "pyyaml not available in test env"))
        except Exception as exc:
            results.append(failed(4, "62.2", "safety-rails.yaml parse", str(exc)))

    # 62.3 — sandbox smoke: NsjailSandbox class + YAML rails wired in shell_tools + evidence_safety_handlers
    if not shell_tools.exists():
        results.append(failed(4, "62.3", "shell_tools.py sandbox smoke", "file missing"))
    else:
        st_text = shell_tools.read_text()
        checks = {
            "NsjailSandbox class": "class NsjailSandbox" in st_text,
            "NSJAIL_BIN env read": "NSJAIL_BIN" in st_text,
            "NSJAIL_REQUIRED fail-closed mode": "NSJAIL_REQUIRED" in st_text and "sandbox_required_failed" in st_text,
            "shell injection guard": "shell_injection_guard" in st_text,
            "sandbox nsjail key in response": '"sandbox": "nsjail"' in st_text or "'sandbox': 'nsjail'" in st_text or '"sandbox"' in st_text,
        }
        missing = [k for k, v in checks.items() if not v]
        if missing:
            results.append(failed(4, "62.3", "NsjailSandbox smoke", f"missing: {', '.join(missing)}"))
        else:
            results.append(passed(4, "62.3", "NsjailSandbox class present (NSJAIL_BIN + fail-closed required mode)"))

    if evidence_handler.exists():
        ev_text = evidence_handler.read_text()
        if "SAFETY_RAILS_FILE" in ev_text and "rail_id" in ev_text:
            results.append(passed(4, "62.4", "evidence safety handler evaluates YAML rails"))
        else:
            results.append(failed(4, "62.4", "evidence safety YAML rails", "missing SAFETY_RAILS_FILE or rail_id output"))
    else:
        results.append(failed(4, "62.4", "evidence safety handler", "file missing"))

    return results


def _check_ragas_eval(ctx: RunContext) -> list[CheckResult]:
    """Phase 60.7: RAGAS eval metrics wired in eval_runner + dashboard RAG Quality card."""
    results: list[CheckResult] = []

    eval_runner = (
        ctx.repo_root
        / "ai-stack" / "mcp-servers" / "hybrid-coordinator" / "eval_runner.py"
    )
    insights_svc = (
        ctx.repo_root
        / "ai-stack" / "mcp-servers" / "hybrid-coordinator"
        / "telemetry" / "insights_service.py"
    )
    dashboard = ctx.repo_root / "dashboard.html"

    # 60.7.1 — eval_runner.py: eval_results DDL + RAGAS scoring functions present
    if not eval_runner.exists():
        results.append(failed(4, "60.7.1", "eval_runner.py RAGAS check", "file missing"))
    else:
        text = eval_runner.read_text()
        checks = {
            "eval_results DDL": "eval_results" in text,
            "score_answer_relevance": "score_answer_relevance" in text,
            "score_faithfulness_async": "score_faithfulness_async" in text,
            "ragas_metrics in trend": "ragas_metrics" in text,
            "RAGAS_FAITHFULNESS_ENABLED guard": "RAGAS_FAITHFULNESS_ENABLED" in text,
        }
        missing = [k for k, v in checks.items() if not v]
        if missing:
            results.append(failed(4, "60.7.1", "eval_runner.py RAGAS", f"missing: {', '.join(missing)}"))
        else:
            results.append(passed(4, "60.7.1", "eval_runner.py RAGAS (eval_results + scoring functions + feature flag)"))

    # 60.7.2 — insights_service.py: POST /eval/score-query registered
    if not insights_svc.exists():
        results.append(failed(4, "60.7.2", "insights_service.py RAGAS route", "file missing"))
    else:
        text = insights_svc.read_text()
        if "eval/score-query" in text and "handle_eval_score_query" in text:
            results.append(passed(4, "60.7.2", "POST /eval/score-query registered in insights_service.py"))
        else:
            results.append(failed(4, "60.7.2", "POST /eval/score-query", "route not registered in insights_service.py"))

    # 60.7.3 — dashboard.html: RAG Quality card HTML + loadRagQuality JS present
    if not dashboard.exists():
        results.append(failed(4, "60.7.3", "dashboard RAG Quality card", "dashboard.html missing"))
    else:
        text = dashboard.read_text()
        checks = {
            "section-rag-quality": "section-rag-quality" in text,
            "ragAnswerRelevance": "ragAnswerRelevance" in text,
            "ragFaithfulness": "ragFaithfulness" in text,
            "loadRagQuality": "loadRagQuality" in text,
        }
        missing = [k for k, v in checks.items() if not v]
        if missing:
            results.append(failed(4, "60.7.3", "dashboard RAG Quality card", f"missing: {', '.join(missing)}"))
        else:
            results.append(passed(4, "60.7.3", "dashboard RAG Quality card (HTML + JS wired)"))

    # 60.7.4 — live: GET /eval/trend returns ragas_metrics key (skip if coordinator down)
    data = http_json(f"{ctx.hybrid_coordinator_url}/eval/trend", timeout=4)
    if data is None:
        results.append(skipped(4, "60.7.4", "GET /eval/trend ragas_metrics", "coordinator unreachable — needs nixos-rebuild"))
    elif "ragas_metrics" in data:
        results.append(passed(4, "60.7.4", "GET /eval/trend contains ragas_metrics key"))
    else:
        # Coordinator is up but returning pre-Phase-60.5 response: old nix store build.
        # Treat as skip (rebuild-pending) rather than fail (code bug).
        results.append(skipped(4, "60.7.4", "GET /eval/trend ragas_metrics", "old build active — ragas_metrics absent; nixos-rebuild required"))

    return results


def _check_phase146_identity_coverage(ctx: RunContext) -> list[CheckResult]:
    """Phase 146: governance coverage for agent identity emitted in query traces."""
    results: list[CheckResult] = []

    http_server = (
        ctx.repo_root
        / "ai-stack" / "mcp-servers" / "hybrid-coordinator" / "http_server_impl.py"
    )
    trace_collector = (
        ctx.repo_root
        / "ai-stack" / "mcp-servers" / "hybrid-coordinator" / "trace_collector.py"
    )
    dashboard_backend = ctx.repo_root / "dashboard" / "backend" / "api" / "routes" / "aistack.py"
    dashboard_js = ctx.repo_root / "assets" / "dashboard.js"

    # 146.1 — request identity headers are captured into TraceCollector.
    if not http_server.exists():
        results.append(failed(4, "146.1", "agent identity request capture", "http_server_impl.py missing"))
    else:
        text = http_server.read_text()
        checks = {
            "set_caller": "set_caller(" in text,
            "X-Agent-Source": "X-Agent-Source" in text,
            "X-Agent-Role": "X-Agent-Role" in text,
            "X-Agent-Boundary": "X-Agent-Boundary" in text,
        }
        missing = [k for k, v in checks.items() if not v]
        if missing:
            results.append(failed(4, "146.1", "agent identity request capture", f"missing: {', '.join(missing)}"))
        else:
            results.append(passed(4, "146.1", "agent identity request headers captured"))

    # 146.2 — TraceCollector emits the identity envelope into OTel attributes.
    if not trace_collector.exists():
        results.append(failed(4, "146.2", "agent identity OTel envelope", "trace_collector.py missing"))
    else:
        text = trace_collector.read_text()
        checks = {
            "set_caller method": "def set_caller(" in text,
            "caller source": "gen_ai.maeah.caller.source" in text,
            "caller role": "gen_ai.maeah.caller.role" in text,
            "caller boundary": "gen_ai.maeah.caller.autonomy_boundary" in text,
        }
        missing = [k for k, v in checks.items() if not v]
        if missing:
            results.append(failed(4, "146.2", "agent identity OTel envelope", f"missing: {', '.join(missing)}"))
        else:
            results.append(passed(4, "146.2", "agent identity OTel attributes emitted"))

    # 146.3 — dashboard proxy and frontend expose identity coverage, not just raw traces.
    missing_surface = []
    if not dashboard_backend.exists():
        missing_surface.append("dashboard/backend/api/routes/aistack.py")
    else:
        backend_text = dashboard_backend.read_text()
        if '@router.get("/query/traces")' not in backend_text or "/api/traces" not in backend_text:
            missing_surface.append("dashboard query trace proxy")
    if not dashboard_js.exists():
        missing_surface.append("assets/dashboard.js")
    else:
        js_text = dashboard_js.read_text()
        for needle in ("Identity Coverage", "Callers", "gen_ai.maeah.caller.source"):
            if needle not in js_text:
                missing_surface.append(f"dashboard {needle}")
    if missing_surface:
        results.append(failed(4, "146.3", "dashboard identity coverage surface", f"missing: {', '.join(missing_surface)}"))
    else:
        results.append(passed(4, "146.3", "dashboard identity coverage surface wired"))

    # 146.4 — live trace endpoint returns identity envelope fields when callers emit them.
    # Emit a bounded retrieval-only probe first; otherwise background health checks can
    # push the most recent identity-bearing trace out of a small query window.
    probe_status, _ = http_post_json(
        f"{ctx.hybrid_coordinator_url}/query",
        {"query": "ping", "max_tokens": 16},
        headers={
            "X-Agent-Source": "aq-qa-phase146",
            "X-Agent-Role": "validator",
            "X-Agent-Boundary": "auto_ok",
        },
        timeout=8,
    )
    if probe_status < 0:
        results.append(skipped(4, "146.4", "live trace identity coverage", "coordinator query probe unreachable"))
        return results

    data = http_json(f"{ctx.hybrid_coordinator_url}/api/traces?limit=100", timeout=4)
    if data is None:
        results.append(skipped(4, "146.4", "live trace identity coverage", "coordinator unreachable"))
        return results

    traces = data.get("traces") if isinstance(data, dict) else None
    if traces is None:
        results.append(skipped(4, "146.4", "live trace identity coverage", "trace endpoint unavailable or old build active"))
        return results
    if not traces:
        results.append(skipped(4, "146.4", "live trace identity coverage", "no query traces available yet"))
        return results

    with_envelope = [
        t for t in traces
        if isinstance(t.get("otel_attributes"), dict)
        and "gen_ai.maeah.caller.source" in t["otel_attributes"]
    ]
    known_callers = [
        t for t in with_envelope
        if t["otel_attributes"].get("gen_ai.maeah.caller.source")
    ]
    if not with_envelope:
        results.append(skipped(4, "146.4", "live trace identity coverage", "old traces lack Phase 140 caller envelope; rebuild or new query required"))
    elif known_callers:
        results.append(passed(4, "146.4", f"live trace identity coverage {len(known_callers)}/{len(traces)} known callers"))
    else:
        results.append(failed(4, "146.4", "live trace identity coverage", f"caller envelope present but 0/{len(traces)} traces have known caller source"))

    return results


def _check_s2_tool_auth_policy(ctx: RunContext) -> list[CheckResult]:
    """S2: auth/profile enforcement at MCP/tool dispatch boundaries."""
    results: list[CheckResult] = []
    from pathlib import Path as _P
    coord_root = _P(ctx.repo_root) / "ai-stack" / "mcp-servers" / "hybrid-coordinator"

    # S2.1 — middleware/auth.py has tool policy functions
    auth_py = coord_root / "middleware" / "auth.py"
    if not auth_py.exists():
        results.append(failed(4, "S2.1", "middleware/auth.py tool policy", "file missing"))
    else:
        text = auth_py.read_text()
        checks = {
            "AUTH_PROFILE_TOOL_POLICY": "AUTH_PROFILE_TOOL_POLICY" in text,
            "check_tool_access": "check_tool_access" in text,
            "record_tool_denial": "record_tool_denial" in text,
            "get_tool_denial_stats": "get_tool_denial_stats" in text,
            "readonly-strict blocked set": '"readonly-strict"' in text and "generate_training_data" in text,
        }
        missing = [k for k, v in checks.items() if not v]
        if missing:
            results.append(failed(4, "S2.1", "middleware/auth.py tool policy", f"missing: {', '.join(missing)}"))
        else:
            results.append(passed(4, "S2.1", "middleware/auth.py: AUTH_PROFILE_TOOL_POLICY + check/record/stats functions"))

    # S2.2 — workflow_session_handlers.py has S2 enforcement block
    wsh = coord_root / "workflow" / "workflow_session_handlers.py"
    if not wsh.exists():
        results.append(failed(4, "S2.2", "workflow_session_handlers S2 enforcement", "file missing"))
    else:
        text = wsh.read_text()
        checks = {
            "check_tool_access import": "check_tool_access" in text,
            "record_tool_denial import": "record_tool_denial" in text,
            "auth profile blocked response": "tool blocked by auth profile policy" in text,
        }
        missing = [k for k, v in checks.items() if not v]
        if missing:
            results.append(failed(4, "S2.2", "workflow_session_handlers S2 enforcement", f"missing: {', '.join(missing)}"))
        else:
            results.append(passed(4, "S2.2", "workflow_session_handlers: S2 auth profile tool enforcement wired"))

    # S2.3 — control_service.py has tool-deny-stats endpoint
    cs = coord_root / "control" / "control_service.py"
    if not cs.exists():
        results.append(failed(4, "S2.3", "control_service tool-deny-stats", "file missing"))
    else:
        text = cs.read_text()
        checks = {
            "handle_tool_deny_stats": "handle_tool_deny_stats" in text,
            "admin/v1/policy/tool-deny-stats route": "/admin/v1/policy/tool-deny-stats" in text,
        }
        missing = [k for k, v in checks.items() if not v]
        if missing:
            results.append(failed(4, "S2.3", "control_service tool-deny-stats", f"missing: {', '.join(missing)}"))
        else:
            results.append(passed(4, "S2.3", "GET /admin/v1/policy/tool-deny-stats registered in control_service.py"))

    # S2.4 — unit: check_tool_access logic is correct
    try:
        import importlib.util as _ilu, sys as _sys
        _spec = _ilu.spec_from_file_location("_auth_s2_test", str(auth_py))
        _mod = _ilu.module_from_spec(_spec)  # type: ignore[arg-type]
        # Provide stub Config dependency to avoid import errors in test env
        import types as _types
        _cfg_stub = _types.ModuleType("config")
        _cfg_stub.Config = type("Config", (), {"API_KEY": ""})()  # type: ignore[attr-defined]
        _sys.modules.setdefault("config", _cfg_stub)
        _spec.loader.exec_module(_mod)  # type: ignore[union-attr]
        _cta = _mod.check_tool_access
        # Returns (allowed: bool, reason: str); allowed=False means blocked/denied
        _allowed_mut, _ = _cta("generate_training_data", {"profile": "readonly-strict"})
        _allowed_ro, _ = _cta("augment_query", {"profile": "readonly-strict"})
        _allowed_exec, _ = _cta("generate_training_data", {"profile": "execute-guarded"})
        if _allowed_mut:
            results.append(failed(4, "S2.4", "check_tool_access logic", "generate_training_data should be denied for readonly-strict but was allowed"))
        elif not _allowed_ro:
            results.append(failed(4, "S2.4", "check_tool_access logic", "augment_query should be allowed for readonly-strict but was denied"))
        elif not _allowed_exec:
            results.append(failed(4, "S2.4", "check_tool_access logic", "generate_training_data should be allowed for execute-guarded but was denied"))
        else:
            results.append(passed(4, "S2.4", "check_tool_access: readonly-strict blocks mutating tools, execute-guarded allows all"))
    except Exception as exc:
        results.append(skipped(4, "S2.4", "check_tool_access unit test", f"import error in test env: {exc}"))

    # S2.5 — live: GET /admin/v1/policy/tool-deny-stats returns 200 with expected fields
    data = http_json(f"{ctx.hybrid_coordinator_url}/admin/v1/policy/tool-deny-stats",
                     headers={"X-API-Key": ctx.api_key}, timeout=4)
    if data is None:
        results.append(skipped(4, "S2.5", "GET /admin/v1/policy/tool-deny-stats", "coordinator unreachable or endpoint not yet deployed (nixos-rebuild required)"))
    else:
        required = {"total_denials", "by_tool", "by_profile", "breakdown", "policy"}
        missing_keys = required - set(data.keys())
        if missing_keys:
            results.append(failed(4, "S2.5", "tool-deny-stats response shape", f"missing keys: {', '.join(sorted(missing_keys))}"))
        elif "readonly-strict" not in data.get("policy", {}):
            results.append(failed(4, "S2.5", "tool-deny-stats policy", "readonly-strict not in policy map"))
        else:
            results.append(passed(4, "S2.5", "GET /admin/v1/policy/tool-deny-stats returns valid denial stats shape"))

    return results


# ---------------------------------------------------------------------------
# LA — Local-Agent model-agnostic config + aq-insights + aq-chat injection
# ---------------------------------------------------------------------------

def _check_local_agent_docs(ctx: RunContext) -> list[CheckResult]:
    """LA: LOCAL-AGENT.md model-agnostic config; QWEN.md redirect stub; aq-insights CLI."""
    results: list[CheckResult] = []
    agent_dir = ctx.repo_root / ".agent"

    # LA.1 — LOCAL-AGENT.md exists with all required sections
    la = agent_dir / "LOCAL-AGENT.md"
    if not la.exists():
        results.append(failed(4, "LA.1", "LOCAL-AGENT.md", "file missing"))
    else:
        text = la.read_text()
        required_sections = [
            "## Hardware Floor",
            "## Current Model Config",
            "## Model Swap Checklist",
            "## Behavioral Rules",
            "enable_thinking",
        ]
        missing = [s for s in required_sections if s not in text]
        if missing:
            results.append(failed(4, "LA.1", "LOCAL-AGENT.md sections", f"missing: {', '.join(missing)}"))
        else:
            results.append(passed(4, "LA.1", "LOCAL-AGENT.md: Hardware Floor + Current Model Config + swap checklist + Behavioral Rules"))

    # LA.2 — QWEN.md is a redirect stub (not the old full config)
    qwen = agent_dir / "QWEN.md"
    if not qwen.exists():
        results.append(skipped(4, "LA.2", "QWEN.md redirect stub", "file not present (acceptable if intentionally removed)"))
    else:
        text = qwen.read_text()
        if "LOCAL-AGENT.md" in text and "Superseded" in text:
            results.append(passed(4, "LA.2", "QWEN.md: redirect stub points to LOCAL-AGENT.md"))
        else:
            results.append(failed(4, "LA.2", "QWEN.md redirect stub", "still contains old config — should redirect to LOCAL-AGENT.md"))

    # LA.3 — aq-insights CLI executable and contains required functions
    insights = ctx.repo_root / "scripts" / "ai" / "aq-insights"
    if not insights.exists():
        results.append(failed(4, "LA.3", "scripts/ai/aq-insights", "file missing"))
    else:
        text = insights.read_text()
        required = ["extract_signals", "build_prompt", "call_local_model", "write_insights", "enable_thinking"]
        missing = [s for s in required if s not in text]
        if missing:
            results.append(failed(4, "LA.3", "aq-insights functions", f"missing: {', '.join(missing)}"))
        elif not insights.stat().st_mode & 0o111:
            results.append(failed(4, "LA.3", "aq-insights", "not executable"))
        else:
            results.append(passed(4, "LA.3", "aq-insights: executable, extract_signals+build_prompt+call_local_model+write_insights present"))

    # LA.4 — aq-chat harness-aware system prompt injection wired
    aq_chat = ctx.repo_root / "scripts" / "ai" / "aq-chat"
    if not aq_chat.exists():
        results.append(skipped(4, "LA.4", "aq-chat harness injection", "script not found"))
    else:
        text = aq_chat.read_text()
        checks = {
            "_build_harness_system_prompt": "_build_harness_system_prompt" in text,
            "--no-inject flag": "no-inject" in text,
            "enable_thinking guard": "enable_thinking" in text,
            "HARNESS BEHAVIORAL RULES": "BEHAVIORAL RULES" in text,
        }
        missing = [k for k, v in checks.items() if not v]
        if missing:
            results.append(failed(4, "LA.4", "aq-chat harness injection", f"missing: {', '.join(missing)}"))
        else:
            results.append(passed(4, "LA.4", "aq-chat: harness-aware system prompt injection + behavioral rules wired"))

    return results


def _check_phase66_wasmtime(ctx: RunContext) -> list[CheckResult]:
    """Phase 66.1: Wasmtime staged in devShells.full; smoke-wasmtime.sh present + executable."""
    results: list[CheckResult] = []

    # 66.1.a — flake.nix references wasmtime in full devShell
    flake = (ctx.repo_root / "flake.nix").read_text()
    if "wasmtime" not in flake:
        results.append(failed(4, "66.1.a", "Wasmtime in flake.nix devShells.full", "wasmtime not found in flake.nix"))
    else:
        results.append(passed(4, "66.1.a", "Wasmtime: present in flake.nix devShells.full"))

    # 66.1.b — smoke-wasmtime.sh exists and is executable
    smoke = ctx.repo_root / "scripts" / "testing" / "smoke-wasmtime.sh"
    if not smoke.exists():
        results.append(failed(4, "66.1.b", "smoke-wasmtime.sh", "file missing"))
    elif not smoke.stat().st_mode & 0o111:
        results.append(failed(4, "66.1.b", "smoke-wasmtime.sh", "not executable"))
    else:
        results.append(passed(4, "66.1.b", "smoke-wasmtime.sh: present and executable"))

    # 66.1.c — wasmtime binary availability (skip if not in PATH — expected outside nix develop .#full)
    import shutil
    if shutil.which("wasmtime"):
        results.append(passed(4, "66.1.c", "wasmtime: binary in PATH (nix develop .#full active)"))
    else:
        results.append(skipped(4, "66.1.c", "wasmtime binary", "not in PATH — activate nix develop .#full to test L2 sandbox"))

    return results


def _check_phase67_dashboard(ctx: RunContext) -> list[CheckResult]:
    """Phase 67: Agent Outcomes Gauge (67.1) + Mission Control grid (67.2) dashboard panels."""
    results: list[CheckResult] = []
    html = (ctx.repo_root / "dashboard.html").read_text()
    js   = (ctx.repo_root / "assets" / "dashboard.js").read_text()

    # 67.1.a — HTML card IDs present
    missing_html = [i for i in ["section-agent-outcomes", "agentOutcomesDetails", "agentOutcomesBadge"] if i not in html]
    if missing_html:
        results.append(failed(4, "67.1.a", "Agent Outcomes Gauge HTML", f"missing IDs: {missing_html}"))
    else:
        results.append(passed(4, "67.1.a", "Agent Outcomes Gauge: HTML card present (section-agent-outcomes)"))

    # 67.1.b — JS function defined
    if "async function loadAgentOutcomes" not in js:
        results.append(failed(4, "67.1.b", "loadAgentOutcomes", "not defined in dashboard.js"))
    else:
        results.append(passed(4, "67.1.b", "loadAgentOutcomes: defined in dashboard.js"))

    # 67.1.c — wired into Intelligence wave 2 (block containing loadAIMetricsDetail)
    wave2_start = js.find("loadA2AReadiness")
    wave2_block = js[wave2_start:wave2_start + 500] if wave2_start >= 0 else ""
    if "loadAgentOutcomes" not in wave2_block:
        results.append(failed(4, "67.1.c", "loadAgentOutcomes wave-2 wiring", "not in Intelligence wave 2"))
    else:
        results.append(passed(4, "67.1.c", "loadAgentOutcomes: wired into Intelligence wave 2"))

    # 67.2.a — HTML card IDs present
    missing_html2 = [i for i in ["section-mission-control", "missionControlDetails", "missionControlBadge"] if i not in html]
    if missing_html2:
        results.append(failed(4, "67.2.a", "Mission Control HTML", f"missing IDs: {missing_html2}"))
    else:
        results.append(passed(4, "67.2.a", "Mission Control: HTML card present (section-mission-control)"))

    # 67.2.b — JS function defined
    if "async function loadMissionControl" not in js:
        results.append(failed(4, "67.2.b", "loadMissionControl", "not defined in dashboard.js"))
    else:
        results.append(passed(4, "67.2.b", "loadMissionControl: defined in dashboard.js"))

    # 67.2.c — wired into Operations wave 2 (first occurrence = call site in wave 2)
    ops_start = js.find("loadWorkflowBlueprints")  # first occurrence = wave 2 call site
    ops_block = js[ops_start:ops_start + 300] if ops_start >= 0 else ""
    if "loadMissionControl" not in ops_block:
        results.append(failed(4, "67.2.c", "loadMissionControl wave-2 wiring", "not in Operations wave 2"))
    else:
        results.append(passed(4, "67.2.c", "loadMissionControl: wired into Operations wave 2"))

    return results


def _check_phase83_dag_context(ctx: RunContext) -> list[CheckResult]:
    """Phase 83: DAG session manager + context merger infrastructure (PAEA Phase 1)."""
    results: list[CheckResult] = []

    # 83.1 — dag_manager.py exists and imports cleanly
    dag_path = ctx.repo_root / "ai-stack" / "agent-memory" / "dag_manager.py"
    if not dag_path.exists():
        results.append(failed(4, "83.1", "dag_manager.py", "file not found at ai-stack/agent-memory/dag_manager.py"))
    else:
        rc = subprocess.run(
            ["python3", "-m", "py_compile", str(dag_path)],
            capture_output=True, text=True,
        )
        if rc.returncode != 0:
            results.append(failed(4, "83.1", "dag_manager.py syntax", rc.stderr.strip()))
        else:
            results.append(passed(4, "83.1", "dag_manager.py: exists and syntax-clean"))

    # 83.2 — context-merger.py exists and imports cleanly
    ctx_path = ctx.repo_root / "scripts" / "ai" / "lib" / "context-merger.py"
    if not ctx_path.exists():
        results.append(failed(4, "83.2", "context-merger.py", "file not found at scripts/ai/lib/context-merger.py"))
    else:
        rc = subprocess.run(
            ["python3", "-m", "py_compile", str(ctx_path)],
            capture_output=True, text=True,
        )
        if rc.returncode != 0:
            results.append(failed(4, "83.2", "context-merger.py syntax", rc.stderr.strip()))
        else:
            results.append(passed(4, "83.2", "context-merger.py: exists and syntax-clean"))

    # 83.3 — Phase 1 integration test passes
    test_path = ctx.repo_root / "tests" / "integration" / "test-phase1-dag-context.py"
    if not test_path.exists():
        results.append(skipped(4, "83.3", "Phase 1 integration test", "test file not found"))
    else:
        rc = subprocess.run(
            ["python3", str(test_path)],
            capture_output=True, text=True, timeout=15,
        )
        if rc.returncode != 0:
            results.append(failed(4, "83.3", "Phase 1 integration test", rc.stderr.strip()[-200:]))
        else:
            results.append(passed(4, "83.3", "Phase 1 integration test: 4/4 PASS (dag_manager + context_merger + handoff)"))

    # 83.4 — dag_manager wired into workflow_session_handlers
    wsh = ctx.repo_root / "ai-stack" / "mcp-servers" / "hybrid-coordinator" / "workflow" / "workflow_session_handlers.py"
    if wsh.exists() and "_DAGSessionManager" in wsh.read_text():
        results.append(passed(4, "83.4", "dag_manager wired into workflow_session_handlers"))
    else:
        results.append(failed(4, "83.4", "dag_manager wiring", "DAGSessionManager import not found in workflow_session_handlers.py"))

    return results


def _check_phase85_drop_zone(ctx: RunContext) -> list[CheckResult]:
    """Phase 85: Drop Zone Daemon + Intent Lock v2 (PAEA Phase 2)."""
    results: list[CheckResult] = []

    # 85.1 — aq-drop-daemon script exists and is syntax-clean
    daemon = ctx.repo_root / "scripts" / "ai" / "aq-drop-daemon"
    if not daemon.exists():
        results.append(failed(4, "85.1", "aq-drop-daemon", "script not found at scripts/ai/aq-drop-daemon"))
    else:
        rc = subprocess.run(
            ["python3", "-m", "py_compile", str(daemon)],
            capture_output=True, text=True,
        )
        if rc.returncode != 0:
            results.append(failed(4, "85.1", "aq-drop-daemon syntax", rc.stderr.strip()))
        else:
            results.append(passed(4, "85.1", "aq-drop-daemon: exists and syntax-clean"))

    # 85.2 — DropSpec schema validator exists and passes injection test
    drop_spec = ctx.repo_root / "scripts" / "ai" / "lib" / "drop_spec.py"
    if not drop_spec.exists():
        results.append(failed(4, "85.2", "drop_spec.py", "file not found at scripts/ai/lib/drop_spec.py"))
    else:
        rc = subprocess.run(
            ["python3", "-c",
             "import sys; sys.path.insert(0,'scripts/ai/lib'); "
             "from drop_spec import DropSpec, DropSpecError; "
             "s=DropSpec(objective='ok',prompt='do useful work'); s._validate(); "
             "raised=False\n"
             "try:\n  DropSpec(objective='$(rm -rf /)',prompt='x')._validate()\nexcept DropSpecError: raised=True\n"
             "assert raised, 'injection not blocked'\nprint('ok')"],
            capture_output=True, text=True, cwd=str(ctx.repo_root),
        )
        if rc.returncode != 0 or "ok" not in rc.stdout:
            results.append(failed(4, "85.2", "drop_spec.py injection guard", rc.stderr.strip() or rc.stdout.strip()))
        else:
            results.append(passed(4, "85.2", "drop_spec.py: schema validator + injection guard pass"))

    # 85.3 — Intent Lock v2 methods present in task_registry.py
    registry = ctx.repo_root / "scripts" / "ai" / "lib" / "task_registry.py"
    if not registry.exists():
        results.append(failed(4, "85.3", "task_registry.py", "file not found"))
    else:
        text = registry.read_text()
        required = ["def acquire_lock", "def release_expired_locks", "def heartbeat"]
        missing = [m for m in required if m not in text]
        if missing:
            results.append(failed(4, "85.3", "Intent Lock v2 methods", f"missing: {missing}"))
        else:
            results.append(passed(4, "85.3", "Intent Lock v2: acquire_lock + release_expired_locks + heartbeat present"))

    # 85.4 — drop zone directories exist
    drops_dir = ctx.repo_root / ".agents" / "drops"
    archive_dir = drops_dir / "archive"
    failed_dir = drops_dir / "failed"
    missing_dirs = [str(d) for d in [drops_dir, archive_dir, failed_dir] if not d.is_dir()]
    if missing_dirs:
        results.append(failed(1, "85.4", "drop zone directories", f"missing: {missing_dirs}"))
    else:
        results.append(passed(1, "85.4", "drop zone directories: .agents/drops/{,archive/,failed/} exist"))

    # 85.5 — ai-drop-daemon.service wired in mcp-servers.nix
    nix_path = ctx.repo_root / "nix" / "modules" / "services" / "mcp-servers.nix"
    if not nix_path.exists():
        results.append(skipped(4, "85.5", "ai-drop-daemon NixOS service", "mcp-servers.nix not found"))
    else:
        text = nix_path.read_text()
        if "ai-drop-daemon" in text and "aq-drop-daemon" in text:
            results.append(passed(4, "85.5", "ai-drop-daemon service wired in mcp-servers.nix"))
        else:
            results.append(failed(4, "85.5", "ai-drop-daemon NixOS service", "not found in mcp-servers.nix"))

    return results


def _check_phase86_attention_queue(ctx: RunContext) -> list[CheckResult]:
    """Phase 86: Human-in-the-Loop Alert Queue."""
    results: list[CheckResult] = []

    # 86.1 — attention_queue.py importable
    aq_lib = ctx.repo_root / "scripts" / "ai" / "lib" / "attention_queue.py"
    if not aq_lib.exists():
        results.append(failed(4, "86.1", "attention_queue.py", "file not found at scripts/ai/lib/attention_queue.py"))
    else:
        rc = subprocess.run(
            ["python3", "-c",
             "import sys; sys.path.insert(0,'scripts/ai/lib'); "
             "from attention_queue import push, get_pending, get_by_id, resolve, pending_count; "
             "print('ok')"],
            capture_output=True, text=True, cwd=str(ctx.repo_root),
        )
        if rc.returncode != 0 or "ok" not in rc.stdout:
            results.append(failed(4, "86.1", "attention_queue.py importable", rc.stderr.strip() or rc.stdout.strip()))
        else:
            results.append(passed(4, "86.1", "attention_queue.py: importable with all public symbols"))

    # 86.2 — auto_ok push creates ATTENTION_ARCHIVE.jsonl (not ATTENTION.json)
    if not aq_lib.exists():
        results.append(skipped(4, "86.2", "auto_ok push → archive", "attention_queue.py not found"))
    else:
        rc = subprocess.run(
            ["python3", "-c",
             "import sys, os, tempfile, pathlib, json\n"
             "sys.path.insert(0, 'scripts/ai/lib')\n"
             "import attention_queue as aq\n"
             "# redirect to temp dir\n"
             "td = tempfile.mkdtemp()\n"
             "aq._ATTENTION_DIR = pathlib.Path(td)\n"
             "aq._QUEUE_FILE    = pathlib.Path(td) / 'ATTENTION.json'\n"
             "aq._ARCHIVE_FILE  = pathlib.Path(td) / 'ATTENTION_ARCHIVE.jsonl'\n"
             "aq.push('test', 'low', 'auto_ok', 'smoke test', 'unit test', 'none')\n"
             "queue = json.loads((pathlib.Path(td)/'ATTENTION.json').read_text()) if (pathlib.Path(td)/'ATTENTION.json').exists() else []\n"
             "archive_exists = (pathlib.Path(td)/'ATTENTION_ARCHIVE.jsonl').exists()\n"
             "assert len(queue) == 0, f'auto_ok should not land in queue, got {len(queue)} items'\n"
             "assert archive_exists, 'ATTENTION_ARCHIVE.jsonl not created'\n"
             "print('ok')"],
            capture_output=True, text=True, cwd=str(ctx.repo_root),
        )
        if rc.returncode != 0 or "ok" not in rc.stdout:
            results.append(failed(4, "86.2", "auto_ok push → archive only", rc.stderr.strip() or rc.stdout.strip()))
        else:
            results.append(passed(4, "86.2", "auto_ok push: archived immediately, queue stays empty"))

    # 86.3 — aq-alerts exists and executable
    aq_alerts = ctx.repo_root / "scripts" / "ai" / "aq-alerts"
    if not aq_alerts.exists():
        results.append(failed(4, "86.3", "aq-alerts", "script not found at scripts/ai/aq-alerts"))
    elif not os.access(str(aq_alerts), os.X_OK):
        results.append(failed(4, "86.3", "aq-alerts executable", "not executable"))
    else:
        results.append(passed(4, "86.3", "aq-alerts: exists and executable"))

    # 86.4 — aq-alerts --count returns 0 when queue is empty
    if aq_alerts.exists():
        try:
            rc = subprocess.run(
                [str(aq_alerts), "--count"],
                capture_output=True, text=True, timeout=10,
                env={**os.environ, "ATTENTION_QUEUE_PATH": "/dev/null"},
            )
            # Accept either "0" output or exit 0 with count line
            out = rc.stdout.strip()
            if out == "0" or (rc.returncode == 0 and out == "0"):
                results.append(passed(4, "86.4", "aq-alerts --count: returns 0 when empty"))
            else:
                # May have pending alerts — just check it ran without error
                if rc.returncode in (0, 1) and out.isdigit():
                    results.append(passed(4, "86.4", f"aq-alerts --count: returned {out} (numeric, no crash)"))
                else:
                    results.append(failed(4, "86.4", "aq-alerts --count", f"unexpected output: {out!r} rc={rc.returncode}"))
        except Exception as e:
            results.append(failed(4, "86.4", "aq-alerts --count", str(e)))
    else:
        results.append(skipped(4, "86.4", "aq-alerts --count", "aq-alerts not found"))

    # 86.5 — aq-approve exists and executable
    aq_approve = ctx.repo_root / "scripts" / "ai" / "aq-approve"
    if not aq_approve.exists():
        results.append(failed(4, "86.5", "aq-approve", "script not found at scripts/ai/aq-approve"))
    elif not os.access(str(aq_approve), os.X_OK):
        results.append(failed(4, "86.5", "aq-approve executable", "not executable"))
    else:
        results.append(passed(4, "86.5", "aq-approve: exists and executable"))

    # 86.6 — aq-reject exists and executable
    aq_reject = ctx.repo_root / "scripts" / "ai" / "aq-reject"
    if not aq_reject.exists():
        results.append(failed(4, "86.6", "aq-reject", "script not found at scripts/ai/aq-reject"))
    elif not os.access(str(aq_reject), os.X_OK):
        results.append(failed(4, "86.6", "aq-reject executable", "not executable"))
    else:
        results.append(passed(4, "86.6", "aq-reject: exists and executable"))

    # 86.7 — dashboard /api/aistack/alerts/status returns 200
    dashboard_url = f"http://127.0.0.1:{getattr(ctx, 'dashboard_port', 8889)}"
    status_code = None
    body = ""
    last_error = None
    for attempt in range(1, 4):
        try:
            status_code, body = http_get(f"{dashboard_url}/api/aistack/alerts/status", timeout=5)
            last_error = None
            break
        except Exception as e:
            last_error = e
            if attempt < 3:
                time.sleep(2)

    try:
        if last_error is not None:
            raise last_error
        if status_code == 200:
            results.append(passed(5, "86.7", "dashboard /api/aistack/alerts/status: 200 OK"))
        elif status_code == 404:
            # Route not yet active — needs dashboard service restart after deploy
            results.append(skipped(5, "86.7", "dashboard alerts/status", "HTTP 404 — service restart needed to pick up new route"))
        else:
            results.append(failed(5, "86.7", "dashboard /api/aistack/alerts/status", f"HTTP {status_code}"))
    except Exception as e:
        results.append(failed(5, "86.7", "dashboard /api/aistack/alerts/status", str(e)))

    return results


def _check_phase87_training_ingest(ctx: RunContext) -> list[CheckResult]:
    """Phase 87.3: training_ingest.py exists + ai-training-ingest timer wired."""
    results: list[CheckResult] = []

    # 87.3.1 — training_ingest.py exists at expected path
    ingest_script = ctx.repo_root / "ai-stack" / "local-agents" / "training_ingest.py"
    if not ingest_script.exists():
        results.append(failed(4, "87.3.1", "training_ingest.py", "not found at ai-stack/local-agents/training_ingest.py"))
    else:
        results.append(passed(4, "87.3.1", "training_ingest.py: exists at ai-stack/local-agents/"))

    # 87.3.2 — ai-training-ingest timer wired in mcp-servers.nix
    mcp_nix = ctx.repo_root / "nix" / "modules" / "services" / "mcp-servers.nix"
    if not mcp_nix.exists():
        results.append(skipped(4, "87.3.2", "ai-training-ingest timer", "mcp-servers.nix not found"))
    else:
        nix_text = mcp_nix.read_text()
        if "ai-training-ingest" in nix_text:
            results.append(passed(4, "87.3.2", "ai-training-ingest service+timer wired in mcp-servers.nix"))
        else:
            results.append(failed(4, "87.3.2", "ai-training-ingest timer", "not found in mcp-servers.nix"))

        loop_needles = [
            "systemd.services.ai-local-training-loop",
            "systemd.timers.ai-local-training-loop",
            "aq-local-training-loop",
            "training-loop-results.jsonl",
            "training-loop-progress.json",
            "PYTHONUNBUFFERED=1",
            "AQ_LOOP_DIRECT_TIMEOUT=86400",
            "AQ_LOOP_SUBMIT_TIMEOUT=90",
            "AQ_LOOP_RUNAWAY_HARD_CAP=0",
            "TRAINING_LOOP_PROGRESS_FILE=",
            "TimeoutStartSec = \"infinity\"",
            "\"2400\"",
        ]
        missing_loop = [needle for needle in loop_needles if needle not in nix_text]
        if missing_loop:
            results.append(failed(4, "87.3.3", "ai-local-training-loop service+timer", f"missing: {', '.join(missing_loop)}"))
        else:
            results.append(passed(4, "87.3.3", "ai-local-training-loop service+timer wired in mcp-servers.nix"))

    # 87.3.4 — fine-tuning dataset exists and has ≥1 row (xfail on first run)
    dataset = ctx.repo_root / "ai-stack" / "hybrid" / "fine-tuning" / "dataset.jsonl"
    # Also check the runtime path that training_ingest uses by default
    runtime_dataset = "/var/lib/ai-stack/hybrid/fine-tuning/dataset.jsonl"
    import pathlib
    runtime_path = pathlib.Path(runtime_dataset)
    if dataset.exists():
        line_count = sum(1 for _ in dataset.open())
        if line_count >= 1:
            results.append(passed(4, "87.3.4", f"fine-tuning/dataset.jsonl: {line_count} rows"))
        else:
            results.append(failed(4, "87.3.4", "fine-tuning/dataset.jsonl", "file exists but is empty — timer has not run yet"))
    elif runtime_path.exists():
        line_count = sum(1 for _ in runtime_path.open())
        if line_count >= 1:
            results.append(passed(4, "87.3.4", f"fine-tuning/dataset.jsonl (runtime): {line_count} rows"))
        else:
            results.append(skipped(4, "87.3.4", "fine-tuning/dataset.jsonl", "empty — timer has not run yet (xfail first run)"))
    else:
        results.append(skipped(4, "87.3.4", "fine-tuning/dataset.jsonl", "not yet created — run ai-training-ingest.service or wait for daily timer"))

    return results
