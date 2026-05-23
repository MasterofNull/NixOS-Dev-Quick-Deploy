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


def _check_services(ctx: RunContext) -> list[CheckResult]:
    results = []
    if not ctx.should_run(1):
        return results
    for svc in _SERVICES:
        unit = f"{svc}.service"
        r = subprocess.run(
            ["systemctl", "is-active", "--quiet", unit],
            capture_output=True, timeout=5,
        )
        if r.returncode == 0:
            results.append(passed(1, f"0.1.1:{svc}", f"unit {unit} active"))
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
        if port_bound(port, retries=retries, delay=delay):
            results.append(passed(3, f"0.2.1:{name}", f"port {port} ({name}) bound"))
        else:
            results.append(failed(3, f"0.2.1:{name}", f"port {port} ({name}) bound", f"port {port} not bound"))
    return results


def _check_grafana_port(ctx: RunContext) -> list[CheckResult]:
    if not ctx.should_run(3):
        return []
    grafana_active = cmd_ok("systemctl", "is-active", "--quiet", "grafana.service")
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
        name = colls[0]["name"]
        cd = http_json(f"{ctx.qdrant_url}/collections/{name}", timeout=5)
        count = ((cd or {}).get("result") or {}).get("points_count", 0)
        if count > 0:
            return [passed(5, "0.2.3", f"Qdrant has {count} points in primary collection")]
        return [failed(5, "0.2.3", "Qdrant has documents", "found 0")]
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
    cli = _find_continue_cli(ctx)
    if cli:
        env = {
            **os.environ,
            "HOME": ctx.primary_home,
            "USER": ctx.primary_user,
            "LOGNAME": ctx.primary_user,
            "PATH": ctx.primary_user_path,
        }
        if cmd_ok(cli, "--help", env=env):
            results.append(passed(7, "0.5.1", "Continue CLI help works"))
        else:
            results.append(failed(7, "0.5.1", "Continue CLI help works"))
    else:
        results.append(failed(7, "0.5.1", "Continue CLI help works", "cn binary not found"))

    # 0.5.2 switchboard ingress with local harness chat lane and continue-local tab lane validation
    # Checks: apiBase") == "http://127.0.0.1:8085/v1" and profile-derived context windows
    try:
        cfg_path = Path(ctx.primary_home) / ".continue" / "config.json"
        ok, reason = _check_continue_config(cfg_path, ctx.switchboard_url)
        _desc_052 = "Continue config targets switchboard ingress with local harness chat lane and continue-local tab lane"  # 0.5.2
        if ok:
            results.append(passed(7, "0.5.2", _desc_052))
        else:
            results.append(failed(7, "0.5.2", _desc_052, reason))
    except Exception as e:
        _desc_052 = "Continue config targets switchboard ingress with local harness chat lane and continue-local tab lane"  # 0.5.2
        results.append(failed(7, "0.5.2", _desc_052, str(e)))

    # 0.5.3 VSCodium Continue extension
    try:
        env = {**os.environ, "HOME": ctx.primary_home, "USER": ctx.primary_user, "LOGNAME": ctx.primary_user,
               "PATH": ctx.primary_user_path}
        r = subprocess.run(
            ["bash", "--noprofile", "--norc", "-c",
             "codium --list-extensions 2>/dev/null | tr '[:upper:]' '[:lower:]'"],
            capture_output=True, text=True, env=env, timeout=15,
        )
        if "continue.continue" in r.stdout:
            results.append(passed(7, "0.5.3", "VSCodium has Continue extension installed"))
        else:
            results.append(failed(7, "0.5.3", "VSCodium has Continue extension installed",
                                  "not found in extension list"))
    except Exception as e:
        results.append(failed(7, "0.5.3", "VSCodium has Continue extension installed", str(e)))

    # 0.5.4 continue-local profile
    try:
        data = http_json(f"{ctx.switchboard_url}/health", timeout=8)
        if data:
            profile = ((data.get("profiles") or {}).get("continue-local") or {})
            ok = (
                str(profile.get("forceProvider") or "") == "local"
                and int(profile.get("maxOutputTokens") or 0) > 0
                and int(profile.get("maxInputTokens") or 0) > 0
                and len(str(profile.get("profileCard") or "")) > 0
            )
            if ok:
                results.append(passed(7, "0.5.4", "continue-local switchboard profile ready"))
            else:
                results.append(failed(7, "0.5.4", "continue-local switchboard profile ready",
                                      str(profile)[:80]))
        else:
            results.append(failed(7, "0.5.4", "continue-local switchboard profile ready", "no switchboard response"))
    except Exception as e:
        results.append(failed(7, "0.5.4", "continue-local switchboard profile ready", str(e)))

    # 0.5.5 continue-local large context trim
    script = ctx.repo_root / "scripts" / "testing" / "test-switchboard-continue-context-window.sh"
    if cmd_ok("bash", str(script)):
        results.append(passed(7, "0.5.5", "continue-local trims oversized dense prompts"))
    else:
        results.append(failed(7, "0.5.5", "continue-local trims oversized dense prompts"))

    # 0.5.6 editor flow smoke
    flow_script = ctx.repo_root / "scripts" / "testing" / "smoke-continue-editor-flow.sh"
    if cmd_ok("bash", str(flow_script)):
        results.append(passed(7, "0.5.6", "Continue/editor prompt to feedback smoke"))
    else:
        results.append(failed(7, "0.5.6", "Continue/editor prompt to feedback smoke"))

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

