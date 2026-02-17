# Dynamic Agent Endpoint — Product Requirements Document

## Overview

A FastAPI endpoint that dynamically loads an agent configuration by slug, connects to the specified MCP servers with a per-agent tool allowlist, runs an agentic LLM loop, and returns the result. Each slug maps to a named agent with its own set of tools drawn from one or more MCP servers.

---

## Goals

- Allow multiple agents to be defined in a single config file
- Each agent exposes only the tools it needs (tool allowlist per MCP server)
- A single FastAPI endpoint routes requests to the right agent by slug
- Config is validated at startup with Pydantic so misconfiguration fails fast

---

## Architecture

```
POST /agents/{slug}/run
        │
        ▼
  gateway/router.py
  look up AgentConfig by slug
        │
        ▼
  gateway/agent.py
  get-or-create fastmcp.Client for each server URL
  (MCP connections are created once, reused across requests)
        │
        ├──► filter tools to allowlist
        │
        ▼
  LLM agentic loop (LiteLLM)
  tool calls → client.call_tool(fn_name, args)
        │
        ▼
  return final text response
```

MCP servers run as separate processes (or can be mounted in-process). The gateway treats them as **remote HTTP endpoints** and manages a pool of `fastmcp.Client` instances — one per unique server URL — so connections are not recreated on every request.

---

## File Structure

```
config/
└── agents.yaml          # Agent definitions (slug → servers + tool allowlists)
gateway/
├── __init__.py
├── config.py            # Pydantic models + YAML loader for agents.yaml
├── connections.py       # Client pool: get-or-create fastmcp.Client per server URL
├── agent.py             # Agent loop: filter tools, call LLM
└── router.py            # FastAPI router with POST /agents/{slug}/run
```

---

## Config Schema (`agents.yaml`)

```yaml
agents:
  clinical-reader:
    name: "Clinical Reader"
    system_prompt: "You are a read-only clinical assistant."
    servers:
      - url: "http://localhost:8001/mcp"
        tools: ["list_patients", "get_patient"]

  clinical-writer:
    name: "Clinical Writer"
    system_prompt: "You are a clinical data entry assistant."
    servers:
      - url: "http://localhost:8001/mcp"
        tools: ["create_patient", "update_patient", "delete_patient"]
```

### Fields

| Field                       | Type         | Description                                        |
|-----------------------------|--------------|----------------------------------------------------|
| `agents.<slug>`             | key          | URL-safe identifier used in the endpoint path      |
| `name`                      | string       | Human-readable name (informational)                |
| `system_prompt`             | string       | System prompt injected into the LLM for this agent |
| `servers[].url`             | string       | MCP server base URL                                |
| `servers[].tools`           | list[string] | Allowlisted tool names from that server            |

---

## Pydantic Models (`config.py`)

```python
class MCPServerConfig(BaseModel):
    url: str
    tools: list[str]

class AgentConfig(BaseModel):
    name: str
    system_prompt: str
    servers: list[MCPServerConfig]

class AgentsConfig(BaseModel):
    agents: dict[str, AgentConfig]
```

Config is loaded once at startup and stored on the FastAPI `app.state`.

---

## Endpoint

```
POST /agents/{slug}/run
```

### Request Body

```json
{ "message": "List all patients" }
```

### Response

```json
{ "response": "Here are the patients: ..." }
```

### Errors

| Status | Condition               |
|--------|-------------------------|
| 404    | slug not found in config |
| 502    | MCP server unreachable  |
| 500    | LLM call failed         |

---

## Client Pool (`connections.py`)

A module-level dict maps `server_url → fastmcp.Client`. On first use the client is created and entered (`async with` context kept open for the process lifetime). Subsequent requests to the same server URL reuse the existing client.

```python
_clients: dict[str, Client] = {}

async def get_client(server_url: str) -> Client:
    if server_url not in _clients:
        client = Client({"mcpServers": {"server": {"url": server_url}}})
        await client.__aenter__()
        _clients[server_url] = client
    return _clients[server_url]
```

Clients are closed on app shutdown via a FastAPI lifespan handler.

---

## Agent Loop (`agent.py`)

1. Look up `AgentConfig` by slug from `app.state`
2. For each server in the config, call `get_client(server_url)` from the pool
3. Collect all tools from all clients, **filter** to each server's allowlist
4. Convert filtered tools to OpenAI function-calling format
5. Run the agentic LLM loop (same pattern as `host.py`)
6. Return the final text response

### Tool Filtering

Tools are filtered **after** connecting so MCP servers don't need to know about allowlists — the gateway enforces them. Tool names in the allowlist that don't exist on the server are silently ignored (logged as a warning).

---

## Startup Behaviour

```
gateway/router.py  →  loads agents.yaml on app startup
                   →  validates with Pydantic (raises on bad config)
                   →  stores AgentsConfig on app.state.agents_config
                   →  eagerly opens clients for all unique server URLs
```

---

## Out of Scope

- Auth on the `/agents` endpoint (covered separately)
- Streaming responses
- Conversation history / sessions (stateless per request for now)
- Dynamic config reload without restart
