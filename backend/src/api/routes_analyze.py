"""POST /api/v1/analyze — image classification + Gemma 4 narrative."""

import uuid

import httpx
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from src.agent.executor import generate_narrative
from src.clinical.urgency import determine_urgency
from src.config import settings
from src.rag.search import semantic_search

router = APIRouter(prefix="/api/v1")


class AnalyzeResponse(BaseModel):
    analysis_id: str
    classification: dict
    narrative: str
    urgency: str
    rag_matches: list
    pharma: list
    source: str


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(
    image: UploadFile = File(...),
    species: str = Form(...),
    module: str = Form(...),
) -> AnalyzeResponse:
    """Accept an image + metadata, run classification + narrative, return structured report.

    species: 'canine' | 'feline'
    module:  'dermatology' | 'parasites'
    """
    analysis_id = str(uuid.uuid4())
    image_bytes = await image.read()

    # 1. Classification via vision service — species is NOT part of the URL,
    #    it's passed downstream for narrative context only.
    vision_url = f"{settings.vision_service_url.rstrip('/')}/vision/{module}"
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

    label: str = vision_data.get("prediction", "unknown")
    confidence: float = vision_data.get("confidence", 0.0)
    differentials: list = vision_data.get("differentials", [])
    urgency = determine_urgency(label, confidence)

    # 2. Narrative via Gemma 4
    narrative = await generate_narrative(
        label=label,
        confidence=confidence,
        differentials=differentials,
        species=species,
        module=module,
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
    )
