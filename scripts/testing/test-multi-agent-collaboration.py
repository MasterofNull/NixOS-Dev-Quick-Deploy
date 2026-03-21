#!/usr/bin/env python3
"""
Test Suite for Multi-Agent Collaboration System

Comprehensive tests for all collaboration components:
- Dynamic team formation
- Agent communication protocol
- Collaborative planning
- Quality consensus
- Collaboration patterns
- Team performance metrics
"""

import asyncio
import sys
import time
from pathlib import Path
import tempfile
import shutil

# Add lib to path
lib_path = Path(__file__).parent.parent.parent / "lib"
sys.path.insert(0, str(lib_path))

from agents import (
    DynamicTeamFormation,
    AgentCommunicationProtocol,
    CollaborativePlanning,
    QualityConsensus,
    CollaborationPatterns,
    TeamPerformanceMetrics,
    AgentProfile,
    AgentCapability,
    AgentRole,
    TaskRequirements,
    MessageType,
    MessagePriority,
    PlanningMode,
    PhaseType,
    ConsensusThreshold,
    VoteType,
    TaskCharacteristic,
    CollaborationPatternType,
    create_default_agents,
)


class TestResults:
    """Track test results."""

    def __init__(self):
        self.total = 0
        self.passed = 0
        self.failed = 0
        self.errors = []

    def record_pass(self, test_name: str):
        """Record passed test."""
        self.total += 1
        self.passed += 1
        print(f"✓ {test_name}")

    def record_fail(self, test_name: str, error: str):
        """Record failed test."""
        self.total += 1
        self.failed += 1
        self.errors.append((test_name, error))
        print(f"✗ {test_name}: {error}")

    def print_summary(self):
        """Print test summary."""
        print("\n" + "=" * 60)
        print(f"Test Results: {self.passed}/{self.total} passed")
        if self.failed > 0:
            print(f"\nFailed Tests ({self.failed}):")
            for test_name, error in self.errors:
                print(f"  - {test_name}: {error}")
        print("=" * 60)

        return self.failed == 0


# Test Dynamic Team Formation

async def test_team_formation(results: TestResults):
    """Test team formation functionality."""
    print("\n=== Testing Dynamic Team Formation ===\n")

    temp_dir = Path(tempfile.mkdtemp())
    try:
        formation = DynamicTeamFormation(state_dir=temp_dir)

        # Test 1: Register agents
        try:
            agents = create_default_agents()
            for agent in agents:
                formation.register_agent(agent)

            if len(formation.agent_profiles) == len(agents):
                results.record_pass("Register agents")
            else:
                results.record_fail("Register agents", "Agent count mismatch")
        except Exception as e:
            results.record_fail("Register agents", str(e))

        # Test 2: Form team
        try:
            requirements = TaskRequirements(
                task_id="test-task-1",
                description="Test task requiring code generation and review",
                required_capabilities=[
                    AgentCapability.CODE_GENERATION,
                    AgentCapability.CODE_REVIEW,
                ],
                complexity=3,
            )

            team = await formation.form_team(requirements)

            if len(team.members) >= 1:
                results.record_pass("Form team")
            else:
                results.record_fail("Form team", "Team is empty")
        except Exception as e:
            results.record_fail("Form team", str(e))

        # Test 3: Team optimization
        try:
            optimal_size = formation._optimize_team_size(requirements)
            if 1 <= optimal_size <= 5:
                results.record_pass("Optimize team size")
            else:
                results.record_fail("Optimize team size", f"Invalid size: {optimal_size}")
        except Exception as e:
            results.record_fail("Optimize team size", str(e))

        # Test 4: Pattern selection
        try:
            pattern = formation._select_coordination_pattern(requirements, 3)
            results.record_pass("Select coordination pattern")
        except Exception as e:
            results.record_fail("Select coordination pattern", str(e))

        # Test 5: Get metrics
        try:
            metrics = formation.get_team_metrics()
            if "total_teams" in metrics:
                results.record_pass("Get team metrics")
            else:
                results.record_fail("Get team metrics", "Missing metrics")
        except Exception as e:
            results.record_fail("Get team metrics", str(e))

    finally:
        shutil.rmtree(temp_dir)


