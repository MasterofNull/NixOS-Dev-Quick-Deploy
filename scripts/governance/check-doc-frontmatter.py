#!/usr/bin/env python3
"""
scripts/governance/check-doc-frontmatter.py
Validates YAML frontmatter in markdown files against config/doc-frontmatter-schema.yaml.
Uses 'yq' as a fallback if PyYAML is not installed.
"""

import os
import sys
import json
import argparse
import re
import subprocess
from typing import List, Dict, Any, Optional

SCHEMA_PATH = "config/doc-frontmatter-schema.yaml"

def load_yaml(path_or_content: str, is_content: bool = False) -> Any:
    """Loads YAML using PyYAML or yq fallback."""
    try:
        import yaml
        if is_content:
            return yaml.safe_load(path_or_content)
        with open(path_or_content, 'r') as f:
            return yaml.safe_load(f)
    except ImportError:
        # Fallback to yq
        if is_content:
            cmd = ["yq", "-o", "json"]
            result = subprocess.run(cmd, input=path_or_content, capture_output=True, text=True)
        else:
            cmd = ["yq", "-o", "json", path_or_content]
            result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise ValueError(f"yq failed: {result.stderr}")
        return json.loads(result.stdout)

def dump_yaml(data: Any) -> str:
    """Dumps data to YAML string using PyYAML or yq fallback."""
    try:
        import yaml
        return yaml.dump(data, sort_keys=False)
    except ImportError:
        # Fallback to yq
        cmd = ["yq", "-P", "-o", "yaml"]
        result = subprocess.run(cmd, input=json.dumps(data), capture_output=True, text=True)
        if result.returncode != 0:
            raise ValueError(f"yq failed to dump: {result.stderr}")
        return result.stdout

def get_doc_type_from_path(file_path: str) -> Optional[str]:
    """Infers doc_type from file path if possible."""
    if "skills/" in file_path:
        return "skill"
    if "plans/" in file_path or "PRD" in file_path:
        if "PRD" in file_path:
            return "prd"
        return "plan"
    if "HANDOFF" in file_path:
        return "handoff"
    if "memory/" in file_path or "MEMORY" in file_path:
        return "memory"
    return None

def validate_frontmatter(file_path: str, schema: Dict[str, Any], fix_missing: bool = False) -> bool:
    try:
        with open(file_path, 'r') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return False

    # Regex to find YAML frontmatter
    match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
    
    if not match:
        if fix_missing:
            doc_type = get_doc_type_from_path(file_path)
            if doc_type and doc_type in schema['doc_types']:
                example = schema['doc_types'][doc_type]['examples']
                # Try to infer ID from filename
                if 'id' in example:
                    filename = os.path.basename(os.path.dirname(file_path)) if "SKILL.md" in file_path else os.path.splitext(os.path.basename(file_path))[0]
                    example['id'] = filename.lower()
                
                header = "---\n" + dump_yaml(example) + "---\n\n"
                with open(file_path, 'w') as f:
                    f.write(header + content)
                print(f"Fixed: Added minimal frontmatter to {file_path}")
                return True
            else:
                # print(f"Skipping {file_path}: No frontmatter and could not infer doc_type")
                return True # Old docs are exempt if we can't infer
        return True # Old docs are exempt if no frontmatter

    try:
        data = load_yaml(match.group(1), is_content=True)
    except Exception as e:
        print(f"Error: Invalid YAML in {file_path}: {e}")
        return False

    if not data or not isinstance(data, dict):
        # Malformed or empty frontmatter in a legacy doc — skip.
        return True

    doc_type = data.get('doc_type')
    if not doc_type:
        # Pre-schema legacy doc — has frontmatter but no doc_type.
        # Exempt until explicitly migrated (phased rollout).
        return True

    if doc_type not in schema['doc_types']:
        print(f"Error: Unknown doc_type '{doc_type}' in {file_path}")
        return False

    type_schema = schema['doc_types'][doc_type]
    required_fields = type_schema.get('required', [])
    
    errors = []
    for field in required_fields:
        if field not in data:
            errors.append(f"Missing required field: {field}")

    # Validate allowed values if globals defined
    globals_schema = schema.get('globals', {})
    if 'status' in data and 'allowed_status' in globals_schema:
        if data['status'] not in globals_schema['allowed_status']:
            errors.append(f"Invalid status '{data['status']}'. Allowed: {globals_schema['allowed_status']}")

    if errors:
        print(f"Validation failed for {file_path} ({doc_type}):")
        for err in errors:
            print(f"  - {err}")
        return False

    return True

def main():
    parser = argparse.ArgumentParser(description="Validate markdown frontmatter")
    parser.add_argument("files", nargs="*", help="Files to check")
    parser.add_argument("--all", action="store_true", help="Scan all relevant directories")
    parser.add_argument("--fix-missing", action="store_true", help="Add minimal valid frontmatter to files that have none")
    args = parser.parse_args()

    try:
        schema = load_yaml(SCHEMA_PATH)
    except Exception as e:
        print(f"Error loading schema: {e}")
        sys.exit(1)
    
    files_to_check = args.files
    if args.all:
        # Define relevant directories
        dirs = ['.agent/', '.agents/plans/', 'ai-stack/agent-memory/']
        for d in dirs:
            if os.path.exists(d):
                for root, _, filenames in os.walk(d):
                    for f in filenames:
                        if f.endswith(".md"):
                            files_to_check.append(os.path.join(root, f))

    if not files_to_check:
        print("No files to check.")
        return

    success = True
    for file_path in files_to_check:
        if not validate_frontmatter(file_path, schema, args.fix_missing):
            success = False

    if not success:
        sys.exit(1)
    else:
        print("Frontmatter validation passed.")

if __name__ == "__main__":
    main()
