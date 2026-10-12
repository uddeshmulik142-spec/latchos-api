from fastapi import APIRouter, Depends, HTTPException, status

from app.database import fetch_rows
from app.dependencies import check_rate_limit, verify_api_key

router = APIRouter(prefix="/api/v1", tags=["events"])


@router.get(
    "/gate-events",
    dependencies=[Depends(verify_api_key), Depends(check_rate_limit)],
)
async def get_gate_events():
    try:
        rows = await fetch_rows(
            "SELECT id, driver_name, license_number, compliance_status, scan_time "
            "FROM gate_events ORDER BY scan_time DESC LIMIT 50"
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
        return {"events": events}

    except Exception as exc:
        print(f"⚠️ Failed to retrieve gate events: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve gate events.",
        ) from exc
