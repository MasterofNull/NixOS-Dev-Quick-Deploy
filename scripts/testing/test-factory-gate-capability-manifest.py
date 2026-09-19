#!/usr/bin/env python3
"""Focused proof for the F1/F2 capability-manifest fix.

Audit: .agents/plans/factory-gate-templates/TEMPLATE-SHARED-ENGINE-AUDIT-20260918.md

  F1 (no capability manifest in the payload): a fresh install must render
     .factory/capability-manifest.json declaring the shared-engine endpoints
     + a per-capability state (available | unavailable | unauthorized).
  F2 (settings.json.tmpl hardcoded host URLs with no placeholder/fallback):
     templates/agentic-workflow/.claude/settings.json.tmpl must resolve from
     the target ENV (HYBRID_URL/AIDB_URL), never bake a dead 127.0.0.1 literal,
     and declare a typed "unavailable" state instead when the env is unset.

Covers:
  (a) fresh install renders a capability manifest with engine endpoints + state
  (b) engine env unset -> manifest + settings.json declare UNAVAILABLE, never
      a hardcoded 127.0.0.1 dead URL
  (c) engine env set -> both resolve to that endpoint
  (d) no host secrets/credentials are copied (installer never touches
      /run/secrets; only a conventional file *path* is templated, unchanged
      by this fix and never populated with a live secret value)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AQD = ROOT / "scripts/ai/aqd"
SETTINGS_TMPL = ROOT / "templates/agentic-workflow/.claude/settings.json.tmpl"


def run(*command: str, cwd: Path | None = None, expected: int | None = 0,
        extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    # Hermetic: strip GIT_* routing vars and any HYBRID_URL/AIDB_URL the
    # calling shell (tier0/aq-qa coordinator env) may already export, so the
    # "unset" fixtures below are not silently polluted by the outer harness.
    environment = {key: value for key, value in os.environ.items()
                   if key not in {"GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
                                   "GIT_ALTERNATE_OBJECT_DIRECTORIES", "HYBRID_URL", "AIDB_URL"}}
    if extra_env:
        environment.update(extra_env)
    result = subprocess.run(command, cwd=cwd, env=environment, text=True, capture_output=True, check=False)
    if expected is not None and (result.returncode == 0) != (expected == 0):
        raise AssertionError(f"unexpected exit {result.returncode}: {' '.join(command)}\n{result.stdout}\n{result.stderr}")
    return result


def project_init(target: Path, name: str, extra_env: dict[str, str] | None = None) -> None:
    run(str(AQD), "workflows", "project-init", "--target", str(target), "--name", name,
        "--goal", "prove capability manifest", "--stack", "generic", "--owner", "test",
        cwd=ROOT, extra_env=extra_env)


def main() -> int:
    evidence = {
        "template_no_hardcoded_host_literal": False,
        "fresh_install_renders_manifest": False,
        "unset_env_declares_unavailable_no_dead_url": False,
        "set_env_resolves_to_endpoint": False,
        "no_secrets_copied": False,
        "manifest_refreshed_on_upgrade": False,
    }

    # -- Static check: the source template itself carries no dead 127.0.0.1
    #    literal any more (regression guard against reintroducing F2). ------
    template_text = SETTINGS_TMPL.read_text(encoding="utf-8")
    assert "127.0.0.1" not in template_text, "settings.json.tmpl still hardcodes a host literal"
    assert "{{HYBRID_COORDINATOR_ENDPOINT}}" in template_text
    assert "{{AIDB_ENDPOINT}}" in template_text
    evidence["template_no_hardcoded_host_literal"] = True

    with tempfile.TemporaryDirectory(prefix="factory capability manifest fixture ") as temporary:
        work = Path(temporary)

        # -- (a) + (b): fresh install, engine env unset -----------------
        unset_target = work / "unset target"
        project_init(unset_target, "unset target")

        manifest_path = unset_target / ".factory/capability-manifest.json"
        assert manifest_path.is_file(), "F1: no capability manifest rendered"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        caps = manifest["capabilities"]
        assert caps["hybrid_coordinator"]["state"] == "unavailable"
        assert caps["aidb"]["state"] == "unavailable"
        assert caps["hybrid_coordinator"]["endpoint"] == ""
        assert caps["aidb"]["endpoint"] == ""
        evidence["fresh_install_renders_manifest"] = True

        settings_path = unset_target / ".claude/settings.json"
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        env_block = settings["mcpServers"]["ai-stack-harness"]["env"]
        assert env_block["HYBRID_URL"] == "" and "127.0.0.1" not in env_block["HYBRID_URL"]
        assert env_block["AIDB_URL"] == "" and "127.0.0.1" not in env_block["AIDB_URL"]
        assert settings["hints"]["enabled"] is False
        assert "127.0.0.1" not in settings["hints"]["endpoint"]
        assert not any("127.0.0.1" in entry for entry in settings["permissions"]["allow"])
        # Check the raw file text, not json.dumps() (compact-JSON re-encoding
        # naturally produces adjacent closing braces like "}}}" that are not
        # unresolved placeholders).
        assert "{{" not in settings_path.read_text(encoding="utf-8"), "unresolved placeholder shipped in rendered settings.json"
        evidence["unset_env_declares_unavailable_no_dead_url"] = True

        # -- (c): fresh install, engine env set --------------------------
        set_target = work / "set target"
        engine_env = {"HYBRID_URL": "http://coordinator.example.internal:8003",
                      "AIDB_URL": "http://aidb.example.internal:8002"}
        project_init(set_target, "set target", extra_env=engine_env)

        set_manifest = json.loads((set_target / ".factory/capability-manifest.json").read_text(encoding="utf-8"))
        set_caps = set_manifest["capabilities"]
        assert set_caps["hybrid_coordinator"] == {
            "kind": "shared_engine_transport", "state": "available",
            "endpoint": "http://coordinator.example.internal:8003", "source": "env:HYBRID_URL"}
        assert set_caps["aidb"]["endpoint"] == "http://aidb.example.internal:8002"
        assert set_caps["aidb"]["state"] == "available"

        set_settings = json.loads((set_target / ".claude/settings.json").read_text(encoding="utf-8"))
        set_env_block = set_settings["mcpServers"]["ai-stack-harness"]["env"]
        assert set_env_block["HYBRID_URL"] == "http://coordinator.example.internal:8003"
        assert set_env_block["AIDB_URL"] == "http://aidb.example.internal:8002"
        assert set_settings["hints"]["enabled"] is True
        assert set_settings["hints"]["endpoint"] == "http://coordinator.example.internal:8003/hints"
        evidence["set_env_resolves_to_endpoint"] = True

        # -- (d): no host secrets/credentials copied ----------------------
        # The installer never reads /run/secrets; the API_KEY_FILE fields are
        # an unchanged conventional path template, never a live secret value.
        assert "/run/secrets" not in json.dumps(manifest)
        # HYBRID_API_KEY_FILE/AIDB_API_KEY_FILE are a conventional *path*
        # string, unchanged by this fix; this run's environment may or may
        # not have real secrets mounted at that host path, so the meaningful
        # assertion is that the installer never dereferences/embeds file
        # content -- only a static path -- checked via the byte-content scan
        # below (no key material substrings in anything rendered).
        assert set_env_block["HYBRID_API_KEY_FILE"] == "/run/secrets/hybrid_coordinator_api_key"
        rendered_bytes = json.dumps(manifest) + json.dumps(set_manifest) + json.dumps(settings) + json.dumps(set_settings)
        assert "-----BEGIN" not in rendered_bytes and "ghp_" not in rendered_bytes
        evidence["no_secrets_copied"] = True

        # -- Upgrade re-declares current state instead of freezing it -----
        # (FACTORY_MANAGED_PREFIXES now includes capability-manifest.json.)
        upgrade_target = work / "upgrade target"
        upgrade_target.mkdir()
        run("git", "init", cwd=upgrade_target)
        run("git", "config", "user.name", "Fixture Author", cwd=upgrade_target)
        run("git", "config", "user.email", "fixture@example.invalid", cwd=upgrade_target)
        run(str(AQD), "workflows", "project-init", "--target", str(upgrade_target), "--name", "upgrade target",
            "--goal", "prove upgrade refresh", "--stack", "generic", "--owner", "test", cwd=ROOT)
        before = json.loads((upgrade_target / ".factory/capability-manifest.json").read_text(encoding="utf-8"))
        assert before["capabilities"]["hybrid_coordinator"]["state"] == "unavailable"

        preview = run(str(AQD), "workflows", "retrofit", "--target", str(upgrade_target), "--name", "upgrade target",
                      "--stack", "generic", cwd=ROOT, extra_env=engine_env)
        preview_json = json.loads(preview.stdout)
        assert preview_json["safe_to_install"] and preview_json.get("upgrade") is True, preview_json
        installed = run(str(AQD), "workflows", "retrofit", "--target", str(upgrade_target), "--name", "upgrade target",
                        "--stack", "generic", "--confirm-retrofit", preview_json["preview_digest"],
                        cwd=ROOT, extra_env=engine_env)
        installed_json = json.loads(installed.stdout)
        assert installed_json["installation"]["state"] == "INSTALLED", installed_json
        after = json.loads((upgrade_target / ".factory/capability-manifest.json").read_text(encoding="utf-8"))
        assert after["capabilities"]["hybrid_coordinator"]["state"] == "available"
        assert after["capabilities"]["hybrid_coordinator"]["endpoint"] == "http://coordinator.example.internal:8003"
        evidence["manifest_refreshed_on_upgrade"] = True

    assert all(evidence.values()), evidence
    print("AQ_QA_FACTORY_CAPABILITY_MANIFEST_FIXTURE=" + json.dumps(evidence, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
