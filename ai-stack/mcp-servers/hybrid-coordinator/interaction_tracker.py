"""
Interaction tracking, feedback recording, pattern extraction, and training-data archive
for the hybrid-coordinator.

Extracted from server.py (Phase 6.1 decomposition).

Usage:
    import interaction_tracker
    interaction_tracker.init(
        qdrant_client=qdrant_client,
        postgres_client=postgres_client,
        llama_cpp_client=llama_cpp_client,
        embed_fn=embed_text,
        store_memory_fn=store_agent_memory,
        record_telemetry_fn=record_telemetry_event,
        performance_window=performance_window,
        collections=COLLECTIONS,
    )
    interaction_id = await interaction_tracker.track_interaction(...)
"""

import json
import logging
import os
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

from config import Config, performance_window as _default_perf_window
from qdrant_client.models import FieldCondition, Filter, MatchValue, PointStruct, Range

logger = logging.getLogger("hybrid-coordinator")

# ---------------------------------------------------------------------------
# Module-level state — populated by init()
# ---------------------------------------------------------------------------
_qdrant: Optional[Any] = None
_postgres: Optional[Any] = None
_llama_cpp: Optional[Any] = None
_embed: Optional[Callable] = None
_store_memory: Optional[Callable] = None
_record_telemetry: Optional[Callable] = None
_perf_window: Any = None
_collections: Dict[str, Any] = {}


def init(
    *,
    qdrant_client: Any,
    postgres_client: Optional[Any],
    llama_cpp_client: Any,
    embed_fn: Callable,
    store_memory_fn: Callable,
    record_telemetry_fn: Callable,
    performance_window: Any,
    collections: Dict[str, Any],
) -> None:
    """Inject runtime dependencies.  Call once from server.py initialize_server()."""
    global _qdrant, _postgres, _llama_cpp, _embed, _store_memory, _record_telemetry, _perf_window, _collections
    _qdrant = qdrant_client
    _postgres = postgres_client
    _llama_cpp = llama_cpp_client
    _embed = embed_fn
    _store_memory = store_memory_fn
    _record_telemetry = record_telemetry_fn
    _perf_window = performance_window
    _collections = collections


# ---------------------------------------------------------------------------
# Value Scoring
# ---------------------------------------------------------------------------

def compute_value_score(interaction: Dict[str, Any]) -> float:
    """Score interaction value (0-1) based on multiple factors."""
    score = 0.0
    if interaction.get("outcome") == "success":
        score += 0.4
    elif interaction.get("outcome") == "partial":
        score += 0.2
    user_feedback = interaction.get("user_feedback", 0)
    if user_feedback == 1:
        score += 0.2
    elif user_feedback == 0:
        score += 0.1
    reusability = estimate_reusability(interaction.get("query", ""))
    score += 0.2 * reusability
    complexity = estimate_complexity(interaction.get("response", ""))
    score += 0.1 * complexity
    score += 0.1 * 0.5  # novelty — simplified
    return min(score, 1.0)


def estimate_reusability(query: str) -> float:
    """Estimate how likely this query pattern will recur."""
    reusable_keywords = ["how to", "best practice", "configure", "setup", "install"]
    keyword_count = sum(1 for kw in reusable_keywords if kw.lower() in query.lower())
    return min(keyword_count * 0.25, 1.0)


def estimate_complexity(response: str) -> float:
    """Estimate response complexity."""
    steps = response.count("1.") + response.count("2.") + response.count("3.")
    code_blocks = response.count("```")
    length_score = min(len(response) / 2000, 1.0)
    return min((steps * 0.1 + code_blocks * 0.15 + length_score * 0.5), 1.0)


# ---------------------------------------------------------------------------
# Simple feedback
# ---------------------------------------------------------------------------

