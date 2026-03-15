#!/usr/bin/env python3
"""
Improvement Candidate Detector

Automatically identifies code improvement opportunities through:
- Code smell detection
- Performance regression analysis
- Pattern mining from telemetry
- LLM-based code review

Part of Phase 3 Batch 3.1: Improvement Candidate Detection
"""

import ast
import json
import logging
import re
import subprocess
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


@dataclass
class CodeSmell:
    """Detected code smell"""
    file_path: str
    line_number: int
    smell_type: str
    severity: str  # "critical", "high", "medium", "low"
    description: str
    suggestion: str
    confidence: float  # 0.0-1.0


@dataclass
class PerformanceRegression:
    """Detected performance regression"""
    operation: str
    baseline_ms: float
    current_ms: float
    regression_pct: float
    severity: str
    affected_code: List[str]
    recommendation: str


@dataclass
class ImprovementCandidate:
    """Identified improvement opportunity"""
    title: str
    category: str  # "performance", "quality", "security", "maintainability"
    priority: int  # 1-5, 1 highest
    estimated_impact: str  # "high", "medium", "low"
    effort: str  # "low", "medium", "high"
    description: str
    evidence: List[str]
    suggested_changes: List[str]
    related_files: List[str]


class CodeSmellDetector:
    """Detects code smells in Python code"""

    def __init__(self):
        self.smells: List[CodeSmell] = []

    def detect_in_file(self, file_path: Path) -> List[CodeSmell]:
        """Detect code smells in a Python file"""
        if not file_path.suffix == ".py":
            return []

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                source = f.read()

            # Parse AST
            tree = ast.parse(source, filename=str(file_path))

            smells = []

            # Check for various code smells
            smells.extend(self._detect_long_functions(tree, file_path))
            smells.extend(self._detect_high_complexity(tree, file_path))
            smells.extend(self._detect_duplicate_code(source, file_path))
            smells.extend(self._detect_magic_numbers(tree, file_path))
            smells.extend(self._detect_broad_exceptions(tree, file_path))
            smells.extend(self._detect_dead_code(tree, file_path))

            return smells

        except Exception as e:
            logger.warning(f"Failed to analyze {file_path}: {e}")
            return []

    def _detect_long_functions(self, tree: ast.AST, file_path: Path) -> List[CodeSmell]:
        """Detect overly long functions"""
        smells = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Count lines in function
                if hasattr(node, "end_lineno") and hasattr(node, "lineno"):
                    length = node.end_lineno - node.lineno

                    if length > 100:
                        severity = "high"
                        suggestion = "Consider breaking into smaller functions"
                    elif length > 50:
                        severity = "medium"
                        suggestion = "Function is getting long, consider refactoring"
                    else:
                        continue

                    smells.append(CodeSmell(
                        file_path=str(file_path),
                        line_number=node.lineno,
                        smell_type="long_function",
                        severity=severity,
                        description=f"Function '{node.name}' is {length} lines long",
                        suggestion=suggestion,
                        confidence=0.9,
                    ))

        return smells

    def _detect_high_complexity(self, tree: ast.AST, file_path: Path) -> List[CodeSmell]:
        """Detect high cyclomatic complexity"""
        smells = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                complexity = self._calculate_complexity(node)

                if complexity > 15:
                    severity = "high"
                    suggestion = "High complexity - refactor into smaller functions"
                elif complexity > 10:
                    severity = "medium"
                    suggestion = "Consider simplifying logic"
                else:
                    continue

                smells.append(CodeSmell(
                    file_path=str(file_path),
                    line_number=node.lineno,
                    smell_type="high_complexity",
                    severity=severity,
                    description=f"Function '{node.name}' has complexity {complexity}",
                    suggestion=suggestion,
                    confidence=0.85,
                ))

        return smells

    def _calculate_complexity(self, node: ast.FunctionDef) -> int:
        """Calculate cyclomatic complexity (simplified)"""
        complexity = 1  # Base complexity

        for child in ast.walk(node):
            # Count decision points
            if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1

        return complexity

    def _detect_duplicate_code(self, source: str, file_path: Path) -> List[CodeSmell]:
        """Detect potential code duplication"""
        smells = []

        # Simple heuristic: look for similar multiline blocks
        lines = source.split("\n")
        line_hashes = defaultdict(list)

        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                line_hashes[hash(stripped)].append(i)

        # Find lines that appear multiple times
        for line_hash, line_numbers in line_hashes.items():
            if len(line_numbers) > 3:  # Same line appears >3 times
                smells.append(CodeSmell(
                    file_path=str(file_path),
                    line_number=line_numbers[0],
                    smell_type="code_duplication",
                    severity="medium",
                    description=f"Code pattern repeated {len(line_numbers)} times",
                    suggestion="Extract into reusable function or constant",
                    confidence=0.7,
                ))

        return smells[:5]  # Limit to top 5

    def _detect_magic_numbers(self, tree: ast.AST, file_path: Path) -> List[CodeSmell]:
        """Detect magic numbers"""
        smells = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Num):
                # Skip common numbers
                if node.n in (0, 1, -1, 2, 10, 100, 1000):
                    continue

                # Skip if in constant assignment
                parent = getattr(node, "parent", None)
                if isinstance(parent, ast.Assign):
                    continue

                smells.append(CodeSmell(
                    file_path=str(file_path),
                    line_number=getattr(node, "lineno", 0),
                    smell_type="magic_number",
                    severity="low",
                    description=f"Magic number: {node.n}",
                    suggestion="Extract to named constant",
                    confidence=0.6,
                ))

        return smells[:10]  # Limit output

    def _detect_broad_exceptions(self, tree: ast.AST, file_path: Path) -> List[CodeSmell]:
        """Detect overly broad exception handling"""
        smells = []

        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                if node.type is None:  # bare except:
                    smells.append(CodeSmell(
                        file_path=str(file_path),
                        line_number=getattr(node, "lineno", 0),
                        smell_type="broad_exception",
                        severity="high",
                        description="Bare except clause catches all exceptions",
                        suggestion="Catch specific exception types",
                        confidence=0.95,
                    ))
                elif isinstance(node.type, ast.Name) and node.type.id == "Exception":
                    smells.append(CodeSmell(
                        file_path=str(file_path),
                        line_number=getattr(node, "lineno", 0),
                        smell_type="broad_exception",
                        severity="medium",
                        description="Catching generic Exception",
                        suggestion="Catch more specific exception types",
                        confidence=0.8,
                    ))

        return smells

    def _detect_dead_code(self, tree: ast.AST, file_path: Path) -> List[CodeSmell]:
        """Detect potentially dead code"""
        smells = []

        # Look for functions that are defined but never called (simple heuristic)
        defined_functions = set()
        called_functions = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                defined_functions.add(node.name)
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    called_functions.add(node.func.id)

        # Find functions that might be dead
        potentially_dead = defined_functions - called_functions

        # Filter out special methods and public API
        for func_name in potentially_dead:
            if func_name.startswith("_") and not func_name.startswith("__"):
                # Private function never called
                smells.append(CodeSmell(
                    file_path=str(file_path),
                    line_number=0,  # Would need more analysis
                    smell_type="dead_code",
                    severity="low",
                    description=f"Private function '{func_name}' appears unused",
                    suggestion="Remove if truly unused, or make public if API",
                    confidence=0.5,
                ))

        return smells[:5]


