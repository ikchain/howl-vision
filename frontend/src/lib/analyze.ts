import { getServerUrl } from "./connection";
import { classifyImage, isModelLoaded, loadModel } from "./onnx";
import { getTemplateNarrative } from "../data/templates";
import type { AnalyzeResponse } from "../types";

// Pre-load ONNX model in the background on module initialization.
// The 20MB download happens once and is then cached by the service worker.
loadModel().catch(() => {
  // Failure is non-fatal at startup — the offline path will retry on demand
  // and surface an explicit error if the model is still unavailable at that point.
});

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
const URGENCY_HEALTHY = new Set(["Healthy", "RBCs", "Leukocyte"]);

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
): Promise<AnalyzeResponse> {
  const serverUrl = getServerUrl();

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
      });

      if (res.ok) {
        return res.json() as Promise<AnalyzeResponse>;
      }
      // Non-2xx from server — fall through to offline path below
    } catch {
      // Network error (timeout, DNS failure, etc.) — fall through to offline
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

  if (!isModelLoaded()) {
    try {
      await loadModel();
    } catch {
      throw new Error(
        "Offline model could not be loaded. Connect to a Clinic Hub for image analysis.",
      );
    }
  }

  const classification = await classifyImage(image);
  const urgency = determineUrgency(classification.label, classification.confidence);
  const narrative = getTemplateNarrative(classification.label);

  return {
    analysis_id: crypto.randomUUID(),
    classification,
    narrative,
    urgency,
    rag_matches: [],
    pharma: [],
    source: "local_ai",
  };
}
