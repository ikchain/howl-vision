"""
Formal evaluation of vision models (dermatology + parasites) on held-out test sets.

Metrics: accuracy (Wilson CI), F1 macro (bootstrap CI), Cohen's Kappa,
AUROC OvR, Brier multiclass, ECE, per-class P/R/F1, and baselines.
"""

import json
import math
import random
import collections
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch
import torchvision.transforms as T
from PIL import Image
from scipy.stats import norm
from sklearn.metrics import (
    classification_report,
    cohen_kappa_score,
    confusion_matrix,
    f1_score,
    roc_auc_score,
    roc_curve,
)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
SEED = 42
BATCH_SIZE = 32
N_BOOTSTRAP = 1000
ECE_BIN_COUNTS = [5, 10, 15]
CONFIDENCE_BANDS = {"high": 0.80, "medium": 0.50, "low": 0.30, "very_low": 0.0}
TIMM_MODEL_NAME = "tf_efficientnetv2_s.in21k_ft_in1k"
INPUT_SIZE = 384
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DERMA_MODEL_PATH = PROJECT_ROOT / "data/models/vision/vet_dermatology.pt"
PARA_MODEL_PATH = PROJECT_ROOT / "data/models/vision/vet_parasites.pt"
DERMA_TEST_DIR = PROJECT_ROOT / "data/datasets/canine/canine/dermatology/test"
PARA_TEST_DIR = PROJECT_ROOT / "data/datasets/parasites/parasites/test"
FIGURES_DIR = Path(__file__).resolve().parent / "figures"

# ---------------------------------------------------------------------------
# Class mappings — order MUST match model CLASS_NAMES used at training time
# ---------------------------------------------------------------------------

# Dermatology: folder "Hypersensitivity" -> model class index 4
# (model was trained as "Hypersensitivity_Allergic_Dermatitis")
DERMA_CLASS_NAMES = [
    "demodicosis",
    "Dermatitis",
    "Fungal_infections",
    "Healthy",
    "Hypersensitivity_Allergic_Dermatitis",
    "ringworm",
]
DERMA_FOLDER_TO_INDEX = {
    "demodicosis": 0,
    "Dermatitis": 1,
    "Fungal_infections": 2,
    "Healthy": 3,
    "Hypersensitivity": 4,  # folder name differs from model class name
    "ringworm": 5,
}
EXPECTED_COUNTS_DERMA = {
    "demodicosis": 100,
    "Dermatitis": 66,
    "Fungal_infections": 54,
    "Healthy": 69,
    "Hypersensitivity": 29,
    "ringworm": 115,
}

# Parasites: folder names match model class names exactly
PARA_CLASS_NAMES = [
    "Babesia",
    "Leishmania",
    "Leukocyte",
    "Plasmodium",
    "RBCs",
    "Toxoplasma",
    "Trichomonad",
    "Trypanosome",
]
PARA_FOLDER_TO_INDEX = {name: i for i, name in enumerate(PARA_CLASS_NAMES)}
EXPECTED_COUNTS_PARA = {
    "Babesia": 118,
    "Leishmania": 271,
    "Leukocyte": 110,
    "Plasmodium": 85,
    "RBCs": 900,
    "Toxoplasma": 294,
    "Trichomonad": 1015,
    "Trypanosome": 239,
}

# ---------------------------------------------------------------------------
# Reproducibility seeds
# ---------------------------------------------------------------------------
random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)
if torch.cuda.is_available():
    torch.cuda.manual_seed_all(SEED)

# ---------------------------------------------------------------------------
# Task 1 -- Model loading + test-set loading
# ---------------------------------------------------------------------------


def load_classification_model(model_path: Path, n_classes: int):
    """Load an EfficientNetV2-S checkpoint and return (model, device).

    The checkpoint dict is expected to have a 'model_state_dict' key, which is
    the convention used throughout this project's training pipeline.
    """
    import timm  # local import -- timm only needed in the evaluation venv

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    model = timm.create_model(
        TIMM_MODEL_NAME,
        pretrained=False,
        num_classes=n_classes,
    )

    # weights_only=False required for checkpoints that include numpy scalars
    # (PyTorch 2.6+ changed the default to True). These are our own checkpoints.
    checkpoint = torch.load(model_path, map_location=device, weights_only=False)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()
    model.to(device)

    print(f"[load_classification_model] Loaded {model_path.name} -> device={device}")
    return model, device


