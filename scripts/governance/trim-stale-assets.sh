#!/usr/bin/env bash
set -euo pipefail

# Archive stale tracked assets (docs/scripts) by age and reference policy.
# Default behavior is dry-run; --apply moves files into archive domains.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CUTOFF_DAYS="${CUTOFF_DAYS:-45}"
MODE="dry-run"
SCOPE="docs"
REPORT_FILE="${ROOT_DIR}/docs/operations/STALE-ASSET-TRIM-REPORT.md"
KEEP_LIST_FILE="${ROOT_DIR}/config/stale-trim-keep.txt"

usage() {
  cat <<'EOF'
Usage: scripts/governance/trim-stale-assets.sh [--apply] [--scope docs|all] [--cutoff-days N]

Behavior:
  - Never hard-deletes. Moves stale assets into archive domains.
  - Docs scope moves stale markdown files from docs/ (excluding docs/archive/)
    into docs/archive/stale/YYYY-MM/.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --apply)
      MODE="apply"
      shift
      ;;
    --scope)
      SCOPE="${2:-docs}"
      shift 2
      ;;
    --cutoff-days)
      CUTOFF_DAYS="${2:-45}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "[trim-stale] Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

cutoff_epoch="$(date -d "${CUTOFF_DAYS} days ago" +%s)"
stamp_month="$(date +%Y-%m)"
stale_root_docs="${ROOT_DIR}/docs/archive/stale/${stamp_month}"
stale_root_scripts="${ROOT_DIR}/archive/deprecated/scripts-stale/${stamp_month}"
mkdir -p "${stale_root_docs}" "${stale_root_scripts}" "$(dirname "${REPORT_FILE}")"

is_excluded_doc() {
  local rel="$1"
  [[ "${rel}" == docs/archive/* ]] && return 0
  [[ "${rel}" == docs/generated/* ]] && return 0
  [[ "${rel}" == docs/development/SYSTEM-UPGRADE-ROADMAP.md ]] && return 0
  [[ "${rel}" == docs/development/SYSTEM-UPGRADE-ROADMAP-UPDATES.md ]] && return 0
  [[ "${rel}" == docs/SYSTEM-IMPROVEMENT-PLAN-2026-03.md ]] && return 0
  return 1
}

is_tracked_file() {
  local rel="$1"
  git -C "${ROOT_DIR}" ls-files --error-unmatch -- "${rel}" >/dev/null 2>&1
}

declare -a KEEP_LIST=()
if [[ -f "${KEEP_LIST_FILE}" ]]; then
  while IFS= read -r line; do
    line="${line%%#*}"
    line="$(printf '%s' "${line}" | sed 's/[[:space:]]*$//')"
    [[ -z "${line}" ]] && continue
    KEEP_LIST+=("${line}")
  done < "${KEEP_LIST_FILE}"
fi

in_keep_list() {
  local rel="$1"
  local item
  for item in "${KEEP_LIST[@]}"; do
    if [[ "${item}" == */ ]]; then
      [[ "${rel}" == "${item}"* ]] && return 0
    else
      [[ "${rel}" == "${item}" ]] && return 0
    fi
  done
  return 1
}

doc_candidates=()
while IFS= read -r -d '' file; do
  rel="${file#${ROOT_DIR}/}"
  is_tracked_file "${rel}" || continue
  in_keep_list "${rel}" && continue
  if is_excluded_doc "${rel}"; then
    continue
  fi
  last_epoch="$(git -C "${ROOT_DIR}" log -1 --format=%ct -- "${rel}" 2>/dev/null || true)"
  [[ -z "${last_epoch}" ]] && continue
  if (( last_epoch <= cutoff_epoch )); then
    doc_candidates+=("${rel}:${last_epoch}")
  fi
done < <(find "${ROOT_DIR}/docs" -type f -name '*.md' -print0)

