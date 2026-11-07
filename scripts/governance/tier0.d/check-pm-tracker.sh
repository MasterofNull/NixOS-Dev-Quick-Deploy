#!/usr/bin/env bash
# Tier0 extension: PM-tracker projection is valid on every commit.
# The rule "keep the gantt/kanban updated on every commit" is satisfied by CONSTRUCTION — status is
# PROJECTED live from ground truth by aq-pm-tracker (git + freeze records + activation grants + blockers),
# never a hand-maintained artifact that can rot. So the only per-commit obligation is: every plan's
# editorial manifest (<plan-dir>/tracker.json) stays VALID and projects. This gate enforces that (a broken
# or gamed manifest fails the commit). Missing-tracker-for-an-active-plan is a freshness-class WARN, never
# a hard block (Rule 19 gate-hygiene: block a regression the change introduces, not cosmetic absence).
set -euo pipefail

MODE="${1:---pre-commit}"
REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "${REPO_ROOT}"

TRACKER="scripts/ai/aq-pm-tracker"
REFACTOR_STATUS="scripts/ai/aq-refactor-status"
# Owner-acceptance gate (verified acceptance): UNCONDITIONAL, no SKIP. A missing projector or interpreter is a FAIL,
# not a pass: a check that could not run must never read green. BASELINE_SHA256 pins config/
# pm-tracker-unbacked-owner-acceptances.baseline.json; changing the baseline means editing this line (review-visible).
BASELINE_SHA256="20ef02f7295a7bd592db49af36c016f16c42240417a57f3f4e414df1d56c6f27"
if [[ ! -f "${TRACKER}" ]] || ! command -v python3 >/dev/null 2>&1; then
  echo "[tier0.d/check-pm-tracker] FAIL: projector or python3 unavailable; the owner-acceptance gate cannot run (no SKIP)"
  exit 1
fi

run_full_owner_acceptance() {
  python3 "${TRACKER}" --check-owner-acceptance --baseline-sha256 "${BASELINE_SHA256}" 2>&1
}

# Offline subset for --pre-commit: pinned-digest, strict parse, allowlist subset of baseline. These need no
# network; the full check (fetched origin/main merge-base and tip) is what a transient DNS failure broke.
offline_owner_acceptance() {
  BASELINE_SHA256="${BASELINE_SHA256}" python3 - <<'PY'
import hashlib, json, os, sys
base_f = "config/pm-tracker-unbacked-owner-acceptances.baseline.json"
allow_f = "config/pm-tracker-unbacked-owner-acceptances.json"
bad = []
def entries(path):
    try:
        raw = open(path, "rb").read()
        d = json.loads(raw)
        return raw, {(e["plan"], e["item"], e["acceptance_sha256"]) for e in d["entries"]}
    except FileNotFoundError:
        return None, None
    except Exception as exc:
        bad.append(f"{path} unparsable: {exc}")
        return None, None
braw, bset = entries(base_f)
araw, aset = entries(allow_f)
if braw is not None and hashlib.sha256(braw).hexdigest() != os.environ["BASELINE_SHA256"]:
    bad.append(f"{base_f} sha256 differs from the pinned literal in the gate")
if bset is not None and aset is not None and not aset <= bset:
    bad.append("allowlist has tuples that are not in the frozen baseline: " + ", ".join(sorted(f"{a}:{b}" for a, b, _ in aset - bset)))
if bad:
    print("\n".join(bad)); sys.exit(1)
PY
}

# `--owner-acceptance`: only the full fail-closed check (used by pre-push, which has just fetched). It never
# passes offline: an unreachable origin is a FAIL.
if [[ "${MODE}" == "--owner-acceptance" ]]; then
  if out="$(run_full_owner_acceptance)"; then
    echo "[tier0.d/check-pm-tracker] PASS: owner-acceptance (full, fetched origin/main)"; exit 0
  fi
  echo "[tier0.d/check-pm-tracker] FAIL: owner acceptances must be backed by an approval_ref or the frozen remove-only allowlist:"
  echo "${out}" | sed 's/^/    /'
  exit 1
