#!/usr/bin/env python3
"""
CLI tool to record issues in the issue tracking database

Usage:
    ./record-issue.py "Issue title" "Issue description" \
        --severity high \
        --category integration \
        --component p1-integration \
        --error "Error message" \
        --fix "Suggested fix 1" --fix "Suggested fix 2"
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "ai-stack" / "mcp-servers" / "aidb"))

import asyncpg
from issue_tracker import IssueTracker, IssueSeverity, IssueCategory


async def record_issue_cli():
    """CLI interface for recording issues"""
    parser = argparse.ArgumentParser(
        description="Record issues in the issue tracking database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Record a test failure
  ./record-issue.py "Integration tests failed" "Tests failed during P1 deployment" \\
      --severity high --category integration --component p1-integration

  # Record with error details and suggested fixes
  ./record-issue.py "Database connection timeout" "PostgreSQL connection timed out" \\
      --severity critical --category reliability --component aidb \\
      --error "connection timeout after 30s" \\
      --fix "Increase connection pool size" \\
      --fix "Add connection retry logic" \\
      --change "Implement connection health checks"

  # Record a deployment issue
  ./record-issue.py "Deployment failed" "P1 features failed to deploy" \\
      --severity high --category deployment --component p1-integration \\
      --tag deployment --tag p1 --tag failed
        """
    )

    parser.add_argument("title", help="Issue title (short summary)")
    parser.add_argument("description", help="Issue description (detailed)")

    parser.add_argument(
        "--severity", "-s",
        choices=["critical", "high", "medium", "low", "info"],
        default="medium",
        help="Issue severity (default: medium)"
    )

    parser.add_argument(
        "--category", "-c",
        choices=[
            "security", "performance", "reliability", "data_integrity",
            "configuration", "deployment", "integration", "validation",
            "monitoring", "other"
        ],
        default="other",
        help="Issue category (default: other)"
    )

    parser.add_argument(
        "--component",
        required=True,
        help="Component where issue occurred (e.g., aidb, hybrid-coordinator, p1-integration)"
    )

    parser.add_argument(
        "--error", "-e",
        help="Error message (if applicable)"
    )

    parser.add_argument(
        "--error-type",
        help="Error type (e.g., ConnectionError, ValueError)"
    )

    parser.add_argument(
        "--stack-trace",
        help="Stack trace (if applicable)"
    )

    parser.add_argument(
        "--fix", "-f",
        action="append",
        dest="fixes",
        help="Suggested fix (can be used multiple times)"
    )

    parser.add_argument(
        "--change",
        action="append",
        dest="changes",
        help="System change needed (can be used multiple times)"
    )

    parser.add_argument(
        "--tag", "-t",
        action="append",
        dest="tags",
        help="Tag for categorization (can be used multiple times)"
    )

    parser.add_argument(
        "--context",
        help="Additional context (JSON string)"
    )

    parser.add_argument(
        "--db-host",
        default="localhost",
        help="Database host (default: localhost)"
    )

    parser.add_argument(
        "--db-port",
        type=int,
        default=5432,
        help="Database port (default: 5432)"
    )

    parser.add_argument(
        "--db-name",
        default="aidb",
        help="Database name (default: aidb)"
    )

    parser.add_argument(
        "--db-user",
        default="aidb",
        help="Database user (default: aidb)"
    )

    parser.add_argument(
        "--db-password",
        default="aidb_password",
        help="Database password (default: aidb_password)"
    )

    args = parser.parse_args()

    # Parse context if provided
    context = {}
    if args.context:
        import json
        try:
            context = json.loads(args.context)
        except json.JSONDecodeError:
            print(f"Error: Invalid JSON in --context: {args.context}", file=sys.stderr)
            sys.exit(1)

    # Connect to database
    try:
        db_pool = await asyncpg.create_pool(
            host=args.db_host,
            port=args.db_port,
            database=args.db_name,
            user=args.db_user,
            password=args.db_password,
            min_size=1,
            max_size=5
        )
    except Exception as e:
        print(f"Error: Failed to connect to database: {e}", file=sys.stderr)
        sys.exit(1)

    # Initialize tracker
    tracker = IssueTracker(db_pool)
    await tracker.initialize_schema()

    # Record issue
    try:
        issue = await tracker.record_issue(
            title=args.title,
            description=args.description,
            severity=IssueSeverity(args.severity),
            category=IssueCategory(args.category),
            component=args.component,
            error_message=args.error,
            error_type=args.error_type,
            stack_trace=args.stack_trace,
            context=context,
            tags=args.tags or [],
            suggested_fixes=args.fixes or [],
            system_changes_needed=args.changes or []
        )

        print("\n✅ Issue recorded successfully!")
        print(f"   ID: {issue.id}")
        print(f"   Title: {issue.title}")
        print(f"   Severity: {issue.severity.value}")
        print(f"   Category: {issue.category.value}")
        print(f"   Component: {issue.component}")

        if issue.suggested_fixes:
            print("\n   Suggested Fixes:")
            for fix in issue.suggested_fixes:
                print(f"   - {fix}")

        if issue.system_changes_needed:
            print("\n   System Changes Needed:")
            for change in issue.system_changes_needed:
                print(f"   - {change}")

        print(f"\n   View all issues: ./scripts/list-issues.py")
        print(f"   Analyze patterns: ./scripts/analyze-issues.py")

    except Exception as e:
        print(f"Error: Failed to record issue: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        await db_pool.close()


if __name__ == "__main__":
    asyncio.run(record_issue_cli())
