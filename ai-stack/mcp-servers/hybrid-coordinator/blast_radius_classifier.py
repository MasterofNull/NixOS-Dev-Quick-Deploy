import re
from typing import Dict, List

def classify(action: str) -> str:
    """
    Classify a string action or tool call into: "low" | "medium" | "high" | "critical"
    based on pattern matching.
    """
    action_lower = action.lower()

    critical_patterns = [
        r"\brm\s+-rf\b", r"\bdrop\s+table\b", r"--force\b", r"\bforce-push\b",
        r"\bnixos-rebuild\s+switch\b"
    ]
    high_patterns = [
        r"\bgit\s+push\b", r"\bgit\s+reset\b", r"\bdelete\s+/api/",
        r"\bnixos-rebuild\b", r"\bsystemctl\s+(stop|restart)\b"
    ]
    medium_patterns = [
        r"\bgit\s+commit\b", r"\bpost\s+/", r"\bput\s+/", r"\bpatch\s+/"
    ]

    for pattern in critical_patterns:
        if re.search(pattern, action_lower):
            return "critical"

    for pattern in high_patterns:
        if re.search(pattern, action_lower):
            return "high"

    for pattern in medium_patterns:
        if re.search(pattern, action_lower):
            return "medium"

    return "low"

def batch_classify(actions: List[str]) -> Dict[str, str]:
    """Classify a list of actions and return a mapping of action to blast radius."""
    return {action: classify(action) for action in actions}
