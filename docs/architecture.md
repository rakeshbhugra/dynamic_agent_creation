# Dynamic Agent Creation — Architecture

## Overview

A multi-layer system that exposes a patient management API as dynamically-configured MCP (Model Context Protocol) servers. Each agent slug maps to a filtered subset of tools, mounted lazily on first request — no restart required when adding new agents.

---

## Network Flow

```
┌──────────────────────────────────────────────────────────────────────────┐
│                            CLIENT LAYER                                  │
│                                                                          │
│   host.py  (LiteLLM + fastmcp.Client)                                    │
│   SLUG = "clinical-reader"  →  http://localhost:8002/mcp/clinical-reader │
└───────────────────────────────────┬──────────────────────────────────────┘
                                    │  POST /mcp/{slug}
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       ORCHESTRATOR  :8002                               │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  DynamicMCPMiddleware  (middleware.py)                           │   │
│  │                                                                  │   │
│  │  path starts with /mcp/{slug}?                                   │   │
│  │       │ yes                    │ no                              │   │
│  │       ▼                        ▼                                 │   │
│  │  ensure_agent(slug)      FastAPI routes (/health)                │   │
│  │  (registry.py)                                                   │   │
│  │       │                                                          │   │
│  │       ├── slug in handlers? ──yes──► dispatch to handler         │   │
│  │       │                                                          │   │
│  │       └── no ──► read agents.yaml (fresh)                        │   │
│  │                  build FastMCP (allowed tools only)              │   │
│  │                  start session manager                           │   │
│  │                  cache handler                                   │   │
│  │                  dispatch to handler                             │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│   handlers["clinical-reader"]  →  FastMCP(list_patients, get_patient)   │
│   handlers["clinical-writer"]  →  FastMCP(create, update, delete)       │
│   handlers["clinical-admin"]   →  FastMCP(all 5 tools)                  │
└───────────────────────────────────┬─────────────────────────────────────┘
                                    │  httpx  POST /patients
                                    │         (X-API-Key header)
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       PLATFORM API  :8000                               │
│                                                                         │
│   FastAPI  +  API key middleware                                        │
│                                                                         │
│   GET  /patients          GET  /patients/{id}                           │
│   POST /patients          PUT  /patients/{id}                           │
│                           DELETE /patients/{id}                         │
│                                    │                                    │
│                                    ▼                                    │
│                               db.json                                   │
└─────────────────────────────────────────────────────────────────────────┘

  config/agents.yaml  ──► read fresh on first hit per slug
  logs/gateway.log    ◄── structlog JSON from all orchestrator modules
```

---

## File Structure

```
platform/
├── main.py          # FastAPI app, routes, API key middleware
├── utils.py         # JSON DB helpers (load, save, CRUD)
└── db.json          # Mock patient database

orchestrator/
├── tools.py         # Raw tool functions + _call_api helper (httpx → platform)
├── config.py        # Pydantic models + YAML loader (fresh= flag)
├── registry.py      # build_agent_mcp + ensure_agent (lazy session start)
├── middleware.py    # DynamicMCPMiddleware — routes /mcp/{slug}
├── logging_setup.py # structlog: JSON to file + ConsoleRenderer to stdout
└── main.py          # FastAPI app wiring: lifespan + /health

config/
└── agents.yaml      # Agent definitions: slug → servers + tool allowlists

host.py              # Interactive LiteLLM agentic loop (connects to gateway)
docs/                # PRDs and architecture docs
logs/
└── gateway.log      # Structured JSON log output
```

---

## Ports

| Service        | Port | Command                                              |
|----------------|------|------------------------------------------------------|
| Platform API   | 8000 | `uv run uvicorn platform.main:app --port 8000`       |
| Gateway        | 8002 | `uv run uvicorn orchestrator.main:app --port 8002`   |

---

## Agent Config (`config/agents.yaml`)

```yaml
agents:
  clinical-reader:
    name: "Clinical Reader"
    system_prompt: "You are a read-only clinical assistant."
    servers:
      - url: "http://localhost:8001/mcp"
        tools:
          - list_patients
          - get_patient

  clinical-writer:
    name: "Clinical Writer"
    system_prompt: "You are a clinical data entry assistant."
    servers:
      - url: "http://localhost:8001/mcp"
        tools:
          - create_patient
          - update_patient
          - delete_patient
```

Each entry under `agents` becomes a live MCP endpoint at `/mcp/{slug}` on first request. Add a new slug and it's available immediately — no restart.

---

## Available Tools

| Tool              | Method | Platform endpoint        |
|-------------------|--------|--------------------------|
| `list_patients`   | GET    | `/patients`              |
| `get_patient`     | GET    | `/patients/{id}`         |
| `create_patient`  | POST   | `/patients`              |
| `update_patient`  | PUT    | `/patients/{id}`         |
| `delete_patient`  | DELETE | `/patients/{id}`         |

---

## Lazy Mounting Flow

1. Request arrives at `POST /mcp/clinical-reader`
2. `DynamicMCPMiddleware` extracts slug `clinical-reader`
3. `ensure_agent("clinical-reader")` checks `handlers` dict — miss on first call
4. Acquires lock, reads `agents.yaml` fresh from disk
5. Calls `build_agent_mcp` — creates `FastMCP` with only `list_patients` + `get_patient`
6. Calls `streamable_http_app()` then starts `session_manager`
7. Stores handler in `handlers["clinical-reader"]`
8. Strips `/mcp/clinical-reader` prefix, dispatches request to handler
9. All subsequent requests skip steps 3–8 and hit the cached handler directly

---

## Running the Host

Edit `SLUG` in `host.py` to select an agent, then:

```bash
uv run host.py
```

The host connects to `http://localhost:8002/mcp/{SLUG}`, lists available tools, and starts an interactive LiteLLM loop using `openai/gpt-4o`.

---

## Logging

All orchestrator modules log via `structlog`:

- **Console** — human-readable `ConsoleRenderer`
- **File** — `logs/gateway.log` in JSON format (one object per line)

Key log events:

| Event                      | Module       | Meaning                              |
|----------------------------|--------------|--------------------------------------|
| `config_loaded`            | config       | YAML parsed and validated            |
| `agent_mcp_built`          | registry     | FastMCP instance created for slug    |
| `agent_mcp_lazily_started` | registry     | Session manager started, handler cached |
| `agent_slug_not_found`     | registry     | Slug not in agents.yaml              |
| `mcp_request_dispatched`   | middleware   | Request forwarded to agent handler   |
| `tool_skipped`             | registry     | Tool not in allowlist                |