def load_test_images(
    test_dir: Path,
    folder_to_index: dict,
    expected_counts: dict,
):
    """Collect image paths + integer labels using an explicit folder-to-index map.

    Using explicit mapping (NOT ImageFolder) because alphabetical class ordering
    from ImageFolder would silently mismatch the model's training-time ordering.

    Returns:
        image_paths: list of Path objects
        y_true: np.ndarray of int labels (shape [N])
        transform: torchvision Compose ready for inference
    """
    image_paths = []
    labels = []
    actual_counts: dict = {}

    for folder_name, class_idx in folder_to_index.items():
        folder = test_dir / folder_name
        if not folder.is_dir():
            raise FileNotFoundError(f"Test folder not found: {folder}")

        imgs = sorted(
            p for p in folder.iterdir()
            if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"}
        )
        actual_counts[folder_name] = len(imgs)
        image_paths.extend(imgs)
        labels.extend([class_idx] * len(imgs))
        print(f"  {folder_name:<40} {len(imgs):>5} images  (idx={class_idx})")

    # Guard: counts must exactly match expectations so we catch dataset drift
    for folder_name, expected in expected_counts.items():
        actual = actual_counts[folder_name]
        assert actual == expected, (
            f"Count mismatch for '{folder_name}': expected {expected}, got {actual}"
        )

    transform = T.Compose([
        T.Resize((INPUT_SIZE, INPUT_SIZE)),
        T.ToTensor(),
        T.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
    ])

    y_true = np.array(labels, dtype=np.int64)
    print(f"  Total: {len(image_paths)} images, {len(folder_to_index)} classes")
    return image_paths, y_true, transform


# ---------------------------------------------------------------------------
# Task 2 -- Inference loop
# ---------------------------------------------------------------------------


@torch.no_grad()
def run_inference(
    model,
    device,
    image_paths: list,
    transform,
    batch_size: int = BATCH_SIZE,
):
    """Run batched inference and return (y_pred, softmax_probs) as numpy arrays.

    Images are opened as RGB to handle RGBA PNGs and grayscale files uniformly.
    Progress is printed every 10 batches to give feedback on long test sets.
    """
    all_probs = []
    n_batches = math.ceil(len(image_paths) / batch_size)

    for batch_idx in range(n_batches):
        start = batch_idx * batch_size
        end = min(start + batch_size, len(image_paths))
        batch_paths = image_paths[start:end]

        tensors = []
        for p in batch_paths:
            img = Image.open(p).convert("RGB")
            tensors.append(transform(img))
        batch_tensor = torch.stack(tensors).to(device)  # (B, C, H, W)

        logits = model(batch_tensor)
        probs = torch.softmax(logits, dim=1)
        all_probs.append(probs.cpu().numpy())

        if (batch_idx + 1) % 10 == 0 or (batch_idx + 1) == n_batches:
            print(
                f"  Batch {batch_idx + 1}/{n_batches} "
                f"({end}/{len(image_paths)} images)"
            )

    softmax_probs = np.concatenate(all_probs, axis=0)  # (N, C)
    y_pred = np.argmax(softmax_probs, axis=1)           # (N,)
    return y_pred, softmax_probs


# ---------------------------------------------------------------------------
# Task 3 -- Core metrics
# ---------------------------------------------------------------------------


def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple:
    """Wilson score confidence interval for a proportion k/n.

    Preferred over normal approximation because it stays within [0,1] even for
    extreme proportions and small sample sizes (Wilson 1927).
    """
    if n == 0:
        return 0.0, 0.0
    p_hat = k / n
    denominator = 1 + z**2 / n
    centre = (p_hat + z**2 / (2 * n)) / denominator
    margin = (z * math.sqrt(p_hat * (1 - p_hat) / n + z**2 / (4 * n**2))) / denominator
    lo = max(0.0, centre - margin)
    hi = min(1.0, centre + margin)
    return round(lo, 4), round(hi, 4)


def bootstrap_f1_macro(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    n_classes: int,
    B: int = N_BOOTSTRAP,
) -> tuple:
    """Stratified bootstrap 95% CI for macro-F1.

    Resamples within each class independently (stratified) so that class
    representation is preserved even on imbalanced datasets. Classes that
    happen to draw 0 samples in an iteration contribute F1=0 for that class.
    """
    rng = np.random.RandomState(SEED)

    # Pre-group indices by class for fast stratified sampling
    class_indices = defaultdict(list)
    for i, label in enumerate(y_true):
        class_indices[label].append(i)

    boot_scores = []
    for _ in range(B):
        boot_idx = []
        for c in range(n_classes):
            idx = class_indices[c]
            if len(idx) == 0:
                continue
            sampled = rng.choice(idx, size=len(idx), replace=True)
            boot_idx.extend(sampled.tolist())

        bt = y_true[boot_idx]
        bp = y_pred[boot_idx]

        # Classes absent from bt get per-class F1=0 via zero_division=0
        score = f1_score(bt, bp, average="macro", labels=list(range(n_classes)), zero_division=0)
        boot_scores.append(score)

    ci_lo = float(np.percentile(boot_scores, 2.5))
    ci_hi = float(np.percentile(boot_scores, 97.5))
    return round(ci_lo, 4), round(ci_hi, 4)


