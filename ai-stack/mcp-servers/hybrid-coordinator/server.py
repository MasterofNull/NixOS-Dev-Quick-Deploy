#!/usr/bin/env python3
"""
Hybrid Agent Coordinator MCP Server

Coordinates between local LLMs and remote agents while implementing
continuous learning through interaction tracking and pattern extraction.

Features:
- Context augmentation from Qdrant
- Query routing (local vs remote)
- Outcome tracking and value scoring
- Pattern extraction and storage
- Fine-tuning data generation
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

import httpx
from mcp import Tool
from mcp.server import Server
from mcp.types import TextContent
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    Range,
    VectorParams,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("hybrid-coordinator")

# Initialize server
app = Server("hybrid-coordinator")

# Global clients
qdrant_client: Optional[QdrantClient] = None
llama_cpp_client: Optional[httpx.AsyncClient] = None
embedding_client: Optional[httpx.AsyncClient] = None

TELEMETRY_PATH = os.path.expanduser(
    os.getenv(
        "HYBRID_TELEMETRY_PATH",
        os.getenv(
            "TELEMETRY_PATH",
            "~/.local/share/nixos-ai-stack/telemetry/hybrid-events.jsonl",
        ),
    )
)


def record_telemetry_event(event_type: str, payload: Dict[str, Any]) -> None:
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        **payload,
    }
    os.makedirs(os.path.dirname(TELEMETRY_PATH), exist_ok=True)
    with open(TELEMETRY_PATH, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload) + "\n")


# ============================================================================
# Configuration
# ============================================================================


class Config:
    """Hybrid coordinator configuration"""

    QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
    QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", None)
    LLAMA_CPP_URL = os.getenv("LLAMA_CPP_BASE_URL", "http://localhost:8080")
    LLAMA_CPP_CODER_URL = os.getenv(
        "LLAMA_CPP_CODER_URL", "http://localhost:8080"
    )
    LLAMA_CPP_DEEPSEEK_URL = os.getenv(
        "LLAMA_CPP_DEEPSEEK_URL", "http://localhost:8080"
    )

    EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_DIM = 384

    LOCAL_CONFIDENCE_THRESHOLD = float(
        os.getenv("LOCAL_CONFIDENCE_THRESHOLD", "0.7")
    )
    HIGH_VALUE_THRESHOLD = float(os.getenv("HIGH_VALUE_THRESHOLD", "0.7"))
    PATTERN_EXTRACTION_ENABLED = os.getenv("PATTERN_EXTRACTION_ENABLED", "true").lower() == "true"

    FINETUNE_DATA_PATH = os.path.expanduser(
        os.getenv(
            "FINETUNE_DATA_PATH",
            "~/.local/share/nixos-ai-stack/fine-tuning/dataset.jsonl",
        )
    )


# ============================================================================
# Qdrant Collection Management
# ============================================================================


COLLECTIONS = {
    "codebase-context": {
        "vector_size": Config.EMBEDDING_DIM,
        "distance": Distance.COSINE,
        "payload_schema": {
            "file_path": "string",
            "code_snippet": "text",
            "language": "string",
            "framework": "string",
            "purpose": "text",
            "last_accessed": "integer",
            "access_count": "integer",
            "success_rate": "float",
        },
    },
    "skills-patterns": {
        "vector_size": Config.EMBEDDING_DIM,
        "distance": Distance.COSINE,
        "payload_schema": {
            "skill_name": "string",
            "description": "text",
            "usage_pattern": "text",
            "success_examples": "array",
            "failure_examples": "array",
            "prerequisites": "array",
            "related_skills": "array",
            "value_score": "float",
            "last_updated": "integer",
        },
    },
    "error-solutions": {
        "vector_size": Config.EMBEDDING_DIM,
        "distance": Distance.COSINE,
        "payload_schema": {
            "error_message": "text",
            "error_type": "string",
            "context": "text",
            "solution": "text",
            "solution_verified": "boolean",
            "success_count": "integer",
            "failure_count": "integer",
            "first_seen": "integer",
            "last_used": "integer",
            "confidence_score": "float",
        },
    },
    "interaction-history": {
        "vector_size": Config.EMBEDDING_DIM,
        "distance": Distance.COSINE,
        "payload_schema": {
            "query": "text",
            "agent_type": "string",
            "model_used": "string",
            "context_provided": "array",
            "response": "text",
            "outcome": "string",
            "user_feedback": "integer",
            "tokens_used": "integer",
            "latency_ms": "integer",
            "timestamp": "integer",
            "value_score": "float",
        },
    },
    "best-practices": {
        "vector_size": Config.EMBEDDING_DIM,
        "distance": Distance.COSINE,
        "payload_schema": {
            "category": "string",
            "title": "string",
            "description": "text",
            "examples": "array",
            "anti_patterns": "array",
            "references": "array",
            "endorsement_count": "integer",
            "last_validated": "integer",
        },
    },
}


async def initialize_collections():
    """Initialize Qdrant collections if they don't exist"""
    global qdrant_client

    for collection_name, schema in COLLECTIONS.items():
        try:
            # Check if collection exists
            collections = qdrant_client.get_collections().collections
            exists = any(c.name == collection_name for c in collections)

            if not exists:
                logger.info(f"Creating collection: {collection_name}")
                qdrant_client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(
                        size=schema["vector_size"], distance=schema["distance"]
                    ),
                )
                logger.info(f"✓ Collection created: {collection_name}")
            else:
                logger.info(f"✓ Collection exists: {collection_name}")

        except Exception as e:
            logger.error(f"Error creating collection {collection_name}: {e}")


