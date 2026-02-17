"""
FastAPI router: POST /agents/{slug_id}

Loads the agent config for the slug, filters tool functions to the allowlist,
and runs the ReAct loop directly — no MCP client involved.
"""

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from orchestrator.agent_tools import build_openai_tools, run_react_loop
from orchestrator.config import get_config
from orchestrator.registry import TOOL_REGISTRY

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/agents", tags=["agents"])


class RunRequest(BaseModel):
    message: str


class RunResponse(BaseModel):
    response: str


@router.post("/{slug_id}", response_model=RunResponse)
async def run_agent(slug_id: str, body: RunRequest):

    # if this client is allowed this agent - client call header will need to send api key
    
    bound_log = log.bind(slug=slug_id)
    bound_log.info("agent_request_received", message=body.message)

    config = get_config(fresh=True)
    if slug_id not in config.agents:
        bound_log.warning("agent_not_found", available=list(config.agents.keys()))
        raise HTTPException(status_code=404, detail=f"Agent '{slug_id}' not found")

    agent_config = config.agents[slug_id]
    allowed = {tool for srv in agent_config.servers for tool in srv.tools}

    # Filter registry to only this agent's allowed tools
    fn_registry = {name: fn for name, fn in TOOL_REGISTRY.items() if name in allowed}
    bound_log.info("tools_loaded", tools=sorted(fn_registry.keys()))

    openai_tools = build_openai_tools(fn_registry)

    messages = [
        {"role": "system", "content": agent_config.system_prompt},
        {"role": "user", "content": body.message},
    ]

    response = await run_react_loop(messages, openai_tools, fn_registry)

    bound_log.info("agent_request_complete")
    return RunResponse(response=response)
