#!/usr/bin/env python3
"""
Test that CI skill bundle distribution smoke job has test step.

Verifies that the workflow has:
1. A skill-bundle-parity job
2. The job has a test step
3. The test step runs the smoke check script
"""

import sys
import yaml
from pathlib import Path

def get_test_root():
    """Find the repository root."""
    script_dir = Path(__file__).resolve().parent
    return script_dir.parent.parent

def test_skill_bundle_job_exists():
    """Verify that skill-bundle-parity job exists."""
    repo_root = get_test_root()
    workflow_file = repo_root / ".github" / "workflows" / "test.yml"

    with open(workflow_file) as f:
        workflow = yaml.safe_load(f)

    assert 'jobs' in workflow, "Workflow should have jobs section"
    assert 'skill-bundle-parity' in workflow['jobs'], \
        "Workflow should have skill-bundle-parity job"

def test_skill_bundle_job_has_test_step():
    """Verify that skill-bundle-parity job has a test step."""
    repo_root = get_test_root()
    workflow_file = repo_root / ".github" / "workflows" / "test.yml"

    with open(workflow_file) as f:
        workflow = yaml.safe_load(f)

    job = workflow['jobs']['skill-bundle-parity']
    assert 'steps' in job, "Job should have steps"

    steps = job['steps']
    assert len(steps) > 0, "Job should have at least one step"

    # Look for a step that runs the smoke check
    test_steps = [s for s in steps if 'run' in s and 'smoke' in s.get('run', '').lower()]
    assert len(test_steps) > 0, \
        "Job should have a step that runs the smoke check script"

def test_skill_bundle_job_runs_correct_script():
    """Verify that the correct smoke check script is run."""
    repo_root = get_test_root()
    workflow_file = repo_root / ".github" / "workflows" / "test.yml"

    with open(workflow_file) as f:
        workflow = yaml.safe_load(f)

    job = workflow['jobs']['skill-bundle-parity']
    steps = job['steps']

    # Find the test step
    test_step = None
    for s in steps:
        if 'run' in s and 'smoke-skill-bundle-distribution.sh' in s.get('run', ''):
            test_step = s
            break

    assert test_step is not None, \
        "Should have a step running smoke-skill-bundle-distribution.sh"

    assert 'scripts/testing/smoke-skill-bundle-distribution.sh' in test_step['run'], \
        "Should run the smoke check script from scripts/testing (live tool test; not archived)"

def test_skill_bundle_job_has_dependencies():
    """Verify that the job has correct dependencies."""
    repo_root = get_test_root()
    workflow_file = repo_root / ".github" / "workflows" / "test.yml"

    with open(workflow_file) as f:
        workflow = yaml.safe_load(f)

    job = workflow['jobs']['skill-bundle-parity']

    assert 'needs' in job, "Job should have dependencies"
    needs = job['needs'] if isinstance(job['needs'], list) else [job['needs']]
    assert 'syntax' in needs, "Job should depend on syntax check"

def test_smoke_script_exists():
    """Verify that the smoke check script exists."""
    repo_root = get_test_root()
    script_file = repo_root / "scripts" / "testing" / "smoke-skill-bundle-distribution.sh"

    assert script_file.exists(), \
        f"Smoke check script should exist at {script_file}"

if __name__ == "__main__":
    print("Testing skill bundle job exists...")
    test_skill_bundle_job_exists()
    print("✓ Skill bundle job exists test passed")

    print("Testing skill bundle job has test step...")
    test_skill_bundle_job_has_test_step()
    print("✓ Skill bundle job test step test passed")

    print("Testing skill bundle job runs correct script...")
    test_skill_bundle_job_runs_correct_script()
    print("✓ Skill bundle job correct script test passed")

    print("Testing skill bundle job has dependencies...")
    test_skill_bundle_job_has_dependencies()
    print("✓ Skill bundle job dependencies test passed")

    print("Testing smoke script exists...")
    test_smoke_script_exists()
    print("✓ Smoke script exists test passed")

    print("\nAll tests passed!")
    sys.exit(0)
