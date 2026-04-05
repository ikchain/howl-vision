import { getServerUrl } from "./connection";
import type { AnalyzeResponse } from "../types";

export async function analyzeImage(
  image: File,
  species: "canine" | "feline",
  module: "dermatology" | "parasites",
): Promise<AnalyzeResponse> {
  const serverUrl = getServerUrl();
  if (!serverUrl) {
    // Task 8 (ONNX offline analysis) will intercept here before the throw.
    throw new Error("No server connected. Connect to a Clinic Hub for image analysis.");
  }

  const form = new FormData();
  form.append("image", image);
  form.append("species", species);
  form.append("module", module);

  const res = await fetch(`${serverUrl}/api/v1/analyze`, {
    method: "POST",
    body: form,
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`Analysis failed (${res.status}): ${text || res.statusText}`);
  }

  return res.json();
}
