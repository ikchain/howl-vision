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


# ---------------------------------------------------------------------------
# Task 4 -- Calibration metrics
# ---------------------------------------------------------------------------


def compute_calibration(
    y_true: np.ndarray,
    softmax_probs: np.ndarray,
    n_classes: int,
) -> dict:
    """Compute calibration metrics: ECE at multiple bin counts, per-confidence-band
    accuracy, and selective prediction curve.

    ECE sensitivity is checked at 5, 10, and 15 bins. Bins with fewer than 10
    samples are excluded from the weighted ECE sum (they are unreliable) but
    kept in the output for inspection.

    Selective prediction curve measures accuracy when the model is only asked to
    predict on the samples it is most confident about — a proxy for real-world
    triage where low-confidence cases are escalated to a human.
    """
    max_probs = softmax_probs.max(axis=1)                              # (N,)
    y_argmax = softmax_probs.argmax(axis=1)
    correct = (y_argmax == y_true).astype(float)                       # (N,)
    n = len(y_true)

    # ------------------------------------------------------------------
    # ECE at multiple bin counts (sensitivity check)
    # ------------------------------------------------------------------
    ece_results: dict = {}
    bin_details_10: list = []

    for n_bins in ECE_BIN_COUNTS:
        bin_edges = np.linspace(0.0, 1.0, n_bins + 1)
        ece_accum = 0.0
        mce = 0.0
        bins: list = []

        for b in range(n_bins):
            lo, hi = bin_edges[b], bin_edges[b + 1]
            # Use half-open intervals [lo, hi) except the last bin which is [lo, hi]
            if b < n_bins - 1:
                mask = (max_probs >= lo) & (max_probs < hi)
            else:
                mask = (max_probs >= lo) & (max_probs <= hi)

            n_bin = int(mask.sum())
            excluded = n_bin < 10

            if n_bin > 0:
                avg_confidence = float(max_probs[mask].mean())
                avg_accuracy = float(correct[mask].mean())
            else:
                avg_confidence = float((lo + hi) / 2)
                avg_accuracy = 0.0

            gap = abs(avg_confidence - avg_accuracy)

            if not excluded:
                ece_accum += (n_bin / n) * gap
                mce = max(mce, gap)

            bin_info = {
                "bin_lower": round(lo, 4),
                "bin_upper": round(hi, 4),
                "n": n_bin,
                "avg_confidence": round(avg_confidence, 4),
                "avg_accuracy": round(avg_accuracy, 4),
                "gap": round(gap, 4),
                "excluded": excluded,
            }
            bins.append(bin_info)

        ece_results[f"ece_{n_bins}bins"] = round(ece_accum, 4)

        if n_bins == 10:
            ece_results["mce_10bins"] = round(mce, 4)
            bin_details_10 = bins

    ece_results["bin_details_10bins"] = bin_details_10

    # ------------------------------------------------------------------
    # Per-band accuracy (production confidence bands)
    # Bands defined in CONFIDENCE_BANDS; processed high → low so each
    # sample falls into exactly one band.
    # ------------------------------------------------------------------
    # Band midpoints used for calibration_gap (gap = midpoint - accuracy)
    band_midpoints = {
        "high": 0.90,    # [0.80, 1.00] midpoint
        "medium": 0.65,  # [0.50, 0.80) midpoint
        "low": 0.40,     # [0.30, 0.50) midpoint
        "very_low": 0.15,  # [0.00, 0.30) midpoint
    }

    band_thresholds = [
        ("high",     CONFIDENCE_BANDS["high"]),     # >= 0.80
        ("medium",   CONFIDENCE_BANDS["medium"]),   # >= 0.50
        ("low",      CONFIDENCE_BANDS["low"]),       # >= 0.30
        ("very_low", CONFIDENCE_BANDS["very_low"]), # >= 0.00 (catch-all)
    ]

    per_band: dict = {}
    for band_name, threshold in band_thresholds:
        if band_name == "high":
            mask = max_probs >= threshold
        elif band_name == "medium":
            mask = (max_probs >= threshold) & (max_probs < CONFIDENCE_BANDS["high"])
        elif band_name == "low":
            mask = (max_probs >= threshold) & (max_probs < CONFIDENCE_BANDS["medium"])
        else:  # very_low
            mask = max_probs < CONFIDENCE_BANDS["low"]

        n_band = int(mask.sum())
        accuracy_band = float(correct[mask].mean()) if n_band > 0 else 0.0
        midpoint = band_midpoints[band_name]
        calibration_gap = round(midpoint - accuracy_band, 4)

        per_band[band_name] = {
            "n": n_band,
            "accuracy": round(accuracy_band, 4),
            "calibration_gap": calibration_gap,
        }

    # ------------------------------------------------------------------
    # Selective prediction curve
    # Sort by descending confidence; at each coverage threshold compute
    # accuracy on the top-N most confident predictions.
    # ------------------------------------------------------------------
    coverages = [1.0, 0.95, 0.90, 0.85, 0.80, 0.75, 0.70, 0.65, 0.60, 0.50]
    sorted_idx = np.argsort(-max_probs)  # descending confidence order
    sorted_correct = correct[sorted_idx]

    selective_curve: list = []
    for cov in coverages:
        keep_n = int(len(sorted_correct) * cov)
        # Always keep at least 1 sample
        keep_n = max(keep_n, 1)
        acc_at_cov = float(sorted_correct[:keep_n].mean())
        selective_curve.append([round(cov, 2), round(acc_at_cov, 4)])

    return {
        **ece_results,
        "per_band": per_band,
        "selective_prediction_curve": selective_curve,
    }


