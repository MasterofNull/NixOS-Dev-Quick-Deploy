# Python Testing Infrastructure with pytest
# NixOS 26.05 Yarara
# Purpose: Comprehensive testing framework for Python development
#
# Features:
# - pytest with plugins
# - Code coverage reporting
# - Parallel test execution
# - Property-based testing
# - Test data generation
# - Code quality integration
#
# Usage: Import this file in your home.nix:
#   imports = [ ./nixos-improvements/testing.nix ];

{ config, pkgs, lib, ... }:

let
  py =
    if pkgs ? python3Packages then pkgs.python3Packages
    else if pkgs ? python313Packages then pkgs.python313Packages
    else if pkgs ? python312Packages then pkgs.python312Packages
    else pkgs.python311Packages;
  pythonPackageNames = [
    "pytest"
    "pytest-cov"
    "pytest-xdist"
    "pytest-asyncio"
    "pytest-timeout"
    "pytest-repeat"
    "pytest-rerunfailures"
    "pytest-benchmark"
    "pytest-mock"
    "pytest-freezegun"
    "pytest-env"
    "pytest-httpserver"
    "hypothesis"
    "faker"
    "factory-boy"
    "pytest-flake8"
    "pytest-mypy"
    "pytest-black"
    "pytest-isort"
    "pytest-pylint"
    "pytest-html"
    "pytest-json-report"
    "pytest-sugar"
    "pytest-clarity"
    "pytest-postgresql"
    "pytest-redis"
    "pytest-mongodb"
    "pytest-django"
    "pytest-flask"
    "pytest-tornado"
    "requests-mock"
    "tox"
    "coverage"
    "nose2"
    "flake8"
    "black"
    "isort"
    "mypy"
    "pylint"
    "ruff"
  ];
  pythonPackages =
    lib.concatMap
      (name:
        lib.optional (builtins.hasAttr name py) (builtins.getAttr name py)
      )
      pythonPackageNames;
  pytestWatchPkg =
    if builtins.hasAttr "pytest-watch" py then py."pytest-watch" else null;
