#!/usr/bin/env python3
"""Static contract for the unprivileged SC-1 Secrets & Access dashboard card."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HTML = (ROOT / "dashboard.html").read_text(encoding="utf-8")
JS = (ROOT / "assets/dashboard.js").read_text(encoding="utf-8")


def require(text: str, message: str) -> None:
    if text not in HTML + JS:
        raise AssertionError(message)


def main() -> int:
    require('id="secretsAccessDetails"', "Security Center needs a live Secrets & Access projection")
    require('id="secretsAccessBadge"', "Security Center needs a visible readiness state")
    require('apiFetch("/security-settings/status")', "Security Center must use the metadata-only status endpoint")
    require("payload?.overall_state", "Security Center must honor the backend's canonical overall state")
    require("counts.unavailable", "Unavailable credential observations must not render as protected")
    require("counts.managed_separately", "PAM and vault backends need a truthful separate-management count")
    require("counts.not_enabled", "Optional credentials must be distinct from missing credentials")
    require("function securityCenterEscape", "Security Center must escape all dynamic display text")
    require("Protected", "Security Center must explain the protected state")
    require("Needs attention", "Security Center must explain attention needed")
    require("Setup incomplete", "Security Center must explain incomplete setup")
    require("Unavailable", "Security Center must explain unavailable inventory")
    require("Show protected item names and affected services", "Credential metadata needs progressive disclosure")
    require("never displays secret values, password material, hashes, or storage paths", "UI must state its secret boundary")
    require("secured Settings Broker", "Mutation authority must remain outside the dashboard")

    forbidden = [
        "/security-settings/reveal",
        "/security-settings/decrypt",
        "/security-settings/apply",
        "type=\"password\"",
        "localStorage.setItem",
    ]
    for token in forbidden:
        if token in JS:
            raise AssertionError(f"SC-1 must not introduce privileged secret UI behavior: {token}")

    print("PASS: Security Center UI is metadata-only, escaped, and progressively disclosed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
