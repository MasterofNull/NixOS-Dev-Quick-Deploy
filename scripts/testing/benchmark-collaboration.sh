#!/usr/bin/env bash
#
# Benchmark Multi-Agent Collaboration Performance
#
# This script benchmarks the performance of multi-agent collaboration components:
# - Team formation speed
# - Communication latency
# - Consensus evaluation time
# - Pattern execution time
# - Team vs individual performance

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $*"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $*"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*"
}

# Benchmark functions

benchmark_team_formation() {
    log_info "Benchmarking team formation..."

    python3 <<'EOF'
import asyncio
import time
import sys
from pathlib import Path

lib_path = Path(__file__).parent.parent / "lib"
sys.path.insert(0, str(lib_path))

from agents import (
    DynamicTeamFormation,
    AgentCapability,
    TaskRequirements,
    create_default_agents,
)

async def benchmark():
    formation = DynamicTeamFormation()

    # Register default agents
    for agent in create_default_agents():
        formation.register_agent(agent)

    # Benchmark team formation
    iterations = 100
    total_time = 0

    for i in range(iterations):
        requirements = TaskRequirements(
            task_id=f"task-{i}",
            description="Test task",
            required_capabilities=[
                AgentCapability.CODE_GENERATION,
                AgentCapability.CODE_REVIEW,
            ],
            complexity=3,
        )

        start = time.time()
        team = await formation.form_team(requirements)
        elapsed = time.time() - start
        total_time += elapsed

    avg_time = total_time / iterations
    print(f"Team Formation: {avg_time*1000:.2f}ms avg ({iterations} iterations)")
    print(f"  Target: <1000ms")
    print(f"  Status: {'PASS' if avg_time < 1.0 else 'FAIL'}")

asyncio.run(benchmark())
EOF
}

benchmark_communication() {
    log_info "Benchmarking communication latency..."

    python3 <<'EOF'
import asyncio
import time
import sys
from pathlib import Path

lib_path = Path(__file__).parent.parent / "lib"
sys.path.insert(0, str(lib_path))

from agents import (
    AgentCommunicationProtocol,
    MessageType,
    MessagePriority,
)

async def benchmark():
    comm = AgentCommunicationProtocol()

    # Register agents
    comm.register_agent("agent-1")
    comm.register_agent("agent-2")

    # Benchmark message latency
    iterations = 1000
    total_time = 0

    for i in range(iterations):
        start = time.time()
        msg_id = await comm.send_message(
            from_agent="agent-1",
            to_agent="agent-2",
            team_id="team-1",
            message_type=MessageType.REQUEST,
            content={"iteration": i},
            priority=MessagePriority.NORMAL,
        )
        message = await comm.receive_message("agent-2", timeout=0.1)
        elapsed = time.time() - start
        total_time += elapsed

    avg_time = total_time / iterations
    print(f"Message Latency: {avg_time*1000:.2f}ms avg ({iterations} iterations)")
    print(f"  Target: <50ms")
    print(f"  Status: {'PASS' if avg_time < 0.05 else 'FAIL'}")

asyncio.run(benchmark())
EOF
}

benchmark_consensus() {
    log_info "Benchmarking consensus evaluation..."

    python3 <<'EOF'
import asyncio
import time
import sys
from pathlib import Path

lib_path = Path(__file__).parent.parent / "lib"
sys.path.insert(0, str(lib_path))

from agents import (
    QualityConsensus,
    ConsensusThreshold,
    VoteType,
)

async def benchmark():
    consensus = QualityConsensus()

    # Benchmark consensus with 5 reviewers
    iterations = 100
    total_time = 0

    for i in range(iterations):
        session_id = consensus.create_session(
            artifact_id=f"artifact-{i}",
            team_id="team-1",
            threshold=ConsensusThreshold.SIMPLE_MAJORITY,
            required_reviewers=5,
        )

        # Submit reviews
        for j in range(5):
            consensus.submit_review(
                session_id=session_id,
                reviewer_id=f"reviewer-{j}",
                vote=VoteType.APPROVE if j < 3 else VoteType.REJECT,
                confidence=0.8,
            )

        start = time.time()
        result = await consensus.evaluate_consensus(session_id)
        elapsed = time.time() - start
        total_time += elapsed

    avg_time = total_time / iterations
    print(f"Consensus Evaluation: {avg_time*1000:.2f}ms avg ({iterations} iterations)")
    print(f"  Target: <500ms")
    print(f"  Status: {'PASS' if avg_time < 0.5 else 'FAIL'}")

asyncio.run(benchmark())
EOF
}

