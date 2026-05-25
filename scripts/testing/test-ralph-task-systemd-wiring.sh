#!/usr/bin/env bash
# Guard Ralph timer units against minimal systemd PATH failures.
set -euo pipefail

module="nix/modules/roles/ai-stack.nix"
helper="scripts/ai/aq-ralph-task"

grep -q 'export PATH="/run/current-system/sw/bin:/usr/bin:/bin:${PATH:-}"' "$helper" \
  || { echo "FAIL: aq-ralph-task must set a runtime PATH for curl/jq dependencies"; exit 1; }

count="$(grep -c 'ExecStart = "${pkgs.bash}/bin/bash ${cfg.mcpServers.repoPath}/scripts/ai/aq-ralph-task' "$module")"
if [[ "$count" -lt 4 ]]; then
  echo "FAIL: expected Ralph timer ExecStart entries to invoke aq-ralph-task through pkgs.bash, got ${count}"
  exit 1
fi

echo "PASS: Ralph task systemd wiring"
