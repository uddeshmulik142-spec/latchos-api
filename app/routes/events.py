from fastapi import APIRouter, Depends, HTTPException, status

from app.config import DATABASE_URL
from app.database import fetch_rows
from app.dependencies import check_rate_limit, resolve_organization
from app.models import Organization

router = APIRouter(prefix="/api/v1", tags=["events"])


@router.get(
    "/gate-events",
    dependencies=[Depends(check_rate_limit)],
)
async def get_gate_events(org: Organization = Depends(resolve_organization)):
    # Graceful degradation if DATABASE_URL is not configured (e.g. offline unit testing)
    if not DATABASE_URL:
        return {
            "depot_name": org.name,
            "depot_slug": org.slug,
            "events": [],
        }

    try:
        # Fetch events strictly scoped to this organization
        # Also include unassigned legacy events (org_id IS NULL) for the default Main Depot (id: 1)
        if org.id == 1:
            rows = await fetch_rows(
                "SELECT id, driver_name, license_number, compliance_status, scan_time "
                "FROM gate_events WHERE org_id = $1 OR org_id IS NULL "
                "ORDER BY scan_time DESC LIMIT 100",
                org.id,
            )
        else:
            rows = await fetch_rows(
                "SELECT id, driver_name, license_number, compliance_status, scan_time "
                "FROM gate_events WHERE org_id = $1 "
                "ORDER BY scan_time DESC LIMIT 100",
                org.id,
            )

        events = [
            {
                "id": row.get("id"),
                "driver_name": row.get("driver_name"),
                "licence_number": row.get("license_number"),
                "status": row.get("compliance_status"),
                "timestamp": row.get("scan_time").isoformat() if row.get("scan_time") else None,
            }
            for row in rows
        ]
        return {
            "depot_name": org.name,
            "depot_slug": org.slug,
            "events": events,
        }

    except Exception as exc:
        print(f"⚠️ Failed to retrieve gate events: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve gate events.",
        ) from exc
