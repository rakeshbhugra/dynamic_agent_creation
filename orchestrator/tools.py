"""
MCP tools for the Platform Patient API.

Each tool makes an async HTTP call to the running FastAPI server.
Central helper `_call_api` handles auth headers and error propagation.
"""

import httpx
from mcp.server.fastmcp import FastMCP

BASE_URL = "http://localhost:8000"
API_KEY = "secret-api-key-123"

mcp = FastMCP(name="PatientMCP", streamable_http_path="/mcp")


async def _call_api(method: str, path: str, **kwargs) -> dict | list | None:
    """Central HTTP client. Raises httpx.HTTPStatusError on non-2xx responses."""
    async with httpx.AsyncClient() as client:
        response = await client.request(
            method,
            f"{BASE_URL}{path}",
            headers={"X-API-Key": API_KEY},
            **kwargs,
        )
        response.raise_for_status()
        if response.status_code == 204:
            return None
        return response.json()


@mcp.tool()
async def list_patients() -> list:
    """List all patients."""
    return await _call_api("GET", "/patients")


@mcp.tool()
async def get_patient(patient_id: str) -> dict:
    """Get a single patient by ID."""
    return await _call_api("GET", f"/patients/{patient_id}")


@mcp.tool()
async def create_patient(name: str, age: int, gender: str, diagnosis: str) -> dict:
    """Create a new patient."""
    return await _call_api("POST", "/patients", json={
        "name": name,
        "age": age,
        "gender": gender,
        "diagnosis": diagnosis,
    })


@mcp.tool()
async def update_patient(
    patient_id: str,
    name: str | None = None,
    age: int | None = None,
    gender: str | None = None,
    diagnosis: str | None = None,
) -> dict:
    """Update fields on an existing patient. Only provided fields are changed."""
    updates = {k: v for k, v in {
        "name": name,
        "age": age,
        "gender": gender,
        "diagnosis": diagnosis,
    }.items() if v is not None}
    return await _call_api("PUT", f"/patients/{patient_id}", json=updates)


@mcp.tool()
async def delete_patient(patient_id: str) -> str:
    """Delete a patient by ID. Returns a confirmation message."""
    await _call_api("DELETE", f"/patients/{patient_id}")
    return f"Patient {patient_id} deleted."
