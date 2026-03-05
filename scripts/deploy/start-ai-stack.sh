#!/usr/bin/env bash
set -euo pipefail

exec systemctl start ai-stack.target
