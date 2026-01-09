#!/usr/bin/env python3
"""
Analyze issue patterns and suggest system improvements

Usage:
    ./analyze-issues.py
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "ai-stack" / "mcp-servers" / "aidb"))

import asyncpg
from issue_tracker import IssueTracker


async def analyze_issues_cli():
    """CLI interface for analyzing issues"""
    parser = argparse.ArgumentParser(description="Analyze issue patterns and suggest improvements")

    parser.add_argument(
        "--db-host", default="localhost", help="Database host"
    )
    parser.add_argument(
        "--db-port", type=int, default=5432, help="Database port"
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

    try:
        # Analyze patterns
        print("\n" + "="*100)
        print("📊 ISSUE PATTERN ANALYSIS (Last 7 Days)")
        print("="*100 + "\n")

        patterns = await tracker.analyze_patterns()

        # Statistics
        stats = patterns["statistics"]
        print("📈 Statistics:")
        print(f"   Total issues: {stats['total_issues']}")
        print(f"   Open issues: {stats['open_issues']}")
        print(f"   Critical issues: {stats['critical_issues']}")
        print(f"   High priority issues: {stats['high_issues']}")
        print(f"   Total occurrences: {stats['total_occurrences']}")
        print()

        # Common errors
        if patterns["common_errors"]:
            print("🔥 Most Common Errors:")
            for i, error in enumerate(patterns["common_errors"][:5], 1):
                print(f"   {i}. {error['error_type']} in {error['component']}")
                print(f"      Count: {error['count']} issues, {error['occurrences']} occurrences")
            print()

        # Affected components
        if patterns["affected_components"]:
            print("🎯 Most Affected Components:")
            for i, comp in enumerate(patterns["affected_components"][:5], 1):
                print(f"   {i}. {comp['component']}")
                print(f"      Issues: {comp['issue_count']}, Occurrences: {comp['occurrences']}")
            print()

        # Category breakdown
        if patterns["category_breakdown"]:
            print("📂 Category Breakdown:")
            for i, cat in enumerate(patterns["category_breakdown"], 1):
                print(f"   {i}. {cat['category']}: {cat['count']} issues, {cat['occurrences']} occurrences")
            print()

        # Get improvement suggestions
        print("="*100)
        print("💡 SYSTEM IMPROVEMENT SUGGESTIONS")
        print("="*100 + "\n")

        suggestions = await tracker.suggest_system_improvements()

        if not suggestions:
            print("✅ No critical improvement suggestions at this time.")
        else:
            # Group by priority
            high_priority = [s for s in suggestions if s["priority"] == "high"]
            medium_priority = [s for s in suggestions if s["priority"] == "medium"]
            low_priority = [s for s in suggestions if s["priority"] == "low"]

            if high_priority:
                print("🔴 HIGH PRIORITY:")
                for i, sug in enumerate(high_priority, 1):
                    print(f"   {i}. {sug['description']}")
                    print(f"      → {sug['suggestion']}")
                    if 'occurrences' in sug:
                        print(f"      Occurrences: {sug['occurrences']}")
                    if 'issue_count' in sug:
                        print(f"      Issues: {sug['issue_count']}")
                    print()

            if medium_priority:
                print("🟡 MEDIUM PRIORITY:")
                for i, sug in enumerate(medium_priority, 1):
                    print(f"   {i}. {sug['description']}")
                    print(f"      → {sug['suggestion']}")
                    if 'occurrences' in sug:
                        print(f"      Occurrences: {sug['occurrences']}")
                    if 'issue_count' in sug:
                        print(f"      Issues: {sug['issue_count']}")
                    print()

            if low_priority:
                print("🔵 LOW PRIORITY:")
                for i, sug in enumerate(low_priority, 1):
                    print(f"   {i}. {sug['description']}")
                    print(f"      → {sug['suggestion']}")
                    print()

        print("="*100)
        print("\n✅ Analysis complete!")
        print(f"   List all issues: ./scripts/list-issues.py")
        print(f"   Record new issue: ./scripts/record-issue.py \"Title\" \"Description\" ...")

    except Exception as e:
        print(f"Error: Failed to analyze issues: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        await db_pool.close()


if __name__ == "__main__":
    asyncio.run(analyze_issues_cli())