class PerformanceRegressionDetector:
    """Detects performance regressions from telemetry"""

    def __init__(self, baseline_file: Optional[Path] = None):
        self.baseline_file = baseline_file or Path(".agents/performance/baseline.json")
        self.baseline: Dict[str, float] = {}

        if self.baseline_file.exists():
            with open(self.baseline_file) as f:
                self.baseline = json.load(f)

    def update_baseline(self, metrics: Dict[str, float]):
        """Update performance baseline"""
        self.baseline.update(metrics)

        self.baseline_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.baseline_file, "w") as f:
            json.dump(self.baseline, f, indent=2)

        logger.info(f"Baseline updated with {len(metrics)} metrics")

    def detect_regressions(
        self,
        current_metrics: Dict[str, float],
        threshold_pct: float = 20.0,
    ) -> List[PerformanceRegression]:
        """Detect performance regressions"""
        regressions = []

        for operation, current_ms in current_metrics.items():
            baseline_ms = self.baseline.get(operation)

            if baseline_ms is None:
                continue

            # Calculate regression
            regression_pct = ((current_ms - baseline_ms) / baseline_ms) * 100

            if regression_pct > threshold_pct:
                # Determine severity
                if regression_pct > 100:
                    severity = "critical"
                elif regression_pct > 50:
                    severity = "high"
                else:
                    severity = "medium"

                regression = PerformanceRegression(
                    operation=operation,
                    baseline_ms=baseline_ms,
                    current_ms=current_ms,
                    regression_pct=regression_pct,
                    severity=severity,
                    affected_code=[],  # Would need code analysis
                    recommendation=self._generate_recommendation(operation, regression_pct),
                )

                regressions.append(regression)

        return regressions

    def _generate_recommendation(self, operation: str, regression_pct: float) -> str:
        """Generate recommendation for regression"""
        if regression_pct > 100:
            return f"{operation} performance degraded by {regression_pct:.1f}% - URGENT investigation needed"
        elif regression_pct > 50:
            return f"{operation} shows significant slowdown ({regression_pct:.1f}%) - profile and optimize"
        else:
            return f"{operation} performance regression detected ({regression_pct:.1f}%) - monitor and investigate"


