#!/usr/bin/env bash
set -euo pipefail

bundle_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
work_dir="$(mktemp -d "${TMPDIR:-/tmp}/factory-gate-self-test.XXXXXXXX")"
target="${work_dir}/target"
mkdir -p "${target}/.factory" "${target}/src" "${target}/tests" "${target}/.agents/plans/sample"
git -C "${target}" init -q -b main
git -C "${target}" config user.name "Factory Author"
git -C "${target}" config user.email "author@example.invalid"
printf 'required=src\nrequired=tests\n' >"${target}/.factory/repo-structure.conf"

FACTORY_REPO_ROOT="${target}" \
FACTORY_STRUCTURE_POLICY="${target}/.factory/repo-structure.conf" \
FACTORY_SECRET_SCAN_NOT_APPLICABLE=1 \
FACTORY_BUILD_NOT_APPLICABLE=1 \
FACTORY_TEST_NOT_APPLICABLE=1 \
FACTORY_LINT_NOT_APPLICABLE=1 \
FACTORY_LIVE_SERVICE_NOT_APPLICABLE=1 \
FACTORY_FRESHNESS_NOT_APPLICABLE=1 \
  "${bundle_root}/gate-runner" --pre-commit >/dev/null
echo "PASS: generic checks.d discovery and pre-commit run"

unconfigured_checks="${work_dir}/unconfigured-checks"
mkdir -p "${unconfigured_checks}"
cp "${bundle_root}/checks.d/hard-30-build.sh" "${unconfigured_checks}/hard-30-build.sh"
chmod +x "${unconfigured_checks}/hard-30-build.sh"
if FACTORY_GATE_CHECKS_DIR="${unconfigured_checks}" "${bundle_root}/gate-runner" --pre-commit >"${work_dir}/unconfigured.out" 2>&1; then
  echo "FAIL: unresolved required check passed" >&2
  exit 1
fi
grep -qx 'UNCONFIGURED: hard-30-build' "${work_dir}/unconfigured.out"
echo "PASS: unresolved required checks are typed UNCONFIGURED and fail closed"

severity_checks="${work_dir}/severity-checks"
mkdir -p "${severity_checks}"
cat >"${severity_checks}/live-10-synthetic.sh" <<'EOF'
#!/usr/bin/env bash
exit 1
EOF
chmod +x "${severity_checks}/live-10-synthetic.sh"
FACTORY_GATE_CHECKS_DIR="${severity_checks}" "${bundle_root}/gate-runner" --pre-commit >/dev/null 2>&1
if FACTORY_GATE_CHECKS_DIR="${severity_checks}" "${bundle_root}/gate-runner" --pre-deploy >/dev/null 2>&1; then
  echo "FAIL: live failure did not harden for pre-deploy" >&2
  exit 1
fi
echo "PASS: live/freshness severity corollary"

rendered_hook="${work_dir}/commit-msg"
sed 's/{{PROTECTED_BRANCHES}}/main/g' "${bundle_root}/hooks/commit-msg" >"${rendered_hook}"
chmod +x "${rendered_hook}"
printf 'subject\n' >"${target}/subject.txt"
git -C "${target}" add subject.txt
subject_sha="$(git -C "${target}" diff --cached --binary --full-index --no-ext-diff -- | sha256sum | awk '{print $1}')"

printf 'test(factory): missing review\n' >"${work_dir}/message"
if git -C "${target}" -c core.hooksPath=/dev/null var GIT_AUTHOR_IDENT >/dev/null \
    && (cd "${target}" && "${rendered_hook}" "${work_dir}/message") >/dev/null 2>&1; then
  echo "FAIL: commit-msg accepted missing review trailers" >&2
  exit 1
fi
cat >"${work_dir}/message" <<EOF
test(factory): wrong hash

Independent-Review: PASS
Reviewed-subject-sha256: 0000000000000000000000000000000000000000000000000000000000000000
Reviewed-by: Factory Reviewer <reviewer@example.invalid>
Review-Disposition: ACCEPTED
EOF
if (cd "${target}" && "${rendered_hook}" "${work_dir}/message") >/dev/null 2>&1; then
  echo "FAIL: commit-msg accepted an unbound review" >&2
  exit 1
fi
cat >"${work_dir}/message" <<EOF
test(factory): self review