# ---------------------------------------------------------------------------
# Task 5 -- Visualization functions
# ---------------------------------------------------------------------------


def plot_confusion_matrix(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    class_names: list,
    title: str,
    save_path: Path,
) -> None:
    """Side-by-side confusion matrix: normalised (recall) + raw counts.

    Normalised matrix uses row-wise (per-true-class) normalisation so each row
    sums to 1 and the diagonal reads as per-class recall. Raw counts are shown
    alongside so the absolute sample sizes remain visible.
    """
    cm_raw = confusion_matrix(y_true, y_pred, labels=list(range(len(class_names))))
    # Row-wise normalisation: recall matrix. Avoid divide-by-zero for absent classes.
    row_sums = cm_raw.sum(axis=1, keepdims=True)
    cm_norm = np.where(row_sums > 0, cm_raw / row_sums, 0.0)

    fig, axes = plt.subplots(1, 2, figsize=(16, 7))
    fig.suptitle(title, fontsize=13, y=1.01)

    for ax, data, subtitle, fmt_float in [
        (axes[0], cm_norm, "Normalised (recall)", True),
        (axes[1], cm_raw,  "Raw counts",          False),
    ]:
        kwargs = dict(
            cmap="Blues",
            aspect="auto",
        )
        if fmt_float:
            kwargs["vmin"] = 0.0
            kwargs["vmax"] = 1.0

        im = ax.imshow(data, **kwargs)
        plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

        ax.set_xticks(range(len(class_names)))
        ax.set_yticks(range(len(class_names)))
        ax.set_xticklabels(class_names, rotation=45, ha="right", fontsize=8)
        ax.set_yticklabels(class_names, fontsize=8)
        ax.set_xlabel("Predicted", fontsize=10)
        ax.set_ylabel("True", fontsize=10)
        ax.set_title(subtitle, fontsize=11)

        # Annotate cells
        thresh = data.max() / 2.0
        for i in range(data.shape[0]):
            for j in range(data.shape[1]):
                val = data[i, j]
                text = f"{val:.2f}" if fmt_float else str(int(val))
                color = "white" if val > thresh else "black"
                ax.text(j, i, text, ha="center", va="center", fontsize=7, color=color)

    plt.tight_layout()
    save_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {save_path.name}")


