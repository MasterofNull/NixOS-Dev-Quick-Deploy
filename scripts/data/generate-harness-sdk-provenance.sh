#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${ROOT:-$(cd "${SCRIPT_DIR}/../.." && pwd)}"
SDK_DIR="${ROOT}/ai-stack/mcp-servers/hybrid-coordinator"
OUT_DIR="${1:-${XDG_STATE_HOME:-$HOME/.local/state}/nixos-ai-stack/harness-sdk-provenance}"
mkdir -p "$OUT_DIR"

PKG_JSON="${SDK_DIR}/package.json"
PYPROJECT="${SDK_DIR}/pyproject.toml"

python - "$SDK_DIR" "$PKG_JSON" "$PYPROJECT" "$OUT_DIR/provenance.json" <<'PY'
import hashlib
import json
import pathlib
import re
import sys
from datetime import datetime, timezone

sdk_dir = pathlib.Path(sys.argv[1])
pkg_json = pathlib.Path(sys.argv[2])
pyproject = pathlib.Path(sys.argv[3])
out = pathlib.Path(sys.argv[4])

def sha256(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

pkg = json.loads(pkg_json.read_text(encoding="utf-8"))
py_text = pyproject.read_text(encoding="utf-8")
py_ver_match = re.search(r'^version\s*=\s*"([^"]+)"', py_text, flags=re.MULTILINE)
py_ver = py_ver_match.group(1) if py_ver_match else "unknown"
py_deps = re.findall(r'^\s*"([^"]+)"\s*,?\s*$', re.search(r"dependencies\s*=\s*\[(.*?)\]", py_text, flags=re.S|re.M).group(1), flags=re.M) if "dependencies" in py_text else []

files = []
for p in sorted(sdk_dir.glob("harness_sdk.*")):
    if p.is_file():
        files.append({
            "path": str(p.relative_to(sdk_dir)),
            "sha256": sha256(p),
            "size_bytes": p.stat().st_size,
        })

payload = {
    "schema_version": 1,
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "python_package": {
        "name": "nixos-ai-harness-sdk",
        "version": py_ver,
        "dependencies": py_deps,
    },
    "npm_package": {
        "name": pkg.get("name", ""),
        "version": pkg.get("version", ""),
    },
    "files": files,
    "sbom_minimal": {
        "components": [
            {"name": "httpx", "type": "python"},
            {"name": "node-fetch-compatible-runtime", "type": "javascript-runtime"}
        ],
        "note": "Minimal generated SBOM; replace with syft/cyclonedx for full inventory."
    }
}

out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(out)
PY

printf '%s\n' "Generated provenance: ${OUT_DIR}/provenance.json"
