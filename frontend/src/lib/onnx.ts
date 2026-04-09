import * as ort from "onnxruntime-web";

const MODEL_PATH = "/models/dermatology_int8.onnx";
const INPUT_SIZE = 384;
// ImageNet normalization constants — must match timm defaults used during training
const MEAN: [number, number, number] = [0.485, 0.456, 0.406];
const STD: [number, number, number] = [0.229, 0.224, 0.225];

// Prediction quality thresholds (spec D1, D7).
// Synced with vision-service/src/config.py — update both together.
const CONFIDENT_THRESHOLD = 0.80;
const INCONCLUSIVE_THRESHOLD = 0.50;

// Class labels in the exact order the model outputs them.
// Source: vision-service/src/models/dermatology.py CLASS_NAMES
const CLASS_NAMES = [
  "demodicosis",
  "Dermatitis",
  "Fungal_infections",
  "Healthy",
  "Hypersensitivity_Allergic_Dermatitis",
  "ringworm",
] as const;

let session: ort.InferenceSession | null = null;
// Prevents duplicate concurrent load calls
let loadPromise: Promise<void> | null = null;
let loadError: string | null = null;

export async function loadModel(): Promise<void> {
  if (session) return;
  if (loadPromise) return loadPromise;

  loadError = null;
  loadPromise = (async () => {
    try {
      // Single-thread WASM for broadest device compatibility (no SharedArrayBuffer required)
      ort.env.wasm.numThreads = 1;
      session = await ort.InferenceSession.create(MODEL_PATH, {
        executionProviders: ["wasm"],
        graphOptimizationLevel: "all",
      });
    } catch (err) {
      loadError = err instanceof Error ? err.message : "Failed to load model";
      loadPromise = null; // Allow retry on next call
      throw err;
    }
  })();

  return loadPromise;
}

export function isModelLoaded(): boolean {
  return session !== null;
}

export function getLoadError(): string | null {
  return loadError;
}

async function preprocessImage(file: File): Promise<ort.Tensor> {
  const img = await createImageBitmap(file);
  const canvas = new OffscreenCanvas(INPUT_SIZE, INPUT_SIZE);
  const ctx = canvas.getContext("2d");
  if (!ctx) {
    throw new Error("OffscreenCanvas 2D context unavailable");
  }
  ctx.drawImage(img, 0, 0, INPUT_SIZE, INPUT_SIZE);
  const imageData = ctx.getImageData(0, 0, INPUT_SIZE, INPUT_SIZE);
  const pixels = imageData.data; // RGBA uint8, length = INPUT_SIZE * INPUT_SIZE * 4

  // Reorder HWC RGBA uint8 → CHW RGB float32 and apply ImageNet normalization.
  // Loop bound c < 3 guarantees c is always a valid index into the MEAN/STD tuples.
  const float32 = new Float32Array(3 * INPUT_SIZE * INPUT_SIZE);
  for (let c = 0; c < 3; c++) {
    const mean = MEAN[c as 0 | 1 | 2];
    const std = STD[c as 0 | 1 | 2];
    for (let i = 0; i < INPUT_SIZE * INPUT_SIZE; i++) {
      float32[c * INPUT_SIZE * INPUT_SIZE + i] =
        (pixels[i * 4 + c]! / 255 - mean) / std;
    }
  }

  return new ort.Tensor("float32", float32, [1, 3, INPUT_SIZE, INPUT_SIZE]);
}

function softmax(logits: Float32Array): number[] {
  const max = Math.max(...logits);
  const exps = Array.from(logits).map((x) => Math.exp(x - max));
  const sum = exps.reduce((a, b) => a + b, 0);
  return exps.map((x) => x / sum);
}

export interface OnnxClassification {
  label: string;
  confidence: number;
  differentials: Array<{ label: string; confidence: number }>;
  prediction_quality: "confident" | "low_confidence" | "inconclusive";
  entropy: number;
}

export async function classifyImage(file: File): Promise<OnnxClassification> {
  if (!session) {
    await loadModel();
  }
  if (!session) {
    throw new Error("Model not available");
  }

  const tensor = await preprocessImage(file);
  // Input node name confirmed by inspecting the exported ONNX graph: "input"
  const results = await session.run({ input: tensor });
  const outputTensor = results["logits"];
  if (!outputTensor) {
    throw new Error("ONNX model did not return expected 'logits' output");
  }
  const logits = outputTensor.data as Float32Array;
  const probs = softmax(logits);

  const indexed = CLASS_NAMES.map((name, i) => ({
    label: name as string,
    confidence: probs[i] ?? 0,
  }));
  indexed.sort((a, b) => b.confidence - a.confidence);

  // Entropy of full softmax distribution — logged for OOD analysis (spec D4).
  const entropy = -probs.reduce((sum, p) => sum + (p > 1e-12 ? p * Math.log(p) : 0), 0);

  // CLASS_NAMES is non-empty (6 entries) so indexed is guaranteed non-empty after map
  const top = indexed[0]!;
  const prediction_quality: OnnxClassification["prediction_quality"] =
    top.confidence >= CONFIDENT_THRESHOLD
      ? "confident"
      : top.confidence >= INCONCLUSIVE_THRESHOLD
        ? "low_confidence"
        : "inconclusive";

  return {
    label: top.label,
    confidence: top.confidence,
    differentials: indexed.slice(1, 4),
    prediction_quality,
    entropy: Math.round(entropy * 10000) / 10000,
  };
}
