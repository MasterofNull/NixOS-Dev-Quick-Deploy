#!/usr/bin/env python3
"""
Comprehensive MCP Server Discovery and Database Import
Searches GitHub for all MCP servers with ranking metrics
"""

import argparse
import json
import os
import time
from datetime import datetime
from typing import List, Dict, Any

import requests

# Service host (for AIDB export defaults)
SERVICE_HOST = os.environ.get("SERVICE_HOST", "localhost")

# GitHub API configuration
GITHUB_API = "https://api.github.com"

# Search categories for comprehensive coverage
SEARCH_QUERIES = [
    # Core MCP queries
    "mcp server",
    "model context protocol server",
    "mcp-server",

    # Category-specific
    "mcp security",
    "mcp database",
    "mcp filesystem",
    "mcp git",
    "mcp docker",
    "mcp kubernetes",
    "mcp aws",
    "mcp azure",
    "mcp github",
    "mcp gitlab",

    # Language-specific
    "mcp python",
    "mcp typescript",
    "mcp javascript",
    "mcp go",
    "mcp rust",

    # Function-specific
    "mcp audit",
    "mcp testing",
    "mcp monitoring",
    "mcp logging",
    "mcp analytics",
    "mcp compliance",
    "mcp vulnerability",
    "mcp scanner",

    # Red team/security
    "mcp red team",
    "mcp penetration testing",
    "mcp security audit",
    "mcp vulnerability scan",
]

