import asyncio
import pytest
import numpy as np
from unittest.mock import AsyncMock, MagicMock
from memory_broker import MemoryBroker
from intent_classifier import IntentClassifier

def test_l5_memory_broker_contradiction():
    """L5: Ensure contradiction detection blocks conflicting facts."""
    async def run():
        calls = []
        
        async def _store(**kwargs):
            calls.append(kwargs)
            return {"status": "stored", "memory_id": "mem-1"}
            
        async def _recall(query, **kwargs):
            # Return a fact that contradicts "Postgres is down"
            return {"results": [{"content": "Postgres is up and healthy", "score": 0.9, "id": "mem-0"}]}

        from memory_superseder import MemorySuperseder
        broker = MemoryBroker(_store, _recall, superseder=MemorySuperseder())

        # Try to write a contradicting fact with supersession disabled
        result = await broker.write("semantic", "Postgres is down", check_contradictions=True, supersede=False)

        assert result["status"] == "contradiction_blocked"

        assert "contradicts existing memory" in result["reason"]
        assert len(calls) == 0 # Should not have reached store_fn
    
    asyncio.run(run())

def test_l5_memory_temporal_filtering():
    """L5: Ensure expired memories are filtered out."""
    async def run():
        async def _store(**kwargs): return {}
        
        async def _recall(query, **kwargs):
            return {"results": [
                {
                    "content": "Old fact", 
                    "metadata": {"valid_until": "2020-01-01T00:00:00Z"},
                    "score": 0.9
                },
                {
                    "content": "Fresh fact",
                    "metadata": {"valid_until": "2099-01-01T00:00:00Z"},
                    "score": 0.9
                }
            ]}

        from memory_superseder import MemorySuperseder
        broker = MemoryBroker(_store, _recall, superseder=MemorySuperseder())
        results = await broker.read("semantic", "any query", include_expired=False)
        
        assert len(results) == 1
        assert results[0]["content"] == "Fresh fact"
    
    asyncio.run(run())

def test_l5_memory_supersession():
    """L5: Ensure newer facts supersede older contradicting ones."""
    async def run():
        # Stateful mock store
        memory_store = []
        
        async def _store(**kwargs):
            # Simulate ID generation
            new_id = f"mem-{len(memory_store)}"
            kwargs["memory_id"] = new_id
            memory_store.append(kwargs)
            return {"status": "stored", "memory_id": new_id}
            
        async def _recall(query, **kwargs):
            # Return all stored items (simplified mock)
            return {"results": [
                {
                    "id": m["memory_id"],
                    "content": m["content"],
                    "metadata": m["metadata"],
                    "score": 1.0
                } for m in memory_store
            ]}

        from memory_superseder import MemorySuperseder
        broker = MemoryBroker(_store, _recall, superseder=MemorySuperseder())
        
        # 1. Write initial fact
        await broker.write("semantic", "System version is 1.0", check_contradictions=False)
        
        # 2. Write contradicting fact with supersession enabled (default)
        # Note: "1.0" and "2.0" aren't antonyms, so we need to use actual antonyms for the mock check_contradiction
        await broker.write("semantic", "The database is up", check_contradictions=False)
        await broker.write("semantic", "The database is down", supersede=True)
        
        # 3. Verify standard read only shows the newest "down" fact
        results = await broker.read("semantic", "database status")
        contents = [r["content"] for r in results]
        assert "The database is down" in contents
        assert "The database is up" not in contents # Should be filtered out
        
        # 4. Verify include_superseded shows both
        results_all = await broker.read("semantic", "database status", include_superseded=True)
        assert len(results_all) >= 2
    
    asyncio.run(run())

def test_l6_homeostasis_remediation():
    """L6: Ensure HomeostasisManager triggers remediation on high drift."""
    async def run():
        from homeostasis_manager import HomeostasisManager
        hm = HomeostasisManager()
        
        # Simulate a result with HIGH drift (0.6 > 0.4)
        mock_result = {
            "intent_classification": {
                "intent": "planning",
                "drift": {"drift_score": 0.6, "is_stable": False}
            },
            "response": "confused reasoning loop"
        }
        
        # Evaluate stability
        eval_res = await hm.evaluate_stability(mock_result, session_id="test-session")
        
        assert eval_res["status"] == "remediating"
        assert eval_res["remediation"]["action"] == "profile_elevation"
        assert eval_res["remediation"]["target_profile"] == "strong-reasoning"
        
        # Verify event was recorded
        events = hm.get_recent_events()
        assert len(events) == 1
        assert events[0]["score"] == 0.6
        
    asyncio.run(run())
    """L6: Ensure RAG dynamically searches multiple projects based on intent."""
    async def run():
        # Mock AIDB client
        mock_client = AsyncMock()
        
        # Simulate results from different projects
        def _mock_search_side_effect(path, json, **kwargs):
            project = json.get("project")
            if project == "error-solutions":
                return MagicMock(status_code=200, json=lambda: {"hits": [{"content": "Solution A", "score": 0.9, "project": "error-solutions"}]})
            if project == "semantic":
                return MagicMock(status_code=200, json=lambda: {"hits": [{"content": "General B", "score": 0.7, "project": "semantic"}]})
            return MagicMock(status_code=200, json=lambda: {"hits": []})

        mock_client.post.side_effect = _mock_search_side_effect
        
        from rag_augmentor import RagAugmentor
        aug = RagAugmentor(aidb_client=mock_client)
        
        # Test troubleshooting intent (should search both error-solutions and semantic)
        # Note: In the real server, the map lookup happens in http_server.py
        # Here we test the RagAugmentor's ability to handle the multi-project string
        result = await aug.augment(
            query="crashing service", 
            intent="troubleshooting", 
            rag_project="error-solutions,semantic"
        )
        
        assert result["augmented"] is True
        assert "Source: error-solutions" in result["context_text"]
        assert "Source: semantic" in result["context_text"]
        assert result["hits"] >= 2
        
        # Verify both projects were searched
        called_projects = [call.kwargs["json"]["project"] for call in mock_client.post.call_args_list]
        assert "error-solutions" in called_projects
        assert "semantic" in called_projects
    
    asyncio.run(run())

def test_l6_intent_classifier_semantic_boost():
    """L6: Ensure semantic prototyping boosts intent confidence."""
    async def run():
        clf = IntentClassifier()
        
        # Mock embedding fetch to return a high similarity for "planning"
        # Using a list that numpy can convert to a vector
        vector = [0.1] * 384
        clf._get_embedding = AsyncMock(return_value=np.array(vector))
        clf._prototype_embeddings = {"planning": [np.array(vector)]}
        
        # Use a query that has NO keywords from the signals map to ensure low baseline
        query = "totally unique query without standard words"
        
        # 1. Test keyword fallback (synchronous)
        kw_result = clf.classify(query)
        
        # 2. Test semantic boost (async)
        semantic_scores = await clf.classify_semantic(query)
        assert "planning" in semantic_scores
        assert semantic_scores["planning"] > 0.9 
        
        # Verify lift
        cognitive_lift = semantic_scores["planning"] - kw_result["confidence"]
        assert cognitive_lift > 0
    
    asyncio.run(run())
