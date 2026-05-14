from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import sessionmaker

from schema import INTERACTION_HISTORY

logger = logging.getLogger("aidb.interaction_history")

class InteractionHistoryStore:
    """Persistent storage for AI interaction history using PostgreSQL."""

    def __init__(self, engine: sa.Engine):
        self.engine = engine
        self._session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)

    async def record_interaction(self, interaction: Dict[str, Any]) -> str:
        """
        Record a single AI interaction.

        Args:
            interaction: Dictionary containing interaction details.

        Returns:
            Interaction ID (string)
        """
        def _insert():
            with self.engine.begin() as conn:
                stmt = insert(INTERACTION_HISTORY).values(
                    session_id=interaction.get("session_id"),
                    project=interaction.get("project"),
                    query=interaction["query"],
                    response=interaction.get("response"),
                    agent_type=interaction.get("agent_type", "unknown"),
                    model_used=interaction.get("model_used"),
                    role=interaction.get("role"),
                    outcome=interaction.get("outcome", "unknown"),
                    tokens_in=interaction.get("tokens_in", 0),
                    tokens_out=interaction.get("tokens_out", 0),
                    latency_ms=interaction.get("latency_ms", 0),
                    value_score=interaction.get("value_score", 0.0),
                    metadata=interaction.get("metadata", {}),
                ).returning(INTERACTION_HISTORY.c.interaction_id)
                
                result = conn.execute(stmt)
                return str(result.scalar())

        try:
            interaction_id = await sa.to_thread(_insert) if hasattr(sa, "to_thread") else _insert()
            logger.info(f"Recorded interaction {interaction_id}")
            return interaction_id
        except Exception as e:
            logger.error(f"Failed to record interaction: {e}")
            raise

    async def get_history(
        self,
        session_id: Optional[UUID] = None,
        agent_type: Optional[str] = None,
        project: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Retrieve interaction history with filters.
        """
        def _fetch():
            query = sa.select(INTERACTION_HISTORY).order_by(INTERACTION_HISTORY.c.created_at.desc())
            
            if session_id:
                query = query.where(INTERACTION_HISTORY.c.session_id == session_id)
            if agent_type:
                query = query.where(INTERACTION_HISTORY.c.agent_type == agent_type)
            if project:
                query = query.where(INTERACTION_HISTORY.c.project == project)
                
            query = query.limit(limit).offset(offset)
            
            with self.engine.connect() as conn:
                result = conn.execute(query)
                return [dict(row._mapping) for row in result]

        return await sa.to_thread(_fetch) if hasattr(sa, "to_thread") else _fetch()

    async def get_stats(self) -> Dict[str, Any]:
        """Get summary statistics for interaction history."""
        def _fetch():
            with self.engine.connect() as conn:
                total = conn.execute(sa.select(sa.func.count()).select_from(INTERACTION_HISTORY)).scalar()
                outcomes = conn.execute(
                    sa.select(INTERACTION_HISTORY.c.outcome, sa.func.count())
                    .group_by(INTERACTION_HISTORY.c.outcome)
                ).all()
                
                return {
                    "total_interactions": total,
                    "outcomes": {row[0]: row[1] for row in outcomes}
                }
        return await sa.to_thread(_fetch) if hasattr(sa, "to_thread") else _fetch()