class ImprovementCandidateGenerator:
    """Generates prioritized improvement candidates"""

    def __init__(self):
        self.code_smell_detector = CodeSmellDetector()
        self.regression_detector = PerformanceRegressionDetector()

    def generate_candidates(
        self,
        code_paths: List[Path],
        current_metrics: Optional[Dict[str, float]] = None,
    ) -> List[ImprovementCandidate]:
        """Generate improvement candidates"""
        candidates = []

        # Code quality improvements
        for path in code_paths:
            if path.is_file() and path.suffix == ".py":
                smells = self.code_smell_detector.detect_in_file(path)
                candidates.extend(self._smells_to_candidates(smells))

        # Performance improvements
        if current_metrics:
            regressions = self.regression_detector.detect_regressions(current_metrics)
            candidates.extend(self._regressions_to_candidates(regressions))

        # Sort by priority
        candidates.sort(key=lambda c: (c.priority, -self._impact_score(c.estimated_impact)))

        return candidates

    def _smells_to_candidates(self, smells: List[CodeSmell]) -> List[ImprovementCandidate]:
        """Convert code smells to improvement candidates"""
        # Group smells by type
        grouped = defaultdict(list)
        for smell in smells:
            grouped[smell.smell_type].append(smell)

        candidates = []

        for smell_type, smell_list in grouped.items():
            # Skip if not enough occurrences
            if len(smell_list) < 2:
                continue

            # Determine priority based on severity
            severity_scores = {"critical": 1, "high": 2, "medium": 3, "low": 4}
            avg_severity = sum(severity_scores[s.severity] for s in smell_list) / len(smell_list)
            priority = min(5, int(avg_severity) + 1)

            candidate = ImprovementCandidate(
                title=f"Address {smell_type} issues ({len(smell_list)} occurrences)",
                category="quality",
                priority=priority,
                estimated_impact="medium",
                effort="medium",
                description=f"Multiple instances of {smell_type} detected across codebase",
                evidence=[f"{s.file_path}:{s.line_number} - {s.description}" for s in smell_list[:5]],
                suggested_changes=[smell_list[0].suggestion],
                related_files=list(set(s.file_path for s in smell_list)),
            )

            candidates.append(candidate)

        return candidates

    def _regressions_to_candidates(
        self,
        regressions: List[PerformanceRegression],
    ) -> List[ImprovementCandidate]:
        """Convert performance regressions to candidates"""
        candidates = []

        for regression in regressions:
            severity_priority = {
                "critical": 1,
                "high": 2,
                "medium": 3,
                "low": 4,
            }

            candidate = ImprovementCandidate(
                title=f"Fix performance regression in {regression.operation}",
                category="performance",
                priority=severity_priority[regression.severity],
                estimated_impact="high" if regression.regression_pct > 50 else "medium",
                effort="medium",
                description=f"{regression.operation} degraded by {regression.regression_pct:.1f}%",
                evidence=[
                    f"Baseline: {regression.baseline_ms:.1f}ms",
                    f"Current: {regression.current_ms:.1f}ms",
                    f"Regression: {regression.regression_pct:.1f}%",
                ],
                suggested_changes=[regression.recommendation],
                related_files=[],
            )

            candidates.append(candidate)

        return candidates

    def _impact_score(self, impact: str) -> int:
        """Convert impact to numeric score"""
        return {"high": 3, "medium": 2, "low": 1}.get(impact, 1)

    def export_candidates(self, candidates: List[ImprovementCandidate], output_path: Path):
        """Export candidates to JSON"""
        data = {
            "generated_at": datetime.now().isoformat(),
            "total_candidates": len(candidates),
            "candidates": [
                {
                    "title": c.title,
                    "category": c.category,
                    "priority": c.priority,
                    "estimated_impact": c.estimated_impact,
                    "effort": c.effort,
                    "description": c.description,
                    "evidence": c.evidence,
                    "suggested_changes": c.suggested_changes,
                    "related_files": c.related_files,
                }
                for c in candidates
            ],
        }

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)

        logger.info(f"Exported {len(candidates)} candidates to {output_path}")


if __name__ == "__main__":
    # Test improvement detection
    logging.basicConfig(level=logging.INFO)

    generator = ImprovementCandidateGenerator()

    # Scan AI stack code
    code_paths = list(Path("ai-stack").rglob("*.py"))[:20]  # Limit for testing

    logger.info(f"Scanning {len(code_paths)} Python files...")
    candidates = generator.generate_candidates(code_paths)

    logger.info(f"\nFound {len(candidates)} improvement candidates:")
    for i, candidate in enumerate(candidates[:10], 1):
        logger.info(f"\n{i}. {candidate.title}")
        logger.info(f"   Priority: {candidate.priority}, Impact: {candidate.estimated_impact}")
        logger.info(f"   {candidate.description}")

    # Export
    output_path = Path(".agents/improvement/candidates.json")
    generator.export_candidates(candidates, output_path)
    logger.info(f"\nFull report: {output_path}")