script_runtime_refs=(
  "scripts/ai/aq-report"
  "scripts/testing/compare-installed-vs-intended.sh"
  "scripts/data/import-agent-instructions.sh"
  "scripts/data/rebuild-qdrant-collections.sh"
  "scripts/data/seed-routing-traffic.sh"
  "scripts/data/sync-flatpak-profile.sh"
  "scripts/governance/analyze-clean-deploy-readiness.sh"
  "scripts/governance/discover-system-facts.sh"
  "scripts/governance/git-safe.sh"
  "scripts/governance/preflight-auto-remediate.sh"
  "scripts/health/system-health-check.sh"
  "scripts/testing/check-mcp-health.sh"
  "scripts/testing/validate-runtime-declarative.sh"
  "scripts/testing/verify-flake-first-roadmap-completion.sh"
)

active_script_file="$(mktemp)"
trap 'rm -f "${active_script_file}"' EXIT

python3 - "${ROOT_DIR}" "${active_script_file}" "${script_runtime_refs[@]}" <<'PY'
import pathlib
import re
import subprocess
import sys

root = pathlib.Path(sys.argv[1])
out_file = pathlib.Path(sys.argv[2])
seed_refs = set(sys.argv[3:])

seed_files = [
    root / "nixos-quick-deploy.sh",
    root / "Makefile",
    root / "config",
    root / "nix",
    root / "systemd",
    root / ".github" / "workflows",
]

active = set(seed_refs)
queue = list(seed_refs)

script_ref_patterns = [
    re.compile(r"\$\{REPO_ROOT\}/(scripts/[^\s\"')]+)"),
    re.compile(r"\b(scripts/[A-Za-z0-9_./-]+)"),
]

