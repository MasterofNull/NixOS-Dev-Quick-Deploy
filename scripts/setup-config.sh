#!/usr/bin/env bash
#
# Initialize AI stack .env from template if missing.
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TEMPLATE_ENV="${PROJECT_ROOT}/templates/local-ai-stack/.env.example"
TARGET_ENV="${AI_STACK_ENV_FILE:-$HOME/.config/nixos-ai-stack/.env}"

if [[ -f "$TARGET_ENV" ]]; then
  echo "AI stack env already exists: $TARGET_ENV"
  exit 0
fi

if [[ ! -f "$TEMPLATE_ENV" ]]; then
  echo "Template env not found: $TEMPLATE_ENV" >&2
  exit 1
fi

mkdir -p "$(dirname "$TARGET_ENV")"
cp "$TEMPLATE_ENV" "$TARGET_ENV"

home_placeholder="/${HOME_ROOT_DIR:-home}/your-user"
sed -i "s|${home_placeholder}|$HOME|g" "$TARGET_ENV"

echo "Created AI stack env: $TARGET_ENV"
echo "Review and update POSTGRES_PASSWORD and other secrets before starting the stack."
