from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp_server.server import MCPServer

LOGGER = logging.getLogger(__name__)
router = APIRouter(prefix="/registry", tags=["registry"])

def get_mcp_server(request: Request) -> "MCPServer":
    return request.app.state.mcp_server

def _system_registry():
    from mcp_server.server import SYSTEM_REGISTRY
    return SYSTEM_REGISTRY

class RegistryResource(BaseModel):
    """Represents a resource in the system registry."""
    id: int
    resource_type: str = Field(..., description="Type of the resource (e.g., 'skill', 'tool', 'data_source').")
    name: str = Field(..., description="Unique name of the resource.")
    version: str = Field(..., description="Version of the resource.")
    description: Optional[str] = Field(None, description="Detailed description of the resource.")
    location: str = Field(..., description="Location of the resource (e.g., Git URL, API endpoint, file path).")
    install_command: Optional[str] = Field(None, description="Shell command to install or set up the resource.")
    dependencies: Optional[dict] = Field(None, description="List of other resource names it depends on.")
    added_at: str

    class Config:
        orm_mode = True

@router.post("/register", status_code=201)
async def register_resource(
    resource: RegistryResource,
    mcp_server: MCPServer = Depends(get_mcp_server),
) -> Dict[str, Any]:
    """Registers a new resource in the system registry."""
    LOGGER.info(f"Registering resource: {resource.name}")
    
    def _insert():
        with mcp_server._engine.begin() as conn:
            registry = _system_registry()
            stmt = insert(registry).values(
                resource_type=resource.resource_type,
                name=resource.name,
                version=resource.version,
                description=resource.description,
                location=resource.location,
                install_command=resource.install_command,
                dependencies=resource.dependencies,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["name"],
                set_={
                    "resource_type": stmt.excluded.resource_type,
                    "version": stmt.excluded.version,
                    "description": stmt.excluded.description,
                    "location": stmt.excluded.location,
                    "install_command": stmt.excluded.install_command,
                    "dependencies": stmt.excluded.dependencies,
                },
            )
            conn.execute(stmt)

    await asyncio.to_thread(_insert)

    return {"status": "ok", "message": f"Resource '{resource.name}' registered successfully."}

@router.get("/resources", response_model=List[RegistryResource])
async def list_resources(
    resource_type: Optional[str] = None,
    mcp_server: MCPServer = Depends(get_mcp_server),
) -> List[RegistryResource]:
    """Lists all available resources, optionally filtering by type."""
    LOGGER.info(f"Listing resources of type: {resource_type}")
    
    def _fetch():
        with mcp_server._engine.connect() as conn:
            registry = _system_registry()
            query = sa.select(registry)
            if resource_type:
                query = query.where(registry.c.resource_type == resource_type)
            result = conn.execute(query)
            return [RegistryResource.from_orm(row) for row in result.mappings()]

    resources = await asyncio.to_thread(_fetch)
    return resources

@router.get("/search", response_model=List[RegistryResource])
async def search_resources(
    query: str,
    mcp_server: MCPServer = Depends(get_mcp_server),
) -> List[RegistryResource]:
    """Searches for resources based on a query string."""
    LOGGER.info(f"Searching for resources with query: {query}")
    
    def _search():
        with mcp_server._engine.connect() as conn:
            search_query = f"%{query}%"
            registry = _system_registry()
            stmt = sa.select(registry).where(
                sa.or_(
                    registry.c.name.ilike(search_query),
                    registry.c.description.ilike(search_query),
                )
            )
            result = conn.execute(stmt)
            return [RegistryResource.from_orm(row) for row in result.mappings()]

    resources = await asyncio.to_thread(_search)
    return resources
