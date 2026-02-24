# CI/CD Pipeline Integration

## API Contract Tests Integration

The API contract tests created in Phase 2 should be integrated into the CI/CD pipeline.

### Test Suite Location
- File: `ai-stack/tests/test_api_contracts.py`
- Tests included:
  - Ralph → Aider-wrapper payload compatibility
  - Aider-wrapper → llama-cpp compatibility  
  - Ralph response format validation
  - All health endpoints

### CI/CD Integration Steps
1. Add test execution to build pipeline
2. Configure test execution on PRs to main branch
3. Set up test execution on merge to main
4. Configure test reporting and notifications

### GitHub Actions Workflow Example
```yaml
name: API Contract Tests
on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: 3.13
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
    - name: Run API contract tests
      run: |
        python -m pytest ai-stack/tests/test_api_contracts.py -v
```

### Expected Outcome
Automated tests prevent API breakage in CI/CD pipeline.