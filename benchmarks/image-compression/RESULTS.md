# Image-Compression Accuracy Evaluation

**Protocol:** AC-10 with v3 thresholds (full-set n=433, McNemar exact, asymmetric ECE).
**Dataset:** canine dermatology held-out test split, n=433, seed=42
**Generated:** 2026-04-21T16:09:12.731550+00:00
**Baseline:** single-generation JPEG decode (source files are `.jpg`; **not lossless**)
**Determinism:** `cudnn.deterministic=True`, `cudnn.benchmark=False`, torch/numpy/random seeded

## Noise floor (baseline vs baseline_repeat)

Running the SAME input through the pipeline twice produces **0 label flips** (p95 |softmax delta| = 0.00000, max = 0.00000). These are NOT compression-caused; they reflect intrinsic non-determinism (CUDA kernel selection, floating-point order).

Compression-attributable flips per Q level = `max(0, total_flips_Q - 0)`.

## AC-10 thresholds (spec v3, merge-blocking)

- Label flips: McNemar exact p ≥ 0.05 AND flip_rate_point < 0.02 AND no directional degradation at p<0.05
- ECE delta (asymmetric): regression ≤ 0.005; improvements unconditionally accepted
- Gate FRR delta: |Δ| < 2.0 pp
- ONNX INT8 disagreement delta: |Δ| < 1.0 pp
- 95th-pct |softmax delta|: < 0.05

*Caveat on McNemar:* at small discordant counts (b+c < 10) the exact test has
limited power; p=1.00 means symmetric noise is indistinguishable from zero effect,
not that equivalence is proven. The merge gate is the *combined* rule above,
not the p-value alone.

## Q = 85

**Overall:** PASS  
**McNemar exact p:** 1.0000  (2 baseline-correct-compressed-wrong, 3 reverse)  **Flips attributable to compression (total − noise floor):** 7

| Metric | Value | Threshold | Result |
|--------|-------|-----------|--------|
| Directional degradation (compression one-sidedly worse) | no | must be 'no' (or McNemar p ≥ 0.05) | PASS |
| Label flip rate (point) | 0.016166 | 0.02 | PASS |
| ECE delta (direction: improved) | -0.006435 | ≤ 0.005 (regression only) | PASS |
| |Gate FRR delta| (pp) | 0.230947 | 2.0 | PASS |
| |ONNX INT8 disagreement delta| (pp) | 0.692841 | 1.0 | PASS |
| 95th-pct |softmax delta_top1| | 0.044749 | 0.05 | PASS |

**Softmax delta_top1 distribution:**
- median: 0.00012, p90: 0.03088, p95: 0.04475, p99: 0.09591, max: 0.16170

**Softmax KL divergence distribution:**
- median: 0.00002, p90: 0.00506, p95: 0.00885, p99: 0.04989, max: 0.09311

**Calibration:** ECE_baseline = 0.03138, ECE_compressed = 0.02494, Delta = -0.00643 (compressed BETTER calibrated than baseline)
**Gate:** FRR_baseline = 4.85%, FRR_compressed = 4.62%, Delta = -0.231 pp
**ONNX INT8:** disagree_baseline = 3.46%, disagree_compressed = 2.77%, Delta = -0.693 pp

## Q = 90

**Overall:** PASS  
**McNemar exact p:** 1.0000  (2 baseline-correct-compressed-wrong, 1 reverse)  **Flips attributable to compression (total − noise floor):** 5

| Metric | Value | Threshold | Result |
|--------|-------|-----------|--------|
| Directional degradation (compression one-sidedly worse) | no | must be 'no' (or McNemar p ≥ 0.05) | PASS |
| Label flip rate (point) | 0.011547 | 0.02 | PASS |
| ECE delta (direction: improved) | -0.005345 | ≤ 0.005 (regression only) | PASS |
| |Gate FRR delta| (pp) | 0.230947 | 2.0 | PASS |
| |ONNX INT8 disagreement delta| (pp) | 0.230947 | 1.0 | PASS |
| 95th-pct |softmax delta_top1| | 0.030049 | 0.05 | PASS |

**Softmax delta_top1 distribution:**
- median: 0.00006, p90: 0.01701, p95: 0.03005, p99: 0.04812, max: 0.09842

**Softmax KL divergence distribution:**
- median: 0.00001, p90: 0.00194, p95: 0.00370, p99: 0.00905, max: 0.02073

**Calibration:** ECE_baseline = 0.03138, ECE_compressed = 0.02603, Delta = -0.00535 (compressed BETTER calibrated than baseline)
**Gate:** FRR_baseline = 4.85%, FRR_compressed = 4.62%, Delta = -0.231 pp
**ONNX INT8:** disagree_baseline = 3.46%, disagree_compressed = 3.70%, Delta = +0.231 pp

## Q = 95

**Overall:** PASS  
**McNemar exact p:** 1.0000  (0 baseline-correct-compressed-wrong, 1 reverse)  **Flips attributable to compression (total − noise floor):** 2

| Metric | Value | Threshold | Result |
|--------|-------|-----------|--------|
| Directional degradation (compression one-sidedly worse) | no | must be 'no' (or McNemar p ≥ 0.05) | PASS |
| Label flip rate (point) | 0.004619 | 0.02 | PASS |
| ECE delta (direction: improved) | -0.002343 | ≤ 0.005 (regression only) | PASS |
| |Gate FRR delta| (pp) | 0.692841 | 2.0 | PASS |
| |ONNX INT8 disagreement delta| (pp) | 0.230947 | 1.0 | PASS |
| 95th-pct |softmax delta_top1| | 0.015917 | 0.05 | PASS |

**Softmax delta_top1 distribution:**
- median: 0.00003, p90: 0.00975, p95: 0.01592, p99: 0.02908, max: 0.08360

**Softmax KL divergence distribution:**
- median: 0.00000, p90: 0.00055, p95: 0.00094, p99: 0.00268, max: 0.01567

**Calibration:** ECE_baseline = 0.03138, ECE_compressed = 0.02903, Delta = -0.00234 (compressed BETTER calibrated than baseline)
**Gate:** FRR_baseline = 4.85%, FRR_compressed = 4.16%, Delta = -0.693 pp
**ONNX INT8:** disagree_baseline = 3.46%, disagree_compressed = 3.23%, Delta = -0.231 pp

## Verdict

**Recommended quality:** Q = 85 (lowest Q that passes all thresholds).
Configure `compressImage` default accordingly in `frontend/src/lib/image.ts`.
