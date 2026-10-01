#!/usr/bin/env python3
"""
Test that Trivy SARIF results are uploaded to GitHub Security.

Verifies that:
1. The trivy-scan-core job uploads SARIF to GitHub Security
2. The upload uses the correct action
3. The upload has proper conditions
"""

import sys
import yaml
from pathlib import Path

def get_test_root():
    """Find the repository root."""
    script_dir = Path(__file__).resolve().parent
    return script_dir.parent.parent

def test_trivy_scan_core_job_exists():
    """Verify that trivy-scan-core job exists."""
    repo_root = get_test_root()
    workflow_file = repo_root / ".github" / "workflows" / "security.yml"

    with open(workflow_file) as f:
        workflow = yaml.safe_load(f)

    assert 'jobs' in workflow, "Workflow should have jobs section"
    assert 'trivy-scan-core' in workflow['jobs'], \
        "Workflow should have trivy-scan-core job"

def test_trivy_scan_core_has_sarif_upload():
    """Verify that trivy-scan-core job uploads SARIF to GitHub Security."""
    repo_root = get_test_root()
    workflow_file = repo_root / ".github" / "workflows" / "security.yml"

    with open(workflow_file) as f:
        workflow = yaml.safe_load(f)

    job = workflow['jobs']['trivy-scan-core']
    assert 'steps' in job, "Job should have steps"

    steps = job['steps']

    # Look for codeql-action/upload-sarif
    upload_steps = [s for s in steps if 'uses' in s and 'codeql-action/upload-sarif' in s['uses']]
    assert len(upload_steps) > 0, \
        "Job should have a step that uploads SARIF using codeql-action/upload-sarif"

def test_sarif_upload_has_correct_parameters():
    """Verify that SARIF upload has correct parameters."""
    repo_root = get_test_root()
    workflow_file = repo_root / ".github" / "workflows" / "security.yml"

    with open(workflow_file) as f:
        workflow = yaml.safe_load(f)

    job = workflow['jobs']['trivy-scan-core']
    steps = job['steps']

    # Find the codeql-action/upload-sarif step
    upload_step = None
    for s in steps:
        if 'uses' in s and 'codeql-action/upload-sarif' in s['uses']:
            upload_step = s
            break

    assert upload_step is not None, "SARIF upload step should exist"
    assert 'with' in upload_step, "Upload step should have 'with' parameters"

    with_params = upload_step['with']
    assert 'sarif_file' in with_params, "Should specify sarif_file parameter"
    assert 'category' in with_params, "Should specify category parameter"

def test_sarif_upload_has_conditions():
    """Verify that SARIF upload has proper conditions."""
    repo_root = get_test_root()
    workflow_file = repo_root / ".github" / "workflows" / "security.yml"

    with open(workflow_file) as f:
        workflow = yaml.safe_load(f)

    job = workflow['jobs']['trivy-scan-core']
    steps = job['steps']

    # Find the codeql-action/upload-sarif step
    upload_step = None
    for s in steps:
        if 'uses' in s and 'codeql-action/upload-sarif' in s['uses']:
            upload_step = s
            break

    assert upload_step is not None, "SARIF upload step should exist"
    assert 'if' in upload_step, "Upload step should have conditional"

    if_condition = upload_step['if']
    # Should check that file exists and handle pull requests
    assert 'hashFiles' in if_condition or 'always' in if_condition, \
        "Should check if SARIF file exists"

def test_artifact_upload_still_exists():
    """Verify that artifact upload step still exists."""
    repo_root = get_test_root()
    workflow_file = repo_root / ".github" / "workflows" / "security.yml"

    with open(workflow_file) as f:
        workflow = yaml.safe_load(f)

    job = workflow['jobs']['trivy-scan-core']
    steps = job['steps']

    # Look for artifact upload step
    artifact_steps = [s for s in steps if 'uses' in s and 'upload-artifact' in s['uses']]
    assert len(artifact_steps) > 0, \
        "Job should still have artifact upload step"

def test_upload_order():
    """Verify that upload steps are in correct order."""
    repo_root = get_test_root()
    workflow_file = repo_root / ".github" / "workflows" / "security.yml"

    with open(workflow_file) as f:
        workflow = yaml.safe_load(f)

    job = workflow['jobs']['trivy-scan-core']
    steps = job['steps']

    # Find step positions
    artifact_pos = None
    sarif_pos = None

    for i, s in enumerate(steps):
        if 'uses' in s and 'upload-artifact' in s['uses']:
            artifact_pos = i
        elif 'uses' in s and 'codeql-action/upload-sarif' in s['uses']:
            sarif_pos = i

    # Both should exist
    assert artifact_pos is not None, "Artifact upload should exist"
    assert sarif_pos is not None, "SARIF upload should exist"

    # SARIF upload should come after artifact upload
    assert artifact_pos < sarif_pos, \
        "Artifact upload should come before SARIF upload"

def test_custom_image_job_also_has_sarif():
    """Verify that trivy-scan-custom job also has SARIF upload."""
    repo_root = get_test_root()
    workflow_file = repo_root / ".github" / "workflows" / "security.yml"

    with open(workflow_file) as f:
        workflow = yaml.safe_load(f)

    # Check if custom job exists
    if 'trivy-scan-custom' not in workflow['jobs']:
        return  # Job might not exist in all versions

    job = workflow['jobs']['trivy-scan-custom']
    steps = job['steps']

    # Look for codeql-action/upload-sarif
    upload_steps = [s for s in steps if 'uses' in s and 'codeql-action/upload-sarif' in s['uses']]
    assert len(upload_steps) > 0, \
        "Custom image job should also have SARIF upload"

if __name__ == "__main__":
    print("Testing trivy-scan-core job exists...")
    test_trivy_scan_core_job_exists()
    print("✓ Trivy-scan-core job exists test passed")

    print("Testing trivy-scan-core has SARIF upload...")
    test_trivy_scan_core_has_sarif_upload()
    print("✓ SARIF upload test passed")

    print("Testing SARIF upload has correct parameters...")
    test_sarif_upload_has_correct_parameters()
    print("✓ SARIF upload parameters test passed")

    print("Testing SARIF upload has conditions...")
    test_sarif_upload_has_conditions()
    print("✓ SARIF upload conditions test passed")

    print("Testing artifact upload still exists...")
    test_artifact_upload_still_exists()
    print("✓ Artifact upload test passed")

    print("Testing upload order...")
    test_upload_order()
    print("✓ Upload order test passed")

    print("Testing custom image job also has SARIF...")
    test_custom_image_job_also_has_sarif()
    print("✓ Custom image job SARIF test passed")

    print("\nAll tests passed!")
    sys.exit(0)
