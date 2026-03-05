#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

violations=0

while IFS= read -r path; do
  [[ -n "${path}" ]] || continue
  base="$(basename "${path}")"
  dir="$(dirname "${path}")"
  ext="${base##*.}"
  stem="${base%.*}"

  [[ "${stem}" == *"_"* ]] || continue

  kebab_stem="${stem//_/-}"
  kebab_path="${dir}/${kebab_stem}.${ext}"
  mapfile -t kebab_candidates < <(rg --files scripts | rg "/${kebab_stem}\\.${ext}$" || true)

  if [[ ! -f "${kebab_path}" ]]; then
    if [[ "${#kebab_candidates[@]}" -eq 0 ]]; then
      echo "[script-shim] FAIL missing kebab target: ${path} -> ${kebab_path}"
      violations=$((violations + 1))
      continue
    fi
  fi

  if [[ "${ext}" == "sh" ]]; then
    if ! grep -Eq 'exec .*[/-]'"${kebab_stem}"'\.sh' "${path}"; then
      echo "[script-shim] FAIL shell shim not forwarding to kebab target: ${path}"
      violations=$((violations + 1))
      continue
    fi
    if [[ ! -f "${kebab_path}" ]]; then
      found_ref=0
      for candidate in "${kebab_candidates[@]}"; do
        if grep -Fq "${candidate#scripts/}" "${path}" || grep -Fq "${candidate}" "${path}"; then
          found_ref=1
          break
        fi
      done
      if [[ "${found_ref}" -ne 1 ]]; then
        echo "[script-shim] FAIL shell shim references kebab name but not a concrete candidate path: ${path}"
        violations=$((violations + 1))
      fi
    fi
    continue
  fi

  if [[ "${ext}" == "py" ]]; then
    if ! grep -Eq 'runpy\.run_path|runpy\.run_module' "${path}"; then
      echo "[script-shim] FAIL python shim missing runpy forwarding: ${path}"
      violations=$((violations + 1))
      continue
    fi
    if ! grep -Eq "${kebab_stem}\.py" "${path}"; then
      echo "[script-shim] FAIL python shim missing kebab target reference: ${path}"
      violations=$((violations + 1))
      continue
    fi
    if [[ ! -f "${kebab_path}" ]]; then
      found_ref=0
      for candidate in "${kebab_candidates[@]}"; do
        if grep -Fq "${candidate#scripts/}" "${path}" || grep -Fq "${candidate}" "${path}"; then
          found_ref=1
          break
        fi
      done
      if [[ "${found_ref}" -ne 1 ]]; then
        echo "[script-shim] FAIL python shim references kebab name but not a concrete candidate path: ${path}"
        violations=$((violations + 1))
      fi
    fi
  fi
done < <(rg --files scripts | rg '\.(sh|py)$' | sort)

if [[ "${violations}" -ne 0 ]]; then
  echo "[script-shim] FAIL: ${violations} shim consistency issue(s)."
  exit 1
fi

echo "[script-shim] PASS: underscore script shims forward to kebab targets."
