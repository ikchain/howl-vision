from src.config import CLASSIFICATION_DEVICE, PARASITES_CHECKPOINT
from src.models.base import ClassificationModel


class ParasitesModel(ClassificationModel):
    CLASS_NAMES = [
        "Babesia",
        "Leishmania",
        "Leukocyte",
        "Plasmodium",
        "RBCs",
        "Toxoplasma",
        "Trichomonad",
        "Trypanosome",
    ]
    CHECKPOINT_PATH = PARASITES_CHECKPOINT
    DEVICE = CLASSIFICATION_DEVICE