def brier_multiclass(
    y_true: np.ndarray,
    softmax_probs: np.ndarray,
    n_classes: int,
) -> float:
    """Multiclass Brier score (Brier 1950).

    BS = (1/N) * sum_i sum_k (p_ik - o_ik)^2

    sklearn's brier_score_loss is binary-only. Lower is better (0 = perfect).
    """
    n = len(y_true)
    # One-hot encode ground truth
    y_onehot = np.zeros((n, n_classes), dtype=np.float32)
    y_onehot[np.arange(n), y_true] = 1.0

    diff = softmax_probs - y_onehot
    brier = float(np.mean(np.sum(diff**2, axis=1)))
    return round(brier, 4)


def compute_classification_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    softmax_probs: np.ndarray,
    class_names: list,
) -> dict:
    """Compute the full metrics suite for one model evaluation.

    Returns a flat dict suitable for JSON serialisation.
    """
    n = len(y_true)
    n_classes = len(class_names)
    labels = list(range(n_classes))

    # ------------------------------------------------------------------
    # Accuracy + Wilson CI
    # ------------------------------------------------------------------
    n_correct = int(np.sum(y_true == y_pred))
    accuracy = round(n_correct / n, 4)
    acc_ci_lo, acc_ci_hi = wilson_ci(n_correct, n)

    # ------------------------------------------------------------------
    # F1 scores
    # ------------------------------------------------------------------
    f1_macro = round(float(f1_score(y_true, y_pred, average="macro", labels=labels, zero_division=0)), 4)
    f1_weighted = round(float(f1_score(y_true, y_pred, average="weighted", labels=labels, zero_division=0)), 4)
    f1_ci_lo, f1_ci_hi = bootstrap_f1_macro(y_true, y_pred, n_classes)

    # ------------------------------------------------------------------
    # Cohen's Kappa
    # ------------------------------------------------------------------
    kappa = round(float(cohen_kappa_score(y_true, y_pred, labels=labels)), 4)

    # ------------------------------------------------------------------
    # AUROC macro OvR (may fail if a class has 0 positive samples)
    # ------------------------------------------------------------------
    try:
        auroc = round(float(roc_auc_score(y_true, softmax_probs, multi_class="ovr", average="macro")), 4)
    except ValueError as exc:
        auroc = None
        print(f"  [AUROC] skipped: {exc}")

    # ------------------------------------------------------------------
    # Brier score (multiclass, not sklearn binary)
    # ------------------------------------------------------------------
    brier = brier_multiclass(y_true, softmax_probs, n_classes)

    # ------------------------------------------------------------------
    # Per-class precision / recall / F1 + Wilson CI on recall + support
    # ------------------------------------------------------------------
    report = classification_report(
        y_true, y_pred, labels=labels, target_names=class_names, output_dict=True, zero_division=0
    )
    per_class = {}
    for cls_name in class_names:
        r = report[cls_name]
        support = int(r["support"])
        recall = r["recall"]
        n_tp = round(recall * support)  # approximate TP count
        ci_lo, ci_hi = wilson_ci(n_tp, support)
        per_class[cls_name] = {
            "precision": round(r["precision"], 4),
            "recall": round(recall, 4),
            "f1": round(r["f1-score"], 4),
            "support": support,
            "recall_ci_lo": ci_lo,
            "recall_ci_hi": ci_hi,
        }

    # ------------------------------------------------------------------
    # Baselines
    # ------------------------------------------------------------------
    counts = np.bincount(y_true, minlength=n_classes)
    majority_class = int(np.argmax(counts))
    y_majority = np.full(n, majority_class, dtype=np.int64)
    f1_majority = round(float(f1_score(y_true, y_majority, average="macro", labels=labels, zero_division=0)), 4)

    y_random_uniform = np.random.randint(0, n_classes, size=n)
    f1_random_uniform = round(float(f1_score(y_true, y_random_uniform, average="macro", labels=labels, zero_division=0)), 4)

    class_probs = counts / counts.sum()
    y_random_prop = np.array([np.random.choice(labels, p=class_probs) for _ in range(n)])
    f1_random_prop = round(float(f1_score(y_true, y_random_prop, average="macro", labels=labels, zero_division=0)), 4)

    return {
        "n_samples": n,
        "n_classes": n_classes,
        "accuracy": accuracy,
        "accuracy_ci_lo": acc_ci_lo,
        "accuracy_ci_hi": acc_ci_hi,
        "f1_macro": f1_macro,
        "f1_macro_ci_lo": f1_ci_lo,
        "f1_macro_ci_hi": f1_ci_hi,
        "f1_weighted": f1_weighted,
        "cohen_kappa": kappa,
        "auroc_macro_ovr": auroc,
        "brier_multiclass": brier,
        "per_class": per_class,
        "baselines": {
            "majority_f1_macro": f1_majority,
            "random_uniform_f1_macro": f1_random_uniform,
            "random_proportional_f1_macro": f1_random_prop,
        },
    }