async def record_simple_feedback(
    interaction_id: str,
    rating: int,
    note: str = "",
    query: str = "",
) -> str:
    """Record a simple +1/-1 rating for an interaction to learning_feedback + PerformanceWindow."""
    feedback_id = str(uuid4())
    if _postgres is not None:
        try:
            await _postgres.execute(
                """
                INSERT INTO learning_feedback (
                    feedback_id, interaction_id, query,
                    correction, rating, source
                ) VALUES (%s, %s, %s, %s, %s, %s)
                """,
                feedback_id,
                interaction_id,
                query[:500] if query else "",
                note[:1000] if note else "",
                rating,
                "user-rating",
            )
        except Exception as exc:
            logger.warning("feedback_postgres_failed error=%s", exc)
    pw = _perf_window or _default_perf_window
    await pw.record("general", success=(rating > 0))
    logger.info("simple_feedback_recorded interaction_id=%s rating=%d", interaction_id, rating)
    return feedback_id


async def _record_query_gap(
    query_hash: str,
    query_text: str,
    score: float,
    collection: str = "unknown",
) -> None:
    """Phase 3.2.1 — Insert a low-confidence query into the query_gaps table."""
    if _postgres is None:
        return
    try:
        await _postgres.execute(
            """
            INSERT INTO query_gaps (query_hash, query_text, score, collection)
            VALUES (%s, %s, %s, %s)
            """,
            query_hash, query_text, score, collection,
        )
        logger.info("query_gap_recorded score=%.3f collection=%s", score, collection)
    except Exception as exc:
        logger.debug("query_gap_insert_failed error=%s", exc)


async def get_feedback_variant_stats(tag: str, days: Optional[int] = None) -> Dict[str, Any]:
    """Summarize feedback ratings for a tag (e.g., variant:model-a)."""
    if _postgres is None:
        raise RuntimeError("Postgres client not configured")
    query = """
        SELECT
            COUNT(*) AS total,
            COUNT(rating) AS rated,
            AVG(rating)::float AS avg_rating
        FROM learning_feedback
        WHERE tags ? %s
    """
    params: List[Any] = [tag]
    if days and days > 0:
        query += " AND created_at >= NOW() - (%s || ' days')::interval"
        params.append(str(days))
    rows = await _postgres.fetch_all(query, *params)
    if not rows:
        return {"tag": tag, "total": 0, "rated": 0, "avg_rating": None}
    row = rows[0]
    return {
        "tag": tag,
        "total": int(row.get("total", 0) or 0),
        "rated": int(row.get("rated", 0) or 0),
        "avg_rating": row.get("avg_rating"),
    }


# ---------------------------------------------------------------------------
# Interaction Tracking
# ---------------------------------------------------------------------------

async def track_interaction(
    query: str,
    response: str,
    agent_type: str,
    model_used: str,
    context_ids: List[str],
    outcome: str = "unknown",
    user_feedback: int = 0,
    tokens_used: int = 0,
    latency_ms: int = 0,
) -> str:
    """Store interaction in Qdrant for learning."""
    interaction_id = str(uuid4())
    timestamp = int(datetime.now().timestamp())
    interaction = {
        "query": query,
        "response": response,
        "agent_type": agent_type,
        "model_used": model_used,
        "context_provided": context_ids,
        "outcome": outcome,
        "user_feedback": user_feedback,
        "tokens_used": tokens_used,
        "latency_ms": latency_ms,
        "timestamp": timestamp,
        "value_score": 0.0,
    }
    query_embedding = await _embed(query)
    try:
        _qdrant.upsert(
            collection_name="interaction-history",
            points=[PointStruct(id=interaction_id, vector=query_embedding, payload=interaction)],
        )
        if Config.AI_MEMORY_ENABLED and _store_memory is not None:
            await _store_memory(
                "episodic",
                summary=f"{agent_type} interaction: {query[:120]}",
                content=response[:600],
                metadata={
                    "query": query,
                    "response": response[:2000],
                    "outcome": outcome,
                    "tags": [f"model:{model_used}", f"agent:{agent_type}"],
                },
            )
        logger.info("Tracked interaction: %s", interaction_id)
        if _record_telemetry is not None:
            _record_telemetry(
                "interaction_tracked",
                {
                    "interaction_id": interaction_id,
                    "agent_type": agent_type,
                    "model_used": model_used,
                    "tokens_used": tokens_used,
                    "latency_ms": latency_ms,
                    "context_count": len(context_ids),
                },
            )
        return interaction_id
    except Exception as exc:
        logger.error("Error tracking interaction: %s", exc)
        return ""


