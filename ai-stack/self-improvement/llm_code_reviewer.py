#!/usr/bin/env python3
"""
LLM-Based Code Reviewer

Automated code review using LLMs to identify:
- Logic errors
- Best practice violations
- Security vulnerabilities
- Documentation issues
- Optimization opportunities

Part of Phase 3 Batch 3.1: Improvement Candidate Detection
"""

import asyncio
import json
import logging
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ReviewComment:
    """Code review comment"""
    file_path: str
    line_number: int
    severity: str  # "critical", "major", "minor", "suggestion"
    category: str  # "logic", "security", "performance", "style", "documentation"
    message: str
    suggestion: Optional[str] = None
    confidence: float = 0.8  # 0.0-1.0


@dataclass
class CodeReviewResult:
    """Complete code review result"""
    file_path: str
    reviewed_at: datetime
    reviewer: str  # "qwen-4b", "claude-sonnet", etc.
    overall_quality: float  # 0.0-1.0
    comments: List[ReviewComment] = field(default_factory=list)
    summary: str = ""
    recommendations: List[str] = field(default_factory=list)


class LLMCodeReviewer:
    """LLM-based code reviewer"""

    def __init__(
        self,
        model: str = "qwen-4b",
        use_local: bool = True,
    ):
        self.model = model
        self.use_local = use_local

        logger.info(f"LLM Code Reviewer initialized (model={model}, local={use_local})")

    async def review_file(self, file_path: Path) -> CodeReviewResult:
        """Review a single file"""
        logger.info(f"Reviewing {file_path}...")

        # Read file content
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            logger.error(f"Failed to read {file_path}: {e}")
            return CodeReviewResult(
                file_path=str(file_path),
                reviewed_at=datetime.now(),
                reviewer=self.model,
                overall_quality=0.0,
                summary=f"Failed to read file: {e}",
            )

        # Truncate if too long (to fit in context)
        max_lines = 500
        lines = content.split("\n")
        if len(lines) > max_lines:
            content = "\n".join(lines[:max_lines])
            logger.warning(f"File truncated to {max_lines} lines")

        # Generate review prompt
        prompt = self._build_review_prompt(file_path, content)

        # Get review from LLM
        review_text = await self._query_llm(prompt)

        # Parse review
        result = self._parse_review(file_path, review_text)

        return result

    def _build_review_prompt(self, file_path: Path, content: str) -> str:
        """Build code review prompt"""
        return f"""You are a senior software engineer performing a code review.

File: {file_path.name}
Language: Python

Code:
```python
{content}
```

Please review this code and provide:

1. **Overall Quality Score** (0-10): Rate the code quality
2. **Critical Issues**: Any bugs, security vulnerabilities, or critical problems
3. **Major Issues**: Performance problems, maintainability concerns
4. **Minor Issues**: Code style, naming, minor improvements
5. **Documentation**: Missing or unclear documentation
6. **Recommendations**: Specific suggestions for improvement

Format your response as follows:

QUALITY_SCORE: X/10

CRITICAL:
- [Line N] Issue description | Suggested fix

MAJOR:
- [Line N] Issue description | Suggested fix

MINOR:
- [Line N] Issue description | Suggested fix

DOCUMENTATION:
- Missing or unclear documentation points

RECOMMENDATIONS:
- Specific actionable recommendations

SUMMARY:
Brief overall assessment

Focus on actionable, specific feedback."""

    async def _query_llm(self, prompt: str) -> str:
        """Query LLM for code review"""
        if self.use_local:
            # Use local model via switchboard or direct llama.cpp
            return await self._query_local_model(prompt)
        else:
            # Use remote model (Claude, OpenRouter, etc.)
            return await self._query_remote_model(prompt)

    async def _query_local_model(self, prompt: str) -> str:
        """Query local model"""
        try:
            # Call local llama.cpp server
            import httpx

            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    "http://localhost:8080/v1/chat/completions",
                    json={
                        "model": "qwen",
                        "messages": [
                            {
                                "role": "system",
                                "content": "You are a senior software engineer performing code reviews.",
                            },
                            {"role": "user", "content": prompt},
                        ],
                        "temperature": 0.3,  # Lower temperature for consistency
                        "max_tokens": 2000,
                    },
                )

                if response.status_code == 200:
                    data = response.json()
                    return data["choices"][0]["message"]["content"]
                else:
                    logger.error(f"Local model error: {response.status_code}")
                    return "Error: Failed to get review from local model"

        except Exception as e:
            logger.error(f"Local model query failed: {e}")
            return f"Error: {e}"

    async def _query_remote_model(self, prompt: str) -> str:
        """Query remote model (placeholder)"""
        # TODO: Implement remote model query via OpenRouter/Claude
        logger.warning("Remote model query not yet implemented")
        return "Remote model query not available"

    def _parse_review(self, file_path: Path, review_text: str) -> CodeReviewResult:
        """Parse LLM review response"""
        comments = []

        # Extract quality score
        quality_score = 7.0  # Default
        if "QUALITY_SCORE:" in review_text:
            try:
                score_line = [l for l in review_text.split("\n") if "QUALITY_SCORE:" in l][0]
                score_str = score_line.split(":")[1].strip().split("/")[0]
                quality_score = float(score_str) / 10.0
            except:
                pass

        # Parse sections
        sections = {
            "CRITICAL": "critical",
            "MAJOR": "major",
            "MINOR": "minor",
            "DOCUMENTATION": "documentation",
        }

        for section_header, severity in sections.items():
            if section_header in review_text:
                section_content = self._extract_section(review_text, section_header)
                for line in section_content.split("\n"):
                    line = line.strip()
                    if line.startswith("-"):
                        # Parse comment
                        comment = self._parse_comment_line(
                            file_path, line[1:].strip(), severity
                        )
                        if comment:
                            comments.append(comment)

        # Extract recommendations
        recommendations = []
        if "RECOMMENDATIONS:" in review_text:
            rec_content = self._extract_section(review_text, "RECOMMENDATIONS")
            for line in rec_content.split("\n"):
                line = line.strip()
                if line.startswith("-"):
                    recommendations.append(line[1:].strip())

        # Extract summary
        summary = ""
        if "SUMMARY:" in review_text:
            summary = self._extract_section(review_text, "SUMMARY").strip()

        return CodeReviewResult(
            file_path=str(file_path),
            reviewed_at=datetime.now(),
            reviewer=self.model,
            overall_quality=quality_score,
            comments=comments,
            summary=summary,
            recommendations=recommendations,
        )

    def _extract_section(self, text: str, section_name: str) -> str:
        """Extract content of a section"""
        lines = text.split("\n")
        in_section = False
        content = []

        for line in lines:
            if line.strip().startswith(section_name):
                in_section = True
                continue

            if in_section:
                # Stop at next section
                if line.strip() and line.strip()[0].isupper() and ":" in line:
                    break
                content.append(line)

        return "\n".join(content)

    def _parse_comment_line(
        self, file_path: Path, line: str, severity: str
    ) -> Optional[ReviewComment]:
        """Parse a single comment line"""
        # Format: [Line N] Issue description | Suggested fix
        try:
            if "[Line" in line:
                parts = line.split("]", 1)
                line_num_str = parts[0].replace("[Line", "").strip()
                line_number = int(line_num_str)
                rest = parts[1].strip()
            else:
                line_number = 0
                rest = line

            # Split message and suggestion
            if "|" in rest:
                message, suggestion = rest.split("|", 1)
                message = message.strip()
                suggestion = suggestion.strip()
            else:
                message = rest
                suggestion = None

            # Determine category from keywords
            message_lower = message.lower()
            if any(word in message_lower for word in ["security", "vulnerability", "inject"]):
                category = "security"
            elif any(word in message_lower for word in ["performance", "slow", "optimize"]):
                category = "performance"
            elif any(word in message_lower for word in ["bug", "error", "wrong", "incorrect"]):
                category = "logic"
            elif any(word in message_lower for word in ["document", "comment", "unclear"]):
                category = "documentation"
            else:
                category = "style"

            return ReviewComment(
                file_path=str(file_path),
                line_number=line_number,
                severity=severity,
                category=category,
                message=message,
                suggestion=suggestion,
            )

        except Exception as e:
            logger.warning(f"Failed to parse comment: {line} - {e}")
            return None

    async def review_directory(
        self,
        directory: Path,
        pattern: str = "**/*.py",
        max_files: int = 20,
    ) -> List[CodeReviewResult]:
        """Review all matching files in a directory"""
        files = list(directory.glob(pattern))[:max_files]

        logger.info(f"Reviewing {len(files)} files in {directory}...")

        results = []
        for file_path in files:
            result = await self.review_file(file_path)
            results.append(result)

        return results

    def export_results(self, results: List[CodeReviewResult], output_path: Path):
        """Export review results to JSON"""
        data = {
            "reviewed_at": datetime.now().isoformat(),
            "reviewer": self.model,
            "total_files": len(results),
            "files": [
                {
                    "file_path": r.file_path,
                    "overall_quality": r.overall_quality,
                    "comments_count": len(r.comments),
                    "summary": r.summary,
                    "recommendations": r.recommendations,
                    "comments": [
                        {
                            "line": c.line_number,
                            "severity": c.severity,
                            "category": c.category,
                            "message": c.message,
                            "suggestion": c.suggestion,
                        }
                        for c in r.comments
                    ],
                }
                for r in results
            ],
        }

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)

        logger.info(f"Exported reviews to {output_path}")


async def main():
    """Test LLM code reviewer"""
    logging.basicConfig(level=logging.INFO)

    reviewer = LLMCodeReviewer(model="qwen-4b", use_local=True)

    # Review a test file
    test_file = Path("ai-stack/self-improvement/improvement_detector.py")

    if test_file.exists():
        result = await reviewer.review_file(test_file)

        logger.info(f"\nReview Results for {test_file.name}:")
        logger.info(f"Quality Score: {result.overall_quality:.2f}/1.0")
        logger.info(f"Comments: {len(result.comments)}")

        for comment in result.comments[:5]:
            logger.info(f"\n[{comment.severity.upper()}] Line {comment.line_number}")
            logger.info(f"  {comment.message}")
            if comment.suggestion:
                logger.info(f"  Suggestion: {comment.suggestion}")

        logger.info(f"\nSummary: {result.summary}")

        # Export
        output_path = Path(".agents/reviews/code-review.json")
        reviewer.export_results([result], output_path)
        logger.info(f"\nFull report: {output_path}")
    else:
        logger.warning(f"Test file not found: {test_file}")


if __name__ == "__main__":
    asyncio.run(main())
