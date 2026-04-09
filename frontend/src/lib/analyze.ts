import { getEffectiveServerUrl } from "./connection";
import { getTemplateNarrative } from "../data/templates";
import type { AnalyzeResponse } from "../types";

// ONNX module loaded on demand — avoids ~20MB download until the offline
// path is actually needed (dynamic import splits it into a separate chunk).
let onnxModule: typeof import("./onnx") | null = null;

async function getOnnx() {
  if (!onnxModule) {
    onnxModule = await import("./onnx");
  }
  return onnxModule;
}

// Urgency classification rules that mirror backend/src/clinical/urgency.py.
// Duplicating these here is intentional: the offline path must be self-contained.
// If you update urgency rules on the backend, update this function too.
const URGENCY_EMERGENCY = new Set([
  "Leishmania",
  "Plasmodium",
  "Toxoplasma",
  "Trypanosome",
]);
const URGENCY_SOON = new Set([
  "demodicosis",
  "Scabies",
  "ringworm",
  "Fungal_infections",
  "Babesia",
  "Trichomonad",
]);
const URGENCY_MONITOR = new Set([
  "Dermatitis",
  "Hypersensitivity_Allergic_Dermatitis",
  "Flea_Allergy",
]);
const URGENCY_HEALTHY = new Set(["Healthy", "Health", "RBCs", "Leukocyte"]);

const CONFIDENCE_THRESHOLD_HEALTHY = 0.85;
const CONFIDENCE_THRESHOLD_MINIMUM = 0.7;

function determineUrgency(
  label: string,
  confidence: number,
): AnalyzeResponse["urgency"] {
  // Low-confidence results default to "soon" regardless of class —
  // the model is uncertain enough that precaution is warranted.
  if (confidence < CONFIDENCE_THRESHOLD_MINIMUM) return "soon";
  if (URGENCY_EMERGENCY.has(label)) return "emergency";
  if (URGENCY_HEALTHY.has(label) && confidence >= CONFIDENCE_THRESHOLD_HEALTHY)
    return "healthy";
  if (URGENCY_SOON.has(label)) return "soon";
  if (URGENCY_MONITOR.has(label)) return "monitor";
  return "soon";
}

export async function analyzeImage(
  image: File,
  species: "canine" | "feline",
  module: "dermatology" | "parasites",
  onStatus?: (status: "loading_model" | "analyzing") => void,
): Promise<AnalyzeResponse> {
  const serverUrl = getEffectiveServerUrl();

  // Track why the server path failed so the UI can surface it.
  let fallbackReason: string | undefined;

  // Always try the server first when a URL is configured.
  // Only fall through to offline on network or server errors.
  if (serverUrl) {
    try {
      const form = new FormData();
      form.append("image", image);
      form.append("species", species);
      form.append("module", module);

      const res = await fetch(`${serverUrl}/api/v1/analyze`, {
        method: "POST",
        body: form,
        signal: AbortSignal.timeout(60000),
      });

      if (res.ok) {
        return res.json() as Promise<AnalyzeResponse>;
      }
      // Non-2xx from server — capture the reason and fall through
      const detail = await res.text().catch(() => "");
      fallbackReason = `Server returned ${res.status}${detail ? `: ${detail.slice(0, 120)}` : ""}`;
      console.warn("[analyzeImage] server failed, falling back to offline.", fallbackReason);
    } catch (err) {
      // Network error (timeout, DNS failure, etc.)
      fallbackReason =
        err instanceof DOMException && err.name === "TimeoutError"
          ? "Server request timed out (60 s)"
          : `Network error: ${err instanceof Error ? err.message : String(err)}`;
      console.warn("[analyzeImage] server unreachable, falling back to offline.", fallbackReason);
    }
  }

  // Offline path: ONNX classifier + template narrative.
  // Only the canine dermatology model has been exported to ONNX.
  // Parasites would require a separate export (tracked as future work).
  if (module !== "dermatology") {
    throw new Error(
      "Blood sample analysis requires a Clinic Hub connection. Only skin lesion analysis is available offline.",
    );
  }

  const onnx = await getOnnx();
  if (!onnx.isModelLoaded()) {
    onStatus?.("loading_model");
    try {
      await onnx.loadModel();
    } catch {
      throw new Error(
        "Offline model could not be loaded. Connect to a Clinic Hub for image analysis.",
      );
    }
    onStatus?.("analyzing");
  }

  const classification = await onnx.classifyImage(image);
  const narrative = getTemplateNarrative(classification.label, classification.prediction_quality);

  // Inconclusive offline results get urgency "unknown" (spec D10)
  const urgency = classification.prediction_quality === "inconclusive"
    ? "unknown" as const
    : determineUrgency(classification.label, classification.confidence);

  return {
    analysis_id: crypto.randomUUID(),
    classification,
    narrative,
    urgency,
    rag_matches: [],
    pharma: [],
    source: "local_ai",
    fallback_reason: fallbackReason,
    prediction_quality: classification.prediction_quality,
    entropy: classification.entropy,
  };
}
