#!/usr/bin/env python3
"""
System Prompt Effectiveness Testing Framework

Tests the local orchestrator's ability to understand and execute prompts
across different complexity categories.
"""

import asyncio
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Optional
import sys

# Add parent paths
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "ai-stack"))

from local_orchestrator.orchestrator import LocalOrchestrator


@dataclass
class PromptTest:
    """Single prompt test case."""
    id: str
    category: str  # "simple", "synthesis", "delegation", "planning"
    prompt: str
    expected_action: str  # "local", "delegate", "plan"
    expected_tools: List[str] = field(default_factory=list)
    correctness_criteria: List[str] = field(default_factory=list)


@dataclass
class TestResult:
    """Result from a single test."""
    test_id: str
    success: bool
    correctness_score: float  # 0.0 - 5.0
    completeness_score: float  # 0.0 - 5.0
    response_time: float  # seconds
    tools_used: List[str]
    action_taken: str
    delegation_correct: Optional[bool] = None
    notes: str = ""


class PromptEffectivenessTest:
    """Test framework for system prompt effectiveness."""

    def __init__(self, system_prompt_path: Path):
        """
        Initialize test framework.

        Args:
            system_prompt_path: Path to system prompt to test
        """
        self.system_prompt_path = system_prompt_path
        self.orchestrator = None
        self.test_corpus = self._load_test_corpus()

    def _load_test_corpus(self) -> List[PromptTest]:
        """Load test corpus of prompts."""
        return [
            # Category 1: Simple Queries
            PromptTest(
                id="simple_1",
                category="simple",
                prompt="What's the current git status?",
                expected_action="local",
                expected_tools=[],
                correctness_criteria=["Shows git status", "No unnecessary delegation"],
            ),
            PromptTest(
                id="simple_2",
                category="simple",
                prompt="List available MCP tools",
                expected_action="local",
                expected_tools=["tooling_manifest"],
                correctness_criteria=["Lists MCP tools", "Uses tooling_manifest"],
            ),
            PromptTest(
                id="simple_3",
                category="simple",
                prompt="Search for 'authentication' in the codebase",
                expected_action="local",
                expected_tools=["hybrid_search"],
                correctness_criteria=["Uses hybrid_search", "Returns relevant results"],
            ),
            PromptTest(
                id="simple_4",
                category="simple",
                prompt="What workflows are available?",
                expected_action="local",
                expected_tools=["aqd_workflows_list"],
                correctness_criteria=["Lists workflows", "Uses aqd_workflows_list"],
            ),
            PromptTest(
                id="simple_5",
                category="simple",
                prompt="Check AI harness health status",
                expected_action="local",
                expected_tools=[],
                correctness_criteria=["Checks services", "Reports status"],
            ),

            # Category 2: Context Synthesis
            PromptTest(
                id="synthesis_1",
                category="synthesis",
                prompt="How does routing work in the hybrid coordinator?",
                expected_action="local",
                expected_tools=["hybrid_search", "query_aidb"],
                correctness_criteria=[
                    "Searches for routing code",
                    "Synthesizes explanation",
                    "No unnecessary delegation"
                ],
            ),
            PromptTest(
                id="synthesis_2",
                category="synthesis",
                prompt="Explain the memory system architecture",
                expected_action="local",
                expected_tools=["hybrid_search", "query_aidb"],
                correctness_criteria=[
                    "Searches architecture docs",
                    "Provides comprehensive explanation",
                ],
            ),
            PromptTest(
                id="synthesis_3",
                category="synthesis",
                prompt="What's the purpose of the hints engine?",
                expected_action="local",
                expected_tools=["hybrid_search", "get_hints"],
                correctness_criteria=[
                    "Searches hints engine code/docs",
                    "Explains purpose clearly",
                ],
            ),
            PromptTest(
                id="synthesis_4",
                category="synthesis",
                prompt="How do I add a new workflow?",
                expected_action="local",
                expected_tools=["hybrid_search", "get_hints"],
                correctness_criteria=[
                    "Searches workflow docs",
                    "Provides step-by-step guidance",
                ],
            ),
            PromptTest(
                id="synthesis_5",
                category="synthesis",
                prompt="What validation checks are required before git commit?",
                expected_action="local",
                expected_tools=["get_hints", "hybrid_search"],
                correctness_criteria=[
                    "Lists validation steps",
                    "References repo-structure-lint",
                ],
            ),

            # Category 3: Delegation Decisions
            PromptTest(
                id="delegation_1",
                category="delegation",
                prompt="Implement a new cache layer for AIDB with TTL and eviction",
                expected_action="delegate",
                expected_tools=["hybrid_search", "get_hints"],
                correctness_criteria=[
                    "Gathers context first",
                    "Correctly identifies as complex task",
                    "Delegates to Claude Sonnet",
                    "Provides clear task description",
                ],
            ),
            PromptTest(
                id="delegation_2",
                category="delegation",
                prompt="Add comprehensive logging to all HTTP API endpoints",
                expected_action="delegate",
                expected_tools=["hybrid_search"],
                correctness_criteria=[
                    "Searches for existing endpoints",
                    "Delegates for implementation",
                    "Provides context about endpoints",
                ],
            ),
            PromptTest(
                id="delegation_3",
                category="delegation",
                prompt="Refactor the search router to improve performance by 50%",
                expected_action="delegate",
                expected_tools=["hybrid_search", "get_hints"],
                correctness_criteria=[
                    "Gathers performance context",
                    "Identifies as complex refactoring",
                    "Delegates appropriately",
                ],
            ),
            PromptTest(
                id="delegation_4",
                category="delegation",
                prompt="Create comprehensive unit tests for the memory manager module",
                expected_action="delegate",
                expected_tools=["hybrid_search"],
                correctness_criteria=[
                    "Finds memory manager code",
                    "Delegates test creation",
                    "Provides code context",
                ],
            ),
            PromptTest(
                id="delegation_5",
                category="delegation",
                prompt="Implement security headers and CORS for all HTTP endpoints",
                expected_action="delegate",
                expected_tools=["hybrid_search"],
                correctness_criteria=[
                    "Gathers endpoint context",
                    "Correctly delegates security work",
                ],
            ),

            # Category 4: Planning
            PromptTest(
                id="planning_1",
                category="planning",
                prompt="Create an implementation plan for distributed caching across services",
                expected_action="plan",
                expected_tools=["workflow_plan", "hybrid_search"],
                correctness_criteria=[
                    "Uses workflow_plan tool",
                    "Gathers architecture context",
                    "Produces phased plan",
                ],
            ),
            PromptTest(
                id="planning_2",
                category="planning",
                prompt="Design a monitoring dashboard for the AI harness",
                expected_action="plan",
                expected_tools=["workflow_plan", "hybrid_search"],
                correctness_criteria=[
                    "Searches for existing metrics",
                    "Creates workflow plan",
                    "Defines phases",
                ],
            ),
            PromptTest(
                id="planning_3",
                category="planning",
                prompt="Plan the workflow for onboarding a new local model",
                expected_action="plan",
                expected_tools=["workflow_plan", "get_hints"],
                correctness_criteria=[
                    "Uses workflow_plan",
                    "Defines clear steps",
                    "Includes validation",
                ],
            ),
            PromptTest(
                id="planning_4",
                category="planning",
                prompt="Create a plan for security hardening the API layer",
                expected_action="plan",
                expected_tools=["workflow_plan", "hybrid_search"],
                correctness_criteria=[
                    "Searches for security patterns",
                    "Creates phased plan",
                    "Includes validation steps",
                ],
            ),
            PromptTest(
                id="planning_5",
                category="planning",
                prompt="Design an integration test framework for workflow execution",
                expected_action="plan",
                expected_tools=["workflow_plan", "hybrid_search"],
                correctness_criteria=[
                    "Searches existing test patterns",
                    "Creates structured plan",
                    "Defines test scenarios",
                ],
            ),
        ]

    async def run_test(self, test: PromptTest) -> TestResult:
        """Run a single prompt test."""
        print(f"  Running {test.id}: {test.prompt[:50]}...")

        start_time = time.time()

        try:
            # Process prompt through orchestrator
            response = await self.orchestrator.process(test.prompt)

            response_time = time.time() - start_time

            # Evaluate response
            correctness = self._evaluate_correctness(test, response)
            completeness = self._evaluate_completeness(test, response)
            delegation_correct = self._evaluate_delegation(test, response)

            success = correctness >= 3.0 and completeness >= 3.0

            return TestResult(
                test_id=test.id,
                success=success,
                correctness_score=correctness,
                completeness_score=completeness,
                response_time=response_time,
                tools_used=list(response.context_gathered.keys()),
                action_taken=response.action,
                delegation_correct=delegation_correct,
                notes=f"Action: {response.action}, Backend: {response.backend_used}",
            )

        except Exception as e:
            return TestResult(
                test_id=test.id,
                success=False,
                correctness_score=0.0,
                completeness_score=0.0,
                response_time=time.time() - start_time,
                tools_used=[],
                action_taken="error",
                notes=f"Error: {str(e)}",
            )

    def _evaluate_correctness(self, test: PromptTest, response: Any) -> float:
        """Evaluate correctness (0-5 scale)."""
        score = 0.0

        # Check if action matches expected
        if response.action == test.expected_action:
            score += 2.0

        # Check if expected tools were used (approximately)
        if test.expected_tools:
            tools_used = set(response.context_gathered.keys())
            expected = set(test.expected_tools)
            overlap = len(tools_used & expected)
            score += (overlap / len(expected)) * 2.0

        # Check response content quality (basic)
        if hasattr(response, 'content') and response.content:
            if len(response.content) > 50:  # Non-trivial response
                score += 1.0

        return min(score, 5.0)

    def _evaluate_completeness(self, test: PromptTest, response: Any) -> float:
        """Evaluate completeness (0-5 scale)."""
        score = 0.0

        # Has response content
        if hasattr(response, 'content') and response.content:
            score += 2.0

        # Used tools for context gathering
        if response.context_gathered:
            score += 2.0

        # Response is substantial
        if hasattr(response, 'content') and len(response.content) > 100:
            score += 1.0

        return min(score, 5.0)

    def _evaluate_delegation(self, test: PromptTest, response: Any) -> Optional[bool]:
        """Evaluate if delegation decision was correct."""
        if test.expected_action not in ["delegate", "local"]:
            return None

        expected_delegate = (test.expected_action == "delegate")
        actual_delegate = (response.action == "delegate" or response.backend_used != "LOCAL")

        return expected_delegate == actual_delegate

    async def run_all_tests(self) -> Dict[str, Any]:
        """Run all tests in the corpus."""
        print(f"\n=== Testing System Prompt: {self.system_prompt_path.name} ===\n")

        # Initialize orchestrator with specified system prompt
        # TODO: Implement system prompt override in orchestrator
        self.orchestrator = LocalOrchestrator()

        results = []
        for test in self.test_corpus:
            result = await self.run_test(test)
            results.append(result)
            time.sleep(0.5)  # Rate limiting

        # Analyze results
        return self._analyze_results(results)

    def _analyze_results(self, results: List[TestResult]) -> Dict[str, Any]:
        """Analyze test results and produce summary."""
        total = len(results)
        successful = sum(1 for r in results if r.success)
        success_rate = (successful / total) * 100 if total > 0 else 0

        # Category breakdown
        categories = {}
        for test in self.test_corpus:
            cat = test.category
            if cat not in categories:
                categories[cat] = {"total": 0, "successful": 0}
            categories[cat]["total"] += 1

        for result in results:
            test = next(t for t in self.test_corpus if t.id == result.test_id)
            if result.success:
                categories[test.category]["successful"] += 1

        # Calculate category success rates
        for cat in categories:
            total = categories[cat]["total"]
            successful = categories[cat]["successful"]
            categories[cat]["success_rate"] = (successful / total) * 100 if total > 0 else 0

        # Scores
        avg_correctness = sum(r.correctness_score for r in results) / total if total > 0 else 0
        avg_completeness = sum(r.completeness_score for r in results) / total if total > 0 else 0
        avg_response_time = sum(r.response_time for r in results) / total if total > 0 else 0

        # Delegation accuracy
        delegation_results = [r for r in results if r.delegation_correct is not None]
        delegation_accuracy = (
            (sum(1 for r in delegation_results if r.delegation_correct) / len(delegation_results)) * 100
            if delegation_results else None
        )

        summary = {
            "system_prompt": str(self.system_prompt_path),
            "total_tests": total,
            "successful": successful,
            "failed": total - successful,
            "success_rate": round(success_rate, 1),
            "avg_correctness": round(avg_correctness, 2),
            "avg_completeness": round(avg_completeness, 2),
            "avg_response_time": round(avg_response_time, 2),
            "delegation_accuracy": round(delegation_accuracy, 1) if delegation_accuracy else None,
            "category_breakdown": {
                cat: {
                    "total": data["total"],
                    "successful": data["successful"],
                    "success_rate": round(data["success_rate"], 1)
                }
                for cat, data in categories.items()
            },
            "individual_results": [
                {
                    "test_id": r.test_id,
                    "success": r.success,
                    "correctness": round(r.correctness_score, 2),
                    "completeness": round(r.completeness_score, 2),
                    "response_time": round(r.response_time, 2),
                    "delegation_correct": r.delegation_correct,
                    "notes": r.notes,
                }
                for r in results
            ],
        }

        return summary

    def print_summary(self, summary: Dict[str, Any]):
        """Print human-readable summary."""
        print(f"\n{'='*70}")
        print(f"SYSTEM PROMPT EFFECTIVENESS TEST RESULTS")
        print(f"{'='*70}\n")

        print(f"System Prompt: {summary['system_prompt']}")
        print(f"Total Tests: {summary['total_tests']}")
        print(f"Successful: {summary['successful']} ({summary['success_rate']}%)")
        print(f"Failed: {summary['failed']}\n")

        print(f"Average Correctness: {summary['avg_correctness']}/5.0")
        print(f"Average Completeness: {summary['avg_completeness']}/5.0")
        print(f"Average Response Time: {summary['avg_response_time']}s")

        if summary["delegation_accuracy"]:
            print(f"Delegation Accuracy: {summary['delegation_accuracy']}%")

        print(f"\nCategory Breakdown:")
        for cat, data in summary["category_breakdown"].items():
            print(f"  {cat:12s}: {data['successful']}/{data['total']} ({data['success_rate']}%)")

        print(f"\n{'='*70}\n")

    def save_results(self, summary: Dict[str, Any], output_path: Path):
        """Save results to JSON file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(summary, f, indent=2)
        print(f"Results saved to: {output_path}")


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Test system prompt effectiveness")
    parser.add_argument(
        "--prompt-v1",
        type=Path,
        default=Path("ai-stack/local-orchestrator/system-prompt.md"),
        help="Path to v1 system prompt",
    )
    parser.add_argument(
        "--prompt-v2",
        type=Path,
        default=Path("ai-stack/local-orchestrator/system-prompt-v2-optimized.md"),
        help="Path to v2 optimized system prompt",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("test-data/prompt-effectiveness"),
        help="Output directory for results",
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="Run both v1 and v2 and compare results",
    )

    args = parser.parse_args()

    if args.compare:
        # Test v1
        print("\n" + "="*70)
        print("TESTING v1 (Original)")
        print("="*70)
        tester_v1 = PromptEffectivenessTest(args.prompt_v1)
        results_v1 = await tester_v1.run_all_tests()
        tester_v1.print_summary(results_v1)
        tester_v1.save_results(results_v1, args.output_dir / "v1-results.json")

        # Test v2
        print("\n" + "="*70)
        print("TESTING v2 (Optimized)")
        print("="*70)
        tester_v2 = PromptEffectivenessTest(args.prompt_v2)
        results_v2 = await tester_v2.run_all_tests()
        tester_v2.print_summary(results_v2)
        tester_v2.save_results(results_v2, args.output_dir / "v2-results.json")

        # Comparison
        print("\n" + "="*70)
        print("COMPARISON: v1 vs v2")
        print("="*70 + "\n")

        print(f"Success Rate:      v1: {results_v1['success_rate']}%  v2: {results_v2['success_rate']}%  "
              f"Delta: {results_v2['success_rate'] - results_v1['success_rate']:+.1f}%")
        print(f"Correctness:       v1: {results_v1['avg_correctness']}/5.0  v2: {results_v2['avg_correctness']}/5.0  "
              f"Delta: {results_v2['avg_correctness'] - results_v1['avg_correctness']:+.2f}")
        print(f"Completeness:      v1: {results_v1['avg_completeness']}/5.0  v2: {results_v2['avg_completeness']}/5.0  "
              f"Delta: {results_v2['avg_completeness'] - results_v1['avg_completeness']:+.2f}")
        print(f"Response Time:     v1: {results_v1['avg_response_time']}s  v2: {results_v2['avg_response_time']}s  "
              f"Delta: {results_v2['avg_response_time'] - results_v1['avg_response_time']:+.2f}s")

        if results_v1["delegation_accuracy"] and results_v2["delegation_accuracy"]:
            print(f"Delegation Acc:    v1: {results_v1['delegation_accuracy']}%  "
                  f"v2: {results_v2['delegation_accuracy']}%  "
                  f"Delta: {results_v2['delegation_accuracy'] - results_v1['delegation_accuracy']:+.1f}%")

        print()

    else:
        # Test single prompt
        prompt_path = args.prompt_v2 if args.prompt_v2.exists() else args.prompt_v1
        tester = PromptEffectivenessTest(prompt_path)
        results = await tester.run_all_tests()
        tester.print_summary(results)
        tester.save_results(results, args.output_dir / "results.json")


if __name__ == "__main__":
    asyncio.run(main())
