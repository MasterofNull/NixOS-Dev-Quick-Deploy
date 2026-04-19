---
name: Test Validation SOP
description: Comprehensive test suite validation procedure
version: 1.0.0
parameters:
  test_level: "all"
  coverage_threshold: 80
---

# Test Validation SOP

Standard operating procedure for validating test suites and ensuring code quality through comprehensive testing.

## Test Discovery

1. MUST identify all test files and frameworks
   - Locate unit test files
   - Find integration and e2e tests
   - Identify test configuration files

2. SHOULD catalog test types and coverage
   - List test frameworks in use (pytest, jest, etc.)
   - Map tests to source code modules
   - Calculate initial coverage baseline

## Unit Test Validation

1. MUST run all unit tests
   - Execute complete unit test suite
   - Verify zero failures
   - Check test execution time

2. MUST achieve minimum coverage threshold
   - Measure line and branch coverage
   - Verify coverage meets or exceeds threshold
   - Identify uncovered critical paths

3. SHOULD validate test quality
   - Check for test isolation
   - Verify no test interdependencies
   - Ensure tests are deterministic

## Integration Test Validation

1. MUST run integration tests
   - Execute all integration tests
   - Verify external service mocks
   - Confirm database state management

2. SHOULD validate test data management
   - Check for test data fixtures
   - Verify cleanup after tests
   - Ensure no test pollution

3. MAY perform contract testing
   - Validate API contracts
   - Check backward compatibility
   - Verify schema definitions

## End-to-End Test Validation

1. SHOULD run e2e test suite
   - Execute critical user journey tests
   - Verify UI automation works
   - Check cross-browser compatibility

2. MAY run visual regression tests
   - Capture and compare screenshots
   - Identify unintended UI changes
   - Verify responsive design

## Performance Testing

1. SHOULD run performance benchmarks
   - Execute load tests
   - Measure response times
   - Check resource utilization

2. MAY perform stress testing
   - Test system limits
   - Identify bottlenecks
   - Verify graceful degradation

## Security Testing

1. MUST scan for security vulnerabilities
   - Run dependency vulnerability scans
   - Check for common security issues
   - Verify input validation

2. SHOULD perform authentication testing
   - Test auth and authorization flows
   - Verify session management
   - Check for privilege escalation

3. MUST NOT expose sensitive data in tests
   - Verify no hardcoded credentials
   - Check test logs for secrets
   - Ensure secure test data handling

## Test Maintenance

1. SHOULD identify flaky tests
   - Run tests multiple times
   - Track failure patterns
   - Fix or quarantine flaky tests

2. MAY update test documentation
   - Document test patterns and conventions
   - Update testing guidelines
   - Provide examples for new tests

## Continuous Integration Validation

1. MUST verify CI pipeline runs
   - Check all CI jobs execute
   - Verify test results are reported
   - Confirm artifacts are generated

2. SHOULD validate pre-commit hooks
   - Test hooks on sample commits
   - Verify formatting and linting
   - Check for commit message validation

## Coverage Analysis

1. MUST generate coverage reports
   - Produce HTML and JSON reports
   - Highlight uncovered lines
   - Track coverage trends over time

2. SHOULD identify coverage gaps
   - List uncovered files
   - Prioritize critical uncovered code
   - Create tasks for coverage improvement

## Output Requirements

1. MUST generate test validation report
   - Save to `.agents/summary/test-validation-{timestamp}.md`
   - Include pass/fail counts
   - List coverage metrics and trends

2. SHOULD create test improvement plan
   - Document identified issues
   - Propose coverage improvements
   - Assign priority to test gaps

3. MAY generate test badges
   - Create coverage badge
   - Generate build status badge
   - Update README with badges

## Failure Handling

1. MUST investigate test failures immediately
   - Analyze failure logs
   - Reproduce failures locally
   - Determine root cause

2. SHOULD NOT ignore failing tests
   - Fix or disable broken tests
   - Document known issues
   - Track test debt

3. MUST block deployment on critical test failures
   - Define critical test suite
   - Prevent deployment if critical tests fail
   - Require manual override with justification