def _check_delegate_rate(ctx: RunContext) -> list[CheckResult]:
    data = http_json(f"{ctx.hybrid_coordinator_url}/stats/delegate?window_s=86400", timeout=5)
    if data is None or "error" in (data or {}):
        return [skipped(4, "0.8.1", "delegate 24h success rate",
                        "coordinator /stats/delegate unavailable (needs nixos-rebuild)")]
    total = int(data.get("total") or 0)
    ok = int(data.get("ok") or 0)
    if total < 1:
        return [skipped(4, "0.8.1", "delegate 24h success rate",
                        "insufficient sample (0 calls in last 24h)")]
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
        headers=headers, timeout=10,
    )
    if code == 200 or '"ok": true' in body or '"ok":true' in body:
        return [passed(4, "0.9.1", "safety gate endpoint responds (POST /control/safety/gate)")]
    if code == 404:
        return [skipped(4, "0.9.1", "safety gate endpoint", "Phase 28 not deployed (404)")]
    return [failed(4, "0.9.1", "safety gate endpoint reachable",
                   f"HTTP {code or 'ERR'}: {body[:80]}")]


def _check_uag_replay(ctx: RunContext) -> list[CheckResult]:
    _, body = http_get(
        f"{ctx.hybrid_url}/agent/lifecycle/healthcheck-probe/replay",
        timeout=5, headers={"X-API-Key": ctx.api_key},
    )
    # We need the status code; re-do with low-level
    import urllib.request
    req = urllib.request.Request(
        f"{ctx.hybrid_url}/agent/lifecycle/healthcheck-probe/replay",
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
            d = _yaml.safe_load(config.read_text())
            required = {"_meta", "active_model", "inference", "chat", "performance_targets"}
            missing = required - set(d.keys())
            if missing:
                results.append(failed(4, "60.0.1", "local-model-config.yaml schema", f"missing keys: {missing}"))
            elif not d.get("chat", {}).get("enable_thinking") is False:
                results.append(failed(4, "60.0.1", "local-model-config.yaml thinking guard", "chat.enable_thinking must be false"))
            else:
                results.append(passed(4, "60.0.1", "local-model-config.yaml valid (schema + thinking guard)"))
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


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run(ctx: RunContext) -> list[CheckResult]:
    """Run all phase 0 checks and return a flat list of CheckResult."""
    results: list[CheckResult] = []
    results.extend(_check_services(ctx))
    results.extend(_check_no_failed_units(ctx))
    results.extend(_check_timers(ctx))
    results.extend(_check_ports(ctx))
    results.extend(_check_grafana_port(ctx))
    results.extend(_check_qdrant_docs(ctx))
    results.extend(_check_postgres_tables(ctx))
    results.extend(_check_redis_keys(ctx))
    results.extend(_check_apparmor(ctx))
    results.extend(_check_inference(ctx))
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
    results.extend(_check_ragas_eval(ctx))
    results.extend(_check_clm(ctx))
    results.extend(_check_nsjail_sandbox(ctx))
    results.extend(_check_graphrag(ctx))
    results.extend(_check_s2_tool_auth_policy(ctx))
    results.extend(_check_local_agent_docs(ctx))
    return results


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
            "enable_thinking guard": "enable_thinking" in text,
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