Independent-Review: PASS
Reviewed-subject-sha256: ${subject_sha}
Reviewed-by: Factory Author <author@example.invalid>
Review-Disposition: ACCEPTED
EOF
if (cd "${target}" && "${rendered_hook}" "${work_dir}/message") >/dev/null 2>&1; then
  echo "FAIL: commit-msg accepted author self-review" >&2
  exit 1
fi
cat >"${work_dir}/message" <<EOF
test(factory): bound review

Independent-Review: PASS
Reviewed-subject-sha256: ${subject_sha}
Reviewed-by: Factory Reviewer <reviewer@example.invalid>
Review-Disposition: ACCEPTED
EOF
(cd "${target}" && "${rendered_hook}" "${work_dir}/message")
echo "PASS: commit-msg rejects missing, unbound, and author reviews; accepts bound independent review"

cp "${bundle_root}/pm-tracker/sample/tracker.json" "${target}/.agents/plans/sample/tracker.json"
FACTORY_REPO_ROOT="${target}" python3 "${bundle_root}/pm-tracker/projector.py" \
  "${target}/.agents/plans/sample" --check >/dev/null
echo "PASS: PM tracker sample validates and projects"

cat >"${target}/.agents/plans/sample/tracker.json" <<'EOF'
{"plan":{"id":"sample","title":"Sample","goal":"Proof"},"items":[{"id":"FT-1","goal":"Proof","validation_goal":"Validate","deps":[],"detection":{"commit_match":["missing-git-evidence"]},"pct_hint":100,"acceptance":{"status":"accepted"}}]}
EOF
projection="$(FACTORY_REPO_ROOT="${target}" python3 "${bundle_root}/pm-tracker/projector.py" "${target}/.agents/plans/sample")"
if printf '%s\n' "${projection}" | grep -q '"status": "SHIPPED"'; then
  echo "FAIL: editorial acceptance produced SHIPPED without git evidence" >&2
  exit 1
fi
cat >"${target}/.agents/plans/sample/tracker.json" <<'EOF'
{"plan":{"id":1,"title":"Sample","goal":"Proof"},"items":[{"id":"FT-1","goal":"Proof","validation_goal":"Validate","deps":"none","detection":{"commit_match":"bad"},"pct_hint":101}]}
EOF
if FACTORY_REPO_ROOT="${target}" python3 "${bundle_root}/pm-tracker/projector.py" "${target}/.agents/plans/sample" --check >/dev/null 2>&1; then
  echo "FAIL: projector accepted invalid schema types and bounds" >&2
  exit 1
fi
echo "PASS: projector rejects invalid types/bounds and requires git evidence for SHIPPED"

python3 - "${bundle_root}" <<'PY'
import json
import re
import sys
from pathlib import Path

root = Path(sys.argv[1])
manifest = json.loads((root / "MANIFEST.json").read_text(encoding="utf-8"))
declared = {entry["bundle_path"] for entry in manifest["files"] if entry["bundle_path"] != "."}
actual = {
    str(path.relative_to(root)) for path in root.rglob("*")
    if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
}
if declared != actual:
    raise SystemExit(f"manifest mismatch: missing={sorted(actual-declared)} extra={sorted(declared-actual)}")
for entry in manifest["files"]:
    if not entry.get("install_target") or Path(entry["install_target"]).is_absolute():
        raise SystemExit(f"invalid install target for {entry['bundle_path']}")
    if not entry.get("derived_from"):
        raise SystemExit(f"missing derivation for {entry['bundle_path']}")
targets = [entry["install_target"] for entry in manifest["files"]]
if len(targets) != len(set(targets)):
    raise SystemExit("manifest install targets must be unique")
declared_placeholders = set(manifest["placeholders"])
used_placeholders = set()
for path in root.rglob("*"):
    if (
        path.is_file()
        and path.name != "MANIFEST.json"
        and "__pycache__" not in path.parts
        and path.suffix != ".pyc"
    ):
        used_placeholders.update(re.findall(r"\{\{([A-Z0-9_]+)\}\}", path.read_text(encoding="utf-8")))
if used_placeholders != declared_placeholders:
    raise SystemExit(
        f"placeholder mismatch: undeclared={sorted(used_placeholders-declared_placeholders)} "
        f"unused={sorted(declared_placeholders-used_placeholders)}"
    )
print(f"PASS: manifest resolves all {len(actual)} bundle files")
PY

python3 - "${bundle_root}" "${target}" <<'PY'
import json
import shutil
import sys
from pathlib import Path