# ============================================================================
# Embedding Functions
# ============================================================================


async def embed_text(text: str) -> List[float]:
    """
    Generate embedding for text using local embedding model
    (llama.cpp OpenAI-compatible embeddings)
    """
    global embedding_client

    try:
        # Using llama.cpp embedding endpoint
        response = await embedding_client.post(
            f"{Config.LLAMA_CPP_URL}/v1/embeddings",
            json={"model": "nomic-embed-text", "input": text},
            timeout=30.0,
        )
        response.raise_for_status()
        result = response.json()
        return result.get("data", [{}])[0].get("embedding", [])

    except Exception as e:
        logger.error(f"Embedding error: {e}")
        # Fallback: return zero vector
        return [0.0] * Config.EMBEDDING_DIM


# ============================================================================
# Value Scoring Algorithm
# ============================================================================


def compute_value_score(interaction: Dict[str, Any]) -> float:
    """
    Score interaction value (0-1) based on multiple factors
    """
    score = 0.0

    # 1. Outcome quality (40% weight)
    if interaction.get("outcome") == "success":
        score += 0.4
    elif interaction.get("outcome") == "partial":
        score += 0.2

    # 2. User feedback (20% weight)
    user_feedback = interaction.get("user_feedback", 0)
    if user_feedback == 1:
        score += 0.2
    elif user_feedback == 0:
        score += 0.1

    # 3. Reusability potential (20% weight)
    reusability = estimate_reusability(interaction.get("query", ""))
    score += 0.2 * reusability

    # 4. Complexity (10% weight)
    complexity = estimate_complexity(interaction.get("response", ""))
    score += 0.1 * complexity

    # 5. Novelty (10% weight)
    novelty = 0.5  # Simplified for now
    score += 0.1 * novelty

    return min(score, 1.0)


def estimate_reusability(query: str) -> float:
    """Estimate how likely this query pattern will recur"""
    reusable_keywords = ["how to", "best practice", "configure", "setup", "install"]
    keyword_count = sum(1 for kw in reusable_keywords if kw.lower() in query.lower())
    return min(keyword_count * 0.25, 1.0)


def estimate_complexity(response: str) -> float:
    """Estimate response complexity"""
    # Multi-step solutions
    steps = response.count("1.") + response.count("2.") + response.count("3.")

    # Code blocks
    code_blocks = response.count("```")

    # Length-based complexity
    length_score = min(len(response) / 2000, 1.0)

    return min((steps * 0.1 + code_blocks * 0.15 + length_score * 0.5), 1.0)


# ============================================================================
# Context Augmentation
# ============================================================================


