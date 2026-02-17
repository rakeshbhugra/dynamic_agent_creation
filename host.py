"""
MCP Host — connects to the orchestrator MCP server and runs an agentic loop.

Usage:
    1. Start the platform API (port 8000):
        uv run uvicorn platform.main:app --port 8000 --reload

    2. Start the orchestrator MCP server (port 8001):
        uv run uvicorn orchestrator.server:app --port 8001 --reload

    3. Run the host:
        uv run host.py

Example prompts:
    "List all patients"
    "Get patient with id <uuid>"
    "Create a patient named John, age 45, male, diagnosis: hypertension"
    "Update patient <uuid> diagnosis to diabetes"
    "Delete patient <uuid>"
"""

import asyncio
import json
import warnings
from pathlib import Path

import litellm
from dotenv import load_dotenv
from fastmcp import Client

load_dotenv(Path(__file__).parent / ".env")

warnings.filterwarnings("ignore", message="enable_cleanup_closed")

MODEL = "openai/gpt-4o"

SERVERS_CONFIG = {
    "mcpServers": {
        "orchestrator": {
            "url": "http://localhost:8001/mcp",
        },
    }
}

SYSTEM_PROMPT = """You are a helpful assistant with access to a patient management system.
Use the available tools to manage patients. When you have the result, respond clearly and concisely."""


def mcp_tools_to_openai(tools) -> list[dict]:
    openai_tools = []
    for tool in tools:
        openai_tools.append({
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description or "",
                "parameters": tool.inputSchema or {"type": "object", "properties": {}},
            },
        })
    return openai_tools


async def agent_loop(client: Client, user_input: str, messages: list[dict]) -> str:
    messages.append({"role": "user", "content": user_input})

    tools = await client.list_tools()
    openai_tools = mcp_tools_to_openai(tools)

    while True:
        response = await litellm.acompletion(
            model=MODEL,
            messages=messages,
            tools=openai_tools if openai_tools else None,
            tool_choice="auto" if openai_tools else None,
        )

        choice = response.choices[0]
        assistant_message = choice.message
        messages.append(assistant_message.model_dump())

        if not assistant_message.tool_calls:
            return assistant_message.content or ""

        for tool_call in assistant_message.tool_calls:
            fn_name = tool_call.function.name
            fn_args = json.loads(tool_call.function.arguments or "{}")

            print(f"  [tool] {fn_name}({fn_args})")

            try:
                result = await client.call_tool(fn_name, fn_args)
                result_str = str(result)
            except Exception as e:
                result_str = f"Error: {e}"

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result_str,
            })


async def main():
    client = Client(SERVERS_CONFIG)

    async with client:
        tools = await client.list_tools()
        print("Connected to orchestrator MCP server.")
        print(f"Available tools: {[t.name for t in tools]}\n")

        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        print("Type your message (or 'quit' to exit):\n")
        while True:
            user_input = input("You: ").strip()
            if user_input.lower() in ("quit", "exit"):
                break
            if not user_input:
                continue

            response = await agent_loop(client, user_input, messages)
            print(f"\nAssistant: {response}\n")


if __name__ == "__main__":
    asyncio.run(main())
