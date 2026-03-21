"""
dashboard/backend/api/routes/adk.py

Purpose: Google ADK integration API endpoints for dashboard

Status: production
Owner: ai-harness
Last Updated: 2026-03-20

Features:
- GET /api/adk/parity - Get current parity status
- GET /api/adk/discoveries - List recent ADK feature discoveries
- GET /api/adk/integrations - List adopted/adapted/deferred integrations
- GET /api/adk/gaps - List capability gaps
- POST /api/adk/discovery/trigger - Trigger manual discovery
- GET /api/adk/roadmap-impact - Show roadmap items from ADK discoveries
"""

from fastapi import APIRouter, HTTPException, Response, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
import logging
import json
import subprocess
import os
from datetime import datetime, timedelta
from pathlib import Path

router = APIRouter()
logger = logging.getLogger(__name__)

# Declarative paths
REPO_ROOT = Path(os.getenv('REPO_ROOT', '/etc/nixos'))
ADK_DATA_DIR = REPO_ROOT / '.agent' / 'adk'
ADK_REPORTS_DIR = ADK_DATA_DIR / 'reports'
ADK_DISCOVERIES_DIR = ADK_DATA_DIR / 'discoveries'
LIB_ADK_DIR = REPO_ROOT / 'lib' / 'adk'

# Cache for parity data
_PARITY_CACHE: Dict[str, Any] = {"ts": 0.0, "payload": {}}
_DISCOVERIES_CACHE: Dict[str, Any] = {"ts": 0.0, "payload": []}
CACHE_TTL = 300  # 5 minutes


class ParityStatusResponse(BaseModel):
    """Parity status response model."""
    overall_parity: float = Field(..., description="Overall parity score (0-1)")
    generated_at: str = Field(..., description="Timestamp of parity calculation")
    adk_version: str = Field(..., description="ADK version tracked")
    harness_version: str = Field(..., description="Harness version")
    categories: Dict[str, Any] = Field(..., description="Category-level parity")


class DiscoveryResponse(BaseModel):
    """Discovery response model."""
    discovered_at: str = Field(..., description="Discovery timestamp")
    total_features: int = Field(..., description="Total features discovered")
    releases_analyzed: int = Field(..., description="Number of releases analyzed")
    discoveries: List[Dict[str, Any]] = Field(..., description="Discovery details")


class IntegrationResponse(BaseModel):
    """Integration status response model."""
    adopted: List[Dict[str, Any]] = Field(..., description="Adopted integrations")
    adapted: List[Dict[str, Any]] = Field(..., description="Adapted integrations")
    deferred: List[Dict[str, Any]] = Field(..., description="Deferred integrations")
    not_applicable: List[Dict[str, Any]] = Field(..., description="Not applicable")


class GapResponse(BaseModel):
    """Capability gap response model."""
    total_gaps: int = Field(..., description="Total capability gaps")
    high_priority: int = Field(..., description="High priority gaps")
    medium_priority: int = Field(..., description="Medium priority gaps")
    low_priority: int = Field(..., description="Low priority gaps")
    gaps: List[Dict[str, Any]] = Field(..., description="Gap details")


class RoadmapImpactResponse(BaseModel):
    """Roadmap impact response model."""
    high_priority_items: List[Dict[str, Any]] = Field(..., description="High priority roadmap items")
    medium_priority_items: List[Dict[str, Any]] = Field(..., description="Medium priority items")
    estimated_effort: str = Field(..., description="Estimated effort")


