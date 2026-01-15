"""
API Token Authentication Middleware.

Protects /v1/* routes with Bearer token authentication.
Public endpoints (/health, /version, /api/*) are not protected.
"""

import logging
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from atlas.config import get_settings

logger = logging.getLogger(__name__)


class APITokenMiddleware(BaseHTTPMiddleware):
    """
    Middleware that enforces API token authentication for /v1/* routes.
    
    - Requires Authorization: Bearer <API_TOKEN> header
    - Skips authentication for public endpoints
    - Returns 401 Unauthorized if token is missing or invalid
    """

    # Paths that don't require authentication
    PUBLIC_PATHS = frozenset([
        "/health",
        "/version",
        "/docs",
        "/openapi.json",
        "/redoc",
    ])

    # Path prefixes that don't require authentication
    PUBLIC_PREFIXES = (
        "/api/",  # Legacy API endpoints (optional: remove if you want to protect these too)
    )

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process the request and check authentication for protected routes."""
        path = request.url.path
        
        # Check if path is public
        if self._is_public_path(path):
            return await call_next(request)
        
        # Check if path requires authentication (only /v1/* routes)
        if not path.startswith("/v1"):
            return await call_next(request)
        
        # Get settings
        settings = get_settings()
        
        # If no API token configured, allow all requests (dev mode)
        if not settings.api_token:
            return await call_next(request)
        
        # Validate Authorization header
        auth_header = request.headers.get("Authorization")
        
        if not auth_header:
            logger.warning(f"Missing Authorization header for {path}")
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing Authorization header"},
            )
        
        # Check Bearer token format
        if not auth_header.startswith("Bearer "):
            logger.warning(f"Invalid Authorization format for {path}")
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid Authorization format. Use: Bearer <token>"},
            )
        
        # Extract and validate token
        token = auth_header[7:]  # Remove "Bearer " prefix
        
        if token != settings.api_token:
            logger.warning(f"Invalid API token for {path}")
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid API token"},
            )
        
        # Token is valid, proceed with request
        return await call_next(request)

    def _is_public_path(self, path: str) -> bool:
        """Check if path is public (no auth required)."""
        if path in self.PUBLIC_PATHS:
            return True
        
        for prefix in self.PUBLIC_PREFIXES:
            if path.startswith(prefix):
                return True
        
        return False
