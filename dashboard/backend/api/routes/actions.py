"""
Action execution API endpoints
Supports executing predefined shell commands from config
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import logging
import json
import shlex
import subprocess
import asyncio
from pathlib import Path

router = APIRouter()
logger = logging.getLogger(__name__)

DATA_DIR = Path.home() / '.local/share/nixos-system-dashboard'


class ActionRequest(BaseModel):
    """Request to execute an action"""
    label: str


class ActionResponse(BaseModel):
    """Response from action execution"""
    status: str
    code: int
    message: str
    output: str


class Action(BaseModel):
    """Action definition"""
    label: str
    mode: str
    command: str
    description: Optional[str] = None


class ActionsConfig(BaseModel):
    """Configuration file format"""
    actions: List[Action]


def load_config() -> ActionsConfig:
    """Load actions configuration from config.json"""
    config_path = DATA_DIR / 'config.json'

    if not config_path.exists():
        logger.warning(f"Config file not found: {config_path}")
        return ActionsConfig(actions=[])

    try:
        with open(config_path, 'r') as f:
            config_data = json.load(f)
        return ActionsConfig(**config_data)
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load config: {e}")


@router.get("/", response_model=List[Action])
async def list_actions() -> List[Action]:
    """List all available actions"""
    try:
        config = load_config()
        return config.actions
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing actions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execute", response_model=ActionResponse)
async def execute_action(request: ActionRequest) -> ActionResponse:
    """Execute a predefined action by label"""
    try:
        config = load_config()

        # Find action by label
        action = next(
            (a for a in config.actions if a.label == request.label),
            None
        )

        if not action:
            raise HTTPException(
                status_code=404,
                detail=f"Action '{request.label}' not found"
            )

        # Verify action mode
        if action.mode != 'run':
            raise HTTPException(
                status_code=403,
                detail=f"Action '{request.label}' is not executable (mode: {action.mode})"
            )

        if not action.command:
            raise HTTPException(
                status_code=400,
                detail=f"Action '{request.label}' has no command defined"
            )

        # Execute command
        logger.info(f"Executing action '{request.label}': {action.command}")

        try:
            # Run command asynchronously with timeout
            process = await asyncio.create_subprocess_shell(
                action.command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(Path(__file__).resolve().parents[3])  # Project root
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=120.0
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                raise HTTPException(
                    status_code=504,
                    detail=f"Action '{request.label}' timed out after 120 seconds"
                )

            returncode = process.returncode
            output = (stdout.decode('utf-8', errors='replace') +
                     stderr.decode('utf-8', errors='replace'))

            # Limit output to last 4000 chars
            if len(output) > 4000:
                output = "...[truncated]...\n" + output[-4000:]

            status = 'ok' if returncode == 0 else 'error'
            message = f"{request.label} finished with exit code {returncode}"

            logger.info(f"Action '{request.label}' completed with status: {status}")

            return ActionResponse(
                status=status,
                code=returncode,
                message=message,
                output=output
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error executing action '{request.label}': {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to execute action: {e}"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in execute_action: {e}")
        raise HTTPException(status_code=500, detail=str(e))