async def augment_query_with_context(
    query: str, agent_type: str = "remote"
) -> Dict[str, Any]:
    """
    Enhance query with relevant local context from Qdrant
    """
    global qdrant_client

    # 1. Embed the query
    query_embedding = await embed_text(query)

    context_ids = []
    results_text = []

    # 2. Search codebase context
    try:
        codebase_results = qdrant_client.query_points(
            collection_name="codebase-context",
            query=query_embedding,
            limit=5,
            score_threshold=0.7,
        ).points

        if codebase_results:
            results_text.append("## Relevant Code Context\n")
            for result in codebase_results:
                context_ids.append(str(result.id))
                payload = result.payload
                results_text.append(
                    f"- **{payload.get('file_path', 'Unknown')}** ({payload.get('language', 'unknown')})\n"
                )
                results_text.append(f"  {payload.get('purpose', 'No description')}\n")
                snippet = payload.get("code_snippet", "")
                if snippet:
                    results_text.append(f"  ```{payload.get('language', '')}\n  {snippet[:200]}...\n  ```\n")
    except Exception as e:
        logger.warning(f"Error searching codebase-context: {e}")

    # 3. Search skills/patterns
    try:
        skills_results = qdrant_client.query_points(
            collection_name="skills-patterns",
            query=query_embedding,
            limit=3,
            score_threshold=0.75,
        ).points

        if skills_results:
            results_text.append("\n## Related Skills & Patterns\n")
            for result in skills_results:
                context_ids.append(str(result.id))
                payload = result.payload
                results_text.append(f"- **{payload.get('skill_name', 'Unknown Skill')}**\n")
                results_text.append(f"  {payload.get('description', 'No description')}\n")
    except Exception as e:
        logger.warning(f"Error searching skills-patterns: {e}")

    # 4. Search error solutions
    try:
        error_results = qdrant_client.query_points(
            collection_name="error-solutions",
            query=query_embedding,
            limit=2,
            score_threshold=0.8,
        ).points

        if error_results:
            results_text.append("\n## Similar Error Solutions\n")
            for result in error_results:
                context_ids.append(str(result.id))
                payload = result.payload
                results_text.append(f"- **Error**: {payload.get('error_type', 'Unknown')}\n")
                results_text.append(f"  **Solution**: {payload.get('solution', 'No solution')[:200]}...\n")
                confidence = payload.get('confidence_score', 0)
                results_text.append(f"  **Confidence**: {confidence:.2f}\n")
    except Exception as e:
        logger.warning(f"Error searching error-solutions: {e}")

    # 5. Search best practices
    try:
        bp_results = qdrant_client.query_points(
            collection_name="best-practices",
            query=query_embedding,
            limit=2,
            score_threshold=0.75,
        ).points

        if bp_results:
            results_text.append("\n## Best Practices\n")
            for result in bp_results:
                context_ids.append(str(result.id))
                payload = result.payload
                results_text.append(f"- **{payload.get('title', 'Unknown')}** ({payload.get('category', 'general')})\n")
                results_text.append(f"  {payload.get('description', 'No description')}\n")
    except Exception as e:
        logger.warning(f"Error searching best-practices: {e}")

    # 6. Construct augmented prompt
    context_text = "".join(results_text) if results_text else "No relevant context found in local knowledge base."

    augmented_prompt = f"""Query: {query}

Relevant Context from Local Knowledge Base:
{context_text}

Please use this context to provide a more accurate and efficient response.
"""

    record_telemetry_event(
        "context_augmented",
        {
            "agent_type": agent_type,
            "context_count": len(context_ids),
            "collections": list(COLLECTIONS.keys()),
        },
    )

    return {
        "augmented_prompt": augmented_prompt,
        "context_ids": context_ids,
        "original_query": query,
        "context_count": len(context_ids),
    }


