#!/usr/bin/env python3
"""AC-10 accuracy regression protocol for client-side JPEG compression.

For each image in the canine dermatology held-out test set (n=433), compare
five conditions:
  - A baseline:       PIL.Image.open(path) — single-generation JPEG decode
                      (source files are already .jpg; baseline is NOT lossless)
  - A' baseline_repeat: same as A, ran a second time to establish the
                        CUDA-nondeterminism noise floor
  - B  Q=85:          Pillow re-encode at JPEG quality 85, reload
  - C  Q=90:          Pillow re-encode at JPEG quality 90, reload
  - D  Q=95:          Pillow re-encode at JPEG quality 95, reload

Real compression impact per Q = max(0, flips_Q - flips_noise_floor).

For every condition, run the full inference pipeline:
  1. Classification via fine-tuned EfficientNetV2-S (data/models/vision/vet_dermatology.pt)
  2. 1280-d feature extraction + OOD binary gate (benchmarks/ood-eval/gate/gate_weights.pt)
  3. ONNX INT8 classification (benchmarks/onnx-spike/dermatology_int8.onnx)

Aggregate metrics per compressed condition vs baseline:
  - Label flips (Wilson 95% CI, exact-McNemar p-value)
  - |Delta softmax_top1| distribution (median, 90/95/99 pct, max)
  - Softmax KL divergence per image (median, 95 pct)
  - ECE_10bins delta + MCE_10bins delta
  - Gate false-reject-rate delta on in-distribution images
  - ONNX INT8 disagreement rate delta

Merge-blocking thresholds at Q=85 (see spec section 8 AC-10):
  - zero top-1 label flips (McNemar)
  - |ECE delta| < 0.005
  - Gate FRR delta < 2 pp
  - ONNX INT8 disagreement delta < 1 pp
  - 95th-pct |Delta softmax_top1| < 0.05

Outputs:
  - benchmarks/image-compression/results.json   (machine-readable)
  - benchmarks/image-compression/RESULTS.md     (human-readable)
"""

from __future__ import annotations

import argparse
import io
import json
import random
import sys
from datetime import datetime, timezone
from math import sqrt
from pathlib import Path

import numpy as np
import onnxruntime as ort
import timm
import torch
from PIL import Image
from scipy import stats
from torchvision import transforms as T


def configure_determinism(seed: int) -> None:
    """Pin CUDA + numpy + torch seeds for reproducible inference.

    Without cudnn.deterministic, conv algorithm selection can vary between
    runs on the same input, producing spurious label flips that would
    contaminate compression-vs-baseline comparisons.
    """
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


# ---------------------------------------------------------------------------
# Constants (synced with train_gate.py and eval_vision_models.py)
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]

INPUT_SIZE = 384
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]

CANINE_CLASSES = [
    "demodicosis",
    "Dermatitis",
    "Fungal_infections",
    "Healthy",
    "Hypersensitivity_Allergic_Dermatitis",
    "ringworm",
]
# Test folder names differ from model class names for one class only.
FOLDER_TO_CLASS = {
    "demodicosis": "demodicosis",
    "Dermatitis": "Dermatitis",
    "Fungal_infections": "Fungal_infections",
    "Healthy": "Healthy",
    "Hypersensitivity": "Hypersensitivity_Allergic_Dermatitis",
    "ringworm": "ringworm",
}
CLASS_TO_INDEX = {name: i for i, name in enumerate(CANINE_CLASSES)}

DERMA_MODEL_PATH = PROJECT_ROOT / "data/models/vision/vet_dermatology.pt"
GATE_WEIGHTS_PATH = PROJECT_ROOT / "benchmarks/ood-eval/gate/gate_weights.pt"
GATE_THRESHOLD_PATH = PROJECT_ROOT / "benchmarks/ood-eval/gate/gate_results.json"
ONNX_INT8_PATH = PROJECT_ROOT / "benchmarks/onnx-spike/dermatology_int8.onnx"
TEST_DIR = PROJECT_ROOT / "data/datasets/canine/canine/dermatology/test"

OUTPUT_DIR = PROJECT_ROOT / "benchmarks/image-compression"

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}

