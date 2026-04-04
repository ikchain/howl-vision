# Vision Models Validation Protocol
# Hackathon Gemma 4 Good — Technical Depth Track

**Date drafted:** 2026-04-04  
**Status:** Protocol definition (pre-execution)

---

## 0. Ground Truth About What We Actually Have

Honest status of the "claimed" numbers before running anything:

| Model | Claimed | Source | Provenance | Status |
|---|---|---|---|---|
| Dermatology | 93.49% acc | checkpoint `metrics` key | Val split, epoch 9 | NOT held-out test |
| Parasites | 99.87% acc | checkpoint `metrics` key | Val split, epoch 14 | NOT held-out test |
| Segmentation | 99.99% Dice | checkpoint `best_metric` | Val split, epoch 34 | NOT held-out test |

The training script does run the best checkpoint on test_loader at the end and logs results, but
does NOT persist those metrics to the checkpoint file. The saved checkpoint stores val metrics only.
Every claimed number is a validation-set number selected by early stopping on that same validation
set — indirect optimistic bias from hyperparameter selection exists. Not fraud, but not a formal
held-out test result.

**What this protocol produces:** Formally executed inference on held-out test splits using frozen
model weights, with no information from the test set used in any model or threshold decisions.

---

## 1. Falsifiable Hypotheses

Defined BEFORE running inference. Thresholds are not adjusted after seeing results.

### H-DERMA
- H0: Dermatology test accuracy <= 0.85
- H1: Accuracy > 0.85, F1-macro > 0.80; Hypersensitivity (n=29) reported separately with Wilson CI only
- If H1 fails, report the honest number.

### H-PARA
- H0: Parasites test accuracy <= 0.95
- H1: Accuracy > 0.95, F1-macro > 0.95
- The 99.87% val metric is from a standardized microscopy dataset with low intra-class variability.
  High test accuracy is expected but does NOT imply generalization to real clinical images.

### H-SEG
- H0: No independent test evaluation is possible
- H1: If original porcine ultrasound dataset is accessible, independent Dice/IoU can be measured
- If the dataset is not accessible locally: report val metric with explicit caveat.
  Do NOT fabricate a test result.

---

## 2. Metrics Per Model Type

### 2.1 Classification Models (Dermatology, Parasites)

Primary metrics — all must be reported:

| Metric | Justification |
|---|---|
| Accuracy (overall) | Baseline comparability |
| F1-macro | Equal weight per class — sensitive to minority class failure |
| F1-weighted | Proportional to class frequency — reflects deployment reality |
| Per-class precision, recall, F1 | Simpson's paradox: aggregate hides per-class collapse |
| Cohen's Kappa | Corrects for chance agreement |
| AUROC (macro OvR) | Threshold-independent, uses softmax probabilities directly |
| Brier score (macro) | Proper scoring rule for calibration |

Why both macro and weighted F1: On the parasites dataset they will diverge substantially.
Reporting only weighted F1 lets Trichomonad (n=1015) dominate and hides Plasmodium (n=85) failure.
Both must be reported with explicit explanation of the difference.

Calibration metrics (mandatory because the system outputs high/medium/low confidence):

| Metric | Implementation |
|---|---|
| ECE (Expected Calibration Error) | 10-bin equal-width. Report with sensitivity check at 5 and 15 bins. |
| MCE (Maximum Calibration Error) | Single worst bin — flags catastrophic overconfidence |
| Reliability diagram | Confidence vs actual accuracy, with confidence histogram |
| Selective prediction curve | At coverage thresholds 100%, 90%, 80%, 70%, 60%: report accuracy on answered subset |

Mandatory baselines for every aggregate metric:

| Baseline | What it measures |
|---|---|
| Majority class (always predict most frequent) | Absolute floor |
| Uniform random | Statistical floor |
| Prior-proportional random (seed=42) | Random sampler matching class frequencies |
| Perfect calibration diagonal | Reference for reliability diagram |

