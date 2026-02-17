"""
ReAct agent loop using LiteLLM tool calling.

Tools are loaded directly from the function registry based on the agent
config — no MCP client required.

Pattern:
    user message
        │
        ▼
    reasoner ── tool_calls? ──yes──► tools_node ──► reasoner
        │
        no
        │
        ▼
    final answer
"""

import inspect
import json
from typing import Callable, get_type_hints

import litellm
import structlog

log = structlog.get_logger(__name__)

MODEL = "openai/gpt-4o"


_PYTHON_TO_JSON: dict[type, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
}


def _fn_to_schema(name: str, fn: Callable) -> dict:
    """Build an OpenAI function schema from a function's signature and docstring."""
    hints = get_type_hints(fn)
    hints.pop("return", None)
    sig = inspect.signature(fn)

    properties: dict[str, dict] = {}
    required: list[str] = []

    for param_name, param in sig.parameters.items():
        py_type = hints.get(param_name, str)
        json_type = _PYTHON_TO_JSON.get(py_type, "string")
        # handle Optional[X] (X | None)
        origin = getattr(py_type, "__origin__", None)
        if origin is type(None):
            json_type = "string"
        elif origin is not None:
            args = [a for a in getattr(py_type, "__args__", []) if a is not type(None)]
            json_type = _PYTHON_TO_JSON.get(args[0], "string") if args else "string"

        properties[param_name] = {"type": json_type}
        if param.default is inspect.Parameter.empty:
            required.append(param_name)

    return {
        "name": name,
        "description": (fn.__doc__ or "").strip(),
        "parameters": {
            "type": "object",
            "properties": properties,
            "required": required,
        },
    }


def build_openai_tools(fn_registry: dict[str, Callable]) -> list[dict]:
    """Convert a dict of {name: fn} to OpenAI function-calling format."""
    return [
        {"type": "function", "function": _fn_to_schema(name, fn)}
        for name, fn in fn_registry.items()
    ]


async def run_react_loop(
    messages: list[dict],
    openai_tools: list[dict],
    fn_registry: dict[str, Callable],
) -> str:
    """
    Run the ReAct loop until the LLM produces a final answer.

    messages      — initial message list (system + user)
    openai_tools  — tools in OpenAI function-calling format
    fn_registry   — {tool_name: callable} for executing tool calls
    """
    turn = 0

    while True:
        turn += 1
        log.debug("reasoner_thinking", turn=turn, message_count=len(messages))

        response = await litellm.acompletion(
            model=MODEL,
            messages=messages,
            tools=openai_tools or None,
            tool_choice="auto" if openai_tools else None,
        )

        msg = response.choices[0].message

        # --- Reasoner ---
        if msg.tool_calls:
            messages.append({
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": msg.tool_calls,
            })
            log.info("reasoner_requesting_tools", turn=turn, tools=[tc.function.name for tc in msg.tool_calls])

            # --- Tools node ---
            for tc in msg.tool_calls:
                fn_name = tc.function.name
                fn_args = json.loads(tc.function.arguments or "{}")

                log.info("tool_call", tool=fn_name, args=fn_args)
                try:
                    fn = fn_registry[fn_name]
                    result = await fn(**fn_args)
                    result_str = json.dumps(result) if isinstance(result, (dict, list)) else str(result)
                    log.debug("tool_result", tool=fn_name, preview=result_str[:200])
                except Exception as exc:
                    result_str = f"Error: {exc}"
                    log.error("tool_call_failed", tool=fn_name, error=str(exc))

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result_str,
                })

        else:
            log.info("reasoner_final_answer", turns=turn)
            return msg.content or ""