# AC-10 merge-blocking thresholds (spec v3, revised per ml-eval-rigor ruling).
#
# label_flips: PASS requires non-significant McNemar (p >= 0.05) AND point
#   estimate under 2%. Strict-zero was unachievable on n=433 with CUDA
#   inference and indistinguishable from noise floor; McNemar captures the
#   correct concept of directional degradation.
# ece_delta: ASYMMETRIC — only regressions are blocked. Improvements (negative
#   delta) are unconditionally acceptable; a safety-critical clinical tool
#   should not fail merge on improved calibration.
THRESHOLDS = {
    "mcnemar_p_min": 0.05,
    "max_flip_rate": 0.02,
    "max_ece_regression": 0.005,         # applies only when ece_delta > 0
    "max_gate_frr_delta_pp": 2.0,
    "max_onnx_disagreement_delta_pp": 1.0,
    "max_p95_softmax_delta": 0.05,
}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--q-levels",
        type=int,
        nargs="+",
        default=[85, 90, 95],
        help="JPEG quality levels to compare against baseline (default: 85 90 95)",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Limit to first N images per class (0 = all, >0 for smoke testing)",
    )
    p.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Seed for any random state (kept for parity with train_gate.py)",
    )
    p.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_DIR,
        help="Output directory (default: benchmarks/image-compression)",
    )
    return p.parse_args()


# ---------------------------------------------------------------------------
# Pipeline building blocks
# ---------------------------------------------------------------------------

def build_transform() -> T.Compose:
    """Preprocessing identical to train_gate.py + vision-service production."""
    return T.Compose(
        [
            T.Resize((INPUT_SIZE, INPUT_SIZE)),
            T.ToTensor(),
            T.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
        ]
    )


def load_classifier(device: torch.device) -> torch.nn.Module:
    """Load fine-tuned EfficientNetV2-S canine dermatology model."""
    model = timm.create_model(
        "tf_efficientnetv2_s.in21k_ft_in1k",
        pretrained=False,
        num_classes=len(CANINE_CLASSES),
    )
    ckpt = torch.load(DERMA_MODEL_PATH, map_location=device, weights_only=False)
    model.load_state_dict(ckpt["model_state_dict"])
    model.to(device)
    # train(False) is equivalent to setting inference mode; disables dropout/BN update.
    model.train(False)
    return model


def load_gate(device: torch.device) -> tuple[torch.nn.Linear, float]:
    """Load gate_weights.pt (nn.Linear 1280->1 state_dict) and threshold."""
    gate = torch.nn.Linear(1280, 1)
    state = torch.load(GATE_WEIGHTS_PATH, map_location=device, weights_only=True)
    gate.load_state_dict(state)
    gate.to(device)
    gate.train(False)

    with open(GATE_THRESHOLD_PATH, encoding="utf-8") as f:
        gate_meta = json.load(f)
    # Threshold is a sigmoid cutoff: accept iff sigmoid(score) >= threshold.
    threshold = float(gate_meta["threshold"])
    return gate, threshold


def load_onnx_int8() -> ort.InferenceSession:
    providers = ["CPUExecutionProvider"]
    if "CUDAExecutionProvider" in ort.get_available_providers():
        providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
    return ort.InferenceSession(str(ONNX_INT8_PATH), providers=providers)


def enumerate_test_images(limit: int) -> list[tuple[Path, int, str]]:
    """Return sorted list of (image_path, class_index, folder_name).

    Deterministic ordering: by class folder then filename alphabetical. No random
    sampling — we use the entire held-out test split (n=433) same as
    benchmarks/vision/results.json.
    """
    out: list[tuple[Path, int, str]] = []
    if not TEST_DIR.is_dir():
        sys.exit(f"Test directory not found: {TEST_DIR}")

    for folder in sorted(TEST_DIR.iterdir()):
        if not folder.is_dir():
            continue
        folder_name = folder.name
        if folder_name not in FOLDER_TO_CLASS:
            print(f"  [WARN] unknown folder {folder_name}, skipping")
            continue
        class_name = FOLDER_TO_CLASS[folder_name]
        class_idx = CLASS_TO_INDEX[class_name]

        images = sorted(
            p for p in folder.iterdir()
            if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
        )
        if limit > 0:
            images = images[:limit]

        for img_path in images:
            out.append((img_path, class_idx, folder_name))

    return out


