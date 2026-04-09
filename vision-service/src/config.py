import os

# Paths — montados via docker-compose volume
MODELS_DIR = os.getenv("VISION_MODELS_DIR", "/app/models/vision")
DERMATOLOGY_CHECKPOINT = os.path.join(MODELS_DIR, "vet_dermatology.pt")
FELINE_DERMATOLOGY_CHECKPOINT = os.path.join(MODELS_DIR, "vet_feline_dermatology.pt")
PARASITES_CHECKPOINT = os.path.join(MODELS_DIR, "vet_parasites.pt")
SEGMENTATION_CHECKPOINT = os.path.join(MODELS_DIR, "vet_segmentation.pt")

# Segmentación corre en CPU para no competir con Ollama por VRAM
SEGMENTATION_DEVICE = os.getenv("VISION_SEGMENTATION_DEVICE", "cpu")

# Clasificadores usan GPU si hay disponible
CLASSIFICATION_DEVICE = os.getenv("VISION_CLASSIFICATION_DEVICE", "cuda")

# Confianza mínima para incluir una predicción en el response
MIN_CONFIDENCE = 0.1
TOP_K = 5

# Preprocess — EfficientNetV2-S fue entrenado con ImageNet stats
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]
CLASSIFICATION_INPUT_SIZE = 384

# Prediction quality thresholds (spec D1, D7).
# Synced with frontend/src/lib/onnx.ts — update both together.
CONFIDENT_THRESHOLD = 0.80
INCONCLUSIVE_THRESHOLD = 0.50
SEGMENTATION_INPUT_SIZE = 256
