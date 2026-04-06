"""POST /api/v1/triage — text-based symptom triage via Gemma 4."""
import uuid
import logging

import httpx
from fastapi import APIRouter
from pydantic import BaseModel, Field

from src.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1")


class TriageRequest(BaseModel):
    species: str = Field(..., pattern="^(canine|feline)$")
    symptoms: str = Field(..., min_length=5, max_length=2000)


class PossibleCondition(BaseModel):
    name: str
    probability: float
    urgency: str


class TriageResponse(BaseModel):
    triage_id: str
    possible_conditions: list[PossibleCondition] = []
    recommendation: str
    source: str


@router.post("/triage", response_model=TriageResponse)
async def triage(request: TriageRequest):
    triage_id = str(uuid.uuid4())

    prompt = (
        f"Species: {request.species}.\n"
        f"Owner reports these symptoms: {request.symptoms}\n\n"
        f"Provide:\n"
        f"1) Top 3 possible conditions with likelihood (high/medium/low) and urgency\n"
        f"2) A clear recommendation for what the owner should do right now\n"
        f"Be concise. State that this is not a diagnosis and recommend consulting a veterinarian."
    )

    try:
        payload = {
            "model": settings.ollama_model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are Howl Vision, a veterinary AI assistant. "
                        "Provide symptom-based triage guidance. "
                        "Always state this is not a diagnosis. "
                        "Never use the word 'diagnosis' — say 'assessment' or 'triage'. "
                        "Recommend consulting a veterinarian."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "stream": False,
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{settings.ollama_base_url.rstrip('/')}/api/chat",
                json=payload,
            )
            resp.raise_for_status()
            recommendation = resp.json()["message"]["content"]
    except httpx.HTTPStatusError as e:
        logger.error("Triage Ollama HTTP %s: %s", e.response.status_code, e.response.text[:500])
        recommendation = (
            "Unable to generate AI triage at this time. "
            "Based on the symptoms described, please consult a veterinarian. "
            "If symptoms are severe (difficulty breathing, seizures, bleeding), "
            "seek emergency care immediately."
        )
    except Exception as e:
        logger.error("Triage generation failed: %s", e)
        recommendation = (
            "Unable to generate AI triage at this time. "
            "Based on the symptoms described, please consult a veterinarian. "
            "If symptoms are severe (difficulty breathing, seizures, bleeding), "
            "seek emergency care immediately."
        )

    return TriageResponse(
        triage_id=triage_id,
        recommendation=recommendation,
        source="server",
    )