def plot_roc_curves(
    y_true: np.ndarray,
    softmax_probs: np.ndarray,
    class_names: list,
    auroc: float,
    title: str,
    save_path: Path,
) -> None:
    """Per-class OvR ROC curves + macro average overlay.

    Per-class curves are drawn at low opacity to show individual spread.
    The macro average is computed by interpolating each class's TPR onto a
    shared FPR grid and then averaging — same methodology as sklearn's
    macro-average ROC for multiclass.
    """
    n_classes = len(class_names)
    fpr_grid = np.linspace(0, 1, 100)
    tprs_interpolated: list = []

    fig, ax = plt.subplots(figsize=(8, 8))

    for c in range(n_classes):
        y_bin = (y_true == c).astype(int)
        if y_bin.sum() == 0:
            continue  # skip classes with no positive samples in test set
        fpr_c, tpr_c, _ = roc_curve(y_bin, softmax_probs[:, c])
        ax.plot(fpr_c, tpr_c, alpha=0.3, linewidth=1, label=f"_{class_names[c]}")
        tprs_interpolated.append(np.interp(fpr_grid, fpr_c, tpr_c))

    # Macro average
    mean_tpr = np.mean(tprs_interpolated, axis=0)
    mean_tpr[0] = 0.0
    ax.plot(
        fpr_grid,
        mean_tpr,
        color="navy",
        linewidth=2.5,
        label=f"Macro avg (AUROC={auroc:.3f})" if auroc is not None else "Macro avg",
    )

    # Random baseline
    ax.plot([0, 1], [0, 1], "k--", alpha=0.5, label="Random baseline")

    ax.set_xlabel("False Positive Rate", fontsize=11)
    ax.set_ylabel("True Positive Rate", fontsize=11)
    ax.set_title(title, fontsize=12)
    ax.legend(loc="lower right", fontsize=7)

    save_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {save_path.name}")


def plot_reliability_diagram(
    y_true: np.ndarray,
    softmax_probs: np.ndarray,
    ece_10: float,
    title: str,
    save_path: Path,
) -> None:
    """Reliability diagram (calibration plot) with 10 equal-width bins.

    A perfectly calibrated model would have all bars exactly on the diagonal.
    The right y-axis histogram shows the distribution of predicted confidences
    so that well- vs. poorly-supported bins are immediately visible.
    """
    n_bins = 10
    max_probs = softmax_probs.max(axis=1)
    correct = (softmax_probs.argmax(axis=1) == y_true).astype(float)
    bin_edges = np.linspace(0.0, 1.0, n_bins + 1)
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2.0

    accuracies: list = []
    counts: list = []

    for b in range(n_bins):
        lo, hi = bin_edges[b], bin_edges[b + 1]
        if b < n_bins - 1:
            mask = (max_probs >= lo) & (max_probs < hi)
        else:
            mask = (max_probs >= lo) & (max_probs <= hi)
        n_bin = int(mask.sum())
        counts.append(n_bin)
        accuracies.append(float(correct[mask].mean()) if n_bin > 0 else 0.0)

    fig, ax1 = plt.subplots(figsize=(8, 6))

    # Bar chart: observed accuracy per bin
    ax1.bar(
        bin_centers,
        accuracies,
        width=0.08,
        alpha=0.7,
        color="steelblue",
        edgecolor="navy",
        label="Accuracy per bin",
    )

    # Perfect calibration diagonal
    ax1.plot([0, 1], [0, 1], "r--", linewidth=1.5, label="Perfect calibration")

    ax1.set_xlabel("Mean predicted confidence", fontsize=11)
    ax1.set_ylabel("Fraction correct", fontsize=11)
    ax1.set_xlim(0, 1)
    ax1.set_ylim(0, 1)
    ax1.set_title(f"{title} — Reliability Diagram (ECE={ece_10:.3f})", fontsize=12)
    ax1.legend(loc="upper left", fontsize=9)

    # Twin axis: sample count histogram (secondary visual guide)
    ax2 = ax1.twinx()
    ax2.bar(
        bin_centers,
        counts,
        width=0.08,
        alpha=0.2,
        color="gray",
        label="Sample count",
    )
    ax2.set_ylabel("Sample count", fontsize=10, color="gray")
    ax2.tick_params(axis="y", labelcolor="gray")

    save_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {save_path.name}")


