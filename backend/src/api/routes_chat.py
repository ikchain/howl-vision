from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.agent.orchestrator import run_agent

router = APIRouter(prefix="/api/v1")


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    image_b64: str | None = None
    history: list = Field(default_factory=list)  # Reserved for future multi-turn


@router.post("/chat")
async def chat(request: ChatRequest):
    return StreamingResponse(
        run_agent(message=request.message, image_b64=request.image_b64),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
