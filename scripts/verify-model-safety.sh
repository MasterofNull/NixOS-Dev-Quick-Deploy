#!/usr/bin/env bash
set -euo pipefail

# Phase 11.3 — Model Weight Integrity and Provenance
# Verifies GGUF model files for:
# 1. Pickle magic bytes in first 4KB (malicious model detection)
# 2. Records HuggingFace provenance metadata
#
# Usage: scripts/verify-model-safety.sh [--provenance-dir PATH] <model.gguf>
#
# Exit codes:
#   0 — Model passed all safety checks
#   1 — Safety check failed (pickle detected or invalid GGUF)
#   2 — Usage/configuration error

PROVENANCE_DIR="${AI_MODEL_PROVENANCE_DIR:-${HOME}/.local/share/nixos-ai-stack/models}"
HF_API_BASE="https://huggingface.co/api"

usage() {
  cat <<'EOF'
Usage: scripts/verify-model-safety.sh [--provenance-dir PATH] <model.gguf>

Phase 11.3 — Model Weight Integrity and Provenance verification.

Options:
  --provenance-dir PATH   Directory to store provenance.json (default: ~/.local/share/nixos-ai-stack/models)
  --hf-repo REPO          HuggingFace repo (org/name) for provenance recording
  --hf-commit HASH        HuggingFace commit hash for provenance recording
  -h, --help              Show this help message

Safety checks performed:
  1. GGUF magic bytes verification (first 4 bytes must be "GGUF")
  2. Pickle magic byte scan (first 4KB must not contain \\x80\\x04 or \\x80\\x05)
  3. Optional: Record HuggingFace provenance metadata

Exit codes:
  0 — Model passed all safety checks
  1 — Safety check failed (pickle detected, invalid GGUF, or malformed file)
  2 — Usage/configuration error
EOF
}

# Parse arguments
HF_REPO=""
HF_COMMIT=""
MODEL_PATH=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --provenance-dir)
      PROVENANCE_DIR="${2:?missing value for --provenance-dir}"
      shift 2
      ;;
    --hf-repo)
      HF_REPO="${2:?missing value for --hf-repo}"
      shift 2
      ;;
    --hf-commit)
      HF_COMMIT="${2:?missing value for --hf-commit}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    -*)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
    *)
      if [[ -z "${MODEL_PATH}" ]]; then
        MODEL_PATH="$1"
      else
        echo "Unexpected argument: $1" >&2
        usage >&2
        exit 2
      fi
      shift
      ;;
  esac
done

if [[ -z "${MODEL_PATH}" ]]; then
  echo "Error: Model path required" >&2
  usage >&2
  exit 2
fi

if [[ ! -f "${MODEL_PATH}" ]]; then
  echo -e "Error: Model file not found: ${MODEL_PATH}" >&2
  exit 2
fi

# Ensure provenance directory exists
mkdir -p "${PROVENANCE_DIR}"

# ── Safety Check 1: GGUF magic bytes ────────────────────────────────────────
# GGUF files start with the 4-byte magic "GGUF" (0x47475546 in little-endian)
gguf_magic="$(xxd -l 4 -p "${MODEL_PATH}" 2>/dev/null || echo "")"
if [[ "${gguf_magic}" != "46554747" ]]; then
  echo -e "ERROR: Invalid GGUF magic bytes. Expected 46554747 (GGUF), got: ${gguf_magic}" >&2
  echo -e "This file may not be a valid GGUF model." >&2
  exit 1
fi
echo -e "✓ GGUF magic bytes verified"

# ── Safety Check 2: Pickle magic byte scan ───────────────────────────────────
# Python pickle protocol 4-5 use \\x80\\x04 or \\x80\\x05 as the first two bytes.
# Malicious models could embed pickle payloads in metadata sections.
# We scan the first 4KB for these patterns.
first_4kb="$(xxd -l 4096 -p "${MODEL_PATH}" 2>/dev/null | tr -d '\n' || echo "")"

