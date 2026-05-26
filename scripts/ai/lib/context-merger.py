#!/usr/bin/env python3
"""
context_merger.py — Hierarchical context loader for Agentic Engineering.
                    Walks up the directory tree and merges AGENTS.md/CLAUDE.md files.
"""

import os
from pathlib import Path
from typing import List, Optional

def get_hierarchical_context(start_path: Optional[Path] = None, filenames: List[str] = ["AGENTS.md", "CLAUDE.md"]) -> str:
    """
    Traverse from start_path upwards to the root, collecting and merging instructions.
    Child instructions are appended after parent instructions (so they can override).
    """
    if start_path is None:
        start_path = Path.cwd()
    
    start_path = start_path.resolve()
    # Ensure start_path is within the repo
    repo_root = find_repo_root(start_path)
    
    collected_files = []
    current = start_path
    
    while True:
        for filename in filenames:
            file_path = current / filename
            if file_path.is_file():
                collected_files.append(file_path)
        
        if current == repo_root or current == current.parent:
            break
        current = current.parent
        
    # Reverse so root files are processed first
    collected_files.reverse()
    
    merged_content = []
    for file_path in collected_files:
        try:
            with open(file_path, "r") as f:
                content = f.read().strip()
                if content:
                    merged_content.append(f"--- Context from: {file_path} ---\n{content}")
        except Exception as e:
            merged_content.append(f"--- Error reading {file_path}: {e} ---")
            
    return "\n\n".join(merged_content)

def find_repo_root(path: Path) -> Path:
    """Find the repository root by looking for .git or flake.nix."""
    current = path
    while current != current.parent:
        if (current / ".git").exists() or (current / "flake.nix").exists():
            return current
        current = current.parent
    return path # Fallback to start path if not found

if __name__ == "__main__":
    import sys
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    print(get_hierarchical_context(path))