fi

fail=0
# Stage placement: the full check fetches origin/main, so it runs where a network is expected (CI via tier0 --ci,
# --pre-deploy, --maintenance, and pre-push). Local --pre-commit keeps the offline subset only.
if [[ "${MODE}" == "--pre-commit" && "${TIER0_CI:-0}" != "1" ]]; then
  if ! owner_out="$(offline_owner_acceptance 2>&1)"; then
    echo "[tier0.d/check-pm-tracker] FAIL: owner-acceptance baseline/allowlist (offline subset):"
    echo "${owner_out}" | sed 's/^/    /'
    fail=1
  fi
elif ! owner_out="$(run_full_owner_acceptance)"; then
  echo "[tier0.d/check-pm-tracker] FAIL: owner acceptances must be backed by an approval_ref or the frozen remove-only allowlist:"
  echo "${owner_out}" | sed 's/^/    /'
  fail=1
fi
shopt -s nullglob
manifests=(.agents/plans/*/tracker.json)
if [[ ${#manifests[@]} -eq 0 ]]; then
  echo "[tier0.d/check-pm-tracker] no plan trackers yet (nothing to project)"
  exit "${fail}"
fi

for m in "${manifests[@]}"; do
  plan_dir="$(dirname "${m}")"
  if out="$(python3 "${TRACKER}" "${plan_dir}" --check 2>&1)"; then
    :
  else
    echo "[tier0.d/check-pm-tracker] FAIL: ${plan_dir}/tracker.json does not validate/project:"
    echo "${out}" | sed 's/^/    /'
    fail=1
  fi
done

if ! allow_out="$(python3 "${TRACKER}" --check-legacy-allowlist 2>&1)"; then
  echo "[tier0.d/check-pm-tracker] FAIL: legacy acceptance allowlist is remove-only:"
  echo "${allow_out}" | sed 's/^/    /'
  fail=1
fi

if ! items_out="$(python3 "${TRACKER}" --check-untrusted-items 2>&1)"; then
  echo "[tier0.d/check-pm-tracker] FAIL: untrusted-provenance items list is remove-only (removal needs a cleared hold):"
  echo "${items_out}" | sed 's/^/    /'
  fail=1
fi

# The current refactor rundown is an operator-facing projection, not a second
# owner-gate source of truth.  Fail if it says an owner decision is pending
# after the ratification/projector has resolved that gate.  Historical plans
# are deliberately outside this check; the manifest names the one current
# rundown that must stay synchronized.
if [[ -x "${REFACTOR_STATUS}" ]]; then
  if ! refactor_out="$(python3 "${REFACTOR_STATUS}" --check-owner-gates 2>&1)"; then
    echo "[tier0.d/check-pm-tracker] FAIL: refactor owner-gate reconciliation:"
    echo "${refactor_out}" | sed 's/^/    /'
    fail=1
  fi
else
  echo "[tier0.d/check-pm-tracker] FAIL: refactor owner-gate projector unavailable"
  fail=1
fi

# Freshness-class WARN (never a hard block): a plan dir with staged changes this commit but no tracker.json.
if [[ "${MODE}" == "--pre-commit" ]]; then
  while IFS= read -r changed; do
    [[ -z "${changed}" ]] && continue
    case "${changed}" in
      .agents/plans/*/*)
        pd="$(echo "${changed}" | cut -d/ -f1-3)"
        [[ -f "${pd}/tracker.json" ]] || echo "[tier0.d/check-pm-tracker] WARN: ${pd} has changes but no tracker.json (consider adding one so its progress projects)"
        ;;
    esac
  done < <(git diff --cached --name-only 2>/dev/null | sort -u) 2>/dev/null || true
fi

if [[ "${fail}" -eq 0 ]]; then
  echo "[tier0.d/check-pm-tracker] PASS: ${#manifests[@]} plan tracker(s) valid + projecting from ground truth"
fi
exit "${fail}"
