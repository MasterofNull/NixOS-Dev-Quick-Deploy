# Dependency audit recovery

The hosted Security Configuration Audit ran Python 3.11 after the AIDB manifest raised its NumPy floor to 2.5.5. NumPy 2.5.5 requires Python 3.12 or newer. The hosted audit reported two completed scans and one failure, and the downstream Nix closure job was skipped. See the [hosted audit failure](https://github.com/MasterofNull/NixOS-Dev-Quick-Deploy/actions/runs/44676436398/job/136089273802) and [NumPy package metadata](https://pypi.org/project/numpy/2.5.5/).

The workflow now reads the Python 3.13 baseline from `.python-version`. The audit reports the repository-relative path for a failed manifest and distinguishes an unexpected scanner exit from a rejected report. The scanner regression suite covers unexpected exits, rejected reports, and a manifest path containing a newline and Markdown delimiters. The audit preserves each discovered path and encodes it before publication. Scanner stderr stays out of the published failure line and incomplete coverage still blocks CI. YAML parsing and shell syntax checks passed.

A local CI-mode run with Python 3.13 and pip-audit 2.10.1 completed all three scans with `blocking=0` and `status=ok`. Two expired exception entries were reported and were not applied.

Hosted acceptance requires three completed scans, covering AIDB, hybrid-coordinator, and nixos-docs. Read the audit artifact alongside the job conclusion because advisory findings can block the job after coverage is restored. Check the downstream Nix closure result separately. Record the hosted results and independent planning and code reviews on the recovery PR.

Release evidence covers the focused CI recovery. Deployment validation, Dependabot workflow changes, and individual dependency PR remediation are tracked through their respective PRs.
