"""RunContext — configuration and environment for a QA run."""
from __future__ import annotations

import os
import pwd
import subprocess
from pathlib import Path
from functools import cached_property


class RunContext:
    """Carries all run-time configuration needed by phase check functions."""

    def __init__(
        self,
        *,
        repo_root: Path,
        layer_filter: int = 0,
        causality_mode: bool = False,
        use_sudo: bool = False,
        aq_report_json: str = "",
        skip_report_checks: bool = False,
        query_timeout_s: int = 45,
        port_retry_attempts: int = 4,
        port_retry_delay_s: float = 1.0,
    ) -> None:
        self.repo_root = repo_root
        self.layer_filter = layer_filter
        self.causality_mode = causality_mode
        self.use_sudo = use_sudo
        self.aq_report_json = aq_report_json
        self.skip_report_checks = skip_report_checks
        self.query_timeout_s = query_timeout_s
        self.port_retry_attempts = port_retry_attempts
        self.port_retry_delay_s = port_retry_delay_s

    def should_run(self, layer: int) -> bool:
        if self.layer_filter == 0:
            return True
        if self.layer_filter == layer:
            return True
        if self.causality_mode and self.layer_filter > layer:
            return True
        return False

    # ------------------------------------------------------------------ env
    @cached_property
    def llama_url(self) -> str:
        host = os.environ.get("LLAMA_HOST", "127.0.0.1")
        port = os.environ.get("LLAMA_PORT", "8080")
        return os.environ.get("LLAMA_URL", f"http://{host}:{port}")

    @cached_property
    def embeddings_url(self) -> str:
        host = os.environ.get("EMBEDDINGS_HOST", "127.0.0.1")
        port = os.environ.get("EMBEDDINGS_PORT", "8081")
        return f"http://{host}:{port}"

    @cached_property
    def aidb_url(self) -> str:
        host = os.environ.get("AIDB_HOST", "127.0.0.1")
        port = os.environ.get("AIDB_PORT", "8002")
        return os.environ.get("AIDB_URL", f"http://{host}:{port}")

    @cached_property
    def hybrid_url(self) -> str:
        host = os.environ.get("HYBRID_HOST", "127.0.0.1")
        port = os.environ.get("HYBRID_PORT", "8003")
        return os.environ.get("HYBRID_URL", f"http://{host}:{port}")

    @cached_property
    def hybrid_coordinator_url(self) -> str:
        return os.environ.get("HYBRID_COORDINATOR_URL", self.hybrid_url)

    @cached_property
    def qdrant_url(self) -> str:
        host = os.environ.get("QDRANT_HOST", "127.0.0.1")
        port = os.environ.get("QDRANT_PORT", "6333")
        return os.environ.get("QDRANT_URL", f"http://{host}:{port}")

    @cached_property
    def switchboard_url(self) -> str:
        host = os.environ.get("SWITCHBOARD_HOST", "127.0.0.1")
        port = os.environ.get("SWITCHBOARD_PORT", "8085")
        return os.environ.get("SWITCHBOARD_URL", f"http://{host}:{port}")

    @cached_property
    def api_key(self) -> str:
        """Read hybrid coordinator API key from secrets file."""
        try:
            return Path("/run/secrets/hybrid_coordinator_api_key").read_text().strip()
        except OSError:
            return os.environ.get("HYBRID_API_KEY", "")

    @cached_property
    def primary_user(self) -> str:
        if v := os.environ.get("AQ_QA_PRIMARY_USER"):
            return v
        if v := os.environ.get("SUDO_USER"):
            return v
        try:
            return pwd.getpwuid(self.repo_root.stat().st_uid).pw_name
        except (KeyError, OSError):
            pass
        return os.environ.get("USER", "")

    @cached_property
    def primary_home(self) -> str:
        if v := os.environ.get("AQ_QA_PRIMARY_HOME"):
            return v
        try:
            return pwd.getpwnam(self.primary_user).pw_dir
        except (KeyError, OSError):
            pass
        return os.environ.get("HOME", "")

    @cached_property
    def primary_user_path(self) -> str:
        h = self.primary_home
        return ":".join([
            f"{h}/.npm-global/bin",
            f"{h}/.local/bin",
            f"{h}/.nix-profile/bin",
            os.environ.get("PATH", ""),
        ])

    @cached_property
    def aq_report_snapshot(self) -> str:
        """Return aq-report JSON (from env fixture, file, or inline run)."""
        if self.aq_report_json:
            return self.aq_report_json
        snapshot_path = os.environ.get(
            "AQ_QA_AQ_REPORT_PATH",
            "/var/lib/ai-stack/hybrid/telemetry/latest-aq-report.json"
        )
        p = Path(snapshot_path)
        if p.is_file() and p.stat().st_size > 0:
            try:
                import json
                text = p.read_text()
                json.loads(text)  # validate
                return text
            except Exception:
                pass
        return ""
