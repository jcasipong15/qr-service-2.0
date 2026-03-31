"""
security.py — API Key auth, per-key rate limiting, and IP allowlist.
All settings are controlled via environment variables (see .env.example).
"""
import logging
import os
import time
from collections import deque
from typing import Deque

from fastapi import HTTPException, Request, Security
from fastapi.security import APIKeyHeader
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config — loaded from environment (set in .env)
# ---------------------------------------------------------------------------

def _get_api_keys() -> set[str]:
    """Comma-separated list of valid API keys. Empty = auth disabled."""
    raw = os.getenv("API_KEYS", "")
    return {k.strip() for k in raw.split(",") if k.strip()}

def _get_allowed_ips() -> set[str]:
    """Comma-separated allowed IPs. Empty = allow all."""
    raw = os.getenv("ALLOWED_IPS", "")
    return {ip.strip() for ip in raw.split(",") if ip.strip()}

def _rate_limit_config() -> tuple[int, int]:
    """Returns (max_requests, window_seconds). Defaults: 60 req / 60s."""
    return (
        int(os.getenv("RATE_LIMIT_REQUESTS", "60")),
        int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60")),
    )


# ---------------------------------------------------------------------------
# IP Allowlist Middleware
# ---------------------------------------------------------------------------

class IPAllowlistMiddleware(BaseHTTPMiddleware):
    """Block requests from IPs not in ALLOWED_IPS. If list is empty, allows all."""

    async def dispatch(self, request: Request, call_next):
        allowed = _get_allowed_ips()
        if allowed:
            client_ip = request.client.host if request.client else "unknown"
            # Also check X-Forwarded-For for reverse proxy setups
            forwarded = request.headers.get("X-Forwarded-For")
            if forwarded:
                client_ip = forwarded.split(",")[0].strip()
            if client_ip not in allowed:
                logger.warning("Blocked request from unauthorized IP: %s", client_ip)
                return JSONResponse(
                    status_code=403,
                    content={"detail": f"IP address not allowed: {client_ip}"},
                )
        return await call_next(request)


# ---------------------------------------------------------------------------
# Rate Limiter — sliding window per API key (or IP if auth disabled)
# ---------------------------------------------------------------------------

# {identifier: deque of request timestamps}
_rate_store: dict[str, Deque[float]] = {}


def _check_rate_limit(identifier: str) -> None:
    max_req, window = _rate_limit_config()
    now = time.monotonic()
    cutoff = now - window

    if identifier not in _rate_store:
        _rate_store[identifier] = deque()

    window_deque = _rate_store[identifier]

    # Evict timestamps outside the current window
    while window_deque and window_deque[0] < cutoff:
        window_deque.popleft()

    if len(window_deque) >= max_req:
        retry_after = int(window - (now - window_deque[0])) + 1
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded: {max_req} requests per {window}s. Retry after {retry_after}s.",
            headers={"Retry-After": str(retry_after)},
        )

    window_deque.append(now)


# ---------------------------------------------------------------------------
# API Key Dependency
# ---------------------------------------------------------------------------

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_api_key(request: Request, api_key: str | None = Security(_api_key_header)) -> str:
    """
    FastAPI dependency. Call this on any protected route.
    - If API_KEYS env var is empty: auth is disabled (open, dev mode).
    - Otherwise: validates the X-API-Key header.
    - Always applies rate limiting (by key or by IP).
    """
    valid_keys = _get_api_keys()

    if valid_keys:
        key = request.headers.get("X-API-Key")
        if not key or key not in valid_keys:
            raise HTTPException(
                status_code=401,
                detail="Invalid or missing API key. Pass it as X-API-Key header.",
                headers={"WWW-Authenticate": "ApiKey"},
            )
        identifier = f"key:{key}"
    else:
        # Auth disabled — rate limit by IP
        client_ip = request.client.host if request.client else "unknown"
        identifier = f"ip:{client_ip}"

    _check_rate_limit(identifier)
    return identifier
