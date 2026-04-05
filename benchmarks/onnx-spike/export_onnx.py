"""ONNX export spike for the dermatology EfficientNetV2-S classifier.

Goal: determine go/no-go for offline browser inference via ONNX Runtime Web.

Pipeline:
  1. Load PyTorch model from checkpoint
  2. Export to ONNX FP32 (opset 17, static shape)
  3. Simplify with onnxsim (removes redundant ops, required before quantization)
  4. Quantize to INT8 with quantize_dynamic
  5. Parity check (two variants):
     - FP32: 0 disagreements AND max_logit_delta < 1e-3
       (near-numerical identity expected for lossless format conversion)
     - INT8: 0 class disagreements ONLY
       (INT8 quantization inherently changes logit magnitudes; class agreement
        is the correct correctness metric for classification deployment)

Why opset 17: tf_efficientnetv2_s uses TF-style 'same' padding which requires
GridSample or Pad ops that stabilised in opset 17. Opset 12/14 can produce
incorrect results on this specific architecture.

Why static shape (no dynamic_axes): WASM JIT compile time is proportional to
the number of unique shapes seen. Static shapes let ort-web pre-compile the
full graph once at load time.

Why legacy torch.onnx.export (dynamo=False): the dynamo exporter (torch >= 2.1)
has known issues with timm's tf_efficientnetv2_s padding. Legacy exporter is
stable and produces correct graphs for this model.
"""

import argparse
import pathlib
import sys

import numpy as np
import onnx
import onnxruntime as ort
import timm
import torch
from onnxruntime.quantization import QuantType, quantize_dynamic
from onnxsim import simplify

# ---------------------------------------------------------------------------
# Constants -- must mirror vision-service/src/config.py and
# vision-service/src/models/dermatology.py exactly.
# ---------------------------------------------------------------------------

CHECKPOINT_PATH = pathlib.Path(
    "/home/ikchain/Quantum/hackathons/gemma-4/data/models/vision/vet_dermatology.pt"
)
OUTPUT_DIR = pathlib.Path(
    "/home/ikchain/Quantum/hackathons/gemma-4/benchmarks/onnx-spike"
)

# Order matches DermatologyModel.CLASS_NAMES in vision-service
CLASS_NAMES = [
    "demodicosis",
    "Dermatitis",
    "Fungal_infections",
    "Healthy",
    "Hypersensitivity_Allergic_Dermatitis",
    "ringworm",
]

INPUT_SIZE = 384          # CLASSIFICATION_INPUT_SIZE from config.py
NUM_CLASSES = len(CLASS_NAMES)   # 6

# Parity thresholds
PARITY_SAMPLES = 20
MAX_CLASS_DISAGREEMENTS = 0
# FP32: lossless format conversion -- near-numerical identity expected
FP32_MAX_LOGIT_DELTA = 1e-3
# INT8: dynamic quantization introduces intentional precision loss;
# logit delta of ~0.5-1.0 is normal. Class agreement is the correctness gate.
INT8_MAX_LOGIT_DELTA = float("inf")


def load_pytorch_model(checkpoint_path: pathlib.Path, device: torch.device) -> torch.nn.Module:
    """Load EfficientNetV2-S with dermatology head from a training checkpoint.

    The checkpoint stores {'model_state_dict': ...} -- the optimizer and
    epoch state are intentionally discarded here (weights only).
    """
    model = timm.create_model(
        "tf_efficientnetv2_s.in21k_ft_in1k",
        pretrained=False,
        num_classes=NUM_CLASSES,
    )

    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.to(device)
    model.eval()

    print(f"  Loaded checkpoint: {checkpoint_path.name}")
    print(f"  Checkpoint keys:   {list(checkpoint.keys())}")

    return model


