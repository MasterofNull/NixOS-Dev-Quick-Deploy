#!/usr/bin/env bash
# Smoke test for capabilities kept/revived by the 2026-10-09 dead-capability triage.
# No DB, AIDB, Qdrant or inference calls: syntax checks, --help, and tmp-dir dry-runs only.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
fail=0
ok() { printf 'PASS %s\n' "$1"; }
bad() { printf 'FAIL %s\n' "$1"; fail=1; }
chk() { local d="$1"; shift; if "$@" >/dev/null 2>&1; then ok "$d"; else bad "$d"; fi; }

for f in scripts/ai/cli-enhanced.sh scripts/ai/resume-model-download.sh scripts/ai/aq-enrich-plans \
         scripts/ai/ai-metrics-auto-updater.sh scripts/ai/ai-model-setup.sh scripts/ai/ai-stack-e2e-test.sh \
         scripts/ai/ai-stack-feature-scenario.sh scripts/ai/ai-stack-resume-recovery.sh \
         scripts/ai/ai-stack-troubleshoot.sh scripts/ai/llama-model-cli.sh; do
  chk "bash -n $f" bash -n "$f"
done
for f in scripts/ai/cli-utils.py scripts/ai/aq-propose scripts/ai/aq-factory scripts/ai/aq-skill-factory \
         scripts/ai/backfill-interaction-history-qdrant.py scripts/ai/generate-module-dashboard.py; do
  chk "py_compile $f" python3 -m py_compile "$f"
done
chk "aq-enrich-plans --help" bash scripts/ai/aq-enrich-plans --help
chk "aq-propose --help" python3 scripts/ai/aq-propose --help
chk "aq-factory --help" python3 scripts/ai/aq-factory --help
chk "aq-skill-factory --help" python3 scripts/ai/aq-skill-factory --help
chk "backfill-interaction-history-qdrant --help" python3 scripts/ai/backfill-interaction-history-qdrant.py --help
chk "resume-model-download --dry-run" bash scripts/ai/resume-model-download.sh --dry-run
for s in ai-metrics-auto-updater ai-model-setup ai-stack-e2e-test ai-stack-feature-scenario ai-stack-resume-recovery; do
  chk "$s --help" bash "scripts/ai/$s.sh" --help
done
chk "llama-model-cli help" bash scripts/ai/llama-model-cli.sh help

T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
chk "aq-factory scaffolds frontmatter" bash -c "python3 scripts/ai/aq-factory smoke-skill 'smoke purpose' --root '$T' && head -2 '$T/smoke-skill/SKILL.md' | grep -q '^name: smoke-skill'"
chk "generate-module-dashboard --out-dir" bash -c "python3 scripts/ai/generate-module-dashboard.py --out-dir '$T/m' && ls '$T/m'/*.html"
chk "cli-utils humanize_bytes" python3 -c "
import importlib.util as u
s=u.spec_from_file_location('cu','scripts/ai/cli-utils.py'); m=u.module_from_spec(s); s.loader.exec_module(m)
assert m.humanize_bytes(2048)=='2.0KB' and m.humanize_duration(90)=='1.5m'"
chk "cli-enhanced humanize_bytes" bash -c "source scripts/ai/cli-enhanced.sh && [ -n \"\$(humanize_bytes 2048)\" ]"
chk "static_rules hint ids present" python3 -c "
import sys; sys.path.insert(0,'ai-stack/mcp-servers/hybrid-coordinator/knowledge')
import static_rules as s; ids={r['id'] for r in s.STATIC_RULES}
need={'annotate_plans_with_tools','generate_improvement_proposals','cli_output_helpers','scaffold_new_skill','backfill_interaction_history_qdrant','regenerate_module_dashboard_pages','resume_interrupted_model_download','legacy_ai_stack_script_names'}
assert need<=ids"
exit "$fail"
