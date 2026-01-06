"""Service management API endpoints"""
from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
import logging

from api.services.service_manager import ServiceManager

router = APIRouter()
logger = logging.getLogger(__name__)
service_manager = ServiceManager()


@router.get("")
async def list_services() -> List[Dict[str, Any]]:
    """List all monitored services"""
    try:
        services = await service_manager.list_services()
        return services
    except Exception as e:
        logger.error(f"Error listing services: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{service_id}/start")
async def start_service(service_id: str) -> Dict[str, Any]:
    """Start a service"""
    try:
        result = await service_manager.start_service(service_id)
        return result
    except Exception as e:
        logger.error(f"Error starting service {service_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{service_id}/stop")
async def stop_service(service_id: str) -> Dict[str, Any]:
    """Stop a service"""
    try:
        result = await service_manager.stop_service(service_id)
        return result
    except Exception as e:
        logger.error(f"Error stopping service {service_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{service_id}/restart")
async def restart_service(service_id: str) -> Dict[str, Any]:
    """Restart a service"""
    try:
        result = await service_manager.restart_service(service_id)
        return result
    except Exception as e:
        logger.error(f"Error restarting service {service_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/actions/start-all")
async def start_all_services() -> Dict[str, Any]:
    """Start all monitored services"""
    try:
        result = await service_manager.start_all_services()
        return result
    except Exception as e:
        logger.error(f"Error starting all services: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/actions/stop-all")
async def stop_all_services() -> Dict[str, Any]:
    """Stop all monitored services"""
    try:
        result = await service_manager.stop_all_services()
        return result
    except Exception as e:
        logger.error(f"Error stopping all services: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/actions/restart-all")
async def restart_all_services() -> Dict[str, Any]:
    """Restart all monitored services"""
    try:
        result = await service_manager.restart_all_services()
        return result
    except Exception as e:
        logger.error(f"Error restarting all services: {e}")
        raise HTTPException(status_code=500, detail=str(e))
