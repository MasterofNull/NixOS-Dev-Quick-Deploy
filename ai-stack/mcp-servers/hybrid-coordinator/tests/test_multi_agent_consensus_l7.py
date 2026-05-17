import asyncio
import pytest
import numpy as np
from unittest.mock import AsyncMock, MagicMock
from consensus_arbiter import ConsensusArbiter

def test_consensus_best_of_n():
    """L7: Ensure Arbiter selects the highest confidence candidate."""
    arb = ConsensusArbiter()
    
    candidates = [
        {
            "response": "Answer A",
            "intent_classification": {"confidence": 0.5},
            "quality_score": 0.4
        },
        {
            "response": "Answer B",
            "intent_classification": {"confidence": 0.9},
            "quality_score": 0.8
        }
    ]
    
    async def run():
        result = await arb.resolve(candidates, strategy="best_of_n")
        assert result["response"] == "Answer B"
        assert result["consensus_score"] > 0.8
        
    asyncio.run(run())

def test_consensus_majority_vote():
    """L7: Ensure Arbiter selects semantically central candidate."""
    # Mock embedding function using distinct directions
    async def mock_embed(text):
        # Consensus group in direction [1, 0, 0, ...]
        if "consensus" in text:
            v = np.zeros(384)
            v[0] = 1.0
            return v.tolist()
        # Outlier in direction [0, 1, 0, ...]
        if "outlier" in text:
            v = np.zeros(384)
            v[1] = 1.0
            return v.tolist()
        return np.zeros(384).tolist()

    arb = ConsensusArbiter(embed_fn=mock_embed)
    
    candidates = [
        {"response": "consensus solution 1"},
        {"response": "consensus solution 2"},
        {"response": "totally outlier answer"}
    ]
    
    async def run():
        result = await arb.resolve(candidates, strategy="majority_vote")
        # Centroid will be in direction [2, 1, 0], which is closer to [1,0] than [0,1]
        assert "consensus" in result["response"]
        assert result["consensus_strategy"] == "majority_vote"
        
    asyncio.run(run())