# ============================================================================
# Interaction Tracking
# ============================================================================


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
    """
    Store interaction in Qdrant for learning
    """
    global qdrant_client

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
        "value_score": 0.0,  # Computed later after outcome
    }

    # Embed the query for future similarity search
    query_embedding = await embed_text(query)

    # Store in Qdrant
    try:
        qdrant_client.upsert(
            collection_name="interaction-history",
            points=[
                PointStruct(
                    id=interaction_id, vector=query_embedding, payload=interaction
                )
            ],
        )
        logger.info(f"Tracked interaction: {interaction_id}")
        record_telemetry_event(
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

    except Exception as e:
        logger.error(f"Error tracking interaction: {e}")
        return ""


async def update_interaction_outcome(
    interaction_id: str, outcome: str, user_feedback: int = 0
):
    """
    Update interaction with outcome and compute value score
    """
    global qdrant_client

    try:
        # Fetch interaction
        result = qdrant_client.retrieve(
            collection_name="interaction-history", ids=[interaction_id]
        )

        if not result:
            logger.error(f"Interaction not found: {interaction_id}")
            return

        interaction = result[0].payload

        # Update outcome
        interaction["outcome"] = outcome
        interaction["user_feedback"] = user_feedback

        # Compute value score
        value_score = compute_value_score(interaction)
        interaction["value_score"] = value_score

        # Update in Qdrant
        qdrant_client.set_payload(
            collection_name="interaction-history",
            payload=interaction,
            points=[interaction_id],
        )

        logger.info(
            f"Updated interaction {interaction_id}: outcome={outcome}, value={value_score:.2f}"
        )

        # If high-value, extract patterns
        if value_score >= Config.HIGH_VALUE_THRESHOLD and Config.PATTERN_EXTRACTION_ENABLED:
            await extract_patterns(interaction)

        # Update context success rates
        if interaction.get("context_provided"):
            await update_context_metrics(
                interaction["context_provided"], outcome == "success"
            )

    except Exception as e:
        logger.error(f"Error updating interaction outcome: {e}")


async def update_context_metrics(context_ids: List[str], success: bool):
    """
    Update success rates and access counts for context items
    """
    global qdrant_client

    collections_to_update = [
        "codebase-context",
        "skills-patterns",
        "error-solutions",
        "best-practices",
    ]

    for collection_name in collections_to_update:
        for context_id in context_ids:
            try:
                # Fetch current payload
                result = qdrant_client.retrieve(
                    collection_name=collection_name, ids=[context_id]
                )

                if result:
                    payload = result[0].payload

                    # Update metrics
                    access_count = payload.get("access_count", 0) + 1
                    payload["access_count"] = access_count
                    payload["last_accessed"] = int(datetime.now().timestamp())

                    # Update success rate
                    if "success_rate" in payload:
                        current_rate = payload.get("success_rate", 0.5)
                        # Moving average
                        new_rate = (
                            current_rate * 0.9 + (1.0 if success else 0.0) * 0.1
                        )
                        payload["success_rate"] = new_rate

                    # Update in Qdrant
                    qdrant_client.set_payload(
                        collection_name=collection_name,
                        payload=payload,
                        points=[context_id],
                    )

            except Exception as e:
                logger.warning(
                    f"Error updating context {context_id} in {collection_name}: {e}"
                )


# ============================================================================
# Pattern Extraction
# ============================================================================


async def extract_patterns(interaction: Dict[str, Any]):
    """
    Extract reusable patterns from successful interactions using local LLM
    """
    global llama_cpp_client

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
        # Use llama.cpp for pattern extraction
        response = await llama_cpp_client.post(
            "/chat/completions",
            json={
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 500,
            },
            timeout=60.0,
        )
        response.raise_for_status()
        result = response.json()

        # Parse LLM response
        content = result["choices"][0]["message"]["content"]

        # Extract JSON from response
        if "```json" in content:
            json_str = content.split("```json")[1].split("```")[0].strip()
        elif "{" in content:
            json_str = content[content.index("{") : content.rindex("}") + 1]
        else:
            json_str = content

        pattern_data = json.loads(json_str)

        # Store as new skill/pattern
        await store_pattern(pattern_data, interaction)

        logger.info(f"Extracted pattern: {pattern_data.get('problem_type', 'Unknown')}")

    except Exception as e:
        logger.error(f"Error extracting patterns: {e}")


async def store_pattern(pattern_data: Dict[str, Any], source_interaction: Dict[str, Any]):
    """
    Store extracted pattern in skills-patterns collection
    """
    global qdrant_client

    # Create skill/pattern payload
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

    # Embed the description
    embedding = await embed_text(skill["description"])

    # Check if similar pattern exists
    similar = qdrant_client.query_points(
        collection_name="skills-patterns",
        query=embedding,
        limit=1,
        score_threshold=0.9,
    ).points

    if similar:
        # Update existing pattern
        existing_id = str(similar[0].id)
        existing_payload = similar[0].payload

        # Add to success examples
        existing_payload["success_examples"].append(skill["success_examples"][0])

        # Update value score (moving average)
        existing_value = existing_payload.get("value_score", 0.5)
        new_value = existing_value * 0.8 + skill["value_score"] * 0.2
        existing_payload["value_score"] = new_value
        existing_payload["last_updated"] = skill["last_updated"]

        qdrant_client.set_payload(
            collection_name="skills-patterns",
            payload=existing_payload,
            points=[existing_id],
        )

        logger.info(f"Updated existing pattern: {existing_id}")
    else:
        # Create new pattern
        pattern_id = str(uuid4())
        qdrant_client.upsert(
            collection_name="skills-patterns",
            points=[PointStruct(id=pattern_id, vector=embedding, payload=skill)],
        )

        logger.info(f"Created new pattern: {pattern_id}")


# ============================================================================
# Fine-Tuning Data Generation
# ============================================================================


async def generate_fine_tuning_dataset() -> str:
    """
    Generate fine-tuning dataset from high-value interactions
    """
    global qdrant_client

    try:
        # Query high-value successful interactions
        high_value_interactions = qdrant_client.scroll(
            collection_name="interaction-history",
            scroll_filter=Filter(
                must=[
                    FieldCondition(
                        key="value_score", range=Range(gte=Config.HIGH_VALUE_THRESHOLD)
                    ),
                    FieldCondition(key="outcome", match=MatchValue(value="success")),
                ]
            ),
            limit=1000,
        )[0]

        # Format for fine-tuning (OpenAI format)
        training_data = []
        for point in high_value_interactions:
            payload = point.payload
            training_data.append(
                {
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a helpful NixOS and coding assistant specialized in system configuration and development.",
                        },
                        {"role": "user", "content": payload.get("query", "")},
                        {"role": "assistant", "content": payload.get("response", "")},
                    ]
                }
            )

        # Save to JSONL
        os.makedirs(os.path.dirname(Config.FINETUNE_DATA_PATH), exist_ok=True)

        with open(Config.FINETUNE_DATA_PATH, "w") as f:
            for item in training_data:
                f.write(json.dumps(item) + "\n")

        logger.info(
            f"Generated fine-tuning dataset: {len(training_data)} examples at {Config.FINETUNE_DATA_PATH}"
        )

        return Config.FINETUNE_DATA_PATH

    except Exception as e:
        logger.error(f"Error generating fine-tuning dataset: {e}")
        return ""


