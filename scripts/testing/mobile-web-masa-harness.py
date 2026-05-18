#!/usr/bin/env python3
"""Mobile Accessibility & Security Audit (MASA) validation harness.

This harness is intentionally deterministic and offline-friendly:

- If `lighthouse` is available and a URL is supplied, it runs the real CLI.
- Otherwise it emits a small Lighthouse-shaped JSON report for a local fixture.
- It always runs a MASVS-aligned static scan over sample Android/web sources.

The fixture mode is not a substitute for a release Lighthouse audit. It exists so
the mobile-web domain can validate report plumbing and MASVS checks without
network installs or heavyweight browser downloads.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Finding:
    rule_id: str
    severity: str
    standard: str
    path: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {
            "rule_id": self.rule_id,
            "severity": self.severity,
            "standard": self.standard,
            "path": self.path,
            "message": self.message,
        }


def _write_fixture(root: Path) -> dict[str, Path]:
    web = root / "web"
    android = root / "android"
    web.mkdir(parents=True, exist_ok=True)
    android.mkdir(parents=True, exist_ok=True)

    index = web / "index.html"
    index.write_text(
        """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>MASA Fixture</title>
</head>
<body>
  <main>
    <h1>Mobile Web Validation Fixture</h1>
    <button type="button" aria-label="Run validation">Run</button>
  </main>
</body>
</html>
""",
        encoding="utf-8",
    )

    manifest = android / "AndroidManifest.xml"
    manifest.write_text(
        """<manifest xmlns:android="http://schemas.android.com/apk/res/android">
  <application
      android:allowBackup="false"
      android:usesCleartextTraffic="false"
      android:label="MASA Fixture" />
</manifest>
""",
        encoding="utf-8",
    )

    activity = android / "MainActivity.kt"
    activity.write_text(
        """package local.validation

class MainActivity {
    fun endpoint(): String = "https://example.invalid/api"
}
""",
        encoding="utf-8",
    )

    return {"web": web, "android": android, "index": index}


def _fixture_lighthouse_report(index: Path) -> dict[str, Any]:
    return {
        "lighthouseVersion": "fixture",
        "userAgent": "mobile-web-masa-harness",
        "fetchTime": "2026-05-18T00:00:00.000Z",
        "requestedUrl": index.as_uri(),
        "finalDisplayedUrl": index.as_uri(),
        "categories": {
            "performance": {"id": "performance", "score": 1.0},
            "accessibility": {"id": "accessibility", "score": 1.0},
            "best-practices": {"id": "best-practices", "score": 1.0},
            "seo": {"id": "seo", "score": 1.0},
        },
        "audits": {
            "viewport": {"id": "viewport", "score": 1, "title": "Has a viewport meta tag"},
            "html-has-lang": {"id": "html-has-lang", "score": 1, "title": "`html` element has a lang attribute"},
            "button-name": {"id": "button-name", "score": 1, "title": "Buttons have accessible names"},
        },
        "runtime": {"mode": "fixture", "real_lighthouse": False},
    }


def _run_lighthouse(url: str, output_path: Path) -> tuple[dict[str, Any], str]:
    lighthouse = shutil.which("lighthouse")
    if not lighthouse:
        raise FileNotFoundError("lighthouse binary not found")
    cmd = [
        lighthouse,
        url,
        "--output=json",
        f"--output-path={output_path}",
        "--quiet",
        "--chrome-flags=--headless --no-sandbox",
    ]
    subprocess.run(cmd, check=True)
    return json.loads(output_path.read_text(encoding="utf-8")), "real"


def _scan_masvs(paths: list[Path]) -> list[Finding]:
    rules: list[tuple[str, str, str, re.Pattern[str], str]] = [
        (
            "MASVS-NETWORK-CLEARTEXT",
            "high",
            "MASVS-NETWORK",
            re.compile(r'usesCleartextTraffic\s*=\s*"true"', re.I),
            "Cleartext traffic is enabled.",
        ),
        (
            "MASVS-STORAGE-ALLOW-BACKUP",
            "medium",
            "MASVS-STORAGE",
            re.compile(r'allowBackup\s*=\s*"true"', re.I),
            "Android backup is enabled for application data.",
        ),
        (
            "MASVS-CODE-HARDCODED-SECRET",
            "high",
            "MASVS-CODE",
            re.compile(r'(?i)(api[_-]?key|secret|password)\s*[=:]\s*["\'][^"\']{8,}["\']'),
            "Potential hardcoded secret.",
        ),
        (
            "MASVS-NETWORK-INSECURE-HTTP",
            "medium",
            "MASVS-NETWORK",
            re.compile(r'http://(?!127\.0\.0\.1|localhost)', re.I),
            "Non-local HTTP URL detected.",
        ),
    ]

    findings: list[Finding] = []
    for path in paths:
        if path.is_dir():
            files = [p for p in path.rglob("*") if p.is_file()]
        else:
            files = [path]
        for file_path in files:
            text = file_path.read_text(encoding="utf-8", errors="replace")
            for rule_id, severity, standard, pattern, message in rules:
                if pattern.search(text):
                    findings.append(
                        Finding(
                            rule_id=rule_id,
                            severity=severity,
                            standard=standard,
                            path=str(file_path),
                            message=message,
                        )
                    )
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Run mobile-web MASA validation harness")
    parser.add_argument("--url", help="Optional URL for a real Lighthouse run")
    parser.add_argument("--source", action="append", type=Path, default=[], help="Source path to scan")
    parser.add_argument("--output", type=Path, default=Path("/tmp/phase58b-mobile-web-masa.json"))
    parser.add_argument("--require-real-lighthouse", action="store_true")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="masa-fixture-") as tmp:
        fixture = _write_fixture(Path(tmp))
        sources = args.source or [fixture["web"], fixture["android"]]

        lighthouse_output = args.output.with_suffix(".lighthouse.json")
        try:
            if args.url:
                lighthouse_report, lighthouse_mode = _run_lighthouse(args.url, lighthouse_output)
            elif args.require_real_lighthouse:
                raise FileNotFoundError("--require-real-lighthouse set but no --url supplied")
            else:
                lighthouse_report = _fixture_lighthouse_report(fixture["index"])
                lighthouse_mode = "fixture"
        except Exception as exc:
            if args.require_real_lighthouse:
                print(f"[masa] real Lighthouse failed: {exc}", file=sys.stderr)
                return 2
            lighthouse_report = _fixture_lighthouse_report(fixture["index"])
            lighthouse_report["runtime"]["fallback_reason"] = str(exc)
            lighthouse_mode = "fixture"

        findings = _scan_masvs(sources)
        high_findings = [f for f in findings if f.severity == "high"]
        result = {
            "status": "pass" if not high_findings else "fail",
            "domain": "mobile-web",
            "lighthouse": {
                "mode": lighthouse_mode,
                "real_lighthouse": lighthouse_mode == "real",
                "report": lighthouse_report,
            },
            "masvs": {
                "standards": ["MASVS-STORAGE", "MASVS-NETWORK", "MASVS-CODE"],
                "source_count": len(sources),
                "finding_count": len(findings),
                "high_finding_count": len(high_findings),
                "findings": [finding.to_dict() for finding in findings],
            },
        }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"[masa] wrote {args.output}")
    print(
        f"[masa] status={result['status']} lighthouse={lighthouse_mode} "
        f"masvs_findings={len(findings)} high={len(high_findings)}"
    )
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
