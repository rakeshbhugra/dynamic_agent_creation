"""
Agent registry: builds and lazily starts FastMCP instances per slug.

_build_agent_mcp  — creates a FastMCP with only the allowlisted tools
_ensure_agent     — get-or-create the ASGI handler for a slug (thread-safe)
"""

import asyncio
import contextlib

import structlog
from mcp.server.fastmcp import FastMCP
from starlette.types import ASGIApp

from orchestrator.config import AgentConfig, get_config
from orchestrator.tools import (
    create_patient,
    delete_patient,
    get_patient,
    list_patients,
    update_patient,
)

log = structlog.get_logger(__name__)

TOOL_REGISTRY: dict = {
    "list_patients": list_patients,
    "get_patient": get_patient,
    "create_patient": create_patient,
    "update_patient": update_patient,
    "delete_patient": delete_patient,
}

# slug → live ASGI handler
handlers: dict[str, ASGIApp] = {}
exit_stack = contextlib.AsyncExitStack()

_lock = asyncio.Lock()


def build_agent_mcp(slug: str, config: AgentConfig) -> FastMCP:
    allowed: set[str] = {tool for srv in config.servers for tool in srv.tools}

    # streamable_http_path="/" because the middleware strips /mcp/{slug}
    # before dispatching, so the sub-app always sees path "/"
    agent_mcp = FastMCP(name=f"agent-{slug}", streamable_http_path="/")

    registered = []
    for tool_name, fn in TOOL_REGISTRY.items():
        if tool_name in allowed:
            agent_mcp.tool()(fn)
            registered.append(tool_name)
        else:
            log.debug("tool_skipped", slug=slug, tool=tool_name)

    unknown = allowed - set(TOOL_REGISTRY)
    if unknown:
        log.warning("unknown_tools_in_config", slug=slug, unknown=sorted(unknown))

    log.info("agent_mcp_built", slug=slug, tools=sorted(registered))
    return agent_mcp


async def ensure_agent(slug: str) -> ASGIApp | None:
    """Return the ASGI handler for slug, starting the MCP session on first call."""
    if slug in handlers:
        return handlers[slug]

    async with _lock:
        if slug in handlers:  # re-check inside lock
            return handlers[slug]

        config = get_config(fresh=True)
        if slug not in config.agents:
            log.warning("agent_slug_not_found", slug=slug, available=list(config.agents.keys()))
            return None

        agent_mcp = build_agent_mcp(slug, config.agents[slug])
        handler = agent_mcp.streamable_http_app()  # must be called before session_manager
        await exit_stack.enter_async_context(agent_mcp.session_manager.run())
        handlers[slug] = handler
        log.info("agent_mcp_lazily_started", slug=slug)
        return handlers[slug]
