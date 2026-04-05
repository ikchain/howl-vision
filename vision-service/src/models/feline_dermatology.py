from src.config import CLASSIFICATION_DEVICE, FELINE_DERMATOLOGY_CHECKPOINT
from src.models.base import ClassificationModel


class FelineDermatologyModel(ClassificationModel):
    CLASS_NAMES = [
        "Flea_Allergy",
        "Health",
        "Ringworm",
        "Scabies",
    ]
    CHECKPOINT_PATH = FELINE_DERMATOLOGY_CHECKPOINT
    DEVICE = CLASSIFICATION_DEVICE