async def update_interaction_outcome(
    interaction_id: str, outcome: str, user_feedback: int = 0
) -> None:
    """Update interaction with outcome and compute value score."""
    try:
        result = _qdrant.retrieve(collection_name="interaction-history", ids=[interaction_id])
        if not result:
            logger.error("Interaction not found: %s", interaction_id)
            return
        interaction = result[0].payload
        interaction["outcome"] = outcome
        interaction["user_feedback"] = user_feedback
        value_score = compute_value_score(interaction)
        interaction["value_score"] = value_score
        _qdrant.set_payload(
            collection_name="interaction-history",
            payload=interaction,
            points=[interaction_id],
        )
        logger.info("Updated interaction %s: outcome=%s, value=%.2f", interaction_id, outcome, value_score)
        if value_score >= Config.HIGH_VALUE_THRESHOLD and Config.PATTERN_EXTRACTION_ENABLED:
            await extract_patterns(interaction)
            if Config.AI_MEMORY_ENABLED and outcome == "success" and _store_memory is not None:
                await _store_memory(
                    "procedural",
                    summary=f"Successful procedure: {interaction.get('query', '')[:120]}",
                    content=interaction.get("response", "")[:1500],
                    metadata={
                        "trigger": interaction.get("query", ""),
                        "procedure": interaction.get("response", "")[:2000],
                        "outcome": outcome,
                        "value_score": value_score,
                    },
                )
        if interaction.get("context_provided"):
            await update_context_metrics(interaction["context_provided"], outcome == "success")
    except Exception as exc:
        logger.error("Error updating interaction outcome: %s", exc)


async def update_context_metrics(context_ids: List[str], success: bool) -> None:
    """Update success rates and access counts for context items."""
    collections_to_update = [
        "codebase-context", "skills-patterns", "error-solutions", "best-practices",
    ]
    for collection_name in collections_to_update:
        for context_id in context_ids:
            try:
                result = _qdrant.retrieve(collection_name=collection_name, ids=[context_id])
                if result:
                    payload = result[0].payload
                    payload["access_count"] = payload.get("access_count", 0) + 1
                    payload["last_accessed"] = int(datetime.now().timestamp())
                    if "success_rate" in payload:
                        current_rate = payload.get("success_rate", 0.5)
                        payload["success_rate"] = current_rate * 0.9 + (1.0 if success else 0.0) * 0.1
                    _qdrant.set_payload(
                        collection_name=collection_name,
                        payload=payload,
                        points=[context_id],
                    )
            except Exception as exc:
                logger.warning("Error updating context %s in %s: %s", context_id, collection_name, exc)


# ---------------------------------------------------------------------------
# Pattern Extraction
# ---------------------------------------------------------------------------

async def extract_patterns(interaction: Dict[str, Any]) -> None:
    """Extract reusable patterns from successful interactions using local LLM."""
    if _llama_cpp is None:
        return
    prompt = f"""Analyze this successful interaction and extract reusable patterns:

Query: {interaction.get('query', '')}
Response: {interaction.get('response', '')[:500]}...

Extract:
1. What problem was solved?
2. What approach was used?
3. What skills/knowledge were applied?
4. What can be generalized for future use?

Return a JSON object with these fields:
{{
    "problem_type": "brief description",
    "solution_approach": "general approach used",
    "skills_used": ["skill1", "skill2"],
    "generalizable_pattern": "reusable pattern description"
}}

JSON:"""
    try:
        response = await _llama_cpp.post(
            "/chat/completions",
            json={"messages": [{"role": "user", "content": prompt}], "temperature": 0.3, "max_tokens": 500},
            timeout=60.0,
        )
        response.raise_for_status()
        result = response.json()
        content = result["choices"][0]["message"]["content"]
        if "```json" in content:
            json_str = content.split("```json")[1].split("```")[0].strip()
        elif "{" in content:
            json_str = content[content.index("{"):content.rindex("}") + 1]
        else:
            json_str = content
        pattern_data = json.loads(json_str)
        await store_pattern(pattern_data, interaction)
        logger.info("Extracted pattern: %s", pattern_data.get("problem_type", "Unknown"))
    except Exception as exc:
        logger.error("Error extracting patterns: %s", exc)


