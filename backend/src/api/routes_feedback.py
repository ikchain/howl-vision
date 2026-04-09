"""POST /api/v1/feedback — active learning label from users."""

import json
import logging
from pathlib import Path

import psycopg2
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from src.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1")

# Images saved here — volume-mounted, NOT web-accessible (spec D5).
FEEDBACK_IMAGES_DIR = Path("/app/feedback_images")

# MIME type → file extension mapping
MIME_TO_EXT = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/heic": ".heic",
    "image/webp": ".webp",
}


class FeedbackResponse(BaseModel):
    feedback_id: str
    status: str


@router.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(
    image: UploadFile = File(...),
    metadata: str = Form(...),
) -> FeedbackResponse:
    """Accept user feedback for a classification result.

    Stores image to disk and metadata to PostgreSQL.
    Returns 200 on success or duplicate (spec D12 — idempotent).
    """
    try:
        meta = json.loads(metadata)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid metadata JSON")

    analysis_id = meta.get("analysis_id")
    if not analysis_id:
        raise HTTPException(status_code=400, detail="Missing analysis_id")

    # Determine file extension from MIME type
    content_type = image.content_type or "image/jpeg"
    ext = MIME_TO_EXT.get(content_type, ".jpg")
    filename = f"{analysis_id}{ext}"

    # Save image to disk
    FEEDBACK_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    image_path = FEEDBACK_IMAGES_DIR / filename
    image_bytes = await image.read()
    image_path.write_bytes(image_bytes)

    # Save metadata to PostgreSQL (ON CONFLICT = idempotent, spec D12)
    feedback_id = meta.get("id", analysis_id)
    try:
        with psycopg2.connect(
            host=settings.postgres_host,
            port=settings.postgres_port,
            dbname=settings.postgres_db,
            user=settings.postgres_user,
            password=settings.postgres_password,
        ) as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO user_feedback
                        (id, analysis_id, user_label, notes, original_label,
                         original_conf, prediction_quality, species, image_path, content_type)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (analysis_id) DO NOTHING
                    """,
                    (
                        feedback_id,
                        analysis_id,
                        meta.get("user_label", ""),
                        meta.get("notes", ""),
                        meta.get("original_label", ""),
                        meta.get("original_confidence", 0),
                        meta.get("prediction_quality", ""),
                        meta.get("species", ""),
                        filename,
                        content_type,
                    ),
                )
    except Exception as e:
        logger.error("Feedback DB save failed: %s", e)
        raise HTTPException(status_code=500, detail="Database error") from e

    return FeedbackResponse(feedback_id=feedback_id, status="saved")
