"""
Keycloak MCP Server

A Python MCP server for managing Keycloak identity and access management.
Supports both stdio and HTTP transports.
"""

import os
import sys
import uvicorn
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from .common.server import mcp

# Import all tool modules to register them with the MCP server
from . import tools  # noqa: F401
from .tools import user_tools  # noqa: F401
from .tools import client_tools  # noqa: F401
from .tools import realm_tools  # noqa: F401
from .tools import role_tools  # noqa: F401
from .tools import group_tools  # noqa: F401

class OriginValidationMiddleware(BaseHTTPMiddleware):
    """Middleware to validate Origin header to prevent DNS rebinding attacks"""
    
    def __init__(self, app, allowed_origins=None):
        super().__init__(app)
        # Default to localhost origins for security
        self.allowed_origins = allowed_origins or {
            "http://localhost:8000",
            "http://127.0.0.1:8000",
            "null",  # For file:// origins in development
        }
    
    async def dispatch(self, request, call_next):
        # Skip validation for preflight OPTIONS requests
        if request.method == "OPTIONS":
            return await call_next(request)
        
        origin = request.headers.get("origin")
        
        # If no Origin header, allow (some clients don't send it)
        if not origin:
            return await call_next(request)
        
        # Validate origin against allowed list
        if origin not in self.allowed_origins:
            print(f"Blocked request from unauthorized origin: {origin}", file=sys.stderr)
            return Response(
                content="Forbidden: Invalid origin",
                status_code=403,
                headers={"Content-Type": "text/plain"}
            )
        
        return await call_next(request)


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """Simple authentication middleware for MCP server"""
    
    def __init__(self, app, auth_token=None):
        super().__init__(app)
        self.auth_token = auth_token
    
    async def dispatch(self, request, call_next):
        # Skip auth for OPTIONS requests
        if request.method == "OPTIONS":
            return await call_next(request)
        
        # If no auth token configured, skip authentication
        if not self.auth_token:
            return await call_next(request)
        
        # Check for Authorization header
        auth_header = request.headers.get("authorization")
        if not auth_header:
            return Response(
                content="Unauthorized: Missing Authorization header",
                status_code=401,
                headers={"Content-Type": "text/plain"}
            )
        
        # Validate bearer token
        if not auth_header.startswith("Bearer ") or auth_header[7:] != self.auth_token:
            return Response(
                content="Unauthorized: Invalid token",
                status_code=401,
                headers={"Content-Type": "text/plain"}
            )
        
        return await call_next(request)


def main():
    transport_mode = os.getenv("TRANSPORT", "stdio")
    
    if transport_mode == "http":
        print("Keycloak MCP Server starting in HTTP mode...", file=sys.stderr)
        
        # Create Starlette app with streamable HTTP
        app = mcp.streamable_http_app()
        
        # Get configuration from environment
        port = int(os.environ.get("PORT", 8000))
        # Check both MCP_AUTH_TOKEN and AUTH_TOKEN for compatibility with Smithery
        auth_token = os.environ.get("MCP_AUTH_TOKEN") or os.environ.get("AUTH_TOKEN")
        
        # Add security middleware (ORDER MATTERS)
        # 1. Authentication middleware (optional)
        if auth_token:
            print("Authentication enabled", file=sys.stderr)
            app.add_middleware(AuthenticationMiddleware, auth_token=auth_token)
        else:
            print("No authentication configured (set MCP_AUTH_TOKEN to enable)", file=sys.stderr)
        
        # 2. Origin validation middleware (REQUIRED by MCP spec)
        allowed_origins = {
            f"http://localhost:{port}",
            f"http://127.0.0.1:{port}",
            "null",  # For file:// origins
        }
        app.add_middleware(OriginValidationMiddleware, allowed_origins=allowed_origins)
        
        # 3. CORS middleware for browser-based clients
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[f"http://localhost:{port}", f"http://127.0.0.1:{port}"],
            allow_credentials=True,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["*"],
            expose_headers=["mcp-session-id", "mcp-protocol-version"],
            max_age=86400,
        )
        
        print(f"Listening on http://127.0.0.1:{port}/mcp/", file=sys.stderr)
        
        # Run with uvicorn
        uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
    
    else:
        # stdio mode (default)
        print("Keycloak MCP Server starting in stdio mode...", file=sys.stderr)
        
        # Run with stdio transport
        mcp.run()


if __name__ == "__main__":
    main()