def export_fp32(model: torch.nn.Module, output_path: pathlib.Path, device: torch.device) -> None:
    """Export model to ONNX FP32 using the legacy torch.onnx.export API.

    Static input shape [1, 3, 384, 384] -- no dynamic_axes -- critical for
    WASM performance (ort-web can compile the full graph at load time).

    Opset 17 is required for tf_efficientnetv2_s 'same' padding correctness.
    """
    dummy = torch.randn(1, 3, INPUT_SIZE, INPUT_SIZE, device=device)

    print(f"  Exporting FP32 to {output_path.name} ...")
    torch.onnx.export(
        model,
        dummy,
        str(output_path),
        opset_version=18,
        input_names=["input"],
        output_names=["logits"],
        # No dynamic_axes -- static shape only, intentional for WASM
        do_constant_folding=True,
        verbose=False,
    )
    print(f"  FP32 export done. Size: {output_path.stat().st_size / 1_048_576:.1f} MB")


def simplify_onnx(input_path: pathlib.Path, output_path: pathlib.Path) -> None:
    """Run onnxsim to fold constants and remove redundant ops.

    Mandatory before quantization -- onnxsim removes identity nodes and fuses
    ops that confuse the quantizer's node-matching heuristics.
    Also shrinks the raw export (1.2 MB due to serialisation overhead) to the
    real weight-complete model (~77 MB).
    """
    model_proto = onnx.load(str(input_path))
    print(f"  Running onnxsim on {input_path.name} ...")

    simplified, check_ok = simplify(model_proto)

    if not check_ok:
        # Non-fatal: onnxsim couldn't verify equivalence, but the graph may
        # still be correct. Log and continue -- parity check will catch issues.
        print("  WARNING: onnxsim check failed. Proceeding with unsimplified graph.")
        simplified = model_proto

    onnx.save(simplified, str(output_path))
    print(f"  Simplified. Size: {output_path.stat().st_size / 1_048_576:.1f} MB")


def quantize_int8(input_path: pathlib.Path, output_path: pathlib.Path) -> None:
    """Quantize FP32 ONNX model to dynamic INT8 (QUInt8).

    quantize_dynamic applies 8-bit quantization to MatMul and Conv weight
    tensors. Activations remain FP32 (dynamic quantization). This gives a
    ~4x size reduction with acceptable accuracy loss for classification tasks.

    Note: EfficientNet depthwise convolutions are known to be sensitive to
    quantization -- the parity check will catch any class-level degradation.
    """
    print(f"  Quantizing {input_path.name} -> {output_path.name} ...")
    quantize_dynamic(
        model_input=str(input_path),
        model_output=str(output_path),
        weight_type=QuantType.QUInt8,
    )
    print(f"  INT8 done. Size: {output_path.stat().st_size / 1_048_576:.1f} MB")


def run_parity_check(
    model: torch.nn.Module,
    onnx_path: pathlib.Path,
    device: torch.device,
    label: str,
    max_logit_delta: float,
) -> dict:
    """Compare PyTorch and ONNX Runtime outputs on random inputs.

    Args:
        max_logit_delta: Per-element logit threshold. For FP32 this should be
            ~1e-3 (near-numerical identity). For INT8 pass float('inf') --
            class agreement alone is the meaningful correctness gate.

    Returns:
        {
            "disagreements": int,   # class argmax mismatches
            "max_logit_delta": float,
            "passed": bool,
        }
    """
    sess_opts = ort.SessionOptions()
    sess_opts.log_severity_level = 3  # suppress ORT INFO/WARNING noise
    session = ort.InferenceSession(str(onnx_path), sess_opts=sess_opts)

    disagreements = 0
    max_delta = 0.0

    rng = np.random.default_rng(seed=42)  # deterministic for reproducibility

    print(f"  Parity check [{label}]: {PARITY_SAMPLES} random inputs ...")

    for i in range(PARITY_SAMPLES):
        x_np = rng.standard_normal((1, 3, INPUT_SIZE, INPUT_SIZE)).astype(np.float32)
        x_pt = torch.from_numpy(x_np).to(device)

        with torch.no_grad():
            pt_logits = model(x_pt).cpu().numpy()  # shape [1, 6]

        ort_logits = session.run(["logits"], {"input": x_np})[0]  # shape [1, 6]

        delta = float(np.abs(pt_logits - ort_logits).max())
        max_delta = max(max_delta, delta)

        pt_class = int(np.argmax(pt_logits))
        ort_class = int(np.argmax(ort_logits))
        if pt_class != ort_class:
            disagreements += 1
            print(f"    Sample {i:02d}: MISMATCH pt={CLASS_NAMES[pt_class]} ort={CLASS_NAMES[ort_class]}")

    passed = (disagreements <= MAX_CLASS_DISAGREEMENTS) and (max_delta < max_logit_delta)

    status = "PASS" if passed else "FAIL"
    delta_note = f"(threshold: {max_logit_delta:.0e})" if max_logit_delta != float("inf") else "(unchecked for INT8)"
    print(f"  [{label}] {status}: disagreements={disagreements}/{PARITY_SAMPLES}, max_delta={max_delta:.2e} {delta_note}")

    return {"disagreements": disagreements, "max_logit_delta": max_delta, "passed": passed}


