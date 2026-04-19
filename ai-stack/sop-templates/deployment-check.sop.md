---
name: Deployment Readiness Check
description: Pre-deployment validation checklist
version: 1.0.0
parameters:
  environment: "production"
  rollback_enabled: true
---

# Deployment Readiness Check SOP

Standard operating procedure for validating deployment readiness before pushing to production or staging environments.

## Pre-Deployment Validation

1. MUST verify all tests pass
   - Run full test suite
   - Confirm zero failures
   - Check test coverage meets threshold

2. MUST validate build artifacts
   - Ensure clean build with no errors
   - Verify artifact integrity (checksums)
   - Confirm correct version tagging

3. MUST NOT deploy with known critical bugs
   - Review open critical/blocker issues
   - Verify all P0 bugs are resolved
   - Check for security vulnerabilities

## Configuration Verification

1. MUST validate environment configuration
   - Verify all required environment variables are set
   - Check configuration matches target environment
   - Confirm no hardcoded secrets or credentials

2. SHOULD review infrastructure changes
   - Check for database migrations
   - Verify resource scaling requirements
   - Review networking and firewall rules

3. MAY perform load testing
   - Run performance benchmarks
   - Validate under expected load
   - Confirm auto-scaling triggers

## Dependency Checks

1. MUST verify dependency compatibility
   - Check all dependencies are available
   - Confirm version compatibility
   - Validate license compliance

2. SHOULD update dependency lock files
   - Regenerate package-lock.json, Cargo.lock, etc.
   - Verify no unexpected changes
   - Commit lock file updates

## Rollback Preparation

1. MUST prepare rollback strategy
   - Document rollback procedure
   - Create database backup if needed
   - Tag previous stable version

2. SHOULD test rollback procedure
   - Verify rollback works in staging
   - Document rollback validation steps
   - Prepare communication plan

## Deployment Execution

1. MUST follow deployment runbook
   - Execute steps in documented order
   - Record start and completion times
   - Monitor application health metrics

2. SHOULD enable gradual rollout
   - Deploy to subset of infrastructure first
   - Monitor error rates and performance
   - Progressively increase traffic

3. MUST NOT skip smoke tests
   - Run post-deployment smoke tests
   - Verify critical user flows
   - Check integration points

## Post-Deployment Validation

1. MUST monitor application health
   - Check error rates and logs
   - Verify all services are healthy
   - Monitor performance metrics

2. SHOULD validate user experience
   - Test critical user workflows
   - Verify UI/UX changes
   - Check cross-browser compatibility

3. MUST document deployment outcome
   - Record deployment timestamp and version
   - Log any issues encountered
   - Update change log and release notes

## Rollback Triggers

1. MUST rollback if error rate exceeds threshold
   - Define acceptable error rate
   - Trigger automatic rollback if exceeded
   - Notify team immediately

2. SHOULD rollback for performance degradation
   - Monitor latency and throughput
   - Compare against baseline metrics
   - Execute rollback if significant degradation

## Output Requirements

1. MUST generate deployment report
   - Save to `.agents/summary/deployment-{timestamp}.md`
   - Include all validation results
   - Document any issues and resolutions

2. SHOULD update deployment dashboard
   - Mark deployment status
   - Update version information
   - Link to deployment artifacts
