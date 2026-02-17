"""
FastAPI router: POST /agents/{slug_id}

Loads the agent config for the slug, filters tool functions to the allowlist,
and runs the ReAct loop directly — no MCP client involved.

Auth:
    Clients must send `Authorization: Bearer <api_key>` header.
    The key is validated against `api_keys` in agents.yaml. A 401 is returned
    if the key is missing/unknown; 403 if the key is not allowed for this agent.

Memory:
    If `user_id` is provided in the request body, conversation history is loaded
    from `memory/{user_id}.json` and persisted after each turn.
"""

import json
from pathlib import Path

import structlog
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from orchestrator.agent_tools import build_openai_tools, run_react_loop
from orchestrator.config import get_config
from orchestrator.registry import TOOL_REGISTRY

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/agents", tags=["agents"])

MEMORY_DIR = Path("memory")


class RunRequest(BaseModel):
    message: str
    user_id: str | None = None


class RunResponse(BaseModel):
    response: str


def _load_history(user_id: str, slug_id: str) -> list[dict]:
    """Load conversation history for a user+agent pair from disk."""
    path = MEMORY_DIR / f"{user_id}.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get(slug_id, [])
    except Exception:
        return []


def _save_history(user_id: str, slug_id: str, history: list[dict]) -> None:
    """Persist updated conversation history for a user+agent pair."""
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    path = MEMORY_DIR / f"{user_id}.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except Exception:
        data = {}
    data[slug_id] = history
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


@router.post("/{slug_id}", response_model=RunResponse)
async def run_agent(
    slug_id: str,
    body: RunRequest,
    authorization: str | None = Header(default=None),
):
    bound_log = log.bind(slug=slug_id, user_id=body.user_id)
    bound_log.info("agent_request_received", message=body.message)

    config = get_config(fresh=True)

    # --- Auth ---
    if not authorization or not authorization.startswith("Bearer "):
        bound_log.warning("missing_api_key")
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    api_key = authorization.removeprefix("Bearer ").strip()
    key_config = config.api_keys.get(api_key)
    if key_config is None:
        bound_log.warning("unknown_api_key")
        raise HTTPException(status_code=401, detail="Invalid API key")

    if slug_id not in key_config.allowed_agents:
        bound_log.warning("api_key_not_authorized", allowed=key_config.allowed_agents)
        raise HTTPException(status_code=403, detail=f"API key not authorized for agent '{slug_id}'")

    # --- Agent lookup ---
    if slug_id not in config.agents:
        bound_log.warning("agent_not_found", available=list(config.agents.keys()))
        raise HTTPException(status_code=404, detail=f"Agent '{slug_id}' not found")

    agent_config = config.agents[slug_id]
    allowed = {tool for srv in agent_config.servers for tool in srv.tools}

    fn_registry = {name: fn for name, fn in TOOL_REGISTRY.items() if name in allowed}
    bound_log.info("tools_loaded", tools=sorted(fn_registry.keys()))

    openai_tools = build_openai_tools(fn_registry)

    # --- Conversation memory ---
    history: list[dict] = []
    if body.user_id:
        history = _load_history(body.user_id, slug_id)
        bound_log.info("memory_loaded", turns=len(history))

    messages = [
        {"role": "system", "content": agent_config.system_prompt},
        *history,
        {"role": "user", "content": body.message},
    ]

    response = await run_react_loop(messages, openai_tools, fn_registry)

    # Persist only the user/assistant exchange (no system, no tool internals)
    if body.user_id:
        history.append({"role": "user", "content": body.message})
        history.append({"role": "assistant", "content": response})
        _save_history(body.user_id, slug_id, history)
        bound_log.info("memory_saved", turns=len(history))

    bound_log.info("agent_request_complete")
    return RunResponse(response=response)
