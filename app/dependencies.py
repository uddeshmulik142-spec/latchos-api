import time
from collections import defaultdict

from fastapi import Header, HTTPException, status

from app.config import API_KEY, RATE_LIMIT_PER_MINUTE

# Simple in-memory rate limiter: IP/token -> list of request timestamps
_rate_limit_records: dict[str, list[float]] = defaultdict(list)


async def verify_api_key(x_api_key: str | None = Header(None)) -> str | None:
    """Validate API key if one is configured in environment."""
    if not API_KEY:
        return None  # No auth required if API_KEY is unset
    if x_api_key != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key.",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return x_api_key


async def check_rate_limit(client_id: str = "global") -> None:
    """Sliding window in-memory rate limiter."""
    now = time.time()
    window_start = now - 60.0

    # Prune old entries
    timestamps = [t for t in _rate_limit_records[client_id] if t > window_start]
    _rate_limit_records[client_id] = timestamps

    if len(timestamps) >= RATE_LIMIT_PER_MINUTE:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Maximum {RATE_LIMIT_PER_MINUTE} requests per minute.",
        )

    _rate_limit_records[client_id].append(now)
