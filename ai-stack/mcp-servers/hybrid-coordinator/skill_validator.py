"""
skill_validator.py — External Skill Import Validation

Validates external skills before import to ensure:
- Proper markdown structure
- Required sections present
- No security issues (malicious code, unsafe commands)
- Metadata completeness
- Quality scoring

Batch 5.2: External Skill Import Validation
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Validation Rules
# ---------------------------------------------------------------------------

REQUIRED_SECTIONS = ["description", "when to use"]
RECOMMENDED_SECTIONS = ["usage", "examples", "notes"]

# Security patterns to check for
UNSAFE_PATTERNS = [
    r"rm\s+-rf",  # Dangerous file deletion
    r"sudo\s+",  # Sudo usage
    r"eval\s*\(",  # eval() execution
    r"exec\s*\(",  # exec() execution
    r"import\s+subprocess",  # Subprocess import (potential command injection)
    r"os\.system",  # OS system calls
    r"__import__",  # Dynamic imports
    r"\|.*sh",  # Pipe to shell
]

# Quality indicators
QUALITY_INDICATORS = {
    "has_code_examples": 10,
    "has_usage_section": 10,
    "has_notes_section": 5,
    "has_limitations_section": 5,
    "has_keywords": 5,
    "proper_heading_structure": 10,
    "adequate_description_length": 10,  # At least 50 chars
    "has_when_to_use": 15,
}


# ---------------------------------------------------------------------------
# Validation Result
# ---------------------------------------------------------------------------

@dataclass
class ValidationResult:
    """Result of skill validation."""
    valid: bool
    quality_score: float  # 0-100
    errors: List[str]
    warnings: List[str]
    suggestions: List[str]
    detected_sections: List[str]
    security_issues: List[str]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "valid": self.valid,
            "quality_score": round(self.quality_score, 1),
            "errors": self.errors,
            "warnings": self.warnings,
            "suggestions": self.suggestions,
            "detected_sections": self.detected_sections,
            "security_issues": self.security_issues,
        }


# ---------------------------------------------------------------------------
# Skill Validation Functions
# ---------------------------------------------------------------------------

def validate_skill_content(content: str, slug: str) -> ValidationResult:
    """
    Validate skill content for quality and security.

    Args:
        content: Skill markdown content
        slug: Skill identifier

    Returns:
        ValidationResult with validation outcome
    """
    errors: List[str] = []
    warnings: List[str] = []
    suggestions: List[str] = []
    security_issues: List[str] = []
    quality_score = 0.0

    # Basic content checks
    if not content or len(content.strip()) < 50:
        errors.append("Skill content too short (minimum 50 characters)")
        return ValidationResult(
            valid=False,
            quality_score=0.0,
            errors=errors,
            warnings=warnings,
            suggestions=suggestions,
            detected_sections=[],
            security_issues=security_issues,
        )

    # Detect sections
    detected_sections = _detect_sections(content)

    # Check required sections
    missing_required = []
    for section in REQUIRED_SECTIONS:
        if not any(section.lower() in s.lower() for s in detected_sections):
            missing_required.append(section)

    if missing_required:
        errors.append(f"Missing required sections: {', '.join(missing_required)}")

    # Check recommended sections
    missing_recommended = []
    for section in RECOMMENDED_SECTIONS:
        if not any(section.lower() in s.lower() for s in detected_sections):
            missing_recommended.append(section)

    if missing_recommended:
        warnings.append(f"Missing recommended sections: {', '.join(missing_recommended)}")

    # Security validation
    security_issues = _check_security_patterns(content)

    if security_issues:
        errors.append(f"Security issues found: {len(security_issues)} patterns detected")

    # Quality scoring
    quality_score = _calculate_quality_score(content, detected_sections, security_issues)

    # Generate suggestions
    if quality_score < 70:
        suggestions.append("Consider adding more detail to improve quality score")
    if "usage" not in [s.lower() for s in detected_sections]:
        suggestions.append("Add a 'Usage' section with examples")
    if not re.search(r"```", content):
        suggestions.append("Add code examples in markdown code blocks")

    # Determine validity
    valid = len(errors) == 0 and len(security_issues) == 0

    return ValidationResult(
        valid=valid,
        quality_score=quality_score,
        errors=errors,
        warnings=warnings,
        suggestions=suggestions,
        detected_sections=detected_sections,
        security_issues=security_issues,
    )


def _detect_sections(content: str) -> List[str]:
    """
    Detect markdown sections from headers.

    Args:
        content: Markdown content

    Returns:
        List of detected section names
    """
    sections = []
    # Match markdown headers (# Header, ## Header, etc.)
    header_pattern = r"^#{1,6}\s+(.+)$"

    for line in content.split("\n"):
        match = re.match(header_pattern, line.strip())
        if match:
            section_name = match.group(1).strip()
            sections.append(section_name)

    return sections


def _check_security_patterns(content: str) -> List[str]:
    """
    Check for unsafe patterns in skill content.

    Args:
        content: Skill content to check

    Returns:
        List of security issues found
    """
    issues = []

    for pattern in UNSAFE_PATTERNS:
        matches = re.findall(pattern, content, re.IGNORECASE)
        if matches:
            issues.append(f"Unsafe pattern detected: {pattern}")

    return issues


def _calculate_quality_score(
    content: str,
    detected_sections: List[str],
    security_issues: List[str],
) -> float:
    """
    Calculate quality score for a skill.

    Args:
        content: Skill content
        detected_sections: List of detected sections
        security_issues: List of security issues

    Returns:
        Quality score 0-100
    """
    score = 0.0

    # Base score for having content
    score += 20.0

    # Section-based scoring
    section_names_lower = [s.lower() for s in detected_sections]

    if any("usage" in s for s in section_names_lower):
        score += QUALITY_INDICATORS["has_usage_section"]

    if any("notes" in s or "note" in s for s in section_names_lower):
        score += QUALITY_INDICATORS["has_notes_section"]

    if any("limitations" in s or "limitation" in s for s in section_names_lower):
        score += QUALITY_INDICATORS["has_limitations_section"]

    if any("when to use" in s for s in section_names_lower):
        score += QUALITY_INDICATORS["has_when_to_use"]

    # Code examples
    if re.search(r"```", content):
        score += QUALITY_INDICATORS["has_code_examples"]

    # Proper heading structure (at least 3 sections)
    if len(detected_sections) >= 3:
        score += QUALITY_INDICATORS["proper_heading_structure"]

    # Adequate description
    desc_match = re.search(r"##?\s+Description\s*\n(.+?)(?:\n#|\Z)", content, re.IGNORECASE | re.DOTALL)
    if desc_match and len(desc_match.group(1).strip()) >= 50:
        score += QUALITY_INDICATORS["adequate_description_length"]

    # Penalty for security issues
    if security_issues:
        score -= len(security_issues) * 20.0

    # Clamp to 0-100 range
    return max(0.0, min(100.0, score))


def validate_skill_metadata(metadata: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validate skill metadata completeness.

    Args:
        metadata: Skill metadata dictionary

    Returns:
        (is_valid, list of errors)
    """
    errors = []

    # Required fields
    required_fields = ["slug", "source_path"]
    for field in required_fields:
        if not metadata.get(field):
            errors.append(f"Missing required field: {field}")

    # Slug validation
    slug = metadata.get("slug", "")
    if slug and not re.match(r"^[a-z0-9-]+$", slug):
        errors.append(f"Invalid slug format: {slug} (must be lowercase alphanumeric with hyphens)")

    is_valid = len(errors) == 0
    return is_valid, errors


def get_validation_summary(results: List[ValidationResult]) -> Dict[str, Any]:
    """
    Get summary of multiple validation results.

    Args:
        results: List of validation results

    Returns:
        Summary dictionary
    """
    total = len(results)
    valid_count = sum(1 for r in results if r.valid)
    avg_quality = sum(r.quality_score for r in results) / total if total > 0 else 0.0

    security_issue_count = sum(len(r.security_issues) for r in results)

    return {
        "total_skills": total,
        "valid_skills": valid_count,
        "invalid_skills": total - valid_count,
        "avg_quality_score": round(avg_quality, 1),
        "security_issues_found": security_issue_count,
        "validation_rate": round(valid_count / total, 3) if total > 0 else 0.0,
    }
