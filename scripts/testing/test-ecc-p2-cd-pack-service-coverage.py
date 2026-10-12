#!/usr/bin/env python3
"""Service coverage gate for ECC P2 separately approval-gated CD pack.

Verifies the service coverage contract:
1. aq-qa check 0.10.63 registered in Phase 0 (phase0.py) and _aq-qa-bash.
2. Dashboard panel: backend endpoint exposes cd_pack and frontend renders '· CD pack'.
3. Factory gate bundle manifests: MANIFEST.json lists factory-cd.yml.tmpl and cd_policy.py.
4. Fixture execution: test-factory-cd-pack.py runs and passes.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    phase0 = (ROOT / "scripts/testing/harness_qa/phases/phase0.py").read_text(encoding="utf-8")
    assert "0.10.63" in phase0, "0.10.63 missing from phase0.py"
    assert "_check_ecc_p2_approval_gated_cd" in phase0, "_check_ecc_p2_approval_gated_cd missing from phase0.py"

    aq_bash = (ROOT / "scripts/ai/_aq-qa-bash").read_text(encoding="utf-8")
    assert "0.10.63" in aq_bash, "0.10.63 missing from _aq-qa-bash"

    backend = (ROOT / "dashboard/backend/api/routes/aistack.py").read_text(encoding="utf-8")
    assert "_cd_pack_health_summary" in backend, "_cd_pack_health_summary missing from aistack.py"
    assert '"cd_pack":' in backend, '"cd_pack" missing from aistack.py'

    frontend = (ROOT / "assets/dashboard.js").read_text(encoding="utf-8")
    assert "· CD pack" in frontend, "· CD pack missing from dashboard.js"

    manifest = (ROOT / "templates/factory-gate-bundle/MANIFEST.json").read_text(encoding="utf-8")
    assert "ci/factory-cd.yml.tmpl" in manifest, "factory-cd.yml.tmpl missing from MANIFEST.json"
    assert "ci/cd_policy.py" in manifest, "cd_policy.py missing from MANIFEST.json"

    proc = subprocess.run([sys.executable, str(ROOT / "scripts/testing/test-factory-cd-pack.py")],
                          capture_output=True, text=True, check=False)
    assert proc.returncode == 0, f"test-factory-cd-pack.py failed:\n{proc.stdout}\n{proc.stderr}"
    assert "PASS: factory CD pack" in proc.stdout

    print("PASS: ecc-p2-cd-pack-service-coverage")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