async def test_communication(results: TestResults):
    """Test communication protocol."""
    print("\n=== Testing Agent Communication ===\n")

    temp_dir = Path(tempfile.mkdtemp())
    try:
        comm = AgentCommunicationProtocol(state_dir=temp_dir)

        # Test 1: Register agents
        try:
            comm.register_agent("agent-1")
            comm.register_agent("agent-2")
            results.record_pass("Register agents for communication")
        except Exception as e:
            results.record_fail("Register agents for communication", str(e))

        # Test 2: Send message
        try:
            msg_id = await comm.send_message(
                from_agent="agent-1",
                to_agent="agent-2",
                team_id="team-1",
                message_type=MessageType.REQUEST,
                content={"test": "data"},
                priority=MessagePriority.NORMAL,
            )

            if msg_id:
                results.record_pass("Send message")
            else:
                results.record_fail("Send message", "No message ID returned")
        except Exception as e:
            results.record_fail("Send message", str(e))

        # Test 3: Receive message
        try:
            message = await comm.receive_message("agent-2", timeout=0.5)

            if message and message.content.get("test") == "data":
                results.record_pass("Receive message")
            else:
                results.record_fail("Receive message", "Message not received correctly")
        except Exception as e:
            results.record_fail("Receive message", str(e))

        # Test 4: Shared context
        try:
            context = comm.create_shared_context("team-1")
            conflicts = await comm.update_shared_context(
                team_id="team-1",
                agent_id="agent-1",
                updates={"key1": "value1"},
                broadcast=False,
            )

            if context and context.data.get("key1") == "value1":
                results.record_pass("Shared context")
            else:
                results.record_fail("Shared context", "Context not updated")
        except Exception as e:
            results.record_fail("Shared context", str(e))

        # Test 5: Broadcast message
        try:
            msg_id = await comm.send_message(
                from_agent="agent-1",
                to_agent=None,  # Broadcast
                team_id="team-1",
                message_type=MessageType.NOTIFICATION,
                content={"broadcast": "test"},
            )

            if msg_id:
                results.record_pass("Broadcast message")
            else:
                results.record_fail("Broadcast message", "No message ID")
        except Exception as e:
            results.record_fail("Broadcast message", str(e))

        # Test 6: Communication metrics
        try:
            metrics = comm.get_communication_metrics()
            if "total_messages_sent" in metrics:
                results.record_pass("Communication metrics")
            else:
                results.record_fail("Communication metrics", "Missing metrics")
        except Exception as e:
            results.record_fail("Communication metrics", str(e))

    finally:
        shutil.rmtree(temp_dir)


async def test_planning(results: TestResults):
    """Test collaborative planning."""
    print("\n=== Testing Collaborative Planning ===\n")

    temp_dir = Path(tempfile.mkdtemp())
    try:
        planning = CollaborativePlanning(state_dir=temp_dir)

        # Test 1: Create plan
        try:
            plan_id = planning.create_plan("task-1", "team-1", PlanningMode.PARALLEL)

            if plan_id:
                results.record_pass("Create plan")
            else:
                results.record_fail("Create plan", "No plan ID returned")
        except Exception as e:
            results.record_fail("Create plan", str(e))

        # Test 2: Add contributions
        try:
            contrib1 = planning.add_contribution(
                plan_id=plan_id,
                agent_id="agent-1",
                content="Suggestion 1",
                suggested_phases=[{
                    "id": "phase-1",
                    "name": "Design",
                    "type": "design",
                    "description": "Design the system",
                }],
            )

            contrib2 = planning.add_contribution(
                plan_id=plan_id,
                agent_id="agent-2",
                content="Suggestion 2",
                suggested_phases=[{
                    "id": "phase-2",
                    "name": "Implementation",
                    "type": "implementation",
                    "description": "Implement the system",
                }],
            )

            if contrib1 and contrib2:
                results.record_pass("Add contributions")
            else:
                results.record_fail("Add contributions", "Missing contribution IDs")
        except Exception as e:
            results.record_fail("Add contributions", str(e))

        # Test 3: Synthesize plan
        try:
            agent_caps = {
                "agent-1": ["code_generation", "architecture"],
                "agent-2": ["code_generation", "testing"],
            }

            plan = await planning.synthesize_plan(plan_id, agent_caps)

            if plan and len(plan.phases) > 0:
                results.record_pass("Synthesize plan")
            else:
                results.record_fail("Synthesize plan", "Plan has no phases")
        except Exception as e:
            results.record_fail("Synthesize plan", str(e))

        # Test 4: Validate plan
        try:
            plan = await planning.validate_plan(plan_id, ["agent-1", "agent-2"])

            if plan.feasibility_score >= 0:
                results.record_pass("Validate plan")
            else:
                results.record_fail("Validate plan", "Invalid feasibility score")
        except Exception as e:
            results.record_fail("Validate plan", str(e))

        # Test 5: Finalize plan
        try:
            final_plan = planning.finalize_plan(plan_id)

            if final_plan.finalized:
                results.record_pass("Finalize plan")
            else:
                results.record_fail("Finalize plan", "Plan not finalized")
        except Exception as e:
            results.record_fail("Finalize plan", str(e))

        # Test 6: Planning metrics
        try:
            metrics = planning.get_planning_metrics()
            if "total_plans" in metrics:
                results.record_pass("Planning metrics")
            else:
                results.record_fail("Planning metrics", "Missing metrics")
        except Exception as e:
            results.record_fail("Planning metrics", str(e))

    finally:
        shutil.rmtree(temp_dir)