# ============================================================================
# MCP Tool Definitions
# ============================================================================


@app.list_tools()
async def list_tools() -> List[Tool]:
    """List available tools"""
    return [
        Tool(
            name="augment_query",
            description="Augment a query with relevant context from local knowledge base",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The query to augment with context",
                    },
                    "agent_type": {
                        "type": "string",
                        "description": "Type of agent requesting context (local or remote)",
                        "enum": ["local", "remote"],
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="track_interaction",
            description="Record an interaction for learning and analysis",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "response": {"type": "string"},
                    "agent_type": {"type": "string"},
                    "model_used": {"type": "string"},
                    "context_ids": {"type": "array", "items": {"type": "string"}},
                    "tokens_used": {"type": "integer"},
                    "latency_ms": {"type": "integer"},
                },
                "required": ["query", "response", "agent_type", "model_used"],
            },
        ),
        Tool(
            name="update_outcome",
            description="Update interaction outcome and trigger learning",
            inputSchema={
                "type": "object",
                "properties": {
                    "interaction_id": {"type": "string"},
                    "outcome": {
                        "type": "string",
                        "enum": ["success", "partial", "failure"],
                    },
                    "user_feedback": {"type": "integer", "minimum": -1, "maximum": 1},
                },
                "required": ["interaction_id", "outcome"],
            },
        ),
        Tool(
            name="generate_training_data",
            description="Generate fine-tuning dataset from high-value interactions",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="search_context",
            description="Search specific collection for relevant context",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "collection": {
                        "type": "string",
                        "enum": [
                            "codebase-context",
                            "skills-patterns",
                            "error-solutions",
                            "best-practices",
                        ],
                    },
                    "limit": {"type": "integer", "default": 5},
                },
                "required": ["query", "collection"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> List[TextContent]:
    """Handle tool calls"""

    if name == "augment_query":
        query = arguments.get("query", "")
        agent_type = arguments.get("agent_type", "remote")

        result = await augment_query_with_context(query, agent_type)

        return [
            TextContent(
                type="text",
                text=json.dumps(result, indent=2),
            )
        ]

    elif name == "track_interaction":
        interaction_id = await track_interaction(
            query=arguments.get("query", ""),
            response=arguments.get("response", ""),
            agent_type=arguments.get("agent_type", "unknown"),
            model_used=arguments.get("model_used", "unknown"),
            context_ids=arguments.get("context_ids", []),
            tokens_used=arguments.get("tokens_used", 0),
            latency_ms=arguments.get("latency_ms", 0),
        )

        return [
            TextContent(
                type="text",
                text=json.dumps({"interaction_id": interaction_id}),
            )
        ]

    elif name == "update_outcome":
        await update_interaction_outcome(
            interaction_id=arguments.get("interaction_id", ""),
            outcome=arguments.get("outcome", "unknown"),
            user_feedback=arguments.get("user_feedback", 0),
        )

        return [TextContent(type="text", text=json.dumps({"status": "updated"}))]

    elif name == "generate_training_data":
        dataset_path = await generate_fine_tuning_dataset()

        return [
            TextContent(
                type="text",
                text=json.dumps({"dataset_path": dataset_path}),
            )
        ]

    elif name == "search_context":
        query = arguments.get("query", "")
        collection = arguments.get("collection", "codebase-context")
        limit = arguments.get("limit", 5)

        query_embedding = await embed_text(query)

        results = qdrant_client.query_points(
            collection_name=collection,
            query=query_embedding,
            limit=limit,
            score_threshold=0.7,
        ).points

        formatted_results = [
            {"id": str(r.id), "score": r.score, "payload": r.payload} for r in results
        ]

        return [
            TextContent(
                type="text",
                text=json.dumps(formatted_results, indent=2),
            )
        ]

    else:
        raise ValueError(f"Unknown tool: {name}")


# ============================================================================
# Server Initialization
# ============================================================================


async def initialize_server():
    """Initialize global clients and collections"""
    global qdrant_client, llama_cpp_client, embedding_client

    logger.info("Initializing Hybrid Agent Coordinator...")

    # Initialize Qdrant client
    qdrant_client = QdrantClient(
        url=Config.QDRANT_URL,
        api_key=Config.QDRANT_API_KEY,
        timeout=30.0,
    )

    # Initialize llama.cpp client
    llama_cpp_client = httpx.AsyncClient(
        base_url=Config.LLAMA_CPP_URL,
        timeout=120.0,
    )

    # Initialize embedding client
    embedding_client = httpx.AsyncClient(timeout=30.0)

    # Create collections
    await initialize_collections()

    logger.info("✓ Hybrid Agent Coordinator initialized successfully")


# ============================================================================
# Main Entry Point
# ============================================================================


async def main():
    """Run the MCP server"""
    await initialize_server()

    # Check if running in HTTP mode (for container deployment)
    mode = os.getenv("MCP_SERVER_MODE", "stdio")

    if mode == "http":
        # Run as HTTP server with health endpoint
        from aiohttp import web

        async def handle_health(request):
            """Health check endpoint"""
            return web.json_response({
                "status": "healthy",
                "service": "hybrid-coordinator",
                "collections": list(COLLECTIONS.keys())
            })

        async def handle_augment_query(request):
            """HTTP endpoint for query augmentation"""
            data = await request.json()
            query = data.get("query", "")
            agent_type = data.get("agent_type", "remote")

            result = await augment_query_with_context(query, agent_type)
            return web.json_response(result)

        http_app = web.Application()
        http_app.router.add_get('/health', handle_health)
        http_app.router.add_post('/augment_query', handle_augment_query)

        port = int(os.getenv("MCP_SERVER_PORT", "8092"))
        logger.info(f"Starting HTTP server on port {port}")

        runner = web.AppRunner(http_app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', port)
        await site.start()

        logger.info(f"✓ Hybrid Coordinator HTTP server running on http://0.0.0.0:{port}")

        # Keep server running
        await asyncio.Event().wait()
    else:
        # Run MCP server via stdin/stdout (for local MCP usage)
        from mcp.server.stdio import stdio_server

        async with stdio_server() as (read_stream, write_stream):
            await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