def main() -> int:
    parser = argparse.ArgumentParser(description="Export dermatology model to ONNX")
    parser.add_argument(
        "--skip-int8",
        action="store_true",
        help="Skip INT8 quantization (faster for iteration)",
    )
    args = parser.parse_args()

    device = torch.device("cpu")  # export always on CPU for portability

    fp32_raw_path = OUTPUT_DIR / "dermatology_fp32_raw.onnx"
    fp32_sim_path = OUTPUT_DIR / "dermatology_fp32.onnx"
    int8_path = OUTPUT_DIR / "dermatology_int8.onnx"

    print("=== Step 1: Load PyTorch model ===")
    model = load_pytorch_model(CHECKPOINT_PATH, device)

    print("\n=== Step 2: Export FP32 ONNX ===")
    export_fp32(model, fp32_raw_path, device)

    print("\n=== Step 3: Simplify with onnxsim ===")
    simplify_onnx(fp32_raw_path, fp32_sim_path)

    # Remove raw export -- it may have an external .data sidecar (torch splits
    # large models), and both files are intermediate artifacts not needed after
    # onnxsim produces the self-contained simplified model.
    fp32_raw_path.unlink(missing_ok=True)
    fp32_raw_data_path = fp32_raw_path.with_suffix(".onnx.data")
    if fp32_raw_data_path.exists():
        fp32_raw_data_path.unlink()

    print("\n=== Step 4: Parity check FP32 ===")
    fp32_result = run_parity_check(
        model, fp32_sim_path, device, "FP32", max_logit_delta=FP32_MAX_LOGIT_DELTA
    )

    if not fp32_result["passed"]:
        print("\nFP32 parity FAILED -- aborting.")
        print(f"  Disagreements: {fp32_result['disagreements']}/{PARITY_SAMPLES}")
        print(f"  Max logit delta: {fp32_result['max_logit_delta']:.2e} (threshold: {FP32_MAX_LOGIT_DELTA:.0e})")
        return 1

    if not args.skip_int8:
        print("\n=== Step 5: Quantize to INT8 ===")
        quantize_int8(fp32_sim_path, int8_path)

        print("\n=== Step 6: Parity check INT8 ===")
        int8_result = run_parity_check(
            model, int8_path, device, "INT8", max_logit_delta=INT8_MAX_LOGIT_DELTA
        )

        if not int8_result["passed"]:
            print("\nINT8 class disagreements detected -- INT8 model NOT suitable.")
            print(f"  Disagreements: {int8_result['disagreements']}/{PARITY_SAMPLES}")
            print(f"  Max logit delta: {int8_result['max_logit_delta']:.2e}")
            print("  NOTE: EfficientNet depthwise convs are known to degrade under INT8.")
            print("  Consider FP32-only deployment or QAT fine-tuning if INT8 is required.")
            return 1

    print("\n=== Summary ===")
    print(f"  FP32: {fp32_sim_path.stat().st_size / 1_048_576:.1f} MB  [{fp32_sim_path.name}]")
    if not args.skip_int8 and int8_path.exists():
        int8_size = int8_path.stat().st_size / 1_048_576
        fp32_size = fp32_sim_path.stat().st_size / 1_048_576
        ratio = fp32_size / int8_size
        print(f"  INT8: {int8_size:.1f} MB  [{int8_path.name}]  ({ratio:.1f}x smaller than FP32)")
    print("\nGO -- ONNX export successful, parity checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
