#!/usr/bin/env bash
set -euo pipefail

# Audit naming and labeling consistency for maintainability.
# Produces a markdown report with findings and recommended next actions.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT_FILE="${ROOT_DIR}/.reports/naming-label-consistency-report.md"
PUBLISH_DOC=false

usage() {
  cat <<'USAGE'
Usage: scripts/governance/check-naming-label-consistency.sh [options]

Options:
  --out-file PATH   Write report to PATH (default: ./.reports/naming-label-consistency-report.md)
  --publish-doc     Write report to docs/operations/NAMING-LABEL-CONSISTENCY-REPORT-2026-03-05.md
  -h, --help        Show this help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --out-file)
      OUT_FILE="$2"
      shift 2
      ;;
    --publish-doc)
      PUBLISH_DOC=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ "${PUBLISH_DOC}" == "true" ]]; then
  OUT_FILE="${ROOT_DIR}/docs/operations/NAMING-LABEL-CONSISTENCY-REPORT-2026-03-05.md"
fi

python3 - "${ROOT_DIR}" "${OUT_FILE}" <<'PY'
from pathlib import Path
import datetime as dt
import re
import sys

root = Path(sys.argv[1])
out = Path(sys.argv[2])

script_files = [p for p in (root / "scripts").rglob("*") if p.is_file() and p.suffix in {".sh", ".py"}]
active_docs = []
for p in (root / "docs").rglob("*.md"):
    rel = p.relative_to(root).as_posix()
    if rel.startswith("docs/archive/"):
        continue
    active_docs.append(p)

non_kebab_scripts = []
underscore_shim_scripts = []
missing_script_headers = []
for p in sorted(script_files):
    name = p.name
    try:
        lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        continue
    first = lines[0].strip() if lines else ""
    second = lines[1].strip() if len(lines) > 1 else ""
    is_compat_shim = (
        first.startswith("#!")
        and (
            "Compatibility shim" in second
            or "compatibility shim" in second
            or "Compatibility shim" in "\n".join(lines[:6])
        )
    )
    if p.suffix in {".sh", ".py"}:
        stem = p.stem
        if "_" in stem:
            rel = p.relative_to(root).as_posix()
            if is_compat_shim:
                underscore_shim_scripts.append(rel)
            else:
                non_kebab_scripts.append(rel)
    head = lines[:8]
    has_shebang = bool(head and head[0].startswith("#!"))
    has_purpose_comment = any(
        l.strip().startswith("#") and len(l.strip().lstrip("#").strip()) >= 8
        for l in head[1:]
    )
    if has_shebang and not has_purpose_comment:
        missing_script_headers.append(p.relative_to(root).as_posix())

frontmatter_missing = []
frontmatter_partial = []
for p in sorted(active_docs):
    text = p.read_text(encoding="utf-8", errors="ignore").splitlines()
    top = text[:30]
    joined = "\n".join(top)
    has_status = "Status:" in joined
    has_owner = "Owner:" in joined
    has_updated = any(k in joined for k in ["Last Updated:", "Updated:"])
    rel = p.relative_to(root).as_posix()
    if has_status and has_owner and has_updated:
        continue
    if has_status or has_owner or has_updated:
        frontmatter_partial.append(rel)
    else:
        frontmatter_missing.append(rel)

title_case_heading_issues = []
for p in sorted(active_docs):
    lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()
    first_h1 = next((l.strip() for l in lines if l.strip().startswith("# ")), "")
    if not first_h1:
        title_case_heading_issues.append((p.relative_to(root).as_posix(), "missing_h1"))
        continue
    title = first_h1[2:].strip()
    if title and title.lower() == title:
        title_case_heading_issues.append((p.relative_to(root).as_posix(), "non_title_case_h1"))

out.parent.mkdir(parents=True, exist_ok=True)
lines = []
lines.append("# Naming & Label Consistency Report")
lines.append("")
lines.append(f"Generated: {dt.datetime.now(dt.UTC).strftime('%Y-%m-%d %H:%M UTC')}")
lines.append("")
lines.append("## Scope")
lines.append("- scripts: `scripts/**/*.sh|py`")
lines.append("- active docs: `docs/**/*.md` excluding `docs/archive/**`")
lines.append("")
lines.append("## Summary Metrics")
lines.append(f"- Script files audited: {len(script_files)}")
lines.append(f"- Active docs audited: {len(active_docs)}")
lines.append(f"- Scripts with underscore naming (non-shim): {len(non_kebab_scripts)}")
lines.append(f"- Underscore compatibility shims (informational): {len(underscore_shim_scripts)}")
lines.append(f"- Scripts missing header purpose comment: {len(missing_script_headers)}")
lines.append(f"- Docs missing metadata block (Status/Owner/Updated): {len(frontmatter_missing)}")
lines.append(f"- Docs with partial metadata block: {len(frontmatter_partial)}")
lines.append(f"- Docs with heading-label issue: {len(title_case_heading_issues)}")
lines.append("")
lines.append("## Conventions Target")
lines.append("- Script naming: prefer kebab-case for new files (`example-task.sh`).")
lines.append("- Script header: shebang + purpose comment within first 8 lines.")
lines.append("- Doc metadata (for active operations/development docs): include `Status:`, `Owner:`, and `Last Updated:` near top.")
lines.append("- First heading should be present and human-readable title case.")
lines.append("")
lines.append("## Findings")
lines.append("")
lines.append("### Scripts: Underscore Naming (Top 40)")
if non_kebab_scripts:
    for rel in non_kebab_scripts[:40]:
        lines.append(f"- `{rel}`")
else:
    lines.append("- none")
lines.append("")
lines.append("### Scripts: Underscore Compatibility Shims (Top 40, Informational)")
if underscore_shim_scripts:
    for rel in underscore_shim_scripts[:40]:
        lines.append(f"- `{rel}`")
else:
    lines.append("- none")
lines.append("")
lines.append("### Scripts: Missing Header Purpose Comment (Top 40)")
if missing_script_headers:
    for rel in missing_script_headers[:40]:
        lines.append(f"- `{rel}`")
else:
    lines.append("- none")
lines.append("")
lines.append("### Docs: Missing Metadata Block (Top 60)")
if frontmatter_missing:
    for rel in frontmatter_missing[:60]:
        lines.append(f"- `{rel}`")
else:
    lines.append("- none")
lines.append("")
lines.append("### Docs: Partial Metadata Block (Top 60)")
if frontmatter_partial:
    for rel in frontmatter_partial[:60]:
        lines.append(f"- `{rel}`")
else:
    lines.append("- none")
lines.append("")
lines.append("### Docs: Heading Label Issues (Top 60)")
if title_case_heading_issues:
    for rel, reason in title_case_heading_issues[:60]:
        lines.append(f"- `{rel}` ({reason})")
else:
    lines.append("- none")
lines.append("")
lines.append("## Recommended Next Slice")
lines.append("1. Add metadata block to active operations/development docs first.")
lines.append("2. Normalize high-touch script names (or add stable wrappers if renaming would break callers).")
lines.append("3. Enforce header standard for new scripts in CI lint stage.")
lines.append("")

out.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"[naming-label] Report written: {out}")
PY
