#!/usr/bin/env python3
"""
Populate PostgreSQL Knowledge Base
Purpose: Automatically populate the database with all system documentation,
         code repository data, deployment history, and more.
"""

import os
import sys
import json
import hashlib
import subprocess
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
import psycopg2
from psycopg2.extras import execute_values
import re

# Database connection
DB_CONFIG = {
    'host': os.getenv('POSTGRES_HOST', 'localhost'),
    'port': int(os.getenv('POSTGRES_PORT', '5432')),
    'database': os.getenv('POSTGRES_DB', 'mcp'),
    'user': os.getenv('POSTGRES_USER', 'mcp'),
    'password': os.getenv('POSTGRES_PASSWORD', 'change_me_in_production')
}

PROJECT_ROOT = Path(__file__).parent.parent
DOCS_DIRS = [
    PROJECT_ROOT / 'docs',
    PROJECT_ROOT / 'ai-stack',
    PROJECT_ROOT,  # Root level markdown files
]

def connect_db():
    """Connect to PostgreSQL database"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        sys.exit(1)

def sha256(content: str) -> str:
    """Calculate SHA256 hash of content"""
    return hashlib.sha256(content.encode()).hexdigest()

def extract_title_from_markdown(content: str, filename: str) -> str:
    """Extract title from markdown content"""
    # Try to find # Title at the start
    lines = content.split('\n')
    for line in lines[:10]:  # Check first 10 lines
        if line.startswith('# '):
            return line[2:].strip()

    # Fallback to filename
    return filename.replace('.md', '').replace('-', ' ').replace('_', ' ').title()

def categorize_doc(file_path: Path) -> str:
    """Categorize documentation based on path"""
    path_str = str(file_path).lower()

    if 'fix' in path_str or 'bug' in path_str:
        return 'fixes'
    elif 'guide' in path_str or 'tutorial' in path_str or 'how-to' in path_str:
        return 'guides'
    elif 'api' in path_str or 'reference' in path_str:
        return 'reference'
    elif 'architecture' in path_str or 'design' in path_str:
        return 'architecture'
    elif 'deployment' in path_str or 'install' in path_str:
        return 'deployment'
    elif 'troubleshoot' in path_str or 'error' in path_str:
        return 'troubleshooting'
    elif 'ai' in path_str or 'ml' in path_str or 'llm' in path_str:
        return 'ai-ml'
    elif 'nixos' in path_str or 'nix' in path_str:
        return 'nixos'
    else:
        return 'general'

def extract_tags_from_content(content: str) -> List[str]:
    """Extract tags from markdown content"""
    tags = set()

    # Extract from headers
    headers = re.findall(r'^#+\s+(.+)$', content, re.MULTILINE)
    for header in headers[:5]:  # First 5 headers
        words = header.lower().split()
        tags.update([w for w in words if len(w) > 3 and w not in {'this', 'that', 'with', 'from', 'have'}])

    # Common technical terms
    tech_terms = ['nixos', 'docker', 'podman', 'python', 'pytorch', 'ai', 'ml', 'llm',
                  'postgres', 'redis', 'qdrant', 'deployment', 'container', 'database']
    for term in tech_terms:
        if term in content.lower():
            tags.add(term)

    return list(tags)[:10]  # Max 10 tags

def populate_documentation(conn):
    """Populate documentation table with all markdown files"""
    print("\n📚 Populating documentation...")

    cursor = conn.cursor()
    docs_found = 0
    docs_inserted = 0

    for docs_dir in DOCS_DIRS:
        if not docs_dir.exists():
            continue

        # Find all markdown files
        for md_file in docs_dir.rglob('*.md'):
            if '.git' in str(md_file) or 'node_modules' in str(md_file):
                continue

            docs_found += 1

            try:
                content = md_file.read_text()
                relative_path = md_file.relative_to(PROJECT_ROOT)

                title = extract_title_from_markdown(content, md_file.name)
                category = categorize_doc(md_file)
                tags = extract_tags_from_content(content)
                checksum = sha256(content)

                metadata = {
                    'file_size': md_file.stat().st_size,
                    'last_modified': md_file.stat().st_mtime,
                }

                # Check if already exists
                cursor.execute(
                    "SELECT checksum FROM documentation WHERE file_path = %s",
                    (str(relative_path),)
                )
                existing = cursor.fetchone()

                if existing and existing[0] == checksum:
                    # Already up to date
                    continue

                # Insert or update
                cursor.execute("""
                    INSERT INTO documentation (file_path, title, content, category, tags, checksum, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (file_path) DO UPDATE SET
                        content = EXCLUDED.content,
                        title = EXCLUDED.title,
                        category = EXCLUDED.category,
                        tags = EXCLUDED.tags,
                        checksum = EXCLUDED.checksum,
                        metadata = EXCLUDED.metadata,
                        updated_at = NOW()
                """, (str(relative_path), title, content, category, tags, checksum, json.dumps(metadata)))

                docs_inserted += 1

            except Exception as e:
                print(f"  ⚠️  Error processing {md_file.name}: {e}")

    conn.commit()
    print(f"  ✅ Found {docs_found} documents, inserted/updated {docs_inserted}")

def populate_repositories(conn):
    """Populate repositories table with git repository info"""
    print("\n📦 Populating repositories...")

    cursor = conn.cursor()

    # Get current repo info
    try:
        remote_url = subprocess.check_output(
            ['git', 'config', '--get', 'remote.origin.url'],
            cwd=PROJECT_ROOT, text=True
        ).strip()
    except:
        remote_url = None

    try:
        current_branch = subprocess.check_output(
            ['git', 'branch', '--show-current'],
            cwd=PROJECT_ROOT, text=True
        ).strip()
    except:
        current_branch = None

    try:
        latest_commit = subprocess.check_output(
            ['git', 'rev-parse', 'HEAD'],
            cwd=PROJECT_ROOT, text=True
        ).strip()
    except:
        latest_commit = None

    # Count files
    code_files = list(PROJECT_ROOT.rglob('*.py')) + list(PROJECT_ROOT.rglob('*.sh')) + \
                 list(PROJECT_ROOT.rglob('*.nix'))

    # Language distribution
    languages = {}
    for f in code_files:
        ext = f.suffix
        lang = {'.py': 'Python', '.sh': 'Bash', '.nix': 'Nix', '.js': 'JavaScript'}.get(ext, 'Other')
        languages[lang] = languages.get(lang, 0) + 1

    cursor.execute("""
        INSERT INTO repositories (name, path, remote_url, current_branch, latest_commit,
                                 file_count, primary_language, languages)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (path) DO UPDATE SET
            current_branch = EXCLUDED.current_branch,
            latest_commit = EXCLUDED.latest_commit,
            file_count = EXCLUDED.file_count,
            languages = EXCLUDED.languages,
            updated_at = NOW()
    """, ('NixOS-Dev-Quick-Deploy', str(PROJECT_ROOT), remote_url, current_branch,
          latest_commit, len(code_files), 'Python', json.dumps(languages)))

    conn.commit()
    print(f"  ✅ Repository info updated")

def populate_source_files(conn):
    """Populate source_files table with code files"""
    print("\n💻 Populating source files...")

    cursor = conn.cursor()

    # Get repository ID
    cursor.execute("SELECT id FROM repositories WHERE path = %s", (str(PROJECT_ROOT),))
    repo = cursor.fetchone()
    if not repo:
        print("  ⚠️  Repository not found, skipping")
        return

    repo_id = repo[0]

    # Scan code files
    file_patterns = ['*.py', '*.sh', '*.nix', '*.js', '*.rs', '*.go']
    files_inserted = 0

    for pattern in file_patterns:
        for code_file in PROJECT_ROOT.rglob(pattern):
            if '.git' in str(code_file) or 'node_modules' in str(code_file):
                continue

            try:
                relative_path = code_file.relative_to(PROJECT_ROOT)
                content = code_file.read_text()
                lines = content.split('\n')

                # Basic line counting
                code_lines = len([l for l in lines if l.strip() and not l.strip().startswith('#')])
                comment_lines = len([l for l in lines if l.strip().startswith('#')])
                blank_lines = len([l for l in lines if not l.strip()])

                language = {
                    '.py': 'Python',
                    '.sh': 'Bash',
                    '.nix': 'Nix',
                    '.js': 'JavaScript',
                    '.rs': 'Rust',
                    '.go': 'Go'
                }.get(code_file.suffix, 'Unknown')

                cursor.execute("""
                    INSERT INTO source_files (repository_id, file_path, relative_path, file_type,
                                            language, size_bytes, line_count, code_lines,
                                            comment_lines, blank_lines, content_hash, last_modified)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (repository_id, relative_path) DO UPDATE SET
                        size_bytes = EXCLUDED.size_bytes,
                        line_count = EXCLUDED.line_count,
                        code_lines = EXCLUDED.code_lines,
                        comment_lines = EXCLUDED.comment_lines,
                        blank_lines = EXCLUDED.blank_lines,
                        content_hash = EXCLUDED.content_hash,
                        last_modified = EXCLUDED.last_modified,
                        indexed_at = NOW()
                """, (repo_id, str(code_file), str(relative_path), code_file.suffix[1:],
                      language, code_file.stat().st_size, len(lines), code_lines,
                      comment_lines, blank_lines, sha256(content),
                      datetime.fromtimestamp(code_file.stat().st_mtime)))

                files_inserted += 1

            except Exception as e:
                print(f"  ⚠️  Error processing {code_file.name}: {e}")

    conn.commit()
    print(f"  ✅ Inserted/updated {files_inserted} source files")

def populate_packages(conn):
    """Populate packages table with installed packages"""
    print("\n📦 Populating packages...")

    cursor = conn.cursor()
    packages_inserted = 0

    # Get Nix packages
    try:
        nix_packages = subprocess.check_output(
            ['nix-env', '-q'], text=True
        ).strip().split('\n')

        for pkg_line in nix_packages:
            if not pkg_line.strip():
                continue

            # Parse package name and version
            parts = pkg_line.split('-')
            if len(parts) >= 2:
                name = '-'.join(parts[:-1])
                version = parts[-1]
            else:
                name = pkg_line
                version = 'unknown'

            cursor.execute("""
                INSERT INTO packages (package_manager, package_name, version, installed_version)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (package_manager, package_name) DO UPDATE SET
                    installed_version = EXCLUDED.installed_version,
                    last_checked = NOW()
            """, ('nix', name, version, version))

            packages_inserted += 1

    except Exception as e:
        print(f"  ⚠️  Error getting Nix packages: {e}")

    conn.commit()
    print(f"  ✅ Inserted/updated {packages_inserted} packages")

def populate_containers(conn):
    """Populate containers table with current container status"""
    print("\n🐳 Populating containers...")

    cursor = conn.cursor()

    try:
        # Get container info from podman
        containers_json = subprocess.check_output(
            ['podman', 'ps', '-a', '--format', 'json'],
            text=True
        )
        containers = json.loads(containers_json)

        for container in containers:
            cursor.execute("""
                INSERT INTO containers (container_id, name, image, status, ports, labels,
                                      started_at, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (container_id) DO UPDATE SET
                    status = EXCLUDED.status,
                    updated_at = NOW()
            """, (
                container.get('Id', '')[:64],
                container.get('Names', [''])[0] if isinstance(container.get('Names'), list) else container.get('Names', ''),
                container.get('Image', ''),
                container.get('State', ''),
                json.dumps(container.get('Ports', [])),
                json.dumps(container.get('Labels', {})),
                datetime.fromtimestamp(container.get('StartedAt', 0)) if container.get('StartedAt') else None,
                datetime.fromtimestamp(container.get('Created', 0)) if container.get('Created') else None
            ))

        conn.commit()
        print(f"  ✅ Updated {len(containers)} containers")

    except Exception as e:
        print(f"  ⚠️  Error getting container info: {e}")

def populate_system_snapshot(conn):
    """Create a system snapshot"""
    print("\n📸 Creating system snapshot...")

    cursor = conn.cursor()

    try:
        # Get NixOS version
        try:
            nixos_version = subprocess.check_output(
                ['nixos-version'], text=True
            ).strip()
        except:
            nixos_version = 'unknown'

        # Get kernel version
        try:
            kernel_version = subprocess.check_output(
                ['uname', '-r'], text=True
            ).strip()
        except:
            kernel_version = 'unknown'

        # Get memory usage
        try:
            mem_info = subprocess.check_output(
                ['free', '-m'], text=True
            ).split('\n')[1].split()
            memory_usage = int(mem_info[2])  # Used memory
        except:
            memory_usage = 0

        # Get disk usage
        try:
            df_output = subprocess.check_output(
                ['df', '-h'], text=True
            )
            disk_usage = {'raw': df_output}
        except:
            disk_usage = {}

        # Get CPU info
        try:
            cpu_info = {'model': subprocess.check_output(['lscpu'], text=True)}
        except:
            cpu_info = {}

        cursor.execute("""
            INSERT INTO system_snapshots (snapshot_type, nixos_version, kernel_version,
                                        memory_usage, disk_usage, cpu_info)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, ('manual', nixos_version, kernel_version, memory_usage,
              json.dumps(disk_usage), json.dumps(cpu_info)))

        conn.commit()
        print(f"  ✅ System snapshot created")

    except Exception as e:
        print(f"  ⚠️  Error creating snapshot: {e}")

def main():
    """Main execution"""
    print("=" * 70)
    print("  NixOS AI Stack - Knowledge Base Population")
    print("=" * 70)

    conn = connect_db()

    try:
        populate_documentation(conn)
        populate_repositories(conn)
        populate_source_files(conn)
        populate_packages(conn)
        populate_containers(conn)
        populate_system_snapshot(conn)

        # Show summary
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM documentation")
        doc_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM source_files")
        file_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM packages")
        pkg_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM containers")
        container_count = cursor.fetchone()[0]

        print("\n" + "=" * 70)
        print("  📊 Population Summary")
        print("=" * 70)
        print(f"  📚 Documentation files: {doc_count}")
        print(f"  💻 Source code files: {file_count}")
        print(f"  📦 Packages: {pkg_count}")
        print(f"  🐳 Containers: {container_count}")
        print("=" * 70)
        print("\n✅ Knowledge base population complete!")

    finally:
        conn.close()

if __name__ == '__main__':
    main()