async def store_pattern(pattern_data: Dict[str, Any], source_interaction: Dict[str, Any]) -> None:
    """Store extracted pattern in skills-patterns collection."""
    skill = {
        "skill_name": pattern_data.get("problem_type", "Unknown Skill"),
        "description": pattern_data.get("generalizable_pattern", ""),
        "usage_pattern": pattern_data.get("solution_approach", ""),
        "success_examples": [source_interaction.get("response", "")[:500]],
        "failure_examples": [],
        "prerequisites": [],
        "related_skills": pattern_data.get("skills_used", []),
        "value_score": source_interaction.get("value_score", 0.7),
        "last_updated": int(datetime.now().timestamp()),
    }
    embedding = await _embed(skill["description"])
    similar = _qdrant.query_points(
        collection_name="skills-patterns",
        query=embedding,
        limit=1,
        score_threshold=0.9,
    ).points
    if similar:
        existing_id = str(similar[0].id)
        existing_payload = similar[0].payload
        existing_payload["success_examples"].append(skill["success_examples"][0])
        existing_value = existing_payload.get("value_score", 0.5)
        existing_payload["value_score"] = existing_value * 0.8 + skill["value_score"] * 0.2
        existing_payload["last_updated"] = skill["last_updated"]
        _qdrant.set_payload(collection_name="skills-patterns", payload=existing_payload, points=[existing_id])
        logger.info("Updated existing pattern: %s", existing_id)
    else:
        pattern_id = str(uuid4())
        _qdrant.upsert(
            collection_name="skills-patterns",
            points=[PointStruct(id=pattern_id, vector=embedding, payload=skill)],
        )
        logger.info("Created new pattern: %s", pattern_id)


# ---------------------------------------------------------------------------
# Training data export
# ---------------------------------------------------------------------------

async def generate_fine_tuning_dataset() -> str:
    """
    Export high-value interactions to JSONL (OpenAI chat format) for archival and
    potential off-device fine-tuning.
    """
    try:
        high_value_interactions = _qdrant.scroll(
            collection_name="interaction-history",
            scroll_filter=Filter(
                must=[
                    FieldCondition(key="value_score", range=Range(gte=Config.HIGH_VALUE_THRESHOLD)),
                    FieldCondition(key="outcome", match=MatchValue(value="success")),
                ]
            ),
            limit=1000,
        )[0]
        training_data = []
        for point in high_value_interactions:
            payload = point.payload
            training_data.append({
                "messages": [
                    {"role": "system", "content": "You are a helpful NixOS and coding assistant specialized in system configuration and development."},
                    {"role": "user", "content": payload.get("query", "")},
                    {"role": "assistant", "content": payload.get("response", "")},
                ]
            })
        os.makedirs(os.path.dirname(Config.FINETUNE_DATA_PATH), exist_ok=True)
        with open(Config.FINETUNE_DATA_PATH, "w") as f:
            for item in training_data:
                f.write(json.dumps(item) + "\n")
        logger.info("Generated fine-tuning dataset: %d examples at %s", len(training_data), Config.FINETUNE_DATA_PATH)
        return Config.FINETUNE_DATA_PATH
    except Exception as exc:
        logger.error("Error generating fine-tuning dataset: %s", exc)
        return ""