### 2.2 Segmentation Model (UNet + EfficientNet-B0)

Primary metrics:

| Metric | Justification |
|---|---|
| Dice coefficient (foreground class) | Standard binary segmentation metric |
| IoU / Jaccard (foreground) | Stricter than Dice, penalizes false positives harder |
| Precision (pixel-level) | Fraction of predicted spinal cord pixels that are correct |
| Recall (pixel-level) | Fraction of actual spinal cord pixels found |
| HD95 (Hausdorff, 95th percentile) | Boundary quality — catches cases where Dice is high but edges are wrong |
| Background Dice | Verify the model is not trivially correct on the dominant class |

Segmentation baselines:

| Baseline | Expected behavior |
|---|---|
| All-background | Dice=0 on foreground, but overall accuracy high due to class imbalance |
| All-foreground | High recall, low precision |
| Center-circle heuristic | Naive anatomical prior — spinal cord is often near center in ultrasound |

---

## 3. Handling Class Imbalance

### Dermatology: Hypersensitivity n=29

Wilson CI formula for binary proportion p at confidence level z:

  CI = (p + z^2/2n +/- z * sqrt(p*(1-p)/n + z^2/4n^2)) / (1 + z^2/n)
  where z=1.96 for 95%

At n=29 and p=0.90: CI approximately [0.73, 0.97] — width of 0.24. This is the honest range.

Protocol for Hypersensitivity:
- Report per-class F1 with explicit n=29 and Wilson CI
- Do NOT report point estimate alone
- Writeup language: "Hypersensitivity class (n=29, insufficient for stable estimation):
  F1=X.XX [95% CI: X.XX-X.XX]. Results should be interpreted with caution."
- Do NOT exclude this class from aggregate metrics (exclusion would inflate macro F1)
- For the hackathon writeup, this is a methodological strength: it demonstrates honest evaluation

Statistical power at n=29:
- To detect a true F1 difference of 0.10 (meaningful clinical effect) at 80% power, alpha=0.05:
  n_required approximately 85 per class minimum