async def test_consensus(results: TestResults):
    """Test quality consensus."""
    print("\n=== Testing Quality Consensus ===\n")

    temp_dir = Path(tempfile.mkdtemp())
    try:
        consensus = QualityConsensus(state_dir=temp_dir)

        # Test 1: Create session
        try:
            session_id = consensus.create_session(
                artifact_id="artifact-1",
                team_id="team-1",
                threshold=ConsensusThreshold.SIMPLE_MAJORITY,
                required_reviewers=3,
            )

            if session_id:
                results.record_pass("Create consensus session")
            else:
                results.record_fail("Create consensus session", "No session ID")
        except Exception as e:
            results.record_fail("Create consensus session", str(e))

        # Test 2: Submit reviews
        try:
            review1 = consensus.submit_review(
                session_id=session_id,
                reviewer_id="agent-1",
                vote=VoteType.APPROVE,
                confidence=0.8,
            )

            review2 = consensus.submit_review(
                session_id=session_id,
                reviewer_id="agent-2",
                vote=VoteType.APPROVE,
                confidence=0.9,
            )

            review3 = consensus.submit_review(
                session_id=session_id,
                reviewer_id="agent-3",
                vote=VoteType.REJECT,
                confidence=0.7,
            )

            if review1 and review2 and review3:
                results.record_pass("Submit reviews")
            else:
                results.record_fail("Submit reviews", "Missing review IDs")
        except Exception as e:
            results.record_fail("Submit reviews", str(e))

        # Test 3: Evaluate consensus
        try:
            result = await consensus.evaluate_consensus(session_id)

            if result and result.achieved:
                results.record_pass("Evaluate consensus")
            else:
                results.record_fail("Evaluate consensus", "Consensus not achieved")
        except Exception as e:
            results.record_fail("Evaluate consensus", str(e))

        # Test 4: Analyze disagreement
        try:
            analysis = consensus.analyze_disagreement(session_id)

            if "vote_distribution" in analysis:
                results.record_pass("Analyze disagreement")
            else:
                results.record_fail("Analyze disagreement", "Missing analysis")
        except Exception as e:
            results.record_fail("Analyze disagreement", str(e))

        # Test 5: Consensus metrics
        try:
            metrics = consensus.get_consensus_metrics()
            if "total_sessions" in metrics:
                results.record_pass("Consensus metrics")
            else:
                results.record_fail("Consensus metrics", "Missing metrics")
        except Exception as e:
            results.record_fail("Consensus metrics", str(e))

    finally:
        shutil.rmtree(temp_dir)


