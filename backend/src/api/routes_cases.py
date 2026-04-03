from fastapi import APIRouter, Query

from src.rag.search import semantic_search

router = APIRouter(prefix="/api/v1")


@router.get("/cases/search")
async def search_cases(
    q: str = Query(..., min_length=1, max_length=500),
    limit: int = Query(5, ge=1, le=20),
    source: str | None = Query(None),
    record_type: str | None = Query(None),
):
    results = await semantic_search(
        query=q, limit=limit, source=source, record_type=record_type
    )
    return {"results": results, "count": len(results)}