- At n=29, we can detect large effects (Cohen's h > 0.52) but not medium ones
- State this explicitly in the writeup

### Parasites: Plasmodium n=85, Babesia n=118

Workable sample sizes. Wilson CIs at n=85: for p=0.95, CI approximately [0.88, 0.98].
Report CIs even here — the range [0.88, 0.98] is informative.

The suspicious signal: Parasites val accuracy is 99.87% with near-perfect per-class F1.
This is a standardized microscopy dataset (Kaggle parasite classification, known-clean images).
Do not generalize to clinical microscopy — real lab slides have artifacts, staining variation,
and imaging noise not present in this dataset. Report this limitation explicitly.

---

## 4. Confidence Intervals — Full Protocol

Wilson CI: Use for all proportions (precision, recall, per-class accuracy).

Bootstrap CI for F1 and composite metrics (F1 is not a proportion):
- B=1000 iterations, seed=42
- Per iteration: sample n_class images WITH replacement from test set, per class
- Sort 1000 values, take [2.5%, 97.5%] as 95% CI

When CIs are too wide to draw conclusions:
- At n=29, CI for F1 spans at minimum +/-0.12
- CAN say: "The model correctly identifies Hypersensitivity at greater than chance level"
- CANNOT say: "The model achieves reliable Hypersensitivity detection"
- Report the point estimate AND the CI. Let the reader judge.

---

## 5. Segmentation: No Test Split Available

Decision tree (execute in order):
1. Check if the IEEE Porcine Ultrasound dataset is accessible locally
2. Check if any segmentation images+masks exist in data/datasets/
3. If accessible: create a fresh test split (stratified, 10%, seed=42) ensuring no overlap with
   the training split defined in the original create_splits logic
4. If NOT accessible: do not fabricate test numbers

What to report if dataset is inaccessible:

  "Segmentation model (UNet + EfficientNet-B0 encoder) was trained on the IEEE Porcine Spinal
   Cord Ultrasound dataset. Best validation Dice: 0.9999 (val split, epoch 34, seed=42).
   No independent held-out test evaluation was performed for this writeup as the original dataset
   is not co-located with the evaluation environment. The val metric was selected by early stopping
   on the validation set (patience=20), which introduces optimistic bias via indirect leakage from
   hyperparameter selection. We report this metric with explicit caveat: it is a validation result,
   not an independent test result."

This is the honest answer. It is defensible to any technical reviewer.

---

## 6. Visualizations — Required

Per-model confusion matrices:
- Normalized (row-wise, i.e., recall per class) AND raw counts in same figure
- Each cell shows both "n=X" and "X%"
- Sort classes by frequency descending

Reliability diagrams (one per classification model):
- 10-bin calibration curve
- Histogram of confidence distribution below (twin-axis)
- Reference diagonal (perfect calibration)
- Mandatory because the system maps softmax to high/medium/low confidence

ROC curves (macro OvR):
- All-class OvR curves on single figure, per-class faded
- Bold macro-average with AUROC in legend
- Random baseline diagonal

Selective prediction curve:
- X: coverage fraction (descending from 1.0 to 0.5)
- Y: accuracy on the answered subset at each coverage threshold
- Threshold = max softmax probability
- This validates whether the high/medium/low confidence mapping has empirical support

Segmentation (if data available):
- 8-sample grid: original | ground truth mask | predicted mask | overlay (alpha=0.5)
- Selection: 2 best Dice, 2 median Dice, 2 worst Dice, 2 failure cases
- Do NOT show only best results

---

## 7. Calibration Analysis

The system maps softmax probabilities to high/medium/low confidence bands that are shown to
veterinary users. If those bands are miscalibrated, the system is misleading clinicians about
the certainty of its predictions. This is a patient safety issue and a strong technical narrative.

What to measure:
1. ECE: lower is better. For a well-calibrated model on 6-class problems, ECE < 0.05 is good.
   ECE > 0.10 means the confidence numbers are substantially misleading.

2. Per-band accuracy: For the thresholds used by the system (high > 0.85, medium 0.60-0.85,
   low < 0.60), report the actual observed accuracy in each band.
   Calibration gap = stated_confidence - observed_accuracy

3. Overconfidence vs underconfidence:
   - Overconfident (model says 90%, is right 75%): dangerous in medical context
   - Underconfident (model says 70%, is right 85%): annoying but safer
   Report which direction the bias runs.

---

## 8. Statistical Power Summary

| Class | n | Can claim | Cannot claim |
|---|---|---|---|
| Hypersensitivity | 29 | Large effects (h > 0.52), point estimate with wide CI | Medium effects, stable F1 estimate |
| Fungal_infections | 54 | Medium-large effects, CI width ~0.13 | Small effects |
| Dermatitis | 66 | Medium effects, CI width ~0.12 | Very small effects |
| Healthy | 69 | Medium effects | Very small effects |
| demodicosis | 100 | Medium effects, CI width ~0.10 | Very small effects |
| ringworm | 115 | Small-medium effects | Very small effects |
| Dermatology overall | 433 | Small-medium effects, CI width ~0.05 | Very small effects |
| Plasmodium | 85 | Medium effects, CI width ~0.11 | Small effects |
| Parasites overall | 3032 | Very small effects, CI width ~0.02 | Essentially all practically meaningful effects |

---

## 9. What NOT to Claim

| Forbidden Claim | Why | Replacement |
|---|---|---|
| "93.49% accuracy" as test result | Val metric from checkpoint, not test split | "Val accuracy: 93.49%. Test accuracy: [run eval]" |
| "99.99% Dice" as formal benchmark | Val metric only | "Best val Dice: 0.9999 (epoch 34). Independent test: not available." |
| "The model is well-calibrated" | Requires ECE measurement | "ECE = X.XX" |
| "The model knows when it is uncertain" | Requires selective prediction curve | "At 80% coverage, accuracy = Y vs Z at full coverage" |
| "State of the art" | No SOTA comparison on same dataset | Omit entirely or cite and compare |
| "Clinically validated" | No deployment or veterinary review | "Evaluated on held-out test set; clinical validation pending" |
| "99.87% indicates strong generalization" | May indicate low dataset diversity | Add explicit limitation on dataset scope |

---

## 10. Implementation Specification

File: benchmarks/vision/eval_vision_models.py

Configuration block (all parameters at top of file, nothing hardcoded in function bodies):

```
SEED = 42
BATCH_SIZE = 32
N_BOOTSTRAP = 1000
ECE_BINS = 10
CONFIDENCE_THRESHOLDS = {"high": 0.85, "medium": 0.60}

DERMA_TEST_DIR = PROJECT_ROOT / "data/datasets/canine/canine/dermatology/test"
PARA_TEST_DIR  = PROJECT_ROOT / "data/datasets/parasites/parasites/test"
SEG_TEST_DIR   = None  # Set if dataset available, do not fabricate

DERMA_MODEL_PATH = PROJECT_ROOT / "data/models/vision/vet_dermatology.pt"
PARA_MODEL_PATH  = PROJECT_ROOT / "data/models/vision/vet_parasites.pt"
SEG_MODEL_PATH   = PROJECT_ROOT / "data/models/vision/vet_segmentation.pt"
```

Preprocessing must exactly match training:
- Dermatology/Parasites: 384x384 RGB, ImageNet normalization
  mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]
