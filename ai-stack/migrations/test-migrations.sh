#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

alembic -c "${ROOT_DIR}/migrations/alembic.ini" upgrade head
alembic -c "${ROOT_DIR}/migrations/alembic.ini" downgrade -1
alembic -c "${ROOT_DIR}/migrations/alembic.ini" upgrade head