root, target = map(Path, sys.argv[1:])
manifest = json.loads((root / "MANIFEST.json").read_text(encoding="utf-8"))
for entry in manifest["files"]:
    source = root / entry["bundle_path"]
    if "__pycache__" in source.parts or source.suffix == ".pyc":
        continue
    destination = target / entry["install_target"]
    if source.is_dir():
        shutil.copytree(
            source, destination, dirs_exist_ok=True,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        continue
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
print("PASS: manifest installs every declared file into a temporary repository")
PY
cat >"${target}/.factory/repo-structure.conf" <<'EOF'
required=src
required=tests
allowed_top=.agent
allowed_top=.agents
allowed_top=.factory
allowed_top=.githooks
allowed_top=AGENTS.md
allowed_top=CLAUDE.md
allowed_top=scripts
allowed_top=src
allowed_top=subject.txt
allowed_top=tests
EOF
installed_gate="${target}/scripts/governance/gate-runner"
installed_checks="${target}/scripts/governance/checks.d"
installed_pm="${installed_checks}/hard-80-pm-tracker.sh"
pm_env=(
  FACTORY_REPO_ROOT="${target}"
  FACTORY_PM_TRACKER="${target}/scripts/pm-tracker"
  FACTORY_PLAN_ROOT="${target}/.agents/plans"
)
if env "${pm_env[@]}" "${installed_pm}" >"${work_dir}/installed-pm-invalid.out" 2>&1; then
  echo "FAIL: installed PM checker accepted an invalid discovered tracker" >&2
  exit 1
fi
if grep -q 'PASS (0 tracker(s))' "${work_dir}/installed-pm-invalid.out"; then
  echo "FAIL: installed PM checker failed to discover the existing tracker" >&2
  exit 1
fi
if FACTORY_GATE_CHECKS_DIR="${installed_checks}" \
FACTORY_REPO_ROOT="${target}" \
FACTORY_STRUCTURE_POLICY="${target}/.factory/repo-structure.conf" \
FACTORY_PM_TRACKER="${target}/scripts/pm-tracker" \
FACTORY_PLAN_ROOT="${target}/.agents/plans" \
FACTORY_SECRET_SCAN_NOT_APPLICABLE=1 \
FACTORY_BUILD_NOT_APPLICABLE=1 \
FACTORY_TEST_NOT_APPLICABLE=1 \
FACTORY_LINT_NOT_APPLICABLE=1 \
FACTORY_LIVE_SERVICE_NOT_APPLICABLE=1 \
FACTORY_FRESHNESS_NOT_APPLICABLE=1 \
  "${installed_gate}" --pre-commit >/dev/null 2>&1; then
  echo "FAIL: installed gate accepted an invalid discovered tracker" >&2
  exit 1
fi
cp "${bundle_root}/pm-tracker/sample/tracker.json" "${target}/.agents/plans/sample/tracker.json"
if ! env "${pm_env[@]}" "${installed_pm}" >"${work_dir}/installed-pm-valid.out"; then
  echo "FAIL: installed PM checker rejected valid sample" >&2
  exit 1
fi
grep -qx 'pm-tracker: PASS (1 tracker(s))' "${work_dir}/installed-pm-valid.out"
FACTORY_GATE_CHECKS_DIR="${installed_checks}" \
FACTORY_REPO_ROOT="${target}" \
FACTORY_STRUCTURE_POLICY="${target}/.factory/repo-structure.conf" \
FACTORY_PM_TRACKER="${target}/scripts/pm-tracker" \
FACTORY_PLAN_ROOT="${target}/.agents/plans" \
FACTORY_SECRET_SCAN_NOT_APPLICABLE=1 \
FACTORY_BUILD_NOT_APPLICABLE=1 \
FACTORY_TEST_NOT_APPLICABLE=1 \
FACTORY_LINT_NOT_APPLICABLE=1 \
FACTORY_LIVE_SERVICE_NOT_APPLICABLE=1 \
FACTORY_FRESHNESS_NOT_APPLICABLE=1 \
  "${installed_gate}" --pre-commit >/dev/null
echo "PASS: installed PM checker discovers trackers and rejects invalid input"
if [[ -z "${FACTORY_GATE_SELF_TEST_INSTALLED:-}" ]]; then
  FACTORY_GATE_SELF_TEST_INSTALLED=1 "${target}/.factory/gate-bundle/self-test.sh" >/dev/null
fi
echo "PASS: installed manifest paths and self-test execute in a temporary repository"

echo "SELF-TEST PASS"
echo "Temporary fixture retained at ${work_dir}"
