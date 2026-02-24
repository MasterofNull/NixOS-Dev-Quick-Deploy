#!/usr/bin/env python3
"""
List issues from the issue tracking database

Usage:
    ./list-issues.py                    # List all open issues
    ./list-issues.py --all              # List all issues
    ./list-issues.py --severity critical # List critical issues only
    ./list-issues.py --category security # List security issues only
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "ai-stack" / "mcp-servers" / "aidb"))

import asyncpg
from issue_tracker import IssueTracker, IssueSeverity, IssueCategory, IssueStatus


async def list_issues_cli():
    """CLI interface for listing issues"""
    parser = argparse.ArgumentParser(description="List issues from the issue tracking database")

    parser.add_argument(
        "--all", "-a",
        action="store_true",
        help="List all issues (including resolved)"
    )

    parser.add_argument(
        "--status",
        choices=["open", "investigating", "in_progress", "resolved", "wont_fix", "duplicate"],
        help="Filter by status"
    )

    parser.add_argument(
        "--severity",
        choices=["critical", "high", "medium", "low", "info"],
        help="Filter by severity"
    )

    parser.add_argument(
        "--category",
        choices=[
            "security", "performance", "reliability", "data_integrity",
            "configuration", "deployment", "integration", "validation",
            "monitoring", "other"
        ],
        help="Filter by category"
    )

    parser.add_argument(
        "--component",
        help="Filter by component"
    )

    parser.add_argument(
        "--limit", "-l",
        type=int,
        default=50,
        help="Limit number of results (default: 50)"
    )

    parser.add_argument(
        "--db-host", default="localhost", help="Database host"
    )
    parser.add_argument(
        "--db-port", type=int, default=int(os.getenv("POSTGRES_PORT", "0")), help="Database port"
    )
    parser.add_argument(
        "--db-name", default="aidb", help="Database name"
    )
    parser.add_argument(
        "--db-user", default="aidb", help="Database user"
    )
    parser.add_argument(
        "--db-password", default="aidb_password", help="Database password"
    )

    args = parser.parse_args()

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

    # List issues
    try:
        status_filter = None if args.all else IssueStatus(args.status) if args.status else IssueStatus.OPEN
        severity_filter = IssueSeverity(args.severity) if args.severity else None
        category_filter = IssueCategory(args.category) if args.category else None

        issues = await tracker.list_issues(
            status=status_filter,
            severity=severity_filter,
            category=category_filter,
            component=args.component,
            limit=args.limit
        )

        if not issues:
            print("No issues found matching the criteria.")
            return

        print(f"\n{'='*100}")
        print(f"Found {len(issues)} issue(s)")
        print(f"{'='*100}\n")

        for issue in issues:
            # Severity emoji
            severity_emoji = {
                "critical": "🔴",
                "high": "🟠",
                "medium": "🟡",
                "low": "🔵",
                "info": "⚪"
            }

            # Status emoji
            status_emoji = {
                "open": "📭",
                "investigating": "🔍",
                "in_progress": "⚙️",
                "resolved": "✅",
                "wont_fix": "❌",
                "duplicate": "♻️"
            }

            print(f"{severity_emoji.get(issue.severity.value, '❓')} {status_emoji.get(issue.status.value, '❓')} [{issue.severity.value.upper()}] {issue.title}")
            print(f"   ID: {issue.id}")
            print(f"   Component: {issue.component}")
            print(f"   Category: {issue.category.value}")
            print(f"   Status: {issue.status.value}")
            print(f"   First seen: {issue.first_seen.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"   Last seen: {issue.last_seen.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"   Occurrences: {issue.occurrence_count}")

            if issue.error_message:
                print(f"   Error: {issue.error_message[:100]}...")

            if issue.suggested_fixes:
                print(f"   Suggested fixes:")
                for fix in issue.suggested_fixes[:3]:
                    print(f"     - {fix}")

            if issue.system_changes_needed:
                print(f"   System changes needed:")
                for change in issue.system_changes_needed[:3]:
                    print(f"     - {change}")

            print()

        print(f"{'='*100}")
        print(f"\nTo resolve an issue: ./scripts/resolve-issue.py <issue_id> \"Resolution description\"")
        print(f"To analyze patterns: ./scripts/analyze-issues.py")

    except Exception as e:
        print(f"Error: Failed to list issues: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        await db_pool.close()


if __name__ == "__main__":
    asyncio.run(list_issues_cli())