def load_parity_scorecard() -> Dict[str, Any]:
    """Load parity scorecard from file."""
    scorecard_file = ADK_DATA_DIR / 'parity-scorecard.json'

    if not scorecard_file.exists():
        # Generate scorecard if it doesn't exist
        logger.info("Parity scorecard not found, generating...")
        try:
            subprocess.run(
                [str(LIB_ADK_DIR / 'parity-tracker.py'), '--data-dir', str(ADK_DATA_DIR)],
                check=True,
                capture_output=True,
                timeout=30
            )
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to generate parity scorecard: {e}")
            return {}
        except subprocess.TimeoutExpired:
            logger.error("Parity tracker timed out")
            return {}

    try:
        with open(scorecard_file, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load parity scorecard: {e}")
        return {}


def load_latest_discoveries() -> Dict[str, Any]:
    """Load latest discovery data."""
    # Find most recent discovery file
    if not ADK_DISCOVERIES_DIR.exists():
        return {}

    discovery_files = sorted(ADK_DISCOVERIES_DIR.glob('features-*.json'), reverse=True)

    if not discovery_files:
        return {}

    try:
        with open(discovery_files[0], 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load discoveries: {e}")
        return {}


def load_latest_gaps() -> Dict[str, Any]:
    """Load latest capability gaps."""
    if not ADK_REPORTS_DIR.exists():
        return {}

    gap_files = sorted(ADK_REPORTS_DIR.glob('capability-gaps-*.json'), reverse=True)

    if not gap_files:
        return {}

    try:
        with open(gap_files[0], 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load gaps: {e}")
        return {}


@router.get("/api/adk/parity", response_model=ParityStatusResponse)
async def get_parity_status():
    """
    Get current ADK parity status.

    Returns overall parity score and category breakdowns.
    """
    global _PARITY_CACHE

    # Check cache
    now = datetime.now().timestamp()
    if _PARITY_CACHE["ts"] > 0 and (now - _PARITY_CACHE["ts"]) < CACHE_TTL:
        return _PARITY_CACHE["payload"]

    # Load fresh data
    scorecard = load_parity_scorecard()

    if not scorecard:
        raise HTTPException(status_code=503, detail="Parity scorecard not available")

    response = ParityStatusResponse(
        overall_parity=scorecard.get('overall_parity', 0.0),
        generated_at=scorecard.get('generated_at', datetime.now().isoformat()),
        adk_version=scorecard.get('adk_version', 'unknown'),
        harness_version=scorecard.get('harness_version', 'unknown'),
        categories=scorecard.get('categories', {})
    )

    # Update cache
    _PARITY_CACHE["ts"] = now
    _PARITY_CACHE["payload"] = response

    return response


@router.get("/api/adk/discoveries", response_model=DiscoveryResponse)
async def get_discoveries():
    """
    List recent ADK feature discoveries.

    Returns features extracted from ADK releases.
    """
    global _DISCOVERIES_CACHE

    # Check cache
    now = datetime.now().timestamp()
    if _DISCOVERIES_CACHE["ts"] > 0 and (now - _DISCOVERIES_CACHE["ts"]) < CACHE_TTL:
        return _DISCOVERIES_CACHE["payload"]

    # Load fresh data
    discoveries = load_latest_discoveries()

    if not discoveries:
        # Return empty response
        return DiscoveryResponse(
            discovered_at=datetime.now().isoformat(),
            total_features=0,
            releases_analyzed=0,
            discoveries=[]
        )

    response = DiscoveryResponse(
        discovered_at=discoveries.get('discovered_at', datetime.now().isoformat()),
        total_features=discoveries.get('features_found', 0),
        releases_analyzed=discoveries.get('releases_analyzed', 0),
        discoveries=discoveries.get('discoveries', [])
    )

    # Update cache
    _DISCOVERIES_CACHE["ts"] = now
    _DISCOVERIES_CACHE["payload"] = response

    return response


@router.get("/api/adk/integrations", response_model=IntegrationResponse)
async def get_integrations():
    """
    List ADK integrations by status.

    Returns adopted, adapted, deferred, and not applicable integrations.
    """
    scorecard = load_parity_scorecard()

    if not scorecard:
        raise HTTPException(status_code=503, detail="Integration data not available")

    adopted = []
    adapted = []
    deferred = []
    not_applicable = []

    # Extract capabilities by status
    for category_name, category_data in scorecard.get('categories', {}).items():
        for capability in category_data.get('capabilities', []):
            cap_info = {
                'name': capability['name'],
                'description': capability['description'],
                'category': category_name,
                'priority': capability['priority'],
                'notes': capability.get('notes', ''),
                'harness_equivalent': capability.get('harness_equivalent')
            }

            status = capability['status']
            if status == 'adopted':
                adopted.append(cap_info)
            elif status == 'adapted':
                adapted.append(cap_info)
            elif status == 'deferred':
                deferred.append(cap_info)
            elif status == 'not_applicable':
                not_applicable.append(cap_info)

    return IntegrationResponse(
        adopted=adopted,
        adapted=adapted,
        deferred=deferred,
        not_applicable=not_applicable
    )


@router.get("/api/adk/gaps", response_model=GapResponse)
async def get_gaps():
    """
    List capability gaps.

    Returns identified gaps between ADK and harness capabilities.
    """
    gaps_data = load_latest_gaps()

    if not gaps_data:
        return GapResponse(
            total_gaps=0,
            high_priority=0,
            medium_priority=0,
            low_priority=0,
            gaps=[]
        )

    return GapResponse(
        total_gaps=gaps_data.get('total_gaps', 0),
        high_priority=gaps_data.get('high_priority', 0),
        medium_priority=gaps_data.get('medium_priority', 0),
        low_priority=gaps_data.get('low_priority', 0),
        gaps=gaps_data.get('gaps', [])
    )


@router.post("/api/adk/discovery/trigger")
async def trigger_discovery(background_tasks: BackgroundTasks):
    """
    Trigger manual ADK discovery.

    Runs discovery workflow in background.
    """
    def run_discovery():
        """Background task to run discovery."""
        try:
            discovery_script = LIB_ADK_DIR / 'implementation-discovery.sh'

            if not discovery_script.exists():
                logger.error(f"Discovery script not found: {discovery_script}")
                return

            result = subprocess.run(
                [str(discovery_script), '--force'],
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes
            )

            if result.returncode == 0:
                logger.info("ADK discovery completed successfully")
                # Invalidate caches
                global _PARITY_CACHE, _DISCOVERIES_CACHE
                _PARITY_CACHE = {"ts": 0.0, "payload": {}}
                _DISCOVERIES_CACHE = {"ts": 0.0, "payload": []}
            else:
                logger.error(f"Discovery failed: {result.stderr}")

        except subprocess.TimeoutExpired:
            logger.error("Discovery timed out")
        except Exception as e:
            logger.error(f"Discovery error: {e}")

    background_tasks.add_task(run_discovery)

    return {
        "status": "triggered",
        "message": "ADK discovery workflow started in background",
        "timestamp": datetime.now().isoformat()
    }


@router.get("/api/adk/roadmap-impact", response_model=RoadmapImpactResponse)
async def get_roadmap_impact():
    """
    Show roadmap impact from ADK discoveries.

    Returns high-impact items that should be added to roadmap.
    """
    gaps_data = load_latest_gaps()

    if not gaps_data:
        return RoadmapImpactResponse(
            high_priority_items=[],
            medium_priority_items=[],
            estimated_effort="unknown"
        )

    high_priority = [
        {
            'feature': gap['feature'],
            'priority': gap['priority'],
            'release': gap['release'],
            'url': gap.get('url', ''),
            'recommended_action': 'Evaluate for immediate integration'
        }
        for gap in gaps_data.get('gaps', [])
        if gap['priority'] == 'high'
    ]

    medium_priority = [
        {
            'feature': gap['feature'],
            'priority': gap['priority'],
            'release': gap['release'],
            'recommended_action': 'Add to backlog for next sprint'
        }
        for gap in gaps_data.get('gaps', [])
        if gap['priority'] == 'medium'
    ][:5]  # Top 5 medium priority

    # Simple effort estimation
    total_items = len(high_priority) + len(medium_priority)
    if total_items == 0:
        effort = "none"
    elif total_items <= 3:
        effort = "1-2 sprints"
    elif total_items <= 6:
        effort = "2-3 sprints"
    else:
        effort = "3+ sprints"

    return RoadmapImpactResponse(
        high_priority_items=high_priority,
        medium_priority_items=medium_priority,
        estimated_effort=effort
    )


@router.get("/api/adk/status")
async def get_status():
    """
    Get ADK integration health status.

    Returns overall health and data freshness.
    """
    scorecard_file = ADK_DATA_DIR / 'parity-scorecard.json'
    discoveries_file = sorted(ADK_DISCOVERIES_DIR.glob('features-*.json'), reverse=True)
    gaps_file = sorted(ADK_REPORTS_DIR.glob('capability-gaps-*.json'), reverse=True)

    status = {
        'healthy': True,
        'components': {
            'parity_tracker': {
                'available': scorecard_file.exists(),
                'last_updated': None
            },
            'discovery': {
                'available': len(discoveries_file) > 0,
                'last_run': None
            },
            'gap_analysis': {
                'available': len(gaps_file) > 0,
                'last_run': None
            }
        }
    }

    # Check file ages
    if scorecard_file.exists():
        mtime = scorecard_file.stat().st_mtime
        status['components']['parity_tracker']['last_updated'] = datetime.fromtimestamp(mtime).isoformat()

    if discoveries_file:
        mtime = discoveries_file[0].stat().st_mtime
        status['components']['discovery']['last_run'] = datetime.fromtimestamp(mtime).isoformat()

    if gaps_file:
        mtime = gaps_file[0].stat().st_mtime
        status['components']['gap_analysis']['last_run'] = datetime.fromtimestamp(mtime).isoformat()

    # Check if any component is stale (>7 days)
    now = datetime.now().timestamp()
    stale_threshold = 7 * 24 * 3600  # 7 days

    for component_name, component in status['components'].items():
        if component['available']:
            if component_name == 'parity_tracker':
                last_time = scorecard_file.stat().st_mtime
            elif component_name == 'discovery':
                last_time = discoveries_file[0].stat().st_mtime if discoveries_file else 0
            else:
                last_time = gaps_file[0].stat().st_mtime if gaps_file else 0

            if (now - last_time) > stale_threshold:
                status['healthy'] = False
                component['stale'] = True

    return status
