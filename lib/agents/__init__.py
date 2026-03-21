#!/usr/bin/env python3
"""
AI Agents Module

This package provides comprehensive agent infrastructure including:

Phase 4.2: AI Learning Integration
- Query routing to appropriate agents
- Interaction storage in vector DB
- Pattern extraction from interactions
- Learning loop hint generation
- Continuous improvement tracking

Phase 4: Multi-Agent Collaboration
- Dynamic team formation with capability matching
- Agent communication protocol
- Collaborative planning
- Quality consensus with weighted voting
- Collaboration patterns (parallel, sequential, consensus, expert override)
- Team performance metrics

Components:
  - interaction_storage: Persist interactions with embeddings
  - pattern_extractor: Extract patterns from interaction history
  - learning_loop: Generate hints and detect gaps
  - dynamic_team_formation: Form optimal agent teams
  - agent_communication_protocol: Message passing and shared context
  - collaborative_planning: Multi-agent planning
  - quality_consensus: Weighted voting and consensus
  - collaboration_patterns: Pattern orchestration
  - team_performance_metrics: Performance tracking
"""

__version__ = "4.4.0"
__author__ = "AI Harness Team"

# Import core classes for convenience
try:
    from .interaction_storage import (
        Interaction,
        InteractionStatus,
        InteractionStorageSystem,
    )
    from .pattern_extractor import (
        Pattern,
        PatternType,
        PatternExtractor,
    )
    from .learning_loop import (
        Hint,
        HintType,
        GapDetection,
        LearningLoopEngine,
    )
    from .dynamic_team_formation import (
        AgentRole,
        CoordinationPattern,
        AgentCapability,
        AgentProfile,
        TaskRequirements,
        Team,
        DynamicTeamFormation,
        create_default_agents,
    )
    from .agent_communication_protocol import (
        MessageType,
        MessagePriority,
        Message,
        SharedContext,
        AgentCommunicationProtocol,
    )
    from .collaborative_planning import (
        PlanningMode,
        PhaseType,
        PlanContribution,
        PlanPhase,
        CollaborativePlan,
        CollaborativePlanning,
    )
    from .quality_consensus import (
        ConsensusThreshold,
        VoteType,
        Review,
        ConsensusResult,
        QualityConsensus,
    )
    from .collaboration_patterns import (
        PatternType as CollaborationPatternType,
        TaskCharacteristic,
        PatternConfig,
        PatternExecution,
        CollaborationPatterns,
    )
    from .team_performance_metrics import (
        IndividualPerformance,
        TeamPerformance,
        ComparisonResult,
        TeamPerformanceMetrics,
    )
except ImportError as e:
    # Allow module to be imported even if some dependencies are missing
    pass

__all__ = [
    # Phase 4.2 exports
    "Interaction",
    "InteractionStatus",
    "InteractionStorageSystem",
    "Pattern",
    "PatternType",
    "PatternExtractor",
    "Hint",
    "HintType",
    "GapDetection",
    "LearningLoopEngine",
    # Phase 4 exports
    "AgentRole",
    "CoordinationPattern",
    "AgentCapability",
    "AgentProfile",
    "TaskRequirements",
    "Team",
    "DynamicTeamFormation",
    "create_default_agents",
    "MessageType",
    "MessagePriority",
    "Message",
    "SharedContext",
    "AgentCommunicationProtocol",
    "PlanningMode",
    "PhaseType",
    "PlanContribution",
    "PlanPhase",
    "CollaborativePlan",
    "CollaborativePlanning",
    "ConsensusThreshold",
    "VoteType",
    "Review",
    "ConsensusResult",
    "QualityConsensus",
    "CollaborationPatternType",
    "TaskCharacteristic",
    "PatternConfig",
    "PatternExecution",
    "CollaborationPatterns",
    "IndividualPerformance",
    "TeamPerformance",
    "ComparisonResult",
    "TeamPerformanceMetrics",
]