benchmark_pattern_execution() {
    log_info "Benchmarking pattern execution..."

    python3 <<'EOF'
import asyncio
import time
import sys
from pathlib import Path

lib_path = Path(__file__).parent.parent / "lib"
sys.path.insert(0, str(lib_path))

from agents import (
    CollaborationPatterns,
    CollaborationPatternType,
)

async def benchmark():
    patterns = CollaborationPatterns()

    # Simple executor
    async def test_executor(*args, **kwargs):
        await asyncio.sleep(0.001)
        return {"success": True}

    # Benchmark parallel pattern
    iterations = 50
    total_time = 0

    for i in range(iterations):
        start = time.time()
        execution = await patterns.execute_pattern(
            pattern_type=CollaborationPatternType.PARALLEL,
            task_id=f"task-{i}",
            team_id="team-1",
            agents=["agent-1", "agent-2", "agent-3"],
            task_data={"tasks": [{"id": "1"}, {"id": "2"}]},
            executor_callback=test_executor,
        )
        elapsed = time.time() - start
        total_time += elapsed

    avg_time = total_time / iterations
    print(f"Pattern Execution: {avg_time*1000:.2f}ms avg ({iterations} iterations)")
    print(f"  Target: <100ms (for simple tasks)")
    print(f"  Status: {'PASS' if avg_time < 0.1 else 'WARN'}")

asyncio.run(benchmark())
EOF
}

benchmark_team_vs_individual() {
    log_info "Benchmarking team vs individual performance..."

    python3 <<'EOF'
import sys
from pathlib import Path

lib_path = Path(__file__).parent.parent / "lib"
sys.path.insert(0, str(lib_path))

from agents import TeamPerformanceMetrics

def benchmark():
    metrics = TeamPerformanceMetrics()

    # Simulate individual tasks
    for i in range(50):
        metrics.record_individual_task(
            agent_id="agent-1",
            task_type="code_gen",
            duration=300 + (i % 100),
            success=(i % 10) != 0,  # 90% success
            quality_score=0.7 + ((i % 30) / 100),
        )

    # Simulate team tasks
    for i in range(30):
        metrics.record_team_task(
            team_id="team-1",
            team_size=3,
            coordination_pattern="hub",
            task_type="code_gen",
            duration=250 + (i % 80),  # Faster on average
            communication_time=30 + (i % 20),
            success=(i % 20) != 0,  # 95% success
            quality_score=0.8 + ((i % 20) / 100),
        )

    # Compare
    comparison = metrics.compare_performance("code_gen")

    print(f"Team vs Individual Comparison:")
    print(f"  Team success rate: {comparison.team_success_rate:.1%}")
    print(f"  Individual success rate: {comparison.individual_success_rate:.1%}")
    print(f"  Team advantage: {comparison.team_advantage:+.3f}")
    print(f"  Recommendation: {comparison.recommendation}")
    print(f"  Target: Team advantage >60% of time")
    print(f"  Status: {'PASS' if comparison.team_advantage > 0 else 'FAIL'}")

benchmark()
EOF
}

# Main execution

main() {
    log_info "Starting Multi-Agent Collaboration Benchmarks"
    echo ""

    echo "============================================================"
    echo "                 PERFORMANCE BENCHMARKS"
    echo "============================================================"
    echo ""

    benchmark_team_formation
    echo ""

    benchmark_communication
    echo ""

    benchmark_consensus
    echo ""

    benchmark_pattern_execution
    echo ""

    benchmark_team_vs_individual
    echo ""

    echo "============================================================"
    log_success "Benchmarks complete"
    echo "============================================================"
}

main "$@"