class MCPServerDiscovery:
    def __init__(self, api_token=None):
        self.api_token = api_token
        self.headers = {
            "Accept": "application/vnd.github.v3+json"
        }
        if api_token:
            self.headers["Authorization"] = f"token {api_token}"

        self.servers = {}
        self.rate_limit_remaining = 60

    def search_github(self, query: str, max_results: int = 30) -> List[Dict[str, Any]]:
        """Search GitHub for repositories matching query"""
        url = f"{GITHUB_API}/search/repositories"
        params = {
            "q": query,
            "sort": "stars",
            "order": "desc",
            "per_page": max_results
        }

        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=30)

            # Check rate limit
            self.rate_limit_remaining = int(response.headers.get('X-RateLimit-Remaining', 0))

            if response.status_code == 403 and self.rate_limit_remaining == 0:
                reset_time = int(response.headers.get('X-RateLimit-Reset', 0))
                wait_time = reset_time - time.time()
                print(f"Rate limit exceeded. Waiting {wait_time:.0f} seconds...")
                time.sleep(wait_time + 1)
                return self.search_github(query, max_results)

            response.raise_for_status()
            data = response.json()

            return data.get('items', [])

        except Exception as e:
            print(f"Error searching for '{query}': {e}")
            return []

    def get_repo_details(self, full_name: str) -> Dict[str, Any]:
        """Get detailed repository information"""
        url = f"{GITHUB_API}/repos/{full_name}"

        try:
            response = requests.get(url, headers=self.headers, timeout=15)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error getting details for {full_name}: {e}")
            return {}

    def calculate_score(self, repo: Dict[str, Any]) -> float:
        """
        Calculate weighted score for MCP server ranking

        Metrics:
        - Stars: 40%
        - Forks: 20%
        - Watchers: 10%
        - Recent updates: 20%
        - Open issues ratio: 10% (penalize high issues)
        """
        stars = repo.get('stargazers_count', 0)
        forks = repo.get('forks_count', 0)
        watchers = repo.get('watchers_count', 0)
        open_issues = repo.get('open_issues_count', 0)

        # Recency score (repos updated in last 30 days get bonus)
        updated_at = repo.get('updated_at', '')
        try:
            update_time = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
            days_since_update = (datetime.now(update_time.tzinfo) - update_time).days
            recency_score = max(0, 100 - days_since_update) / 100
        except:
            recency_score = 0

        # Issue ratio (lower is better)
        if stars > 0:
            issue_ratio = min(open_issues / stars, 1.0)
            issue_score = 1.0 - issue_ratio
        else:
            issue_score = 0.5

        # Weighted score
        score = (
            (stars * 0.4) +
            (forks * 0.2) +
            (watchers * 0.1) +
            (recency_score * 100 * 0.2) +
            (issue_score * 100 * 0.1)
        )

        return round(score, 2)

    def categorize_server(self, repo: Dict[str, Any]) -> List[str]:
        """Categorize MCP server based on description and topics"""
        description = (repo.get('description', '') or '').lower()
        topics = [t.lower() for t in repo.get('topics', [])]
        name = repo.get('name', '').lower()

        categories = []

        # Security/Red Team
        if any(kw in description or kw in name or kw in topics for kw in
               ['security', 'audit', 'vulnerability', 'pentest', 'red team', 'scanner']):
            categories.append('security')

        # Development Tools
        if any(kw in description or kw in name or kw in topics for kw in
               ['git', 'github', 'gitlab', 'version control', 'code']):
            categories.append('development')

        # Database
        if any(kw in description or kw in name or kw in topics for kw in
               ['database', 'postgres', 'mysql', 'mongo', 'sql']):
            categories.append('database')

        # Cloud/Infrastructure
        if any(kw in description or kw in name or kw in topics for kw in
               ['aws', 'azure', 'gcp', 'cloud', 'kubernetes', 'docker', 'container']):
            categories.append('cloud')

        # Monitoring/Observability
        if any(kw in description or kw in name or kw in topics for kw in
               ['monitor', 'logging', 'metrics', 'observability', 'trace']):
            categories.append('monitoring')

        # Filesystem
        if any(kw in description or kw in name or kw in topics for kw in
               ['file', 'filesystem', 'storage']):
            categories.append('filesystem')

        # NixOS/Nix
        if any(kw in description or kw in name or kw in topics for kw in
               ['nix', 'nixos', 'nixpkgs']):
            categories.append('nixos')

        # Web/API
        if any(kw in description or kw in name or kw in topics for kw in
               ['web', 'api', 'http', 'rest', 'graphql']):
            categories.append('web')

        return categories or ['general']

    def process_repository(self, repo: Dict[str, Any]) -> Dict[str, Any]:
        """Process repository and extract MCP server metadata"""
        full_name = repo.get('full_name', '')

        # Skip if already processed
        if full_name in self.servers:
            return None

        # Filter: must be MCP-related
        description = (repo.get('description', '') or '').lower()
        topics = [t.lower() for t in repo.get('topics', [])]
        name = repo.get('name', '').lower()

        mcp_keywords = ['mcp', 'model context protocol', 'model-context-protocol']
        is_mcp = any(kw in description or kw in name or kw in topics for kw in mcp_keywords)

        if not is_mcp:
            return None

        # Calculate metrics
        score = self.calculate_score(repo)
        categories = self.categorize_server(repo)

        server_data = {
            'name': repo.get('name', ''),
            'full_name': full_name,
            'description': repo.get('description', 'No description'),
            'url': repo.get('html_url', ''),
            'stars': repo.get('stargazers_count', 0),
            'forks': repo.get('forks_count', 0),
            'watchers': repo.get('watchers_count', 0),
            'open_issues': repo.get('open_issues_count', 0),
            'language': repo.get('language', 'Unknown'),
            'topics': repo.get('topics', []),
            'created_at': repo.get('created_at', ''),
            'updated_at': repo.get('updated_at', ''),
            'license': repo.get('license', {}).get('name', 'No license') if repo.get('license') else 'No license',
            'categories': categories,
            'score': score,
            'rank': 0,  # Will be set after sorting
            'discovered_at': datetime.now().isoformat()
        }

        self.servers[full_name] = server_data
        return server_data

    def search_all_categories(self) -> Dict[str, Any]:
        """Search all categories and compile results"""
        print(f"Searching {len(SEARCH_QUERIES)} query categories...")

        all_repos = []

        # Sequential search to respect rate limits
        for i, query in enumerate(SEARCH_QUERIES, 1):
            print(f"[{i}/{len(SEARCH_QUERIES)}] Searching: {query}")
            repos = self.search_github(query, max_results=30)
            all_repos.extend(repos)

            # Rate limit check
            if self.rate_limit_remaining < 10:
                print(f"Rate limit low ({self.rate_limit_remaining}), pausing...")
                time.sleep(2)

        # Process all repositories
        print(f"\nProcessing {len(all_repos)} repositories...")
        for repo in all_repos:
            self.process_repository(repo)

        # Rank servers by score
        sorted_servers = sorted(
            self.servers.values(),
            key=lambda x: x['score'],
            reverse=True
        )

        for rank, server in enumerate(sorted_servers, 1):
            server['rank'] = rank

        return {
            'total_servers': len(self.servers),
            'search_queries': len(SEARCH_QUERIES),
            'generated_at': datetime.now().isoformat(),
            'servers': sorted_servers
        }

    def export_to_aidb(self, results: Dict[str, Any], aidb_url: str = f"http://{SERVICE_HOST}:8091/documents") -> bool:
        """Export results to AIDB"""
        # Create comprehensive document
        document = {
            'project': 'NixOS-Dev-Quick-Deploy',
            'file_path': 'mcp-servers/comprehensive-directory.json',
            'content': json.dumps(results, indent=2),
            'metadata': {
                'type': 'mcp-directory',
                'total_servers': results['total_servers'],
                'generated_at': results['generated_at'],
                'categories': list(set(cat for server in results['servers'] for cat in server['categories']))
            }
        }

        try:
            response = requests.post(aidb_url, json=document, timeout=10)
            response.raise_for_status()
            print(f"✅ Exported {results['total_servers']} MCP servers to AIDB")
            return True
        except Exception as e:
            print(f"❌ Failed to export to AIDB: {e}")
            return False

    def save_results(self, results: Dict[str, Any], filename: str) -> None:
        """Save results to JSON file"""
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"✅ Saved results to {filename}")

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Discover MCP servers on GitHub and export a ranked directory (optionally into AIDB)."
    )
    parser.add_argument(
        "--output",
        default="docs/mcp-servers-directory.json",
        help="Path to write the JSON directory (default: docs/mcp-servers-directory.json)",
    )
    parser.add_argument(
        "--no-aidb",
        action="store_true",
        help="Skip exporting results into AIDB (only write the JSON file).",
    )
    parser.add_argument(
        "--aidb-url",
        default=os.environ.get("AIDB_URL", f"http://{SERVICE_HOST}:8091/documents"),
        help="AIDB documents endpoint (default: %(default)s or $AIDB_URL if set).",
    )
    return parser.parse_args()