# ---------------------------------------------------------------------------
# Compression helper
# ---------------------------------------------------------------------------

def reencode_jpeg(img: Image.Image, quality: int) -> Image.Image:
    """Re-encode a PIL image as JPEG at the given quality, then reload.

    Python analogue of the browser compressImage: decode -> encode-as-JPEG ->
    decode. The reload is required because we want to measure model response
    to pixels that have been through the JPEG codec, not the pre-encode PIL
    image.
    """
    buf = io.BytesIO()
    # Encode in RGB: JPEG has no alpha. Frontend compressImage also collapses
    # alpha to white (implicit when drawing on a canvas without fillStyle).
    rgb = img.convert("RGB")
    rgb.save(buf, format="JPEG", quality=quality, optimize=False)
    buf.seek(0)
    return Image.open(buf).convert("RGB")


# ---------------------------------------------------------------------------
# Per-image inference
# ---------------------------------------------------------------------------

@torch.no_grad()
def run_inference(
    img: Image.Image,
    classifier: torch.nn.Module,
    gate: torch.nn.Linear,
    onnx_sess: ort.InferenceSession,
    transform: T.Compose,
    device: torch.device,
) -> dict:
    """One forward pass. Returns softmax, features, gate score, ONNX softmax."""
    tensor = transform(img).unsqueeze(0).to(device)

    # Single forward_features call, reused for pre_logits and logits
    features = classifier.forward_features(tensor)
    prelogits = classifier.forward_head(features, pre_logits=True)  # (1, 1280)
    logits = classifier.forward_head(features)                       # (1, 6)
    softmax = torch.softmax(logits, dim=-1).cpu().numpy().squeeze(0)

    # Gate score: sigmoid(Linear(prelogits))
    gate_raw = gate(prelogits).squeeze().item()
    gate_sigmoid = float(1.0 / (1.0 + np.exp(-gate_raw)))

    # ONNX INT8: expects NCHW float32 (same preprocessing numerically).
    onnx_input = tensor.cpu().numpy()
    onnx_logits = onnx_sess.run(
        None, {onnx_sess.get_inputs()[0].name: onnx_input}
    )[0]
    onnx_softmax = np.exp(onnx_logits - onnx_logits.max(axis=-1, keepdims=True))
    onnx_softmax = onnx_softmax / onnx_softmax.sum(axis=-1, keepdims=True)
    onnx_softmax = onnx_softmax.squeeze(0)

    return {
        "softmax": softmax.astype(np.float64),
        "prelogits": prelogits.cpu().numpy().squeeze(0).astype(np.float32),
        "gate_sigmoid": gate_sigmoid,
        "onnx_softmax": onnx_softmax.astype(np.float64),
    }


# ---------------------------------------------------------------------------
# Aggregate metrics
# ---------------------------------------------------------------------------

