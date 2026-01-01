"""
VSCode Extension Telemetry Router for AIDB MCP Server
Collects and analyzes telemetry from VSCode AI extensions
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import json
import os
from pathlib import Path

router = APIRouter(prefix="/telemetry/vscode", tags=["vscode-telemetry"])

# Telemetry storage path
TELEMETRY_DIR = Path.home() / ".local/share/nixos-ai-stack/telemetry"
TELEMETRY_FILE = TELEMETRY_DIR / "vscode-events.jsonl"

# Ensure telemetry directory exists
TELEMETRY_DIR.mkdir(parents=True, exist_ok=True)


class VscodeEvent(BaseModel):
    """VSCode extension telemetry event schema"""
    event_type: str = Field(..., description="Event type: completion, refactoring, feedback, error, health-check")
    extension: str = Field(..., description="Extension name: claude-code, continue, kombai, codeium")
    timestamp: Optional[datetime] = Field(None, description="Event timestamp (auto-generated if not provided)")
    model_used: Optional[str] = Field(None, description="Model used for inference")
    is_local: bool = Field(True, description="Whether local inference was used")
    tokens_used: Optional[int] = Field(None, description="Number of tokens used")
    latency_ms: Optional[int] = Field(None, description="Request latency in milliseconds")
    success: bool = Field(True, description="Whether the request was successful")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    user_feedback: Optional[int] = Field(None, description="User feedback: -1 (bad), 0 (neutral), 1 (good)")

    class Config:
        json_schema_extra = {
            "example": {
                "event_type": "completion",
                "extension": "continue",
                "model_used": "Qwen/Qwen2.5-Coder-7B-Instruct",
                "is_local": True,
                "tokens_used": 234,
                "latency_ms": 145,
                "success": True,
                "metadata": {"language": "python", "file_extension": ".py"}
            }
        }


class TelemetryStats(BaseModel):
    """VSCode telemetry statistics"""
    total_events: int
    local_usage_pct: float
    remote_usage_pct: float
    avg_latency_ms: float
    success_rate: float
    events_by_extension: Dict[str, int]
    events_by_type: Dict[str, int]
    total_tokens_used: int
    estimated_tokens_saved: int


@router.post("/event", response_model=Dict[str, str])
async def collect_event(event: VscodeEvent):
    """
    Collect VSCode extension telemetry event

    This endpoint receives telemetry events from VSCode AI extensions and stores them
    in a JSONL file for analysis and dashboard display.
    """
    try:
        # Auto-generate timestamp if not provided
        if not event.timestamp:
            event.timestamp = datetime.utcnow()

        # Convert to dict for JSON serialization
        event_dict = event.model_dump()
        event_dict['timestamp'] = event.timestamp.isoformat()

        # Append to JSONL file
        with open(TELEMETRY_FILE, "a") as f:
            f.write(json.dumps(event_dict) + "\n")

        return {"status": "recorded", "timestamp": event_dict['timestamp']}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to record event: {str(e)}")


@router.get("/stats", response_model=TelemetryStats)
async def get_stats():
    """
    Get VSCode telemetry statistics

    Analyzes all recorded telemetry events and returns aggregate statistics including
    local vs remote usage, success rates, and extension-specific metrics.
    """
    try:
        if not TELEMETRY_FILE.exists():
            # Return empty stats if no telemetry yet
            return TelemetryStats(
                total_events=0,
                local_usage_pct=0.0,
                remote_usage_pct=0.0,
                avg_latency_ms=0.0,
                success_rate=0.0,
                events_by_extension={},
                events_by_type={},
                total_tokens_used=0,
                estimated_tokens_saved=0
            )

        # Read all events
        events = []
        with open(TELEMETRY_FILE, "r") as f:
            for line in f:
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue  # Skip malformed lines

        if not events:
            return TelemetryStats(
                total_events=0,
                local_usage_pct=0.0,
                remote_usage_pct=0.0,
                avg_latency_ms=0.0,
                success_rate=0.0,
                events_by_extension={},
                events_by_type={},
                total_tokens_used=0,
                estimated_tokens_saved=0
            )

        # Calculate statistics
        total_events = len(events)
        local_events = [e for e in events if e.get("is_local", False)]
        remote_events = [e for e in events if not e.get("is_local", False)]

        local_usage_pct = (len(local_events) / total_events * 100) if total_events > 0 else 0.0
        remote_usage_pct = (len(remote_events) / total_events * 100) if total_events > 0 else 0.0

        # Average latency
        latencies = [e.get("latency_ms", 0) for e in events if e.get("latency_ms") is not None]
        avg_latency_ms = sum(latencies) / len(latencies) if latencies else 0.0

        # Success rate
        successful = sum(1 for e in events if e.get("success", False))
        success_rate = (successful / total_events * 100) if total_events > 0 else 0.0

        # Events by extension
        events_by_extension = {}
        for event in events:
            ext = event.get("extension", "unknown")
            events_by_extension[ext] = events_by_extension.get(ext, 0) + 1

        # Events by type
        events_by_type = {}
        for event in events:
            etype = event.get("event_type", "unknown")
            events_by_type[etype] = events_by_type.get(etype, 0) + 1

        # Token usage
        total_tokens_used = sum(e.get("tokens_used", 0) for e in events if e.get("tokens_used"))

        # Estimated tokens saved (assume remote would use 2x tokens)
        local_tokens = sum(e.get("tokens_used", 0) for e in local_events if e.get("tokens_used"))
        estimated_tokens_saved = local_tokens  # Tokens that would have been sent to remote API

        return TelemetryStats(
            total_events=total_events,
            local_usage_pct=round(local_usage_pct, 2),
            remote_usage_pct=round(remote_usage_pct, 2),
            avg_latency_ms=round(avg_latency_ms, 2),
            success_rate=round(success_rate, 2),
            events_by_extension=events_by_extension,
            events_by_type=events_by_type,
            total_tokens_used=total_tokens_used,
            estimated_tokens_saved=estimated_tokens_saved
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to calculate stats: {str(e)}")


@router.get("/recent", response_model=List[Dict[str, Any]])
async def get_recent_events(limit: int = Query(100, ge=1, le=1000)):
    """
    Get recent VSCode telemetry events

    Returns the most recent N telemetry events for debugging and monitoring.
    """
    try:
        if not TELEMETRY_FILE.exists():
            return []

        # Read all events and return last N
        events = []
        with open(TELEMETRY_FILE, "r") as f:
            for line in f:
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

        # Return most recent events
        return events[-limit:] if events else []

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch recent events: {str(e)}")


@router.delete("/clear", response_model=Dict[str, str])
async def clear_telemetry():
    """
    Clear all VSCode telemetry events

    ⚠️ WARNING: This deletes all recorded telemetry data. Use only for testing.
    """
    try:
        if TELEMETRY_FILE.exists():
            # Backup before clearing
            backup_file = TELEMETRY_DIR / f"vscode-events-backup-{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
            TELEMETRY_FILE.rename(backup_file)

            # Create new empty file
            TELEMETRY_FILE.touch()

            return {
                "status": "cleared",
                "backup": str(backup_file),
                "message": "All telemetry cleared and backed up"
            }
        else:
            return {"status": "already_empty", "message": "No telemetry data to clear"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear telemetry: {str(e)}")


@router.get("/health", response_model=Dict[str, Any])
async def telemetry_health():
    """
    Check VSCode telemetry system health

    Returns status information about the telemetry collection system.
    """
    try:
        file_exists = TELEMETRY_FILE.exists()
        file_size = TELEMETRY_FILE.stat().st_size if file_exists else 0

        # Count events
        event_count = 0
        if file_exists:
            with open(TELEMETRY_FILE, "r") as f:
                event_count = sum(1 for _ in f)

        return {
            "status": "healthy" if file_exists else "not_initialized",
            "telemetry_file": str(TELEMETRY_FILE),
            "file_size_bytes": file_size,
            "total_events": event_count,
            "collection_enabled": True,
            "storage_path": str(TELEMETRY_DIR)
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


@router.get("/export", response_model=Dict[str, str])
async def export_telemetry(format: str = Query("jsonl", regex="^(jsonl|csv|json)$")):
    """
    Export telemetry data in various formats

    Supports: jsonl (default), csv, json
    """
    try:
        if not TELEMETRY_FILE.exists():
            raise HTTPException(status_code=404, detail="No telemetry data available")

        export_file = TELEMETRY_DIR / f"vscode-telemetry-export-{datetime.now().strftime('%Y%m%d_%H%M%S')}.{format}"

        if format == "jsonl":
            # Just copy the file
            import shutil
            shutil.copy(TELEMETRY_FILE, export_file)

        elif format == "json":
            # Convert JSONL to JSON array
            events = []
            with open(TELEMETRY_FILE, "r") as f:
                for line in f:
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

            with open(export_file, "w") as f:
                json.dump(events, f, indent=2)

        elif format == "csv":
            # Convert to CSV
            import csv
            events = []
            with open(TELEMETRY_FILE, "r") as f:
                for line in f:
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

            if events:
                # Get all unique keys
                all_keys = set()
                for event in events:
                    all_keys.update(event.keys())

                with open(export_file, "w", newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=sorted(all_keys))
                    writer.writeheader()
                    writer.writerows(events)

        return {
            "status": "exported",
            "file": str(export_file),
            "format": format,
            "message": f"Telemetry data exported to {export_file}"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to export: {str(e)}")
