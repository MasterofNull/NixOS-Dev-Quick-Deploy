#!/usr/bin/env python3
"""
Phase 4.2: AI Learning Integration Module

This package provides the complete learning loop infrastructure for Phase 4.2:
- Query routing to appropriate agents
- Interaction storage in vector DB
- Pattern extraction from interactions
- Learning loop hint generation
- Continuous improvement tracking

Components:
  - interaction_storage: Persist interactions with embeddings
  - pattern_extractor: Extract patterns from interaction history
  - learning_loop: Generate hints and detect gaps
  - (improvement_tracker.sh for bash-based metrics)
  - (query_router.sh for bash-based query routing)
"""

__version__ = "4.2.0"
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
except ImportError as e:
    # Allow module to be imported even if some dependencies are missing
    pass

__all__ = [
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
]
