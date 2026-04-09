"""Tool executor — dispatches Gemma 4 tool_calls to real functions/endpoints.

Handles parallel execution, image format conversion, error encapsulation,
and low-confidence annotation for vision results.
"""

import asyncio
import base64
import io
import json
import logging

import httpx

from src.clinical.pharma import calculate_dosage, check_drug_interactions
from src.config import settings
from src.rag.search import semantic_search

logger = logging.getLogger(__name__)


def _b64_to_upload_file(image_b64: str) -> tuple[str, bytes, str]:
    """Convert base64 string to (filename, bytes, content_type) for httpx upload."""
    if "," in image_b64:
        header, data = image_b64.split(",", 1)
        if "png" in header:
            content_type, ext = "image/png", "png"
        elif "gif" in header:
            content_type, ext = "image/gif", "gif"
        else:
            content_type, ext = "image/jpeg", "jpg"
    else:
        data = image_b64
        content_type, ext = "image/jpeg", "jpg"

    image_bytes = base64.b64decode(data)
    return (f"image.{ext}", image_bytes, content_type)


async def _call_vision_endpoint(endpoint: str, image_b64: str) -> dict:
    """POST image to vision-service and return JSON result."""
    filename, image_bytes, content_type = _b64_to_upload_file(image_b64)
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{settings.vision_service_url.rstrip('/')}{endpoint}",
            files={"file": (filename, io.BytesIO(image_bytes), content_type)},
        )
        resp.raise_for_status()
        return resp.json()


def _annotate_confidence(result: dict) -> None:
    """Flag low-confidence vision predictions so Gemma can interpret them."""
    threshold = settings.agent_vision_confidence_threshold
    preds = result.get("predictions")
    if preds and preds[0].get("probability", 1.0) < threshold:
        result["low_confidence"] = True
        result["low_confidence_note"] = (
            f"Top prediction probability ({preds[0]['probability']:.0%}) is below "
            f"the {threshold:.0%} confidence threshold. "
            "Recommend specialist review or laboratory confirmation."
        )


# -- Individual tool handlers --

async def _exec_classify_dermatology(args: dict, image_b64: str | None) -> dict:
    if not image_b64:
        return {"error": "No image provided for dermatology classification."}
    result = await _call_vision_endpoint("/vision/dermatology", image_b64)
    _annotate_confidence(result)
    return result


async def _exec_detect_parasites(args: dict, image_b64: str | None) -> dict:
    if not image_b64:
        return {"error": "No image provided for parasite detection."}
    result = await _call_vision_endpoint("/vision/parasites", image_b64)
    _annotate_confidence(result)
    return result


async def _exec_segment_ultrasound(args: dict, image_b64: str | None) -> dict:
    if not image_b64:
        return {"error": "No image provided for ultrasound segmentation."}
    return await _call_vision_endpoint("/vision/segment", image_b64)


async def _exec_search_clinical_cases(args: dict, image_b64: str | None) -> dict:
    query = args.get("query", "")
    limit = min(int(args.get("limit", 5)), 10)
    if not query:
        return {"error": "Query is required for clinical case search."}
    results = await semantic_search(query=query, limit=limit)
    return {"cases": results, "count": len(results)}


async def _exec_calculate_dosage(args: dict, image_b64: str | None) -> dict:
    drug = args.get("drug", "")
    weight_kg = args.get("weight_kg")
    species = args.get("species", "")
    if not all([drug, weight_kg, species]):
        return {"error": "drug, weight_kg, and species are all required."}
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, calculate_dosage, drug, float(weight_kg), species
    )


async def _exec_check_drug_interactions(args: dict, image_b64: str | None) -> dict:
    drug_a = args.get("drug_a", "")
    drug_b = args.get("drug_b", "")
    if not all([drug_a, drug_b]):
        return {"error": "Both drug_a and drug_b are required."}
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, check_drug_interactions, drug_a, drug_b
    )


