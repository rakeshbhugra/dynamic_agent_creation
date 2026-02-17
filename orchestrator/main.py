"""
Dynamic Agent Gateway.

MCP servers are mounted lazily: on the first request to /mcp/{slug} the config
is read fresh from disk, the FastMCP session is started, and the request is
dispatched. Subsequent requests hit the cached handler directly.

Run:
    uv run uvicorn orchestrator.main:app --port 8002 --reload

Endpoints:
    GET  /health       → health check + list of currently active slugs
    MCP  /mcp/{slug}   → lazily-mounted MCP server for that agent
"""

import contextlib
from pathlib import Path

import structlog
from dotenv import load_dotenv
from fastapi import FastAPI

load_dotenv(Path(__file__).parent.parent / ".env")

from orchestrator.logging_setup import setup_logging

setup_logging()

from orchestrator.middleware import DynamicMCPMiddleware
from orchestrator.registry import exit_stack, handlers

log = structlog.get_logger(__name__)


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("gateway_starting")
    async with exit_stack:
        yield
    log.info("gateway_stopped")


app = FastAPI(title="Dynamic Agent Gateway", lifespan=lifespan)
app.add_middleware(DynamicMCPMiddleware)


@app.get("/health")
def health():
    return {"status": "ok", "active_agents": list(handlers.keys())}
