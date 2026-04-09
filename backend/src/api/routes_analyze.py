"""POST /api/v1/analyze — image classification + Gemma 4 narrative."""

import uuid
from typing import Literal

import httpx
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from src.agent.executor import generate_narrative
from src.clinical.urgency import determine_urgency
from src.config import settings
from src.rag.search import semantic_search

router = APIRouter(prefix="/api/v1")

INCONCLUSIVE_DISCLAIMER = (
    "The image does not clearly match any of the conditions this system was "
    "trained to recognize. The possibilities listed below are the model's best "
    "guesses, but none reached a sufficient confidence level. Please consult a "
    "veterinarian for proper assessment."
)


class AnalyzeResponse(BaseModel):
    analysis_id: str
    classification: dict
    narrative: str
    urgency: Literal["emergency", "soon", "monitor", "healthy", "unknown"]
    rag_matches: list
    pharma: list
    source: Literal["server", "local_ai"]
    prediction_quality: Literal["confident", "low_confidence", "inconclusive"]
    entropy: float
    fallback_reason: str | None = None


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(
    image: UploadFile = File(...),
    species: str = Form(...),
    module: str = Form(...),
) -> AnalyzeResponse:
    """Accept an image + metadata, run classification + narrative, return structured report."""
    analysis_id = str(uuid.uuid4())
    image_bytes = await image.read()

    # 1. Classification via vision service
    vision_url = f"{settings.vision_service_url.rstrip('/')}/vision/{module}?species={species}"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            files = {
                "file": (
                    image.filename or "image.jpg",
                    image_bytes,
                    image.content_type or "image/jpeg",
                )
            }
            vision_resp = await client.post(vision_url, files=files)
            vision_resp.raise_for_status()
            vision_data = vision_resp.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Vision service returned HTTP {e.response.status_code}.",
        ) from e
    except httpx.TimeoutException as e:
        raise HTTPException(
            status_code=504,
            detail="Vision service timed out.",
        ) from e

    # Extract classification results
    preds = vision_data.get("predictions", [])
    label: str = preds[0]["class"] if preds else "unknown"
    confidence: float = preds[0]["probability"] if preds else 0.0
    differentials: list = [
        {"label": p["class"], "confidence": p["probability"]} for p in preds[1:4]
    ]

    # Read prediction quality from vision-service; force inconclusive if empty (spec D8)
    prediction_quality: str = vision_data.get("prediction_quality", "inconclusive")
    entropy: float = vision_data.get("entropy", 0.0)
    if not preds:
        prediction_quality = "inconclusive"

    # 2. Narrative + RAG — skip both for inconclusive (spec D5)
    if prediction_quality == "inconclusive":
        narrative = INCONCLUSIVE_DISCLAIMER
        urgency = "unknown"
        rag_matches: list = []
    else:
        caution = prediction_quality == "low_confidence"
        urgency = determine_urgency(label, confidence)
        narrative = await generate_narrative(
            label=label,
            confidence=confidence,
            differentials=differentials,
            species=species,
            module=module,
            caution_mode=caution,
        )

        # 3. RAG similar cases — best-effort; failure is non-fatal
        try:
            rag_results = await semantic_search(f"{label} {species}", limit=3)
            rag_matches = [
                {
                    "case_id": r.get("id", ""),
                    "similarity": r.get("score", 0),
                    "summary": r.get("text", ""),
                }
                for r in rag_results
            ]
        except Exception:
            rag_matches = []

    return AnalyzeResponse(
        analysis_id=analysis_id,
        classification={
            "label": label,
            "confidence": confidence,
            "differentials": differentials,
        },
        narrative=narrative,
        urgency=urgency,
        rag_matches=rag_matches,
        pharma=[],
        source="server",
        prediction_quality=prediction_quality,
        entropy=entropy,
    )