TOOL_DISPATCH: dict[str, callable] = {
    "classify_dermatology": _exec_classify_dermatology,
    "detect_parasites": _exec_detect_parasites,
    "segment_ultrasound": _exec_segment_ultrasound,
    "search_clinical_cases": _exec_search_clinical_cases,
    "calculate_dosage": _exec_calculate_dosage,
    "check_drug_interactions": _exec_check_drug_interactions,
}


async def execute_tool_calls(
    tool_calls: list,
    image_b64: str | None,
) -> dict[str, dict]:
    """Execute all tool_calls in parallel. Returns {call_id: result_dict}.

    Never raises — errors are encapsulated in the result dict so Gemma
    can reason about failures.
    """

    async def _execute_one(call) -> tuple[str, dict]:
        call_id = getattr(call, "id", None) or "unknown"
        name = call.function.name
        args = call.function.arguments

        if name not in TOOL_DISPATCH:
            logger.warning("Unknown tool '%s' requested by Gemma", name)
            return call_id, {
                "error": f"Tool '{name}' is not available.",
                "available_tools": list(TOOL_DISPATCH.keys()),
            }

        try:
            result = await TOOL_DISPATCH[name](args, image_b64)
        except httpx.HTTPStatusError as e:
            logger.error("HTTP error calling tool '%s': %s", name, e)
            result = {"error": f"Vision service returned HTTP {e.response.status_code}.", "tool": name}
        except httpx.TimeoutException:
            logger.error("Timeout calling tool '%s'", name)
            result = {"error": f"Tool '{name}' timed out.", "tool": name}
        except Exception as e:
            logger.exception("Unexpected error in tool '%s'", name)
            result = {"error": f"Internal error in '{name}': {str(e)}", "tool": name}

        return call_id, result

    pairs = await asyncio.gather(*[_execute_one(c) for c in tool_calls])
    return dict(pairs)


async def generate_narrative(
    label: str,
    confidence: float,
    differentials: list,
    species: str,
    module: str,
    caution_mode: bool = False,
) -> str:
    """Generate a clinical narrative from classification results using Gemma 4.

    Uses httpx to call the Ollama /api/chat endpoint so the URL from
    settings.ollama_base_url is respected (required when Ollama runs on a
    different host than the backend, reached over a configurable URL).
    """
    diff_text = (
        ", ".join(d.get("label", "") for d in differentials[:3])
        if differentials
        else "none"
    )

    if caution_mode:
        prompt = (
            f"Species: {species}. Module: {module}.\n"
            f"Automated classification result: {label} ({confidence * 100:.0f}% model score).\n"
            f"Top differentials: {diff_text}.\n\n"
            f"IMPORTANT: The model confidence is LOW. Lead your assessment with "
            f"uncertainty. Do not anchor on the top classification — give equal "
            f"weight to differentials. Emphasize that veterinary confirmation is "
            f"essential before any action. Provide a structured clinical assessment: "
            f"findings, differential considerations, and recommended next steps."
        )
    else:
        prompt = (
            f"Species: {species}. Module: {module}.\n"
            f"Automated classification result: {label} ({confidence * 100:.0f}% model score).\n"
            f"Top differentials: {diff_text}.\n\n"
            f"Provide a structured clinical assessment: findings, differential diagnosis, "
            f"and recommended next steps. Be concise. Use veterinary terminology. "
            f"State that this classification requires veterinary confirmation."
        )

    payload = {
        "model": settings.ollama_model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are Howl Vision, a veterinary AI copilot. "
                    "Provide structured clinical assessments based on automated "
                    "classification results. Always state that findings require "
                    "veterinary confirmation. Never use the word 'diagnosis' — "
                    "use 'classification result' or 'assessment'."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "stream": False,
    }

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{settings.ollama_base_url.rstrip('/')}/api/chat",
                json=payload,
            )
            resp.raise_for_status()
            return resp.json()["message"]["content"]
    except httpx.HTTPStatusError as e:
        logger.error("Narrative Ollama HTTP %s: %s", e.response.status_code, e.response.text[:500])
    except Exception as e:
        logger.error("Narrative generation failed: %s", e)
        return (
            f"**Classification:** {label} ({confidence * 100:.0f}% model score)\n\n"
            "*Narrative generation unavailable. Please consult a veterinarian.*"
        )
