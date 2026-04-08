from src.config import CLASSIFICATION_DEVICE, FELINE_DERMATOLOGY_CHECKPOINT
from src.models.base import ClassificationModel


class FelineDermatologyModel(ClassificationModel):
    # Index order matches the training folder order in
    # training/train_feline_dermatology.py. The training folder was
    # named "Health" (legacy) but the rendered label surfaces to users
    # as the result of a clinical classification — "Healthy" reads as
    # a prediction, "Health" reads like a form field. The weights are
    # indexed by position, not by string, so renaming the label is a
    # metadata-only change with no effect on inference.
    CLASS_NAMES = [
        "Flea_Allergy",
        "Healthy",
        "Ringworm",
        "Scabies",
    ]
    CHECKPOINT_PATH = FELINE_DERMATOLOGY_CHECKPOINT
    DEVICE = CLASSIFICATION_DEVICE
