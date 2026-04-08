"""Agent orchestrator — the core loop connecting Gemma 4 to all tools.

Receives a veterinary query (text + optional image), runs the agent loop
with tool calling, and yields SSE events for the final response.
"""

import json
import logging
from collections.abc import AsyncGenerator

from ollama import AsyncClient

from src.agent.executor import execute_tool_calls
from src.agent.tools import SYSTEM_PROMPT, TOOL_DEFINITIONS
from src.config import settings

logger = logging.getLogger(__name__)

# Chunk size for fake streaming (words per SSE event)
STREAM_CHUNK_WORDS = 3


def _get_ollama_client() -> AsyncClient:
    # AsyncClient wraps httpx.AsyncClient internally so every chat() call
    # is awaitable. The previous sync Client blocked the FastAPI event loop
    # for the full duration of the generation, so any concurrent request
    # (triage, another analysis, a healthcheck from the frontend) had to
    # wait until the first generation finished. With the async client the
    # loop yields while waiting on the model, and other handlers run.
    return AsyncClient(host=settings.ollama_base_url)


def _build_initial_messages(message: str, image_b64: str | None) -> list[dict]:
    """Build the initial message list for Ollama."""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    user_msg = {"role": "user", "content": message}
    if image_b64:
        # Ollama expects raw base64 without data URI prefix
        raw_b64 = image_b64.split(",", 1)[-1] if "," in image_b64 else image_b64
        user_msg["images"] = [raw_b64]

    messages.append(user_msg)
    return messages


async def run_agent(
    message: str,
    image_b64: str | None = None,
) -> AsyncGenerator[str, None]:
    """Run the agent loop and yield SSE events.

    Events:
        {"type": "tool_status", "tool": "classify_dermatology", "status": "running"}
        {"type": "token", "content": "Based on the analysis..."}
        {"type": "done"}
        {"type": "error", "message": "...", "code": "..."}
    """
    client = _get_ollama_client()
    messages = _build_initial_messages(message, image_b64)
    iteration = 0
    final_response = None

    try:
        while iteration < settings.agent_max_iterations:
            iteration += 1
            logger.info("Agent loop iteration %d/%d", iteration, settings.agent_max_iterations)

            # Awaited call — no streaming during tool-calling iterations.
            # The event loop is free to serve other requests while the
            # model generates.
            response = await client.chat(
                model=settings.ollama_model,
                messages=messages,
                tools=TOOL_DEFINITIONS,
            )

            msg = response.message

            # Case 1: Gemma emits tool_calls → execute and continue loop
            if msg.tool_calls:
                # Add assistant turn to history
                messages.append({
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": [
                        {"function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                        for tc in msg.tool_calls
                    ],
                })

                # Emit tool_status events for frontend transparency
                for tc in msg.tool_calls:
                    yield _sse({"type": "tool_status", "tool": tc.function.name, "status": "running"})

                # Execute all tools in parallel
                tool_results = await execute_tool_calls(msg.tool_calls, image_b64)

                # Add tool results to history + emit status
                for tc in msg.tool_calls:
                    call_id = getattr(tc, "id", None) or "unknown"
                    result = tool_results.get(call_id, {"error": "No result returned"})
                    messages.append({
                        "role": "tool",
                        "content": json.dumps(result, ensure_ascii=False),
                    })
                    yield _sse({"type": "tool_status", "tool": tc.function.name, "status": "done"})

                continue

            # Case 2: Gemma emits text → final response
            if msg.content:
                final_response = msg.content
                break

            # Case 3: Empty response (rare) — continue loop
            logger.warning("Empty response from Gemma at iteration %d", iteration)
            continue

        # Max iterations reached without terminal response
        if final_response is None:
            final_response = (
                "I analyzed the available information but could not synthesize "
                "a complete conclusion within the allowed iterations. "
                "Partial tool results are available in the consultation history."
            )

        # Fake streaming — emit final_response in word chunks for smooth UX
        words = final_response.split()
        for i in range(0, len(words), STREAM_CHUNK_WORDS):
            chunk = " ".join(words[i : i + STREAM_CHUNK_WORDS])
            # Add space after each chunk except the last
            if i + STREAM_CHUNK_WORDS < len(words):
                chunk += " "
            yield _sse({"type": "token", "content": chunk})

        yield _sse({"type": "done"})

    except Exception as e:
        logger.exception("Agent loop error")
        yield _sse({"type": "error", "message": str(e), "code": "AGENT_ERROR"})
        yield _sse({"type": "done"})


def _sse(data: dict) -> str:
    """Format a dict as an SSE event line."""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
