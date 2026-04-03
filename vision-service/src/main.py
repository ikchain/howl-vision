import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.api import routes
from src.models.dermatology import DermatologyModel
from src.models.parasites import ParasitesModel
from src.models.segmentation import SegmentationModel
from src.rag.embedder import SapBERTEmbedder

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load all models once at startup."""
    logger.info("Loading vision models...")

    routes.dermatology_model = DermatologyModel()
    routes.parasites_model = ParasitesModel()
    routes.segmentation_model = SegmentationModel()

    try:
        routes.dermatology_model.load()
        logger.info("Dermatology model loaded")
    except Exception:
        logger.exception("Failed to load dermatology model")

    try:
        routes.parasites_model.load()
        logger.info("Parasites model loaded")
    except Exception:
        logger.exception("Failed to load parasites model")

    try:
        routes.segmentation_model.load()
        logger.info("Segmentation model loaded")
    except Exception:
        logger.exception("Failed to load segmentation model")

    try:
        routes.sapbert_embedder = SapBERTEmbedder.get()
        logger.info("SapBERT embedder loaded")
    except Exception:
        logger.exception("Failed to load SapBERT embedder")

    logger.info("Vision service ready")
    yield


app = FastAPI(
    title="Howl Vision — Vision Service",
    version="0.1.0",
    description="Specialized vision model serving for veterinary image analysis",
    lifespan=lifespan,
)

app.include_router(routes.router)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "vision-service",
        "models": {
            "dermatology": routes.dermatology_model.loaded if routes.dermatology_model else False,
            "parasites": routes.parasites_model.loaded if routes.parasites_model else False,
            "segmentation": routes.segmentation_model.loaded if routes.segmentation_model else False,
            "sapbert": routes.sapbert_embedder.loaded if routes.sapbert_embedder else False,
        },
    }
