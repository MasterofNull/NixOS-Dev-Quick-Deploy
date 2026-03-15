#!/usr/bin/env bash
#
# Deploy CLI - Search Command
# Semantic search for deployments, logs, and code

# ============================================================================
# Help Text
# ============================================================================

help_search() {
  cat <<EOF
Command: deploy search

Semantic search across deployments, logs, and codebase.

USAGE:
  deploy search QUERY [OPTIONS]

OPTIONS:
  --type TYPE             Search type (deployments/logs/code/all)
  --limit N               Maximum results (default: 10)
  --format FORMAT         Output format (text/json)
  --since TIME            Search since timestamp (for logs)
  --help                  Show this help

EXAMPLES:
  deploy search "mTLS configuration"       # Search all
  deploy search "failed deployment" --type logs
  deploy search "nixos config" --type code
  deploy search "ai-stack" --limit 20

DESCRIPTION:
  The 'search' command provides semantic search capabilities across:
  - Deployment history and metadata
  - System and service logs
  - Configuration files and code
  - Documentation

  Search Types:
  - deployments: Search deployment history, changes, outcomes
  - logs: Search across all systemd and application logs
  - code: Search codebase with semantic understanding
  - all: Search everything (default)

  In Phase 3, this command will use:
  - Vector embeddings for semantic search
  - Qdrant for similarity search
  - Knowledge graphs for context
  - AI-powered result ranking

CURRENT STATUS:
  Phase 1.2: Basic text search implemented
  Phase 3: Full semantic search (Weeks 5-6)
  - Vector storage for deployment history
  - Semantic log analysis
  - Code understanding with embeddings
  - AI-powered troubleshooting suggestions

SEARCH CAPABILITIES (Phase 3):

  Deployment Search:
  - Find similar past deployments
  - Search by error messages
  - Find successful resolution paths

  Log Search:
  - Semantic log analysis
  - Error correlation across services
  - Timeline reconstruction

  Code Search:
  - Find similar configurations
  - Locate related code sections
  - Dependency analysis

EXIT CODES:
  0    Results found
  1    No results
  2    Execution error

RELATED COMMANDS:
  deploy ai-stack logs    Service-specific logs
  deploy recover diagnose System diagnostics
  deploy health           Current system state

DOCUMENTATION:
  .agents/designs/unified-deploy-cli-architecture.md
  .agents/plans/SYSTEM-EXCELLENCE-ROADMAP-2026-Q2.md (Phase 3)
EOF
}

# ============================================================================
# Search Operations
# ============================================================================

search_deployments() {
  local query="$1"
  local limit="${2:-10}"

  log_info "Searching deployment history for: $query"

  # Phase 1.2: Basic grep-based search
  # Phase 3: Vector similarity search

  if command -v journalctl >/dev/null 2>&1; then
    log_info "Searching systemd journal for deployment-related entries..."

    journalctl -u nixos-rebuild.service --no-pager | grep -i "$query" | head -n "$limit"
  else
    log_warn "journalctl not available"
  fi

  return 0
}

search_logs() {
  local query="$1"
  local limit="${2:-10}"
  local since="${3:-1 day ago}"

  log_info "Searching logs for: $query"

  # Phase 1.2: Basic journalctl search
  # Phase 3: Semantic log analysis

  if command -v journalctl >/dev/null 2>&1; then
    journalctl --since "$since" --no-pager | grep -i "$query" | head -n "$limit"
  else
    log_warn "journalctl not available"
  fi

  return 0
}

search_code() {
  local query="$1"
  local limit="${2:-10}"

  log_info "Searching codebase for: $query"

  # Phase 1.2: Basic grep search
  # Phase 3: Semantic code search with embeddings

  local script_dir
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

  if command -v rg >/dev/null 2>&1; then
    # Use ripgrep if available
    rg -i "$query" "$script_dir" --max-count "$limit" 2>/dev/null
  elif command -v grep >/dev/null 2>&1; then
    # Fallback to grep
    grep -r -i "$query" "$script_dir" 2>/dev/null | head -n "$limit"
  else
    log_warn "No search tool available"
  fi

  return 0
}

search_all() {
  local query="$1"
  local limit="${2:-10}"

  print_section "Searching: $query"

  log_info "Searching all sources..."

  echo ""
  echo "=== Deployment History ==="
  search_deployments "$query" 3

  echo ""
  echo "=== Recent Logs ==="
  search_logs "$query" 3

  echo ""
  echo "=== Code ==="
  search_code "$query" 4

  return 0
}

# ============================================================================
# Main Command Handler
# ============================================================================

cmd_search() {
  local query=""
  local search_type="all"
  local limit=10
  local format="text"
  local since="1 day ago"

  # Parse arguments
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --help)
        help_search
        return 0
        ;;
      --type)
        search_type="$2"
        shift 2
        ;;
      --limit)
        limit="$2"
        shift 2
        ;;
      --format)
        format="$2"
        shift 2
        ;;
      --since)
        since="$2"
        shift 2
        ;;
      -*)
        log_error "Unknown option: $1"
        echo ""
        echo "Run 'deploy search --help' for usage."
        return 2
        ;;
      *)
        # First positional argument is the query
        query="$1"
        shift
        ;;
    esac
  done

  if [[ -z "$query" ]]; then
    log_error "Search query required"
    echo ""
    echo "Usage: deploy search QUERY [OPTIONS]"
    echo "Run 'deploy search --help' for more information."
    return 2
  fi

  print_header "Search: $query"

  log_warn "Note: Phase 1.2 provides basic text search"
  log_info "Full semantic search coming in Phase 3 (Weeks 5-6)"

  echo ""

  # Dispatch to search type
  case "$search_type" in
    deployments)
      search_deployments "$query" "$limit"
      ;;
    logs)
      search_logs "$query" "$limit" "$since"
      ;;
    code)
      search_code "$query" "$limit"
      ;;
    all)
      search_all "$query" "$limit"
      ;;
    *)
      log_error "Unknown search type: $search_type"
      echo ""
      echo "Valid types: deployments, logs, code, all"
      return 2
      ;;
  esac

  echo ""
  log_info "Phase 3 will add: vector search, semantic ranking, AI suggestions"

  return 0
}
