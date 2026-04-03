"""Segmentation model — UNet with EfficientNet-B0 encoder via smp.

Runs on CPU to avoid competing with Ollama for VRAM (spec section 15).
"""

import base64
import io
import time

import numpy as np
import segmentation_models_pytorch as smp
import torch
from PIL import Image
from torchvision import transforms as T

from src.config import SEGMENTATION_CHECKPOINT, SEGMENTATION_DEVICE, SEGMENTATION_INPUT_SIZE


class SegmentationModel:
    CLASS_NAMES = ["background", "spinal_cord"]

    def __init__(self) -> None:
        self._model: torch.nn.Module | None = None
        self._transform: T.Compose | None = None
        self._loaded = False

    @property
    def loaded(self) -> bool:
        return self._loaded

    def load(self) -> None:
        device = torch.device(SEGMENTATION_DEVICE)

        model = smp.Unet(
            encoder_name="efficientnet-b0",
            encoder_weights=None,  # Loading our own weights
            in_channels=1,
            classes=2,
            activation=None,
        )

        checkpoint = torch.load(
            SEGMENTATION_CHECKPOINT, map_location=device, weights_only=False
        )
        model.load_state_dict(checkpoint["model_state_dict"])
        model.to(device)
        model.eval()

        self._model = model
        self._device = device
        self._transform = T.Compose([
            T.Resize((SEGMENTATION_INPUT_SIZE, SEGMENTATION_INPUT_SIZE)),
            T.ToTensor(),  # PIL → float32 [0,1], CHW
        ])
        self._loaded = True

    def predict(self, image: Image.Image, threshold: float = 0.5) -> dict:
        if not self._loaded:
            raise RuntimeError("SegmentationModel not loaded")

        start = time.perf_counter()

        # Grayscale — the model expects 1 channel
        gray = image.convert("L")
        tensor = self._transform(gray).unsqueeze(0).to(self._device)

        with torch.no_grad():
            logits = self._model(tensor)
            # Channel 1 = spinal_cord probability
            probs = torch.sigmoid(logits[:, 1, :, :])
            mask = (probs > threshold).cpu().numpy().astype(np.uint8)[0] * 255

        # Encode mask as PNG base64
        mask_image = Image.fromarray(mask, mode="L")
        buf = io.BytesIO()
        mask_image.save(buf, format="PNG")
        mask_b64 = base64.b64encode(buf.getvalue()).decode("ascii")

        classes_found = ["spinal_cord"] if mask.any() else []

        elapsed_ms = round((time.perf_counter() - start) * 1000, 1)

        return {
            "mask_base64": mask_b64,
            "classes_found": classes_found,
            "processing_time_ms": elapsed_ms,
        }
