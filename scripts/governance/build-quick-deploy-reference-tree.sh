#!/usr/bin/env bash
set -euo pipefail

# Build a quick-deploy dependency reference tree for runtime-critical paths.
# Output: docs/operations/QUICK-DEPLOY-REFERENCE-TREE.md

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DEPLOY_SCRIPT="${ROOT_DIR}/nixos-quick-deploy.sh"
OUTPUT_MD="${ROOT_DIR}/docs/operations/QUICK-DEPLOY-REFERENCE-TREE.md"

if [[ ! -f "${DEPLOY_SCRIPT}" ]]; then
  echo "[ref-tree] Missing deploy script: ${DEPLOY_SCRIPT}" >&2
  exit 1
fi

mkdir -p "$(dirname "${OUTPUT_MD}")"

python3 - "${ROOT_DIR}" "${DEPLOY_SCRIPT}" "${OUTPUT_MD}" <<'PY'
import datetime as dt
import pathlib
import re
import subprocess
import sys

root = pathlib.Path(sys.argv[1])
deploy_script = pathlib.Path(sys.argv[2])
output_md = pathlib.Path(sys.argv[3])

text = deploy_script.read_text(encoding="utf-8")

pattern = re.compile(r"\$\{REPO_ROOT\}/([^\"\s)]+)")
refs = sorted(set(pattern.findall(text)))

core_refs = []
dynamic_refs = []
for r in refs:
    if "${" in r:
        dynamic_refs.append(r)
    else:
        core_refs.append(r)

def rg_count(p: str) -> int:
    cmd = [
        "rg", "-n", "-S", p,
        str(root / "scripts"),
        str(root / "nix"),
        str(root / "lib"),
        str(root / "config"),
        str(root / ".github" / "workflows"),
        str(root / "Makefile"),
        str(root / "nixos-quick-deploy.sh"),
    ]
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, text=True)
    except subprocess.CalledProcessError:
        return 0
    return len([line for line in out.splitlines() if line.strip()])

lines = []
lines.append("# Quick Deploy Reference Tree")
lines.append("")
lines.append(f"Generated: {dt.datetime.now(dt.UTC).strftime('%Y-%m-%d %H:%M UTC')}")
lines.append("")
lines.append("## Root Runtime Entrypoint")
lines.append("- `nixos-quick-deploy.sh`")
lines.append("")
lines.append("## Direct Runtime Dependencies (Resolved Paths)")
for ref in core_refs:
    status = "exists" if (root / ref).exists() else "missing"
    refs_in_repo = rg_count(ref)
    lines.append(f"- `{ref}` ({status}, {refs_in_repo} references)")
lines.append("")
lines.append("## Dynamic/Templated Dependencies")
for ref in dynamic_refs:
    lines.append(f"- `{ref}`")
lines.append("")
lines.append("## Notes")
lines.append("- Files under this dependency set are considered active runtime scope.")
lines.append("- Stale trimming should not move these files unless paths are rewritten and validated.")
lines.append("")

output_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"[ref-tree] Wrote {output_md}")
PY