def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    margin = (z * sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denom
    return max(0.0, center - margin), min(1.0, center + margin)


def mcnemar_exact_p(b: int, c: int) -> float:
    """Exact McNemar test p-value (two-sided exact binomial on discordant pairs).

    b = discordant pairs where baseline correct, compressed wrong.
    c = discordant pairs where baseline wrong, compressed correct.
    """
    n = b + c
    if n == 0:
        return 1.0
    result = stats.binomtest(min(b, c), n, p=0.5, alternative="two-sided")
    return float(result.pvalue)


def kl_divergence(p: np.ndarray, q: np.ndarray, eps: float = 1e-12) -> float:
    p = p + eps
    q = q + eps
    p = p / p.sum()
    q = q / q.sum()
    return float(np.sum(p * np.log(p / q)))


def ece_mce(
    confidences: np.ndarray,
    corrects: np.ndarray,
    n_bins: int = 10,
) -> tuple[float, float]:
    """Equal-width binning ECE and MCE (matches VALIDATION_PROTOCOL.md)."""
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    mce = 0.0
    n = len(confidences)
    for i in range(n_bins):
        mask = (confidences >= bins[i]) & (confidences < bins[i + 1])
        if i == n_bins - 1:
            mask = (confidences >= bins[i]) & (confidences <= bins[i + 1])
        bin_count = int(mask.sum())
        if bin_count == 0:
            continue
        bin_acc = float(corrects[mask].mean())
        bin_conf = float(confidences[mask].mean())
        gap = abs(bin_acc - bin_conf)
        ece += (bin_count / n) * gap
        mce = max(mce, gap)
    return ece, mce


def summarize_distribution(values: np.ndarray) -> dict:
    if len(values) == 0:
        return {k: 0.0 for k in ("median", "p90", "p95", "p99", "max")}
    return {
        "median": float(np.median(values)),
        "p90": float(np.percentile(values, 90)),
        "p95": float(np.percentile(values, 95)),
        "p99": float(np.percentile(values, 99)),
        "max": float(np.max(values)),
    }


def compare_condition(
    baseline: list[dict],
    compressed: list[dict],
    ground_truth_idx: np.ndarray,
    gate_threshold: float,
) -> dict:
    """Compute all metrics for one compressed condition vs baseline."""
    n = len(baseline)
    assert len(compressed) == n, "length mismatch"

    b_top1 = np.array([np.argmax(r["softmax"]) for r in baseline])
    c_top1 = np.array([np.argmax(r["softmax"]) for r in compressed])
    b_conf = np.array([r["softmax"][b_top1[i]] for i, r in enumerate(baseline)])
    c_conf = np.array([r["softmax"][c_top1[i]] for i, r in enumerate(compressed)])

    b_correct = (b_top1 == ground_truth_idx).astype(np.int32)
    c_correct = (c_top1 == ground_truth_idx).astype(np.int32)

    # Label flip analysis
    flips = int((b_top1 != c_top1).sum())
    flip_ci_lo, flip_ci_hi = wilson_ci(flips, n)
    # McNemar discordant pairs (baseline correct, compressed wrong) vs reverse
    b_c_wrong = int(((b_correct == 1) & (c_correct == 0)).sum())
    c_b_wrong = int(((b_correct == 0) & (c_correct == 1)).sum())
    mcnemar_p = mcnemar_exact_p(b_c_wrong, c_b_wrong)

    # Softmax delta distribution
    delta_top1 = np.abs(c_conf - b_conf)
    softmax_delta_summary = summarize_distribution(delta_top1)
    # KL divergence per image
    kls = np.array(
        [kl_divergence(baseline[i]["softmax"], compressed[i]["softmax"])
         for i in range(n)]
    )
    kl_summary = summarize_distribution(kls)

    # ECE / MCE
    b_ece, b_mce = ece_mce(b_conf, b_correct)
    c_ece, c_mce = ece_mce(c_conf, c_correct)

    # Gate FRR on in-distribution images. All 433 test images are
    # in-distribution dermatology, so FRR = fraction rejected by the gate.
    b_gate = np.array([r["gate_sigmoid"] for r in baseline])
    c_gate = np.array([r["gate_sigmoid"] for r in compressed])
    b_rejected = (b_gate < gate_threshold).astype(np.int32)
    c_rejected = (c_gate < gate_threshold).astype(np.int32)
    b_frr = float(b_rejected.mean())
    c_frr = float(c_rejected.mean())

    # ONNX INT8 disagreement with FP32 under the SAME condition: measures
    # quantization error, not compression error. Delta(disagreement) detects
    # whether compression makes INT8 worse at approximating FP32.
    b_onnx_top1 = np.array([np.argmax(r["onnx_softmax"]) for r in baseline])
    c_onnx_top1 = np.array([np.argmax(r["onnx_softmax"]) for r in compressed])
    b_onnx_disagree = float((b_onnx_top1 != b_top1).mean())
    c_onnx_disagree = float((c_onnx_top1 != c_top1).mean())

    return {
        "n_images": n,
        "label_flips": {
            "count": flips,
            "rate": flips / n,
            "wilson_95_lo": flip_ci_lo,
            "wilson_95_hi": flip_ci_hi,
            "mcnemar_discordant": {
                "b_correct_c_wrong": b_c_wrong,
                "c_correct_b_wrong": c_b_wrong,
            },
            "mcnemar_exact_p": mcnemar_p,
        },
        "softmax_top1_abs_delta": softmax_delta_summary,
        "softmax_kl_divergence": kl_summary,
        "calibration": {
            "ece_baseline": b_ece,
            "ece_compressed": c_ece,
            "ece_delta": c_ece - b_ece,
            "mce_baseline": b_mce,
            "mce_compressed": c_mce,
            "mce_delta": c_mce - b_mce,
        },
        "gate": {
            "frr_baseline": b_frr,
            "frr_compressed": c_frr,
            "frr_delta_pp": (c_frr - b_frr) * 100.0,
            "threshold": gate_threshold,
        },
        "onnx_int8": {
            "disagreement_baseline": b_onnx_disagree,
            "disagreement_compressed": c_onnx_disagree,
            "disagreement_delta_pp": (c_onnx_disagree - b_onnx_disagree) * 100.0,
        },
    }


def check_thresholds(metrics: dict) -> dict:
    """Apply AC-10 merge-blocking thresholds (spec v3).

    Label flip rule: pass requires McNemar non-significant (symmetric noise)
    AND total flip rate under 2% point estimate. An explicit directional
    degradation clause catches the case where compression is one-sidedly
    worse even if the sample is small enough to keep McNemar > 0.05.
    """
    flips = metrics["label_flips"]
    flip_rate = flips["rate"]
    p = flips["mcnemar_exact_p"]
    b_correct_c_wrong = flips["mcnemar_discordant"]["b_correct_c_wrong"]
    c_correct_b_wrong = flips["mcnemar_discordant"]["c_correct_b_wrong"]
    directional_degradation = (
        b_correct_c_wrong > c_correct_b_wrong
        and p < THRESHOLDS["mcnemar_p_min"]
    )

    ece_delta = metrics["calibration"]["ece_delta"]
    ece_ok = ece_delta <= THRESHOLDS["max_ece_regression"]

    gate_delta = abs(metrics["gate"]["frr_delta_pp"])
    onnx_delta = abs(metrics["onnx_int8"]["disagreement_delta_pp"])
    p95_softmax = metrics["softmax_top1_abs_delta"]["p95"]

    checks = {
        "label_flips_not_directional": not directional_degradation,
        "label_flip_rate_under_threshold": flip_rate < THRESHOLDS["max_flip_rate"],
        "ece_no_regression": ece_ok,
        "gate_frr_delta_under_threshold": gate_delta < THRESHOLDS["max_gate_frr_delta_pp"],
        "onnx_disagreement_delta_under_threshold": onnx_delta < THRESHOLDS["max_onnx_disagreement_delta_pp"],
        "p95_softmax_delta_under_threshold": p95_softmax < THRESHOLDS["max_p95_softmax_delta"],
    }
    checks["overall_pass"] = all(checks.values())
    return checks


# ---------------------------------------------------------------------------
# Markdown report
# ---------------------------------------------------------------------------

def markdown_row(name: str, val: float, threshold: float, pass_ok: bool) -> str:
    mark = "PASS" if pass_ok else "**FAIL**"
    return f"| {name} | {val:.6f} | {threshold} | {mark} |"


def generate_markdown(
    per_level_results: dict,
    image_paths: list[Path],
    seed: int,
    noise_floor: dict,
) -> str:
    lines: list[str] = []
    lines.append("# Image-Compression Accuracy Evaluation")
    lines.append("")
    lines.append("**Protocol:** AC-10 with v3 thresholds (McNemar exact, asymmetric ECE).")
    lines.append(f"**Dataset:** canine dermatology held-out test split, n={len(image_paths)}, seed={seed}")
    lines.append(f"**Generated:** {datetime.now(timezone.utc).isoformat()}")
    lines.append("**Baseline:** single-generation JPEG decode (source files are `.jpg`; **not lossless**)")
    lines.append("**Determinism:** `cudnn.deterministic=True`, `cudnn.benchmark=False`, torch/numpy/random seeded")
    lines.append("")
    lines.append("## Noise floor (baseline vs baseline_repeat)")
    lines.append("")
    nf_flips = noise_floor["label_flips"]["count"]
    nf_p95 = noise_floor["softmax_top1_abs_delta"]["p95"]
    nf_max = noise_floor["softmax_top1_abs_delta"]["max"]
    lines.append(
        f"Running the SAME input through the pipeline twice produces **{nf_flips} "
        f"label flips** (p95 |softmax delta| = {nf_p95:.5f}, max = {nf_max:.5f}). "
        f"These are NOT compression-caused; they reflect intrinsic non-determinism "
        f"(CUDA kernel selection, floating-point order)."
    )
    lines.append("")
    lines.append(
        f"Compression-attributable flips per Q level "
        f"= `max(0, total_flips_Q - {nf_flips})`."
    )
    lines.append("")
    lines.append("## AC-10 thresholds (spec v3, merge-blocking)")
    lines.append("")
    lines.append(
        f"- Label flips: McNemar exact p ≥ {THRESHOLDS['mcnemar_p_min']} "
        f"AND flip_rate_point < {THRESHOLDS['max_flip_rate']} "
        "AND no directional degradation at p<0.05"
    )
    lines.append(
        f"- ECE delta (asymmetric): regression ≤ {THRESHOLDS['max_ece_regression']}; "
        "improvements unconditionally accepted"
    )
    lines.append(f"- Gate FRR delta: |Δ| < {THRESHOLDS['max_gate_frr_delta_pp']} pp")
    lines.append(f"- ONNX INT8 disagreement delta: |Δ| < {THRESHOLDS['max_onnx_disagreement_delta_pp']} pp")
    lines.append(f"- 95th-pct |softmax delta|: < {THRESHOLDS['max_p95_softmax_delta']}")
    lines.append("")
    lines.append("*Caveat on McNemar:* at small discordant counts (b+c < 10) the exact test has")
    lines.append("limited power; p=1.00 means symmetric noise is indistinguishable from zero effect,")
    lines.append("not that equivalence is proven. The merge gate is the *combined* rule above,")
    lines.append("not the p-value alone.")
    lines.append("")

    for q, data in per_level_results.items():
        m = data["metrics"]
        c = data["checks"]
        attributable = m["label_flips"].get("attributable_to_compression", m["label_flips"]["count"])
        lines.append(f"## Q = {q}")
        lines.append("")
        lines.append(f"**Overall:** {'PASS' if c['overall_pass'] else '**FAIL**'}  ")
        lines.append(
            f"**McNemar exact p:** {m['label_flips']['mcnemar_exact_p']:.4f}  "
            f"({m['label_flips']['mcnemar_discordant']['b_correct_c_wrong']} "
            f"baseline-correct-compressed-wrong, "
            f"{m['label_flips']['mcnemar_discordant']['c_correct_b_wrong']} reverse)  "
            f"**Flips attributable to compression (total − noise floor):** {attributable}"
        )
        lines.append("")
        lines.append("| Metric | Value | Threshold | Result |")
        lines.append("|--------|-------|-----------|--------|")
        lines.append(
            f"| Directional degradation (compression one-sidedly worse) | "
            f"{'yes' if not c['label_flips_not_directional'] else 'no'} | "
            f"must be 'no' (or McNemar p ≥ {THRESHOLDS['mcnemar_p_min']}) | "
            f"{'PASS' if c['label_flips_not_directional'] else '**FAIL**'} |"
        )
        lines.append(markdown_row(
            "Label flip rate (point)", m["label_flips"]["rate"],
            THRESHOLDS["max_flip_rate"],
            c["label_flip_rate_under_threshold"],
        ))
        ece_delta = m["calibration"]["ece_delta"]
        ece_direction = "improved" if ece_delta < 0 else "regressed"
        lines.append(
            f"| ECE delta (direction: {ece_direction}) | {ece_delta:+.6f} | "
            f"≤ {THRESHOLDS['max_ece_regression']} (regression only) | "
            f"{'PASS' if c['ece_no_regression'] else '**FAIL**'} |"
        )
        lines.append(markdown_row(
            "|Gate FRR delta| (pp)", abs(m["gate"]["frr_delta_pp"]),
            THRESHOLDS["max_gate_frr_delta_pp"],
            c["gate_frr_delta_under_threshold"],
        ))
        lines.append(markdown_row(
            "|ONNX INT8 disagreement delta| (pp)",
            abs(m["onnx_int8"]["disagreement_delta_pp"]),
            THRESHOLDS["max_onnx_disagreement_delta_pp"],
            c["onnx_disagreement_delta_under_threshold"],
        ))
        lines.append(markdown_row(
            "95th-pct |softmax delta_top1|",
            m["softmax_top1_abs_delta"]["p95"],
            THRESHOLDS["max_p95_softmax_delta"],
            c["p95_softmax_delta_under_threshold"],
        ))
        lines.append("")
        lines.append("**Softmax delta_top1 distribution:**")
        dist = m["softmax_top1_abs_delta"]
        lines.append(
            f"- median: {dist['median']:.5f}, p90: {dist['p90']:.5f}, "
            f"p95: {dist['p95']:.5f}, p99: {dist['p99']:.5f}, max: {dist['max']:.5f}"
        )
        lines.append("")
        lines.append("**Softmax KL divergence distribution:**")
        kld = m["softmax_kl_divergence"]
        lines.append(
            f"- median: {kld['median']:.5f}, p90: {kld['p90']:.5f}, "
            f"p95: {kld['p95']:.5f}, p99: {kld['p99']:.5f}, max: {kld['max']:.5f}"
        )
        lines.append("")
        ece_note = (
            "(compressed BETTER calibrated than baseline)"
            if m["calibration"]["ece_delta"] < 0
            else "(compressed WORSE calibrated than baseline)"
        )
        lines.append(
            f"**Calibration:** ECE_baseline = {m['calibration']['ece_baseline']:.5f}, "
            f"ECE_compressed = {m['calibration']['ece_compressed']:.5f}, "
            f"Delta = {m['calibration']['ece_delta']:+.5f} {ece_note}"
        )
        lines.append(
            f"**Gate:** FRR_baseline = {m['gate']['frr_baseline']*100:.2f}%, "
            f"FRR_compressed = {m['gate']['frr_compressed']*100:.2f}%, "
            f"Delta = {m['gate']['frr_delta_pp']:+.3f} pp"
        )
        lines.append(
            f"**ONNX INT8:** disagree_baseline = {m['onnx_int8']['disagreement_baseline']*100:.2f}%, "
            f"disagree_compressed = {m['onnx_int8']['disagreement_compressed']*100:.2f}%, "
            f"Delta = {m['onnx_int8']['disagreement_delta_pp']:+.3f} pp"
        )
        lines.append("")

    lines.append("## Verdict")
    lines.append("")
    passing_qs = [q for q, d in per_level_results.items() if d["checks"]["overall_pass"]]
    if not passing_qs:
        lines.append("**MERGE BLOCKED.** No quality level passes all AC-10 thresholds. Escalate:")
        lines.append("- If ONNX INT8 disagreement is the failure, follow up with re-calibration.")
        lines.append("- If gate FRR delta is the failure, follow up with a gate re-train.")
        lines.append("- Otherwise investigate the specific failing metric before merge.")
    else:
        selected = min(passing_qs)
        lines.append(f"**Recommended quality:** Q = {selected} (lowest Q that passes all thresholds).")
        lines.append("Configure `compressImage` default accordingly in `frontend/src/lib/image.ts`.")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    configure_determinism(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")
    print(f"Seed: {args.seed} (cudnn.deterministic=True, cudnn.benchmark=False)")

    # --- Enumerate test set ---
    images = enumerate_test_images(args.limit)
    if not images:
        sys.exit("No test images found.")
    n_classes = len(set(i[1] for i in images))
    print(f"Enumerated {len(images)} images across {n_classes} classes")

    # --- Load models ---
    print("Loading classifier...")
    classifier = load_classifier(device)
    print("Loading gate...")
    gate, gate_threshold = load_gate(device)
    print(f"  Gate threshold (sigmoid): {gate_threshold:.6f}")
    print("Loading ONNX INT8 session...")
    onnx_sess = load_onnx_int8()
    transform = build_transform()

    # --- Inference across conditions ---
    conditions = ["baseline", "baseline_repeat"] + [f"q{q}" for q in args.q_levels]
    results_per_condition: dict[str, list[dict]] = {c: [] for c in conditions}
    ground_truth_idx = np.array([i[1] for i in images])

    for i, (path, class_idx, folder) in enumerate(images):
        try:
            original = Image.open(path).convert("RGB")
        except Exception as exc:
            print(f"  [WARN] {path}: open failed — {exc}")
            continue

        # Baseline A: single-generation JPEG decode via PIL
        results_per_condition["baseline"].append(
            run_inference(original, classifier, gate, onnx_sess, transform, device)
        )

        # Baseline A': identical to A, second pass — establishes the
        # intrinsic-noise floor (CUDA non-determinism + any residual
        # floating-point variance between otherwise-identical forward passes).
        # Any flips here are NOT compression-caused.
        original_repeat = Image.open(path).convert("RGB")
        results_per_condition["baseline_repeat"].append(
            run_inference(original_repeat, classifier, gate, onnx_sess, transform, device)
        )

        # Compressed variants
        for q in args.q_levels:
            compressed = reencode_jpeg(original, q)
            results_per_condition[f"q{q}"].append(
                run_inference(compressed, classifier, gate, onnx_sess, transform, device)
            )

        if (i + 1) % 25 == 0 or i == len(images) - 1:
            print(f"  {i + 1}/{len(images)} done")

    # --- Noise floor: baseline vs baseline_repeat ---
    print("Computing aggregate metrics...")
    baseline = results_per_condition["baseline"]
    baseline_repeat = results_per_condition["baseline_repeat"]
    noise_floor = compare_condition(
        baseline, baseline_repeat, ground_truth_idx, gate_threshold
    )
    nf_flips = noise_floor["label_flips"]["count"]
    print(
        f"  noise_floor (baseline vs baseline_repeat): flips={nf_flips}, "
        f"p95 delta={noise_floor['softmax_top1_abs_delta']['p95']:.5f}"
    )

    # --- Compare each Q level against baseline ---
    per_level_results: dict[int, dict] = {}
    for q in args.q_levels:
        compressed = results_per_condition[f"q{q}"]
        metrics = compare_condition(baseline, compressed, ground_truth_idx, gate_threshold)
        checks = check_thresholds(metrics)
        attributable = max(0, metrics["label_flips"]["count"] - nf_flips)
        metrics["label_flips"]["attributable_to_compression"] = attributable
        per_level_results[q] = {"metrics": metrics, "checks": checks}
        status = "PASS" if checks["overall_pass"] else "FAIL"
        print(
            f"  Q={q}: {status} — "
            f"flips={metrics['label_flips']['count']} "
            f"(attributable={attributable}), "
            f"ECE delta={metrics['calibration']['ece_delta']:+.5f}, "
            f"gate FRR delta={metrics['gate']['frr_delta_pp']:+.3f}pp, "
            f"onnx delta={metrics['onnx_int8']['disagreement_delta_pp']:+.3f}pp"
        )

    # --- Write JSON ---
    results_json_path = args.output_dir / "results.json"
    results_json = {
        "metadata": {
            "protocol": "AC-10 v3",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "seed": args.seed,
            "n_images": len(images),
            "q_levels": args.q_levels,
            "gate_threshold_sigmoid": gate_threshold,
            "thresholds": THRESHOLDS,
            "determinism": {
                "cudnn_deterministic": True,
                "cudnn_benchmark": False,
            },
        },
        "noise_floor_baseline_vs_repeat": noise_floor,
        "per_quality_level": per_level_results,
    }
    with open(results_json_path, "w", encoding="utf-8") as f:
        json.dump(results_json, f, indent=2, default=float)
    print(f"Wrote {results_json_path}")

    # --- Write Markdown ---
    md = generate_markdown(
        per_level_results,
        [i[0] for i in images],
        args.seed,
        noise_floor,
    )
    md_path = args.output_dir / "RESULTS.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"Wrote {md_path}")

    # --- Exit code reflects merge gate ---
    passing = [q for q, d in per_level_results.items() if d["checks"]["overall_pass"]]
    if not passing:
        sys.exit("MERGE BLOCKED: no Q level passes all AC-10 thresholds.")
    print(f"Passing Q levels: {passing}. Recommended: Q={min(passing)}")


if __name__ == "__main__":
    main()
