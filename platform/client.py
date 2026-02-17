"""
Simple chat client — sends messages to an agent via the gateway.

Usage:
    uv run platform/client.py

Change SLUG to switch agents:
    clinical-reader   → list and view patients
    clinical-writer   → create, update, delete patients
    clinical-admin    → full access
"""

import httpx

GATEWAY_URL = "http://localhost:8002"
SLUG = "test5"       # change this to switch agents
API_KEY = "key-reader-001"  # must match api_keys in config/agents.yaml
USER_ID = "user-123"        # change per user; drives conversation memory


def chat(message: str) -> str:
    response = httpx.post(
        f"{GATEWAY_URL}/agents/{SLUG}",
        headers={"Authorization": f"Bearer {API_KEY}"},
        json={"message": message, "user_id": USER_ID},
        timeout=60,
    )
    response.raise_for_status()
    return response.json()["response"]


if __name__ == "__main__":
    print(f"Chatting with agent: {SLUG}")
    print(f"Gateway: {GATEWAY_URL}/agents/{SLUG}")
    print(f"User: {USER_ID}")
    print("Type 'quit' to exit.\n")

    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in ("quit", "exit"):
            break
        if not user_input:
            continue

        try:
            response = chat(user_input)
            print(f"\nAgent: {response}\n")
        except httpx.HTTPStatusError as e:
            print(f"\nError {e.response.status_code}: {e.response.json()}\n")
