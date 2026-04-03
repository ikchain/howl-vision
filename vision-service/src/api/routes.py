import logging

from fastapi import APIRouter, File, HTTPException, UploadFile
from PIL import Image

from src.models.dermatology import DermatologyModel
from src.models.parasites import ParasitesModel
from src.models.segmentation import SegmentationModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/vision")

# Singletons — populated by main.py on startup
dermatology_model: DermatologyModel | None = None
parasites_model: ParasitesModel | None = None
segmentation_model: SegmentationModel | None = None


def _read_image(file: UploadFile) -> Image.Image:
    try:
        return Image.open(file.file)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid image file")


@router.post("/dermatology")
async def classify_dermatology(file: UploadFile = File(...)):
    if not dermatology_model or not dermatology_model.loaded:
        raise HTTPException(status_code=503, detail="Dermatology model not loaded")
    image = _read_image(file)
    return dermatology_model.predict(image)


@router.post("/parasites")
async def classify_parasites(file: UploadFile = File(...)):
    if not parasites_model or not parasites_model.loaded:
        raise HTTPException(status_code=503, detail="Parasites model not loaded")
    image = _read_image(file)
    return parasites_model.predict(image)


@router.post("/segment")
async def segment_image(file: UploadFile = File(...)):
    if not segmentation_model or not segmentation_model.loaded:
        raise HTTPException(status_code=503, detail="Segmentation model not loaded")
    image = _read_image(file)
    return segmentation_model.predict(image)
