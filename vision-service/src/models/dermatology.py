from src.config import CLASSIFICATION_DEVICE, DERMATOLOGY_CHECKPOINT
from src.models.base import ClassificationModel


class DermatologyModel(ClassificationModel):
    CLASS_NAMES = [
        "demodicosis",
        "Dermatitis",
        "Fungal_infections",
        "Healthy",
        "Hypersensitivity_Allergic_Dermatitis",
        "ringworm",
    ]
    CHECKPOINT_PATH = DERMATOLOGY_CHECKPOINT
    DEVICE = CLASSIFICATION_DEVICE
