"""Base class for vision model inference.

Shared pattern: load checkpoint once at startup, preprocess PIL image,
run forward pass, postprocess logits into structured predictions.
"""

import time
from abc import ABC, abstractmethod

import numpy as np
import timm
import torch
import torch.nn.functional as F
from PIL import Image
from torchvision import transforms as T

from src.config import (
    CLASSIFICATION_INPUT_SIZE,
    IMAGENET_MEAN,
    IMAGENET_STD,
    MIN_CONFIDENCE,
    TOP_K,
)


class ClassificationModel(ABC):
    """EfficientNetV2-S classifier loaded from a .pt checkpoint."""

    # Subclasses define these
    CLASS_NAMES: list[str]
    CHECKPOINT_PATH: str
    DEVICE: str

    def __init__(self) -> None:
        self._model: torch.nn.Module | None = None
        self._transform: T.Compose | None = None
        self._loaded = False

    @property
    def loaded(self) -> bool:
        return self._loaded

    def load(self) -> None:
        device = torch.device(self.DEVICE if torch.cuda.is_available() else "cpu")

        model = timm.create_model(
            "tf_efficientnetv2_s.in21k_ft_in1k",
            pretrained=False,
            num_classes=len(self.CLASS_NAMES),
        )

        checkpoint = torch.load(
            self.CHECKPOINT_PATH, map_location=device, weights_only=False
        )
        model.load_state_dict(checkpoint["model_state_dict"])
        model.to(device)
        model.eval()

        self._model = model
        self._device = device
        self._transform = T.Compose([
            T.Resize((CLASSIFICATION_INPUT_SIZE, CLASSIFICATION_INPUT_SIZE)),
            T.ToTensor(),  # PIL → float32 [0,1], CHW
            T.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
        ])
        self._loaded = True

    def predict(self, image: Image.Image, top_k: int = TOP_K) -> dict:
        if not self._loaded:
            raise RuntimeError(f"{self.__class__.__name__} not loaded")

        start = time.perf_counter()

        tensor = self._transform(image.convert("RGB")).unsqueeze(0).to(self._device)

        with torch.no_grad():
            logits = self._model(tensor)
            probs = F.softmax(logits, dim=1)[0].cpu().float().numpy()

        # Top-K predictions sorted by probability
        top_indices = np.argsort(probs)[::-1][:top_k]
        predictions = []
        for idx in top_indices:
            prob = float(probs[idx])
            if prob < MIN_CONFIDENCE:
                break
            predictions.append({
                "class": self.CLASS_NAMES[idx],
                "probability": round(prob, 4),
                "confidence_level": _confidence_level(prob),
            })

        elapsed_ms = round((time.perf_counter() - start) * 1000, 1)

        return {
            "predictions": predictions,
            "processing_time_ms": elapsed_ms,
        }


def _confidence_level(prob: float) -> str:
    if prob >= 0.8:
        return "high"
    if prob >= 0.5:
        return "medium"
    if prob >= 0.3:
        return "low"
    return "very_low"
