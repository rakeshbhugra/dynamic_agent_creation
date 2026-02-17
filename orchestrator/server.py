"""
MCP server mounted alongside FastAPI.

Run:
    uv run uvicorn orchestrator.server:app --port 8001 --reload

Connect from Claude Desktop or Claude Code:
    { "url": "http://localhost:8001/mcp" }
"""

import contextlib

from fastapi import FastAPI

from orchestrator.tools import mcp


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    async with mcp.session_manager.run():
        yield


app = FastAPI(title="Patient MCP Server", lifespan=lifespan)

app.mount("/", mcp.streamable_http_app())
