#!/usr/bin/env python3
"""
model_tiering.py — Logic for Token Arbitrage and Complexity Estimation.
"""

from typing import Dict, Any, List

def estimate_task_complexity(query: str, tool_names: List[str] = []) -> str:
    """
    Estimate if a task is 'simple' (L1) or 'complex' (L2).
    
    Simple tasks (L1):
    - Triage (ls, grep, read_file)
    - File summaries
    - Status checks
    
    Complex tasks (L2):
    - Multi-file refactors
    - Planning
    - Architecture review
    """
    query_lower = query.lower()
    
    # Read-only or high-signal triage tools always route to L1
    l1_tools = {"ls", "grep", "read_file", "acat", "als", "agrep", "list_directory"}
    if any(tool in l1_tools for tool in tool_names):
        return "L1"

    # Keywords for L2 (Reasoning)
    l2_keywords = {"refactor", "plan", "design", "architecture", "implement", "fix", "debug"}
    if any(word in query_lower for word in l2_keywords):
        return "L2"
        
    # Default to L1 for short, simple queries
    if len(query.split()) < 15:
        return "L1"
        
    return "L2"

def get_recommended_model(complexity: str) -> str:
    """Map complexity to model tier."""
    if complexity == "L1":
        return "llama-3-8b"
    return "qwen-3-35b"
