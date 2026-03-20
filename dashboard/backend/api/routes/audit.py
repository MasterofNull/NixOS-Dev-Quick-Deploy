#!/usr/bin/env python3
"""Operator audit trail routes."""

from fastapi import APIRouter

from api.services.runtime_controls import get_operator_audit_log

router = APIRouter()
audit_log = get_operator_audit_log()


@router.get("/audit/operator/summary")
async def get_operator_audit_summary(limit: int = 500):
    return audit_log.summary(limit=limit)


@router.get("/audit/operator/events")
async def get_operator_audit_events(
    limit: int = 100,
    path_prefix: str = "",
    method: str = "",
    status_code: int | None = None,
    category: str = "",
    contains: str = "",
):
    return {
        "path": str(audit_log.path()),
        "filters": {
            "path_prefix": path_prefix,
            "method": method,
            "status_code": status_code,
            "category": category,
            "contains": contains,
        },
        "events": audit_log.query_events(
            limit=limit,
            path_prefix=path_prefix,
            method=method,
            status_code=status_code,
            category=category,
            contains=contains,
        ),
    }


@router.get("/audit/operator/integrity")
async def get_operator_audit_integrity(limit: int = 500):
    return audit_log.integrity_status(limit=limit)
