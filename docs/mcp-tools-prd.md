# MCP Tools Layer — Product Requirements Document

## Overview

An MCP (Model Context Protocol) server that wraps the Platform Patient API, exposing each REST endpoint as an MCP tool. Agents (Claude Code, Claude Desktop, etc.) interact with patient data entirely through these tools rather than calling the HTTP API directly.

---

## Goals

- Give AI agents structured, typed access to the Patient API via MCP tools
- Keep all network logic in one central helper so auth and error handling are consistent
- Decouple agents from raw HTTP — tool signatures are the contract, not URL paths

---

## File Structure

```
mcp/
├── tools.py     # FastMCP instance, _call_api helper, all tool definitions
server.py        # (future) FastAPI + MCP mount, streamable HTTP endpoint
```

---

## Central HTTP Helper

`_call_api(method, path, **kwargs)` in `mcp/tools.py`:

- Creates a short-lived `httpx.AsyncClient` per call
- Injects the `X-API-Key` header automatically
- Raises `httpx.HTTPStatusError` on non-2xx so tools surface errors cleanly
- Returns `None` on 204 No Content (e.g. DELETE), `dict | list` otherwise

```python
async def _call_api(method: str, path: str, **kwargs) -> dict | list | None:
    async with httpx.AsyncClient() as client:
        response = await client.request(method, f"{BASE_URL}{path}",
                                        headers={"X-API-Key": API_KEY}, **kwargs)
        response.raise_for_status()
        if response.status_code == 204:
            return None
        return response.json()
```

---

## MCP Tools

| Tool              | Maps to                     | Description                              |
|-------------------|-----------------------------|------------------------------------------|
| `list_patients`   | `GET /patients`             | Return all patients                      |
| `get_patient`     | `GET /patients/{id}`        | Return a single patient by ID            |
| `create_patient`  | `POST /patients`            | Create a patient (name, age, gender, dx) |
| `update_patient`  | `PUT /patients/{id}`        | Partial update — only non-None fields    |
| `delete_patient`  | `DELETE /patients/{id}`     | Delete a patient, return confirmation    |

---

## Configuration

| Setting    | Value                    | Notes                              |
|------------|--------------------------|------------------------------------|
| `BASE_URL` | `http://localhost:8000`  | Overridable via env var (future)   |
| `API_KEY`  | `secret-api-key-123`     | Matches the Platform API mock key  |

---

## MCP Server (Future)

The MCP tools will be served via a FastAPI + FastMCP mount so clients can connect over HTTP:

```python
# server.py (not yet implemented)
mcp = FastMCP(name="PatientMCP", streamable_http_path="/mcp")
app = FastAPI(lifespan=lifespan)
app.mount("/", mcp.streamable_http_app())
```

Claude Desktop / Claude Code connect via:
```json
{ "url": "http://localhost:8001/mcp" }
```

---

## Out of Scope

- Retry logic or connection pooling (single `AsyncClient` per call is intentional for simplicity)
- Streaming responses
- MCP server process management
- Authentication for the MCP endpoint itself