# Check for pickle protocol 4 (\\x80\\x04 = 8004 in hex)
if echo "${first_4kb}" | grep -q "8004"; then
  echo "ERROR: Pickle protocol 4 magic bytes (\\x80\\x04) detected in first 4KB" >&2
  echo "GGUF files should NOT contain pickle data. This model may be malicious." >&2
  exit 1
fi

# Check for pickle protocol 5 (\\x80\\x05 = 8005 in hex)
if echo "${first_4kb}" | grep -q "8005"; then
  echo "ERROR: Pickle protocol 5 magic bytes (\\x80\\x05) detected in first 4KB" >&2
  echo "GGUF files should NOT contain pickle data. This model may be malicious." >&2
  exit 1
fi
echo -e "✓ No pickle magic bytes detected in first 4KB"

# ── Safety Check 3: Basic file integrity ─────────────────────────────────────
file_size="$(stat -c%s "${MODEL_PATH}" 2>/dev/null || echo "0")"
if [[ "${file_size}" -lt 1048576 ]]; then
  echo -e "ERROR: Model file suspiciously small (${file_size} bytes). Expected >= 1MB for valid GGUF." >&2
  exit 1
fi
echo -e "✓ File size reasonable (${file_size} bytes)"

# ── Provenance Recording (Phase 11.3.1) ──────────────────────────────────────
# If HF_REPO is provided, record provenance metadata
model_basename="$(basename "${MODEL_PATH}")"
model_id="${model_basename%.gguf}"
provenance_file="${PROVENANCE_DIR}/provenance.json"

# Compute SHA256 of the model file
model_sha256="$(sha256sum "${MODEL_PATH}" | awk '{print $1}')"

# If HF_REPO and HF_COMMIT are provided, use them; otherwise try to fetch from HF API
hf_commit_to_record="${HF_COMMIT}"
hf_repo_to_record="${HF_REPO}"

if [[ -n "${HF_REPO}" && -n "${HF_COMMIT}" ]]; then
  echo -e "✓ Recording provenance with provided HF commit: ${HF_COMMIT}"
elif [[ -n "${HF_REPO}" ]]; then
  # Try to fetch latest commit from HF API
  echo -e "Fetching latest commit from HuggingFace API for ${HF_REPO}..."
  hf_commit_to_record="$(curl -sf "${HF_API_BASE}/repos/${HF_REPO}/revision/main" 2>/dev/null | jq -r '.oid // empty' || echo "")"
  if [[ -z "${hf_commit_to_record}" ]]; then
    echo -e "Warning: Could not fetch commit hash from HuggingFace API for ${HF_REPO}" >&2
    hf_commit_to_record="unknown"
  else
    echo -e "✓ Fetched HF commit: ${hf_commit_to_record}"
  fi
else
  echo -e "Note: No HuggingFace repo provided. Recording provenance without HF metadata." >&2
  hf_repo_to_record="unknown"
  hf_commit_to_record="unknown"
fi

# Create or update provenance file
timestamp="$(date -Iseconds)"

# Use jq to safely construct JSON
jq -n \
  --arg model "${model_id}" \
  --arg model_path "${MODEL_PATH}" \
  --arg sha256 "${model_sha256}" \
  --arg hf_repo "${hf_repo_to_record}" \
  --arg hf_commit "${hf_commit_to_record}" \
  --arg downloaded_at "${timestamp}" \
  --arg safety_check "passed" \
  '{
    model: $model,
    model_path: $model_path,
    sha256: $sha256,
    huggingface: {
      repo: $hf_repo,
      commit: $hf_commit
    },
    downloaded_at: $downloaded_at,
    safety_check: {
      status: $safety_check,
      checked_at: $downloaded_at,
      checks_performed: [
        "gguf_magic_bytes",
        "pickle_scan_first_4kb",
        "file_size_minimum"
      ]
    }
  }' > "${provenance_file}"

echo -e "✓ Provenance recorded: ${provenance_file}"
echo ""
echo -e "Model safety verification PASSED"
echo -e "  Model: ${model_id}"
echo -e "  SHA256: ${model_sha256}"
echo -e "  HF Repo: ${hf_repo_to_record}"
echo -e "  HF Commit: ${hf_commit_to_record}"

exit 0
