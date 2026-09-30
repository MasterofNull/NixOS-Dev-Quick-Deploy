#!/usr/bin/env bash
# Guard Ralph timer units against minimal systemd PATH failures.
set -euo pipefail

module="nix/modules/roles/ai-stack.nix"
helper="scripts/ai/aq-ralph-task"

grep -q 'export PATH="/run/current-system/sw/bin:/usr/bin:/bin:${PATH:-}"' "$helper" \
  || { echo "FAIL: aq-ralph-task must set a runtime PATH for curl/jq dependencies"; exit 1; }

count="$(grep -c 'ExecStart = "${pkgs.bash}/bin/bash ${cfg.mcpServers.repoPath}/scripts/ai/aq-ralph-task' "$module")"
total="$(grep 'ExecStart = ' "$module" | grep -c '/scripts/ai/aq-ralph-task')"
if [[ "$count" -lt 1 || "$count" -ne "$total" ]]; then
  echo "FAIL: expected Ralph timer ExecStart entries to invoke aq-ralph-task through pkgs.bash, got ${count}"
  exit 1
fi

prsi_block="$(sed -n '/systemd.services.ai-prsi-orchestrator = {/,/systemd.timers.ai-prsi-orchestrator/p' "$module")"
if grep -q 'aq-ralph-task' <<<"$(grep 'ExecStart = ' <<<"$prsi_block")"; then
  echo "FAIL: deterministic PRSI orchestration must not queue an LLM task"
  exit 1
fi
grep -q 'ExecStart = "${pkgs.python3}/bin/python3 ${cfg.mcpServers.repoPath}/scripts/automation/prsi-orchestrator.py cycle' <<<"$prsi_block" \
  || { echo "FAIL: PRSI must invoke its Python orchestrator directly"; exit 1; }

grep -q 'rsi-dispatch --execute --apply --limit=1' "$module" \
  || { echo "FAIL: incident dispatch must remain bounded to one isolated repair per run"; exit 1; }
grep -q 'AQ_DELEGATION_DIR=${mutableOptimizerDir}/prsi/delegation' "$module" \
  || { echo "FAIL: PRSI repair must use its writable delegation root"; exit 1; }
grep -q 'systemd.paths.ai-prsi-rsi-dispatch' "$module" \
  || { echo "FAIL: PRSI incidents must wake the repair dispatcher"; exit 1; }
grep -q 'systemd.timers.ai-prsi-rsi-dispatch' "$module" \
  || { echo "FAIL: PRSI queue needs a periodic missed-event sweep"; exit 1; }

context_block="$(sed -n '/systemd.services.ai-context-warmer/,/systemd.timers.ai-context-warmer/p' "$module")"
if grep -q 'aq-ralph-task' <<<"$context_block"; then
  echo "FAIL: ai-context-warmer must run aq-context-warm directly, not queue a Ralph task"
  exit 1
fi

echo "PASS: Ralph task systemd wiring"