def git_tracked(rel: str) -> bool:
    try:
        subprocess.check_call(
            ["git", "-C", str(root), "ls-files", "--error-unmatch", "--", rel],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except subprocess.CalledProcessError:
        return False

def extract_refs(text: str):
    refs = set()
    for pat in script_ref_patterns:
        for m in pat.finditer(text):
            candidate = m.group(1).rstrip(".,:;")
            if candidate.startswith("scripts/"):
                refs.add(candidate)
    return refs

for source in seed_files:
    if source.is_file():
        refs = extract_refs(source.read_text(encoding="utf-8", errors="ignore"))
        for ref in refs:
            if git_tracked(ref):
                active.add(ref)
                queue.append(ref)
    elif source.is_dir():
        for path in source.rglob("*"):
            if not path.is_file():
                continue
            refs = extract_refs(path.read_text(encoding="utf-8", errors="ignore"))
            for ref in refs:
                if git_tracked(ref):
                    active.add(ref)
                    queue.append(ref)

seen = set()
while queue:
    rel = queue.pop()
    if rel in seen:
        continue
    seen.add(rel)
    path = root / rel
    if not path.is_file():
        continue
    text = path.read_text(encoding="utf-8", errors="ignore")
    refs = extract_refs(text)

    # Handle local shell source/call patterns relative to current script dir.
    for m in re.finditer(r"(?:source|bash)\s+([./][^\s\"')]+)", text):
        local_ref = m.group(1).rstrip(".,:;")
        if local_ref.startswith("./"):
            p = (path.parent / local_ref[2:]).resolve()
            try:
                relp = p.relative_to(root).as_posix()
            except Exception:
                continue
            if relp.startswith("scripts/"):
                refs.add(relp)

    for ref in refs:
        if not ref.startswith("scripts/"):
            continue
        if not git_tracked(ref):
            continue
        if ref not in active:
            active.add(ref)
            queue.append(ref)

out_file.write_text("\n".join(sorted(active)) + "\n", encoding="utf-8")
PY

in_runtime_refs() {
  local rel="$1"
  [[ -f "${active_script_file}" ]] || return 1
  grep -Fxq "${rel}" "${active_script_file}"
}

script_referenced_elsewhere() {
  local rel="$1"
  rg -n -S --fixed-strings "${rel}" \
    "${ROOT_DIR}/nixos-quick-deploy.sh" \
    "${ROOT_DIR}/Makefile" \
    "${ROOT_DIR}/config" \
    "${ROOT_DIR}/nix" \
    "${ROOT_DIR}/systemd" \
    "${ROOT_DIR}/.github/workflows" \
    >/dev/null 2>&1
}

script_candidates=()
while IFS= read -r -d '' file; do
  rel="${file#${ROOT_DIR}/}"
  is_tracked_file "${rel}" || continue
  in_keep_list "${rel}" && continue
  in_runtime_refs "${rel}" && continue
  script_referenced_elsewhere "${rel}" && continue
  last_epoch="$(git -C "${ROOT_DIR}" log -1 --format=%ct -- "${rel}" 2>/dev/null || true)"
  [[ -z "${last_epoch}" ]] && continue
  if (( last_epoch <= cutoff_epoch )); then
    script_candidates+=("${rel}:${last_epoch}")
  fi
done < <(find "${ROOT_DIR}/scripts" -type f -print0)

{
  echo "# Stale Asset Trim Report"
  echo
  echo "Generated: $(date -u +'%Y-%m-%d %H:%M UTC')"
  echo "Mode: ${MODE}"
  echo "Scope: ${SCOPE}"
  echo "Cutoff days: ${CUTOFF_DAYS}"
  echo
  echo "## Stale Docs Candidates"
  if [[ ${#doc_candidates[@]} -eq 0 ]]; then
    echo "- none"
  else
    for row in "${doc_candidates[@]}"; do
      rel="${row%%:*}"
      epoch="${row##*:}"
      iso="$(date -u -d "@${epoch}" +%Y-%m-%d)"
      echo "- ${rel} (last commit: ${iso})"
    done
  fi
  echo
  echo "## Stale Script Candidates (Unreferenced by deploy/system wiring)"
  if [[ ${#script_candidates[@]} -eq 0 ]]; then
    echo "- none"
  else
    for row in "${script_candidates[@]}"; do
      rel="${row%%:*}"
      epoch="${row##*:}"
      iso="$(date -u -d "@${epoch}" +%Y-%m-%d)"
      echo "- ${rel} (last commit: ${iso})"
    done
  fi
  echo
} > "${REPORT_FILE}"

echo "[trim-stale] Candidate report written: ${REPORT_FILE}"

if [[ "${MODE}" != "apply" ]]; then
  echo "[trim-stale] Dry-run only. Re-run with --apply to archive candidates."
  exit 0
fi

if [[ "${SCOPE}" != "docs" && "${SCOPE}" != "all" ]]; then
  echo "[trim-stale] Unsupported scope: ${SCOPE}" >&2
  exit 1
fi

moved=0
for row in "${doc_candidates[@]}"; do
  rel="${row%%:*}"
  src="${ROOT_DIR}/${rel}"
  dest="${stale_root_docs}/${rel#docs/}"
  mkdir -p "$(dirname "${dest}")"
  if [[ -f "${src}" ]]; then
    mv "${src}" "${dest}"
    moved=$((moved + 1))
  fi
done

echo "[trim-stale] Moved ${moved} stale docs to ${stale_root_docs}"

if [[ "${SCOPE}" == "all" ]]; then
  moved_scripts=0
  for row in "${script_candidates[@]}"; do
    rel="${row%%:*}"
    src="${ROOT_DIR}/${rel}"
    dest="${stale_root_scripts}/${rel#scripts/}"
    mkdir -p "$(dirname "${dest}")"
    if [[ -f "${src}" ]]; then
      mv "${src}" "${dest}"
      moved_scripts=$((moved_scripts + 1))
    fi
  done
  echo "[trim-stale] Moved ${moved_scripts} stale scripts to ${stale_root_scripts}"
fi
