#!/usr/bin/env bash
# tier0 log_failed_qa_rows prints each failed check's reason from aq-qa's progress
# JSONL, even when the rendered table row truncates the description.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
log() { printf '[tier0] %s\n' "$*"; }
eval "$(sed -n '/^log_failed_qa_rows() {/,/^}/p' "$ROOT/scripts/governance/tier0-validation-gate.sh")"
cat > "$TMP/p.jsonl" <<'J'
{"state":"running","check_id":"0.10.48","detail":null}
{"state":"fail","check_id":"0.10.48","detail":"fixture timed out after 90s"}
{"state":"fail","check_id":"0.2.1:aidb","detail":"port 8002 not bound"}
{"state":"pass","check_id":"0.10.49","detail":null}
J
rows=$'  │       │ 0.10.48                      │ delegation worktree          │   ✗    │\n  │ L2    │ 0.2.1:aidb                   │ port 8002 (aidb) bound       │   ✗    │'
out="$(REPO_ROOT="$TMP" AQ_QA_PROGRESS_JSONL="$TMP/p.jsonl" log_failed_qa_rows "$rows" 30)"
grep -q "↳ fixture timed out after 90s" <<< "$out" || { echo "FAIL: 0.10.48 detail missing"; echo "$out"; exit 1; }
grep -q "↳ port 8002 not bound" <<< "$out" || { echo "FAIL: 0.2.1:aidb detail missing"; echo "$out"; exit 1; }
out2="$(REPO_ROOT="$TMP" AQ_QA_PROGRESS_JSONL="$TMP/missing.jsonl" log_failed_qa_rows "$rows" 30)"
grep -q "0.10.48" <<< "$out2" && ! grep -q "↳" <<< "$out2" || { echo "FAIL: missing progress file must still print rows"; exit 1; }
echo "PASS: tier0 failed QA rows carry their reason from progress JSONL"
