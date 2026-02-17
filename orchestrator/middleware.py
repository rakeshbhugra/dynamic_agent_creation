"""
DynamicMCPMiddleware — intercepts /mcp/{slug} requests and dispatches
to the lazily-started FastMCP session for that agent.
"""

import structlog
from starlette.types import ASGIApp, Receive, Scope, Send

from orchestrator.registry import ensure_agent

log = structlog.get_logger(__name__)


class DynamicMCPMiddleware:
    def __init__(self, app: ASGIApp):
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            path: str = scope["path"]
            if path.startswith("/mcp/"):
                # path = /mcp/{slug}  or  /mcp/{slug}/rest
                parts = path.split("/", 3)  # ['', 'mcp', slug, rest?]
                slug = parts[2] if len(parts) > 2 else ""
                if slug:
                    handler = await ensure_agent(slug)
                    if handler is not None:
                        # Strip /mcp/{slug} so the sub-app sees "/"
                        stripped = f"/{parts[3]}" if len(parts) > 3 and parts[3] else "/"
                        new_scope = {**scope, "path": stripped, "raw_path": stripped.encode()}
                        log.debug("mcp_request_dispatched", slug=slug, original_path=path)
                        await handler(new_scope, receive, send)
                        return

        await self._app(scope, receive, send)
