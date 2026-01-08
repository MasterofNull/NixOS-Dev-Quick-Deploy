"""Container management API endpoints"""
from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
import logging

from api.services.container_manager import ContainerManager

router = APIRouter()
logger = logging.getLogger(__name__)
container_manager = ContainerManager()


@router.get("")
async def list_containers() -> List[Dict[str, Any]]:
    """List all containers"""
    try:
        containers = await container_manager.list_containers()
        return containers
    except Exception as e:
        logger.error(f"Error listing containers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ai-stack/start")
async def start_ai_stack() -> Dict[str, Any]:
    """Start all AI stack containers"""
    try:
        result = await container_manager.start_ai_stack()
        return result
    except Exception as e:
        logger.error(f"Error starting AI stack: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ai-stack/stop")
async def stop_ai_stack() -> Dict[str, Any]:
    """Stop all AI stack containers"""
    try:
        result = await container_manager.stop_ai_stack()
        return result
    except Exception as e:
        logger.error(f"Error stopping AI stack: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ai-stack/restart")
async def restart_ai_stack() -> Dict[str, Any]:
    """Restart all AI stack containers"""
    try:
        result = await container_manager.restart_ai_stack()
        return result
    except Exception as e:
        logger.error(f"Error restarting AI stack: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{container_id}/start")
async def start_container(container_id: str) -> Dict[str, Any]:
    """Start a container"""
    try:
        result = await container_manager.start_container(container_id)
        return result
    except Exception as e:
        logger.error(f"Error starting container: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{container_id}/stop")
async def stop_container(container_id: str) -> Dict[str, Any]:
    """Stop a container"""
    try:
        result = await container_manager.stop_container(container_id)
        return result
    except Exception as e:
        logger.error(f"Error stopping container: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{container_id}/restart")
async def restart_container(container_id: str) -> Dict[str, Any]:
    """Restart a container"""
    try:
        result = await container_manager.restart_container(container_id)
        return result
    except Exception as e:
        logger.error(f"Error restarting container: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{container_id}/logs")
async def get_container_logs(container_id: str, tail: int = 100) -> Dict[str, Any]:
    """Get container logs"""
    try:
        logs = await container_manager.get_logs(container_id, tail)
        return {"logs": logs}
    except Exception as e:
        logger.error(f"Error getting logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))