def plot_selective_prediction(
    selective_data: list,
    title: str,
    save_path: Path,
) -> None:
    """Accuracy vs. coverage (selective prediction) curve.

    X-axis is inverted (1.0 → 0.5) so the "easy" high-coverage regime is on
    the left and the "hard" low-coverage regime is on the right — matching the
    intuition that moving right means increasing selectivity.

    A horizontal dashed line at the full-coverage accuracy (first point) shows
    the gain from abstaining on low-confidence predictions.
    """
    coverages = [pt[0] for pt in selective_data]
    accuracies = [pt[1] for pt in selective_data]

    # Full-coverage accuracy is the point at coverage=1.0
    full_coverage_idx = coverages.index(1.0) if 1.0 in coverages else 0
    full_accuracy = accuracies[full_coverage_idx]

    fig, ax = plt.subplots(figsize=(8, 5))

    ax.plot(
        coverages,
        accuracies,
        "o-",
        color="teal",
        linewidth=2,
        markersize=6,
        label="Accuracy at coverage",
    )
    ax.axhline(
        y=full_accuracy,
        linestyle="--",
        color="gray",
        linewidth=1.2,
        label=f"Full-coverage accuracy ({full_accuracy:.3f})",
    )

    ax.set_xlabel("Coverage", fontsize=11)
    ax.set_ylabel("Accuracy on kept predictions", fontsize=11)
    ax.set_title(title, fontsize=12)
    ax.set_xlim(1.0, 0.5)  # inverted x-axis
    ax.legend(fontsize=9)

    save_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {save_path.name}")


# ---------------------------------------------------------------------------
# Task 6 -- Main evaluation pipeline
# ---------------------------------------------------------------------------


def evaluate_model(
    name: str,
    model_path: Path,
    test_dir: Path,
    class_names: list,
    folder_to_index: dict,
    expected_counts: dict,
) -> dict:
    """Run the full evaluation pipeline for one vision model.

    Loads the model, runs inference on the held-out test set, computes all
    metrics (including calibration), generates four diagnostic figures, and
    returns a serialisable metrics dict.
    """
    sep = "=" * 70
    print(f"\n{sep}")
    print(f"  Evaluating: {name}")
    print(sep)

    # 1. Load model
    model, device = load_classification_model(model_path, len(class_names))

    # 2. Load test images with explicit class mapping
    print("\n[load_test_images]")
    paths, y_true, transform = load_test_images(test_dir, folder_to_index, expected_counts)

    # 3. Batched inference
    print("\n[run_inference]")
    y_pred, softmax_probs = run_inference(model, device, paths, transform)

    # 4. Shape invariant — catches silent truncation / broadcasting bugs
    n_classes = len(class_names)
    assert softmax_probs.shape == (len(paths), n_classes), (
        f"Shape mismatch: expected ({len(paths)}, {n_classes}), "
        f"got {softmax_probs.shape}"
    )

    # 5. Core classification metrics
    print("\n[compute_classification_metrics]")
    metrics = compute_classification_metrics(y_true, y_pred, softmax_probs, class_names)

    # 6. Calibration metrics
    calib = compute_calibration(y_true, softmax_probs, n_classes)
    metrics["calibration"] = calib

    # 7. Human-readable summary
    ece_10 = calib.get("ece_10bins", float("nan"))
    print(f"\n--- Summary: {name} ---")
    print(
        f"  Accuracy : {metrics['accuracy']:.4f}  "
        f"95%CI [{metrics['accuracy_ci_lo']:.4f}, {metrics['accuracy_ci_hi']:.4f}]"
    )
    print(
        f"  F1 macro : {metrics['f1_macro']:.4f}  "
        f"95%CI [{metrics['f1_macro_ci_lo']:.4f}, {metrics['f1_macro_ci_hi']:.4f}]"
    )
    print(f"  Kappa    : {metrics['cohen_kappa']:.4f}")
    auroc_str = f"{metrics['auroc_macro_ovr']:.4f}" if metrics["auroc_macro_ovr"] is not None else "N/A"
    print(f"  AUROC    : {auroc_str}")
    print(f"  Brier    : {metrics['brier_multiclass']:.4f}")
    print(f"  ECE@10   : {ece_10:.4f}")
    print("  Per-class (F1 / Recall / Recall-CI):")
    for cls_name, vals in metrics["per_class"].items():
        print(
            f"    {cls_name:<45}  "
            f"F1={vals['f1']:.3f}  "
            f"Rec={vals['recall']:.3f}  "
            f"CI=[{vals['recall_ci_lo']:.3f},{vals['recall_ci_hi']:.3f}]"
        )

    # 8. Figures — prefix derived from the human-readable model name
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    prefix = name.lower().replace(" ", "_").replace("(", "").replace(")", "")

    print("\n[figures]")
    plot_confusion_matrix(
        y_true, y_pred, class_names,
        title=f"Confusion Matrix — {name}",
        save_path=FIGURES_DIR / f"{prefix}_confusion_matrix.png",
    )
    auroc_val = metrics["auroc_macro_ovr"] if metrics["auroc_macro_ovr"] is not None else 0.0
    plot_roc_curves(
        y_true, softmax_probs, class_names, auroc_val,
        title=f"ROC Curves — {name}",
        save_path=FIGURES_DIR / f"{prefix}_roc_curves.png",
    )
    plot_reliability_diagram(
        y_true, softmax_probs, ece_10,
        title=name,
        save_path=FIGURES_DIR / f"{prefix}_reliability_diagram.png",
    )
    plot_selective_prediction(
        calib["selective_prediction_curve"],
        title=f"Selective Prediction — {name}",
        save_path=FIGURES_DIR / f"{prefix}_selective_prediction.png",
    )

    # 9. Free GPU memory before loading the next model
    del model
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    return metrics