async def test_patterns(results: TestResults):
    """Test collaboration patterns."""
    print("\n=== Testing Collaboration Patterns ===\n")

    temp_dir = Path(tempfile.mkdtemp())
    try:
        patterns = CollaborationPatterns(state_dir=temp_dir)

        # Test 1: Select pattern
        try:
            pattern = patterns.select_pattern([TaskCharacteristic.INDEPENDENT_SUBTASKS])

            if pattern == CollaborationPatternType.PARALLEL:
                results.record_pass("Select pattern")
            else:
                results.record_fail("Select pattern", f"Wrong pattern: {pattern}")
        except Exception as e:
            results.record_fail("Select pattern", str(e))

        # Test 2: Execute pattern
        try:
            async def test_executor(*args, **kwargs):
                await asyncio.sleep(0.01)
                return {"success": True, "result": "test"}

            execution = await patterns.execute_pattern(
                pattern_type=CollaborationPatternType.PARALLEL,
                task_id="task-1",
                team_id="team-1",
                agents=["agent-1", "agent-2"],
                task_data={"tasks": [{"id": "1"}, {"id": "2"}]},
                executor_callback=test_executor,
            )

            if execution.status == "success":
                results.record_pass("Execute pattern")
            else:
                results.record_fail("Execute pattern", f"Status: {execution.status}")
        except Exception as e:
            results.record_fail("Execute pattern", str(e))

        # Test 3: Recommend pattern
        try:
            pattern, confidence = patterns.recommend_pattern(
                task_characteristics=[TaskCharacteristic.HIGH_STAKES],
                available_agents=5,
            )

            if pattern and 0 <= confidence <= 1:
                results.record_pass("Recommend pattern")
            else:
                results.record_fail("Recommend pattern", "Invalid recommendation")
        except Exception as e:
            results.record_fail("Recommend pattern", str(e))

        # Test 4: Pattern metrics
        try:
            metrics = patterns.get_pattern_metrics()
            if isinstance(metrics, dict):
                results.record_pass("Pattern metrics")
            else:
                results.record_fail("Pattern metrics", "Invalid metrics")
        except Exception as e:
            results.record_fail("Pattern metrics", str(e))

    finally:
        shutil.rmtree(temp_dir)


async def test_performance_metrics(results: TestResults):
    """Test team performance metrics."""
    print("\n=== Testing Team Performance Metrics ===\n")

    temp_dir = Path(tempfile.mkdtemp())
    try:
        metrics = TeamPerformanceMetrics(state_dir=temp_dir)

        # Test 1: Record individual tasks
        try:
            metrics.record_individual_task(
                agent_id="agent-1",
                task_type="code_gen",
                duration=300,
                success=True,
                quality_score=0.8,
            )

            metrics.record_individual_task(
                agent_id="agent-1",
                task_type="code_gen",
                duration=350,
                success=True,
                quality_score=0.9,
            )

            results.record_pass("Record individual tasks")
        except Exception as e:
            results.record_fail("Record individual tasks", str(e))

        # Test 2: Record team tasks
        try:
            metrics.record_team_task(
                team_id="team-1",
                team_size=3,
                coordination_pattern="hub",
                task_type="code_gen",
                duration=400,
                communication_time=50,
                success=True,
                quality_score=0.95,
            )

            results.record_pass("Record team tasks")
        except Exception as e:
            results.record_fail("Record team tasks", str(e))

        # Test 3: Compare performance
        try:
            comparison = metrics.compare_performance("code_gen")

            if comparison and comparison.recommendation:
                results.record_pass("Compare performance")
            else:
                results.record_fail("Compare performance", "No comparison result")
        except Exception as e:
            results.record_fail("Compare performance", str(e))

        # Test 4: Analyze composition
        try:
            analysis = metrics.analyze_team_composition()

            if "by_team_size" in analysis or "error" in analysis:
                results.record_pass("Analyze composition")
            else:
                results.record_fail("Analyze composition", "Invalid analysis")
        except Exception as e:
            results.record_fail("Analyze composition", str(e))

        # Test 5: Cost-benefit analysis
        try:
            analysis = metrics.calculate_cost_benefit()

            if "roi" in analysis:
                results.record_pass("Cost-benefit analysis")
            else:
                results.record_fail("Cost-benefit analysis", "Missing ROI")
        except Exception as e:
            results.record_fail("Cost-benefit analysis", str(e))

        # Test 6: Get summary
        try:
            summary = metrics.get_summary()

            if "total_tasks" in summary:
                results.record_pass("Get metrics summary")
            else:
                results.record_fail("Get metrics summary", "Invalid summary")
        except Exception as e:
            results.record_fail("Get metrics summary", str(e))

    finally:
        shutil.rmtree(temp_dir)


async def run_all_tests():
    """Run all tests."""
    results = TestResults()

    print("=" * 60)
    print("Multi-Agent Collaboration Test Suite")
    print("=" * 60)

    await test_team_formation(results)
    await test_communication(results)
    await test_planning(results)
    await test_consensus(results)
    await test_patterns(results)
    await test_performance_metrics(results)

    success = results.print_summary()
    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(run_all_tests())
    sys.exit(exit_code)
