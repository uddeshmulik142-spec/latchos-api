import time
from collections import defaultdict
from typing import Optional

from fastapi import Header, HTTPException, Query, Request, status

from app.config import RATE_LIMIT_PER_MINUTE
from app.database import fetch_rows
from app.models import Organization

# Per-client sliding window rate limiter: client_id -> list of request timestamps
_rate_limit_records: dict[str, list[float]] = defaultdict(list)


async def check_rate_limit(request: Request) -> None:
    """Sliding-window rate limiter per client IP address."""
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    window_start = now - 60.0

    # Prune timestamps older than 60 seconds
    timestamps = [t for t in _rate_limit_records[client_ip] if t > window_start]
    _rate_limit_records[client_ip] = timestamps

    if len(timestamps) >= RATE_LIMIT_PER_MINUTE:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Maximum {RATE_LIMIT_PER_MINUTE} requests per minute.",
        )

    _rate_limit_records[client_ip].append(now)


async def resolve_organization(
    x_depot_key: Optional[str] = Header(None, alias="X-Depot-Key"),
    depot_key: Optional[str] = Query(None, alias="key"),
) -> Organization:
    """Resolve the active depot organization from header or query param.

    Falls back to the default Demo Organization (ID: 1) if no key is provided,
    ensuring single-depot demos work out of the box without requiring manual setup.
    """
    token = x_depot_key or depot_key

    if token:
        try:
            rows = await fetch_rows(
                "SELECT id, name, slug, access_key, created_at FROM organizations WHERE access_key = $1 LIMIT 1",
                token.strip(),
            )
            if rows:
                r = rows[0]
                return Organization(
                    id=r["id"],
                    name=r["name"],
                    slug=r["slug"],
                    access_key=r["access_key"],
                    created_at=r.get("created_at"),
                )
            # If a token was provided but not found, return unauthorized
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid depot access key.",
            )
        except HTTPException:
            raise
        except Exception as exc:
            print(f"⚠️ Organization resolution DB error: {exc}")

    # Default to Main Demo Depot (ID 1)
    return Organization(
        id=1,
        name="Main Depot",
        slug="main-depot",
        access_key="demo-depot-2026",
    )