- Segmentation: 256x256 grayscale, normalize to [0, 1]

Assertions required in eval script:
- Verify model is in eval() mode before any inference
- Verify image shape matches expected input shape
- Assert n_images per class matches expected test split counts
- Log: predictions, softmax probabilities, ground truth, image paths (for post-hoc error analysis)

Output: benchmarks/vision/results.json with schema documenting source, split, seed,
exact counts, all metrics with CIs, and calibration results.

---

## 11. Writeup Language Reference

Use this language:
- "We evaluate on a held-out test set of N images, split prior to training with seed=42."
- "Per-class results for classes with n < 50 are reported with Wilson 95% confidence intervals
  and should be interpreted with caution given limited statistical power."
- "ECE = X.XX (10-bin), indicating [well/moderately/poorly] calibrated confidence estimates."
- "Selective prediction: accuracy improves from X% at full coverage to Y% when deferring
  the Z% of predictions with lowest confidence."

Avoid this language:
- "achieves" (implies causality) -- use "obtains" or "scores"
- "the model understands" -- use "the model correctly classifies"
- "robust" without specifying robust to what
- "state of the art" without citation and comparison
- "validated" without specifying the split and protocol

---

## 12. Execution Order

1. Implement eval_vision_models.py following this protocol
2. Run dermatology eval (n=433, fast, directly tests the 93.49% claim)
3. Run parasites eval (n=3032, confirms or challenges the 99.87% claim)
4. Attempt segmentation: check dataset availability, apply caveat if unavailable
5. Generate all required visualizations
6. Write results.json
7. Update writeup with exact numbers and CIs

Time estimate: 2h implementation + 30min inference + 1h visualization = 3.5h total

---

## Appendix: Power Analysis Reference

| n | Detectable effect (80% power, alpha=0.05) | Proportion CI width (95%) |
|---|---|---|
| 29 | Cohen's h > 0.52 (large) | +/- 0.18 |
| 54 | Cohen's h > 0.38 (medium-large) | +/- 0.13 |
| 85 | Cohen's h > 0.30 (medium) | +/- 0.11 |
| 100 | Cohen's h > 0.28 (medium) | +/- 0.10 |
| 433 | Cohen's h > 0.13 (small-medium) | +/- 0.05 |
| 3032 | Cohen's h > 0.05 (very small) | +/- 0.02 |

Cohen's h: h = 2*arcsin(sqrt(p1)) - 2*arcsin(sqrt(p2))