in
{
  # =========================================================================
  # Core Testing Packages
  # =========================================================================

  home.packages =
    pythonPackages
    ++ [
    # -------------------------------------------------------------------------
    # pytest Core & Essential Plugins
    # -------------------------------------------------------------------------
    py.pytest              # Core testing framework
    py.pytest-cov          # Coverage reporting
    py.pytest-xdist        # Parallel test execution
    py.pytest-asyncio      # Async test support
    py.pytest-timeout      # Test timeouts
    py.pytest-repeat       # Repeat tests
    py.pytest-rerunfailures # Retry flaky tests

    # -------------------------------------------------------------------------
    # Advanced Testing Tools
    # -------------------------------------------------------------------------
    py.pytest-benchmark    # Performance benchmarking
    py.pytest-mock         # Mocking utilities
    py.pytest-freezegun    # Time/date mocking
    py.pytest-env          # Environment variable management
    py.pytest-httpserver   # Mock HTTP servers

    # -------------------------------------------------------------------------
    # Property-Based & Generative Testing
    # -------------------------------------------------------------------------
    py.hypothesis          # Property-based testing
    py.faker               # Realistic test data generation
    py.factory-boy         # Test fixture factories

    # -------------------------------------------------------------------------
    # Code Quality Integration
    # -------------------------------------------------------------------------
    py.pytest-flake8       # Linting integration
    py.pytest-mypy         # Type checking integration
    py.pytest-black        # Code formatting checks
    py.pytest-isort        # Import sorting checks
    py.pytest-pylint       # Pylint integration

    # -------------------------------------------------------------------------
    # Reporting & Output
    # -------------------------------------------------------------------------
    py.pytest-html         # HTML test reports
    py.pytest-json-report  # JSON output for CI
    py.pytest-sugar        # Better test output
    py.pytest-clarity      # Better assertion messages

    # -------------------------------------------------------------------------
    # Database Testing
    # -------------------------------------------------------------------------
    py.pytest-postgresql   # PostgreSQL fixtures
    py.pytest-redis        # Redis fixtures
    py.pytest-mongodb      # MongoDB fixtures

    # -------------------------------------------------------------------------
    # Web/API Testing
    # -------------------------------------------------------------------------
    py.pytest-django       # Django testing support
    py.pytest-flask        # Flask testing support
    py.pytest-tornado      # Tornado testing support
    py.requests-mock       # Mock HTTP requests

    # -------------------------------------------------------------------------
    # Additional Testing Tools
    # -------------------------------------------------------------------------
    py.tox                 # Test automation
    py.coverage            # Coverage CLI
    py.nose2               # Alternative test runner

    # -------------------------------------------------------------------------
    # Linters & Formatters (for quality checks)
    # -------------------------------------------------------------------------
    py.flake8              # Linting
    py.black               # Code formatting
    py.isort               # Import sorting
    py.mypy                # Static type checking
    py.pylint              # Code analysis
    py.ruff                # Fast linter & formatter
  ]
    ++ [
      (pkgs.writeShellScriptBin "pytest-init" ''
        #!/usr/bin/env bash
        # Initialize pytest structure in current directory
        exec ${config.home.homeDirectory}/.config/pytest/init_tests.sh "."
      '')

      (pkgs.writeShellScriptBin "pytest-report" ''
        #!/usr/bin/env bash
        # Generate comprehensive test report
        set -euo pipefail

        echo "📊 Running tests with coverage..."
        pytest \
          --cov \
          --cov-report=html \
          --cov-report=term \
          --html=test-report.html \
          --self-contained-html \
          "$@"

        echo ""
        echo "✅ Reports generated:"
        echo "  Coverage: htmlcov/index.html"
        echo "  Test Report: test-report.html"
      '')

      (pkgs.writeShellScriptBin "pytest-quick" ''
        #!/usr/bin/env bash
        # Quick smoke tests only
        pytest -m "smoke or unit" --maxfail=1 "$@"
      '')
    ]
    ++ lib.optional (pytestWatchPkg != null) (
      pkgs.writeShellScriptBin "pytest-watch" ''
        #!/usr/bin/env bash
        # Watch for file changes and re-run tests
        ${pytestWatchPkg}/bin/ptw "$@"
      ''
    );

  # =========================================================================
  # Test Directory Setup
  # =========================================================================

  # Automatically create test directory structure
  home.file.".config/pytest/init_tests.sh" = {
    executable = true;
    text = ''
      #!/usr/bin/env bash
      # Initialize test directory structure

      PROJECT_ROOT="''${1:-.}"

      echo "📁 Creating test directory structure in: $PROJECT_ROOT"

      mkdir -p "$PROJECT_ROOT/tests"/{unit,integration,e2e,fixtures}
      mkdir -p "$PROJECT_ROOT/tests/.pytest_cache"

      # Create __init__.py files
      touch "$PROJECT_ROOT/tests/__init__.py"
      touch "$PROJECT_ROOT/tests/unit/__init__.py"
      touch "$PROJECT_ROOT/tests/integration/__init__.py"
      touch "$PROJECT_ROOT/tests/e2e/__init__.py"

      # Create conftest.py for shared fixtures
      cat > "$PROJECT_ROOT/tests/conftest.py" <<'EOF'
      """
      Shared pytest fixtures and configuration.
      This file is automatically loaded by pytest.
      """
      import pytest
      import logging

      # Configure logging for tests
      logging.basicConfig(
          level=logging.INFO,
          format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
      )

      @pytest.fixture
      def sample_data():
          """Example fixture providing test data."""
          return {
              "id": 1,
              "name": "Test Item",
              "active": True
          }

      @pytest.fixture
      def temp_file(tmp_path):
          """Create a temporary file for testing."""
          file_path = tmp_path / "test_file.txt"
          file_path.write_text("Test content")
          return file_path
      EOF

      # Create pytest.ini configuration
      cat > "$PROJECT_ROOT/pytest.ini" <<'EOF'
      [pytest]
      # Test discovery
      testpaths = tests
      python_files = test_*.py
      python_classes = Test*
      python_functions = test_*

      # Output options
      addopts =
          -v
          --strict-markers
          --tb=short
          --cov=.
          --cov-report=html
          --cov-report=term-missing:skip-covered
          --cov-report=xml
          --junit-xml=test-results.xml

      # Test markers
      markers =
          unit: Unit tests (fast, isolated)
          integration: Integration tests (slower, with dependencies)
          e2e: End-to-end tests (slowest, full stack)
          slow: Tests that take >1 second
          smoke: Quick smoke tests for CI
          skip_ci: Skip in CI environment

      # Coverage options
      [coverage:run]
      source = .
      omit =
          */tests/*
          */test_*.py
          */.venv/*
          */venv/*
          */dist/*
          */build/*

      [coverage:report]
      precision = 2
      skip_empty = True
      exclude_lines =
          pragma: no cover
          def __repr__
          raise AssertionError
          raise NotImplementedError
          if __name__ == .__main__.:
          if TYPE_CHECKING:
          @abstractmethod
      EOF

      # Create example test file
      cat > "$PROJECT_ROOT/tests/unit/test_example.py" <<'EOF'
      """
      Example unit test file.
      """
      import pytest

      def test_example():
          """Example test that always passes."""
          assert True

      def test_sample_data(sample_data):
          """Test using shared fixture."""
          assert sample_data["id"] == 1
          assert sample_data["active"] is True

      @pytest.mark.unit
      def test_string_operations():
          """Test basic string operations."""
          result = "hello world".upper()
          assert result == "HELLO WORLD"

      @pytest.mark.parametrize("input,expected", [
          (1, 2),
          (2, 4),
          (3, 6),
      ])
      def test_multiply_by_two(input, expected):
          """Parametrized test example."""
          assert input * 2 == expected
      EOF

      echo "✅ Test structure created!"
      echo ""
      echo "Run tests with:"
      echo "  cd $PROJECT_ROOT && pytest"
      echo ""
      echo "Generate coverage report:"
      echo "  pytest --cov --cov-report=html"
      echo "  open htmlcov/index.html"
    '';
  };

  # =========================================================================
  # Shell Aliases
  # =========================================================================

  programs.bash.shellAliases = {
    pt = "pytest";
    ptv = "pytest -v";
    ptx = "pytest -x";  # Stop on first failure
    ptlf = "pytest --lf";  # Re-run last failures
    ptcov = "pytest --cov --cov-report=html";
  };

  programs.zsh.shellAliases = {
    pt = "pytest";
    ptv = "pytest -v";
    ptx = "pytest -x";
    ptlf = "pytest --lf";
    ptcov = "pytest --cov --cov-report=html";
  };

  # =========================================================================
  # VS Code Integration (if using VS Code)
  # =========================================================================

  programs.vscode.profiles.default.userSettings = lib.mkIf (config.programs.vscode.enable) {
    "python.testing.pytestEnabled" = true;
    "python.testing.unittestEnabled" = false;
    "python.testing.pytestArgs" = [
      "tests"
      "-v"
      "--tb=short"
    ];
  };
}
