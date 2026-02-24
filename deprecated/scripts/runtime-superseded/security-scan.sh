#!/usr/bin/env bash
set -euo pipefail

OUTPUT_DIR="data"
OUTPUT_FILE="${OUTPUT_DIR}/security-scan-$(date +%Y-%m-%d).txt"

mkdir -p "$OUTPUT_DIR"

images=$(podman ps --format '{{.Image}}' | sort -u)
if [[ -z "$images" ]]; then
  echo "No running images found"
  exit 1
fi

: > "$OUTPUT_FILE"

while IFS= read -r img; do
  echo "=== ${img} ===" >> "$OUTPUT_FILE"
  trivy image --scanners vuln --severity HIGH,CRITICAL --ignore-unfixed --skip-version-check --timeout 5m "$img" >> "$OUTPUT_FILE"
  echo >> "$OUTPUT_FILE"
done <<< "$images"

echo "Wrote scan results to ${OUTPUT_FILE}"