def main() -> None:
    """Orchestrate evaluation of all vision models and persist results to JSON."""
    sep = "#" * 70
    print(f"\n{sep}")
    print("  Vision Model Formal Evaluation")
    print(f"  Protocol : benchmarks/vision/VALIDATION_PROTOCOL.md  (rev v2)")
    print(f"  Seed     : {SEED}")
    print(f"  Bootstrap: {N_BOOTSTRAP} iterations")
    print(sep)

    results: dict = {
        "meta": {
            "date": "2026-04-04",
            "seed": SEED,
            "protocol": "benchmarks/vision/VALIDATION_PROTOCOL.md",
            "revision": "v2",
            "bootstrap_iterations": N_BOOTSTRAP,
            "caveats": [
                "Split provenance not verifiable from this repo",
                "Models trained in howl-vision, reused here",
            ],
        },
    }

    # Dermatology model
    results["dermatology"] = evaluate_model(
        "Dermatology (Canine)",
        DERMA_MODEL_PATH,
        DERMA_TEST_DIR,
        DERMA_CLASS_NAMES,
        DERMA_FOLDER_TO_INDEX,
        EXPECTED_COUNTS_DERMA,
    )

    # Parasites model
    results["parasites"] = evaluate_model(
        "Parasites",
        PARA_MODEL_PATH,
        PARA_TEST_DIR,
        PARA_CLASS_NAMES,
        PARA_FOLDER_TO_INDEX,
        EXPECTED_COUNTS_PARA,
    )

    # Segmentation — no independent test set; record metadata only
    results["segmentation"] = {
        "status": "val_only",
        "architecture": "smp.Unet(encoder=efficientnet-b0, in_channels=1, classes=2)",
        "best_val_dice": 0.9999,
        "epoch": 34,
        "patience": 20,
        "caveat": (
            "No independent held-out test. Val metric selected by early stopping, "
            "subject to optimistic bias from hyperparameter selection."
        ),
    }

    # Persist
    results_path = Path(__file__).resolve().parent / "results.json"
    results_path.write_text(json.dumps(results, indent=2))
    print(f"\n[saved] {results_path}")

    # Final summary table
    sep2 = "-" * 70
    print(f"\n{sep2}")
    print("  FINAL SUMMARY")
    print(sep2)
    for key, label in [("dermatology", "Dermatology (Canine)"), ("parasites", "Parasites")]:
        m = results[key]
        print(
            f"  {label:<30}  "
            f"acc={m['accuracy']:.4f}  "
            f"f1={m['f1_macro']:.4f}  "
            f"kappa={m['cohen_kappa']:.4f}  "
            f"auroc={m['auroc_macro_ovr']}"
        )
    print(sep2)


if __name__ == "__main__":
    main()