def main():
    print("🔍 Comprehensive MCP Server Discovery")
    print("=" * 60)

    args = parse_args()

    # Initialize discovery
    api_token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GITHUB_API_TOKEN")
    if api_token:
        print("Using GitHub API token from environment for higher rate limits.")
    discovery = MCPServerDiscovery(api_token=api_token)

    # Search all categories
    results = discovery.search_all_categories()

    # Display summary
    print("\n📊 Discovery Summary:")
    print(f"Total MCP Servers Found: {results['total_servers']}")
    print(f"Search Queries Used: {results['search_queries']}")

    # Category breakdown
    categories = {}
    for server in results['servers']:
        for cat in server['categories']:
            categories[cat] = categories.get(cat, 0) + 1

    print("\nCategories:")
    for cat, count in sorted(categories.items(), key=lambda x: x[1], reverse=True):
        print(f"  {cat}: {count} servers")

    # Top 10 servers
    print("\n🏆 Top 10 MCP Servers by Score:")
    for i, server in enumerate(results['servers'][:10], 1):
        print(f"{i}. {server['name']} (⭐{server['stars']} | Score: {server['score']})")
        print(f"   {server['description'][:80]}...")
        print(f"   Categories: {', '.join(server['categories'])}")

    # Save results
    discovery.save_results(results, args.output)

    # Export to AIDB (optional)
    if not args.no_aidb:
        discovery.export_to_aidb(results, aidb_url=args.aidb_url)

    print("\n✅ Discovery complete!")

if __name__ == "__main__":
    main()
